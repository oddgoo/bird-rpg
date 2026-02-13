import io
import os
import urllib.parse
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from utils import nest_showcase


def _write_image(path, color, size=(200, 200), mode="RGB"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    image = Image.new(mode, size, color)
    image.save(path)


@pytest.mark.asyncio
async def test_build_showcase_payload_falls_back_when_featured_missing(tmp_path, monkeypatch):
    species_dir = tmp_path / "species_images"
    species_dir.mkdir(parents=True, exist_ok=True)

    fallback_scientific = "Fallback Bird"
    fallback_path = species_dir / f"{urllib.parse.quote(fallback_scientific)}.jpg"
    _write_image(str(fallback_path), (10, 20, 200))

    monkeypatch.setattr(nest_showcase, "SPECIES_IMAGES_DIR", str(species_dir))

    player = {
        "user_id": "123",
        "nest_name": "Test Nest",
        "featured_bird_scientific_name": "Missing Bird",
        "twigs": 12,
        "seeds": 7,
    }
    birds = [{"scientific_name": fallback_scientific}]
    species = [
        {"scientificName": "Missing Bird", "rarity": "common"},
        {"scientificName": fallback_scientific, "rarity": "common"},
    ]

    with patch("utils.nest_showcase.db.get_player", new=AsyncMock(return_value=player)), \
         patch("utils.nest_showcase.db.get_player_birds", new=AsyncMock(return_value=birds)), \
         patch("utils.nest_showcase.db.get_egg", new=AsyncMock(return_value=None)), \
         patch("utils.nest_showcase.db.get_nest_treasures", new=AsyncMock(return_value=[])), \
         patch("utils.nest_showcase.load_bird_species", new=AsyncMock(return_value=species)), \
         patch("utils.nest_showcase.load_treasures", return_value={}):
        payload = await nest_showcase.build_showcase_payload("123")

    assert payload["featured_scientific_name"] == fallback_scientific
    assert payload["featured_image_path"] == str(fallback_path)


@pytest.mark.asyncio
async def test_build_showcase_payload_uses_papyrus_fallback_for_caller(tmp_path, monkeypatch):
    papyrus_path = tmp_path / "papyrus.jpg"
    _write_image(str(papyrus_path), (240, 230, 180))
    monkeypatch.setattr(nest_showcase, "PAPYRUS_PATH", str(papyrus_path))

    player = {
        "user_id": "123",
        "nest_name": "Empty Bird Nest",
        "featured_bird_scientific_name": None,
        "twigs": 5,
        "seeds": 2,
    }

    with patch("utils.nest_showcase.db.get_player", new=AsyncMock(return_value=player)), \
         patch("utils.nest_showcase.db.get_player_birds", new=AsyncMock(return_value=[])), \
         patch("utils.nest_showcase.db.get_egg", new=AsyncMock(return_value=None)), \
         patch("utils.nest_showcase.db.get_nest_treasures", new=AsyncMock(return_value=[])), \
         patch("utils.nest_showcase.load_bird_species", new=AsyncMock(return_value=[])), \
         patch("utils.nest_showcase.load_treasures", return_value={}):
        payload = await nest_showcase.build_showcase_payload("123", allow_fallback_image=True)

    assert payload["featured_scientific_name"] is None
    assert payload["featured_image_path"] == str(papyrus_path)
    assert payload["chicks"] == 0


@pytest.mark.asyncio
async def test_build_showcase_payload_missing_local_bird_images_error():
    player = {
        "user_id": "123",
        "nest_name": "No Image Nest",
        "featured_bird_scientific_name": "Unknown Bird",
        "twigs": 5,
        "seeds": 2,
    }
    birds = [{"scientific_name": "Unknown Bird"}]
    species = [{"scientificName": "Unknown Bird", "rarity": "common"}]

    with patch("utils.nest_showcase.db.get_player", new=AsyncMock(return_value=player)), \
         patch("utils.nest_showcase.db.get_player_birds", new=AsyncMock(return_value=birds)), \
         patch("utils.nest_showcase.db.get_egg", new=AsyncMock(return_value=None)), \
         patch("utils.nest_showcase.db.get_nest_treasures", new=AsyncMock(return_value=[])), \
         patch("utils.nest_showcase.load_bird_species", new=AsyncMock(return_value=species)), \
         patch("utils.nest_showcase.load_treasures", return_value={}):
        with pytest.raises(nest_showcase.NestShowcaseError) as exc_info:
            await nest_showcase.build_showcase_payload("123", allow_fallback_image=False)

    assert "no local bird image files" in str(exc_info.value)


@pytest.mark.asyncio
async def test_render_showcase_png_respects_z_index(tmp_path, monkeypatch):
    papyrus_path = tmp_path / "papyrus.jpg"
    featured_path = tmp_path / "featured.jpg"
    nest_overlay_path = tmp_path / "nest.png"
    low_path = tmp_path / "low.png"
    high_path = tmp_path / "high.png"

    _write_image(str(papyrus_path), (255, 255, 255))
    _write_image(str(featured_path), (30, 30, 200))
    _write_image(str(nest_overlay_path), (0, 0, 0, 0), mode="RGBA")
    _write_image(str(low_path), (255, 0, 0, 255), mode="RGBA")
    _write_image(str(high_path), (0, 255, 0, 255), mode="RGBA")

    monkeypatch.setattr(nest_showcase, "PAPYRUS_PATH", str(papyrus_path))
    monkeypatch.setattr(nest_showcase, "NEST_OVERLAY_PATH", str(nest_overlay_path))

    payload = {
        "featured_image_path": str(featured_path),
        "decorations": [
            {"image_path": str(high_path), "x": 50, "y": 50, "size": 20, "rotation": 0, "z_index": 2},
            {"image_path": str(low_path), "x": 50, "y": 50, "size": 20, "rotation": 0, "z_index": 1},
        ],
    }

    png = await nest_showcase.render_showcase_png(payload)
    image = Image.open(io.BytesIO(png)).convert("RGB")

    center_x = nest_showcase.FEATURED_X + int(nest_showcase.FEATURED_WIDTH * 0.5)
    center_y = nest_showcase.FEATURED_Y + int(nest_showcase.FEATURED_HEIGHT * 0.5)
    assert image.getpixel((center_x, center_y)) == (0, 255, 0)


@pytest.mark.asyncio
async def test_render_showcase_png_skips_missing_stickers(tmp_path, monkeypatch):
    papyrus_path = tmp_path / "papyrus.jpg"
    featured_path = tmp_path / "featured.jpg"
    nest_overlay_path = tmp_path / "nest.png"

    _write_image(str(papyrus_path), (255, 255, 255))
    _write_image(str(featured_path), (30, 30, 200))
    _write_image(str(nest_overlay_path), (0, 0, 0, 0), mode="RGBA")

    monkeypatch.setattr(nest_showcase, "PAPYRUS_PATH", str(papyrus_path))
    monkeypatch.setattr(nest_showcase, "NEST_OVERLAY_PATH", str(nest_overlay_path))

    payload = {
        "featured_image_path": str(featured_path),
        "decorations": [
            {"image_path": str(tmp_path / "missing.png"), "x": 50, "y": 50, "size": 20, "rotation": 0, "z_index": 1},
        ],
    }

    png = await nest_showcase.render_showcase_png(payload)
    assert isinstance(png, bytes)
    assert len(png) > 0


@pytest.mark.asyncio
async def test_render_showcase_png_returns_nonempty_bytes(tmp_path, monkeypatch):
    papyrus_path = tmp_path / "papyrus.jpg"
    featured_path = tmp_path / "featured.jpg"
    nest_overlay_path = tmp_path / "nest.png"

    _write_image(str(papyrus_path), (255, 255, 255))
    _write_image(str(featured_path), (30, 30, 200))
    _write_image(str(nest_overlay_path), (0, 0, 0, 0), mode="RGBA")

    monkeypatch.setattr(nest_showcase, "PAPYRUS_PATH", str(papyrus_path))
    monkeypatch.setattr(nest_showcase, "NEST_OVERLAY_PATH", str(nest_overlay_path))

    payload = {"featured_image_path": str(featured_path), "decorations": []}
    png = await nest_showcase.render_showcase_png(payload)

    assert isinstance(png, bytes)
    assert len(png) > 0
