"""Avatar uploads are decoded, bounded, durable and account scoped."""
from io import BytesIO
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import Depends, FastAPI
from PIL import Image
from app.api.auth import router, upload_avatar
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.avatar import UserAvatar
from app.services.avatars import normalize_avatar, avatar_media_type, MAX_AVATAR_BYTES
from starlette.datastructures import UploadFile
from tests import test_auth_transactions


def picture():
    output = BytesIO()
    Image.new('RGB', (500, 300), '#3467df').save(output, format='PNG')
    return output.getvalue()


class AvatarTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_auth_transactions.AuthTransactionTests.asyncSetUp
    asyncTearDown = test_auth_transactions.AuthTransactionTests.asyncTearDown

    async def client(self):
        app = FastAPI(); app.include_router(router)
        async def database():
            async with self.sessions() as db:
                yield db
        async def current(db=Depends(get_db)):
            return await db.get(User, self.user.id)
        app.dependency_overrides[get_db] = database
        app.dependency_overrides[get_current_user] = current
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test')

    async def test_upload_replacement_and_reset_persist_and_old_version_expires(self):
        async with await self.client() as client:
            response = await client.post('/api/v1/auth/me/avatar', files={'file': ('fake.html', picture(), 'text/html')})
            self.assertEqual(response.status_code, 200, response.text)
            url = response.json()['avatar_url']
            async with self.sessions() as reader:
                self.assertEqual((await reader.get(User, self.user.id)).avatar_url, url)
                self.assertIsNotNone(await reader.get(UserAvatar, self.user.id))
            image = await client.get(url)
            self.assertEqual(image.status_code, 200)
            self.assertEqual(image.headers['content-type'], 'image/webp')
            self.assertEqual(image.headers['cache-control'], 'private, no-store')
            with Image.open(BytesIO(image.content)) as decoded:
                self.assertEqual(decoded.size, (256, 256))
                self.assertEqual(decoded.format, 'WEBP')
                self.assertFalse(decoded.getexif())
            replaced = await client.post('/api/v1/auth/me/avatar', files={'file': ('avatar.png', picture(), 'image/png')})
            self.assertNotEqual(replaced.json()['avatar_url'], url)
            self.assertEqual((await client.get(url)).status_code, 404)
            cleared = await client.delete('/api/v1/auth/me/avatar')
            self.assertEqual(cleared.json()['avatar_url'], '')
            self.assertEqual((await client.get(replaced.json()['avatar_url'])).status_code, 404)
            async with self.sessions() as reader:
                self.assertIsNone(await reader.get(UserAvatar, self.user.id))

    async def test_frontend_512_webp_is_saved_as_256_webp(self):
        output = BytesIO()
        Image.new('RGBA', (512, 512), (25, 110, 220, 180)).save(output, format='WEBP')
        async with await self.client() as client:
            response = await client.post('/api/v1/auth/me/avatar', files={'file': ('avatar.webp', output.getvalue(), 'image/webp')})
            self.assertEqual(response.status_code, 200, response.text)
            response = await client.get(response.json()['avatar_url'])
            self.assertEqual(response.headers['content-type'], 'image/webp')
            with Image.open(BytesIO(response.content)) as decoded:
                self.assertEqual(decoded.size, (256, 256))
                self.assertEqual(decoded.format, 'WEBP')
                self.assertEqual(decoded.getpixel((128, 128))[3], 180)

    async def test_legacy_png_avatar_remains_readable_until_replaced(self):
        async with self.sessions() as db:
            user = await db.get(User, self.user.id)
            user.avatar_url = '/api/v1/auth/me/avatar?v=' + 'a' * 32
            db.add(UserAvatar(user_id=user.id, version='a' * 32, image=picture()))
            await db.commit()
        async with await self.client() as client:
            response = await client.get('/api/v1/auth/me/avatar?v=' + 'a' * 32)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['content-type'], 'image/png')
            self.assertEqual(response.content, picture())

    async def test_invalid_oversize_and_unsupported_uploads_preserve_existing_avatar(self):
        async with await self.client() as client:
            original = (await client.post('/api/v1/auth/me/avatar', files={'file': ('ok.png', picture())})).json()['avatar_url']
            for data, expected in [(b'', 422), (b'<svg onload="alert(1)"/>', 422), (b'x' * (MAX_AVATAR_BYTES + 1), 413), (picture()[:50], 422)]:
                response = await client.post('/api/v1/auth/me/avatar', files={'file': ('image.png', data, 'image/png')})
                self.assertEqual(response.status_code, expected, response.text)
            self.assertEqual((await client.get('/api/v1/auth/me')).json()['avatar_url'], original)
            self.assertEqual((await client.get(original)).status_code, 200)

    async def test_other_account_cannot_read_avatar_and_anonymous_requests_are_denied(self):
        async with await self.client() as client:
            url = (await client.post('/api/v1/auth/me/avatar', files={'file': ('ok.png', picture())})).json()['avatar_url']
            async with self.sessions() as db:
                other = User(username='other-avatar', email='other-avatar@example.com', password_hash='x')
                db.add(other); await db.commit()
            self.user = other
            self.assertEqual((await client.get(url)).status_code, 404)
        app = FastAPI(); app.include_router(router)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            self.assertIn((await client.get('/api/v1/auth/me/avatar')).status_code, (401, 403))
            self.assertIn((await client.post('/api/v1/auth/me/avatar', files={'file': ('ok.png', picture())})).status_code, (401, 403))
            self.assertIn((await client.delete('/api/v1/auth/me/avatar')).status_code, (401, 403))

    async def test_failed_commit_does_not_publish_avatar(self):
        async with self.sessions() as writer:
            current = await writer.get(User, self.user.id)
            with patch.object(writer, 'commit', AsyncMock(side_effect=RuntimeError('commit rejected'))):
                with self.assertRaisesRegex(RuntimeError, 'commit rejected'):
                    await upload_avatar(UploadFile(BytesIO(picture()), filename='ok.png'), current, writer)
            await writer.rollback()
        async with self.sessions() as reader:
            self.assertEqual((await reader.get(User, self.user.id)).avatar_url, '')
            self.assertIsNone(await reader.get(UserAvatar, self.user.id))


class AvatarDecodeTests(unittest.TestCase):
    def test_supported_formats_are_normalized_without_metadata(self):
        for format in ('PNG', 'JPEG', 'WEBP'):
            with self.subTest(format=format):
                original = Image.new('RGB', (320, 180), '#3467df')
                exif = Image.Exif()
                exif[0x013B] = 'Private author'
                data = BytesIO()
                original.save(data, format=format, exif=exif)
                with Image.open(BytesIO(normalize_avatar(data.getvalue()))) as result:
                    self.assertEqual(result.format, 'WEBP')
                    self.assertEqual(result.size, (256, 256))
                    self.assertFalse(any(key in result.info for key in ('exif', 'icc_profile', 'xmp')))
                    self.assertFalse(result.getexif())

    def test_pixel_limit_checked_before_loading_image(self):
        with patch('app.services.avatars.Image.open') as opened:
            source = opened.return_value.__enter__.return_value
            source.format, source.width, source.height = 'PNG', 5000, 5000
            with self.assertRaisesRegex(ValueError, '像素'):
                normalize_avatar(b'input')
            source.load.assert_not_called()

    def test_server_bounds_bytes_and_detects_stored_formats(self):
        for data in (b'', b'x' * (MAX_AVATAR_BYTES + 1)):
            with self.assertRaisesRegex(ValueError, '2 MB'):
                normalize_avatar(data)
        self.assertEqual(avatar_media_type(picture()), 'image/png')
        self.assertEqual(avatar_media_type(normalize_avatar(picture())), 'image/webp')
        with self.assertRaises(ValueError):
            avatar_media_type(b'<script>not an avatar</script>')
