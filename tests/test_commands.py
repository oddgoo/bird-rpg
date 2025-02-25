import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import discord
import asyncio

from commands.flock import FlockCommands
from commands.incubation import IncubationCommands
from data.models import (
    get_personal_nest, get_remaining_actions,
    record_actions, has_brooded_egg, record_brooding,
    get_egg_cost, get_total_chicks, select_random_bird_species,
    add_bonus_actions, load_bird_species
)
from utils.time_utils import get_current_date
from constants import BASE_DAILY_ACTIONS

@pytest.fixture
def mock_interaction():
    interaction = AsyncMock()
    interaction.user = AsyncMock()
    interaction.guild = AsyncMock()
    interaction.user.id = 123  # Default user ID
    interaction.user.display_name = "Test User"
    interaction.guild.members = []  # Initialize as an empty list
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()

    # Helper function to add a mock member
    def add_member(user_id, display_name=""):
        member = AsyncMock()
        member.id = user_id
        member.display_name = display_name or f"User-{user_id}"
        interaction.guild.members.append(member)
        return member

    interaction.add_member = add_member
    return interaction

@pytest.fixture
def mock_data():
    return {
        "personal_nests": {},
        "common_nest": {"twigs": 0, "seeds": 0},
        "daily_actions": {},
        "daily_songs": {},
        "daily_brooding": {},
        "memoirs": []
    }

@pytest.fixture
def flock_cog(mock_data):
    bot = AsyncMock()
    cog = FlockCommands(bot)
    cog.active_flocks = {}

    # Mock load_data and save_data to use mock_data
    def mock_load_data():
        return mock_data

    def mock_save_data(data):
        mock_data.update(data)

    with patch('commands.flock.load_data', mock_load_data), \
         patch('commands.flock.save_data', mock_save_data):
        yield cog

@pytest.fixture
def incubation_cog(mock_data, mock_interaction):
    bot = AsyncMock()
    cog = IncubationCommands(bot)

    # Mock load_data and save_data to use mock_data
    def mock_load_data():
        return mock_data

    def mock_save_data(data):
        mock_data.update(data)

    # Mock fetch_bird_image to return a fixed URL
    async def mock_fetch_bird_image(self, scientific_name):
        return "http://example.com/bird.jpg", "http://example.com/taxon"

    with patch('commands.incubation.load_data', mock_load_data), \
         patch('commands.incubation.save_data', mock_save_data), \
         patch.object(IncubationCommands, 'fetch_bird_image', mock_fetch_bird_image):
        yield cog


class TestIncubationCommands:
    @pytest.mark.asyncio
    async def test_lay_egg_success(self, incubation_cog, mock_interaction, mock_data):
        """Test laying an egg with sufficient seeds"""
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["seeds"] = get_egg_cost(nest)

        await incubation_cog.lay_egg.callback(incubation_cog, mock_interaction)

        # Check message
        mock_interaction.response.send_message.assert_called_once()
        assert "You laid an egg" in mock_interaction.response.send_message.call_args[0][0]

        # Check egg created
        assert nest["egg"] is not None
        assert nest["egg"]["brooding_progress"] == 0
        assert nest["egg"]["brooded_by"] == []
        
    @pytest.mark.asyncio
    async def test_lay_egg_with_less_brood_effect(self, incubation_cog, mock_interaction, mock_data, mocker):
        """Test laying an egg with plants that reduce brooding needed"""
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["seeds"] = get_egg_cost(nest) + 50  # Ensure enough seeds
        
        # Add plants with less brood effect
        nest["plants"] = [
            {"commonName": "Sturt's Desert Pea", "scientificName": "Swainsona formosa"},
            {"commonName": "Kangaroo Paw", "scientificName": "Anigozanthos flavidus"}
        ]
        
        # Mock get_less_brood_chance to return a fixed value (35%)
        mocker.patch('data.models.get_less_brood_chance', return_value=35)
        
        # Mock random.random to return 0.3 (below 0.35, so additional less brood should trigger)
        mocker.patch('random.random', return_value=0.3)
        
        await incubation_cog.lay_egg.callback(incubation_cog, mock_interaction)
        
        # Check message
        mock_interaction.response.send_message.assert_called_once()
        message = mock_interaction.response.send_message.call_args[0][0]
        assert "You laid an egg" in message
        assert "plants" in message.lower()  # Should mention plants
        
        # Check egg created with reduced brooding needed
        assert nest["egg"] is not None
        assert nest["egg"]["brooding_progress"] == 1  # Should start with 1 brood progress (35% chance = 0 guaranteed + 35% chance of 1)
        assert "The egg needs to be brooded 9 times" in message or "The egg needs to be brooded 9 more times" in message

    @pytest.mark.asyncio
    async def test_lay_egg_insufficient_seeds(self, incubation_cog, mock_interaction, mock_data):
        """Test laying an egg with insufficient seeds"""
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["seeds"] = get_egg_cost(nest) - 1

        await incubation_cog.lay_egg.callback(incubation_cog, mock_interaction)

        # Check message
        mock_interaction.response.send_message.assert_called_once()
        assert "You need" in mock_interaction.response.send_message.call_args[0][0]

        # Check no egg created
        assert nest["egg"] is None

    @pytest.mark.asyncio
    async def test_brood_success(self, incubation_cog, mock_interaction, mock_data):
        """Test brooding an egg successfully"""
        target_user = mock_interaction.add_member(456, "Target")
        target_nest = get_personal_nest(mock_data, target_user.id)
        # Create an egg for the target user
        target_nest["egg"] = {"brooding_progress": 0, "brooded_by": []}
        add_bonus_actions(mock_data, mock_interaction.user.id, BASE_DAILY_ACTIONS)

        # Mock the bot.fetch_user method to return our target_user
        incubation_cog.bot.fetch_user = AsyncMock(return_value=target_user)

        # Pass target_user as a mention string
        await incubation_cog.brood.callback(incubation_cog, mock_interaction, f"<@{target_user.id}>")

        # Check followup message
        mock_interaction.followup.send.assert_called()
        assert mock_interaction.followup.send.call_count == 1
        assert "You brooded at the following nests" in mock_interaction.followup.send.call_args[0][0]

        # Check the egg was brooded
        target_nest = get_personal_nest(mock_data, target_user.id)  # Refresh target_nest
        assert target_nest["egg"]["brooding_progress"] == 1
        assert str(mock_interaction.user.id) in target_nest["egg"]["brooded_by"]

    @pytest.mark.asyncio
    async def test_brood_no_egg(self, incubation_cog, mock_interaction, mock_data):
        """Test brooding when target has no egg"""
        target_user = mock_interaction.add_member(456, "Target")
        get_personal_nest(mock_data, target_user.id)
        add_bonus_actions(mock_data, mock_interaction.user.id, BASE_DAILY_ACTIONS)

        # Mock the bot.fetch_user method to return our target_user
        incubation_cog.bot.fetch_user = AsyncMock(return_value=target_user)

        # Pass target_user as a mention string
        await incubation_cog.brood.callback(incubation_cog, mock_interaction, f"<@{target_user.id}>")

        # Check message
        mock_interaction.followup.send.assert_called()
        assert mock_interaction.followup.send.call_count == 1
        assert "Couldn't brood for" in mock_interaction.followup.send.call_args[0][0]
        assert "doesn't have an egg to brood" in mock_interaction.followup.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_brood_no_actions(self, incubation_cog, mock_interaction, mock_data):
        """Test brooding with no actions remaining"""
        target_user = mock_interaction.add_member(456, "Target")
        target_nest = get_personal_nest(mock_data, target_user.id)
        target_nest["egg"] = {"brooding_progress": 0, "brooded_by": []}

        # Set up the user to have used all their actions
        current_date = get_current_date()
        if "daily_actions" not in mock_data:
            mock_data["daily_actions"] = {}
        mock_data["daily_actions"][str(mock_interaction.user.id)] = {
            f"actions_{current_date}": {
                "used": BASE_DAILY_ACTIONS,
                "bonus": 0
            }
        }

        # Pass target_user as a mention string
        await incubation_cog.brood.callback(incubation_cog, mock_interaction, f"<@{target_user.id}>")

        # Check message
        mock_interaction.followup.send.assert_called_once()
        assert "You've used all your actions for today" in mock_interaction.followup.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_pray_for_bird_success(self, incubation_cog, mock_interaction, mock_data):
        """Test praying for a bird successfully"""
        # Setup
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["egg"] = {
            "brooding_progress": 0,
            "brooded_by": []
        }
        add_bonus_actions(mock_data, mock_interaction.user.id, 5)  # Ensure enough actions

        # Mock bird_species to have a known bird
        test_bird = {"scientificName": "Test Bird", "rarityWeight": 10, "commonName": "Test Bird"}
        
        # Need to patch both the direct function call and the import
        with patch('commands.incubation.load_bird_species', return_value=[test_bird]), \
             patch('data.models.load_bird_species', return_value=[test_bird]):
            await incubation_cog.pray_for_bird.callback(
                incubation_cog,
                mock_interaction,
                "Test Bird",
                3
            )

        # Check message
        mock_interaction.response.send_message.assert_called_once()
        message = mock_interaction.response.send_message.call_args[0][0]
        assert "You offered 3 prayers for Test Bird" in message
        assert "multiplier is now 3x" in message
        
        # Check multiplier was added
        assert "multipliers" in nest["egg"]
        assert nest["egg"]["multipliers"]["Test Bird"] == 3

    @pytest.mark.asyncio
    async def test_pray_for_bird_no_egg(self, incubation_cog, mock_interaction, mock_data):
        """Test praying when user has no egg"""
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["egg"] = None
        add_bonus_actions(mock_data, mock_interaction.user.id, 5)

        test_bird = {"scientificName": "Test Bird", "rarityWeight": 10, "commonName": "Test Bird"}
        with patch('commands.incubation.load_bird_species', return_value=[test_bird]), \
             patch('data.models.load_bird_species', return_value=[test_bird]):
            await incubation_cog.pray_for_bird.callback(
                incubation_cog,
                mock_interaction,
                "Test Bird",
                1
            )

        # Check error message
        mock_interaction.response.send_message.assert_called_once()
        assert "don't have an egg to pray for" in mock_interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_pray_for_bird_cumulative(self, incubation_cog, mock_interaction, mock_data):
        """Test that multiple prayers stack correctly"""
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["egg"] = {
            "brooding_progress": 0,
            "brooded_by": [],
            "multipliers": {}  # Initialize multipliers
        }
        add_bonus_actions(mock_data, mock_interaction.user.id, 10)

        # Mock bird_species
        test_bird = {"scientificName": "Test Bird", "rarityWeight": 10, "commonName": "Test Bird"}
        with patch('commands.incubation.load_bird_species', return_value=[test_bird]), \
             patch('data.models.load_bird_species', return_value=[test_bird]):
            # Pray twice
            await incubation_cog.pray_for_bird.callback(
                incubation_cog,
                mock_interaction,
                "Test Bird",
                2
            )
            
            await incubation_cog.pray_for_bird.callback(
                incubation_cog,
                mock_interaction,
                "Test Bird",
                3
            )

        # Check final multiplier is sum of both prayers
        assert nest["egg"]["multipliers"]["Test Bird"] == 5
        

class TestFlockCommands:
    @pytest.mark.asyncio
    async def test_start_flock_success(self, flock_cog, mock_interaction, mock_data, mocker):
        """Test starting a flock session successfully"""
        # Mock asyncio.sleep to do nothing
        mocker.patch('asyncio.sleep', return_value=None)

        # Mock data module functions
        mocker.patch('data.models.get_personal_nest', return_value={
            'seeds': 0,
            'twigs': 0,
            'name': "Some Bird's Nest",
            'egg': None,
            'chicks': [],
            'garden_size': 0,
            'inspiration': 0,
            'bonus_actions': 0  # Add this field
        })
        mocker.patch('data.storage.load_data', return_value=mock_data)
        mocker.patch('data.storage.save_data')

        # Mock the user mention attribute
        mock_interaction.user.mention = f"<@{mock_interaction.user.id}>"

        await flock_cog.start_flock.callback(flock_cog, mock_interaction)

        # Check messages were sent
        assert mock_interaction.response.send_message.call_count == 1
        assert "has started a pomodoro flock" in mock_interaction.response.send_message.call_args[0][0]
        assert mock_interaction.followup.send.call_count == 1
        assert "The pomodoro flock has ended" in mock_interaction.followup.send.call_args[0][0]

        # Check flock creation and cleanup
        assert mock_interaction.user.id not in flock_cog.active_flocks  # Flock should be cleaned up after completion

    @pytest.mark.asyncio
    async def test_start_flock_when_active(self, flock_cog, mock_interaction, mock_data):
        """Test starting a flock when one is already active"""
        # Set up an existing flock
        flock_cog.active_flock = {
            'leader': mock_interaction.add_member(456, "Leader"),
            'members': [mock_interaction.user],
            'start_time': datetime.now(),
            'end_time': datetime.now() + timedelta(minutes=60)
        }

        await flock_cog.start_flock.callback(flock_cog, mock_interaction)

        # Check error message
        mock_interaction.response.send_message.assert_called_once()
        assert "already an active flock session" in mock_interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_join_flock_success(self, flock_cog, mock_interaction, mock_data):
        """Test joining an existing flock successfully"""
        mock_interaction.user.mention = f"<@{mock_interaction.user.id}>"
        
        leader = mock_interaction.add_member(456, "Leader")
        flock_cog.active_flock = {
            'leader': leader,
            'members': [leader],
            'start_time': datetime.now(),
            'end_time': datetime.now() + timedelta(minutes=60)
        }

        await flock_cog.join_flock.callback(flock_cog, mock_interaction)

        # Check message
        mock_interaction.response.send_message.assert_called_once()
        assert "has joined the flock" in mock_interaction.response.send_message.call_args[0][0]
        assert "minutes remaining" in mock_interaction.response.send_message.call_args[0][0]

        # Check member added
        assert mock_interaction.user in flock_cog.active_flock['members']

    @pytest.mark.asyncio
    async def test_join_flock_no_active(self, flock_cog, mock_interaction, mock_data):
        """Test joining when no flock is active"""
        flock_cog.active_flock = None
        await flock_cog.join_flock.callback(flock_cog, mock_interaction)

        # Check message
        mock_interaction.response.send_message.assert_called_once()
        assert "no active flock session" in mock_interaction.response.send_message.call_args[0][0]


class TestSeedCommands:
    @pytest.mark.asyncio
    async def test_add_seed_with_cockatoo_bonus(self, mock_interaction, mock_data):
        """Test adding seeds with cockatoo garden size bonus"""
        # Set up nest with a Gang-gang Cockatoo
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["twigs"] = 10
        nest["chicks"] = [{
            "commonName": "Gang-gang Cockatoo",
            "scientificName": "Callocephalon fimbriatum",
            "effect": "Your first seed gathering action of the day also gives +1 garden size"
        }]
        
        # Mock the command
        from commands.seeds import SeedCommands
        seed_cog = SeedCommands(AsyncMock())
        
        # Debug assertions before command
        print("\nBefore command:")
        print(f"daily_actions structure: {mock_data['daily_actions']}")
        print(f"nest structure: {nest}")
        
        # Add mock for load_data and save_data
        def mock_load_data():
            return mock_data

        def mock_save_data(data):
            mock_data.update(data)

        with patch('commands.seeds.load_data', mock_load_data), \
             patch('commands.seeds.save_data', mock_save_data):
            await seed_cog.add_seed_own.callback(seed_cog, mock_interaction, 1)

        # Check garden size was initialized and increased
        assert "garden_size" in nest
        assert nest["garden_size"] == 1
        assert nest["seeds"] == 1

    @pytest.mark.asyncio
    async def test_add_seed_with_multiple_cockatoos(self, mock_interaction, mock_data):
        """Test adding seeds with multiple cockatoos for garden size bonus"""
        # Set up nest with both cockatoo species
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["twigs"] = 10
        nest["chicks"] = [
            {
                "commonName": "Gang-gang Cockatoo",
                "scientificName": "Callocephalon fimbriatum",
                "effect": "Your first seed gathering action of the day also gives +1 garden size"
            },
            {
                "commonName": "Major Mitchell's Cockatoo",
                "scientificName": "Lophochroa leadbeateri",
                "effect": "Your first seed gathering action of the day also gives +1 garden size"
            }
        ]
        
        from commands.seeds import SeedCommands
        seed_cog = SeedCommands(AsyncMock())
        
        # Add mock for load_data and save_data
        def mock_load_data():
            return mock_data

        def mock_save_data(data):
            mock_data.update(data)

        with patch('commands.seeds.load_data', mock_load_data), \
             patch('commands.seeds.save_data', mock_save_data):
            await seed_cog.add_seed_own.callback(seed_cog, mock_interaction, 1)
        
        # Check garden size was increased by 2
        assert nest["garden_size"] == 2
        assert nest["seeds"] == 1
