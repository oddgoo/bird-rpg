import pytest
from unittest.mock import AsyncMock, patch

from utils.blessings import get_blessing_amount, apply_blessing


def test_blessing_amounts():
    """Test blessing amount calculation based on human difficulty"""
    # Test tier 0 (easy human)
    assert get_blessing_amount(25) == 10

    # Test tier 1 (medium human)
    assert get_blessing_amount(50) == 20

    # Test tier 2 (hard human)
    assert get_blessing_amount(100) == 30


@pytest.mark.asyncio
async def test_apply_blessing_seeds():
    """Test seeds blessing respects nest capacity"""
    mock_players = [
        {"user_id": "user1", "twigs": 100, "seeds": 0},
        {"user_id": "user2", "twigs": 50, "seeds": 30},  # 20 space left
        {"user_id": "user3", "twigs": 30, "seeds": 30},  # No space left
    ]

    with patch("utils.blessings.db.load_all_players", new_callable=AsyncMock) as mock_load:
        with patch("utils.blessings.db.increment_player_field", new_callable=AsyncMock) as mock_increment:
            mock_load.return_value = mock_players

            await apply_blessing("individual_seeds", 20)

            # Verify load was called
            mock_load.assert_called_once()

            # Verify increments were called correctly
            assert mock_increment.call_count == 2
            # user1: has 100 space, gets 20 seeds
            mock_increment.assert_any_call("user1", "seeds", 20)
            # user2: has 20 space, gets 20 seeds
            mock_increment.assert_any_call("user2", "seeds", 20)
            # user3: has 0 space, gets nothing (no call)


@pytest.mark.asyncio
async def test_apply_blessing_inspiration():
    """Test inspiration blessing applies to all players"""
    mock_players = [
        {"user_id": "user1", "inspiration": 0},
        {"user_id": "user2", "inspiration": 5},
    ]

    with patch("utils.blessings.db.load_all_players", new_callable=AsyncMock) as mock_load:
        with patch("utils.blessings.db.increment_player_field", new_callable=AsyncMock) as mock_increment:
            mock_load.return_value = mock_players

            await apply_blessing("inspiration", 10)

            mock_load.assert_called_once()
            assert mock_increment.call_count == 2
            mock_increment.assert_any_call("user1", "inspiration", 10)
            mock_increment.assert_any_call("user2", "inspiration", 10)


@pytest.mark.asyncio
async def test_apply_blessing_garden_growth():
    """Test garden growth blessing respects MAX_GARDEN_SIZE"""
    mock_players = [
        {"user_id": "user1", "garden_size": 0},
        {"user_id": "user2", "garden_size": 10},
        {"user_id": "user3", "garden_size": 44},  # 1 space left (MAX is 45)
    ]

    with patch("utils.blessings.db.load_all_players", new_callable=AsyncMock) as mock_load:
        with patch("utils.blessings.db.increment_player_field", new_callable=AsyncMock) as mock_increment:
            mock_load.return_value = mock_players

            await apply_blessing("garden_growth", 5)

            mock_load.assert_called_once()
            assert mock_increment.call_count == 3
            # user1: gets full 5
            mock_increment.assert_any_call("user1", "garden_size", 5)
            # user2: gets full 5
            mock_increment.assert_any_call("user2", "garden_size", 5)
            # user3: limited to 1 (MAX_GARDEN_SIZE - current)
            mock_increment.assert_any_call("user3", "garden_size", 1)


@pytest.mark.asyncio
async def test_apply_blessing_bonus_actions():
    """Test bonus actions blessing applies to all players"""
    mock_players = [
        {"user_id": "user1", "bonus_actions": 0},
        {"user_id": "user2", "bonus_actions": 3},
    ]

    with patch("utils.blessings.db.load_all_players", new_callable=AsyncMock) as mock_load:
        with patch("utils.blessings.db.increment_player_field", new_callable=AsyncMock) as mock_increment:
            mock_load.return_value = mock_players

            await apply_blessing("bonus_actions", 15)

            mock_load.assert_called_once()
            assert mock_increment.call_count == 2
            mock_increment.assert_any_call("user1", "bonus_actions", 15)
            mock_increment.assert_any_call("user2", "bonus_actions", 15)


@pytest.mark.asyncio
async def test_apply_blessing_nest_growth():
    """Test individual nest growth blessing applies to all players"""
    mock_players = [
        {"user_id": "user1", "twigs": 100},
        {"user_id": "user2", "twigs": 50},
    ]

    with patch("utils.blessings.db.load_all_players", new_callable=AsyncMock) as mock_load:
        with patch("utils.blessings.db.increment_player_field", new_callable=AsyncMock) as mock_increment:
            mock_load.return_value = mock_players

            await apply_blessing("individual_nest_growth", 25)

            mock_load.assert_called_once()
            assert mock_increment.call_count == 2
            mock_increment.assert_any_call("user1", "twigs", 25)
            mock_increment.assert_any_call("user2", "twigs", 25)
