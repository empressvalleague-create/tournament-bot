# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select
import json, os
from datetime import datetime, timedelta
from .faction_utils import get_faction_channel

CONFIRM_FILE = "data/pending_confirms.json"
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

def get_channel_by_names(guild, *names):
    for name in names:
        ch = discord.utils.get(guild.text_channels, name=name)
        if ch:
            return ch
    return None

NA_TIMEZONES = [
    ("Eastern Time (ET)",   "America/New_York"),
    ("Central Time (CT)",   "America/Chicago"),
    ("Mountain Time (MT)",  "America/Denver"),
    ("Mountain Time - AZ",  "America/Phoenix"),
    ("Pacific Time (PT)",   "America/Los_Angeles"),
    ("Alaska Time (AKT)",   "America/Anchorage"),
    ("Hawaii Time (HAT)",   "Pacific/Honolulu"),
    ("Atlantic Time (AT)",  "America/Halifax"),
]

def get_next_14_dates():
    today = datetime.utcnow().date()
    return [(today + timedelta(days=i)).strftime("%A, %b %d") for i in range(14)]

TIMES = [
    "12:00 PM","12:30 PM",
    "1:00 PM","1:30 PM","2:00 PM","2:30 PM","3:00 PM","3:30 PM",
    "4:00 PM","4:30 PM","5:00 PM","5:30 PM","6:00 PM","6:30 PM",
    "7:00 PM","7:30 PM","8:00 PM","8:30 PM","9:00 PM","9:30 PM",
    "10:00 PM","10:30 PM","11:00 PM","11:30 PM","12:00 AM",
]

def step_embed(title, desc=""):
    return discord.Embed(title=title, description=desc, color=PURPLE)

def preview_embed(state):
    embed = discord.Embed(title="Match Time Preview", description="Does this look right?", color=PURPLE)
    embed.add_field(name="Team 1", value=f"<@&{state['team1_role_id']}>", inline=True)
    embed.add_field(name="Team 2", value=f"<@&{state['team2_role_id']}>", inline=True)
    embed.add_field(name="Date", value=state["day"], inline=True)
    embed.add_field(name="Time", value=state["time"], inline=True)
    embed.add_field(name="Timezone", value=state["timezone_label"], inline=True)
    return embed

def confirm_pending_embed(state, team1_role, team2_role):
    proposer = state["team1_name"] if state["requester_role_id"] == state["team1_role_id"] else state["team2_name"]
    embed = discord.Embed(
        title="Match Time Proposal",
        description=(
            f"## {team1_role.mention if team1_role else state['team1_name']}  vs  "
            f"{team2_role.mention if team2_role else state['team2_name']}\n"
            f"**{state['day']}** at **{state['time']}** {state['timezone_label']}\n\n"
            f"Waiting for the opposing team to confirm..."
        ),
        color=PURPLE,
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=f"Proposed by {proposer}")
    return embed

def confirm_approved_embed(state, team1_role, team2_role, confirmer):
    embed = discord.Embed(
        title="Match Time Confirmed!",
        description=(
            f"## {team1_role.mention if team1_role else state['team1_name']}  vs  "
            f"{team2_role.mention if team2_role else state['team2_name']}\n"
            f"**{state['day']}** at **{state['time']}** {state['timezone_label']}"
        ),
        color=PURPLE,
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=f"Confirmed by {confirmer}")
    return embed


class TimezoneSelect(Select):
    def __init__(self, state):
        self.state = state
        super().__init__(placeholder="Select your timezone...", options=[
            discord.SelectOption(label=l, value=v) for l, v in NA_TIMEZONES
        ])
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.state["requester_id"]:
            await interaction.response.send_message("Not your request.", ephemeral=True)
            return
        self.state["timezone"] = self.values[0]
        self.state["timezone_label"] = next(l for l, v in NA_TIMEZONES if v == self.values[0])
        await interaction.response.edit_message(
            embed=step_embed("Step 2 of 3 - Pick a date", f"Timezone: **{self.state['timezone_label']}**"),
            view=DaySelectView(self.state)
        )

class DaySelect(Select):
    def __init__(self, state):
        self.state = state
        dates = get_next_14_dates()
        super().__init__(placeholder="Select the match date...", options=[
            discord.SelectOption(label=d, value=d) for d in dates
        ])
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.state["requester_id"]:
            await interaction.response.send_message("Not your request.", ephemeral=True)
            return
        self.state["day"] = self.values[0]
        await interaction.response.edit_message(
            embed=step_embed("Step 3 of 3 - Pick a time", f"Date: **{self.state['day']}** - TZ: **{self.state['timezone_label']}**"),
            view=TimeSelectView(self.state)
        )

class TimeSelect(Select):
    def __init__(self, state):
        self.state = state
        super().__init__(placeholder="Select the match time...", options=[
            discord.SelectOption(label=t, value=t) for t in TIMES
        ])
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.state["requester_id"]:
            await interaction.response.send_message("Not your request.", ephemeral=True)
            return
        self.state["time"] = self.values[0]
        await interaction.response.edit_message(embed=preview_embed(self.state), view=SendConfirmView(self.state))

class TimezoneSelectView(View):
    def __init__(self, state):
        super().__init__(timeout=180)
        self.add_item(TimezoneSelect(state))

class DaySelectView(View):
    def __init__(self, state):
        super().__init__(timeout=180)
        self.add_item(DaySelect(state))

class TimeSelectView(View):
    def __init__(self, state):
        super().__init__(timeout=180)
        self.add_item(TimeSelect(state))


class SendConfirmView(View):
    def __init__(self, state):
        super().__init__(timeout=180)
        self.state = state

    @discord.ui.button(label="Send to Channel", style=discord.ButtonStyle.green)
    async def send(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.state["requester_id"]:
            await interaction.response.send_message("Not your request.", ephemeral=True)
            return
        guild = interaction.guild
        t1_slug = self.state["team1_name"].lower().replace(" ", "-")
        t2_slug = self.state["team2_name"].lower().replace(" ", "-")
        target_ch = None
        for ch in guild.text_channels:
            if t1_slug in ch.name and t2_slug in ch.name:
                target_ch = ch
                break
            if t2_slug in ch.name and t1_slug in ch.name:
                target_ch = ch
                break
        if not target_ch:
            target_ch = interaction.channel

        key = f"confirm_{interaction.user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        pending = load_json(CONFIRM_FILE)
        pending[key] = {**self.state, "channel_id": target_ch.id, "status": "pending"}
        save_json(CONFIRM_FILE, pending)

        team1_role = guild.get_role(self.state["team1_role_id"])
        team2_role = guild.get_role(self.state["team2_role_id"])
        await target_ch.send(
            content=f"{team1_role.mention} {team2_role.mention}",
            embed=confirm_pending_embed(self.state, team1_role, team2_role),
            view=OpponentApprovalView(key)
        )
        await interaction.response.edit_message(
            embed=discord.Embed(title="Sent!", description=f"Proposal posted in {target_ch.mention}. Waiting for the other team.", color=PURPLE),
            view=None
        )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.grey)
    async def back(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.state["requester_id"]:
            await interaction.response.send_message("Not your request.", ephemeral=True)
            return
        self.state.pop("time", None)
        await interaction.response.edit_message(
            embed=step_embed("Step 3 of 3 - Pick a time", f"Day: **{self.state['day']}** - TZ: **{self.state['timezone_label']}**"),
            view=TimeSelectView(self.state)
        )


class OpponentApprovalView(View):
    def __init__(self, key):
        super().__init__(timeout=None)
        self.key = key

    def _load(self):
        return load_json(CONFIRM_FILE).get(self.key)

    @discord.ui.button(label="Confirm Match Time", style=discord.ButtonStyle.green, custom_id="confirm_match")
    async def confirm(self, interaction: discord.Interaction, button: Button):
        state = self._load()
        if not state:
            await interaction.response.send_message("This proposal is no longer active.", ephemeral=True)
            return
        if state.get("status") != "pending":
            await interaction.response.send_message("This proposal has already been resolved.", ephemeral=True)
            return

        guild = interaction.guild
        team1_role = guild.get_role(state["team1_role_id"])
        team2_role = guild.get_role(state["team2_role_id"])
        member_role_ids = [r.id for r in interaction.user.roles]
        is_team1 = team1_role and team1_role.id in member_role_ids
        is_team2 = team2_role and team2_role.id in member_role_ids

        if not (is_team1 or is_team2):
            await interaction.response.send_message("You must be on one of the two teams to confirm.", ephemeral=True)
            return

        requester_role_id = state["requester_role_id"]
        if requester_role_id in member_role_ids:
            other_id = state["team2_role_id"] if requester_role_id == state["team1_role_id"] else state["team1_role_id"]
            if other_id not in member_role_ids:
                await interaction.response.send_message("The proposing team cannot confirm their own proposal.", ephemeral=True)
                return

        pending = load_json(CONFIRM_FILE)
        pending[self.key]["status"] = "confirmed"
        pending[self.key]["confirmed_by"] = str(interaction.user)
        save_json(CONFIRM_FILE, pending)

        await interaction.response.edit_message(
            embed=confirm_approved_embed(state, team1_role, team2_role, interaction.user),
            view=None
        )

        # Route to faction-specific #match-times based on the scheduling channel's category
        faction = None
        if interaction.channel.category:
            cat_name = interaction.channel.category.name.lower()
            if "devour" in cat_name:
                faction = "devour"
            elif "dismiss" in cat_name:
                faction = "dismiss"

        times_ch = get_faction_channel(guild, faction, "match-times") if faction else get_channel_by_names(guild, "match-times", "Match-Times")
        if times_ch:
            pub = discord.Embed(
                title="Match Scheduled!",
                description=(
                    f"## {team1_role.mention if team1_role else state['team1_name']}  vs  "
                    f"{team2_role.mention if team2_role else state['team2_name']}\n"
                    f"**{state['day']}** at **{state['time']}** {state['timezone_label']}"
                ),
                color=PURPLE,
                timestamp=datetime.utcnow()
            )
            pub.set_footer(text=f"Confirmed by {interaction.user}")
            await times_ch.send(embed=pub)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, custom_id="decline_match")
    async def decline(self, interaction: discord.Interaction, button: Button):
        state = self._load()
        if not state:
            await interaction.response.send_message("This proposal is no longer active.", ephemeral=True)
            return
        if state.get("status") != "pending":
            await interaction.response.send_message("Already resolved.", ephemeral=True)
            return

        guild = interaction.guild
        team1_role = guild.get_role(state["team1_role_id"])
        team2_role = guild.get_role(state["team2_role_id"])
        member_role_ids = [r.id for r in interaction.user.roles]
        if (not team1_role or team1_role.id not in member_role_ids) and \
           (not team2_role or team2_role.id not in member_role_ids):
            await interaction.response.send_message("You must be on one of the two teams.", ephemeral=True)
            return

        pending = load_json(CONFIRM_FILE)
        pending[self.key]["status"] = "declined"
        save_json(CONFIRM_FILE, pending)

        embed = discord.Embed(
            title="Match Time Declined",
            description=f"**{state['day']}** at **{state['time']}** {state['timezone_label']} was declined.\nPlease continue scheduling.",
            color=PURPLE,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Declined by {interaction.user}")
        await interaction.response.edit_message(embed=embed, view=None)


class ConfirmMatch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        pending = load_json(CONFIRM_FILE)
        for key, entry in pending.items():
            if entry.get("status") == "pending":
                self.bot.add_view(OpponentApprovalView(key))

    @app_commands.command(name="confirm", description="Propose a match time to the opposing team")
    @app_commands.describe(team1="Your team role", team2="Opponent team role")
    async def confirm(self, interaction: discord.Interaction, team1: discord.Role, team2: discord.Role):
        member_role_ids = [r.id for r in interaction.user.roles]
        requester_role_id = team1.id if team1.id in member_role_ids else team2.id
        state = {
            "requester_id": interaction.user.id,
            "requester_name": str(interaction.user),
            "requester_role_id": requester_role_id,
            "team1_role_id": team1.id,
            "team1_name": team1.name,
            "team2_role_id": team2.id,
            "team2_name": team2.name,
        }
        await interaction.response.send_message(
            embed=step_embed("Step 1 of 3 - Select your timezone"),
            view=TimezoneSelectView(state),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(ConfirmMatch(bot))
