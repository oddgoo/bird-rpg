import os
import random
from collections import OrderedDict

import aiohttp

from config.config import XENO_CANTO_API_KEY
from utils.logging import log_debug

XENO_CANTO_API_URL = "https://xeno-canto.org/api/3/recordings"
FALLBACK_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "audio", "birdsongs")

# In-memory LRU cache: scientific_name -> mp3 bytes
_cache = OrderedDict()
_CACHE_MAX = 50


def _cache_get(key: str) -> bytes | None:
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    return None


def _cache_put(key: str, data: bytes):
    _cache[key] = data
    _cache.move_to_end(key)
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)


async def fetch_birdsong_audio(scientific_name: str) -> bytes | None:
    """Fetch a short bird song MP3 from xeno-canto. Returns bytes or None."""
    if not XENO_CANTO_API_KEY or not scientific_name:
        return None

    cached = _cache_get(scientific_name)
    if cached is not None:
        return cached

    parts = scientific_name.split()
    if len(parts) < 2:
        return None

    genus, species = parts[0], parts[1]

    try:
        async with aiohttp.ClientSession() as session:
            # Try quality A first, fall back to B
            for quality in ("A", "B"):
                params = {
                    "query": f'gen:{genus} sp:{species} len:"0-20" q:{quality}',
                    "key": XENO_CANTO_API_KEY,
                }

                async with session.get(XENO_CANTO_API_URL, params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    recordings = data.get("recordings", [])
                    if recordings:
                        break
            else:
                return None

            if not recordings:
                return None

            recording = random.choice(recordings[:10])
            file_url = recording.get("file")
            if not file_url:
                return None

            # Ensure https
            if file_url.startswith("//"):
                file_url = "https:" + file_url

            async with session.get(file_url, timeout=aiohttp.ClientTimeout(total=10)) as dl_resp:
                if dl_resp.status != 200:
                    return None
                # Safety: max 1MB
                content_length = dl_resp.headers.get("Content-Length")
                if content_length and int(content_length) > 1_000_000:
                    return None
                mp3_data = await dl_resp.read()
                if len(mp3_data) > 1_000_000:
                    return None

            _cache_put(scientific_name, mp3_data)
            log_debug(f"Fetched birdsong for {scientific_name} ({len(mp3_data)} bytes)")
            return mp3_data

    except Exception as e:
        log_debug(f"Error fetching birdsong for {scientific_name}: {e}")
        return None


def get_fallback_audio() -> tuple[bytes, str] | None:
    """Pick a random fallback MP3 from the local directory."""
    try:
        files = [f for f in os.listdir(FALLBACK_DIR) if f.endswith(".mp3")]
        if not files:
            return None
        chosen = random.choice(files)
        path = os.path.join(FALLBACK_DIR, chosen)
        with open(path, "rb") as f:
            data = f.read()
        name = os.path.splitext(chosen)[0].replace("_", " ").title()
        return data, name
    except Exception as e:
        log_debug(f"Error loading fallback birdsong: {e}")
        return None


async def get_birdsong_for_bird(bird: dict) -> tuple[bytes | None, str]:
    """Main entry point: try xeno-canto, fall back to local files.

    Returns (mp3_bytes_or_None, display_name).
    """
    common_name = bird.get("common_name", "A bird")
    scientific_name = bird.get("scientific_name", "")

    # Try xeno-canto first
    mp3_data = await fetch_birdsong_audio(scientific_name)
    if mp3_data:
        return mp3_data, common_name

    # Fall back to local files
    fallback = get_fallback_audio()
    if fallback:
        return fallback[0], common_name

    return None, common_name
