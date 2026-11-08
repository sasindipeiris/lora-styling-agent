"""Build data/mock_db.json.  Run: python -m src.dataset.build_db"""

import json
import random
from datetime import date, timedelta

from ..constants import ROOT
from ..utils import CFG
from .constants import (
    CLIMATE,
    COLOR_RULES,
    DAYS,
    EVENTS,
    PINNED,
    RULES,
    THRESHOLDS,
    TIMES,
    VENUES,
    WARDROBE,
)


def build_weather(rng):
    def entry(city, day, i):
        temps, rains = CLIMATE[city]
        temp = temps[i] + rng.randint(-2, 2)
        rain = max(0, min(95, 5 * round((rains[i] + rng.randint(-25, 25)) / 5)))
        return {
            "temp_c": temp,
            "rain_pct": rain,
            **PINNED.get((city, day, TIMES[i]), {}),
        }

    return {
        city: {
            day: {t: entry(city, day, i) for i, t in enumerate(TIMES)} for day in DAYS
        }
        for city in CLIMATE
    }


def check_integrity(db):
    ids = [it["id"] for it in db["wardrobe"]]
    assert len(ids) == len(set(ids)), "duplicate wardrobe ids"
    for key, v in db["venues"].items():
        assert v["city"] in db["weather"], f"{key}: unknown city {v['city']}"
        assert set(v["events"]) <= set(db["events"]), f"{key}: unknown event"
        assert set(v["rules"]) <= set(db["rules"]), f"{key}: unknown rule"


def main():
    today = date.fromisoformat(CFG["today"])
    assert today.weekday() == 0, "config 'today' must be a Monday"

    db = {
        "today": CFG["today"],
        "days": {
            d: (today + timedelta(days=i)).isoformat() for i, d in enumerate(DAYS)
        },
        "thresholds": THRESHOLDS,
        "rules": RULES,
        "events": EVENTS,
        "venues": VENUES,
        "weather": build_weather(random.Random(CFG["seed"])),
        "wardrobe": WARDROBE,
        "color_rules": COLOR_RULES,
    }
    check_integrity(db)

    out = ROOT / CFG["paths"]["db"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(db, indent=2))
    print(
        f"wrote {out}: {len(VENUES)} venues, {len(EVENTS)} events, {len(WARDROBE)} items"
    )


if __name__ == "__main__":
    main()
