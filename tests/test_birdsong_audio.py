import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from utils.birdsong_audio import (
    fetch_birdsong_audio,
    get_fallback_audio,
    get_birdsong_for_bird,
    _cache,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the LRU cache before each test."""
    _cache.clear()
    yield
    _cache.clear()


@pytest.mark.asyncio
async def test_fetch_birdsong_no_scientific_name():
    """Empty scientific name returns None."""
    result = await fetch_birdsong_audio("")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_birdsong_single_word_name():
    """Single-word scientific name (no genus+species) returns None."""
    result = await fetch_birdsong_audio("Casspie")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_birdsong_no_api_key():
    """No API key returns None without making HTTP calls."""
    with patch("utils.birdsong_audio.XENO_CANTO_API_KEY", ""):
        result = await fetch_birdsong_audio("Dacelo novaeguineae")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_birdsong_success():
    """Successful API call returns MP3 bytes and populates cache."""
    fake_mp3 = b"\xff\xfb\x90\x00" * 100  # fake MP3 data

    mock_api_response = MagicMock()
    mock_api_response.status = 200
    mock_api_response.json = AsyncMock(return_value={
        "recordings": [{"file": "//xeno-canto.org/sounds/test.mp3"}]
    })
    mock_api_response.__aenter__ = AsyncMock(return_value=mock_api_response)
    mock_api_response.__aexit__ = AsyncMock(return_value=False)

    mock_dl_response = MagicMock()
    mock_dl_response.status = 200
    mock_dl_response.headers = {"Content-Length": str(len(fake_mp3))}
    mock_dl_response.read = AsyncMock(return_value=fake_mp3)
    mock_dl_response.__aenter__ = AsyncMock(return_value=mock_dl_response)
    mock_dl_response.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=[mock_api_response, mock_dl_response])
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("utils.birdsong_audio.XENO_CANTO_API_KEY", "test-key"), \
         patch("utils.birdsong_audio.aiohttp.ClientSession", return_value=mock_session):
        result = await fetch_birdsong_audio("Dacelo novaeguineae")

    assert result == fake_mp3
    assert "Dacelo novaeguineae" in _cache


@pytest.mark.asyncio
async def test_fetch_birdsong_cache_hit():
    """Cache hit returns data without making HTTP calls."""
    fake_mp3 = b"cached_mp3_data"
    _cache["Dacelo novaeguineae"] = fake_mp3

    with patch("utils.birdsong_audio.XENO_CANTO_API_KEY", "test-key"), \
         patch("utils.birdsong_audio.aiohttp.ClientSession") as mock_cls:
        result = await fetch_birdsong_audio("Dacelo novaeguineae")
        mock_cls.assert_not_called()

    assert result == fake_mp3


def test_get_fallback_audio_with_files(tmp_path):
    """Returns audio bytes when fallback files exist."""
    mp3_data = b"fake_fallback_mp3"
    (tmp_path / "test_bird.mp3").write_bytes(mp3_data)

    with patch("utils.birdsong_audio.FALLBACK_DIR", str(tmp_path)):
        result = get_fallback_audio()

    assert result is not None
    data, name = result
    assert data == mp3_data
    assert name == "Test Bird"


def test_get_fallback_audio_empty_dir(tmp_path):
    """Returns None when no fallback files exist."""
    with patch("utils.birdsong_audio.FALLBACK_DIR", str(tmp_path)):
        result = get_fallback_audio()
    assert result is None


@pytest.mark.asyncio
async def test_get_birdsong_for_bird_uses_api():
    """get_birdsong_for_bird returns API data when available."""
    fake_mp3 = b"api_mp3_data"
    bird = {"common_name": "Laughing Kookaburra", "scientific_name": "Dacelo novaeguineae"}

    with patch("utils.birdsong_audio.fetch_birdsong_audio", new_callable=AsyncMock, return_value=fake_mp3):
        data, name = await get_birdsong_for_bird(bird)

    assert data == fake_mp3
    assert name == "Laughing Kookaburra"


@pytest.mark.asyncio
async def test_get_birdsong_for_bird_fallback():
    """Falls back to local files when API returns None."""
    fallback_mp3 = b"fallback_mp3_data"
    bird = {"common_name": "Laughing Kookaburra", "scientific_name": "Dacelo novaeguineae"}

    with patch("utils.birdsong_audio.fetch_birdsong_audio", new_callable=AsyncMock, return_value=None), \
         patch("utils.birdsong_audio.get_fallback_audio", return_value=(fallback_mp3, "Generic Bird")):
        data, name = await get_birdsong_for_bird(bird)

    assert data == fallback_mp3
    assert name == "Laughing Kookaburra"


@pytest.mark.asyncio
async def test_get_birdsong_for_bird_no_audio():
    """Returns None data when both API and fallback fail."""
    bird = {"common_name": "Laughing Kookaburra", "scientific_name": "Dacelo novaeguineae"}

    with patch("utils.birdsong_audio.fetch_birdsong_audio", new_callable=AsyncMock, return_value=None), \
         patch("utils.birdsong_audio.get_fallback_audio", return_value=None):
        data, name = await get_birdsong_for_bird(bird)

    assert data is None
    assert name == "Laughing Kookaburra"
