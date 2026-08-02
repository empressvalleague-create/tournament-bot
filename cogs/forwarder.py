# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import os
import aiohttp

WEBHOOK_URL = os.getenv("MATCH_RESULTS_WEBHOOK", "")


import re

def resolve_mentions(embed: discord.Embed, guild: discord.Guild) -> discord.Embed:
    """Replace <@&role_id> and <@user_id> with their names so they render in other servers."""
    def replace(text: str) -> str:
        if not text:
            return text
        def sub_role(m):
            role = guild.get_role(int(m.group(1)))
            return role.name if role else m.group(0)
        def sub_user(m):
            member = guild.get_member(int(m.group(1)))
            return member.display_name if member else m.group(0)
        text = re.sub(r"<@&(\d+)>", sub_role, text)
        text = re.sub(r"<@!?(\d+)>", sub_user, text)
        return text

    new = embed.copy()
    if embed.title:
        new.title = replace(embed.title)
    if embed.description:
        new.description = replace(embed.description)
    new.clear_fields()
    for field in embed.fields:
        new.add_field(name=replace(field.name), value=replace(field.value), inline=field.inline)
    if embed.footer.text:
        new.set_footer(text=replace(embed.footer.text), icon_url=embed.footer.icon_url)
    return new


def is_results_channel(channel) -> bool:
    return "match-times" in channel.name.lower()


class Forwarder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print(f"Forwarder cog loaded. Webhook set: {bool(WEBHOOK_URL)}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not isinstance(message.channel, discord.TextChannel):
            return
        # Debug: log every message channel name so we can confirm the event fires
        print(f"Forwarder on_message: #{message.channel.name} | embeds={len(message.embeds)} | author_bot={message.author.bot}")

        if not WEBHOOK_URL:
            print("Forwarder: MATCH_RESULTS_WEBHOOK not set.")
            return
        if not is_results_channel(message.channel):
            return
        if not message.embeds:
            return

        print(f"Forwarder: forwarding {len(message.embeds)} embed(s) from #{message.channel.name}")
        try:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(WEBHOOK_URL, session=session)
                for embed in message.embeds:
                    sent = await webhook.send(
                        embed=resolve_mentions(embed, message.guild),
                        username=message.guild.name,
                        avatar_url=message.guild.icon.url if message.guild.icon else discord.utils.MISSING,
                        wait=True,
                    )
                    for emoji in ("✅", "❌"):
                        await self.bot.http.add_reaction(sent.channel_id, sent.id, emoji)
        except Exception as e:
            print(f"Forwarder error: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Forwarder(bot))
