"""Decode and re-encode uploads; never serve original user-supplied bytes."""
from io import BytesIO
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_AVATAR_BYTES = 2 * 1024 * 1024
MAX_AVATAR_PIXELS = 16_000_000


def normalize_avatar(data: bytes) -> bytes:
    if not data or len(data) > MAX_AVATAR_BYTES:
        raise ValueError("头像必须为不超过 2 MB 的非空图片")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ValueError("请选择 PNG、JPEG 或 WebP 图片")
                if source.width * source.height > MAX_AVATAR_PIXELS:
                    raise ValueError("图片像素过大，请选择不超过 1600 万像素的图片")
                source.load()
                image = ImageOps.fit(ImageOps.exif_transpose(source).convert("RGBA"), (256, 256), method=Image.Resampling.LANCZOS)
                image.info.clear()
                output = BytesIO()
                image.save(output, format="WEBP", quality=85, method=6)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError("图片无法读取，请重新选择有效图片") from error


def avatar_media_type(data: bytes) -> str:
    """Old installations may still contain normalized PNG avatars."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ValueError("头像格式无效")
