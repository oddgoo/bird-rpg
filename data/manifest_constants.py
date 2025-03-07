# Manifestation points needed for each rarity
MANIFESTATION_POINTS = {
    "common": 40,
    "uncommon": 70,
    "rare": 110,
    "mythical": 160
}

def get_points_needed(rarity):
    """Get the number of points needed to fully manifest a species based on rarity"""
    return MANIFESTATION_POINTS.get(rarity.lower(), 100)
