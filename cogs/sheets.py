# -*- coding: utf-8 -*-
"""
Google Sheets integration for roster management.

Sheet structure (each team occupies 3 rows):
  Row 1: [empty] | SEED | TEAM | MANAGER CONTACT | PLAYER1 IGN | PLAYER2 IGN | ... | PLAYER7 IGN | POINT AVG
  Row 2: [rank]  | seed | -Announced-        | rank scores ...
  Row 3: [empty] | [empty] | [empty] | [empty] | discord_name1 | discord_name2 | ...

Columns (1-indexed):
  A=1, B=2(SEED), C=3(TEAM), D=4(MANAGER), E=5(P1 IGN), F=6(P2 IGN), G=7(P3 IGN),
  H=8(P4 IGN), I=9(P5 IGN), J=10(P6 IGN), K=11(P7 IGN), L=12(POINT AVG)

Discord names live on Row+2, same columns as IGNs.
"""

import discord
import gspread
import os
import json
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

PLAYER_COLS = [5, 6, 7, 8, 9, 10, 11]  # columns E–K (1-indexed)

DISMISS_SHEET_NAME = os.getenv("DISMISS_SHEET_NAME", "MOD - DISMISS")
DEVOUR_SHEET_NAME  = os.getenv("DEVOUR_SHEET_NAME",  "MOD - DEVOUR")


def get_client():
    """Build a gspread client from the GOOGLE_CREDENTIALS env var (JSON string)."""
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise RuntimeError("GOOGLE_CREDENTIALS environment variable is not set.")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def get_sheet(faction: str):
    """Return the worksheet for the given faction ('devour' or 'dismiss')."""
    gc = get_client()
    name = DEVOUR_SHEET_NAME if faction == "devour" else DISMISS_SHEET_NAME
    return gc.open(name).sheet1


def find_team_start_row(sheet, team_name: str) -> int | None:
    """
    Find the first row of a team block by searching column C for the team name.
    Returns the 1-indexed row number, or None if not found.
    """
    col_c = sheet.col_values(3)  # column C = index 3
    for i, val in enumerate(col_c):
        if val.strip().lower() == team_name.strip().lower():
            return i + 1  # convert to 1-indexed
    return None


def get_team_players(sheet, start_row: int) -> list[dict]:
    """
    Return a list of player dicts for a team, reading IGN (start_row) and
    discord name (start_row + 2) for each player column.
    """
    ign_row    = sheet.row_values(start_row)
    discord_row = sheet.row_values(start_row + 2)

    players = []
    for col in PLAYER_COLS:
        idx = col - 1  # convert to 0-indexed for list access
        ign     = ign_row[idx].strip()     if idx < len(ign_row)     else ""
        discord = discord_row[idx].strip() if idx < len(discord_row) else ""
        if ign or discord:
            players.append({"col": col, "ign": ign, "discord": discord})
    return players


def find_player_col(sheet, start_row: int, search: str) -> int | None:
    """
    Find the column of a player by matching either their IGN or discord name.
    Returns the column number (1-indexed) or None.
    """
    search = search.strip().lower()
    ign_row     = sheet.row_values(start_row)
    discord_row = sheet.row_values(start_row + 2)
    for col in PLAYER_COLS:
        idx = col - 1
        ign     = ign_row[idx].strip().lower()     if idx < len(ign_row)     else ""
        discord = discord_row[idx].strip().lower() if idx < len(discord_row) else ""
        if search in (ign, discord):
            return col
    return None


def first_empty_player_col(sheet, start_row: int) -> int | None:
    """Return the column number of the first empty player slot, or None if full."""
    ign_row = sheet.row_values(start_row)
    for col in PLAYER_COLS:
        idx = col - 1
        val = ign_row[idx].strip() if idx < len(ign_row) else ""
        if not val:
            return col
    return None


# ─── Public helpers called by roster.py ──────────────────────────────────────

def sheets_add_player(faction: str, team_name: str, ign: str, discord_name: str) -> str:
    """
    Add a player to the first empty slot for a team.
    Returns a human-readable result string.
    """
    sheet = get_sheet(faction)
    start = find_team_start_row(sheet, team_name)
    if start is None:
        return f"Could not find team **{team_name}** in the {faction.capitalize()} sheet."

    col = first_empty_player_col(sheet, start)
    if col is None:
        return f"**{team_name}** already has 7 players — no empty slot available."

    sheet.update_cell(start,     col, ign)
    sheet.update_cell(start + 2, col, discord_name)
    return f"Added **{ign}** / `{discord_name}` to **{team_name}** in column {col}."


def sheets_remove_player(faction: str, team_name: str, search: str) -> str:
    """
    Remove a player by IGN or discord name, clearing both the IGN and discord rows.
    Returns a human-readable result string.
    """
    sheet = get_sheet(faction)
    start = find_team_start_row(sheet, team_name)
    if start is None:
        return f"Could not find team **{team_name}** in the {faction.capitalize()} sheet."

    col = find_player_col(sheet, start, search)
    if col is None:
        return f"Could not find player **{search}** on **{team_name}**."

    ign_row     = sheet.row_values(start)
    discord_row = sheet.row_values(start + 2)
    idx = col - 1
    old_ign     = ign_row[idx]     if idx < len(ign_row)     else ""
    old_discord = discord_row[idx] if idx < len(discord_row) else ""

    sheet.update_cell(start,     col, "")
    sheet.update_cell(start + 2, col, "")
    return f"Removed **{old_ign}** / `{old_discord}` from **{team_name}**."


def sheets_update_ign(faction: str, team_name: str, old_ign: str, new_ign: str) -> str:
    """
    Update a player's IGN (row 1 only). Discord name row stays the same.
    Returns a human-readable result string.
    """
    sheet = get_sheet(faction)
    start = find_team_start_row(sheet, team_name)
    if start is None:
        return f"Could not find team **{team_name}** in the {faction.capitalize()} sheet."

    col = find_player_col(sheet, start, old_ign)
    if col is None:
        return f"Could not find player **{old_ign}** on **{team_name}**."

    sheet.update_cell(start, col, new_ign)
    return f"Updated IGN from **{old_ign}** to **{new_ign}** on **{team_name}**."


def sheets_get_roster(faction: str, team_name: str) -> str:
    """Return a formatted roster string for a team."""
    sheet = get_sheet(faction)
    start = find_team_start_row(sheet, team_name)
    if start is None:
        return f"Could not find team **{team_name}** in the {faction.capitalize()} sheet."
    players = get_team_players(sheet, start)
    if not players:
        return f"**{team_name}** has no players on the sheet."
    lines = [f"• **{p['ign']}** (`{p['discord']}`)" for p in players]
    return "\n".join(lines)
