# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import os
import aiohttp

MATCH_RESULTS_CHANNEL = "match-results"
WEBHOOK_URL = os.getenv("MATCH_RESULTS_WEBHOOK", "")


class Forwarder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not WEBHOOK_URL:
            return
        if message.author.bot and message.channel.name != MATCH_RESULTS_CHANNEL:
            return
        if message.channel.name != MATCH_RESULTS_CHANNEL:
            return
        if not message.embeds:
            return

        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(WEBHOOK_URL, session=session)
            for embed in message.embeds:
                await webhook.send(
                    embed=embed,
                    username=message.guild.name,
                    avatar_url=message.guild.icon.url if message.guild.icon else discord.utils.MISSING,
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(Forwarder(bot))
