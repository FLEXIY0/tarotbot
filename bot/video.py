"""Сборка кадров Pillow в MP4 через ffmpeg (пайп rawvideo -> libx264)."""

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from bot.deck import DrawnCard
from bot.render import FPS, iter_frames, render_collage, with_fade_in
from bot.spreads import Spread

log = logging.getLogger(__name__)


def ffmpeg_exe() -> str:
    if env := os.getenv("FFMPEG_PATH"):
        return env
    if found := shutil.which("ffmpeg"):
        return found
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def render_reading_video(drawn: list[DrawnCard], spread: Spread, subtitle: str = "") -> Path | None:
    """Возвращает путь к mp4 или None при сбое (тогда шлём статичный коллаж)."""
    frames = with_fade_in(iter_frames(drawn, spread, subtitle))
    first = next(frames)
    w, h = first.size
    out = Path(tempfile.mkstemp(suffix=".mp4", prefix="tarot_")[1])
    cmd = [
        ffmpeg_exe(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "26",
        "-movflags", "+faststart", str(out),
    ]
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdin is not None
        proc.stdin.write(first.tobytes())
        for f in frames:
            proc.stdin.write(f.tobytes())
        proc.stdin.close()
        if proc.wait(timeout=120) != 0:
            stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            raise RuntimeError(f"ffmpeg exit {proc.returncode}: {stderr[:500]}")
        return out
    except Exception:
        log.exception("Не удалось собрать видео расклада (%s)", spread.key)
        out.unlink(missing_ok=True)
        return None


def render_collage_jpeg(drawn: list[DrawnCard], spread: Spread, subtitle: str = "") -> Path:
    img = render_collage(drawn, spread, subtitle)
    out = Path(tempfile.mkstemp(suffix=".jpg", prefix="tarot_")[1])
    img.save(out, "JPEG", quality=90)
    return out
