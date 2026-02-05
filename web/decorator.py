"""Flask routes for the visual sticker decorator."""

from collections import Counter
from flask import render_template, request, jsonify, abort
from web.decorator_tokens import validate_token
from data.models import load_treasures
import data.storage as db


def decorator_routes(app):

    @app.route('/decorate/<token>')
    def decorate_page(token):
        token_data = validate_token(token)
        if not token_data:
            return render_template('decorator_expired.html'), 403

        entity_type = token_data["entity_type"]
        entity_id = token_data["entity_id"]
        user_id = token_data["user_id"]

        # Verify ownership
        if not db.verify_entity_ownership_sync(user_id, entity_type, entity_id):
            abort(403)

        # Load entity info
        entity_info = _load_entity_info(user_id, entity_type, entity_id)
        if not entity_info:
            abort(404, "Entity not found.")

        # Load player's unplaced treasure inventory
        inventory_rows = db.get_player_treasures_sync(user_id)

        # Load all treasure metadata
        treasures_data = load_treasures()
        all_treasures = {}
        for category in treasures_data.values():
            for treasure in category:
                all_treasures[treasure['id']] = treasure

        # Enrich inventory with treasure metadata
        inventory = []
        for row in inventory_rows:
            tid = row["treasure_id"]
            if tid in all_treasures:
                inventory.append({
                    "treasure_id": tid,
                    "db_id": row["id"],
                    **all_treasures[tid],
                })

        # Enrich current decorations with treasure metadata
        current_decorations = []
        for dec in entity_info["decorations"]:
            tid = dec["treasure_id"]
            if tid in all_treasures:
                # Use saved size from DB if available, otherwise fall back to treasure default
                saved_size = dec.get("size")
                default_size = all_treasures[tid].get("size", 100)
                current_decorations.append({
                    "treasure_id": tid,
                    "x": dec.get("x", 0),
                    "y": dec.get("y", 0),
                    "rotation": dec.get("rotation", 0),
                    "z_index": dec.get("z_index", 0),
                    "size": saved_size if saved_size is not None else default_size,
                    "name": all_treasures[tid].get("name", tid),
                })

        return render_template('decorator.html',
            token=token,
            entity_type=entity_type,
            entity_info=entity_info,
            current_decorations=current_decorations,
            inventory=inventory,
            all_treasures=all_treasures,
        )

    @app.route('/decorate/<token>/save', methods=['POST'])
    def decorate_save(token):
        token_data = validate_token(token)
        if not token_data:
            return jsonify({"error": "Token expired or invalid"}), 403

        entity_type = token_data["entity_type"]
        entity_id = token_data["entity_id"]
        user_id = token_data["user_id"]

        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request body"}), 400

        placed = data.get("placed", [])
        returned_inventory = data.get("inventory", [])

        # Load current state from DB for validation
        original_placed_ids = _get_current_decoration_ids(entity_type, entity_id, user_id)
        original_inventory_rows = db.get_player_treasures_sync(user_id)
        original_inventory_ids = [r["treasure_id"] for r in original_inventory_rows]

        # Build multiset of what the user originally had
        original_all = Counter(original_placed_ids + original_inventory_ids)

        # Build multiset of what the user is submitting
        new_placed_ids = [item["treasure_id"] for item in placed]
        new_all = Counter(new_placed_ids + returned_inventory)

        # Validate: no stickers created or destroyed
        if original_all != new_all:
            return jsonify({"error": "Sticker mismatch - cannot create or destroy stickers"}), 400

        # Build decoration rows
        decorations = []
        for item in placed:
            decorations.append({
                "treasure_id": item["treasure_id"],
                "x": max(0, min(100, int(item.get("x", 0)))),
                "y": max(0, min(100, int(item.get("y", 0)))),
                "rotation": int(item.get("rotation", 0)) % 360,
                "z_index": int(item.get("z_index", 0)),
                "size": max(5, min(100, int(item.get("size", 100)))),
            })

        # Save decorations (delete-then-insert)
        if entity_type == "bird":
            db.save_bird_decorations_sync(entity_id, decorations)
        elif entity_type == "plant":
            db.save_plant_decorations_sync(entity_id, decorations)
        elif entity_type == "nest":
            db.save_nest_decorations_sync(user_id, decorations)

        # Reconcile inventory: figure out what moved
        old_placed_counter = Counter(original_placed_ids)
        new_placed_counter = Counter(new_placed_ids)

        # Stickers that moved FROM inventory TO entity
        moved_to_entity = new_placed_counter - old_placed_counter
        for tid, count in moved_to_entity.items():
            for _ in range(count):
                db.remove_player_treasure_sync(user_id, tid)

        # Stickers that moved FROM entity TO inventory
        moved_to_inventory = old_placed_counter - new_placed_counter
        for tid, count in moved_to_inventory.items():
            for _ in range(count):
                db.add_player_treasure_sync(user_id, tid)

        return jsonify({"success": True})


def _load_entity_info(user_id, entity_type, entity_id):
    """Load entity name, image URL, and current decorations."""
    if entity_type == "bird":
        birds = db.get_player_birds_sync(user_id)
        bird = next((b for b in birds if b["id"] == entity_id), None)
        if not bird:
            return None
        decorations = db.get_bird_treasures_sync(entity_id)
        # Determine image URL
        from data.models import load_bird_species_sync
        all_species = {s["scientificName"]: s for s in load_bird_species_sync()}
        species_info = all_species.get(bird["scientific_name"], {})
        rarity = species_info.get("rarity", "common")
        if rarity == "Special":
            image_url = f"/static/images/special-birds/{bird['scientific_name']}.png"
        else:
            image_url = f"/species_images/{bird['scientific_name']}.jpg"
        return {
            "name": bird["common_name"],
            "scientific_name": bird["scientific_name"],
            "image_url": image_url,
            "decorations": decorations,
        }
    elif entity_type == "plant":
        plants = db.get_player_plants_sync(user_id)
        plant = next((p for p in plants if p["id"] == entity_id), None)
        if not plant:
            return None
        decorations = db.get_plant_treasures_sync(entity_id)
        return {
            "name": plant["common_name"],
            "scientific_name": plant["scientific_name"],
            "image_url": f"/species_images/{plant['scientific_name']}.jpg",
            "decorations": decorations,
        }
    elif entity_type == "nest":
        player = db.load_player_sync(user_id)
        decorations = db.get_nest_treasures_sync(user_id)
        return {
            "name": player.get("nest_name", "My Nest"),
            "image_url": "/static/images/papyrus.jpg",
            "decorations": decorations,
        }
    return None


def _get_current_decoration_ids(entity_type, entity_id, user_id):
    """Get the list of treasure_ids currently placed on an entity."""
    if entity_type == "bird":
        rows = db.get_bird_treasures_sync(entity_id)
    elif entity_type == "plant":
        rows = db.get_plant_treasures_sync(entity_id)
    elif entity_type == "nest":
        rows = db.get_nest_treasures_sync(user_id)
    else:
        return []
    return [r["treasure_id"] for r in rows]
