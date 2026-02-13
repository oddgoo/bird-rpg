"""
Storage layer: all database operations via Supabase.

Async functions (used by Discord commands) and sync variants (suffixed _sync, used by Flask routes).
Reference data loaders (bird_species.json, plant_species.json, etc.) remain as local JSON reads.
"""

import os
import io
import json
import uuid
import asyncio
import glob as glob_module
from utils.logging import log_debug
from config.config import DATA_PATH, BIRDWATCH_MAX_DIMENSION, BIRDWATCH_JPEG_QUALITY

# ---------------------------------------------------------------------------
# Reference data loaders (read-only JSON bundled with code)
# ---------------------------------------------------------------------------

_research_entities_cache = {}

def load_research_entities(event="default"):
    """Load research entities data from JSON file (read-only reference data, cached).

    For the default event, loads research_entities.json.
    For other events, loads research_entities_{event}.json, falling back to default.
    """
    global _research_entities_cache
    if event in _research_entities_cache:
        return _research_entities_cache[event]

    if event == "default":
        file_path = os.path.join(os.path.dirname(__file__), 'research_entities.json')
    else:
        file_path = os.path.join(os.path.dirname(__file__), f'research_entities_{event}.json')

    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                log_debug(f"Research entities data loaded successfully for event: {event}")
                _research_entities_cache[event] = data
                return data
        # Fallback to default if event file missing
        if event != "default":
            log_debug(f"No research entities for event '{event}', falling back to default")
            return load_research_entities("default")
        log_debug("No existing research entities data, returning empty list")
        return []
    except Exception as e:
        log_debug(f"Error loading research entities data: {e}")
        raise


def load_all_research_entities():
    """Load research entities from ALL event files (default + all event variants).

    Returns a combined list of all entities across all events.
    Used by milestone bonus calculations so bonuses persist across events.
    """
    data_dir = os.path.dirname(__file__)
    all_entities = []
    seen_files = set()

    # Load default
    default_path = os.path.join(data_dir, 'research_entities.json')
    if os.path.exists(default_path):
        seen_files.add(os.path.normpath(default_path))
        all_entities.extend(load_research_entities("default"))

    # Load all event variants
    pattern = os.path.join(data_dir, 'research_entities_*.json')
    for file_path in glob_module.glob(pattern):
        norm_path = os.path.normpath(file_path)
        if norm_path in seen_files:
            continue
        seen_files.add(norm_path)
        # Extract event name from filename: research_entities_{event}.json
        basename = os.path.basename(file_path)
        event_name = basename.replace('research_entities_', '').replace('.json', '')
        all_entities.extend(load_research_entities(event_name))

    return all_entities


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------

async def _client():
    from data.db import get_async_client
    return await get_async_client()


def _sync_client():
    from data.db import get_sync_client
    return get_sync_client()


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------

_DEFAULT_NEST = {
    "nest_name": "Some Bird's Nest",
    "twigs": 0,
    "seeds": 0,
    "inspiration": 0,
    "garden_size": 0,
    "bonus_actions": 0,
    "locked": False,
    "featured_bird_common_name": None,
    "featured_bird_scientific_name": None,
}


async def load_player(user_id):
    """Load a player row, creating one if it doesn't exist. Returns a dict."""
    user_id = str(user_id)
    sb = await _client()
    res = await sb.table("players").select("*").eq("user_id", user_id).execute()
    if res.data:
        return res.data[0]
    # Auto-create
    row = {"user_id": user_id, **_DEFAULT_NEST}
    await sb.table("players").insert(row).execute()
    log_debug(f"Created new player: {user_id}")
    return row


def load_player_sync(user_id):
    user_id = str(user_id)
    sb = _sync_client()
    res = sb.table("players").select("*").eq("user_id", user_id).execute()
    if res.data:
        return res.data[0]
    row = {"user_id": user_id, **_DEFAULT_NEST}
    sb.table("players").insert(row).execute()
    return row


def get_player_sync(user_id):
    """Read-only player lookup. Returns dict or None. Does NOT auto-create."""
    user_id = str(user_id)
    sb = _sync_client()
    res = sb.table("players").select("*").eq("user_id", user_id).execute()
    return res.data[0] if res.data else None


async def update_player(user_id, **fields):
    """Update specific fields on a player row."""
    user_id = str(user_id)
    sb = await _client()
    await sb.table("players").update(fields).eq("user_id", user_id).execute()


def update_player_sync(user_id, **fields):
    user_id = str(user_id)
    sb = _sync_client()
    sb.table("players").update(fields).eq("user_id", user_id).execute()


async def increment_player_field(user_id, field, amount):
    """Atomically increment a numeric player field via RPC."""
    sb = await _client()
    await sb.rpc("increment_player_field", {
        "p_user_id": str(user_id),
        "field_name": field,
        "amount": amount,
    }).execute()


def increment_player_field_sync(user_id, field, amount):
    sb = _sync_client()
    sb.rpc("increment_player_field", {
        "p_user_id": str(user_id),
        "field_name": field,
        "amount": amount,
    }).execute()


async def load_all_players():
    """Load all player rows."""
    sb = await _client()
    res = await sb.table("players").select("*").limit(10000).execute()
    return res.data or []


def load_all_players_sync():
    sb = _sync_client()
    res = sb.table("players").select("*").limit(10000).execute()
    return res.data or []


# ---------------------------------------------------------------------------
# Common Nest
# ---------------------------------------------------------------------------

async def load_common_nest():
    sb = await _client()
    res = await sb.table("common_nest").select("*").eq("id", 1).execute()
    if res.data:
        return res.data[0]
    await sb.table("common_nest").insert({"id": 1, "twigs": 0, "seeds": 0}).execute()
    return {"id": 1, "twigs": 0, "seeds": 0}


def load_common_nest_sync():
    sb = _sync_client()
    res = sb.table("common_nest").select("*").eq("id", 1).execute()
    if res.data:
        return res.data[0]
    sb.table("common_nest").insert({"id": 1, "twigs": 0, "seeds": 0}).execute()
    return {"id": 1, "twigs": 0, "seeds": 0}


async def increment_common_nest(field, amount):
    sb = await _client()
    await sb.rpc("increment_common_nest", {"field_name": field, "amount": amount}).execute()


def increment_common_nest_sync(field, amount):
    sb = _sync_client()
    sb.rpc("increment_common_nest", {"field_name": field, "amount": amount}).execute()


# ---------------------------------------------------------------------------
# Player Birds
# ---------------------------------------------------------------------------

async def get_player_birds(user_id):
    """Return list of bird dicts for a player."""
    sb = await _client()
    res = await sb.table("player_birds").select("*").eq("user_id", str(user_id)).execute()
    return res.data or []


async def get_bird_counts_for_users(user_ids):
    """Return a dict of user_id -> bird count for the given users."""
    normalized_ids = [str(uid) for uid in user_ids]
    if not normalized_ids:
        return {}

    sb = await _client()
    res = await sb.table("player_birds").select("user_id").in_("user_id", normalized_ids).execute()

    counts = {}
    for row in (res.data or []):
        user_id = row["user_id"]
        counts[user_id] = counts.get(user_id, 0) + 1
    return counts


def get_player_birds_sync(user_id):
    sb = _sync_client()
    res = sb.table("player_birds").select("*").eq("user_id", str(user_id)).execute()
    return res.data or []


async def add_bird(user_id, common_name, scientific_name):
    """Add a bird to a player's nest. Returns the inserted row."""
    sb = await _client()
    res = await sb.table("player_birds").insert({
        "user_id": str(user_id),
        "common_name": common_name,
        "scientific_name": scientific_name,
    }).execute()
    return res.data[0] if res.data else None


async def remove_bird(bird_id):
    """Remove a bird by its DB id."""
    sb = await _client()
    await sb.table("player_birds").delete().eq("id", bird_id).execute()


async def remove_bird_by_name(user_id, common_name):
    """Remove the first bird matching common_name from a player's nest. Returns the removed bird or None."""
    sb = await _client()
    res = await sb.table("player_birds").select("*").eq("user_id", str(user_id)).ilike("common_name", common_name).limit(1).execute()
    if not res.data:
        return None
    bird = res.data[0]
    await sb.table("player_birds").delete().eq("id", bird["id"]).execute()
    return bird


async def update_bird_group(bird_id, group_name):
    """Set group_name on a bird row by its DB id."""
    sb = await _client()
    await sb.table("player_birds").update({"group_name": group_name}).eq("id", bird_id).execute()


async def clear_group_birds(user_id, group_name):
    """Set group_name=NULL for all birds matching user_id + group_name. Returns count cleared."""
    sb = await _client()
    res = await sb.table("player_birds").select("id").eq("user_id", str(user_id)).eq("group_name", group_name).execute()
    count = len(res.data or [])
    if count:
        await sb.table("player_birds").update({"group_name": None}).eq("user_id", str(user_id)).eq("group_name", group_name).execute()
    return count


async def get_all_birds():
    """Get all birds across all players."""
    sb = await _client()
    res = await sb.table("player_birds").select("*").limit(10000).execute()
    return res.data or []


def get_all_birds_sync():
    sb = _sync_client()
    res = sb.table("player_birds").select("*").limit(10000).execute()
    return res.data or []


# ---------------------------------------------------------------------------
# Bird Treasures (decorations on birds)
# ---------------------------------------------------------------------------

async def get_bird_treasures(bird_id):
    sb = await _client()
    res = await sb.table("bird_treasures").select("*").eq("bird_id", bird_id).execute()
    return res.data or []


def get_bird_treasures_for_birds_sync(bird_ids):
    """Bulk-fetch bird treasures for multiple birds. Returns dict of bird_id -> list of rows."""
    if not bird_ids:
        return {}
    sb = _sync_client()
    res = sb.table("bird_treasures").select("*").in_("bird_id", bird_ids).execute()
    grouped = {}
    for row in (res.data or []):
        grouped.setdefault(row["bird_id"], []).append(row)
    return grouped


async def add_bird_treasure(bird_id, treasure_id, x=0, y=0, rotation=0, z_index=0):
    sb = await _client()
    await sb.table("bird_treasures").insert({
        "bird_id": bird_id,
        "treasure_id": treasure_id,
        "x": x,
        "y": y,
        "rotation": rotation,
        "z_index": z_index,
    }).execute()


async def remove_bird_treasures(bird_id):
    """Remove all treasures from a bird. Returns the treasure_ids removed."""
    sb = await _client()
    res = await sb.table("bird_treasures").select("treasure_id").eq("bird_id", bird_id).execute()
    ids = [r["treasure_id"] for r in (res.data or [])]
    if ids:
        await sb.table("bird_treasures").delete().eq("bird_id", bird_id).execute()
    return ids


# ---------------------------------------------------------------------------
# Player Plants
# ---------------------------------------------------------------------------

async def get_player_plants(user_id):
    sb = await _client()
    res = await sb.table("player_plants").select("*").eq("user_id", str(user_id)).execute()
    return res.data or []


def get_player_plants_sync(user_id):
    sb = _sync_client()
    res = sb.table("player_plants").select("*").eq("user_id", str(user_id)).execute()
    return res.data or []


async def add_plant(user_id, common_name, scientific_name, planted_date=None):
    sb = await _client()
    await sb.table("player_plants").insert({
        "user_id": str(user_id),
        "common_name": common_name,
        "scientific_name": scientific_name,
        "planted_date": planted_date,
    }).execute()


async def remove_plant_by_name(user_id, common_name):
    """Remove the first plant matching common_name. Returns the removed plant or None."""
    sb = await _client()
    res = await sb.table("player_plants").select("*").eq("user_id", str(user_id)).ilike("common_name", common_name).limit(1).execute()
    if not res.data:
        return None
    plant = res.data[0]
    await sb.table("player_plants").delete().eq("id", plant["id"]).execute()
    return plant


async def update_plant_group(plant_id, group_name):
    """Set group_name on a plant row by its DB id."""
    sb = await _client()
    await sb.table("player_plants").update({"group_name": group_name}).eq("id", plant_id).execute()


async def clear_group_plants(user_id, group_name):
    """Set group_name=NULL for all plants matching user_id + group_name. Returns count cleared."""
    sb = await _client()
    res = await sb.table("player_plants").select("id").eq("user_id", str(user_id)).eq("group_name", group_name).execute()
    count = len(res.data or [])
    if count:
        await sb.table("player_plants").update({"group_name": None}).eq("user_id", str(user_id)).eq("group_name", group_name).execute()
    return count


async def get_all_plants():
    """Get all plants across all players."""
    sb = await _client()
    res = await sb.table("player_plants").select("*").limit(10000).execute()
    return res.data or []


def get_all_plants_sync():
    sb = _sync_client()
    res = sb.table("player_plants").select("*").limit(10000).execute()
    return res.data or []


# ---------------------------------------------------------------------------
# Plant Treasures
# ---------------------------------------------------------------------------

async def get_plant_treasures(plant_id):
    sb = await _client()
    res = await sb.table("plant_treasures").select("*").eq("plant_id", plant_id).execute()
    return res.data or []


async def add_plant_treasure(plant_id, treasure_id, x=0, y=0, rotation=0, z_index=0):
    sb = await _client()
    await sb.table("plant_treasures").insert({
        "plant_id": plant_id,
        "treasure_id": treasure_id,
        "x": x,
        "y": y,
        "rotation": rotation,
        "z_index": z_index,
    }).execute()


async def remove_plant_treasures(plant_id):
    """Remove all treasures from a plant. Returns the treasure_ids removed."""
    sb = await _client()
    res = await sb.table("plant_treasures").select("treasure_id").eq("plant_id", plant_id).execute()
    ids = [r["treasure_id"] for r in (res.data or [])]
    if ids:
        await sb.table("plant_treasures").delete().eq("plant_id", plant_id).execute()
    return ids


# ---------------------------------------------------------------------------
# Player Treasures (inventory)
# ---------------------------------------------------------------------------

async def get_player_treasures(user_id):
    sb = await _client()
    res = await sb.table("player_treasures").select("*").eq("user_id", str(user_id)).execute()
    return res.data or []


async def add_player_treasure(user_id, treasure_id):
    sb = await _client()
    await sb.table("player_treasures").insert({
        "user_id": str(user_id),
        "treasure_id": treasure_id,
    }).execute()


async def remove_player_treasure(user_id, treasure_id):
    """Remove one instance of a treasure from inventory. Returns True if removed."""
    sb = await _client()
    res = await sb.table("player_treasures").select("id").eq("user_id", str(user_id)).eq("treasure_id", treasure_id).limit(1).execute()
    if not res.data:
        return False
    await sb.table("player_treasures").delete().eq("id", res.data[0]["id"]).execute()
    return True


# ---------------------------------------------------------------------------
# Nest Treasures (decorations on nest)
# ---------------------------------------------------------------------------

async def get_nest_treasures(user_id):
    sb = await _client()
    res = await sb.table("nest_treasures").select("*").eq("user_id", str(user_id)).execute()
    return res.data or []


def get_nest_treasures_sync(user_id):
    sb = _sync_client()
    res = sb.table("nest_treasures").select("*").eq("user_id", str(user_id)).execute()
    return res.data or []


async def add_nest_treasure(user_id, treasure_id, x=0, y=0, rotation=0, z_index=0):
    sb = await _client()
    await sb.table("nest_treasures").insert({
        "user_id": str(user_id),
        "treasure_id": treasure_id,
        "x": x,
        "y": y,
        "rotation": rotation,
        "z_index": z_index,
    }).execute()


async def remove_nest_treasures(user_id):
    """Remove all nest treasures. Returns the treasure_ids removed."""
    sb = await _client()
    res = await sb.table("nest_treasures").select("treasure_id").eq("user_id", str(user_id)).execute()
    ids = [r["treasure_id"] for r in (res.data or [])]
    if ids:
        await sb.table("nest_treasures").delete().eq("user_id", str(user_id)).execute()
    return ids


# ---------------------------------------------------------------------------
# Decorator sync helpers (for visual decorator web page)
# ---------------------------------------------------------------------------

def get_bird_treasures_sync(bird_id):
    """Fetch treasures for a single bird (sync)."""
    sb = _sync_client()
    res = sb.table("bird_treasures").select("*").eq("bird_id", bird_id).execute()
    return res.data or []


def get_plant_treasures_sync(plant_id):
    """Fetch treasures for a single plant (sync)."""
    sb = _sync_client()
    res = sb.table("plant_treasures").select("*").eq("plant_id", plant_id).execute()
    return res.data or []


def get_player_treasures_sync(user_id):
    """Get unplaced treasure inventory (sync)."""
    sb = _sync_client()
    res = sb.table("player_treasures").select("*").eq("user_id", str(user_id)).execute()
    return res.data or []


def add_player_treasure_sync(user_id, treasure_id):
    """Add a treasure to player inventory (sync)."""
    sb = _sync_client()
    sb.table("player_treasures").insert({
        "user_id": str(user_id),
        "treasure_id": treasure_id,
    }).execute()


def remove_player_treasure_sync(user_id, treasure_id):
    """Remove one instance of a treasure from inventory (sync). Returns True if removed."""
    sb = _sync_client()
    res = sb.table("player_treasures").select("id").eq("user_id", str(user_id)).eq("treasure_id", treasure_id).limit(1).execute()
    if not res.data:
        return False
    sb.table("player_treasures").delete().eq("id", res.data[0]["id"]).execute()
    return True


def save_bird_decorations_sync(bird_id, decorations):
    """Replace all bird decorations. decorations = [{treasure_id, x, y, rotation, z_index}, ...]"""
    sb = _sync_client()
    sb.table("bird_treasures").delete().eq("bird_id", bird_id).execute()
    if decorations:
        rows = [{"bird_id": bird_id, **d} for d in decorations]
        sb.table("bird_treasures").insert(rows).execute()


def save_plant_decorations_sync(plant_id, decorations):
    """Replace all plant decorations."""
    sb = _sync_client()
    sb.table("plant_treasures").delete().eq("plant_id", plant_id).execute()
    if decorations:
        rows = [{"plant_id": plant_id, **d} for d in decorations]
        sb.table("plant_treasures").insert(rows).execute()


def save_nest_decorations_sync(user_id, decorations):
    """Replace all nest decorations."""
    sb = _sync_client()
    sb.table("nest_treasures").delete().eq("user_id", str(user_id)).execute()
    if decorations:
        rows = [{"user_id": str(user_id), **d} for d in decorations]
        sb.table("nest_treasures").insert(rows).execute()


def verify_entity_ownership_sync(user_id, entity_type, entity_id):
    """Returns True if user_id owns the entity."""
    sb = _sync_client()
    if entity_type == "nest":
        return str(entity_id) == str(user_id)
    elif entity_type == "bird":
        res = sb.table("player_birds").select("user_id").eq("id", entity_id).execute()
        return bool(res.data) and str(res.data[0]["user_id"]) == str(user_id)
    elif entity_type == "plant":
        res = sb.table("player_plants").select("user_id").eq("id", entity_id).execute()
        return bool(res.data) and str(res.data[0]["user_id"]) == str(user_id)
    return False


# ---------------------------------------------------------------------------
# Eggs
# ---------------------------------------------------------------------------

async def get_egg(user_id):
    sb = await _client()
    res = await sb.table("eggs").select("*").eq("user_id", str(user_id)).execute()
    if not res.data:
        return None
    egg = res.data[0]
    # Also load multipliers and brooders
    mults = await sb.table("egg_multipliers").select("*").eq("egg_user_id", str(user_id)).execute()
    brooders = await sb.table("egg_brooders").select("brooder_user_id").eq("egg_user_id", str(user_id)).execute()
    egg["multipliers"] = {m["scientific_name"]: m["multiplier"] for m in (mults.data or [])}
    egg["brooded_by"] = [b["brooder_user_id"] for b in (brooders.data or [])]
    return egg


async def get_eggs_for_users(user_ids, include_details=False):
    """Batch fetch eggs for a list of users.

    Returns a dict keyed by user_id. If include_details=True, includes the same
    multipliers/brooders fields as get_egg().
    """
    normalized_ids = [str(uid) for uid in user_ids]
    if not normalized_ids:
        return {}

    sb = await _client()
    egg_select = "*" if include_details else "user_id,brooding_progress,protected_prayers"
    eggs_res = await sb.table("eggs").select(egg_select).in_("user_id", normalized_ids).execute()
    eggs = eggs_res.data or []
    eggs_by_user = {row["user_id"]: row for row in eggs}

    if not include_details or not eggs_by_user:
        return eggs_by_user

    mults_res = await sb.table("egg_multipliers").select("*").in_("egg_user_id", list(eggs_by_user.keys())).execute()
    brooders_res = await sb.table("egg_brooders").select("egg_user_id,brooder_user_id").in_("egg_user_id", list(eggs_by_user.keys())).execute()

    multipliers_by_user = {}
    for mult in (mults_res.data or []):
        egg_user_id = mult["egg_user_id"]
        if egg_user_id not in multipliers_by_user:
            multipliers_by_user[egg_user_id] = {}
        multipliers_by_user[egg_user_id][mult["scientific_name"]] = mult["multiplier"]

    brooders_by_user = {}
    for brooder in (brooders_res.data or []):
        egg_user_id = brooder["egg_user_id"]
        if egg_user_id not in brooders_by_user:
            brooders_by_user[egg_user_id] = []
        brooders_by_user[egg_user_id].append(brooder["brooder_user_id"])

    for egg_user_id, egg in eggs_by_user.items():
        egg["multipliers"] = multipliers_by_user.get(egg_user_id, {})
        egg["brooded_by"] = brooders_by_user.get(egg_user_id, [])

    return eggs_by_user


async def create_egg(user_id, brooding_progress=0, protected_prayers=False):
    sb = await _client()
    await sb.table("eggs").upsert({
        "user_id": str(user_id),
        "brooding_progress": brooding_progress,
        "protected_prayers": protected_prayers,
    }).execute()


async def update_egg(user_id, **fields):
    sb = await _client()
    await sb.table("eggs").update(fields).eq("user_id", str(user_id)).execute()


async def delete_egg(user_id):
    """Delete an egg and its related multipliers/brooders (cascade)."""
    sb = await _client()
    await sb.table("eggs").delete().eq("user_id", str(user_id)).execute()


def get_egg_progress_sync(user_id):
    """Return the brooding_progress for a user's egg, or None if no egg."""
    sb = _sync_client()
    res = sb.table("eggs").select("brooding_progress").eq("user_id", str(user_id)).execute()
    if not res.data:
        return None
    return res.data[0]["brooding_progress"]


async def upsert_egg_multiplier(user_id, scientific_name, multiplier):
    sb = await _client()
    await sb.table("egg_multipliers").upsert({
        "egg_user_id": str(user_id),
        "scientific_name": scientific_name,
        "multiplier": multiplier,
    }, on_conflict="egg_user_id,scientific_name").execute()


async def add_egg_brooder(user_id, brooder_user_id):
    sb = await _client()
    await sb.table("egg_brooders").upsert({
        "egg_user_id": str(user_id),
        "brooder_user_id": str(brooder_user_id),
    }, on_conflict="egg_user_id,brooder_user_id").execute()


# ---------------------------------------------------------------------------
# Daily Actions
# ---------------------------------------------------------------------------

async def get_daily_actions(user_id, action_date):
    sb = await _client()
    res = await sb.table("daily_actions").select("*").eq("user_id", str(user_id)).eq("action_date", action_date).execute()
    if res.data:
        return res.data[0]
    return None


async def upsert_daily_actions(user_id, action_date, used, action_history):
    sb = await _client()
    await sb.table("daily_actions").upsert({
        "user_id": str(user_id),
        "action_date": action_date,
        "used": used,
        "action_history": action_history,
    }, on_conflict="user_id,action_date").execute()


async def delete_old_daily_actions(cutoff_date):
    """Delete daily actions older than cutoff_date."""
    sb = await _client()
    await sb.table("daily_actions").delete().lt("action_date", cutoff_date).execute()


def delete_old_daily_actions_sync(cutoff_date):
    sb = _sync_client()
    sb.table("daily_actions").delete().lt("action_date", cutoff_date).execute()


def get_all_daily_actions_sync(since_date=None):
    """Get all daily actions, optionally filtered to on or after since_date."""
    sb = _sync_client()
    query = sb.table("daily_actions").select("*")
    if since_date:
        query = query.gte("action_date", since_date)
    res = query.order("action_date", desc=True).limit(10000).execute()
    return res.data or []


def get_all_birdwatch_sightings_unpaginated_sync():
    sb = _sync_client()
    res = sb.table("birdwatch_sightings").select("user_id, created_at").limit(10000).execute()
    return res.data or []


# ---------------------------------------------------------------------------
# Daily Songs
# ---------------------------------------------------------------------------

async def record_song(singer_user_id, target_user_id, song_date, points_given=3):
    sb = await _client()
    await sb.table("daily_songs").upsert({
        "song_date": song_date,
        "singer_user_id": str(singer_user_id),
        "target_user_id": str(target_user_id),
        "points_given": points_given,
    }, on_conflict="song_date,singer_user_id,target_user_id").execute()


async def record_songs_batch(singer_user_id, target_user_ids, song_date, points_given=3):
    """Record multiple songs at once."""
    sb = await _client()
    rows = [{"song_date": song_date, "singer_user_id": str(singer_user_id),
             "target_user_id": str(tid), "points_given": points_given} for tid in target_user_ids]
    await sb.table("daily_songs").upsert(rows,
        on_conflict="song_date,singer_user_id,target_user_id").execute()


async def get_sung_to_targets_today(singer_user_id, target_user_ids, song_date):
    """Return set of target_user_ids the singer has already sung to today."""
    sb = await _client()
    res = await sb.table("daily_songs").select("target_user_id") \
        .eq("song_date", song_date) \
        .eq("singer_user_id", str(singer_user_id)) \
        .in_("target_user_id", [str(t) for t in target_user_ids]) \
        .execute()
    return {r["target_user_id"] for r in (res.data or [])}


async def has_been_sung_to_by(singer_user_id, target_user_id, song_date):
    sb = await _client()
    res = await sb.table("daily_songs").select("id").eq("song_date", song_date).eq("singer_user_id", str(singer_user_id)).eq("target_user_id", str(target_user_id)).execute()
    return len(res.data or []) > 0


async def has_been_sung_to(target_user_id, song_date):
    sb = await _client()
    res = await sb.table("daily_songs").select("id").eq("song_date", song_date).eq("target_user_id", str(target_user_id)).limit(1).execute()
    return len(res.data or []) > 0


async def get_singers_today(target_user_id, song_date):
    sb = await _client()
    res = await sb.table("daily_songs").select("singer_user_id").eq("song_date", song_date).eq("target_user_id", str(target_user_id)).execute()
    return [r["singer_user_id"] for r in (res.data or [])]


async def get_all_songs_for_date(song_date):
    sb = await _client()
    res = await sb.table("daily_songs").select("*").eq("song_date", song_date).execute()
    return res.data or []


def get_all_songs_sync(since_date=None):
    """Get all songs, optionally filtered to on or after since_date."""
    sb = _sync_client()
    query = sb.table("daily_songs").select("*")
    if since_date:
        query = query.gte("song_date", since_date)
    res = query.order("song_date", desc=True).limit(10000).execute()
    return res.data or []


async def delete_old_songs(cutoff_date):
    sb = await _client()
    await sb.table("daily_songs").delete().lt("song_date", cutoff_date).execute()


def delete_old_songs_sync(cutoff_date):
    sb = _sync_client()
    sb.table("daily_songs").delete().lt("song_date", cutoff_date).execute()


# ---------------------------------------------------------------------------
# Daily Brooding
# ---------------------------------------------------------------------------

async def record_brooding(brooder_user_id, target_user_id, brooding_date):
    sb = await _client()
    await sb.table("daily_brooding").upsert({
        "brooding_date": brooding_date,
        "brooder_user_id": str(brooder_user_id),
        "target_user_id": str(target_user_id),
    }, on_conflict="brooding_date,brooder_user_id,target_user_id").execute()


async def get_brooded_targets_today(brooder_user_id, brooding_date, target_user_ids=None):
    """Return a set of target_user_id values brooded by this user on this date."""
    sb = await _client()
    query = sb.table("daily_brooding").select("target_user_id") \
        .eq("brooding_date", brooding_date) \
        .eq("brooder_user_id", str(brooder_user_id))

    if target_user_ids is not None:
        normalized_ids = [str(uid) for uid in target_user_ids]
        if not normalized_ids:
            return set()
        query = query.in_("target_user_id", normalized_ids)

    res = await query.execute()
    return {r["target_user_id"] for r in (res.data or [])}


async def has_brooded_today(brooder_user_id, target_user_id, brooding_date):
    sb = await _client()
    res = await sb.table("daily_brooding").select("id").eq("brooding_date", brooding_date).eq("brooder_user_id", str(brooder_user_id)).eq("target_user_id", str(target_user_id)).execute()
    return len(res.data or []) > 0


async def delete_old_brooding(cutoff_date):
    sb = await _client()
    await sb.table("daily_brooding").delete().lt("brooding_date", cutoff_date).execute()


def delete_old_brooding_sync(cutoff_date):
    sb = _sync_client()
    sb.table("daily_brooding").delete().lt("brooding_date", cutoff_date).execute()


# ---------------------------------------------------------------------------
# Last Song Targets
# ---------------------------------------------------------------------------

async def get_last_song_targets(user_id):
    sb = await _client()
    res = await sb.table("last_song_targets").select("target_user_id").eq("user_id", str(user_id)).order("sort_order").execute()
    return [r["target_user_id"] for r in (res.data or [])]


async def set_last_song_targets(user_id, target_user_ids):
    """Replace the last song targets for a user."""
    user_id = str(user_id)
    sb = await _client()
    # Delete existing
    await sb.table("last_song_targets").delete().eq("user_id", user_id).execute()
    # Insert new
    if target_user_ids:
        rows = [{"user_id": user_id, "target_user_id": str(tid), "sort_order": i}
                for i, tid in enumerate(target_user_ids)]
        await sb.table("last_song_targets").insert(rows).execute()


# ---------------------------------------------------------------------------
# Released Birds
# ---------------------------------------------------------------------------

async def get_released_birds():
    sb = await _client()
    res = await sb.table("released_birds").select("*").limit(10000).execute()
    return res.data or []


def get_released_birds_sync():
    sb = _sync_client()
    res = sb.table("released_birds").select("*").limit(10000).execute()
    return res.data or []


async def upsert_released_bird(common_name, scientific_name):
    """Atomically increment count for a released bird, or insert with count=1."""
    sb = await _client()
    await sb.rpc("upsert_released_bird_atomic", {
        "p_common_name": common_name,
        "p_scientific_name": scientific_name,
    }).execute()


# ---------------------------------------------------------------------------
# Defeated Humans
# ---------------------------------------------------------------------------

async def add_defeated_human(name, max_resilience, defeat_date, blessing_name, blessing_amount):
    sb = await _client()
    await sb.table("defeated_humans").insert({
        "name": name,
        "max_resilience": max_resilience,
        "defeat_date": defeat_date,
        "blessing_name": blessing_name,
        "blessing_amount": blessing_amount,
    }).execute()


async def get_defeated_humans(limit=5):
    sb = await _client()
    res = await sb.table("defeated_humans").select("*").order("defeat_date", desc=True).limit(limit).execute()
    return res.data or []


def get_defeated_humans_sync(limit=None):
    sb = _sync_client()
    query = sb.table("defeated_humans").select("*").order("defeat_date", desc=True)
    if limit is not None:
        query = query.limit(limit)
    return query.execute().data or []


# ---------------------------------------------------------------------------
# Memoirs (lore)
# ---------------------------------------------------------------------------

async def add_memoir(user_id, nest_name, text, memoir_date):
    sb = await _client()
    await sb.table("memoirs").insert({
        "user_id": str(user_id),
        "nest_name": nest_name,
        "text": text,
        "memoir_date": memoir_date,
    }).execute()


async def get_player_memoirs(user_id):
    sb = await _client()
    res = await sb.table("memoirs").select("*").eq("user_id", str(user_id)).order("memoir_date", desc=True).execute()
    return res.data or []


async def load_memoirs():
    sb = await _client()
    res = await sb.table("memoirs").select("*").order("memoir_date", desc=True).execute()
    return res.data or []


def load_memoirs_sync():
    sb = _sync_client()
    res = sb.table("memoirs").select("*").order("memoir_date", desc=True).limit(10000).execute()
    return res.data or []


# ---------------------------------------------------------------------------
# Realm Messages (realm lore)
# ---------------------------------------------------------------------------

async def load_realm_messages():
    sb = await _client()
    res = await sb.table("realm_messages").select("*").order("message_date", desc=True).execute()
    return res.data or []


def load_realm_messages_sync():
    sb = _sync_client()
    res = sb.table("realm_messages").select("*").order("message_date", desc=True).execute()
    return res.data or []


# ---------------------------------------------------------------------------
# Manifested Birds
# ---------------------------------------------------------------------------

async def load_manifested_birds():
    sb = await _client()
    res = await sb.table("manifested_birds").select("*").execute()
    return res.data or []


def load_manifested_birds_sync():
    sb = _sync_client()
    res = sb.table("manifested_birds").select("*").execute()
    return res.data or []


async def upsert_manifested_bird(bird_data):
    """Upsert a manifested bird by scientific_name."""
    sb = await _client()
    await sb.table("manifested_birds").upsert(bird_data, on_conflict="scientific_name").execute()


async def get_manifested_bird(scientific_name):
    sb = await _client()
    res = await sb.table("manifested_birds").select("*").eq("scientific_name", scientific_name).execute()
    return res.data[0] if res.data else None


# ---------------------------------------------------------------------------
# Manifested Plants
# ---------------------------------------------------------------------------

async def load_manifested_plants():
    sb = await _client()
    res = await sb.table("manifested_plants").select("*").execute()
    return res.data or []


def load_manifested_plants_sync():
    sb = _sync_client()
    res = sb.table("manifested_plants").select("*").execute()
    return res.data or []


async def upsert_manifested_plant(plant_data):
    """Upsert a manifested plant by scientific_name."""
    sb = await _client()
    await sb.table("manifested_plants").upsert(plant_data, on_conflict="scientific_name").execute()


async def get_manifested_plant(scientific_name):
    sb = await _client()
    res = await sb.table("manifested_plants").select("*").eq("scientific_name", scientific_name).execute()
    return res.data[0] if res.data else None


# ---------------------------------------------------------------------------
# Research Progress
# ---------------------------------------------------------------------------

async def load_research_progress():
    sb = await _client()
    res = await sb.table("research_progress").select("*").execute()
    return {r["author_name"]: r["points"] for r in (res.data or {})}


def load_research_progress_sync():
    sb = _sync_client()
    res = sb.table("research_progress").select("*").execute()
    return {r["author_name"]: r["points"] for r in (res.data or {})}


async def increment_research(author_name, points):
    """Atomically upsert research progress, incrementing points."""
    sb = await _client()
    await sb.rpc("increment_research_progress", {
        "p_author_name": author_name,
        "p_points": points,
    }).execute()


# ---------------------------------------------------------------------------
# Exploration (simple key-value, stored in a table)
# ---------------------------------------------------------------------------

async def get_exploration_data():
    sb = await _client()
    res = await sb.table("exploration").select("*").execute()
    return {r["region"]: r["points"] for r in (res.data or [])}


def get_exploration_data_sync():
    sb = _sync_client()
    res = sb.table("exploration").select("*").execute()
    return {r["region"]: r["points"] for r in (res.data or [])}


async def increment_exploration(region, amount):
    """Atomically increment exploration points. Returns new total."""
    sb = await _client()
    res = await sb.rpc("increment_exploration_points", {
        "p_region": region,
        "p_amount": amount,
    }).execute()
    # RPC returns the new total as a scalar
    return res.data


# ---------------------------------------------------------------------------
# Weather Channels
# ---------------------------------------------------------------------------

async def get_weather_channels():
    sb = await _client()
    res = await sb.table("weather_channels").select("*").execute()
    return {r["guild_id"]: r["channel_id"] for r in (res.data or [])}


async def set_weather_channel(guild_id, channel_id):
    sb = await _client()
    await sb.table("weather_channels").upsert({
        "guild_id": str(guild_id),
        "channel_id": str(channel_id),
    }, on_conflict="guild_id").execute()


async def remove_weather_channel(guild_id):
    sb = await _client()
    await sb.table("weather_channels").delete().eq("guild_id", str(guild_id)).execute()


# ---------------------------------------------------------------------------
# Bulk-fetch functions (for homepage performance)
# ---------------------------------------------------------------------------

def get_all_eggs_sync():
    """Fetch all eggs in one query. Returns dict keyed by user_id."""
    sb = _sync_client()
    res = sb.table("eggs").select("user_id, brooding_progress").limit(10000).execute()
    return {row["user_id"]: row["brooding_progress"] for row in (res.data or [])}


def get_all_player_birds_sync():
    """Fetch all player birds. Returns dict of user_id -> list of birds."""
    sb = _sync_client()
    res = sb.table("player_birds").select("*").limit(10000).execute()
    grouped = {}
    for row in (res.data or []):
        grouped.setdefault(str(row["user_id"]), []).append(row)
    return grouped


def get_all_player_plants_sync():
    """Fetch all player plants. Returns dict of user_id -> list of plants."""
    sb = _sync_client()
    res = sb.table("player_plants").select("*").limit(10000).execute()
    grouped = {}
    for row in (res.data or []):
        grouped.setdefault(str(row["user_id"]), []).append(row)
    return grouped


def get_all_nest_treasures_sync():
    """Fetch all nest treasures. Returns dict of user_id -> list of decorations."""
    sb = _sync_client()
    res = sb.table("nest_treasures").select("*").limit(10000).execute()
    grouped = {}
    for row in (res.data or []):
        grouped.setdefault(str(row["user_id"]), []).append(row)
    return grouped


# ---------------------------------------------------------------------------
# Game Settings (event system)
# ---------------------------------------------------------------------------

async def get_active_event():
    """Get the currently active event name from game_settings. Returns 'default' if not set."""
    sb = await _client()
    res = await sb.table("game_settings").select("value").eq("key", "active_event").execute()
    if res.data:
        return res.data[0]["value"]
    return "default"


def get_active_event_sync():
    """Sync variant: get the currently active event name."""
    sb = _sync_client()
    res = sb.table("game_settings").select("value").eq("key", "active_event").execute()
    if res.data:
        return res.data[0]["value"]
    return "default"


async def set_active_event(event_name):
    """Set the active event in game_settings (upsert)."""
    sb = await _client()
    await sb.table("game_settings").upsert({
        "key": "active_event",
        "value": event_name,
    }, on_conflict="key").execute()


# ---------------------------------------------------------------------------
# Weather Location
# ---------------------------------------------------------------------------

_DEFAULT_WEATHER_LOCATION = {
    "latitude": -37.8142,
    "longitude": 144.9632,
    "timezone": "Australia/Sydney",
    "name": "Naarm",
}


async def get_weather_location():
    """Get the weather location from game_settings. Returns Melbourne defaults if not set."""
    sb = await _client()
    res = await sb.table("game_settings").select("value").eq("key", "weather_location").execute()
    if res.data:
        try:
            return json.loads(res.data[0]["value"])
        except (json.JSONDecodeError, KeyError):
            pass
    return dict(_DEFAULT_WEATHER_LOCATION)


def get_weather_location_sync():
    """Sync variant: get the weather location."""
    sb = _sync_client()
    res = sb.table("game_settings").select("value").eq("key", "weather_location").execute()
    if res.data:
        try:
            return json.loads(res.data[0]["value"])
        except (json.JSONDecodeError, KeyError):
            pass
    return dict(_DEFAULT_WEATHER_LOCATION)


async def set_weather_location(latitude, longitude, timezone, name):
    """Set the weather location in game_settings (upsert)."""
    sb = await _client()
    value = json.dumps({"latitude": latitude, "longitude": longitude, "timezone": timezone, "name": name})
    await sb.table("game_settings").upsert({
        "key": "weather_location",
        "value": value,
    }, on_conflict="key").execute()


# ---------------------------------------------------------------------------
# Birdwatch Sightings
# ---------------------------------------------------------------------------

BIRDWATCH_BUCKET = "birdwatch-images"


def _compress_image(file_data: bytes) -> bytes:
    """Resize and compress an image to JPEG. Runs in a thread (CPU-bound)."""
    from PIL import Image
    img = Image.open(io.BytesIO(file_data))
    img = img.convert("RGB")  # Ensure JPEG-compatible (no alpha)

    # Resize if longest side exceeds max dimension
    max_dim = max(img.size)
    if max_dim > BIRDWATCH_MAX_DIMENSION:
        ratio = BIRDWATCH_MAX_DIMENSION / max_dim
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=BIRDWATCH_JPEG_QUALITY, optimize=True)
    buf.seek(0)
    return buf.getvalue()


async def compress_image(file_data: bytes) -> bytes:
    """Async wrapper for image compression (runs in thread pool)."""
    return await asyncio.to_thread(_compress_image, file_data)


def _upload_to_storage(storage_path: str, file_data: bytes):
    """Upload bytes to Supabase Storage using the sync client. Runs in a thread."""
    sb = _sync_client()
    sb.storage.from_(BIRDWATCH_BUCKET).upload(
        path=storage_path,
        file=file_data,
        file_options={"content-type": "image/jpeg", "upsert": "false"}
    )
    return sb.storage.from_(BIRDWATCH_BUCKET).get_public_url(storage_path)


async def upload_birdwatch_image(user_id: str, filename: str, file_data: bytes):
    """Compress and upload an image to Supabase Storage. Returns (storage_path, public_url, compressed_bytes)."""
    storage_path = f"{user_id}/{uuid.uuid4().hex}_{filename}"
    # Compress first
    compressed = await compress_image(file_data)
    # Upload via sync client in thread (async client may not expose .storage)
    public_url = await asyncio.to_thread(_upload_to_storage, storage_path, compressed)
    return storage_path, public_url, compressed


async def save_birdwatch_sighting(user_id: str, image_url: str, storage_path: str, original_filename: str, description: str = None):
    """Insert a birdwatch sighting record."""
    sb = await _client()
    row = {
        "user_id": str(user_id),
        "image_url": image_url,
        "storage_path": storage_path,
        "original_filename": original_filename,
    }
    if description:
        row["description"] = description
    await sb.table("birdwatch_sightings").insert(row).execute()


async def get_birdwatch_sightings(user_id: str, limit: int = 10):
    """Get recent birdwatch sightings for a user."""
    sb = await _client()
    res = await sb.table("birdwatch_sightings") \
        .select("*") \
        .eq("user_id", str(user_id)) \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()
    return res.data or []


def get_all_birdwatch_sightings_sync(page: int = 1, per_page: int = 12):
    """Get paginated birdwatch sightings with player usernames. Returns (sightings, total_count)."""
    sb = _sync_client()

    # Get total count
    count_res = sb.table("birdwatch_sightings").select("id", count="exact").execute()
    total_count = count_res.count or 0

    # Get paginated sightings with player username via join
    offset = (page - 1) * per_page
    res = sb.table("birdwatch_sightings") \
        .select("*, players(discord_username, nest_name)") \
        .order("created_at", desc=True) \
        .range(offset, offset + per_page - 1) \
        .execute()

    return res.data or [], total_count
