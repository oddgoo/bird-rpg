from flask import render_template
from data.storage import load_data
from data.models import get_common_nest
from utils.time_utils import get_time_until_reset

def get_home_page():
    data = load_data()
    
    # Get common nest data
    common_nest = get_common_nest(data)
    
    # Get time until reset
    time_until_reset = get_time_until_reset()
    
    # Get all personal nests and sort them by total resources
    personal_nests = []
    for user_id in data["personal_nests"]:
        nest = data["personal_nests"][user_id]
        total_resources = nest["seeds"]
        space_available = nest["twigs"] - nest["seeds"]
        personal_nests.append({
            "user_id": user_id,
            "name": nest.get("name", "Unnamed Nest"),  # Use .get() with default value
            "twigs": nest["twigs"],
            "seeds": nest["seeds"],
            "total": total_resources,
            "space": space_available
        })
    
    # Sort nests by total resources, descending
    personal_nests.sort(key=lambda x: x["total"], reverse=True)
    
    return render_template(
        'home.html',
        common_nest=common_nest,
        personal_nests=personal_nests,
        time_until_reset=time_until_reset
    )
