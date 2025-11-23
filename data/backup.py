import os
import shutil
from typing import List, Optional

from config.config import DATA_PATH
from utils.logging import log_debug
from utils.time_utils import get_australian_time, get_current_date

BACKUP_DIR = os.path.join(DATA_PATH, "backups")
BACKUP_MARKER_FILE = os.path.join(DATA_PATH, "last_backup.txt")
FILES_TO_BACKUP: List[str] = [
    "nests.json",
    "manifested_birds.json",
    "manifested_plants.json",
    "research_progress.json",
]
MAX_BACKUPS = 10


def _read_last_backup_date() -> Optional[str]:
    """Return the last backup date stored in the marker file."""
    try:
        if os.path.exists(BACKUP_MARKER_FILE):
            with open(BACKUP_MARKER_FILE, "r") as f:
                return f.read().strip()
    except Exception as e:
        log_debug(f"Failed to read backup marker: {e}")
    return None


def _write_last_backup_date(date_str: str) -> None:
    """Persist the last backup date to the marker file."""
    try:
        with open(BACKUP_MARKER_FILE, "w") as f:
            f.write(date_str)
    except Exception as e:
        log_debug(f"Failed to write backup marker: {e}")


def _rotate_backups() -> None:
    """Keep only the newest MAX_BACKUPS backup directories."""
    if not os.path.exists(BACKUP_DIR):
        return

    backup_dirs = [
        os.path.join(BACKUP_DIR, name)
        for name in os.listdir(BACKUP_DIR)
        if os.path.isdir(os.path.join(BACKUP_DIR, name))
    ]

    backup_dirs.sort(key=lambda path: os.path.getmtime(path))

    while len(backup_dirs) > MAX_BACKUPS:
        oldest = backup_dirs.pop(0)
        try:
            shutil.rmtree(oldest)
            log_debug(f"Removed old backup: {oldest}")
        except Exception as e:
            log_debug(f"Failed to remove old backup {oldest}: {e}")


def _copy_backup_files(destination_dir: str) -> None:
    """Copy each tracked data file into the destination directory."""
    os.makedirs(destination_dir, exist_ok=True)

    for filename in FILES_TO_BACKUP:
        source_path = os.path.join(DATA_PATH, filename)
        dest_path = os.path.join(destination_dir, filename)

        if not os.path.exists(source_path):
            log_debug(f"Backup skipped (missing): {source_path}")
            continue

        try:
            shutil.copy2(source_path, dest_path)
            log_debug(f"Backed up {filename} to {dest_path}")
        except Exception as e:
            log_debug(f"Failed to back up {filename}: {e}")


def ensure_daily_backup() -> None:
    """
    Run once per day to back up key data files and rotate old backups.
    Called from the first action of the day.
    """
    today = get_current_date()
    last_backup = _read_last_backup_date()

    if last_backup == today:
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = get_australian_time().strftime("%Y-%m-%d-%H%M%S")
    destination_dir = os.path.join(BACKUP_DIR, f"backup-{timestamp}")

    _copy_backup_files(destination_dir)
    _rotate_backups()
    _write_last_backup_date(today)

    log_debug(f"Daily backup complete for {today}")
