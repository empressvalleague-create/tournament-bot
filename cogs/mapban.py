# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import json, os, random
from datetime import datetime

MAPBAN_FILE = "data/mapban_sessions.json"
PURPLE = 0x9b59b6

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

def is_schedule_channel(channel) -> bool:
    if not isinstance(channel, discord.TextChannel):
        return False
    if channel.category is None:
        return False
    return "scheduling" in channel.category.name.lower() or "devour" in channel.category.name.lower() or "dismiss" in channel.category.name.lower()

def get_session(channel_id: int):
    return load_json(MAPBAN_FILE).get(str(channel_id))

def save_session(channel_id: int, session: dict):
    sessions = load_json(MAPBAN_FILE)
    sessions[str(channel_id)] = session
    save_json(MAPBAN_FILE, sessions)

def delete_session(channel_id: int):
    sessions = load_json(MAPBAN_FILE)
    sessions.pop(str(channel_id), None)
    save_json(MAPBAN_FILE, sessions)

STEPS = [
    ("team1", "ban"),
    ("team2", "ban"),
    ("team1", "pick"),
    ("team2", "side"),
    ("team2", "pick"),
    ("team1", "side"),
    ("team1", "ban"),
    ("team2", "pick"),
    ("team1", "side"),
]

def next_action_text(session: dict) -> str:
    step = session["step"]
    if step >= len(STEPS):
        return ""
    team_key, action = STEPS[step]
    role_id = session[team_key + "_role_id"]
    if action == "ban":
        return f"<@&{role_id}> — type a map to **BAN**."
    elif action == "pick":
        return f"<@&{role_id}> — type a map to **PICK**."
    elif action == "side":
        return f"<@&{role_id}> — type **Attack** or **Defense**."
    return ""

def summary_embed(session: dict, done: bool = False) -> discord.Embed:
    embed = discord.Embed(title="Map Ban Complete!" if done else "Map Ban in Progress", color=PURPLE, timestamp=datetime.utcnow())
    embed.add_field(name="Teams", value=f"Team 1: <@&{session['team1_role_id']}>\nTeam 2: <@&{session['team2_role_id']}>", inline=False)
    bans = session.get("bans", [])
    picks = session.get("picks", [])
    sides = session.get("sides", [])
    if bans:
        embed.add_field(name="Banned Maps", value="\n".join(f"- {b}" for b in bans), inline=True)
    if picks:
        lines = []
        for i, p in enumerate(picks):
            side = sides[i] if i < len(sides) else "TBD"
            lines.append(f"Map {i+1}: **{p}** — Attacker: {side}")
        embed.add_field(name="Picked Maps", value="\n".join(lines), inline=False)
    if not done:
        nxt = next_action_text(session)
        if nxt:
            embed.add_field(name="Next", value=nxt, inline=False)
    return embed


class CoinFlipView(View):
    def __init__(self, caller_id, team1_role_id, team1_name, team2_role_id, team2_name):
        super().__init__(timeout=120)
        self.caller_id = caller_id
        self.team1_role_id = team1_role_id
        self.team1_name = team1_name
        self.team2_role_id = team2_role_id
        self.team2_name = team2_name

    @discord.ui.button(label="Heads", style=discord.ButtonStyle.blurple)
    async def heads(self, interaction: discord.Interaction, button: Button):
        await self._flip(interaction, "Heads")

    @discord.ui.button(label="Tails", style=discord.ButtonStyle.grey)
    async def tails(self, interaction: discord.Interaction, button: Button):
        await self._flip(interaction, "Tails")

    async def _flip(self, interaction: discord.Interaction, choice: str):
        if interaction.user.id != self.caller_id:
            await interaction.response.send_message("Only the person who ran /coinflip can call it.", ephemeral=True)
            return
        result = random.choice(["Heads", "Tails"])
        won = (choice == result)
        member_role_ids = [r.id for r in interaction.user.roles]
        caller_is_team1 = self.team1_role_id in member_role_ids
        if caller_is_team1:
            winner_role_id = self.team1_role_id if won else self.team2_role_id
            winner_name    = self.team1_name    if won else self.team2_name
            loser_role_id  = self.team2_role_id if won else self.team1_role_id
            loser_name     = self.team2_name    if won else self.team1_name
        else:
            winner_role_id = self.team2_role_id if won else self.team1_role_id
            winner_name    = self.team2_name    if won else self.team1_name
            loser_role_id  = self.team1_role_id if won else self.team2_role_id
            loser_name     = self.team1_name    if won else self.team2_name
        embed = discord.Embed(
            title="Coin Flip Result!",
            description=(
                f"You called: **{choice}**\nResult: **{result}**\n\n"
                f"**{winner_name}** wins the flip!\n\n"
                f"<@&{winner_role_id}> — pick which team you want to be:"
            ),
            color=PURPLE
        )
        view = PickTeamView(winner_role_id=winner_role_id, winner_name=winner_name, loser_role_id=loser_role_id, loser_name=loser_name, channel_id=interaction.channel.id)
        await interaction.response.edit_message(embed=embed, view=view)


class PickTeamView(View):
    def __init__(self, winner_role_id, winner_name, loser_role_id, loser_name, channel_id):
        super().__init__(timeout=120)
        self.winner_role_id = winner_role_id
        self.winner_name    = winner_name
        self.loser_role_id  = loser_role_id
        self.loser_name     = loser_name
        self.channel_id     = channel_id

    def _is_winner(self, interaction):
        return self.winner_role_id in [r.id for r in interaction.user.roles]

    @discord.ui.button(label="We'll be Team 1 (bans first)", style=discord.ButtonStyle.green)
    async def be_team1(self, interaction: discord.Interaction, button: Button):
        if not self._is_winner(interaction):
            await interaction.response.send_message("Only the flip winner can choose.", ephemeral=True)
            return
        await self._start(interaction, team1_id=self.winner_role_id, team1_name=self.winner_name, team2_id=self.loser_role_id, team2_name=self.loser_name)

    @discord.ui.button(label="We'll be Team 2", style=discord.ButtonStyle.blurple)
    async def be_team2(self, interaction: discord.Interaction, button: Button):
        if not self._is_winner(interaction):
            await interaction.response.send_message("Only the flip winner can choose.", ephemeral=True)
            return
        await self._start(interaction, team1_id=self.loser_role_id, team1_name=self.loser_name, team2_id=self.winner_role_id, team2_name=self.winner_name)

    async def _start(self, interaction, team1_id, team1_name, team2_id, team2_name):
        session = {"channel_id": self.channel_id, "team1_role_id": team1_id, "team1_name": team1_name, "team2_role_id": team2_id, "team2_name": team2_name, "step": 0, "bans": [], "picks": [], "sides": [], "started_at": datetime.utcnow().isoformat()}
        save_session(self.channel_id, session)
        await interaction.response.edit_message(embed=summary_embed(session), view=None)


class MapBan(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="coinflip", description="Start a coin flip to begin the map ban process")
    @app_commands.describe(team1="First team role", team2="Second team role")
    async def coinflip(self, interaction: discord.Interaction, team1: discord.Role, team2: discord.Role):
        if not is_schedule_channel(interaction.channel):
            await interaction.response.send_message("This command can only be used inside a scheduling channel.", ephemeral=True)
            return
        if get_session(interaction.channel.id):
            await interaction.response.send_message("A map ban is already in progress in this channel.", ephemeral=True)
            return
        member_roles = [r.id for r in interaction.user.roles]
        if team1.id not in member_roles and team2.id not in member_roles:
            await interaction.response.send_message("You must be on one of the two teams to start the flip.", ephemeral=True)
            return
        embed = discord.Embed(title="Coin Flip!", description=f"**{team1.name}** vs **{team2.name}**\n\n<@{interaction.user.id}> is calling — Heads or Tails?", color=PURPLE)
        await interaction.response.send_message(embed=embed, view=CoinFlipView(caller_id=interaction.user.id, team1_role_id=team1.id, team1_name=team1.name, team2_role_id=team2.id, team2_name=team2.name))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not isinstance(message.channel, discord.TextChannel):
            return
        if not is_schedule_channel(message.channel):
            return
        session = get_session(message.channel.id)
        if not session:
            return
        step = session["step"]
        if step >= len(STEPS):
            return
        team_key, action = STEPS[step]
        role_id = session[team_key + "_role_id"]
        if role_id not in [r.id for r in message.author.roles]:
            return
        content = message.content.strip()
        if not content or content.startswith("/"):
            return
        if action == "side":
            if content.lower() not in ("attack", "defense", "defence"):
                await message.channel.send("Please type **Attack** or **Defense**.", delete_after=5)
                return
            session["sides"].append("Attack" if content.lower() == "attack" else "Defense")
        elif action == "ban":
            session["bans"].append(content)
        elif action == "pick":
            session["picks"].append(content)
        session["step"] += 1
        try:
            await message.delete()
        except Exception:
            pass
        if session["step"] >= len(STEPS):
            save_session(message.channel.id, session)
            await message.channel.send(embed=summary_embed(session, done=True))
            delete_session(message.channel.id)
            return
        save_session(message.channel.id, session)
        await message.channel.send(embed=summary_embed(session))


async def setup(bot):
    await bot.add_cog(MapBan(bot))
