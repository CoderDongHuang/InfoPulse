import io,unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
import app.models
from app.core.database import Base
from app.models.enterprise import TenantQuota
from app.models.multimodal import MediaAsset,MediaEvidence,MediaProcessingRun
from app.models.user import User
from app.services.enterprise import provision_personal_tenant
from app.services.multimodal import perceptual_hash,process_asset,transcribe,validate_media

def png(color="white"):
 stream=io.BytesIO();Image.new("RGB",(16,12),color).save(stream,"PNG");return stream.getvalue()

class MultimodalTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.engine=create_async_engine("sqlite+aiosqlite:///:memory:");self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
  async with self.engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
 async def asyncTearDown(self):await self.engine.dispose()
 def test_signature_and_perceptual_hash(self):
  data=png();self.assertEqual(validate_media("capture.png",data),("image","image/png"));self.assertEqual(len(perceptual_hash(data)),16)
  with self.assertRaisesRegex(ValueError,"corrupted"):validate_media("capture.png",b"not an image")
  with self.assertRaisesRegex(ValueError,"WAV signature"):validate_media("recording.wav",b"bad")
 async def test_transcription_preserves_real_segment_locators(self):
  response=SimpleNamespace(model_dump=lambda:{"segments":[{"start":1.25,"end":2.5,"text":"verified statement","speaker":"speaker_1","confidence":.91}]})
  api=SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=AsyncMock(return_value=response))))
  with patch("app.services.multimodal.client",return_value=api):segments=await transcribe(b"RIFFxxxxWAVE","clip.wav","approved-model")
  self.assertEqual(segments[0]["speaker"],"speaker_1");self.assertEqual(segments[0]["start"],1.25)
 async def test_vision_processing_creates_bbox_evidence_and_requires_review_for_pii(self):
  async with self.sessions() as db:
   user=User(username="mediaowner",email="mediaowner@test.local",password_hash="x");db.add(user);await db.flush();org=await provision_personal_tenant(db,user);quota=await db.get(TenantQuota,org.id);quota.monthly_cost_limit=100
   data=png();asset=MediaAsset(organization_id=org.id,user_id=user.id,filename="capture.png",media_type="image",mime_type="image/png",byte_size=len(data),content_hash="a"*64,storage_key="unused",safety_findings=[]);db.add(asset);await db.flush();run=MediaProcessingRun(organization_id=org.id,asset_id=asset.id);db.add(run);await db.flush()
   result={"ocr":[{"text":"Contact a@b.com","bbox":[1,2,3,4],"confidence":.9}],"chart":{},"summary":"Visible contact"}
   with patch("app.services.multimodal.storage.get",return_value=data),patch("app.services.multimodal.route_for",AsyncMock(return_value=("approved-vision",4))),patch("app.services.multimodal.vision",AsyncMock(return_value=result)):
    await process_asset(db,asset,run)
   evidence=(await db.scalars(select(MediaEvidence).where(MediaEvidence.asset_id==asset.id).order_by(MediaEvidence.ordinal))).all();self.assertEqual(evidence[0].bbox,[1,2,3,4]);self.assertEqual(asset.safety_status,"review_required");self.assertEqual(run.actual_cost_cents,4)

if __name__=="__main__":unittest.main()
