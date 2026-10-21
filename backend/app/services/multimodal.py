"""Real multimodal ingestion, processing, evidence and safety pipeline."""
import asyncio,base64,hashlib,io,json,logging,re,shutil,socket,subprocess,tempfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from PIL import Image
from sqlalchemy import func,or_,select,update
from uuid import uuid4
from openai import AsyncOpenAI
from app.core.runtime_settings import RuntimeSettings, use_settings
from app.core.private_clients import managed_model_client, model_http_client
from app.core.model_compat import chat_options
from app.services.service_settings import owner_settings
from app.core.database import _get_sessionmaker
from app.models.enterprise import TenantQuota
from app.models.intelligence import ModelUsage
from app.models.multimodal import MediaAsset,MediaEvidence,MediaProcessingRun
from app.models.orchestration import ModelRoute
from app.services.knowledge import safe_filename,storage

settings=RuntimeSettings();UTC=timezone.utc
MIME={".png":("image","image/png"),".jpg":("image","image/jpeg"),".jpeg":("image","image/jpeg"),".webp":("image","image/webp"),".wav":("audio","audio/wav"),".mp3":("audio","audio/mpeg"),".m4a":("audio","audio/mp4"),".ogg":("audio","audio/ogg"),".mp4":("video","video/mp4"),".mov":("video","video/quicktime"),".webm":("video","video/webm")}
def now():return datetime.now(UTC)
def validate_media(name,data):
 ext=Path(name).suffix.lower()
 if ext not in MIME:raise ValueError("unsupported media format")
 if not data:raise ValueError("media file is empty")
 if len(data)>settings.MEDIA_MAX_FILE_MB*1024*1024:raise ValueError("media file exceeds configured limit")
 kind,mime=MIME[ext]
 if kind=="image":
  try:
   image=Image.open(io.BytesIO(data));image.verify()
  except Exception as exc:raise ValueError("invalid or corrupted image") from exc
 elif ext==".wav" and not(data.startswith(b"RIFF") and data[8:12]==b"WAVE"):raise ValueError("invalid WAV signature")
 elif ext==".ogg" and not data.startswith(b"OggS"):raise ValueError("invalid OGG signature")
 elif ext==".webm" and not data.startswith(b"\x1aE\xdf\xa3"):raise ValueError("invalid WebM signature")
 elif ext in {".mp4",".mov",".m4a"} and b"ftyp" not in data[:32]:raise ValueError("invalid ISO media signature")
 elif ext==".mp3" and not(data.startswith(b"ID3") or (len(data)>2 and data[0]==0xff and data[1]&0xe0==0xe0)):raise ValueError("invalid MP3 signature")
 return kind,mime
def perceptual_hash(data):
 image=Image.open(io.BytesIO(data)).convert("L").resize((9,8));pixels=list(image.get_flattened_data() if hasattr(image,"get_flattened_data") else image.getdata());bits=[]
 for y in range(8):
  for x in range(8):bits.append(pixels[y*9+x]>pixels[y*9+x+1])
 return f"{sum((1<<i) for i,v in enumerate(bits) if v):016x}"
def pii_findings(text):
 rules=(("email",r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),("phone",r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)"),("id_number",r"(?<!\d)\d{17}[\dXx](?!\d)"))
 return [{"type":name,"count":len(re.findall(pattern,text))} for name,pattern in rules if re.search(pattern,text)]
async def route_for(db,asset,task):
 route=await db.scalar(select(ModelRoute).where(ModelRoute.organization_id==asset.organization_id,ModelRoute.workspace_id==asset.workspace_id,ModelRoute.task_type==task,ModelRoute.enabled.is_(True)))
 model=(route.primary_model if route else settings.MEDIA_VISION_MODEL if task in {"vision","video_vision"} else settings.MEDIA_TRANSCRIPTION_MODEL)
 if not model:raise RuntimeError(f"no approved {task} model route configured")
 cost=route.max_cost_cents if route else 25
 quota=await db.get(TenantQuota,asset.organization_id)
 used=float(await db.scalar(select(func.coalesce(func.sum(ModelUsage.cost),0)).where(ModelUsage.organization_id==asset.organization_id)) or 0)
 if quota and used+cost/100>quota.monthly_cost_limit:raise RuntimeError("tenant model cost limit exceeded")
 return model,cost
def client():
 if not settings.LLM_API_KEY:raise RuntimeError("multimodal model credential is not configured")
 # A transport timeout cannot prove the provider did not process or bill the
 # request. Reconciliation owns retries; disable the SDK's implicit replay.
 return AsyncOpenAI(api_key=settings.LLM_API_KEY,base_url=settings.LLM_API_BASE,max_retries=0,timeout=settings.LLM_TIMEOUT_SECONDS,http_client=model_http_client(settings.LLM_TIMEOUT_SECONDS))
async def vision(data,mime,model):
 encoded=base64.b64encode(data).decode();prompt="Extract only visible evidence. Return strict JSON: {ocr:[{text,bbox:[x,y,w,h],confidence}], chart:{type,title,series,findings}, summary}. Do not infer hidden values. Empty arrays when unsupported."
 async with managed_model_client(client) as sdk:
  response=await asyncio.wait_for(sdk.chat.completions.create(model=model,messages=[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":f"data:{mime};base64,{encoded}"}}]}],temperature=0,max_tokens=3000,response_format={"type":"json_object"},**chat_options(settings.LLM_API_BASE,model)),timeout=settings.LLM_TIMEOUT_SECONDS)
  return json.loads(response.choices[0].message.content or "{}")
def validate_transcription(data, name, model):
    if settings.MEDIA_TRANSCRIPTION_PROTOCOL != "qwen_asr":
        return
    # Filetrans/realtime models use different APIs and must never be silently
    # submitted to chat.completions. Limit the encoded payload, not only the file.
    if not (model == "qwen3-asr-flash" or re.fullmatch(r"qwen3-asr-flash-\d{4}-\d{2}-\d{2}", model)):
        raise ValueError("Qwen chat ASR requires qwen3-asr-flash or a dated snapshot; filetrans/realtime APIs are not supported")
    if Path(name).suffix.lower() not in {".wav", ".mp3", ".m4a", ".ogg"}:
        raise ValueError("Qwen chat ASR supports WAV, MP3, M4A or OGG uploads")
    if 4 * ((len(data) + 2) // 3) + 64 >= 10_000_000:
        raise ValueError("Qwen chat ASR requires a Base64 payload under 10 MB and audio under 5 minutes; split the recording first")


async def transcribe(data, name, model):
    validate_transcription(data, name, model)
    async with managed_model_client(client) as sdk:
        if settings.MEDIA_TRANSCRIPTION_PROTOCOL == "qwen_asr":
            mime = MIME[Path(name).suffix.lower()][1]
            encoded = base64.b64encode(data).decode("ascii")
            result = await asyncio.wait_for(sdk.chat.completions.create(
                model=model, messages=[{"role": "user", "content": [{"type": "input_audio", "input_audio": {
                    "data": f"data:{mime};base64,{encoded}"}}]}], stream=False,
                extra_body={"asr_options": {"enable_itn": False}},
            ), timeout=settings.LLM_TIMEOUT_SECONDS)
            text = (result.choices[0].message.content or "").strip()
            if not text:
                raise ValueError("Transcription returned no text")
            # This API has no segment timestamps or diarization. Unknown values
            # remain null; they must not become fabricated 0-second evidence.
            return [{"start": None, "end": None, "text": text, "speaker": "speaker_unknown", "confidence": 0}]
        stream = io.BytesIO(data)
        stream.name = name
        result = await asyncio.wait_for(sdk.audio.transcriptions.create(
            model=model, file=stream, response_format="verbose_json", timestamp_granularities=["segment"],
        ), timeout=settings.LLM_TIMEOUT_SECONDS)
    raw = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    segments = raw.get("segments") or []
    if not segments and raw.get("text"):
        segments = [{"start": None, "end": None, "text": raw["text"]}]
    if not segments:
        raise ValueError("Transcription returned no text")
    return [{"start": float(x["start"]) if x.get("start") is not None else None,
             "end": float(x["end"]) if x.get("end") is not None else None,
             "text": str(x.get("text", "")).strip(), "speaker": x.get("speaker") or "speaker_unknown",
             "confidence": float(x.get("confidence", 0) or 0)} for x in segments if str(x.get("text", "")).strip()]


def transcript_locator(item):
    return {"start_ms": int(item["start"] * 1000) if item["start"] is not None else None,
            "end_ms": int(item["end"] * 1000) if item["end"] is not None else None,
            "speaker": item["speaker"], "confidence": item["confidence"]}
def ffprobe(path):
 exe=shutil.which("ffprobe")
 if not exe:raise RuntimeError("ffprobe is required for video processing")
 out=subprocess.run([exe,"-v","error","-show_entries","format=duration:stream=width,height,codec_type","-of","json",str(path)],capture_output=True,text=True,timeout=30,check=True);return json.loads(out.stdout)
def video_parts(data,suffix):
 ffmpeg=shutil.which("ffmpeg")
 if not ffmpeg:raise RuntimeError("ffmpeg is required for video processing")
 temp=tempfile.TemporaryDirectory();root=Path(temp.name);source=root/f"source{suffix}";source.write_bytes(data);meta=ffprobe(source);frames=root/"frames";frames.mkdir();interval=max(1,settings.MEDIA_FRAME_INTERVAL_SECONDS)
 subprocess.run([ffmpeg,"-v","error","-i",str(source),"-vf",f"fps=1/{interval}","-frames:v",str(settings.MEDIA_MAX_VIDEO_FRAMES),str(frames/"%06d.jpg")],timeout=300,check=True)
 audio=root/"audio.wav";audio_data=None
 proc=subprocess.run([ffmpeg,"-v","error","-i",str(source),"-vn","-ac","1","-ar","16000",str(audio)],capture_output=True,timeout=300)
 if proc.returncode==0 and audio.exists():audio_data=audio.read_bytes()
 return temp,meta,[(int(x.stem),x.read_bytes()) for x in sorted(frames.glob("*.jpg"))],audio_data
def evidence(db,asset,ordinal,kind,text,metadata=None,**locator):
 value=text.strip();metadata=metadata or {};fingerprint={**locator,"metadata":metadata};row=MediaEvidence(organization_id=asset.organization_id,asset_id=asset.id,ordinal=ordinal,evidence_type=kind,text=value,content_hash=hashlib.sha256((kind+value+json.dumps(fingerprint,sort_keys=True,default=str)).encode()).hexdigest(),start_ms=locator.pop("start_ms",None),end_ms=locator.pop("end_ms",None),frame_number=locator.pop("frame_number",None),bbox=locator.pop("bbox",[]),speaker=locator.pop("speaker",""),confidence=locator.pop("confidence",0),storage_key=locator.pop("storage_key",""),metadata_json={**metadata,**locator});db.add(row)
async def process_asset(db,asset,run):
 lease_owner=run.lease_owner
 try:
  private=await owner_settings(db,asset.user_id)
 except Exception:
  await db.rollback()
  await db.refresh(asset);await db.refresh(run)
  if lease_owner is not None and (run.lease_owner!=lease_owner or run.status!="running"):
   raise RuntimeError("Media lease recovered by another worker")
  asset.status="failed";asset.error_message="Private service configuration unavailable; restore the instance encryption key"
  run.status="failed";run.error_message=asset.error_message;run.finished_at=now();run.lease_owner=None;run.lease_until=None
  await db.commit()
  raise
 with use_settings(private):
  return await _process_asset(db,asset,run)

async def _process_asset(db,asset,run):
 # Evidence, metadata and usage must publish together. A failed flush must be
 # rolled back before recording the terminal state in a fresh transaction.
 provider_started=False;ordinal=0;all_text=[];frame_keys=[]
 lease_owner=run.lease_owner
 async def fence():
  if lease_owner is None:return # Direct service calls used without worker claims.
  with db.no_autoflush:
   claimed=await db.execute(update(MediaProcessingRun).where(MediaProcessingRun.id==run.id,MediaProcessingRun.status=="running",MediaProcessingRun.lease_owner==lease_owner).values(lease_until=now()+timedelta(minutes=30)).execution_options(synchronize_session=False))
  if claimed.rowcount!=1:raise RuntimeError("Media lease no longer owned")
 async def mark_provider():
  nonlocal provider_started
  if not provider_started:
   if lease_owner is not None:
    # Persist only the call marker. Metadata may already have autoflushed during
    # route selection; roll that transaction back before recording the marker.
    # Restore its values as unpublished work for the final atomic commit.
    values=[(obj,{column.key:getattr(obj,column.key) for column in obj.__table__.columns}) for obj in (asset,run)]
    await db.rollback()
    await db.refresh(asset);await db.refresh(run)
    await fence()
    run.stage="provider_started"
    await db.commit()
    for obj,columns in values:
     for key,value in columns.items():
      if obj is run and key in {"stage","lease_owner","lease_until"}:continue
      setattr(obj,key,value)
   provider_started=True
 async def call_vision(*args):
  nonlocal provider_started
  await mark_provider()
  return await vision(*args)
 async def call_transcribe(*args):
  nonlocal provider_started
  validate_transcription(*args)
  await mark_provider()
  return await transcribe(*args)
 try:
  data=await asyncio.to_thread(storage.get,asset.storage_key);run.status="running";run.stage="metadata";run.progress=10
  if asset.media_type=="image":
   image=Image.open(io.BytesIO(data));asset.width,asset.height=image.size;asset.perceptual_hash=perceptual_hash(data);model,cost=await route_for(db,asset,"vision");run.model_routes={"vision":model};run.estimated_cost_cents=cost;result=await call_vision(data,asset.mime_type,model)
   for item in result.get("ocr",[]):evidence(db,asset,ordinal,"ocr",str(item.get("text","")),bbox=item.get("bbox",[]),confidence=float(item.get("confidence",0) or 0));ordinal+=1;all_text.append(str(item.get("text","")))
   chart=result.get("chart") or {}
   if chart:evidence(db,asset,ordinal,"chart",json.dumps(chart,ensure_ascii=False),metadata=chart);ordinal+=1
   if result.get("summary"):evidence(db,asset,ordinal,"visual_summary",str(result["summary"]));ordinal+=1
  elif asset.media_type=="audio":
   model,cost=await route_for(db,asset,"transcription");run.model_routes={"transcription":model};run.estimated_cost_cents=cost
   for item in await call_transcribe(data,asset.filename,model):evidence(db,asset,ordinal,"transcript",item["text"],**transcript_locator(item));ordinal+=1;all_text.append(item["text"])
  else:
   temp,meta,frames,audio=await asyncio.to_thread(video_parts,data,Path(asset.filename).suffix.lower())
   try:
    asset.duration_ms=int(float(meta.get("format",{}).get("duration",0))*1000);video_stream=next((x for x in meta.get("streams",[]) if x.get("codec_type")=="video"),{});asset.width=video_stream.get("width");asset.height=video_stream.get("height");vision_model,vision_cost=await route_for(db,asset,"video_vision");run.model_routes={"video_vision":vision_model}
    for index,frame in frames:
     await fence()
     frame_key=f"media/{asset.organization_id}/{asset.id}/frames/{index:06d}.jpg";frame_keys.append(frame_key);await asyncio.to_thread(storage.put,frame_key,frame);result=await call_vision(frame,"image/jpeg",vision_model);text="\n".join(str(x.get("text","")) for x in result.get("ocr",[]) if x.get("text"));summary=str(result.get("summary","") or "");evidence(db,asset,ordinal,"video_frame",(text+"\n"+summary).strip(),start_ms=(index-1)*settings.MEDIA_FRAME_INTERVAL_SECONDS*1000,frame_number=index,storage_key=frame_key,metadata={"chart":result.get("chart")});ordinal+=1;all_text.extend([text,summary])
    if audio:
     audio_model,audio_cost=await route_for(db,asset,"transcription");run.model_routes={**run.model_routes,"transcription":audio_model}
     for item in await call_transcribe(audio,"audio.wav",audio_model):evidence(db,asset,ordinal,"transcript",item["text"],**transcript_locator(item));ordinal+=1;all_text.append(item["text"])
     run.estimated_cost_cents=vision_cost+audio_cost
    else:run.estimated_cost_cents=vision_cost
   finally:temp.cleanup()
  await fence()
  findings=[*asset.safety_findings,*pii_findings("\n".join(all_text))];asset.safety_findings=findings;asset.safety_status="review_required" if findings or (asset.media_type in {"audio","video"} and not asset.consent_confirmed) else "passed";asset.status="ready";asset.error_message="";run.status="succeeded";run.stage="completed";run.progress=100;run.actual_cost_cents=run.estimated_cost_cents;run.finished_at=now();run.lease_owner=None;run.lease_until=None;db.add(ModelUsage(user_id=asset.user_id,organization_id=asset.organization_id,workspace_id=asset.workspace_id,feature="multimodal",model_name=",".join(run.model_routes.values()),cost=run.actual_cost_cents/100));await db.commit()
 except Exception as exc:
  await db.rollback()
  await db.refresh(asset);await db.refresh(run)
  if lease_owner is not None and (run.lease_owner!=lease_owner or run.status!="running"):
   raise RuntimeError("Media lease recovered by another worker") from exc
  # Once a provider request started, neither its delivery nor billing is known
  # on failure. Existing retry only accepts failed assets, so unknown is blocked.
  status="unknown" if provider_started else "failed"
  message=("Provider outcome requires manual reconciliation: " if provider_started else "")+str(exc)
  asset.status=status;asset.error_message=message[:1000];run.status=status;run.error_message=message[:2000];run.finished_at=now();run.lease_owner=None;run.lease_until=None
  await db.commit()
  for key in frame_keys:
   try:await asyncio.to_thread(storage.remove,key)
   except Exception:logging.getLogger(__name__).exception("Unable to remove unpublished media frame")
  raise
async def recover_media_leases(db):
 expired=(MediaProcessingRun.lease_until<now()) | MediaProcessingRun.lease_until.is_(None)
 runs=(await db.scalars(select(MediaProcessingRun).where(MediaProcessingRun.status=="running",expired).with_for_update(skip_locked=True))).all()
 for run in runs:
  safe=run.stage=="claimed"
  status="queued" if safe else "unknown"
  claimed=await db.execute(update(MediaProcessingRun).where(MediaProcessingRun.id==run.id,MediaProcessingRun.status=="running",expired).values(status=status,stage="security_scan" if safe else run.stage,lease_owner=None,lease_until=None,error_message="Lease expired before provider request" if safe else "Provider outcome requires manual reconciliation after worker interruption").execution_options(synchronize_session=False))
  if claimed.rowcount==1:
   asset=await db.get(MediaAsset,run.asset_id);asset.status=status
   if not safe:asset.error_message="Provider outcome requires manual reconciliation after worker interruption"
 await db.commit()
 return len(runs)

async def process_media_once(asset_id=None,sessions=None):
 async with (sessions or _get_sessionmaker())() as db:
  await recover_media_leases(db)
  q=select(MediaProcessingRun).where(MediaProcessingRun.status=="queued")
  if asset_id:q=q.where(MediaProcessingRun.asset_id==asset_id)
  run=await db.scalar(q.order_by(MediaProcessingRun.created_at).limit(1).with_for_update(skip_locked=True))
  if not run:return False
  owner=f"{socket.gethostname()[:50]}:{uuid4().hex}"
  claimed=await db.execute(update(MediaProcessingRun).where(MediaProcessingRun.id==run.id,MediaProcessingRun.status=="queued").values(status="running",stage="claimed",lease_owner=owner,lease_until=now()+timedelta(minutes=30)).execution_options(synchronize_session=False))
  await db.commit()
  if claimed.rowcount!=1:return False
  await db.refresh(run)
  asset=await db.get(MediaAsset,run.asset_id)
  await process_asset(db,asset,run)
  return True
async def media_worker_loop(stop):
 while not stop.is_set():
  try:worked=await process_media_once()
  except Exception:worked=True
  if not worked:
   try:await asyncio.wait_for(stop.wait(),timeout=2)
   except asyncio.TimeoutError:pass
