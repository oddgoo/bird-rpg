from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord
import pytest

from commands.info import InfoCommands
from utils.nest_showcase import NestShowcaseError


def _make_interaction(user_id=123):
    interaction = AsyncMock()
    interaction.user = SimpleNamespace(
        id=user_id,
        mention=f"<@{user_id}>",
        bot=False,
        display_name=f"User {user_id}",
    )
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction


def _payload(name="Test Nest"):
    return {
        "nest_name": name,
        "twigs": 11,
        "seeds": 4,
        "chicks": 2,
        "egg_progress": 6,
    }


@pytest.mark.asyncio
async def test_showcase_nest_defaults_to_caller():
    cog = InfoCommands(AsyncMock())
    interaction = _make_interaction(user_id=321)

    with patch("commands.info.build_showcase_payload", new=AsyncMock(return_value=_payload())) as build_mock, \
         patch("commands.info.render_showcase_png", new=AsyncMock(return_value=b"png-bytes")):
        await cog.showcase_nest.callback(cog, interaction, None)

    build_mock.assert_awaited_once_with("321", allow_fallback_image=True)
    interaction.response.defer.assert_awaited_once()
    interaction.followup.send.assert_awaited_once()

    kwargs = interaction.followup.send.call_args.kwargs
    assert isinstance(kwargs["embed"], discord.Embed)
    assert isinstance(kwargs["file"], discord.File)
    assert kwargs["embed"].title == "🪺 Test Nest"


@pytest.mark.asyncio
async def test_showcase_nest_uses_target_user_when_provided():
    cog = InfoCommands(AsyncMock())
    interaction = _make_interaction(user_id=111)
    target = SimpleNamespace(id=999, mention="<@999>", bot=False, display_name="Target Bird")

    with patch("commands.info.build_showcase_payload", new=AsyncMock(return_value=_payload("Target Nest"))) as build_mock, \
         patch("commands.info.render_showcase_png", new=AsyncMock(return_value=b"png-bytes")):
        await cog.showcase_nest.callback(cog, interaction, target)

    build_mock.assert_awaited_once_with("999", allow_fallback_image=False)
    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert embed.description == "Showcasing <@999>'s nest"


@pytest.mark.asyncio
async def test_showcase_nest_rejects_bot_target():
    cog = InfoCommands(AsyncMock())
    interaction = _make_interaction(user_id=111)
    target = SimpleNamespace(id=999, mention="<@999>", bot=True, display_name="Bot")

    with patch("commands.info.build_showcase_payload", new=AsyncMock()) as build_mock:
        await cog.showcase_nest.callback(cog, interaction, target)

    build_mock.assert_not_awaited()
    interaction.followup.send.assert_awaited_once_with("Bots do not have showcaseable nests.")


@pytest.mark.asyncio
async def test_showcase_nest_handles_not_showcaseable_error():
    cog = InfoCommands(AsyncMock())
    interaction = _make_interaction(user_id=111)

    with patch(
        "commands.info.build_showcase_payload",
        new=AsyncMock(side_effect=NestShowcaseError("This user does not have a showcaseable nest yet.")),
    ):
        await cog.showcase_nest.callback(cog, interaction, None)

    interaction.followup.send.assert_awaited_once_with("This user does not have a showcaseable nest yet.")


@pytest.mark.asyncio
async def test_showcase_nest_handles_unexpected_error():
    cog = InfoCommands(AsyncMock())
    interaction = _make_interaction(user_id=111)

    with patch("commands.info.build_showcase_payload", new=AsyncMock(side_effect=RuntimeError("boom"))), \
         patch("commands.info.log_debug") as log_debug_mock:
        await cog.showcase_nest.callback(cog, interaction, None)

    log_debug_mock.assert_called_once()
    interaction.followup.send.assert_awaited_once_with(
        "Couldn't generate this nest showcase right now. Please try again later."
    )
