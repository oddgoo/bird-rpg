from flask import render_template
from collections import defaultdict
from datetime import timedelta
from utils.time_utils import get_australian_time
import data.storage as db

AWARD_CATEGORIES = [
    {"key": "bard", "name": "Bard", "emoji": "🎵"},
    {"key": "conjurer", "name": "Conjurer", "emoji": "✨"},
    {"key": "academic", "name": "Academic", "emoji": "📚"},
    {"key": "caretaker", "name": "Caretaker", "emoji": "🥚"},
    {"key": "builder", "name": "Builder", "emoji": "🪺"},
    {"key": "observer", "name": "Observer", "emoji": "📷"},
    {"key": "gardener", "name": "Gardener", "emoji": "🌱"},
    {"key": "author", "name": "Author", "emoji": "📝"},
    {"key": "forager", "name": "Forager", "emoji": "🍂"},
    {"key": "swooper", "name": "Swooper", "emoji": "🦅"},
    {"key": "devotee", "name": "Devotee", "emoji": "🙏"},
    {"key": "explorer", "name": "Explorer", "emoji": "🧭"},
]

ACTION_AWARDS = {
    "manifest": "conjurer",
    "study": "academic",
    "brood": "caretaker",
    "build_common": "builder",
    "seed_common": "builder",
    "forage": "forager",
    "swoop": "swooper",
    "pray": "devotee",
    "explore": "explorer",
}

MEDALS = ["🥇", "🥈", "🥉"]


def get_awards_page():
    now = get_australian_time()
    cutoff = (now - timedelta(days=30)).strftime('%Y-%m-%d')

    # Load player names
    all_players = db.load_all_players_sync()
    names = {p["user_id"]: p.get("nest_name", "Unknown") for p in all_players}

    # Tallies per award key per user
    tallies = defaultdict(lambda: defaultdict(int))

    # Daily actions
    actions = db.get_all_daily_actions_sync(since_date=cutoff)
    for row in actions:
        history = row.get("action_history") or []
        for entry in history:
            award_key = ACTION_AWARDS.get(entry)
            if award_key:
                tallies[award_key][row["user_id"]] += 1

    # Songs (count of recipients sung to in last 30 days)
    songs = db.get_all_songs_sync(since_date=cutoff)
    for song in songs:
        tallies["bard"][song["singer_user_id"]] += 1

    # Birdwatch sightings
    sightings = db.get_all_birdwatch_sightings_unpaginated_sync()
    for s in sightings:
        created = (s.get("created_at") or "")[:10]
        if created >= cutoff:
            tallies["observer"][s["user_id"]] += 1

    # Plants
    all_plants = db.get_all_player_plants_sync()
    for user_id, plants in all_plants.items():
        count = sum(1 for p in plants if (p.get("planted_date") or "") >= cutoff)
        if count > 0:
            tallies["gardener"][user_id] += count

    # Memoirs
    memoirs = db.load_memoirs_sync()
    for m in memoirs:
        if (m.get("memoir_date") or "") >= cutoff:
            tallies["author"][m["user_id"]] += 1

    # Collective achievements
    manifested_birds = db.load_manifested_birds_sync()
    manifested_plants = db.load_manifested_plants_sync()
    defeated_humans = db.get_defeated_humans_sync()
    collective = [
        {"name": "Manifested species", "emoji": "📖", "count": len(manifested_birds) + len(manifested_plants)},
        {"name": "Sightings", "emoji": "📷", "count": len(sightings)},
        {"name": "Defeated humans", "emoji": "🦅", "count": len(defeated_humans)},
    ]

    # Build results
    awards = []
    for cat in AWARD_CATEGORIES:
        user_counts = tallies[cat["key"]]
        sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        top3 = []
        for i, (user_id, count) in enumerate(sorted_users):
            top3.append({
                "medal": MEDALS[i],
                "name": names.get(user_id, "Unknown"),
                "count": count,
            })
        awards.append({
            "name": cat["name"],
            "emoji": cat["emoji"],
            "top3": top3,
        })

    return render_template("awards.html", awards=awards, collective=collective)
