# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
import json, os, asyncio
from datetime import datetime, timedelta
from .faction_utils import get_faction_role, get_faction_channel

REQUESTS_FILE  = "/opt/render/project/src/data/roster_requests.json"
SUB_EXPIRY_FILE = "/opt/render/project/src/data/sub_expiries.json"
SUB_ROLE_DAYS  = 8
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


def make_key(prefix, user_id):
    return f"{prefix}_{user_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"


def get_mod_ping(guild):
    mod_role = (
        discord.utils.get(guild.roles, name="Moderator") or
        discord.utils.get(guild.roles, name="moderator") or
        discord.utils.get(guild.roles, name="Admin")
    )
    return mod_role.mention if mod_role else ""


# ─── Faction picker ───────────────────────────────────────────────────────────

class FactionSelectView(View):
    def __init__(self, request_type: str, team, add_player=None, remove_player=None, remove_name=None, sub_in=None, sub_out=None, sub_out_name=None):
        super().__init__(timeout=60)
        self.request_type = request_type
        self.team = team
        self.add_player = add_player
        self.remove_player = remove_player
        self.remove_name = remove_name
        self.sub_in = sub_in
        self.sub_out = sub_out
        self.sub_out_name = sub_out_name

    async def _open_modal(self, interaction: discord.Interaction, tier: str):
        if self.request_type == "roster_change":
            if self.add_player:
                modal = RosterTrackerModal(
                    tier=tier, team=self.team,
                    add_player=self.add_player,
                    remove_player=self.remove_player,
                    remove_name=self.remove_name,
                    original_interaction=interaction
                )
            else:
                modal = RosterRemoveOnlyModal(
                    tier=tier, team=self.team,
                    remove_player=self.remove_player,
                    remove_name=self.remove_name,
                    original_interaction=interaction
                )
        elif self.request_type == "sub":
            modal = SubModal(tier=tier, team=self.team, sub_in=self.sub_in, sub_out=self.sub_out, sub_out_name=self.sub_out_name, original_interaction=interaction)
        elif self.request_type == "name_change":
            modal = NameChangeModal(tier=tier, team=self.team, original_interaction=interaction)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Devour", style=discord.ButtonStyle.red)
    async def devour(self, interaction: discord.Interaction, button: Button):
        await self._open_modal(interaction, "devour")

    @discord.ui.button(label="Dismiss", style=discord.ButtonStyle.blurple)
    async def dismiss(self, interaction: discord.Interaction, button: Button):
        await self._open_modal(interaction, "dismiss")


# ─── Roster Change Modals ─────────────────────────────────────────────────────

class RosterTrackerModal(Modal, title="Roster Change - Player Details"):
    """Shown when adding a player — asks for IGN and tracker link."""
    add_ign = TextInput(
        label="IGN of player being added (e.g. Name#tag)",
        placeholder="ExamplePlayer#1234",
        required=True
    )
    tracker_link = TextInput(
        label="Tracker.gg link for the player being added",
        placeholder="https://tracker.gg/...",
        required=True
    )
    note = TextInput(
        label="Reasoning/Notes for Admin (optional)",
        placeholder="Any context for the admins",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500
    )

    def __init__(self, tier, team, add_player, remove_player, remove_name, original_interaction=None):
        super().__init__()
        self.tier = tier
        self.team = team
        self.add_player = add_player
        self.remove_player = remove_player
        self.remove_name = remove_name
        self.original_interaction = original_interaction

    async def on_submit(self, interaction: discord.Interaction):
        remove_id   = self.remove_player.id   if self.remove_player else None
        remove_name = str(self.remove_player) if self.remove_player else self.remove_name

        key = make_key("rc", interaction.user.id)
        requests = load_json(REQUESTS_FILE)
        requests[key] = {
            "type": "roster_change",
            "requester_id": interaction.user.id,
            "requester_name": str(interaction.user),
            "tier": self.tier,
            "team_role_id": self.team.id,
            "team_name": self.team.name,
            "add_player_id": self.add_player.id,
            "add_player_name": str(self.add_player),
            "add_player_ign": self.add_ign.value.strip(),
            "remove_player_id": remove_id,
            "remove_player_name": remove_name,
            "tracker_link": self.tracker_link.value.strip(),
            "note": self.note.value or None,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "pending"
        }
        save_json(REQUESTS_FILE, requests)
        await _send_roster_request(interaction, requests[key], key, self.original_interaction)


class RosterRemoveOnlyModal(Modal, title="Roster Change - Remove Player"):
    """Shown when only removing a player."""
    note = TextInput(
        label="Reasoning/Notes for Admin (optional)",
        placeholder="Any context for the admins",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500
    )

    def __init__(self, tier, team, remove_player, remove_name, original_interaction=None):
        super().__init__()
        self.tier = tier
        self.team = team
        self.remove_player = remove_player
        self.remove_name = remove_name
        self.original_interaction = original_interaction

    async def on_submit(self, interaction: discord.Interaction):
        remove_id   = self.remove_player.id   if self.remove_player else None
        remove_name = str(self.remove_player) if self.remove_player else self.remove_name

        key = make_key("rc", interaction.user.id)
        requests = load_json(REQUESTS_FILE)
        requests[key] = {
            "type": "roster_change",
            "requester_id": interaction.user.id,
            "requester_name": str(interaction.user),
            "tier": self.tier,
            "team_role_id": self.team.id,
            "team_name": self.team.name,
            "add_player_id": None,
            "add_player_name": None,
            "add_player_ign": None,
            "remove_player_id": remove_id,
            "remove_player_name": remove_name,
            "tracker_link": None,
            "note": self.note.value or None,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "pending"
        }
        save_json(REQUESTS_FILE, requests)
        await _send_roster_request(interaction, requests[key], key, self.original_interaction)


async def _send_roster_request(interaction, req, key, original_interaction=None):
    admin_ch = get_channel_by_names(interaction.guild, "bot-requests", "admin-requests", "staff")
    if not admin_ch:
        await interaction.response.send_message(
            "Could not find an admin channel (bot-requests / admin-requests / staff). Please ask an admin to set one up.",
            ephemeral=True
        )
        return

    embed = discord.Embed(title="Roster Change Request", color=PURPLE, timestamp=datetime.utcnow())
    embed.add_field(name="Requested By", value=req["requester_name"], inline=True)
    embed.add_field(name="Team", value=f"<@&{req['team_role_id']}>", inline=True)
    embed.add_field(name="Tier", value=req['tier'].capitalize(), inline=True)
    if req.get("add_player_name"):
        embed.add_field(name="Adding", value=req["add_player_name"], inline=True)
    if req.get("add_player_ign"):
        embed.add_field(name="IGN", value=req["add_player_ign"], inline=True)
    if req.get("remove_player_name"):
        embed.add_field(name="Removing", value=req["remove_player_name"], inline=True)
    if req.get("tracker_link"):
        embed.add_field(name="Tracker.gg", value=req["tracker_link"], inline=False)
    if req.get("note"):
        embed.add_field(name="Admin Note", value=req["note"], inline=False)
    embed.set_footer(text=f"ID: {key}")

    await admin_ch.send(content=get_mod_ping(interaction.guild), embed=embed, view=RequestAdminView())
    await interaction.response.send_message("Your roster change request has been sent to admins!", ephemeral=True)
    if original_interaction:
        try:
            await original_interaction.edit_original_response(content="✅ Request sent!", embed=None, view=None)
        except Exception:
            pass


# ─── Sub Modal ────────────────────────────────────────────────────────────────

class SubModal(Modal, title="Sub Request - Details"):
    sub_in_ign = TextInput(
        label="IGN of player subbing in (e.g. Name#tag)",
        placeholder="ExamplePlayer#1234",
        required=False
    )
    tracker_link = TextInput(
        label="Tracker.gg link for the sub",
        placeholder="https://tracker.gg/...",
        required=True
    )
    note = TextInput(
        label="Reasoning/Notes for Admin (optional)",
        placeholder="Any context for the admins",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500
    )

    def __init__(self, tier, team, sub_in, sub_out=None, sub_out_name=None, original_interaction=None):
        super().__init__()
        self.tier = tier
        self.team = team
        self.sub_in = sub_in
        self.sub_out = sub_out
        self.sub_out_name = sub_out_name
        self.original_interaction = original_interaction

    async def on_submit(self, interaction: discord.Interaction):
        try:
            sub_out_id   = self.sub_out.id   if self.sub_out else None
            sub_out_name = str(self.sub_out) if self.sub_out else self.sub_out_name

            key = make_key("sub", interaction.user.id)
            requests = load_json(REQUESTS_FILE)
            requests[key] = {
                "type": "sub",
                "requester_id": interaction.user.id,
                "requester_name": str(interaction.user),
                "tier": self.tier,
                "team_role_id": self.team.id,
                "team_name": self.team.name,
                "sub_in_id": self.sub_in.id,
                "sub_in_name": str(self.sub_in),
                "sub_in_ign": self.sub_in_ign.value.strip() or None,
                "sub_out_id": sub_out_id,
                "sub_out_name": sub_out_name,
                "tracker_link": self.tracker_link.value.strip(),
                "note": self.note.value or None,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "pending"
            }
            save_json(REQUESTS_FILE, requests)

            admin_ch = get_channel_by_names(interaction.guild, "bot-requests", "admin-requests", "staff")
            if not admin_ch:
                await interaction.response.send_message(
                    "Could not find an admin channel (bot-requests / admin-requests / staff). Please ask an admin to set one up.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(title="Sub Request", color=PURPLE, timestamp=datetime.utcnow())
            embed.add_field(name="Requested By", value=str(interaction.user), inline=True)
            embed.add_field(name="Team", value=f"<@&{self.team.id}>", inline=True)
            embed.add_field(name="Tier", value=self.tier.capitalize(), inline=True)
            embed.add_field(name="Subbing IN", value=str(self.sub_in), inline=True)
            if self.sub_in_ign.value:
                embed.add_field(name="IGN", value=self.sub_in_ign.value, inline=True)
            if sub_out_name:
                embed.add_field(name="Sitting OUT", value=sub_out_name, inline=True)
            if self.tracker_link.value.strip():
                embed.add_field(name="Tracker.gg", value=self.tracker_link.value.strip(), inline=False)
            if self.note.value:
                embed.add_field(name="Admin Note", value=self.note.value, inline=False)
            embed.set_footer(text=f"ID: {key}")

            await admin_ch.send(content=get_mod_ping(interaction.guild), embed=embed, view=RequestAdminView())
            await interaction.response.send_message("Your sub request has been sent to admins!", ephemeral=True)
            if self.original_interaction:
                try:
                    await self.original_interaction.edit_original_response(content="✅ Request sent!", embed=None, view=None)
                except Exception:
                    pass
        except Exception as e:
            print(f"SubModal error: {e}")
            await interaction.response.send_message("Something went wrong submitting your request. Please try again.", ephemeral=True)


# ─── Name Change Modal ────────────────────────────────────────────────────────

class NameChangeModal(Modal, title="Name Change Request"):
    old_ign = TextInput(label="Old IGN", placeholder="Current name on the roster", required=True)
    new_ign = TextInput(label="New IGN", placeholder="New name to update to", required=True)
    note = TextInput(
        label="Reasoning/Notes for Admin (optional)",
        placeholder="Any context for the admins",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500
    )

    def __init__(self, tier, team, original_interaction=None):
        super().__init__()
        self.tier = tier
        self.team = team
        self.original_interaction = original_interaction

    async def on_submit(self, interaction: discord.Interaction):
        key = make_key("nc", interaction.user.id)
        requests = load_json(REQUESTS_FILE)
        requests[key] = {
            "type": "name_change",
            "requester_id": interaction.user.id,
            "requester_name": str(interaction.user),
            "tier": self.tier,
            "team_role_id": self.team.id,
            "team_name": self.team.name,
            "old_ign": self.old_ign.value.strip(),
            "new_ign": self.new_ign.value.strip(),
            "note": self.note.value or None,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "pending"
        }
        save_json(REQUESTS_FILE, requests)

        admin_ch = get_channel_by_names(interaction.guild, "bot-requests", "admin-requests", "staff")
        if not admin_ch:
            await interaction.response.send_message(
                "Could not find an admin channel (bot-requests / admin-requests / staff). Please ask an admin to set one up.",
                ephemeral=True
            )
            return

        embed = discord.Embed(title="Name Change Request", color=PURPLE, timestamp=datetime.utcnow())
        embed.add_field(name="Requested By", value=str(interaction.user), inline=True)
        embed.add_field(name="Team", value=f"<@&{self.team.id}>", inline=True)
        embed.add_field(name="Tier", value=self.tier.capitalize(), inline=True)
        embed.add_field(name="Old IGN", value=self.old_ign.value, inline=True)
        embed.add_field(name="New IGN", value=self.new_ign.value, inline=True)
        if self.note.value:
            embed.add_field(name="Admin Note", value=self.note.value, inline=False)
        embed.set_footer(text=f"ID: {key}")

        await admin_ch.send(content=get_mod_ping(interaction.guild), embed=embed, view=RequestAdminView())
        await interaction.response.send_message("Your name change request has been sent to admins!", ephemeral=True)
        if self.original_interaction:
            try:
                await self.original_interaction.edit_original_response(content="✅ Request sent!", embed=None, view=None)
            except Exception:
                pass


# ─── Deny Reason Modal ────────────────────────────────────────────────────────

class DenyReasonModal(Modal, title="Deny Request - Add Reason"):
    reason = TextInput(
        label="Reason for denial",
        placeholder="This will be sent to the player via DM",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    def __init__(self, key, original_message):
        super().__init__()
        self.key = key
        self.original_message = original_message

    async def on_submit(self, interaction: discord.Interaction):
        requests = load_json(REQUESTS_FILE)
        if self.key not in requests:
            await interaction.response.send_message("Already processed.", ephemeral=True)
            return
        req = requests[self.key]
        req["status"] = "denied"
        req["denied_by"] = str(interaction.user)
        req["deny_reason"] = self.reason.value
        save_json(REQUESTS_FILE, requests)

        embed = self.original_message.embeds[0]
        embed.color = PURPLE
        embed.title += " - DENIED"
        embed.add_field(name="Denial Reason", value=self.reason.value, inline=False)
        embed.set_footer(text=f"Denied by {interaction.user}")
        await self.original_message.edit(embed=embed, view=None)

        try:
            user = await interaction.client.fetch_user(req["requester_id"])
            await user.send(f"Your request for **{req['team_name']}** was denied.\n**Reason:** {self.reason.value}")
        except Exception:
            pass
        await interaction.response.send_message("Request denied and player notified.", ephemeral=True)


# ─── Admin View ───────────────────────────────────────────────────────────────

def _key_from_interaction(interaction: discord.Interaction):
    """Read the request key from the embed footer (ID: <key>)."""
    try:
        footer = interaction.message.embeds[0].footer.text or ""
        return footer.removeprefix("ID: ").strip() or None
    except Exception:
        return None

class RequestAdminView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="req_approve")
    async def approve(self, interaction: discord.Interaction, button: Button):
        is_mod = any("moderator" in r.name.lower() for r in interaction.user.roles)
        if not interaction.user.guild_permissions.manage_guild and not is_mod:
            await interaction.response.send_message("Admins and moderators only.", ephemeral=True)
            return
        key = _key_from_interaction(interaction)
        if not key:
            await interaction.response.send_message("Could not read request ID from this message.", ephemeral=True)
            return
        requests = load_json(REQUESTS_FILE)
        if key not in requests:
            await interaction.response.send_message("Already processed.", ephemeral=True)
            return

        req = requests[key]
        req["status"] = "approved"
        req["approved_by"] = str(interaction.user)
        req["approved_at"] = datetime.utcnow().isoformat()
        save_json(REQUESTS_FILE, requests)

        guild = interaction.guild
        tier = req.get("tier")
        tier_role = get_faction_role(guild, tier) if tier else None
        public_ch = get_faction_channel(guild, tier, "roster-changes") if tier else get_channel_by_names(guild, "roster-changes")
        team_role = guild.get_role(req["team_role_id"])

        if req["type"] == "roster_change":
            add_member = guild.get_member(req["add_player_id"]) if req.get("add_player_id") else None
            remove_member = guild.get_member(req["remove_player_id"]) if req.get("remove_player_id") else None

            if team_role:
                if add_member:
                    try:
                        await add_member.add_roles(team_role, reason="Roster change approved")
                        if tier_role:
                            await add_member.add_roles(tier_role, reason="Roster change approved")
                    except discord.Forbidden:
                        pass
                if remove_member:
                    try:
                        await remove_member.remove_roles(team_role, reason="Roster change approved")
                    except discord.Forbidden:
                        pass

            if public_ch:
                embed = discord.Embed(title="Roster Change", color=PURPLE, timestamp=datetime.utcnow())
                embed.add_field(name="Team", value=f"<@&{req['team_role_id']}>", inline=True)
                if tier:
                    embed.add_field(name="Tier", value=tier.capitalize(), inline=True)
                if req.get("add_player_name"):
                    embed.add_field(name="Added", value=req["add_player_name"], inline=True)
                if req.get("add_player_ign"):
                    embed.add_field(name="IGN", value=req["add_player_ign"], inline=True)
                if req.get("remove_player_name"):
                    embed.add_field(name="Removed", value=req["remove_player_name"], inline=True)
                if req.get("tracker_link"):
                    embed.add_field(name="Tracker.gg", value=req["tracker_link"], inline=False)
                await public_ch.send(embed=embed)

            dm_parts = []
            if req.get("add_player_name"):
                dm_parts.append(f"**{req['add_player_name']}** added")
            if req.get("remove_player_name"):
                dm_parts.append(f"**{req['remove_player_name']}** removed")
            dm_msg = f"Your roster change for **{req['team_name']}** was approved! " + ", ".join(dm_parts) + "."



        elif req["type"] == "sub":
            sub_in = guild.get_member(req["sub_in_id"])
            if team_role and sub_in:
                try:
                    await sub_in.add_roles(team_role, reason="Sub approved")
                    if tier_role:
                        await sub_in.add_roles(tier_role, reason="Sub approved")
                except discord.Forbidden:
                    pass
                # Schedule auto-removal after SUB_ROLE_DAYS
                expiries = load_json(SUB_EXPIRY_FILE)
                expiry_key = f"{guild.id}_{sub_in.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                expiries[expiry_key] = {
                    "guild_id": guild.id,
                    "member_id": sub_in.id,
                    "team_role_id": team_role.id,
                    "tier_role_id": tier_role.id if tier_role else None,
                    "expires_at": (datetime.utcnow() + timedelta(days=SUB_ROLE_DAYS)).isoformat()
                }
                save_json(SUB_EXPIRY_FILE, expiries)

            if public_ch:
                embed = discord.Embed(title="Sub Approved", color=PURPLE, timestamp=datetime.utcnow())
                embed.add_field(name="Team", value=f"<@&{req['team_role_id']}>", inline=True)
                if tier:
                    embed.add_field(name="Tier", value=tier.capitalize(), inline=True)
                embed.add_field(name="Subbing IN", value=req.get("sub_in_name", str(req["sub_in_id"])), inline=True)
                if req.get("sub_out_name"):
                    embed.add_field(name="Sitting OUT", value=req["sub_out_name"], inline=True)
                if req.get("tracker_link"):
                    embed.add_field(name="Tracker.gg", value=req["tracker_link"], inline=False)
                await public_ch.send(embed=embed)

            dm_msg = f"Your sub request for **{req['team_name']}** was approved! **{req.get('sub_in_name')}** is subbing in."

        elif req["type"] == "name_change":
            if public_ch:
                embed = discord.Embed(title="Name Change", color=PURPLE, timestamp=datetime.utcnow())
                embed.add_field(name="Team", value=f"<@&{req['team_role_id']}>", inline=True)
                if tier:
                    embed.add_field(name="Tier", value=tier.capitalize(), inline=True)
                embed.add_field(name="Old IGN", value=req["old_ign"], inline=True)
                embed.add_field(name="New IGN", value=req["new_ign"], inline=True)
                await public_ch.send(embed=embed)

            dm_msg = f"Your name change for **{req['team_name']}** was approved! **{req['old_ign']}** is now **{req['new_ign']}**."


        else:
            dm_msg = "Your request was approved!"

        embed = interaction.message.embeds[0]
        embed.color = PURPLE
        embed.title += " - APPROVED"
        embed.set_footer(text=f"Approved by {interaction.user}")
        await interaction.response.edit_message(embed=embed, view=None)

        try:
            user = await interaction.client.fetch_user(req["requester_id"])
            await user.send(dm_msg)
        except Exception:
            pass

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="req_deny")
    async def deny(self, interaction: discord.Interaction, button: Button):
        is_mod = any("moderator" in r.name.lower() for r in interaction.user.roles)
        if not interaction.user.guild_permissions.manage_guild and not is_mod:
            await interaction.response.send_message("Admins and moderators only.", ephemeral=True)
            return
        key = _key_from_interaction(interaction)
        if not key:
            await interaction.response.send_message("Could not read request ID from this message.", ephemeral=True)
            return
        requests = load_json(REQUESTS_FILE)
        if key not in requests:
            await interaction.response.send_message("Already processed.", ephemeral=True)
            return
        await interaction.response.send_modal(DenyReasonModal(key, interaction.message))


# ─── Cog ──────────────────────────────────────────────────────────────────────

class RosterManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(RequestAdminView())
        self._sub_expiry_task = self.bot.loop.create_task(self._sub_expiry_loop())

    async def cog_unload(self):
        if hasattr(self, "_sub_expiry_task"):
            self._sub_expiry_task.cancel()

    async def _sub_expiry_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                expiries = load_json(SUB_EXPIRY_FILE)
                now = datetime.utcnow()
                removed_keys = []
                for key, entry in expiries.items():
                    if now >= datetime.fromisoformat(entry["expires_at"]):
                        guild = self.bot.get_guild(entry["guild_id"])
                        if guild:
                            member = guild.get_member(entry["member_id"])
                            if member:
                                roles_to_remove = []
                                team_role = guild.get_role(entry["team_role_id"])
                                if team_role:
                                    roles_to_remove.append(team_role)
                                if entry.get("tier_role_id"):
                                    tier_role = guild.get_role(entry["tier_role_id"])
                                    if tier_role:
                                        roles_to_remove.append(tier_role)
                                try:
                                    await member.remove_roles(*roles_to_remove, reason="Sub role expired after 10 days")
                                except discord.Forbidden:
                                    pass
                        removed_keys.append(key)
                for key in removed_keys:
                    expiries.pop(key, None)
                if removed_keys:
                    save_json(SUB_EXPIRY_FILE, expiries)
            except Exception as e:
                print(f"Sub expiry loop error: {e}")
            await asyncio.sleep(3600)

    @app_commands.command(name="rosterchange", description="Request a roster change for your team")
    @app_commands.describe(
        team="The team role",
        add_player="Player to add (optional)",
        remove_player="Player to remove — use this if they're still in the server",
        remove_player_name="Player to remove by name — use this if they LEFT the server"
    )
    async def rosterchange(
        self,
        interaction: discord.Interaction,
        team: discord.Role,
        add_player: discord.Member = None,
        remove_player: discord.Member = None,
        remove_player_name: str = None
    ):
        if not add_player and not remove_player and not remove_player_name:
            await interaction.response.send_message(
                "Please select at least an add_player or remove_player.", ephemeral=True
            )
            return
        view = FactionSelectView(
            "roster_change", team,
            add_player=add_player,
            remove_player=remove_player,
            remove_name=remove_player_name
        )
        await interaction.response.send_message(
            embed=discord.Embed(title="Which tier is this for?", color=PURPLE),
            view=view,
            ephemeral=True
        )

    @app_commands.command(name="subrequest", description="Request a sub for your team")
    @app_commands.describe(
        team="The team role",
        sub_in="Player subbing in",
        sub_out="Player sitting out — use this if they're still in the server",
        sub_out_name="Player sitting out by name — use this if they LEFT the server"
    )
    async def subrequest(
        self,
        interaction: discord.Interaction,
        team: discord.Role,
        sub_in: discord.Member,
        sub_out: discord.Member = None,
        sub_out_name: str = None
    ):
        view = FactionSelectView("sub", team, sub_in=sub_in, sub_out=sub_out, sub_out_name=sub_out_name)
        await interaction.response.send_message(
            embed=discord.Embed(title="Which tier is this for?", color=PURPLE),
            view=view,
            ephemeral=True
        )

    @app_commands.command(name="namechange", description="Request an IGN name change for your roster")
    @app_commands.describe(team="The team role")
    async def namechange(self, interaction: discord.Interaction, team: discord.Role):
        view = FactionSelectView("name_change", team)
        await interaction.response.send_message(
            embed=discord.Embed(title="Which tier is this for?", color=PURPLE),
            view=view,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(RosterManager(bot))
