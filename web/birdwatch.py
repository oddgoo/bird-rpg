from math import ceil
from flask import render_template, request
import data.storage as db


def get_birdwatch_page():
    """Render the birdwatch gallery page with paginated sightings."""
    page = request.args.get('page', 1, type=int)
    page = max(1, page)
    per_page = 12

    sightings, total_count = db.get_all_birdwatch_sightings_sync(page, per_page)
    total_pages = max(1, ceil(total_count / per_page))

    return render_template('birdwatch.html',
                           sightings=sightings,
                           page=page,
                           total_pages=total_pages,
                           total_count=total_count)
