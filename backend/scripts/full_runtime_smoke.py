"""Exercise optional browser/media dependencies with local synthetic fixtures only."""
import argparse
import asyncio
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


async def verify():
    # Do not load a user's .env, provider credentials, database or storage.
    from app.config import Settings, get_settings
    Settings.model_config["env_file"] = None
    for key in Settings.model_fields:
        os.environ.pop(key, None)
    os.environ.update({"CRAWLER_ENABLED": "true", "CRAWLER_HEADLESS": "true",
                       "MEDIA_FRAME_INTERVAL_SECONDS": "1", "MEDIA_MAX_VIDEO_FRAMES": "2"})
    get_settings.cache_clear()
    from PIL import Image
    from app.services.crawler import get_crawler
    from app.services.crawler.browser_manager import BrowserManager
    from app.services.crawler.stealth_patcher import apply_stealth
    from app.services.multimodal import client, perceptual_hash, validate_media, video_parts

    checks = []
    manager = BrowserManager()
    page = None
    try:
        assert get_crawler("tieba") is not None, "enabled browser adapter missing"
        page = await manager.get_page()
        await apply_stealth(page)
        await page.set_content('<main id="fixture">Local rendered evidence</main>')
        assert await page.locator("#fixture").inner_text() == "Local rendered evidence"
        assert await page.evaluate("1 + 2") == 3
        checks.append("project BrowserManager launches Chromium and renders local fixture")
        assert manager._task_lock.locked()
    finally:
        try:
            if page is not None:
                try:
                    await page.close()
                finally:
                    await manager.mark_task_done()
        finally:
            await manager.close()
    assert not manager._task_lock.locked(), "browser slot leaked"
    assert manager._browser is None and manager._playwright is None
    checks.append("browser task slot and processes released")

    image = io.BytesIO()
    Image.new("RGB", (64, 48), "blue").save(image, "PNG")
    assert validate_media("fixture.png", image.getvalue()) == ("image", "image/png")
    assert len(perceptual_hash(image.getvalue())) == 16
    checks.append("Pillow signature and perceptual hash")

    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg and shutil.which("ffprobe"), "ffmpeg/ffprobe missing"
    with tempfile.TemporaryDirectory(prefix="infopulse-media-smoke-") as directory:
        video = Path(directory) / "fixture.mp4"
        subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i",
                        "color=c=blue:s=64x48:r=10:d=3", "-f", "lavfi", "-i",
                        "sine=frequency=440:sample_rate=16000:duration=3",
                        "-c:v", "mpeg4", "-c:a", "aac", "-shortest", str(video)],
                       check=True, timeout=30)
        data = video.read_bytes()
        assert validate_media(video.name, data) == ("video", "video/mp4")
        temporary, metadata, frames, audio = await asyncio.to_thread(video_parts, data, ".mp4")
        try:
            assert 2.5 <= float(metadata["format"]["duration"]) <= 3.5
            assert len(frames) == 2, "configured frame cap not enforced"
            assert [index for index, _ in frames] == [1, 2]
            for _, frame in frames:
                assert validate_media("frame.jpg", frame) == ("image", "image/jpeg")
                assert Image.open(io.BytesIO(frame)).size == (64, 48)
            assert audio is not None
            assert validate_media("audio.wav", audio) == ("audio", "audio/wav")
        finally:
            root = Path(temporary.name)
            temporary.cleanup()
        assert not root.exists(), "video temporary files leaked"
    checks.append("real ffprobe metadata, bounded ffmpeg frames and WAV audio extraction")
    try:
        client()
    except RuntimeError as exc:
        assert "credential" in str(exc)
    else:
        raise AssertionError("unconfigured model must not become available")
    checks.append("missing provider credentials fail closed without a paid request")
    return {"completed": True, "checks": checks,
            "scope": "local Chromium and media dependencies; not external sources or model quality"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("../acceptance-artifacts/full-runtime.json"))
    args = parser.parse_args()
    result = {"completed": False}
    try:
        result = asyncio.run(verify())
        print(json.dumps(result, indent=2))
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
