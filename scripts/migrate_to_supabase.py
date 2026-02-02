"""
Migration script: JSON files -> Supabase

Usage:
    1. Set SUPABASE_URL and SUPABASE_KEY in .env
    2. Run schema.sql in Supabase SQL Editor first
    3. python scripts/migrate_to_supabase.py

Safe to re-run (uses UPSERT where possible).
"""

import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
    sys.exit(1)

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_PATH = "/var/data" if os.path.isdir("/var/data") else PROJECT_ROOT
DATA_PATH = os.path.join(STORAGE_PATH, "bird-rpg")


def load_json(filepath, default=None):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"  File not found: {filepath}")
        return default
    except json.JSONDecodeError as e:
        print(f"  JSON decode error in {filepath}: {e}")
        return default


def migrate_common_nest(data):
    print("\n--- Common Nest ---")
    cn = data.get("common_nest", {})
    sb.table("common_nest").upsert({
        "id": 1,
        "twigs": cn.get("twigs", 0),
        "seeds": cn.get("seeds", 0),
    }).execute()
    print(f"  Migrated: twigs={cn.get('twigs', 0)}, seeds={cn.get('seeds', 0)}")


def migrate_players(data):
    print("\n--- Players ---")
    nests = data.get("personal_nests", {})
    count = 0

    for user_id, nest in nests.items():
        featured = nest.get("featured_bird", {}) or {}
        row = {
            "user_id": user_id,
            "discord_username": nest.get("discord_username"),
            "nest_name": nest.get("name", "Some Bird's Nest"),
            "twigs": nest.get("twigs", 0),
            "seeds": nest.get("seeds", 0),
            "inspiration": nest.get("inspiration", 0),
            "garden_size": nest.get("garden_size", 0),
            "bonus_actions": nest.get("bonus_actions", 0),
            "locked": nest.get("locked", False),
            "featured_bird_common_name": featured.get("commonName"),
            "featured_bird_scientific_name": featured.get("scientificName"),
        }
        sb.table("players").upsert(row, on_conflict="user_id").execute()
        count += 1

    print(f"  Migrated {count} players")
    return nests


def migrate_birds(nests):
    print("\n--- Player Birds ---")
    total_birds = 0
    total_bird_treasures = 0

    for user_id, nest in nests.items():
        chicks = nest.get("chicks", [])
        for chick in chicks:
            res = sb.table("player_birds").insert({
                "user_id": user_id,
                "common_name": chick.get("commonName", ""),
                "scientific_name": chick.get("scientificName", ""),
            }).execute()
            total_birds += 1

            bird_id = res.data[0]["id"]

            # Migrate treasures on this bird
            for treasure in chick.get("treasures", []):
                sb.table("bird_treasures").insert({
                    "bird_id": bird_id,
                    "treasure_id": treasure.get("id", ""),
                    "x": treasure.get("x", 0),
                    "y": treasure.get("y", 0),
                }).execute()
                total_bird_treasures += 1

    print(f"  Migrated {total_birds} birds, {total_bird_treasures} bird treasures")


def migrate_plants(nests):
    print("\n--- Player Plants ---")
    total = 0

    for user_id, nest in nests.items():
        plants = nest.get("plants", [])
        for plant in plants:
            sb.table("player_plants").insert({
                "user_id": user_id,
                "common_name": plant.get("commonName", ""),
                "scientific_name": plant.get("scientificName", ""),
                "planted_date": plant.get("planted_date"),
            }).execute()
            total += 1

    print(f"  Migrated {total} plants")


def migrate_treasures(nests):
    print("\n--- Player Treasures (inventory) ---")
    total_inv = 0
    total_nest = 0

    for user_id, nest in nests.items():
        # Inventory treasures (list of treasure_id strings)
        for tid in nest.get("treasures", []):
            sb.table("player_treasures").insert({
                "user_id": user_id,
                "treasure_id": tid,
            }).execute()
            total_inv += 1

        # Nest-applied treasures
        for t in nest.get("treasures_applied_on_nest", []):
            sb.table("nest_treasures").insert({
                "user_id": user_id,
                "treasure_id": t.get("id", ""),
                "x": t.get("x", 0),
                "y": t.get("y", 0),
            }).execute()
            total_nest += 1

    print(f"  Migrated {total_inv} inventory treasures, {total_nest} nest treasures")


def migrate_eggs(nests):
    print("\n--- Eggs ---")
    total = 0

    for user_id, nest in nests.items():
        egg = nest.get("egg")
        if not egg:
            continue

        sb.table("eggs").upsert({
            "user_id": user_id,
            "brooding_progress": egg.get("brooding_progress", 0),
            "protected_prayers": egg.get("protected_prayers", False),
        }, on_conflict="user_id").execute()
        total += 1

        # Multipliers
        for sci_name, mult in egg.get("multipliers", {}).items():
            sb.table("egg_multipliers").upsert({
                "egg_user_id": user_id,
                "scientific_name": sci_name,
                "multiplier": mult,
            }, on_conflict="egg_user_id,scientific_name").execute()

        # Brooders
        for brooder_id in egg.get("brooded_by", []):
            sb.table("egg_brooders").upsert({
                "egg_user_id": user_id,
                "brooder_user_id": str(brooder_id),
            }, on_conflict="egg_user_id,brooder_user_id").execute()

    print(f"  Migrated {total} eggs")


def migrate_daily_actions(data):
    print("\n--- Daily Actions ---")
    actions = data.get("daily_actions", {})
    total = 0

    for user_id, user_actions in actions.items():
        for key, value in user_actions.items():
            # New format: "actions_YYYY-MM-DD" -> {used, action_history}
            if key.startswith("actions_") and isinstance(value, dict):
                date_str = key[len("actions_"):]
                sb.table("daily_actions").upsert({
                    "user_id": user_id,
                    "action_date": date_str,
                    "used": value.get("used", 0),
                    "action_history": value.get("action_history", []),
                }, on_conflict="user_id,action_date").execute()
                total += 1
            # Old format: "action_type_YYYY-MM-DD": true (skip, these are legacy)

    print(f"  Migrated {total} daily action records")


def migrate_daily_songs(data):
    print("\n--- Daily Songs ---")
    songs = data.get("daily_songs", {})
    total = 0

    for date_str, singers in songs.items():
        for singer_id, targets in singers.items():
            for target_id in targets:
                sb.table("daily_songs").upsert({
                    "song_date": date_str,
                    "singer_user_id": str(singer_id),
                    "target_user_id": str(target_id),
                }, on_conflict="song_date,singer_user_id,target_user_id").execute()
                total += 1

    print(f"  Migrated {total} song records")


def migrate_daily_brooding(data):
    print("\n--- Daily Brooding ---")
    brooding = data.get("daily_brooding", {})
    total = 0

    for date_str, brooders in brooding.items():
        for brooder_id, targets in brooders.items():
            for target_id in targets:
                sb.table("daily_brooding").upsert({
                    "brooding_date": date_str,
                    "brooder_user_id": str(brooder_id),
                    "target_user_id": str(target_id),
                }, on_conflict="brooding_date,brooder_user_id,target_user_id").execute()
                total += 1

    print(f"  Migrated {total} brooding records")


def migrate_last_song_targets(nests):
    print("\n--- Last Song Targets ---")
    total = 0

    for user_id, nest in nests.items():
        targets = nest.get("last_song_target_ids", [])
        for i, target_id in enumerate(targets):
            sb.table("last_song_targets").insert({
                "user_id": user_id,
                "target_user_id": str(target_id),
                "sort_order": i,
            }).execute()
            total += 1

    print(f"  Migrated {total} last song target records")


def migrate_released_birds(data):
    print("\n--- Released Birds ---")
    birds = data.get("released_birds", [])

    for bird in birds:
        sb.table("released_birds").upsert({
            "common_name": bird.get("commonName", ""),
            "scientific_name": bird.get("scientificName", ""),
            "count": bird.get("count", 1),
        }, on_conflict="scientific_name").execute()

    print(f"  Migrated {len(birds)} released bird records")


def migrate_defeated_humans(data):
    print("\n--- Defeated Humans ---")
    humans = data.get("defeated_humans", [])
    total = 0

    for human in humans:
        blessing = human.get("blessing", {})
        sb.table("defeated_humans").insert({
            "name": human.get("name", ""),
            "max_resilience": human.get("max_resilience"),
            "defeat_date": human.get("date", ""),
            "blessing_name": blessing.get("name"),
            "blessing_amount": blessing.get("amount"),
        }).execute()
        total += 1

    print(f"  Migrated {total} defeated human records")


def migrate_exploration(data):
    print("\n--- Exploration ---")
    exploration = data.get("exploration", {})

    for region, points in exploration.items():
        sb.table("exploration").upsert({
            "region": region,
            "points": points,
        }, on_conflict="region").execute()

    print(f"  Migrated {len(exploration)} exploration regions")


def migrate_weather_channels(data):
    print("\n--- Weather Channels ---")
    channels = data.get("weather_channels", {})

    for guild_id, channel_id in channels.items():
        sb.table("weather_channels").upsert({
            "guild_id": guild_id,
            "channel_id": channel_id,
        }, on_conflict="guild_id").execute()

    print(f"  Migrated {len(channels)} weather channels")


def migrate_memoirs():
    print("\n--- Memoirs ---")
    lore = load_json(os.path.join(DATA_PATH, "lore.json"), {"memoirs": []})
    memoirs = lore.get("memoirs", [])

    for m in memoirs:
        sb.table("memoirs").insert({
            "user_id": m.get("user_id", ""),
            "nest_name": m.get("nest_name"),
            "text": m.get("text", ""),
            "memoir_date": m.get("date", ""),
        }).execute()

    print(f"  Migrated {len(memoirs)} memoirs")


def migrate_realm_messages():
    print("\n--- Realm Messages ---")
    realm_path = os.path.join(PROJECT_ROOT, "data", "realm_lore.json")
    realm = load_json(realm_path, {"messages": []})
    messages = realm.get("messages", [])

    for m in messages:
        sb.table("realm_messages").insert({
            "message_date": m.get("date", ""),
            "message": m.get("message", ""),
        }).execute()

    print(f"  Migrated {len(messages)} realm messages")


def migrate_manifested_birds():
    print("\n--- Manifested Birds ---")
    birds = load_json(os.path.join(DATA_PATH, "manifested_birds.json"), [])

    for bird in birds:
        sb.table("manifested_birds").upsert({
            "common_name": bird.get("commonName", ""),
            "scientific_name": bird.get("scientificName", ""),
            "rarity_weight": bird.get("rarityWeight", 0),
            "rarity": bird.get("rarity", "common"),
            "effect": bird.get("effect", ""),
            "manifested_points": bird.get("manifested_points", 0),
            "fully_manifested": bird.get("fully_manifested", False),
        }, on_conflict="scientific_name").execute()

    print(f"  Migrated {len(birds)} manifested birds")


def migrate_manifested_plants():
    print("\n--- Manifested Plants ---")
    plants = load_json(os.path.join(DATA_PATH, "manifested_plants.json"), [])

    for plant in plants:
        sb.table("manifested_plants").upsert({
            "common_name": plant.get("commonName", ""),
            "scientific_name": plant.get("scientificName", ""),
            "rarity_weight": plant.get("rarityWeight", 0),
            "rarity": plant.get("rarity", "common"),
            "effect": plant.get("effect", ""),
            "seed_cost": plant.get("seedCost", 30),
            "size_cost": plant.get("sizeCost", 1),
            "inspiration_cost": plant.get("inspirationCost", 0.2),
            "manifested_points": plant.get("manifested_points", 0),
            "fully_manifested": plant.get("fully_manifested", False),
        }, on_conflict="scientific_name").execute()

    print(f"  Migrated {len(plants)} manifested plants")


def migrate_research_progress():
    print("\n--- Research Progress ---")
    progress = load_json(os.path.join(DATA_PATH, "research_progress.json"), {})

    for author, points in progress.items():
        sb.table("research_progress").upsert({
            "author_name": author,
            "points": points,
        }, on_conflict="author_name").execute()

    print(f"  Migrated {len(progress)} research progress entries")


def main():
    print("=" * 60)
    print("Bird RPG: JSON -> Supabase Migration")
    print("=" * 60)

    # Load main data file
    nests_path = os.path.join(DATA_PATH, "nests.json")
    print(f"\nLoading {nests_path}...")
    data = load_json(nests_path)
    if data is None:
        print("Error: Could not load nests.json")
        sys.exit(1)

    # Migrate in dependency order
    migrate_common_nest(data)
    nests = migrate_players(data)
    migrate_birds(nests)
    migrate_plants(nests)
    migrate_treasures(nests)
    migrate_eggs(nests)
    migrate_daily_actions(data)
    migrate_daily_songs(data)
    migrate_daily_brooding(data)
    migrate_last_song_targets(nests)
    migrate_released_birds(data)
    migrate_defeated_humans(data)
    migrate_exploration(data)
    migrate_weather_channels(data)

    # Migrate separate JSON files
    migrate_memoirs()
    migrate_realm_messages()
    migrate_manifested_birds()
    migrate_manifested_plants()
    migrate_research_progress()

    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
