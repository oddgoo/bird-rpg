"""
Full backup of the Bird RPG Supabase project: every table plus the
birdwatch-images storage bucket.

Usage:
    1. Set SUPABASE_URL and SUPABASE_KEY in .env (the same values the bot uses)
    2. Stop the bot so nothing changes mid-backup
    3. python scripts/backup_supabase.py [--out DIR] [--skip-images]

Output (default: ./backups/supabase-YYYYMMDD-HHMMSS/):
    tables/<table>.json            all rows of each table, as a JSON list
    storage/birdwatch-images/...   every file in the bucket, same paths
    schema.sql                     copy of scripts/schema.sql for restoring
    manifest.json                  row counts, file counts and any errors

The script only reads from Supabase; it never writes or deletes anything there.
Exits with status 1 if any table or file failed, so check the output.
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BUCKET = "birdwatch-images"
PAGE_SIZE = 1000  # Supabase caps a single select at 1000 rows by default

# Every table in scripts/schema.sql, mapped to its primary key column so
# pagination has a stable order. Parents come before children, which is also
# a safe order for re-inserting the data later.
TABLES = {
    "players": "user_id",
    "common_nest": "id",
    "player_birds": "id",
    "bird_treasures": "id",
    "player_plants": "id",
    "plant_treasures": "id",
    "player_treasures": "id",
    "nest_treasures": "id",
    "eggs": "user_id",
    "egg_multipliers": "id",
    "egg_brooders": "id",
    "daily_actions": "id",
    "daily_songs": "id",
    "daily_brooding": "id",
    "last_song_targets": "id",
    "released_birds": "id",
    "defeated_humans": "id",
    "memoirs": "id",
    "realm_messages": "id",
    "manifested_birds": "id",
    "manifested_plants": "id",
    "research_progress": "author_name",
    "exploration": "region",
    "weather_channels": "guild_id",
    "game_settings": "key",
    "birdwatch_sightings": "id",
}


def fetch_all_rows(sb, table, order_column):
    """Return every row of a table, paging past the 1000-row limit."""
    rows = []
    start = 0
    while True:
        res = (
            sb.table(table)
            .select("*")
            .order(order_column)
            .range(start, start + PAGE_SIZE - 1)
            .execute()
        )
        page = res.data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


def list_bucket_files(bucket, prefix=""):
    """Recursively list every file path in a storage bucket.

    Supabase returns folders as entries with no id; we descend into those.
    """
    paths = []
    offset = 0
    while True:
        entries = bucket.list(
            prefix,
            {"limit": PAGE_SIZE, "offset": offset, "sortBy": {"column": "name", "order": "asc"}},
        ) or []
        for entry in entries:
            name = entry.get("name")
            if not name or name == ".emptyFolderPlaceholder":
                continue
            full = f"{prefix}/{name}" if prefix else name
            if entry.get("id") is None:
                paths.extend(list_bucket_files(bucket, full))
            else:
                paths.append(full)
        if len(entries) < PAGE_SIZE:
            return paths
        offset += PAGE_SIZE


def safe_local_path(root, storage_path):
    """Join a storage path under root, refusing anything that escapes it."""
    dest = os.path.normpath(os.path.join(root, storage_path))
    if os.path.commonpath([os.path.abspath(root), os.path.abspath(dest)]) != os.path.abspath(root):
        raise ValueError(f"Unsafe storage path: {storage_path}")
    return dest


def download_file(bucket, path, public_url=None):
    """Download via the storage API, falling back to the public URL.

    The anon key may lack a storage read policy even though the bucket is
    public, in which case the public URL still works.
    """
    try:
        return bucket.download(path)
    except Exception:
        if not public_url:
            raise
        import httpx
        resp = httpx.get(public_url, timeout=60, follow_redirects=True)
        resp.raise_for_status()
        return resp.content


def backup_tables(sb, out_dir, manifest):
    tables_dir = os.path.join(out_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)
    for table, order_column in TABLES.items():
        try:
            rows = fetch_all_rows(sb, table, order_column)
        except Exception as e:
            print(f"  ! {table}: FAILED ({e})")
            manifest["errors"].append(f"table {table}: {e}")
            continue
        with open(os.path.join(tables_dir, f"{table}.json"), "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2, default=str)
        manifest["tables"][table] = len(rows)
        print(f"  {table}: {len(rows)} rows")


def backup_bucket(sb, out_dir, manifest, sighting_rows):
    bucket = sb.storage.from_(BUCKET)
    storage_dir = os.path.join(out_dir, "storage", BUCKET)
    os.makedirs(storage_dir, exist_ok=True)

    try:
        paths = set(list_bucket_files(bucket))
    except Exception as e:
        print(f"  ! listing bucket failed ({e}); falling back to birdwatch_sightings paths")
        manifest["errors"].append(f"bucket list: {e}")
        paths = set()
    # Also include every path the database references, in case listing missed any.
    public_urls = {r["storage_path"]: r.get("image_url") for r in sighting_rows if r.get("storage_path")}
    paths.update(public_urls)

    downloaded = 0
    for path in sorted(paths):
        try:
            dest = safe_local_path(storage_dir, path)
            data = download_file(bucket, path, public_urls.get(path))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(data)
            downloaded += 1
        except Exception as e:
            print(f"  ! {path}: FAILED ({e})")
            manifest["errors"].append(f"file {path}: {e}")
    manifest["storage"][BUCKET] = {"found": len(paths), "downloaded": downloaded}
    print(f"  {BUCKET}: {downloaded}/{len(paths)} files")


def run_backup(sb, out_dir, skip_images=False):
    """Back up everything into out_dir. Returns the manifest dict."""
    os.makedirs(out_dir, exist_ok=True)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tables": {},
        "storage": {},
        "errors": [],
    }

    print("Backing up tables...")
    backup_tables(sb, out_dir, manifest)

    if skip_images:
        print("Skipping storage bucket (--skip-images)")
    else:
        print("Backing up storage bucket...")
        sightings_file = os.path.join(out_dir, "tables", "birdwatch_sightings.json")
        sightings = []
        if os.path.exists(sightings_file):
            with open(sightings_file, encoding="utf-8") as f:
                sightings = json.load(f)
        backup_bucket(sb, out_dir, manifest, sightings)

    schema_src = os.path.join(PROJECT_ROOT, "scripts", "schema.sql")
    if os.path.exists(schema_src):
        shutil.copy2(schema_src, os.path.join(out_dir, "schema.sql"))

    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Back up the Bird RPG Supabase project.")
    parser.add_argument("--out", help="Output directory (default: backups/supabase-<timestamp>)")
    parser.add_argument("--skip-images", action="store_true", help="Only back up tables")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)

    from supabase import create_client
    sb = create_client(url, key)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out or os.path.join(PROJECT_ROOT, "backups", f"supabase-{stamp}")
    print(f"Writing backup to {out_dir}\n")

    manifest = run_backup(sb, out_dir, skip_images=args.skip_images)

    total_rows = sum(manifest["tables"].values())
    print(f"\nDone: {len(manifest['tables'])}/{len(TABLES)} tables, {total_rows} rows.")
    if manifest["errors"]:
        print(f"{len(manifest['errors'])} error(s) - see manifest.json. Do NOT delete the project yet.")
        sys.exit(1)
    print("No errors.")


if __name__ == "__main__":
    main()
