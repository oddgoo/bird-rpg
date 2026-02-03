"""
Game business logic.  All functions are now async and call storage.py DB operations
instead of mutating in-memory dicts.
"""

import json
import os
import random
import re
from utils.time_utils import get_current_date
from constants import BASE_DAILY_ACTIONS
from config.config import DEBUG

import data.storage as db


# ---------------------------------------------------------------------------
# Cached reference data loaders
# ---------------------------------------------------------------------------

_treasures_cache = None

def load_treasures():
    """Load treasures from JSON file with module-level cache (read-only data)."""
    global _treasures_cache
    if _treasures_cache is None:
        file_path = os.path.join(os.path.dirname(__file__), 'treasures.json')
        with open(file_path, 'r') as f:
            _treasures_cache = json.load(f)
    return _treasures_cache


# ---------------------------------------------------------------------------
# Player helpers
# ---------------------------------------------------------------------------

async def get_remaining_actions(user_id):
    """Calculate remaining actions for a user today."""
    user_id = str(user_id)
    today = get_current_date()

    player = await db.load_player(user_id)
    birds = await db.get_player_birds(user_id)
    actions = await db.get_daily_actions(user_id, today)

    used = actions["used"] if actions else 0
    chick_count = len(birds)
    bonus = max(0, player.get("bonus_actions", 0))
    total_available = BASE_DAILY_ACTIONS + bonus + chick_count
    return total_available - used


async def record_actions(user_id, count, action_type=None):
    """Record actions used by a user. Consumes bonus actions first."""
    user_id = str(user_id)
    today = get_current_date()

    player = await db.load_player(user_id)
    actions = await db.get_daily_actions(user_id, today)

    current_used = actions["used"] if actions else 0
    current_history = list(actions["action_history"]) if actions else []

    bonus_to_use = 0
    if player.get("bonus_actions", 0) > 0:
        bonus_to_use = min(count, player["bonus_actions"])
        await db.increment_player_field(user_id, "bonus_actions", -bonus_to_use)
        count -= bonus_to_use

    new_used = current_used + count
    if action_type:
        total = count + bonus_to_use
        current_history.extend([action_type] * total)

    await db.upsert_daily_actions(user_id, today, new_used, current_history)


async def is_first_action_of_type(user_id, action_type):
    """Check if this is the first action of a specific type today."""
    user_id = str(user_id)
    today = get_current_date()
    actions = await db.get_daily_actions(user_id, today)
    if not actions:
        return True
    return action_type not in (actions.get("action_history") or [])


async def add_bonus_actions(user_id, amount):
    await db.increment_player_field(str(user_id), "bonus_actions", amount)


# ---------------------------------------------------------------------------
# Egg helpers
# ---------------------------------------------------------------------------

def get_egg_cost(nest_or_player):
    """Calculate the cost of laying an egg."""
    return 20


EGG_BLESS_INSPIRATION_COST = 1
EGG_BLESS_SEED_COST = 30


async def can_bless_egg(user_id):
    player = await db.load_player(user_id)
    egg = await db.get_egg(user_id)

    if egg is None:
        return False, "You don't have an egg to bless! 🥚"

    if player["inspiration"] < EGG_BLESS_INSPIRATION_COST or player["seeds"] < EGG_BLESS_SEED_COST:
        return False, (
            f"You need {EGG_BLESS_INSPIRATION_COST} inspiration and {EGG_BLESS_SEED_COST} seeds to bless your egg! "
            f"You have {player['inspiration']} inspiration and {player['seeds']} seeds. ✨🌰"
        )

    if egg.get("protected_prayers", False):
        return False, "Your egg is already blessed! 🛡️✨"

    return True, None


async def bless_egg(user_id):
    can_do_it, error = await can_bless_egg(user_id)
    if not can_do_it:
        return False, error

    await db.increment_player_field(user_id, "inspiration", -EGG_BLESS_INSPIRATION_COST)
    await db.increment_player_field(user_id, "seeds", -EGG_BLESS_SEED_COST)
    await db.update_egg(user_id, protected_prayers=True)
    return True, (
        "Your egg has been blessed! ✨ If a bird other than your most-prayed one hatches, "
        "your prayers will be preserved and a new egg will be created! 🥚🛡️"
    )


def handle_blessed_egg_hatching(egg, hatched_bird_name):
    """Returns the multipliers to preserve, or None."""
    if not egg.get("protected_prayers", False):
        return None

    multipliers = egg.get("multipliers", {})
    if not multipliers:
        return None

    max_prayers = 0
    most_prayed_birds = []
    for bird, prayers in multipliers.items():
        if prayers > max_prayers:
            max_prayers = prayers
            most_prayed_birds = [bird]
        elif prayers == max_prayers:
            most_prayed_birds.append(bird)

    if hatched_bird_name not in most_prayed_birds:
        return multipliers
    return None


# ---------------------------------------------------------------------------
# Bird species loading (local JSON + manifested from DB)
# ---------------------------------------------------------------------------

def _load_bird_species_json():
    file_path = os.path.join(os.path.dirname(__file__), 'bird_species.json')
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data["bird_species"]


async def load_bird_species(include_manifested=True):
    base = _load_bird_species_json()
    if not include_manifested:
        return base
    manifested = await db.load_manifested_birds()
    fully = [b for b in manifested if b.get("fully_manifested", False)]
    # Normalize manifested keys to match base species format
    for b in fully:
        b.setdefault("commonName", b.get("common_name", ""))
        b.setdefault("scientificName", b.get("scientific_name", ""))
        b.setdefault("rarityWeight", b.get("rarity_weight", 0))
    return base + fully


def load_bird_species_sync(include_manifested=True):
    base = _load_bird_species_json()
    if not include_manifested:
        return base
    manifested = db.load_manifested_birds_sync()
    fully = [b for b in manifested if b.get("fully_manifested", False)]
    for b in fully:
        b.setdefault("commonName", b.get("common_name", ""))
        b.setdefault("scientificName", b.get("scientific_name", ""))
        b.setdefault("rarityWeight", b.get("rarity_weight", 0))
    return base + fully


async def get_bird_effect(scientific_name):
    all_birds = await load_bird_species()
    for b in all_birds:
        if b.get("scientificName") == scientific_name:
            return b.get("effect", "")
    return ""


def get_bird_effect_sync(scientific_name):
    all_birds = load_bird_species_sync()
    for b in all_birds:
        if b.get("scientificName") == scientific_name:
            return b.get("effect", "")
    return ""


async def select_random_bird_species(multipliers=None):
    all_birds = await load_bird_species()
    if not all_birds:
        return None

    weights = []
    for species in all_birds:
        base_weight = species.get("rarityWeight", 1)
        if multipliers and species.get("scientificName") in multipliers:
            weights.append(base_weight * multipliers[species["scientificName"]])
        else:
            weights.append(base_weight)

    return random.choices(all_birds, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# Discovered species (computed from DB)
# ---------------------------------------------------------------------------

async def get_discovered_species():
    """Retrieve all unique bird species discovered by all players."""
    discovered = set()
    all_birds = await db.get_all_birds()
    for bird in all_birds:
        discovered.add((bird["common_name"], bird["scientific_name"]))
    released = await db.get_released_birds()
    for bird in released:
        discovered.add((bird["common_name"], bird["scientific_name"]))
    return discovered


def get_discovered_species_sync():
    discovered = set()
    all_birds = db.get_all_birds_sync()
    for bird in all_birds:
        discovered.add((bird["common_name"], bird["scientific_name"]))
    released = db.get_released_birds_sync()
    for bird in released:
        discovered.add((bird["common_name"], bird["scientific_name"]))
    return discovered


async def get_discovered_species_count():
    return len(await get_discovered_species())


def get_discovered_species_count_sync():
    return len(get_discovered_species_sync())


async def get_discovered_plants():
    discovered = set()
    all_plants = await db.get_all_plants()
    for plant in all_plants:
        discovered.add((plant["common_name"], plant["scientific_name"]))
    return discovered


def get_discovered_plants_sync():
    discovered = set()
    all_plants = db.get_all_plants_sync()
    for plant in all_plants:
        discovered.add((plant["common_name"], plant["scientific_name"]))
    return discovered


async def get_discovered_plant_species_count():
    return len(await get_discovered_plants())


def get_discovered_plant_species_count_sync():
    return len(get_discovered_plants_sync())


async def get_total_bird_species():
    all_birds = await load_bird_species()
    return len(all_birds)


def get_total_bird_species_sync():
    all_birds = load_bird_species_sync()
    return len(all_birds)


# ---------------------------------------------------------------------------
# Bird effect bonuses
# ---------------------------------------------------------------------------

async def get_nest_building_bonus(user_id, birds):
    """Calculate building bonus from birds that give first-build-of-day bonuses."""
    if not await is_first_action_of_type(user_id, "build"):
        return 0

    total_bonus = 0
    for bird in birds:
        effect = await get_bird_effect(bird["scientific_name"])
        if "Your first nest-building action of the day gives" in effect:
            bonus_amount = int(''.join(filter(str.isdigit, effect)))
            total_bonus += bonus_amount
    return total_bonus


async def get_singing_bonus(birds):
    """Calculate total singing bonus from birds with song-enhancing effects."""
    total_bonus = 0
    for bird in birds:
        effect = await get_bird_effect(bird["scientific_name"])
        if "All your songs give" in effect:
            bonus_amount = int(''.join(filter(str.isdigit, effect)))
            total_bonus += bonus_amount
    return total_bonus


async def get_singing_inspiration_chance(user_id, birds):
    """Calculate chance-based inspiration bonus from finches on first singing action."""
    if not await is_first_action_of_type(user_id, "sing"):
        return 0

    inspiration_chances = 0
    for bird in birds:
        effect = await get_bird_effect(bird["scientific_name"])
        if "has a 50% chance to give you +1 inspiration" in effect:
            if random.random() < 0.5:
                inspiration_chances += 1
        if "has a 90% chance to give you +1 inspiration" in effect:
            if random.random() < 0.9:
                inspiration_chances += 1
    return inspiration_chances


async def get_seed_gathering_bonus(user_id, birds):
    """Calculate garden size bonus from birds that give first-gather-of-day bonuses."""
    if not await is_first_action_of_type(user_id, "seed"):
        return 0

    total_bonus = 0
    for bird in birds:
        effect = await get_bird_effect(bird["scientific_name"])
        if "Your first seed gathering action of the day also gives" in effect:
            bonus_amount = int(''.join(filter(str.isdigit, effect)))
            total_bonus += bonus_amount
    return total_bonus


async def get_swooping_bonus(user_id, birds):
    """Get the bonus swooping damage from birds that boost swooping."""
    if not await is_first_action_of_type(user_id, "swoop"):
        return 0

    bonus = 0
    for bird in birds:
        effect = (await get_bird_effect(bird["scientific_name"])).lower()
        if "your first swoop" in effect and "more effective" in effect:
            try:
                this_bonus = int(''.join(filter(str.isdigit, effect)))
                bonus += this_bonus
            except ValueError:
                continue
    return bonus


# ---------------------------------------------------------------------------
# Plant species loading
# ---------------------------------------------------------------------------

def _load_plant_species_json():
    file_path = os.path.join(os.path.dirname(__file__), 'plant_species.json')
    with open(file_path, 'r') as f:
        return json.load(f)


async def load_plant_species(include_manifested=True):
    base = _load_plant_species_json()
    if not include_manifested:
        return base
    manifested = await db.load_manifested_plants()
    fully = [p for p in manifested if p.get("fully_manifested", False)]
    for p in fully:
        p.setdefault("commonName", p.get("common_name", ""))
        p.setdefault("scientificName", p.get("scientific_name", ""))
        p.setdefault("rarityWeight", p.get("rarity_weight", 0))
        p.setdefault("seedCost", p.get("seed_cost", 30))
        p.setdefault("sizeCost", p.get("size_cost", 1))
        p.setdefault("inspirationCost", p.get("inspiration_cost", 0.2))
    return base + fully


def load_plant_species_sync(include_manifested=True):
    base = _load_plant_species_json()
    if not include_manifested:
        return base
    manifested = db.load_manifested_plants_sync()
    fully = [p for p in manifested if p.get("fully_manifested", False)]
    for p in fully:
        p.setdefault("commonName", p.get("common_name", ""))
        p.setdefault("scientificName", p.get("scientific_name", ""))
        p.setdefault("rarityWeight", p.get("rarity_weight", 0))
        p.setdefault("seedCost", p.get("seed_cost", 30))
        p.setdefault("sizeCost", p.get("size_cost", 1))
        p.setdefault("inspirationCost", p.get("inspiration_cost", 0.2))
    return base + fully


async def get_plant_effect(common_name):
    plants = await load_plant_species()
    for p in plants:
        if p.get("commonName") == common_name:
            return p.get("effect", "")
    return ""


async def get_less_brood_chance(plants):
    """Calculate the total chance of needing one less brood from plants list."""
    total_chance = 0
    all_plant_species = await load_plant_species()
    plant_effects = {p["commonName"]: p.get("effect", "") for p in all_plant_species}

    for plant in plants:
        effect = plant_effects.get(plant["common_name"], "")
        if "chance of your eggs needing one less brood" in effect:
            match = re.search(r'([0-9]*\.?[0-9]+)%', effect)
            if match:
                total_chance += float(match.group(1))
    return total_chance


async def get_extra_bird_chance(plants):
    """Calculate the total chance of hatching an extra bird from plants list."""
    total_chance = 0
    all_plant_species = await load_plant_species()
    plant_effects = {p["commonName"]: p.get("effect", "") for p in all_plant_species}

    for plant in plants:
        effect = plant_effects.get(plant["common_name"], "")
        if "chance of your eggs hatching an extra bird" in effect:
            match = re.search(r'([0-9]*\.?[0-9]+)%', effect)
            if match:
                total_chance += float(match.group(1))
    return total_chance


# ---------------------------------------------------------------------------
# Research-based bonuses
# ---------------------------------------------------------------------------

def _get_milestone_thresholds():
    from commands.research import MILESTONE_THRESHOLDS
    return MILESTONE_THRESHOLDS


async def get_extra_garden_space():
    research_progress = await db.load_research_progress()
    research_entities = db.load_all_research_entities()
    thresholds = _get_milestone_thresholds()

    extra_space = 0
    for entity in research_entities:
        author_name = entity["author"]
        current_progress = research_progress.get(author_name, 0)
        if "+1 Max Garden Size" not in entity["milestones"][0]:
            continue
        for threshold in thresholds:
            if current_progress >= threshold:
                extra_space += 1
            else:
                break
    return extra_space


def get_extra_garden_space_sync():
    research_progress = db.load_research_progress_sync()
    research_entities = db.load_all_research_entities()
    thresholds = _get_milestone_thresholds()

    extra_space = 0
    for entity in research_entities:
        author_name = entity["author"]
        current_progress = research_progress.get(author_name, 0)
        if "+1 Max Garden Size" not in entity["milestones"][0]:
            continue
        for threshold in thresholds:
            if current_progress >= threshold:
                extra_space += 1
            else:
                break
    return extra_space


async def get_prayer_effectiveness_bonus():
    research_progress = await db.load_research_progress()
    research_entities = db.load_all_research_entities()
    thresholds = _get_milestone_thresholds()
    prayer_exponent = 1.0
    bonus_string = "Prayers are 1% more effective. Compounding!"

    for entity in research_entities:
        if entity["milestones"] and bonus_string in entity["milestones"][0]:
            author_name = entity["author"]
            current_progress = research_progress.get(author_name, 0)
            milestones_reached = 0
            for threshold in thresholds:
                if current_progress >= threshold:
                    milestones_reached += 1
                else:
                    break
            prayer_exponent += (milestones_reached * 0.01)
    return prayer_exponent


async def get_extra_bird_space():
    research_progress = await db.load_research_progress()
    research_entities = db.load_all_research_entities()
    thresholds = _get_milestone_thresholds()

    extra_space = 0
    for entity in research_entities:
        author_name = entity["author"]
        current_progress = research_progress.get(author_name, 0)
        if "+1 Bird Limit" not in entity["milestones"][0]:
            continue
        for threshold in thresholds:
            if current_progress >= threshold:
                extra_space += 1
            else:
                break
    return extra_space


def get_extra_bird_space_sync():
    research_progress = db.load_research_progress_sync()
    research_entities = db.load_all_research_entities()
    thresholds = _get_milestone_thresholds()

    extra_space = 0
    for entity in research_entities:
        author_name = entity["author"]
        current_progress = research_progress.get(author_name, 0)
        if "+1 Bird Limit" not in entity["milestones"][0]:
            continue
        for threshold in thresholds:
            if current_progress >= threshold:
                extra_space += 1
            else:
                break
    return extra_space
