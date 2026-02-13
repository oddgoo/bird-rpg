"""Utilities for rendering a nest showcase image for Discord embeds."""

import asyncio
import io
import os
import urllib.parse
from typing import Any

from PIL import Image, ImageOps

import data.storage as db
from config.config import SPECIES_IMAGES_DIR
from data.models import load_bird_species, load_treasures
from utils.logging import log_debug


CANVAS_WIDTH = 1000
CANVAS_HEIGHT = 1400

CARD_X = 70
CARD_Y = 70
CARD_WIDTH = CANVAS_WIDTH - (CARD_X * 2)
CARD_HEIGHT = CANVAS_HEIGHT - (CARD_Y * 2)

FEATURED_X = CARD_X + 60
FEATURED_Y = CARD_Y + 80
FEATURED_WIDTH = CARD_WIDTH - 120
FEATURED_HEIGHT = 760

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
STATIC_IMAGES_DIR = os.path.join(PROJECT_ROOT, "static", "images")
PAPYRUS_PATH = os.path.join(STATIC_IMAGES_DIR, "papyrus.jpg")
NEST_OVERLAY_PATH = os.path.join(STATIC_IMAGES_DIR, "ui", "nest.png")
DECORATIONS_DIR = os.path.join(STATIC_IMAGES_DIR, "decorations")
SPECIAL_BIRDS_DIR = os.path.join(STATIC_IMAGES_DIR, "special-birds")


class NestShowcaseError(Exception):
    """Raised when a nest cannot be rendered for showcase."""


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def _float_value(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _cover_crop(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    scale = max(target_width / image.width, target_height / image.height)
    resized = image.resize(
        (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - target_width) // 2)
    top = max(0, (resized.height - target_height) // 2)
    return resized.crop((left, top, left + target_width, top + target_height))


def _compute_bird_image_paths(scientific_name: str, rarity: str) -> list[str]:
    if rarity == "Special":
        return [os.path.join(SPECIAL_BIRDS_DIR, f"{scientific_name}.png")]

    quoted = urllib.parse.quote(scientific_name)
    return [
        os.path.join(SPECIES_IMAGES_DIR, f"{quoted}.jpg"),
        os.path.join(SPECIES_IMAGES_DIR, f"{scientific_name}.jpg"),
        os.path.join(SPECIES_IMAGES_DIR, f"{quoted}.jpeg"),
        os.path.join(SPECIES_IMAGES_DIR, f"{scientific_name}.jpeg"),
    ]


def _pick_featured_image(player: dict, birds: list[dict], species_by_name: dict[str, dict]) -> tuple[str, str]:
    ordered_candidates = []
    featured = player.get("featured_bird_scientific_name")
    if featured:
        ordered_candidates.append(featured)

    for bird in birds:
        scientific_name = bird.get("scientific_name")
        if scientific_name and scientific_name not in ordered_candidates:
            ordered_candidates.append(scientific_name)

    attempted_candidates = []
    for scientific_name in ordered_candidates:
        species = species_by_name.get(scientific_name, {})
        rarity = species.get("rarity", "common")
        attempted_candidates.append(scientific_name)
        for image_path in _compute_bird_image_paths(scientific_name, rarity):
            if os.path.exists(image_path):
                return scientific_name, image_path

    if attempted_candidates:
        raise NestShowcaseError(
            "This nest has birds, but no local bird image files were found for showcasing yet."
        )
    raise NestShowcaseError("This user does not have a showcaseable nest yet.")


async def build_showcase_payload(user_id: str, allow_fallback_image: bool = False) -> dict:
    """Build a normalized payload for nest showcase rendering."""
    user_id = str(user_id)

    player = await db.get_player(user_id)
    if not player:
        raise NestShowcaseError("This user does not have a showcaseable nest yet.")

    birds = await db.get_player_birds(user_id)
    egg = await db.get_egg(user_id)
    nest_treasures = await db.get_nest_treasures(user_id)
    bird_species = await load_bird_species()
    species_by_name = {item.get("scientificName"): item for item in bird_species}

    featured_scientific_name = None
    featured_image_path = None
    if birds:
        try:
            featured_scientific_name, featured_image_path = _pick_featured_image(player, birds, species_by_name)
        except NestShowcaseError:
            if not allow_fallback_image:
                raise

    if not featured_image_path:
        if allow_fallback_image and os.path.exists(PAPYRUS_PATH):
            featured_image_path = PAPYRUS_PATH
        else:
            raise NestShowcaseError("This user does not have a showcaseable nest yet.")

    treasures_data = load_treasures()
    treasure_by_id = {}
    for category in treasures_data.values():
        for treasure in category:
            treasure_by_id[treasure["id"]] = treasure

    stickers = []
    for row in nest_treasures:
        treasure_id = row.get("treasure_id")
        treasure = treasure_by_id.get(treasure_id)
        if not treasure or treasure.get("type") != "sticker":
            continue

        x_default = _float_value(treasure.get("x"), 50.0)
        y_default = _float_value(treasure.get("y"), 50.0)
        size_default = _float_value(treasure.get("size"), 100.0)

        stickers.append({
            "treasure_id": treasure_id,
            "image_path": os.path.join(DECORATIONS_DIR, f"{treasure_id}.png"),
            "x": _clamp(_float_value(row.get("x"), x_default), 0.0, 100.0),
            "y": _clamp(_float_value(row.get("y"), y_default), 0.0, 100.0),
            "size": _clamp(_float_value(row.get("size"), size_default), 5.0, 100.0),
            "rotation": _float_value(row.get("rotation"), 0.0) % 360,
            "z_index": _int_value(row.get("z_index"), 0),
        })

    stickers.sort(key=lambda item: item["z_index"])

    return {
        "user_id": user_id,
        "nest_name": player.get("nest_name", "Some Bird's Nest"),
        "discord_username": player.get("discord_username", "Unknown User"),
        "twigs": int(player.get("twigs", 0)),
        "seeds": int(player.get("seeds", 0)),
        "chicks": len(birds),
        "egg_progress": egg.get("brooding_progress") if egg else None,
        "featured_scientific_name": featured_scientific_name,
        "featured_image_path": featured_image_path,
        "decorations": stickers,
    }


def _render_showcase_png(payload: dict) -> bytes:
    canvas = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (249, 239, 214, 255))

    if os.path.exists(PAPYRUS_PATH):
        papyrus = Image.open(PAPYRUS_PATH).convert("RGB")
        papyrus = _cover_crop(papyrus, CANVAS_WIDTH, CANVAS_HEIGHT).convert("RGBA")
        canvas.paste(papyrus, (0, 0))

    card = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), (255, 255, 255, 215))
    card = ImageOps.expand(card, border=4, fill=(120, 75, 30, 240))
    canvas.paste(card, (CARD_X, CARD_Y), card)

    featured = Image.open(payload["featured_image_path"]).convert("RGB")
    featured = _cover_crop(featured, FEATURED_WIDTH, FEATURED_HEIGHT).convert("RGBA")
    canvas.paste(featured, (FEATURED_X, FEATURED_Y))

    decorations = sorted(payload.get("decorations", []), key=lambda item: _int_value(item.get("z_index"), 0))
    for decoration in decorations:
        image_path = decoration["image_path"]
        if not os.path.exists(image_path):
            log_debug(f"Showcase sticker missing: {image_path}")
            continue

        sticker = Image.open(image_path).convert("RGBA")
        target_width = max(1, int(FEATURED_WIDTH * (decoration["size"] / 100.0)))
        target_height = max(1, int(sticker.height * (target_width / sticker.width)))
        sticker = sticker.resize((target_width, target_height), Image.Resampling.LANCZOS)
        sticker = sticker.rotate(-decoration["rotation"], expand=True, resample=Image.Resampling.BICUBIC)

        center_x = FEATURED_X + int(FEATURED_WIDTH * (decoration["x"] / 100.0))
        center_y = FEATURED_Y + int(FEATURED_HEIGHT * (decoration["y"] / 100.0))
        paste_x = center_x - (sticker.width // 2)
        paste_y = center_y - (sticker.height // 2)
        canvas.paste(sticker, (paste_x, paste_y), sticker)

    if os.path.exists(NEST_OVERLAY_PATH):
        nest_overlay = Image.open(NEST_OVERLAY_PATH).convert("RGBA")
        target_width = int(FEATURED_WIDTH * 1.15)
        target_height = max(1, int(nest_overlay.height * (target_width / nest_overlay.width)))
        nest_overlay = nest_overlay.resize((target_width, target_height), Image.Resampling.LANCZOS)
        overlay_x = FEATURED_X + ((FEATURED_WIDTH - target_width) // 2)
        overlay_y = FEATURED_Y + int(FEATURED_HEIGHT * 0.84)
        canvas.paste(nest_overlay, (overlay_x, overlay_y), nest_overlay)

    output = io.BytesIO()
    canvas.convert("RGB").save(output, format="PNG")
    output.seek(0)
    return output.getvalue()


async def render_showcase_png(payload: dict) -> bytes:
    """Render showcase image asynchronously as PNG bytes."""
    return await asyncio.to_thread(_render_showcase_png, payload)
