"""Saved titles and follows must reach the workspace and remain account scoped."""
import unittest
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.api.personalization import router as personal_router
from app.api.stage3 import router as stage_router
from app.api.history import router as history_router
from app.models.analysis_history import AnalysisHistory
from app.core.database import Base, get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.intelligence import ContentItem, DataSource, Event, Favorite, Report, WatchTopic


class WorkspacePersonalizationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.sessions() as db:
            self.owner = User(username='owner', email='owner@example.com', password_hash='x')
            self.other = User(username='other', email='other@example.com', password_hash='x')
            self.source = DataSource(key='test', name='真实来源', source_type='rss', health_status='healthy')
            db.add_all([self.owner, self.other, self.source]); await db.flush()
            self.item = ContentItem(source_id=self.source.id, external_id='one', title='OpenAI agent guide',
                body='An AI agent tutorial', content_hash='a'*64, canonical_url='https://example.com/guide',
                content_type='article', published_at=datetime.now(timezone.utc))
            self.deleted = ContentItem(source_id=self.source.id, external_id='deleted', title='Hidden title',
                body='AI agent', content_hash='b'*64, canonical_url='https://example.com/deleted',
                content_type='article', deleted_at=datetime.now(timezone.utc))
            self.event = Event(title='Real event', slug='real-event')
            self.mine = Report(user_id=self.owner.id, title='My report', report_type='daily')
            self.private = Report(user_id=self.other.id, title='Other secret', report_type='daily')
            db.add_all([self.item, self.deleted, self.event, self.mine, self.private]); await db.commit()
        self.current = self.owner
        self.app = FastAPI(); self.app.include_router(personal_router); self.app.include_router(stage_router); self.app.include_router(history_router)
        async def database():
            async with self.sessions() as db:
                yield db
                await db.commit()
        self.app.dependency_overrides[get_db] = database
        self.app.dependency_overrides[get_current_user] = lambda: self.current
        self.http = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://testserver')

    async def asyncTearDown(self):
        await self.http.aclose(); await self.engine.dispose()

    async def test_favorite_roundtrip_resolves_title_source_summary_and_deleted_target(self):
        for kind, target in [('content', self.item), ('event', self.event), ('report', self.mine),
                             ('report', self.private), ('content', self.deleted)]:
            response = await self.http.post('/api/v1/favorites', json={'target_type': kind, 'target_id': target.id})
            self.assertEqual(response.status_code, 201)
        result = (await self.http.get('/api/v1/workspace')).json()
        by_id = {row['target_id']: row for row in result['favorites']}
        article = by_id[self.item.id]
        self.assertEqual(article['title'], 'OpenAI agent guide')
        self.assertEqual(article['source_name'], '真实来源')
        self.assertEqual(article['canonical_url'], 'https://example.com/guide')
        self.assertTrue(article['summary']); self.assertTrue(article['created_at'])
        self.assertEqual(by_id[self.event.id]['path'], '/events/' + self.event.id)
        self.assertEqual(by_id[self.mine.id]['path'], '/reports/' + self.mine.id)
        for row in [by_id[self.private.id], by_id[self.deleted.id]]:
            self.assertFalse(row['available']); self.assertIsNone(row['path']); self.assertIsNone(row['canonical_url'])
        self.assertNotIn('Other secret', str(result)); self.assertNotIn('Hidden title', str(result))
        listed = (await self.http.get('/api/v1/favorites')).json()
        self.assertEqual(next(x for x in listed if x['target_id'] == self.item.id)['title'], article['title'])
        self.current = self.other
        self.assertEqual((await self.http.get('/api/v1/workspace')).json()['favorites'], [])

    async def test_topic_roundtrip_workspace_count_dedup_and_unfollow(self):
        response = await self.http.post('/api/v1/watch-topics', json={'name': 'OpenAI', 'keywords': ['agent', 'AI']})
        self.assertEqual(response.status_code, 201)
        topic_id = response.json()['id']
        listed = (await self.http.get('/api/v1/watch-topics')).json()
        self.assertEqual(listed[0]['id'], topic_id)
        self.assertEqual(datetime.fromisoformat(listed[0]['created_at']).utcoffset().total_seconds(), 0)
        await self.http.post('/api/v1/watch-topics', json={'name': 'disabled', 'keywords': ['agent'], 'enabled': False})
        result = (await self.http.get('/api/v1/workspace')).json()
        self.assertEqual(len(result['attention']), 1)
        self.assertEqual(result['attention'][0]['count'], 1)  # three matches, one article
        self.assertEqual([x['id'] for x in result['followed_items']], [self.item.id])
        self.current = self.other
        self.assertEqual((await self.http.get('/api/v1/workspace')).json()['followed_items'], [])
        self.assertEqual((await self.http.delete('/api/v1/watch-topics/' + topic_id)).status_code, 404)
        self.current = self.owner
        self.assertEqual((await self.http.delete('/api/v1/watch-topics/' + topic_id)).status_code, 204)
        self.assertEqual((await self.http.get('/api/v1/workspace')).json()['followed_items'], [])

    async def test_channel_follow_is_visible_in_workspace_and_removal_takes_effect(self):
        self.assertEqual((await self.http.post('/api/v1/discover/channels/ai/follow')).status_code, 201)
        result = (await self.http.get('/api/v1/workspace')).json()
        self.assertEqual(result['followed_channels'], [{'id': 'ai', 'name': 'AI'}])
        self.assertEqual([x['id'] for x in result['followed_items']], [self.item.id])
        self.assertEqual((await self.http.delete('/api/v1/discover/channels/ai/follow')).status_code, 204)
        self.assertEqual((await self.http.get('/api/v1/workspace')).json()['followed_items'], [])

    async def test_recent_browsing_roundtrip_dedup_order_authoritative_titles_and_privacy(self):
        async def view(kind, target):
            response = await self.http.post('/api/v1/recent-views', json={
                'target_type': kind, 'target_id': target.id, 'title': 'Forged title'})
            self.assertEqual(response.status_code, 200, response.text)
            return response.json()
        first = await view('content', self.item)
        self.assertEqual(first['title'], self.item.title)
        await view('event', self.event)
        again = await view('content', self.item)
        self.assertEqual(first['id'], again['id'])
        result = (await self.http.get('/api/v1/workspace')).json()['recent_views']
        self.assertEqual([x['target_id'] for x in result], [self.item.id, self.event.id])
        self.assertEqual(result[0]['canonical_url'], self.item.canonical_url)
        self.assertEqual(result[1]['path'], '/events/' + self.event.id)
        self.assertEqual(datetime.fromisoformat(result[0]['viewed_at']).utcoffset().total_seconds(), 0)
        for kind, target in [('report', self.private), ('content', self.deleted)]:
            response = await self.http.post('/api/v1/recent-views', json={'target_type': kind, 'target_id': target.id})
            self.assertEqual(response.status_code, 404)
        async with self.sessions() as db:
            item = await db.get(ContentItem, self.item.id)
            item.deleted_at = datetime.now(timezone.utc)
            await db.commit()
        result = (await self.http.get('/api/v1/workspace')).json()['recent_views']
        self.assertFalse(result[0]['available']); self.assertIsNone(result[0]['canonical_url'])
        self.assertNotIn(self.item.title, str(result))
        listed = (await self.http.get('/api/v1/recent-views')).json()
        self.assertFalse(listed[0]['available'])
        self.current = self.other
        self.assertEqual((await self.http.get('/api/v1/workspace')).json()['recent_views'], [])

    async def test_generated_archives_merge_into_recent_reports_and_open_saved_result(self):
        async with self.sessions() as db:
            mine = AnalysisHistory(user_id=self.owner.id, module='insight', status='completed',
                input_params={'keyword': 'AI'}, output_result={'topic': 'Saved insight', 'overview': 'Original result'})
            failed = AnalysisHistory(user_id=self.owner.id, module='timeline', status='failed', output_result={'topic': 'Failed'})
            private = AnalysisHistory(user_id=self.other.id, module='mouthpiece', status='completed', output_result={'title': 'Secret draft'})
            db.add_all([mine, failed, private]); await db.commit()
        result = (await self.http.get('/api/v1/workspace')).json()['recent_reports']
        self.assertEqual(result[0]['title'], 'Saved insight')
        self.assertEqual(result[0]['path'], '/history?record=' + mine.id)
        self.assertEqual(result[0]['kind'], 'history')
        self.assertNotIn('Secret draft', str(result)); self.assertNotIn('Failed', str(result))
        detail = await self.http.get('/api/v1/history/' + mine.id)
        self.assertEqual(detail.json()['output_result']['overview'], 'Original result')
        self.assertEqual((await self.http.get('/api/v1/history/' + private.id)).status_code, 404)
        self.assertEqual((await self.http.post('/api/v1/recent-views', json={'target_type': 'history', 'target_id': mine.id})).status_code, 200)
        self.assertEqual((await self.http.post('/api/v1/recent-views', json={'target_type': 'history', 'target_id': private.id})).status_code, 404)
        self.assertEqual((await self.http.get('/api/v1/workspace')).json()['recent_views'][0]['title'], 'Saved insight')
        self.assertEqual((await self.http.delete('/api/v1/history/' + mine.id)).status_code, 204)
        after = (await self.http.get('/api/v1/workspace')).json()
        self.assertNotIn(mine.id, [x['id'] for x in after['recent_reports']])
        self.assertFalse(after['recent_views'][0]['available'])
