import pytest
from datetime import date, timedelta

from utils.human_spawner import HumanSpawner
from utils.blessings import get_blessing_amount, apply_blessing



def test_blessing_amounts():
    # Test tier 0 (easy human)
    assert get_blessing_amount(25) == 10

    # Test tier 1 (medium human)
    assert get_blessing_amount(50) == 20

    # Test tier 2 (hard human)
    assert get_blessing_amount(100) == 30

def test_apply_blessing_to_nests():
    # Setup test nests
    nests = {
        "user1": {
            "twigs": 100,
            "seeds": 0,
            "inspiration": 0,
            "garden_size": 0,
            "bonus_actions": 0
        },
        "user2": {
            "twigs": 50,  # Limited capacity
            "seeds": 30,
            "inspiration": 5,
            "garden_size": 1,
            "bonus_actions": 3
        }
    }

    # Test seeds blessing
    updated_nests = apply_blessing(nests, "individual_seeds", 20)
    assert updated_nests["user1"]["seeds"] == 20  # Plenty of space
    assert updated_nests["user2"]["seeds"] == 50  # Limited by twigs capacity

    # Test inspiration blessing
    updated_nests = apply_blessing(nests, "inspiration", 10)
    assert updated_nests["user1"]["inspiration"] == 10
    assert updated_nests["user2"]["inspiration"] == 15

    # Test garden blessing
    updated_nests = apply_blessing(nests, "garden_growth", 5)
    assert updated_nests["user1"]["garden_size"] == 5
    assert updated_nests["user2"]["garden_size"] == 6

    # Test bonus actions blessing
    updated_nests = apply_blessing(nests, "bonus_actions", 15)
    assert updated_nests["user1"]["bonus_actions"] == 15
    assert updated_nests["user2"]["bonus_actions"] == 18

    # Test individual nest growth blessing
    updated_nests = apply_blessing(nests, "individual_nest_growth", 25)
    assert updated_nests["user1"]["twigs"] == 125  # 100 + 25
    assert updated_nests["user2"]["twigs"] == 75   # 50 + 25

    # Verify original nests weren't modified
    assert nests["user1"]["seeds"] == 0
    assert nests["user1"]["twigs"] == 100
    assert nests["user1"]["bonus_actions"] == 0
    assert nests["user2"]["bonus_actions"] == 3