# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import json, os, asyncio
from datetime import datetime, timedelta
from .faction_utils import get_member_faction, get_faction_category

SCHEDULE_FILE = "/opt/render/project/src/data/schedule_channels.json"
AUTO_DELETE_DAYS = 14
PURPLE = 0x9b59b6

SCHEDULE_MESSAGE = """All scheduling communications should occur in this channel. **Please start the conversation with the following format:**

Sunday - Times available.
Monday - Times available.
Tuesday - Times available.
Wednesday - Times available.
Thursday - Times available.
Friday - Times available.

Use **/coinflip** if you want to initiate manual map bans

Use **/confirm to finalize your match day and time!** If you have a live match, simply use /confirm for your scheduled time! Map ban links will be sent shortly before live matches."""


def load_json(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class CloseChannelView(View):
    def __init__(self, text_id: int, creator_id: int, key: str):
        super().__init__(timeout=None)
        self.text_id = text_id
        self.creator_id = creator_id
        self.key = key

    @discord.ui.button(label="Close Channel", style=discord.ButtonStyle.red, custom_id="close_schedule_ch")
    async def close(self, interaction: discord.Interaction, button: Button):
        is_admin = interaction.user.guild_permissions.manage_channels
        is_creator = interaction.user.id == self.creator_id
        if not (is_admin or is_creator):
            await interaction.response.send_message("Only the creator or an admin can close this.", ephemeral=True)
            return
        await interaction.response.send_message("Closing this channel in 5 seconds...")
        await asyncio.sleep(5)
        await _delete_schedule(interaction.guild, self.text_id, self.key)


async def _delete_schedule(guild: discord.Guild, text_id: int, key: str):
    ch = guild.get_channel(text_id)
    if ch:
        try:
            await ch.delete(reason="Scheduling channel closed")
        except Exception:
            pass
    data = load_json(SCHEDULE_FILE)
    data.pop(key, None)
    save_json(SCHEDULE_FILE, data)


class SchedulingChannels(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cleanup_task = None

    async def cog_load(self):
        self._cleanup_task = self.bot.loop.create_task(self._auto_delete_loop())

    async def cog_unload(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()

    async def _auto_delete_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                data = load_json(SCHEDULE_FILE)
                now = datetime.utcnow()
                for key, entry in list(data.items()):
                    created = datetime.fromisoformat(entry["created_at"])
                    if (now - created).total_seconds() >= AUTO_DELETE_DAYS * 86400:
                        guild = self.bot.get_guild(entry["guild_id"])
                        if guild:
                            await _delete_schedule(guild, entry["text_channel_id"], key)
            except Exception as e:
                print(f"Auto-delete error: {e}")
            await asyncio.sleep(3600)

    @app_commands.command(name="schedule", description="Create a private scheduling channel between two team roles")
    @app_commands.describe(team1_role="Role for the first team", team2_role="Role for the second team")
    async def schedule(self, interaction: discord.Interaction, team1_role: discord.Role, team2_role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        t1 = team1_role.name.lower().replace(" ", "-")
        t2 = team2_role.name.lower().replace(" ", "-")
        ch_name = f"{t1}-vs-{t2}"

        if discord.utils.get(guild.text_channels, name=ch_name):
            existing = discord.utils.get(guild.text_channels, name=ch_name)
            await interaction.followup.send(f"A scheduling channel already exists: {existing.mention}", ephemeral=True)
            return

        SCHEDULE_CATEGORY = "ᯓ★ SCHEDULE ★ᯓ"
        category = discord.utils.get(guild.categories, name=SCHEDULE_CATEGORY)
        if not category:
            try:
                category = await guild.create_category(SCHEDULE_CATEGORY)
            except discord.Forbidden:
                await interaction.followup.send("Missing permission to create categories.", ephemeral=True)
                return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_messages=True),
            team1_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            team2_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        for role in guild.roles:
            if role.permissions.manage_guild and role not in overwrites:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        mod_role = discord.utils.find(lambda r: "moderator" in r.name.lower(), guild.roles)
        if mod_role and mod_role not in overwrites:
            overwrites[mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        try:
            text_ch = await guild.create_text_channel(
                name=ch_name,
                category=category,
                overwrites=overwrites,
                topic=f"Scheduling: {team1_role.name} vs {team2_role.name} | Auto-deletes in {AUTO_DELETE_DAYS} days"
            )
        except discord.Forbidden:
            await interaction.followup.send("Missing permission to create channels.", ephemeral=True)
            return

        key = f"{team1_role.id}_{team2_role.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        data = load_json(SCHEDULE_FILE)
        data[key] = {
            "guild_id": guild.id,
            "team1": team1_role.name,
            "team2": team2_role.name,
            "text_channel_id": text_ch.id,
            "creator_id": interaction.user.id,
            "created_at": datetime.utcnow().isoformat(),
            "auto_delete_at": (datetime.utcnow() + timedelta(days=AUTO_DELETE_DAYS)).isoformat()
        }
        save_json(SCHEDULE_FILE, data)

        embed = discord.Embed(
            title=f"{team1_role.name} vs {team2_role.name}",
            description=SCHEDULE_MESSAGE,
            color=PURPLE,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Auto-Delete", value=f"This channel will be deleted in **{AUTO_DELETE_DAYS} days**.", inline=True)
        embed.set_footer(text=f"Created by {interaction.user}")

        close_view = CloseChannelView(text_ch.id, interaction.user.id, key)
        msg = await text_ch.send(content=f"{team1_role.mention} {team2_role.mention}", embed=embed, view=close_view)
        try:
            await msg.pin()
        except Exception:
            pass

        await interaction.followup.send(f"Scheduling channel created: {text_ch.mention}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SchedulingChannels(bot))
