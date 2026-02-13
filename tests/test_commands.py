"""
Tests for IncubationCommands and FlockCommands cogs.

All DB operations are mocked via AsyncMock / patch so no real Supabase
connection is needed.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from commands.flock import FlockCommands
from commands.incubation import IncubationCommands
from constants import BASE_DAILY_ACTIONS


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_interaction():
    interaction = AsyncMock()
    interaction.user = AsyncMock()
    interaction.guild = AsyncMock()
    interaction.user.id = 123
    interaction.user.display_name = "Test User"
    interaction.user.mention = "<@123>"
    interaction.guild.members = []
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.channel = AsyncMock()
    interaction.guild.get_member = MagicMock(return_value=None)
    interaction.guild.fetch_member = AsyncMock(return_value=None)

    def add_member(user_id, display_name=""):
        member = AsyncMock()
        member.id = user_id
        member.display_name = display_name or f"User-{user_id}"
        member.mention = f"<@{user_id}>"
        member.bot = False
        interaction.guild.members.append(member)
        return member

    interaction.add_member = add_member
    return interaction


# ---------------------------------------------------------------------------
# Incubation tests
# ---------------------------------------------------------------------------

class TestIncubationCommands:
    @pytest.mark.asyncio
    async def test_lay_egg_success(self, mock_interaction):
        """Test laying an egg with sufficient seeds."""
        bot = AsyncMock()
        cog = IncubationCommands(bot)

        player = {"user_id": "123", "seeds": 20, "twigs": 0, "inspiration": 0,
                   "garden_size": 0, "bonus_actions": 0, "locked": False,
                   "nest_name": "Test Nest"}

        with patch("commands.incubation.db.load_player", new=AsyncMock(return_value=player)), \
             patch("commands.incubation.db.get_egg", new=AsyncMock(return_value=None)), \
             patch("commands.incubation.db.get_player_plants", new=AsyncMock(return_value=[])), \
             patch("commands.incubation.db.increment_player_field", new=AsyncMock()), \
             patch("commands.incubation.db.create_egg", new=AsyncMock()), \
             patch("commands.incubation.get_less_brood_chance", new=AsyncMock(return_value=0)):

            await cog.lay_egg.callback(cog, mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "You laid an egg" in msg

    @pytest.mark.asyncio
    async def test_lay_egg_insufficient_seeds(self, mock_interaction):
        """Test laying an egg with insufficient seeds."""
        bot = AsyncMock()
        cog = IncubationCommands(bot)

        player = {"user_id": "123", "seeds": 5, "twigs": 0, "inspiration": 0,
                   "garden_size": 0, "bonus_actions": 0, "locked": False}

        with patch("commands.incubation.db.load_player", new=AsyncMock(return_value=player)), \
             patch("commands.incubation.db.get_egg", new=AsyncMock(return_value=None)):

            await cog.lay_egg.callback(cog, mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "You need" in msg

    @pytest.mark.asyncio
    async def test_lay_egg_already_has_egg(self, mock_interaction):
        """Test laying an egg when one already exists."""
        bot = AsyncMock()
        cog = IncubationCommands(bot)

        player = {"user_id": "123", "seeds": 100}
        existing_egg = {"user_id": "123", "brooding_progress": 3, "multipliers": {}, "brooded_by": []}

        with patch("commands.incubation.db.load_player", new=AsyncMock(return_value=player)), \
             patch("commands.incubation.db.get_egg", new=AsyncMock(return_value=existing_egg)):

            await cog.lay_egg.callback(cog, mock_interaction)

        msg = mock_interaction.followup.send.call_args[0][0]
        assert "already has an egg" in msg

    @pytest.mark.asyncio
    async def test_brood_success(self, mock_interaction):
        """Test brooding an egg successfully."""
        bot = AsyncMock()
        cog = IncubationCommands(bot)

        target_user = mock_interaction.add_member(456, "Target")
        target_player = {"user_id": "456", "nest_name": "Target Nest", "locked": False}
        target_egg = {"user_id": "456", "brooding_progress": 3, "multipliers": {}, "brooded_by": []}

        bot.fetch_user = AsyncMock(return_value=target_user)

        with patch("commands.incubation.get_remaining_actions", new=AsyncMock(return_value=5)), \
             patch("commands.incubation.record_actions", new=AsyncMock()), \
             patch("commands.incubation.db.load_player", new=AsyncMock(return_value=target_player)), \
             patch("commands.incubation.db.get_egg", new=AsyncMock(return_value=target_egg)), \
             patch("commands.incubation.db.has_brooded_today", new=AsyncMock(return_value=False)), \
             patch("commands.incubation.db.record_brooding", new=AsyncMock()), \
             patch("commands.incubation.db.update_egg", new=AsyncMock()), \
             patch("commands.incubation.db.add_egg_brooder", new=AsyncMock()):

            await cog.brood.callback(cog, mock_interaction, f"<@{target_user.id}>")

        mock_interaction.followup.send.assert_called()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "You brooded at the following nests" in msg

    @pytest.mark.asyncio
    async def test_brood_no_egg(self, mock_interaction):
        """Test brooding when target has no egg."""
        bot = AsyncMock()
        cog = IncubationCommands(bot)

        target_user = mock_interaction.add_member(456, "Target")
        target_player = {"user_id": "456", "nest_name": "Target Nest", "locked": False}

        bot.fetch_user = AsyncMock(return_value=target_user)

        with patch("commands.incubation.get_remaining_actions", new=AsyncMock(return_value=5)), \
             patch("commands.incubation.db.load_player", new=AsyncMock(return_value=target_player)), \
             patch("commands.incubation.db.get_egg", new=AsyncMock(return_value=None)):

            await cog.brood.callback(cog, mock_interaction, f"<@{target_user.id}>")

        mock_interaction.followup.send.assert_called()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "Couldn't brood for" in msg
        assert "doesn't have an egg to brood" in msg

    @pytest.mark.asyncio
    async def test_brood_no_actions(self, mock_interaction):
        """Test brooding with no actions remaining."""
        bot = AsyncMock()
        cog = IncubationCommands(bot)

        target_user = mock_interaction.add_member(456, "Target")
        bot.fetch_user = AsyncMock(return_value=target_user)

        with patch("commands.incubation.get_remaining_actions", new=AsyncMock(return_value=0)):
            await cog.brood.callback(cog, mock_interaction, f"<@{target_user.id}>")

        mock_interaction.followup.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "You've used all your actions for today" in msg

    @pytest.mark.asyncio
    async def test_brood_all_batches_prefetch_and_records_actions_once(self, mock_interaction):
        """brood_all should batch prefiltering and record actions once for all successes."""
        bot = AsyncMock()
        cog = IncubationCommands(bot)

        target_a = mock_interaction.add_member(456, "Target A")
        target_b = mock_interaction.add_member(789, "Target B")

        member_by_id = {
            456: target_a,
            789: target_b,
        }
        mock_interaction.guild.get_member = MagicMock(side_effect=lambda uid: member_by_id.get(uid))

        players = [
            {"user_id": "456", "nest_name": "A Nest", "locked": False},
            {"user_id": "789", "nest_name": "B Nest", "locked": False},
        ]
        eggs = {
            "456": {"user_id": "456", "brooding_progress": 3, "protected_prayers": False},
            "789": {"user_id": "789", "brooding_progress": 4, "protected_prayers": False},
        }

        mock_process = AsyncMock(side_effect=[
            (("progress", 6, "A Nest", target_a), None),
            (("progress", 5, "B Nest", target_b), None),
        ])
        mock_record_actions = AsyncMock()

        with patch("commands.incubation.get_remaining_actions", new=AsyncMock(return_value=5)), \
             patch("commands.incubation.get_extra_bird_space", new=AsyncMock(return_value=0)), \
             patch("commands.incubation.db.load_all_players", new=AsyncMock(return_value=players)), \
             patch("commands.incubation.db.get_eggs_for_users", new=AsyncMock(return_value=eggs)), \
             patch("commands.incubation.db.get_bird_counts_for_users", new=AsyncMock(return_value={"456": 2, "789": 3})), \
             patch("commands.incubation.db.get_brooded_targets_today", new=AsyncMock(return_value=set())), \
             patch.object(cog, "process_brooding", new=mock_process), \
             patch("commands.incubation.record_actions", new=mock_record_actions):

            await cog.brood_all.callback(cog, mock_interaction)

        mock_record_actions.assert_called_once_with(mock_interaction.user.id, 2, "brood")
        assert mock_process.call_count == 2

        first_kwargs = mock_process.call_args_list[0].kwargs
        assert first_kwargs["prefetched_player"]["user_id"] == "456"
        assert first_kwargs["prefetched_egg"]["user_id"] == "456"
        assert first_kwargs["max_birds"] > 0

    @pytest.mark.asyncio
    async def test_brood_stuck_egg_recovery(self, mock_interaction):
        """Test that an egg stuck at progress >= 10 hatches without incrementing."""
        bot = AsyncMock()
        cog = IncubationCommands(bot)

        target_user = mock_interaction.add_member(456, "Target")
        target_player = {"user_id": "456", "nest_name": "Target Nest", "locked": False}
        # Egg is stuck at progress 10 (previously incremented but not hatched)
        stuck_egg = {"user_id": "456", "brooding_progress": 10, "multipliers": {}, "brooded_by": []}
        test_bird = {"commonName": "Robin", "scientificName": "Turdus migratorius", "rarityWeight": 10}

        bot.fetch_user = AsyncMock(return_value=target_user)

        mock_record_brooding = AsyncMock()
        mock_update_egg = AsyncMock()
        mock_delete_egg = AsyncMock()

        with patch("commands.incubation.get_remaining_actions", new=AsyncMock(return_value=5)), \
             patch("commands.incubation.record_actions", new=AsyncMock()), \
             patch("commands.incubation.db.load_player", new=AsyncMock(return_value=target_player)), \
             patch("commands.incubation.db.get_egg", new=AsyncMock(return_value=stuck_egg)), \
             patch("commands.incubation.db.has_brooded_today", new=AsyncMock(return_value=False)), \
             patch("commands.incubation.db.record_brooding", new=mock_record_brooding), \
             patch("commands.incubation.db.update_egg", new=mock_update_egg), \
             patch("commands.incubation.db.add_egg_brooder", new=AsyncMock()), \
             patch("commands.incubation.get_extra_bird_space", new=AsyncMock(return_value=0)), \
             patch("commands.incubation.select_random_bird_species", new=AsyncMock(return_value=test_bird)), \
             patch("commands.incubation.db.add_bird", new=AsyncMock()), \
             patch("commands.incubation.db.get_player_plants", new=AsyncMock(return_value=[])), \
             patch("commands.incubation.get_extra_bird_chance", new=AsyncMock(return_value=0)), \
             patch("commands.incubation.handle_blessed_egg_hatching", return_value=None), \
             patch("commands.incubation.db.delete_egg", new=mock_delete_egg), \
             patch("commands.incubation.db.get_player_birds", new=AsyncMock(return_value=[{"id": 1}])):

            await cog.brood.callback(cog, mock_interaction, f"<@{target_user.id}>")

        # Should NOT have incremented brooding or recorded brooding (stuck recovery path)
        mock_record_brooding.assert_not_called()
        mock_update_egg.assert_not_called()
        # Egg should have been deleted (hatched)
        mock_delete_egg.assert_called_once()

    @pytest.mark.asyncio
    async def test_brood_full_nest_blocks_without_incrementing(self, mock_interaction):
        """Test that brooding at progress 9 with a full nest blocks WITHOUT incrementing progress."""
        bot = AsyncMock()
        cog = IncubationCommands(bot)

        target_user = mock_interaction.add_member(456, "Target")
        target_player = {"user_id": "456", "nest_name": "Target Nest", "locked": False}
        target_egg = {"user_id": "456", "brooding_progress": 9, "multipliers": {}, "brooded_by": []}

        bot.fetch_user = AsyncMock(return_value=target_user)

        # Nest is at max capacity (45 birds, 0 extra space)
        many_birds = [{"id": i} for i in range(45)]
        mock_update_egg = AsyncMock()
        mock_record_brooding = AsyncMock()

        with patch("commands.incubation.get_remaining_actions", new=AsyncMock(return_value=5)), \
             patch("commands.incubation.record_actions", new=AsyncMock()), \
             patch("commands.incubation.db.load_player", new=AsyncMock(return_value=target_player)), \
             patch("commands.incubation.db.get_egg", new=AsyncMock(return_value=target_egg)), \
             patch("commands.incubation.db.has_brooded_today", new=AsyncMock(return_value=False)), \
             patch("commands.incubation.db.record_brooding", new=mock_record_brooding), \
             patch("commands.incubation.db.update_egg", new=mock_update_egg), \
             patch("commands.incubation.get_extra_bird_space", new=AsyncMock(return_value=0)), \
             patch("commands.incubation.db.get_player_birds", new=AsyncMock(return_value=many_birds)):

            await cog.brood.callback(cog, mock_interaction, f"<@{target_user.id}>")

        # Should NOT have incremented — egg stays at 9
        mock_update_egg.assert_not_called()
        mock_record_brooding.assert_not_called()

        # Should report the error
        mock_interaction.followup.send.assert_called()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "maximum" in msg.lower() or "free a spot" in msg.lower()

    @pytest.mark.asyncio
    async def test_pray_for_bird_success(self, mock_interaction):
        """Test praying for a bird successfully."""
        bot = AsyncMock()
        cog = IncubationCommands(bot)

        egg = {"user_id": "123", "brooding_progress": 0, "multipliers": {}, "brooded_by": []}
        test_bird = {"scientificName": "Test Bird", "rarityWeight": 10, "commonName": "Test Bird"}

        with patch("commands.incubation.db.get_egg", new=AsyncMock(return_value=egg)), \
             patch("commands.incubation.get_remaining_actions", new=AsyncMock(return_value=10)), \
             patch("commands.incubation.load_bird_species", new=AsyncMock(return_value=[test_bird])), \
             patch("commands.incubation.record_actions", new=AsyncMock()), \
             patch("commands.incubation.db.upsert_egg_multiplier", new=AsyncMock()), \
             patch("commands.incubation.get_prayer_effectiveness_bonus", new=AsyncMock(return_value=1.0)):

            await cog.pray_for_bird.callback(cog, mock_interaction, "Test Bird", 3)

        mock_interaction.followup.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "You offered 3 prayers for Test Bird" in msg

    @pytest.mark.asyncio
    async def test_pray_for_bird_no_egg(self, mock_interaction):
        """Test praying when user has no egg."""
        bot = AsyncMock()
        cog = IncubationCommands(bot)

        with patch("commands.incubation.db.get_egg", new=AsyncMock(return_value=None)):
            await cog.pray_for_bird.callback(cog, mock_interaction, "Test Bird", 1)

        mock_interaction.followup.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "don't have an egg to pray for" in msg

    @pytest.mark.asyncio
    async def test_pray_for_bird_cumulative(self, mock_interaction):
        """Test that multiple prayers stack correctly."""
        bot = AsyncMock()
        cog = IncubationCommands(bot)

        egg = {"user_id": "123", "brooding_progress": 0, "multipliers": {}, "brooded_by": []}
        test_bird = {"scientificName": "Test Bird", "rarityWeight": 10, "commonName": "Test Bird"}

        upsert_calls = []
        async def track_upsert(uid, sn, mult):
            upsert_calls.append((uid, sn, mult))

        with patch("commands.incubation.db.get_egg", new=AsyncMock(return_value=egg)), \
             patch("commands.incubation.get_remaining_actions", new=AsyncMock(return_value=20)), \
             patch("commands.incubation.load_bird_species", new=AsyncMock(return_value=[test_bird])), \
             patch("commands.incubation.record_actions", new=AsyncMock()), \
             patch("commands.incubation.db.upsert_egg_multiplier", new=track_upsert), \
             patch("commands.incubation.get_prayer_effectiveness_bonus", new=AsyncMock(return_value=1.0)):

            # First prayer: 2 actions
            await cog.pray_for_bird.callback(cog, mock_interaction, "Test Bird", 2)

            # Simulate updated egg with multiplier from first prayer
            egg_after = {"user_id": "123", "brooding_progress": 0,
                         "multipliers": {"Test Bird": 2.0}, "brooded_by": []}
            with patch("commands.incubation.db.get_egg", new=AsyncMock(return_value=egg_after)):
                # Second prayer: 3 more actions
                await cog.pray_for_bird.callback(cog, mock_interaction, "Test Bird", 3)

        # The second call should have a multiplier of 2+3 = 5
        assert len(upsert_calls) == 2
        assert upsert_calls[0][2] == 2.0   # first: 0 + 2
        assert upsert_calls[1][2] == 5.0   # second: 2 + 3


# ---------------------------------------------------------------------------
# Flock tests
# ---------------------------------------------------------------------------

class TestFlockCommands:
    @pytest.mark.asyncio
    async def test_start_flock_success(self, mock_interaction, mocker):
        """Test starting a flock session successfully."""
        bot = AsyncMock()
        cog = FlockCommands(bot)

        mocker.patch('asyncio.sleep', return_value=None)

        with patch("commands.flock.db.load_player", new=AsyncMock(return_value={
            "user_id": "123", "garden_size": 0, "bonus_actions": 0,
        })), \
             patch("commands.flock.db.increment_player_field", new=AsyncMock()), \
             patch("commands.flock.add_bonus_actions", new=AsyncMock()), \
             patch("commands.flock.get_extra_garden_space", new=AsyncMock(return_value=0)):

            await cog.start_flock.callback(cog, mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "has started a pomodoro flock" in msg

        # The channel.send (follow-up at end of flock) should also be called
        mock_interaction.channel.send.assert_called_once()
        end_msg = mock_interaction.channel.send.call_args[0][0]
        assert "The pomodoro flock has ended" in end_msg

        # Flock should be cleaned up
        assert cog.active_flock is None

    @pytest.mark.asyncio
    async def test_start_flock_when_active(self, mock_interaction):
        """Test starting a flock when one is already active."""
        bot = AsyncMock()
        cog = FlockCommands(bot)

        cog.active_flock = {
            'leader': mock_interaction.add_member(456, "Leader"),
            'members': [mock_interaction.user],
            'start_time': datetime.now(),
            'end_time': datetime.now() + timedelta(minutes=60),
            'channel': mock_interaction.channel,
        }

        await cog.start_flock.callback(cog, mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "already an active flock session" in msg

    @pytest.mark.asyncio
    async def test_join_flock_success(self, mock_interaction):
        """Test joining an existing flock successfully."""
        bot = AsyncMock()
        cog = FlockCommands(bot)

        leader = mock_interaction.add_member(456, "Leader")
        cog.active_flock = {
            'leader': leader,
            'members': [leader],
            'start_time': datetime.now(),
            'end_time': datetime.now() + timedelta(minutes=60),
            'channel': mock_interaction.channel,
        }

        await cog.join_flock.callback(cog, mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "has joined the flock" in msg
        assert "minutes remaining" in msg
        assert mock_interaction.user in cog.active_flock['members']

    @pytest.mark.asyncio
    async def test_join_flock_no_active(self, mock_interaction):
        """Test joining when no flock is active."""
        bot = AsyncMock()
        cog = FlockCommands(bot)
        cog.active_flock = None

        await cog.join_flock.callback(cog, mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        msg = mock_interaction.followup.send.call_args[0][0]
        assert "no active flock session" in msg


# ---------------------------------------------------------------------------
# Pure logic tests for egg cost
# ---------------------------------------------------------------------------

class TestEggCost:
    def test_egg_cost_is_constant(self):
        """get_egg_cost always returns 20 regardless of player state."""
        from data.models import get_egg_cost
        assert get_egg_cost({}) == 20
        assert get_egg_cost({"seeds": 999, "twigs": 999}) == 20

    def test_handle_blessed_egg_no_protection(self):
        """Non-blessed egg returns None from handle_blessed_egg_hatching."""
        from data.models import handle_blessed_egg_hatching
        egg = {"protected_prayers": False, "multipliers": {"Bird A": 5}}
        result = handle_blessed_egg_hatching(egg, "Bird A")
        assert result is None

    def test_handle_blessed_egg_most_prayed_hatches(self):
        """Blessed egg returns None if the most-prayed bird hatches."""
        from data.models import handle_blessed_egg_hatching
        egg = {"protected_prayers": True, "multipliers": {"Bird A": 5, "Bird B": 2}}
        result = handle_blessed_egg_hatching(egg, "Bird A")
        assert result is None

    def test_handle_blessed_egg_different_bird_hatches(self):
        """Blessed egg returns multipliers if a different bird hatches."""
        from data.models import handle_blessed_egg_hatching
        egg = {"protected_prayers": True, "multipliers": {"Bird A": 5, "Bird B": 2}}
        result = handle_blessed_egg_hatching(egg, "Bird B")
        assert result == {"Bird A": 5, "Bird B": 2}
