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
    add_bonus_actions
)
from utils.time_utils import get_current_date
from constants import BASE_DAILY_ACTIONS

@pytest.fixture
def mock_ctx():
    ctx = AsyncMock()
    ctx.author = AsyncMock()
    ctx.guild = AsyncMock()
    ctx.author.id = 123  # Default author ID
    ctx.author.display_name = "Test User"
    ctx.guild.members = []  # Initialize as an empty list

    # Helper function to add a mock member
    def add_member(user_id, display_name=""):
        member = AsyncMock()
        member.id = user_id
        member.display_name = display_name or f"User-{user_id}"
        ctx.guild.members.append(member)
        return member

    ctx.add_member = add_member
    return ctx

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
def incubation_cog(mock_data, mock_ctx):
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
    async def test_lay_egg_success(self, incubation_cog, mock_ctx, mock_data):
        """Test laying an egg with sufficient seeds"""
        # Mock the command context
        mock_ctx.command = MagicMock()
        mock_ctx.command.name = "lay_egg"
        
        nest = get_personal_nest(mock_data, mock_ctx.author.id)
        nest["seeds"] = get_egg_cost(nest)

        await incubation_cog.lay_egg.callback(incubation_cog, mock_ctx)

        # Check message
        mock_ctx.send.assert_called_once()
        assert "You laid an egg" in mock_ctx.send.call_args[0][0]

        # Check egg created
        assert nest["egg"] is not None
        assert nest["egg"]["brooding_progress"] == 0
        assert nest["egg"]["brooded_by"] == []

    @pytest.mark.asyncio
    async def test_lay_egg_insufficient_seeds(self, incubation_cog, mock_ctx, mock_data):
        """Test laying an egg with insufficient seeds"""
        # Mock the command context
        mock_ctx.command = MagicMock()
        mock_ctx.command.name = "lay_egg"
        
        nest = get_personal_nest(mock_data, mock_ctx.author.id)
        nest["seeds"] = get_egg_cost(nest) - 1

        await incubation_cog.lay_egg.callback(incubation_cog, mock_ctx)

        # Check message
        mock_ctx.send.assert_called_once()
        assert "You need" in mock_ctx.send.call_args[0][0]

        # Check no egg created
        assert nest["egg"] is None

    @pytest.mark.asyncio
    async def test_brood_success(self, incubation_cog, mock_ctx, mock_data):
        """Test brooding an egg successfully"""
        # Mock the command context
        mock_ctx.command = MagicMock()
        mock_ctx.command.name = "brood"
        
        target_user = mock_ctx.add_member(456, "Target")
        target_nest = get_personal_nest(mock_data, target_user.id)
        target_nest["egg"] = {"brooding_progress": 0, "brooded_by": []}
        add_bonus_actions(mock_data, mock_ctx.author.id, BASE_DAILY_ACTIONS)

        await incubation_cog.brood.callback(incubation_cog, mock_ctx, target_user)

        # Check message
        assert mock_ctx.send.call_count == 2
        assert "You brooded at" in mock_ctx.send.call_args_list[0][0][0]

        # Check brooding recorded
        assert target_nest["egg"]["brooding_progress"] == 1
        assert str(mock_ctx.author.id) in target_nest["egg"]["brooded_by"]

    @pytest.mark.asyncio
    async def test_brood_no_egg(self, incubation_cog, mock_ctx, mock_data):
        """Test brooding when target has no egg"""
        # Mock the command context
        mock_ctx.command = MagicMock()
        mock_ctx.command.name = "brood"
        
        target_user = mock_ctx.add_member(456, "Target")
        get_personal_nest(mock_data, target_user.id)
        add_bonus_actions(mock_data, mock_ctx.author.id, BASE_DAILY_ACTIONS)

        await incubation_cog.brood.callback(incubation_cog, mock_ctx, target_user)

        # Check message
        assert mock_ctx.send.call_count == 2
        assert "doesn`t have an egg to brood" in mock_ctx.send.call_args_list[0][0][0]

    @pytest.mark.asyncio
    async def test_brood_already_brooded(self, incubation_cog, mock_ctx, mock_data):
        """Test brooding when already brooded today"""
        # Mock the command context
        mock_ctx.command = MagicMock()
        mock_ctx.command.name = "brood"
        
        target_user = mock_ctx.add_member(456, "Target")
        target_nest = get_personal_nest(mock_data, target_user.id)
        target_nest["egg"] = {"brooding_progress": 0, "brooded_by": []}
        add_bonus_actions(mock_data, mock_ctx.author.id, BASE_DAILY_ACTIONS)
        record_brooding(mock_data, mock_ctx.author.id, target_user.id)

        await incubation_cog.brood.callback(incubation_cog, mock_ctx, target_user)

        # Check message
        assert mock_ctx.send.call_count == 2
        assert "Already brooded at" in mock_ctx.send.call_args_list[0][0][0]

    @pytest.mark.asyncio
    async def test_brood_no_actions(self, incubation_cog, mock_ctx, mock_data):
        """Test brooding with no actions remaining"""
        # Mock the command context
        mock_ctx.command = MagicMock()
        mock_ctx.command.name = "brood"
        
        target_user = mock_ctx.add_member(456, "Target")
        target_nest = get_personal_nest(mock_data, target_user.id)
        target_nest["egg"] = {"brooding_progress": 0, "brooded_by": []}

        # Set up the user to have used all their actions
        current_date = get_current_date()
        if "daily_actions" not in mock_data:
            mock_data["daily_actions"] = {}
        mock_data["daily_actions"][str(mock_ctx.author.id)] = {
            f"actions_{current_date}": {
                "used": BASE_DAILY_ACTIONS,
                "bonus": 0
            }
        }

        await incubation_cog.brood.callback(incubation_cog, mock_ctx, target_user)

        # Check message
        mock_ctx.send.assert_called_once()
        assert "You've used all your actions for today" in mock_ctx.send.call_args[0][0]


class TestFlockCommands:
    @pytest.mark.asyncio
    async def test_start_flock_success(self, flock_cog, mock_ctx, mock_data, mocker):
        """Test starting a flock session successfully"""
        # Mock asyncio.sleep to do nothing
        mocker.patch('asyncio.sleep', return_value=None)
        
        # Mock data module functions
        mocker.patch('data.models.get_personal_nest', return_value={'seeds': 0, 'twigs': 0})
        mocker.patch('data.storage.load_data', return_value=mock_data)
        mocker.patch('data.storage.save_data')
        
        # Mock the command context and mention attribute
        mock_ctx.command = MagicMock()
        mock_ctx.command.name = "start_flock"
        mock_ctx.author.mention = f"<@{mock_ctx.author.id}>"
        
        await flock_cog.start_flock.callback(flock_cog, mock_ctx)

        # Check all three messages were sent
        assert mock_ctx.send.call_count == 3
        assert "has started a pomodoro flock" in mock_ctx.send.call_args_list[0][0][0]
        assert "The flock session is starting" in mock_ctx.send.call_args_list[1][0][0]
        assert "The pomodoro flock has ended" in mock_ctx.send.call_args_list[2][0][0]

        # Check flock creation and cleanup
        assert mock_ctx.author.id not in flock_cog.active_flocks  # Flock should be cleaned up after completion

    @pytest.mark.asyncio
    async def test_join_flock_success(self, flock_cog, mock_ctx, mock_data):
        """Test joining an existing flock successfully"""
        # Mock the command context
        mock_ctx.command = MagicMock()
        mock_ctx.command.name = "join_flock"
        mock_ctx.author.mention = f"<@{mock_ctx.author.id}>"
        
        leader = mock_ctx.add_member(456, "Leader")
        leader.mention = f"<@{leader.id}>"
        flock_cog.active_flocks[leader.id] = {
            'leader': leader,
            'members': [leader],
            'start_time': datetime.now(),
            'joining_deadline': datetime.now() + timedelta(minutes=10)
        }

        await flock_cog.join_flock.callback(flock_cog, mock_ctx, leader)

        # Check message
        mock_ctx.send.assert_called_once()
        assert "has joined" in mock_ctx.send.call_args[0][0]

        # Check member added
        flock = flock_cog.active_flocks[leader.id]
        assert mock_ctx.author in flock['members']

    @pytest.mark.asyncio
    async def test_join_flock_expired(self, flock_cog, mock_ctx, mock_data):
        """Test joining an expired flock"""
        # Mock the command context
        mock_ctx.command = MagicMock()
        mock_ctx.command.name = "join_flock"
        mock_ctx.author.mention = f"<@{mock_ctx.author.id}>"
        
        leader = mock_ctx.add_member(456, "Leader")
        leader.mention = f"<@{leader.id}>"
        flock_cog.active_flocks[leader.id] = {
            'leader': leader,
            'members': [leader],
            'start_time': datetime.now() - timedelta(minutes=20),
            'joining_deadline': datetime.now() - timedelta(minutes=10)
        }

        await flock_cog.join_flock.callback(flock_cog, mock_ctx, leader)

        # Check message
        mock_ctx.send.assert_called_once()
        assert "joining period for this flock has ended" in mock_ctx.send.call_args[0][0]

        # Check member not added
        flock = flock_cog.active_flocks[leader.id]
        assert mock_ctx.author not in flock['members']

    @pytest.mark.asyncio
    async def test_join_flock_nonexistent(self, flock_cog, mock_ctx, mock_data):
        """Test joining a non-existent flock"""
        # Mock the command context
        mock_ctx.command = MagicMock()
        mock_ctx.command.name = "join_flock"
        
        leader = mock_ctx.add_member(456, "Leader")

        await flock_cog.join_flock.callback(flock_cog, mock_ctx, leader)

        # Check message
        mock_ctx.send.assert_called_once()
        assert "There is no active flock session from this user" in mock_ctx.send.call_args[0][0]

