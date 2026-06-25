# -*- coding: utf-8 -*-
import discord

def get_faction_category(guild: discord.Guild, faction: str):
    if not faction:
        return None
    return discord.utils.find(lambda c: faction in c.name.lower(), guild.categories)

def get_faction_role(guild: discord.Guild, faction: str):
    if not faction:
        return None
    return discord.utils.find(lambda r: faction in r.name.lower(), guild.roles)

def get_faction_channel(guild: discord.Guild, faction: str, channel_name: str):
    category = get_faction_category(guild, faction)
    if category:
        ch = discord.utils.find(
            lambda c: c.name == channel_name and c.category_id == category.id,
            guild.text_channels
        )
        if ch:
            return ch
    return discord.utils.get(guild.text_channels, name=channel_name)

def get_member_faction(member: discord.Member):
    for role in member.roles:
        name_lower = role.name.lower()
        if "devour" in name_lower:
            return "devour", role
        if "dismiss" in name_lower:
            return "dismiss", role
    return None, None
