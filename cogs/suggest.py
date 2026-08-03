# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, TextInput

PURPLE = 0x9b59b6


class SuggestionModal(Modal, title="Submit a Suggestion"):
    suggestion = TextInput(
        label="Your suggestion",
        style=discord.TextStyle.paragraph,
        placeholder="Type your suggestion here...",
        min_length=10,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        channel = discord.utils.find(
            lambda c: "suggestion-box" in c.name.lower(),
            interaction.guild.text_channels
        )
        if not channel:
            await interaction.response.send_message(
                "Couldn't find a suggestion-box channel.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Anonymous Suggestion",
            description=self.suggestion.value,
            color=PURPLE,
        )
        embed.set_footer(text="Use the arrows below to vote!")

        msg = await channel.send(embed=embed)
        await msg.add_reaction("⬆️")
        await msg.add_reaction("⬇️")

        await interaction.response.send_message(
            "✅ Your suggestion was submitted anonymously!", ephemeral=True
        )


class Suggest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="suggest", description="Submit an anonymous suggestion")
    async def suggest(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SuggestionModal())


async def setup(bot: commands.Bot):
    await bot.add_cog(Suggest(bot))
