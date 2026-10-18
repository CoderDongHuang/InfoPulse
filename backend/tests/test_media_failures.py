"""Media failures must not publish partial evidence or replay uncertain calls."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call, patch

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.core.database import Base
from app.models.intelligence import ModelUsage
from app.models.multimodal import MediaAsset, MediaEvidence, MediaProcessingRun
from app.models.user import User
from app.services.enterprise import provision_personal_tenant
from app.services.multimodal import process_media_once
from tests.test_multimodal import png


class MediaFailureTests(unittest.IsolatedAsyncioTestCase):
    def test_media_sdk_does_not_implicitly_replay_uncertain_requests(self):
        from app.services import multimodal
        with patch.object(multimodal.settings, 'LLM_API_KEY', 'fixture-not-a-real-key'), \
             patch('app.services.multimodal.AsyncOpenAI') as sdk:
            multimodal.client()
        self.assertEqual(sdk.call_args.kwargs['max_retries'], 0)

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.tmp.name) / 'media.db'))
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with self.sessions() as db:
            user = User(username='media-failure', email='media-failure@example.com', password_hash='x')
            db.add(user)
            await db.flush()
            org = await provision_personal_tenant(db, user)
            self.asset = MediaAsset(organization_id=org.id, user_id=user.id, filename='fixture.png',
                                    media_type='image', mime_type='image/png', byte_size=100,
                                    content_hash='f' * 64, storage_key='fixture.png', safety_findings=[])
            db.add(self.asset)
            await db.flush()
            self.run = MediaProcessingRun(organization_id=org.id, asset_id=self.asset.id)
            db.add(self.run)
            await db.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.tmp.cleanup()

    async def assert_terminal(self, status):
        # Independent reader: no test-side commit or dependency teardown.
        async with self.sessions() as db:
            asset = await db.get(MediaAsset, self.asset.id)
            run = await db.get(MediaProcessingRun, self.run.id)
            self.assertEqual(asset.status, status)
            self.assertEqual(run.status, status)
            self.assertIsNotNone(run.finished_at)
            self.assertIsNone(run.lease_until)
            self.assertIsNone(run.lease_owner)
            self.assertIsNone(asset.width, 'unpublished metadata leaked')
            self.assertEqual(await db.scalar(select(func.count()).select_from(MediaEvidence)), 0)
            self.assertEqual(await db.scalar(select(func.count()).select_from(ModelUsage)), 0)
            return asset

    async def test_missing_source_is_failed_instead_of_stuck_running_and_can_be_processed_after_repair(self):
        with patch('app.services.multimodal.storage.get', side_effect=FileNotFoundError('source missing')):
            with self.assertRaises(FileNotFoundError):
                await process_media_once(self.asset.id, self.sessions)
        await self.assert_terminal('failed')
        from app.api.multimodal import retry
        async with self.sessions() as db:
            ctx = SimpleNamespace(organization=SimpleNamespace(id=self.asset.organization_id), workspace=None)
            with patch('app.api.multimodal.require_permission'):
                await retry(self.asset.id, ctx, db)
            await db.commit()
        with patch('app.services.multimodal.storage.get', return_value=png()), \
             patch('app.services.multimodal.route_for', AsyncMock(return_value=('fixture', 1))), \
             patch('app.services.multimodal.vision', AsyncMock(return_value={'summary': 'repaired'})):
            self.assertTrue(await process_media_once(self.asset.id, self.sessions))
        async with self.sessions() as db:
            self.assertEqual((await db.get(MediaAsset, self.asset.id)).status, 'ready')
            self.assertEqual(await db.scalar(select(func.count()).select_from(MediaEvidence)), 1)

    async def test_local_model_route_failure_is_failed_with_no_provider_call(self):
        vision = AsyncMock()
        with patch('app.services.multimodal.storage.get', return_value=png()), \
             patch('app.services.multimodal.route_for', AsyncMock(side_effect=RuntimeError('no model route'))), \
             patch('app.services.multimodal.vision', vision):
            with self.assertRaisesRegex(RuntimeError, 'no model route'):
                await process_media_once(self.asset.id, self.sessions)
        await self.assert_terminal('failed')
        vision.assert_not_awaited()

    async def test_unreadable_private_configuration_releases_lease_without_provider_call(self):
        with patch('app.services.multimodal.owner_settings', AsyncMock(side_effect=HTTPException(503, 'unreadable configuration'))), \
             patch('app.services.multimodal.vision', AsyncMock()) as vision:
            with self.assertRaises(HTTPException):
                await process_media_once(self.asset.id, self.sessions)
        asset = await self.assert_terminal('failed')
        self.assertIn('Private service configuration unavailable', asset.error_message)
        vision.assert_not_awaited()

    async def test_provider_timeout_is_unknown_and_never_automatically_or_manually_retried(self):
        vision = AsyncMock(side_effect=TimeoutError('response lost'))
        with patch('app.services.multimodal.storage.get', return_value=png()), \
             patch('app.services.multimodal.route_for', AsyncMock(return_value=('fixture', 1))), \
             patch('app.services.multimodal.vision', vision):
            with self.assertRaises(TimeoutError):
                await process_media_once(self.asset.id, self.sessions)
            self.assertFalse(await process_media_once(self.asset.id, self.sessions))
        await self.assert_terminal('unknown')
        vision.assert_awaited_once()
        from app.api.multimodal import retry
        async with self.sessions() as db:
            ctx = SimpleNamespace(organization=SimpleNamespace(id=self.asset.organization_id), workspace=None)
            with patch('app.api.multimodal.require_permission'):
                with self.assertRaises(HTTPException) as error:
                    await retry(self.asset.id, ctx, db)
            self.assertEqual(error.exception.status_code, 409)

    async def test_malformed_later_ocr_rolls_back_first_evidence(self):
        result = {'ocr': [{'text': 'first', 'confidence': .8}, {'text': 'bad', 'confidence': 'invalid'}]}
        with patch('app.services.multimodal.storage.get', return_value=png()), \
             patch('app.services.multimodal.route_for', AsyncMock(return_value=('fixture', 1))), \
             patch('app.services.multimodal.vision', AsyncMock(return_value=result)):
            with self.assertRaises(ValueError):
                await process_media_once(self.asset.id, self.sessions)
        await self.assert_terminal('unknown')

    async def test_failed_flush_rolls_back_before_recording_failure(self):
        from sqlalchemy.exc import IntegrityError
        from app.services.multimodal import evidence as real_evidence

        def duplicate(db, asset, ordinal, *args, **kwargs):
            real_evidence(db, asset, 0, *args, **kwargs)

        with patch('app.services.multimodal.storage.get', return_value=png()), \
             patch('app.services.multimodal.route_for', AsyncMock(return_value=('fixture', 1))), \
             patch('app.services.multimodal.vision', AsyncMock(return_value={'ocr': [{'text': 'one'}, {'text': 'two'}]})), \
             patch('app.services.multimodal.evidence', side_effect=duplicate):
            with self.assertRaises(IntegrityError):
                await process_media_once(self.asset.id, self.sessions)
        await self.assert_terminal('unknown')

    async def test_video_second_frame_failure_rolls_back_evidence_and_removes_unpublished_files(self):
        async with self.sessions() as db:
            asset = await db.get(MediaAsset, self.asset.id)
            asset.media_type = 'video'
            asset.filename = 'fixture.mp4'
            await db.commit()
        temp = Mock()
        remove = Mock()
        with patch('app.services.multimodal.storage.get', return_value=b'fixture'), \
             patch('app.services.multimodal.storage.put') as put, \
             patch('app.services.multimodal.storage.remove', remove), \
             patch('app.services.multimodal.video_parts', return_value=(temp, {}, [(1, b'one'), (2, b'two')], None)), \
             patch('app.services.multimodal.route_for', AsyncMock(return_value=('fixture', 1))), \
             patch('app.services.multimodal.vision', AsyncMock(side_effect=[{'summary': 'one'}, TimeoutError('frame two')])):
            with self.assertRaises(TimeoutError):
                await process_media_once(self.asset.id, self.sessions)
        await self.assert_terminal('unknown')
        self.assertEqual(put.call_count, 2)
        self.assertEqual(remove.call_args_list, [call(item.args[0]) for item in put.call_args_list])
        temp.cleanup.assert_called_once()
