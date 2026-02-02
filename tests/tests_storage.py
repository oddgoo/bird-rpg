"""
Tests for data.storage async DB operations.

All Supabase client calls are mocked so no real database is needed.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helper: build a fake Supabase client whose chained methods return controlled data
# ---------------------------------------------------------------------------

def _make_mock_client(select_data=None):
    """
    Return a MagicMock that mimics the Supabase chaining API:
        sb.table("x").select("*").eq(...).execute()  -> APIResponse(data=select_data)
    Also supports insert / update / upsert / delete / rpc chains.
    """
    client = MagicMock()
    response = MagicMock()
    response.data = select_data if select_data is not None else []

    # Every chained method returns itself so .eq().limit().execute() works
    chain = MagicMock()
    chain.execute.return_value = response
    chain.eq.return_value = chain
    chain.ilike.return_value = chain
    chain.lt.return_value = chain
    chain.limit.return_value = chain
    chain.order.return_value = chain
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.upsert.return_value = chain
    chain.delete.return_value = chain

    client.table.return_value = chain
    client.rpc.return_value = chain
    return client


# ---------------------------------------------------------------------------
# Tests for load_player
# ---------------------------------------------------------------------------

class TestLoadPlayer:
    @pytest.mark.asyncio
    async def test_load_existing_player(self):
        """load_player returns the existing row when the player is found."""
        player_row = {
            "user_id": "123",
            "nest_name": "Cool Nest",
            "twigs": 10,
            "seeds": 5,
            "inspiration": 2,
            "garden_size": 3,
            "bonus_actions": 0,
            "locked": False,
            "featured_bird_common_name": None,
            "featured_bird_scientific_name": None,
        }
        mock_client = _make_mock_client(select_data=[player_row])

        with patch("data.storage._client", new_callable=lambda: lambda: AsyncMock(return_value=mock_client)):
            with patch("data.storage._client", return_value=mock_client):
                from data.storage import load_player
                # Patch _client to be an async func returning our mock
                async def fake_client():
                    return mock_client
                with patch("data.storage._client", fake_client):
                    result = await load_player("123")

        assert result == player_row
        assert result["twigs"] == 10

    @pytest.mark.asyncio
    async def test_load_player_creates_new(self):
        """load_player auto-creates a player when none exists."""
        # First call to select returns empty, meaning player doesn't exist
        client = MagicMock()
        empty_response = MagicMock()
        empty_response.data = []

        insert_response = MagicMock()
        insert_response.data = [{"user_id": "999"}]

        chain = MagicMock()
        chain.execute.return_value = empty_response
        chain.eq.return_value = chain
        chain.select.return_value = chain
        chain.insert.return_value = chain

        client.table.return_value = chain

        async def fake_client():
            return client

        with patch("data.storage._client", fake_client):
            from data.storage import load_player
            result = await load_player("999")

        # Should return the default nest values
        assert result["user_id"] == "999"
        assert result["twigs"] == 0
        assert result["seeds"] == 0
        # insert should have been called
        chain.insert.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for update_player
# ---------------------------------------------------------------------------

class TestUpdatePlayer:
    @pytest.mark.asyncio
    async def test_update_player_fields(self):
        """update_player sends an update with the given fields."""
        mock_client = _make_mock_client()

        async def fake_client():
            return mock_client

        with patch("data.storage._client", fake_client):
            from data.storage import update_player
            await update_player("123", twigs=50, seeds=30)

        mock_client.table.assert_called_with("players")
        mock_client.table().update.assert_called_once_with({"twigs": 50, "seeds": 30})


# ---------------------------------------------------------------------------
# Tests for increment_player_field
# ---------------------------------------------------------------------------

class TestIncrementPlayerField:
    @pytest.mark.asyncio
    async def test_increment_player_field_calls_rpc(self):
        """increment_player_field calls the RPC with correct params."""
        mock_client = _make_mock_client()

        async def fake_client():
            return mock_client

        with patch("data.storage._client", fake_client):
            from data.storage import increment_player_field
            await increment_player_field("123", "twigs", 5)

        mock_client.rpc.assert_called_once_with("increment_player_field", {
            "p_user_id": "123",
            "field_name": "twigs",
            "amount": 5,
        })


# ---------------------------------------------------------------------------
# Tests for load_all_players
# ---------------------------------------------------------------------------

class TestLoadAllPlayers:
    @pytest.mark.asyncio
    async def test_load_all_players(self):
        """load_all_players returns all rows."""
        rows = [
            {"user_id": "1", "twigs": 1},
            {"user_id": "2", "twigs": 2},
        ]
        mock_client = _make_mock_client(select_data=rows)

        async def fake_client():
            return mock_client

        with patch("data.storage._client", fake_client):
            from data.storage import load_all_players
            result = await load_all_players()

        assert len(result) == 2
        assert result[0]["user_id"] == "1"

    @pytest.mark.asyncio
    async def test_load_all_players_empty(self):
        """load_all_players returns empty list when no players."""
        mock_client = _make_mock_client(select_data=[])

        async def fake_client():
            return mock_client

        with patch("data.storage._client", fake_client):
            from data.storage import load_all_players
            result = await load_all_players()

        assert result == []


# ---------------------------------------------------------------------------
# Tests for bird operations
# ---------------------------------------------------------------------------

class TestPlayerBirds:
    @pytest.mark.asyncio
    async def test_get_player_birds(self):
        """get_player_birds returns list of bird dicts."""
        birds = [
            {"id": 1, "user_id": "123", "common_name": "Emu", "scientific_name": "Dromaius novaehollandiae"},
        ]
        mock_client = _make_mock_client(select_data=birds)

        async def fake_client():
            return mock_client

        with patch("data.storage._client", fake_client):
            from data.storage import get_player_birds
            result = await get_player_birds("123")

        assert len(result) == 1
        assert result[0]["common_name"] == "Emu"

    @pytest.mark.asyncio
    async def test_add_bird(self):
        """add_bird inserts a bird row."""
        inserted = [{"id": 1, "user_id": "123", "common_name": "Kookaburra", "scientific_name": "Dacelo novaeguineae"}]
        mock_client = _make_mock_client(select_data=inserted)

        async def fake_client():
            return mock_client

        with patch("data.storage._client", fake_client):
            from data.storage import add_bird
            result = await add_bird("123", "Kookaburra", "Dacelo novaeguineae")

        mock_client.table.assert_called_with("player_birds")
        mock_client.table().insert.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for manifested birds
# ---------------------------------------------------------------------------

class TestManifestedBirds:
    @pytest.mark.asyncio
    async def test_load_manifested_birds(self):
        """load_manifested_birds returns all rows."""
        birds = [
            {"scientific_name": "Testus birdus", "common_name": "Test Bird", "fully_manifested": True},
        ]
        mock_client = _make_mock_client(select_data=birds)

        async def fake_client():
            return mock_client

        with patch("data.storage._client", fake_client):
            from data.storage import load_manifested_birds
            result = await load_manifested_birds()

        assert len(result) == 1
        assert result[0]["scientific_name"] == "Testus birdus"

    @pytest.mark.asyncio
    async def test_upsert_manifested_bird(self):
        """upsert_manifested_bird sends upsert with on_conflict."""
        mock_client = _make_mock_client()

        async def fake_client():
            return mock_client

        bird_data = {
            "scientific_name": "Casuarius casuarius",
            "common_name": "Southern Cassowary",
            "fully_manifested": False,
            "manifested_points": 10,
        }

        with patch("data.storage._client", fake_client):
            from data.storage import upsert_manifested_bird
            await upsert_manifested_bird(bird_data)

        mock_client.table.assert_called_with("manifested_birds")
        mock_client.table().upsert.assert_called_once_with(bird_data, on_conflict="scientific_name")


# ---------------------------------------------------------------------------
# Tests for egg operations
# ---------------------------------------------------------------------------

class TestEggOperations:
    @pytest.mark.asyncio
    async def test_get_egg_returns_none_when_no_egg(self):
        """get_egg returns None when user has no egg."""
        mock_client = _make_mock_client(select_data=[])

        async def fake_client():
            return mock_client

        with patch("data.storage._client", fake_client):
            from data.storage import get_egg
            result = await get_egg("123")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_egg(self):
        """create_egg upserts an egg row."""
        mock_client = _make_mock_client()

        async def fake_client():
            return mock_client

        with patch("data.storage._client", fake_client):
            from data.storage import create_egg
            await create_egg("123", brooding_progress=0, protected_prayers=False)

        mock_client.table.assert_called_with("eggs")
        mock_client.table().upsert.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for daily actions
# ---------------------------------------------------------------------------

class TestDailyActions:
    @pytest.mark.asyncio
    async def test_get_daily_actions_returns_none(self):
        """get_daily_actions returns None when no record for date."""
        mock_client = _make_mock_client(select_data=[])

        async def fake_client():
            return mock_client

        with patch("data.storage._client", fake_client):
            from data.storage import get_daily_actions
            result = await get_daily_actions("123", "2025-01-01")

        assert result is None

    @pytest.mark.asyncio
    async def test_upsert_daily_actions(self):
        """upsert_daily_actions sends upsert with correct data."""
        mock_client = _make_mock_client()

        async def fake_client():
            return mock_client

        with patch("data.storage._client", fake_client):
            from data.storage import upsert_daily_actions
            await upsert_daily_actions("123", "2025-01-01", 3, ["build", "build", "seed"])

        mock_client.table.assert_called_with("daily_actions")
        mock_client.table().upsert.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for common nest
# ---------------------------------------------------------------------------

class TestCommonNest:
    @pytest.mark.asyncio
    async def test_load_common_nest_existing(self):
        """load_common_nest returns existing row."""
        row = {"id": 1, "twigs": 50, "seeds": 30}
        mock_client = _make_mock_client(select_data=[row])

        async def fake_client():
            return mock_client

        with patch("data.storage._client", fake_client):
            from data.storage import load_common_nest
            result = await load_common_nest()

        assert result["twigs"] == 50

    @pytest.mark.asyncio
    async def test_increment_common_nest(self):
        """increment_common_nest calls rpc."""
        mock_client = _make_mock_client()

        async def fake_client():
            return mock_client

        with patch("data.storage._client", fake_client):
            from data.storage import increment_common_nest
            await increment_common_nest("twigs", 10)

        mock_client.rpc.assert_called_once_with("increment_common_nest", {"field_name": "twigs", "amount": 10})


# ---------------------------------------------------------------------------
# Tests for reference data loader
# ---------------------------------------------------------------------------

class TestReferenceData:
    def test_load_research_entities(self, tmp_path):
        """load_research_entities reads local JSON file."""
        import json
        test_data = [{"author": "Test Author", "milestones": ["+1 Max Garden Size"]}]
        entities_file = tmp_path / "research_entities.json"
        entities_file.write_text(json.dumps(test_data))

        with patch("data.storage.os.path.join", return_value=str(entities_file)):
            with patch("data.storage.os.path.exists", return_value=True):
                from data.storage import load_research_entities
                result = load_research_entities()

        assert len(result) == 1
        assert result[0]["author"] == "Test Author"
