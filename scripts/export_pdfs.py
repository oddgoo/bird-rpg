"""
Export the public Bird RPG web pages as PDFs, for archiving player content.

Prints the real pages with headless Chromium, so the papyrus styling, species
photos and decorated stickers come out exactly as players saw them.

Usage:
    pip install playwright pymupdf && python -m playwright install chromium
    python scripts/export_pdfs.py [--base-url URL] [--out DIR] [--backup DIR]
                                  [--only birdwatch,lore,nests] [--users ID,ID] [--include-empty]

Output (default: ./exports/pdf-YYYYMMDD-HHMMSS/):
    birdwatch.pdf          every page of the Birdwatch gallery, merged
    wings-of-time.pdf      the lore: all memoirs and realm messages
    nests/<name>-<id>.pdf  one PDF per player nest (birds, plants, treasures)
    all-nests.pdf          every nest PDF merged into one book
    export_report.json     what was exported, plus missing images and errors

Player IDs come from players.json in the newest backups/supabase-*/tables
folder (or --backup). Nests with no birds and no plants are skipped unless
--include-empty is given. The script only reads pages; it never writes to the site.
"""

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BASE_URL = "https://bird-rpg.onrender.com"

# Rendered at a desktop width so the card grids keep their 3-4 columns, on a
# page with A4 proportions. Chromium scales it down to fit when printed.
PAGE_WIDTH_PX = 1240
PAGE_HEIGHT_PX = 1754

# Hides site chrome and day-to-day sections, and stops cards splitting across pages.
PRINT_CSS = """
nav, .magpie-left, .magpie-right { display: none !important; }
a[href="/"] { display: none !important; }
.export-hidden { display: none !important; }
li, .shadow-md, h2, h3 { break-inside: avoid; page-break-inside: avoid; }
h2, h3 { break-after: avoid; page-break-after: avoid; }
.hover\\:-translate-y-1, .transform { transform: none !important; }
body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
/* Shadows and blur become a full-page image mask each in the PDF; drop them. */
*, *::before, *::after { box-shadow: none !important; backdrop-filter: none !important; }
.shadow-md, .shadow-sm { outline: 1px solid rgba(146, 64, 14, 0.18); }
"""

# Removes the "Today's Songs" / "Today's Brooding" boxes (only meaningful on
# the day) and the birdwatch pagination, and loads lazy images eagerly.
PREPARE_JS = """
() => {
  document.querySelectorAll('h2').forEach(h => {
    if (/Today's (Songs|Brooding)/.test(h.textContent)) {
      const box = h.closest('.rounded-xl');
      if (box) box.classList.add('export-hidden');
    }
  });
  document.querySelectorAll('a[href*="/birdwatch?page="]').forEach(a => {
    const bar = a.parentElement;
    if (bar) bar.classList.add('export-hidden');
  });
  document.querySelectorAll('img[loading="lazy"]').forEach(img => img.loading = 'eager');
}
"""

# Waits until every image has finished (loaded or failed), then reports failures.
WAIT_IMAGES_JS = """
async () => {
  const imgs = Array.from(document.images).filter(i => i.getAttribute('src'));
  await Promise.all(imgs.map(i => i.complete ? null : new Promise(r => {
    i.addEventListener('load', r, {once: true});
    i.addEventListener('error', r, {once: true});
  })));
  await document.fonts.ready;
  return imgs.filter(i => i.naturalWidth === 0).map(i => i.getAttribute('src'));
}
"""


def latest_backup_dir():
    dirs = sorted(glob.glob(os.path.join(PROJECT_ROOT, "backups", "supabase-*")))
    return dirs[-1] if dirs else None


def load_table(backup_dir, table):
    with open(os.path.join(backup_dir, "tables", f"{table}.json"), encoding="utf-8") as f:
        return json.load(f)


def select_players(backup_dir, include_empty=False, only_ids=None):
    """Return [(user_id, nest_name)] for the nests to export, biggest first."""
    players = load_table(backup_dir, "players")
    counts = {}
    for table in ("player_birds", "player_plants"):
        for row in load_table(backup_dir, table):
            counts[str(row["user_id"])] = counts.get(str(row["user_id"]), 0) + 1
    chosen = []
    for p in players:
        uid = str(p["user_id"])
        if only_ids and uid not in only_ids:
            continue
        if not include_empty and not only_ids and counts.get(uid, 0) == 0:
            continue
        name = p.get("nest_name") or p.get("discord_username") or uid
        chosen.append((uid, name, counts.get(uid, 0)))
    chosen.sort(key=lambda x: -x[2])
    return [(uid, name) for uid, name, _ in chosen]


def slugify(text, max_len=40):
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return slug[:max_len].strip("-") or "nest"


def merge_pdfs(paths, dest):
    """Merge PDFs into dest, storing repeated images (backgrounds) only once."""
    import pymupdf
    out = pymupdf.open()
    for path in paths:
        with pymupdf.open(path) as src:
            out.insert_pdf(src)
    out.save(dest, garbage=4, deflate=True)
    out.close()


def compact_pdf(path):
    """Rewrite a single PDF in place with duplicate images removed."""
    tmp = path + ".tmp"
    merge_pdfs([path], tmp)
    os.replace(tmp, path)


class Exporter:
    def __init__(self, browser, base_url, report):
        self.base_url = base_url.rstrip("/")
        self.report = report
        self.context = browser.new_context(viewport={"width": PAGE_WIDTH_PX, "height": 1000})
        self.page = self.context.new_page()
        self.page.set_default_timeout(120_000)

    def render(self, path, dest):
        """Print one page to dest. Returns the page's HTML (for pagination)."""
        url = self.base_url + path
        resp = self.page.goto(url, wait_until="networkidle")
        if resp is None or resp.status != 200:
            raise RuntimeError(f"{url} returned {resp.status if resp else 'no response'}")
        self.page.evaluate(PREPARE_JS)
        self.page.add_style_tag(content=PRINT_CSS)
        missing = self.page.evaluate(WAIT_IMAGES_JS)
        if missing:
            self.report["missing_images"][path] = missing
        self.page.emulate_media(media="screen")
        self.page.pdf(
            path=dest,
            width=f"{PAGE_WIDTH_PX}px",
            height=f"{PAGE_HEIGHT_PX}px",
            print_background=True,
            margin={"top": "24px", "bottom": "24px", "left": "24px", "right": "24px"},
        )
        compact_pdf(dest)
        return self.page.content()

    def close(self):
        self.context.close()


def export_birdwatch(ex, out_dir, report):
    tmp_dir = os.path.join(out_dir, "_birdwatch_pages")
    os.makedirs(tmp_dir, exist_ok=True)
    parts = []
    page_no = 1
    while True:
        dest = os.path.join(tmp_dir, f"page-{page_no:03d}.pdf")
        html = ex.render(f"/birdwatch?page={page_no}", dest)
        parts.append(dest)
        print(f"  birdwatch page {page_no}")
        if f"/birdwatch?page={page_no + 1}" not in html:
            break
        page_no += 1
    final = os.path.join(out_dir, "birdwatch.pdf")
    merge_pdfs(parts, final)
    for p in parts:
        os.remove(p)
    os.rmdir(tmp_dir)
    report["exported"]["birdwatch.pdf"] = f"{page_no} gallery page(s)"


def export_lore(ex, out_dir, report):
    ex.render("/wings-of-time", os.path.join(out_dir, "wings-of-time.pdf"))
    report["exported"]["wings-of-time.pdf"] = "ok"
    print("  wings-of-time")


def export_nests(ex, out_dir, report, players):
    nests_dir = os.path.join(out_dir, "nests")
    os.makedirs(nests_dir, exist_ok=True)
    done = []
    for i, (uid, name) in enumerate(players, 1):
        dest = os.path.join(nests_dir, f"{slugify(name)}-{uid}.pdf")
        if os.path.exists(dest):  # resume an interrupted run into the same --out
            done.append(dest)
            report["exported"][f"nests/{os.path.basename(dest)}"] = name
            continue
        try:
            ex.render(f"/user/{uid}", dest)
            done.append(dest)
            report["exported"][f"nests/{os.path.basename(dest)}"] = name
            print(f"  [{i}/{len(players)}] {name}")
        except Exception as e:
            print(f"  ! [{i}/{len(players)}] {name}: FAILED ({e})")
            report["errors"].append(f"nest {uid}: {e}")
    if done:
        merge_pdfs(done, os.path.join(out_dir, "all-nests.pdf"))
        report["exported"]["all-nests.pdf"] = f"{len(done)} nests"


def main():
    parser = argparse.ArgumentParser(description="Export Bird RPG pages as PDFs.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Site to print (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--out", help="Output directory (default: exports/pdf-<timestamp>)")
    parser.add_argument("--backup", help="Backup folder with tables/players.json (default: newest backups/supabase-*)")
    parser.add_argument("--only", default="birdwatch,lore,nests", help="Comma list of: birdwatch, lore, nests")
    parser.add_argument("--users", help="Comma list of user IDs to export (default: every nest with birds or plants)")
    parser.add_argument("--include-empty", action="store_true", help="Also export nests with no birds or plants")
    args = parser.parse_args()
    # Nest names contain emoji; the Windows console default (cp1252) can't print them.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parts ={p.strip() for p in args.only.split(",") if p.strip()}
    players = []
    if "nests" in parts:
        backup_dir = args.backup or latest_backup_dir()
        if not backup_dir:
            print("Error: no backups/supabase-* folder found; run scripts/backup_supabase.py or pass --backup")
            sys.exit(1)
        only_ids = {u.strip() for u in args.users.split(",")} if args.users else None
        players = select_players(backup_dir, args.include_empty, only_ids)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out or os.path.join(PROJECT_ROOT, "exports", f"pdf-{stamp}")
    os.makedirs(out_dir, exist_ok=True)
    report = {"base_url": args.base_url, "created_at": stamp, "exported": {}, "missing_images": {}, "errors": []}
    print(f"Printing {args.base_url} to {out_dir}\n")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ex = Exporter(browser, args.base_url, report)
        steps = [("birdwatch", lambda: export_birdwatch(ex, out_dir, report)),
                 ("lore", lambda: export_lore(ex, out_dir, report)),
                 ("nests", lambda: export_nests(ex, out_dir, report, players))]
        for name, step in steps:
            if name not in parts:
                continue
            print(f"Exporting {name}...")
            try:
                step()
            except Exception as e:
                print(f"  ! {name}: FAILED ({e})")
                report["errors"].append(f"{name}: {e}")
        ex.close()
        browser.close()

    with open(os.path.join(out_dir, "export_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    missing = sum(len(v) for v in report["missing_images"].values())
    print(f"\nDone: {len(report['exported'])} PDF(s).")
    if missing:
        print(f"{missing} image(s) failed to load - see export_report.json.")
    if report["errors"]:
        print(f"{len(report['errors'])} error(s) - see export_report.json.")
        sys.exit(1)
    print("No errors.")


if __name__ == "__main__":
    main()
