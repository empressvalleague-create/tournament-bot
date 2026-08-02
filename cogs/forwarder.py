# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import os
import aiohttp

WEBHOOK_URL = os.getenv("MATCH_RESULTS_WEBHOOK", "")


def is_results_channel(channel) -> bool:
    return "match-results" in channel.name.lower() or "match_results" in channel.name.lower()


class Forwarder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not WEBHOOK_URL:
            print("Forwarder: MATCH_RESULTS_WEBHOOK not set, skipping.")
            return
        if not isinstance(message.channel, discord.TextChannel):
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
                    await webhook.send(
                        embed=embed,
                        username=message.guild.name,
                        avatar_url=message.guild.icon.url if message.guild.icon else discord.utils.MISSING,
                    )
        except Exception as e:
            print(f"Forwarder error: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Forwarder(bot))
