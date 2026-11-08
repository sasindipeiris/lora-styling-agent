import re
from pathlib import Path

from .dataset.constants import (
    CATEGORIES,
    CLIMATE,
    DAYS,
    EVENTS,
    RULES,
    THRESHOLDS,
    TIMES,
)

ROOT = Path(__file__).resolve().parents[1]
MAX_RESULTS = 5
CHAIN = {"get_venue_info", "get_weather", "search_wardrobe", "check_color_harmony"}
TOOL_CALL_RE = re.compile(r"<tool_call>(.*?)</tool_call>", re.S)
ASSISTANT_RE = re.compile(r"<\|im_start\|>assistant\n(.*?<\|im_end\|>)", re.S)

SYSTEM_PROMPT = f"""You are a personal stylist in Sri Lanka who picks outfits from the user's own wardrobe.
Today is Monday {{today}}. Day names mean this week; "today" is monday and "tomorrow" is tuesday. Times of day are morning, afternoon and evening ("tonight" is evening).

Use the tools for any fact about venues, weather or the wardrobe; never invent them. For general fashion questions or small talk, answer directly without calling a tool.

To recommend an outfit:
1. Call get_venue_info with the venue and event type.
2. Call get_weather with the venue's city, the day and the time of day.
3. Call search_wardrobe with min_formality, max_formality and rules from get_venue_info for: a dress, or a traditional outfit, or a top and a bottom; then shoes. Also search outerwear if temp_c < {THRESHOLDS["cold_below_c"]} (min_warmth 2) or the setting is outdoor and rain_pct > {THRESHOLDS["rain_above_pct"]} (waterproof true). Avoid items with warmth 3 when temp_c >= {THRESHOLDS["hot_from_c"]}.
4. Call check_color_harmony with the chosen item ids. If it is not ok, swap an item for another search result and check again.
5. Reply with each chosen item's name and id, and briefly why the outfit fits.

Formality scale: 1 casual, 2 smart casual, 3 smart, 4 formal, 5 black tie."""


def _fn(name, description, properties, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


TOOL_SCHEMAS = [
    _fn(
        "get_venue_info",
        "Look up a venue's city, setting, required formality range and dress rules for an event.",
        {
            "venue": {
                "type": "string",
                "description": "Venue name, e.g. 'Galle Face Hotel'",
            },
            "event_type": {"type": "string", "enum": list(EVENTS)},
        },
        ["venue", "event_type"],
    ),
    _fn(
        "get_weather",
        "Get the forecast temperature (C) and rain chance (%) for a city, day and time of day this week.",
        {
            "city": {"type": "string", "enum": list(CLIMATE)},
            "day": {"type": "string", "enum": DAYS},
            "time_of_day": {"type": "string", "enum": TIMES},
        },
        ["city", "day", "time_of_day"],
    ),
    _fn(
        "search_wardrobe",
        "Search the user's wardrobe for one category. Returns at most 5 matching items.",
        {
            "category": {"type": "string", "enum": CATEGORIES},
            "min_formality": {"type": "integer", "minimum": 1, "maximum": 5},
            "max_formality": {"type": "integer", "minimum": 1, "maximum": 5},
            "rules": {
                "type": "array",
                "items": {"type": "string", "enum": list(RULES)},
                "description": "Dress rules from get_venue_info; items breaking them are excluded",
            },
            "waterproof": {"type": "boolean", "description": "Only waterproof items"},
            "min_warmth": {"type": "integer", "minimum": 1, "maximum": 3},
        },
        ["category", "min_formality"],
    ),
    _fn(
        "check_color_harmony",
        "Check whether the colors of the chosen items work together.",
        {
            "item_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Wardrobe item ids, e.g. ['D06', 'S01']",
            }
        },
        ["item_ids"],
    ),
]
