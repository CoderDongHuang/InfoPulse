import asyncio, hashlib, io, ipaddress, math, os, re, socket, zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.models.intelligence import KnowledgeBase, KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentVersion, KnowledgeProcessingRun

ALLOWED={".pdf":"application/pdf",".docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document",".md":"text/markdown",".txt":"text/plain"}
settings=get_settings()

class Storage:
    def __init__(self):
        self.local=Path(settings.KNOWLEDGE_STORAGE_PATH).resolve()
    def put(self,key:str,data:bytes):
        if settings.KNOWLEDGE_STORAGE_BACKEND=="s3":
            import boto3
            boto3.client("s3",endpoint_url=settings.S3_ENDPOINT_URL or None,aws_access_key_id=settings.S3_ACCESS_KEY or None,aws_secret_access_key=settings.S3_SECRET_KEY or None,region_name=settings.S3_REGION).put_object(Bucket=settings.S3_BUCKET,Key=key,Body=data)
            return
        path=(self.local/key).resolve()
        if self.local not in path.parents: raise ValueError("invalid storage key")
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    def get(self,key:str)->bytes:
        if settings.KNOWLEDGE_STORAGE_BACKEND=="s3":
            import boto3
            return boto3.client("s3",endpoint_url=settings.S3_ENDPOINT_URL or None,aws_access_key_id=settings.S3_ACCESS_KEY or None,aws_secret_access_key=settings.S3_SECRET_KEY or None,region_name=settings.S3_REGION).get_object(Bucket=settings.S3_BUCKET,Key=key)["Body"].read()
        path=(self.local/key).resolve()
        if self.local not in path.parents: raise ValueError("invalid storage key")
        return path.read_bytes()
    def remove(self,key:str):
        if settings.KNOWLEDGE_STORAGE_BACKEND=="s3":
            import boto3
            boto3.client("s3",endpoint_url=settings.S3_ENDPOINT_URL or None,aws_access_key_id=settings.S3_ACCESS_KEY or None,aws_secret_access_key=settings.S3_SECRET_KEY or None,region_name=settings.S3_REGION).delete_object(Bucket=settings.S3_BUCKET,Key=key);return
        path=(self.local/key).resolve()
        if self.local in path.parents: path.unlink(missing_ok=True)
    def exists(self,key:str)->bool:
        if settings.KNOWLEDGE_STORAGE_BACKEND=="s3":
            import boto3
            try:boto3.client("s3",endpoint_url=settings.S3_ENDPOINT_URL or None,aws_access_key_id=settings.S3_ACCESS_KEY or None,aws_secret_access_key=settings.S3_SECRET_KEY or None,region_name=settings.S3_REGION).head_object(Bucket=settings.S3_BUCKET,Key=key);return True
            except Exception:return False
        path=(self.local/key).resolve()
        return self.local in path.parents and path.is_file()

storage=Storage()
processing_queue: asyncio.Queue[tuple[str,bytes|None]] = asyncio.Queue()

async def enqueue_document(document_id:str,data:bytes|None=None):
    if data is not None: storage.put(f"staging/{document_id}",data)
    await processing_queue.put((document_id,data))

async def process_knowledge_once(document_id:str|None=None,sessions=None)->bool:
    from app.core.database import _get_sessionmaker
    async with (sessions or _get_sessionmaker())() as db:
        query=select(KnowledgeDocument).where(KnowledgeDocument.status=="queued",KnowledgeDocument.deleted_at.is_(None))
        if document_id: query=query.where(KnowledgeDocument.id==document_id)
        doc=await db.scalar(query.order_by(KnowledgeDocument.updated_at).limit(1).with_for_update(skip_locked=True))
        if not doc:return False
        doc.status="processing";await db.commit()
        staging=f"staging/{doc.id}";data=storage.get(staging) if storage.exists(staging) else None
        await process_document(db,doc,data)
        storage.remove(staging)
        return True

async def knowledge_worker_loop(stop:asyncio.Event):
    from app.core.database import _get_sessionmaker
    while not stop.is_set():
        queued=False
        try: document_id,_data=await asyncio.wait_for(processing_queue.get(),timeout=max(1,settings.KNOWLEDGE_WORKER_POLL_SECONDS));queued=True
        except asyncio.TimeoutError: document_id=None
        try:
            await process_knowledge_once(document_id)
        except Exception:
            pass
        finally:
            if queued: processing_queue.task_done()

def safe_filename(name:str)->str:
    name=Path(name or "document").name
    return re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]","_",name)[:300]

def validate_upload(name:str,data:bytes):
    ext=Path(name).suffix.lower()
    if ext not in ALLOWED: raise ValueError("仅支持 PDF、DOCX、Markdown 和 TXT")
    if not data: raise ValueError("文件为空")
    if len(data)>settings.KNOWLEDGE_MAX_FILE_MB*1024*1024: raise ValueError("文件超过大小限制")
    if ext==".pdf" and not data.startswith(b"%PDF-"): raise ValueError("PDF 文件签名无效")
    if ext==".docx":
        if not data.startswith(b"PK"): raise ValueError("DOCX 文件签名无效")
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names=z.namelist();expanded=sum(x.file_size for x in z.infolist())
            if "word/document.xml" not in names or expanded>100*1024*1024 or any(n.lower().endswith((".exe",".dll","vbaproject.bin")) for n in names): raise ValueError("DOCX 结构或安全检查失败")
    if ext in {".md",".txt"}:
        if b"\x00" in data[:4096]: raise ValueError("文本文件包含二进制内容")
        data.decode("utf-8")

def embedding(text:str,dims:int=96)->list[float]:
    values=[0.0]*dims
    for token in re.findall(r"[\w\u4e00-\u9fff]+",text.lower()):
        digest=hashlib.sha256(token.encode()).digest();idx=int.from_bytes(digest[:4],"big")%dims;values[idx]+=1 if digest[4]%2 else -1
    norm=math.sqrt(sum(x*x for x in values)) or 1
    return [round(x/norm,6) for x in values]

def parse_document(name:str,data:bytes)->list[tuple[str,int|None,int|None,str]]:
    ext=Path(name).suffix.lower();rows=[]
    if ext==".pdf":
        from pypdf import PdfReader
        for page_no,page in enumerate(PdfReader(io.BytesIO(data)).pages,1):
            for para_no,text in enumerate(filter(None,(x.strip() for x in (page.extract_text() or "").splitlines())),1): rows.append((text,page_no,para_no,""))
    elif ext==".docx":
        from docx import Document
        for para_no,p in enumerate(Document(io.BytesIO(data)).paragraphs,1):
            if p.text.strip(): rows.append((p.text.strip(),None,para_no,""))
    else:
        text=data.decode("utf-8")
        heading=""
        for para_no,p in enumerate(re.split(r"\n\s*\n|\r?\n",text),1):
            p=p.strip()
            if p.startswith("#"): heading=p.lstrip("# ")
            if p: rows.append((p,None,para_no,heading))
    return rows

def chunks(rows,limit=1200):
    out=[];buf="";page=para=None;heading=""
    for text,p,idx,h in rows:
        if buf and (len(buf)+len(text)>limit or (p and p!=page)):
            out.append((buf,page,para,heading));buf=""
        if not buf: page,para,heading=p,idx,h
        buf+=("\n" if buf else "")+text
    if buf:out.append((buf,page,para,heading))
    return out

async def process_document(db:AsyncSession,doc:KnowledgeDocument,data:bytes|None=None):
    previous=await db.scalar(select(func.max(KnowledgeDocumentVersion.version_number)).where(KnowledgeDocumentVersion.document_id==doc.id)) or 0
    run=KnowledgeProcessingRun(document_id=doc.id,user_id=doc.user_id,status="running",stage="security_scan",progress=5,attempt=previous+1);db.add(run);doc.status="processing";await db.flush()
    try:
        if data is None:
            current=await db.get(KnowledgeDocumentVersion,doc.active_version_id);data=storage.get(current.storage_key)
        validate_upload(doc.filename,data);digest=hashlib.sha256(data).hexdigest();key=f"{doc.user_id}/{doc.knowledge_base_id}/{doc.id}/v{previous+1}-{digest[:12]}{Path(doc.filename).suffix.lower()}";storage.put(key,data)
        version=KnowledgeDocumentVersion(document_id=doc.id,version_number=previous+1,storage_key=key,content_hash=digest);db.add(version);await db.flush()
        parsed=parse_document(doc.filename,data);version.page_count=max((x[1] or 0 for x in parsed),default=0);run.stage="embedding";run.progress=70
        for ordinal,(text,page,para,heading) in enumerate(chunks(parsed)):
            db.add(KnowledgeChunk(version_id=version.id,document_id=doc.id,knowledge_base_id=doc.knowledge_base_id,user_id=doc.user_id,ordinal=ordinal,content=text,page_number=page,paragraph_index=para,heading=heading,token_count=len(text.split()),content_hash=hashlib.sha256(text.encode()).hexdigest(),embedding=embedding(text)))
        doc.active_version_id=version.id;doc.status="ready";doc.error_message="";run.status="succeeded";run.stage="completed";run.progress=100;run.finished_at=datetime.now(timezone.utc);await db.commit()
    except Exception as exc:
        doc.status="failed";doc.error_message=str(exc)[:1000];run.status="failed";run.error_message=str(exc)[:1000];run.finished_at=datetime.now(timezone.utc);await db.commit();raise

async def validate_public_url(url:str):
    parsed=urlparse(url)
    if parsed.scheme not in {"http","https"} or parsed.username or parsed.password or not parsed.hostname: raise ValueError("仅允许公开 HTTP(S) 地址")
    try: infos=await __import__("asyncio").get_running_loop().run_in_executor(None,lambda:socket.getaddrinfo(parsed.hostname,parsed.port or (443 if parsed.scheme=="https" else 80),type=socket.SOCK_STREAM))
    except socket.gaierror: raise ValueError("网页地址无法解析")
    for info in infos:
        ip=ipaddress.ip_address(info[4][0])
        if not ip.is_global: raise ValueError("网页地址不允许访问内部网络")

async def fetch_web(url:str)->tuple[str,bytes]:
    current=url
    async with httpx.AsyncClient(timeout=12,follow_redirects=False) as client:
        for _ in range(5):
            await validate_public_url(current);resp=await client.get(current,headers={"User-Agent":"InfoPulse-Knowledge/1.0"})
            if resp.status_code in {301,302,303,307,308}:
                current=urljoin(current,resp.headers.get("location",""));continue
            resp.raise_for_status();ctype=resp.headers.get("content-type","").lower()
            if "text/html" not in ctype: raise ValueError("网页内容类型不受支持")
            if len(resp.content)>settings.KNOWLEDGE_WEB_MAX_BYTES: raise ValueError("网页内容超过大小限制")
            soup=BeautifulSoup(resp.content,"lxml");[x.decompose() for x in soup(["script","style","noscript"])]
            title=(soup.title.string.strip() if soup.title and soup.title.string else urlparse(current).hostname);text="\n\n".join(x.strip() for x in soup.get_text("\n").splitlines() if x.strip())
            if not text: raise ValueError("网页没有可解析正文")
            return safe_filename(title)+".md",text.encode()
    raise ValueError("网页重定向次数过多")

def cosine(a,b): return sum(x*y for x,y in zip(a,b))

async def search(db:AsyncSession,user_id:str,base_ids:list[str],query:str,limit=8):
    owned=(await db.scalars(select(KnowledgeBase.id).where(KnowledgeBase.user_id==user_id,KnowledgeBase.deleted_at.is_(None),KnowledgeBase.id.in_(base_ids)))).all()
    if not owned:return []
    rows=(await db.execute(select(KnowledgeChunk,KnowledgeDocument,KnowledgeBase).join(KnowledgeDocument,KnowledgeDocument.id==KnowledgeChunk.document_id).join(KnowledgeBase,KnowledgeBase.id==KnowledgeChunk.knowledge_base_id).where(KnowledgeChunk.user_id==user_id,KnowledgeChunk.knowledge_base_id.in_(owned),KnowledgeDocument.deleted_at.is_(None),KnowledgeBase.deleted_at.is_(None),KnowledgeDocument.status=="ready",KnowledgeDocument.active_version_id==KnowledgeChunk.version_id))).all()
    terms=set(re.findall(r"[\w\u4e00-\u9fff]+",query.lower()));qv=embedding(query);ranked=[]
    for chunk,doc,base in rows:
        content=chunk.content.lower();hits=sum(1 for t in terms if t in content);keyword=hits/max(len(terms),1);vector=max(0.0,cosine(qv,chunk.embedding or []));heading=0.08 if any(t in (chunk.heading or "").lower() for t in terms) else 0
        score=.52*keyword+.4*vector+heading
        if score>0: ranked.append({"citation_type":"private","chunk_id":chunk.id,"knowledge_base_id":base.id,"knowledge_base_name":base.name,"document_id":doc.id,"filename":doc.filename,"page":chunk.page_number,"paragraph":chunk.paragraph_index,"heading":chunk.heading,"quote":chunk.content[:700],"score":round(score,4)})
    return sorted(ranked,key=lambda x:x["score"],reverse=True)[:limit]

async def delete_document(db:AsyncSession,doc:KnowledgeDocument,strict_storage:bool=False):
    doc.deleted_at=datetime.now(timezone.utc);doc.status="deleted";versions=(await db.scalars(select(KnowledgeDocumentVersion).where(KnowledgeDocumentVersion.document_id==doc.id))).all();await db.commit()
    for version in versions:
        try: storage.remove(version.storage_key)
        except Exception:
            if strict_storage: raise
