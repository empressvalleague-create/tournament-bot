# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        # Sync globally
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} global slash command(s): {[c.name for c in synced]}")
        # Also sync to every guild the bot is in
        for guild in bot.guilds:
            try:
                guild_synced = await bot.tree.sync(guild=guild)
                print(f"Synced {len(guild_synced)} command(s) to guild: {guild.name}")
            except Exception as e:
                print(f"Failed to sync to guild {guild.name}: {e}")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

async def load_cogs():
    skip_files = {"__init__.py", "faction_utils.py", "sheets.py"}
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py") and filename not in skip_files:
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"Loaded cog: {filename}")
            except Exception as e:
                print(f"Failed to load cog {filename}: {e}")

async def main():
    async with bot:
        await load_cogs()
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
