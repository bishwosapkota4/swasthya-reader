"""Nepali text-to-speech. edge-tts first, gTTS fallback. Swap in MMS-TTS later if time allows."""
import asyncio
import logging
import re
import time
import uuid

from .config import MEDIA_DIR, TTS_VOICE

logger = logging.getLogger(__name__)


def tts_text(summary: str, tips: dict) -> str:
    """Build the text that gets spoken: summary + short tips."""
    lines = [summary.strip()]
    for key, label in (("diet", "खानपान"), ("lifestyle", "जीवनशैली"), ("behaviour", "बानी")):
        items = tips.get(key) or []
        if items:
            lines.append(f"{label}: " + " ".join(i.strip().rstrip("।.") + "।" for i in items))
    return "\n".join(l for l in lines if l)


def _clean(text: str) -> str:
    text = re.sub(r"[*_#`>\[\]()]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


async def _edge(text: str, path) -> None:
    import edge_tts

    await edge_tts.Communicate(text, TTS_VOICE).save(str(path))


def _gtts(text: str, path) -> None:
    from gtts import gTTS

    gTTS(text=text, lang="ne").save(str(path))


def cleanup_old_audio(max_age_seconds: int = 3600) -> None:
    cutoff = time.time() - max_age_seconds
    for path in MEDIA_DIR.glob("*.mp3"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except FileNotFoundError:
            continue
        except OSError:
            logger.warning("audio_cleanup_failed output=%s", path.name)


def synthesize(text: str) -> str:
    """Return a URL path to an mp3 of the Nepali text."""
    text = _clean(text)
    if not text:
        raise ValueError("Nothing to speak")
    name = f"{uuid.uuid4().hex}.mp3"
    path = MEDIA_DIR / name
    try:
        asyncio.run(_edge(text, path))
        logger.info("tts_engine=edge-tts output=%s", name)
    except Exception:
        _gtts(text, path)
        logger.warning("tts_engine=gTTS output=%s", name)
    return f"/media/{name}"
