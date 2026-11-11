"""
Mirror species photos from the live site's /species_images/ route into the
local species_images folder, so a local copy of the game shows the same
pictures players saw (they live on the Render disk, not in Supabase).

Usage:
    python scripts/download_species_images.py [--base-url URL] [--backup DIR] [--dest DIR]

Species names come from data/bird_species.json, data/plant_species.json and
the backup's player_birds, player_plants, manifested_birds and
manifested_plants tables. Files that already exist locally are skipped.
Writes missing_species_images.json next to the images for anything the site
did not have. Read-only against the site.
"""

import argparse
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.export_pdfs import DEFAULT_BASE_URL, PROJECT_ROOT, latest_backup_dir, load_table  # noqa: E402


def collect_species(backup_dir):
    """Return {scientific_name} for every non-Special species the game knows."""
    with open(os.path.join(PROJECT_ROOT, "data", "bird_species.json"), encoding="utf-8") as f:
        birds = json.load(f)["bird_species"]
    # Special birds use bundled images in static/images/special-birds/.
    special = {b["scientificName"] for b in birds if b.get("rarity") == "Special"}
    names = {b["scientificName"] for b in birds}
    with open(os.path.join(PROJECT_ROOT, "data", "plant_species.json"), encoding="utf-8") as f:
        names.update(p["scientificName"] for p in json.load(f))
    if backup_dir:
        for table in ("player_birds", "player_plants", "manifested_birds", "manifested_plants"):
            names.update(r["scientific_name"] for r in load_table(backup_dir, table) if r.get("scientific_name"))
    return names - special


def local_filename(scientific_name):
    """Same naming the bot uses when it downloads an image."""
    return f"{urllib.parse.quote(scientific_name)}.jpg"


def main():
    parser = argparse.ArgumentParser(description="Download species photos from the live site.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--backup", help="Backup folder (default: newest backups/supabase-*)")
    parser.add_argument("--dest", default=os.path.join(PROJECT_ROOT, "bird-rpg", "species_images"))
    args = parser.parse_args()

    import httpx
    names = sorted(collect_species(args.backup or latest_backup_dir()))
    os.makedirs(args.dest, exist_ok=True)
    base = args.base_url.rstrip("/")
    fetched, skipped, missing = 0, 0, []
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for i, name in enumerate(names, 1):
            dest = os.path.join(args.dest, local_filename(name))
            if os.path.exists(dest) and os.path.getsize(dest) > 0:
                skipped += 1
                continue
            # The same URL the user page requests (encodeURIComponent + .jpg).
            url = f"{base}/species_images/{urllib.parse.quote(name, safe='')}.jpg"
            try:
                resp = client.get(url)
                if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
                    with open(dest, "wb") as f:
                        f.write(resp.content)
                    fetched += 1
                else:
                    missing.append(name)
            except Exception as e:
                missing.append(name)
                print(f"  ! {name}: {e}")
            if i % 100 == 0:
                print(f"  {i}/{len(names)} checked")

    with open(os.path.join(args.dest, "missing_species_images.json"), "w", encoding="utf-8") as f:
        json.dump(missing, f, ensure_ascii=False, indent=2)
    print(f"\n{len(names)} species: {fetched} downloaded, {skipped} already here, {len(missing)} not on the site.")


if __name__ == "__main__":
    main()
