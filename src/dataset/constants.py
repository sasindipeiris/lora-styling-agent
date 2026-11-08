"""Static data: mock DB content and request phrasings."""

import re

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
TIMES = ["morning", "afternoon", "evening"]
CATEGORIES = ["top", "bottom", "dress", "traditional", "shoes", "outerwear"]
KINDS = ("no_tool", "single_tool", "full_outfit")
ITEM_RE = re.compile(r"\b[TBDROS]\d{2}\b")
RECOVERY_P = 0.3  # share of outfit traces that fix a color clash
ERROR_P = 0.15  # share of venue lookups that first fail on the user's wording, then correct it

# ---- mock DB ----
THRESHOLDS = {
    "cold_below_c": 20,
    "rain_above_pct": 50,
    "hot_from_c": 30,
    "max_overdress": 1,
}

RULES = {
    "closed_shoes": "no sandals",
    "no_heels": "no heeled shoes",
    "no_white": "no white items",
    "covered_shoulders_knees": "no sleeveless or short-hem items",
}

EVENTS = {
    "interview": {"formality": 4, "rules": ["closed_shoes"]},
    "wedding": {"formality": 4, "rules": ["no_white"]},
    "gala": {"formality": 5, "rules": []},
    "dinner": {"formality": 3, "rules": []},
    "brunch": {"formality": 2, "rules": []},
    "day_out": {"formality": 1, "rules": []},
    "trip": {"formality": 1, "rules": ["no_heels"]},
}


def _venue(name, city, setting, formality, events, rules=(), aliases=()):
    return {
        "name": name,
        "city": city,
        "setting": setting,
        "base_formality": formality,
        "events": list(events),
        "rules": list(rules),
        "aliases": list(aliases),
    }


VENUES = {
    "galle_face_hotel": _venue(
        "Galle Face Hotel",
        "Colombo",
        "indoor",
        4,
        ["gala", "wedding", "dinner"],
        aliases=["galle face", "gfh"],
    ),
    "cinnamon_grand": _venue(
        "Cinnamon Grand Ballroom",
        "Colombo",
        "indoor",
        4,
        ["gala", "wedding"],
        aliases=["cinnamon grand", "cinnamon ballroom"],
    ),
    "world_trade_center": _venue(
        "World Trade Center",
        "Colombo",
        "indoor",
        4,
        ["interview"],
        ["closed_shoes"],
        aliases=["wtc", "world trade centre"],
    ),
    "ministry_of_crab": _venue(
        "Ministry of Crab",
        "Colombo",
        "indoor",
        3,
        ["dinner"],
        aliases=["ministry of crab restaurant"],
    ),
    "barefoot_cafe": _venue(
        "Barefoot Garden Cafe",
        "Colombo",
        "covered",
        2,
        ["brunch"],
        aliases=["barefoot", "barefoot cafe"],
    ),
    "viharamahadevi_park": _venue(
        "Viharamahadevi Park",
        "Colombo",
        "outdoor",
        1,
        ["day_out"],
        aliases=["viharamahadevi", "town hall park"],
    ),
    "temple_of_the_tooth": _venue(
        "Temple of the Tooth",
        "Kandy",
        "covered",
        2,
        ["day_out", "trip"],
        ["covered_shoulders_knees"],
        aliases=["dalada maligawa", "sri dalada maligawa"],
    ),
    "earls_regency": _venue(
        "Earl's Regency",
        "Kandy",
        "indoor",
        4,
        ["wedding", "dinner"],
        aliases=["earls regency", "earl's regency hotel"],
    ),
    "galle_fort": _venue(
        "Galle Fort",
        "Galle",
        "outdoor",
        1,
        ["day_out", "trip"],
        ["no_heels"],
        aliases=["the fort", "galle dutch fort"],
    ),
    "jetwing_lighthouse": _venue(
        "Jetwing Lighthouse",
        "Galle",
        "covered",
        3,
        ["wedding", "dinner", "brunch"],
        aliases=["lighthouse hotel", "jetwing"],
    ),
    "unawatuna_beach": _venue(
        "Unawatuna Beach",
        "Galle",
        "outdoor",
        1,
        ["day_out"],
        ["no_heels"],
        aliases=["unawatuna"],
    ),
    "grand_hotel": _venue(
        "Grand Hotel",
        "Nuwara Eliya",
        "indoor",
        4,
        ["gala", "dinner"],
        aliases=["the grand hotel", "grand hotel nuwara eliya"],
    ),
    "gregory_lake": _venue(
        "Gregory Lake",
        "Nuwara Eliya",
        "outdoor",
        1,
        ["day_out"],
        aliases=["lake gregory"],
    ),
    "nine_arch_bridge": _venue(
        "Nine Arch Bridge",
        "Ella",
        "outdoor",
        1,
        ["trip"],
        ["closed_shoes"],
        aliases=["nine arches", "ella bridge"],
    ),
}


def _item(
    id,
    name,
    category,
    color,
    formality,
    warmth=1,
    waterproof=False,
    coverage=None,
    shoe_type=None,
):
    d = {
        "id": id,
        "name": name,
        "category": category,
        "color": color,
        "formality": formality,
        "warmth": warmth,
        "waterproof": waterproof,
    }
    if coverage:
        d["coverage"] = coverage
    if shoe_type:
        d["shoe_type"] = shoe_type
    return d


WARDROBE = [
    _item("T01", "linen shirt", "top", "white", 2),
    _item("T02", "crop top", "top", "yellow", 1, coverage="sleeveless"),
    _item("T03", "striped t-shirt", "top", "navy", 1),
    _item("T04", "silk blouse", "top", "cream", 3),
    _item("T05", "chiffon blouse", "top", "pink", 3),
    _item("T06", "formal blouse", "top", "white", 4),
    _item("T07", "shell top", "top", "navy", 4, coverage="sleeveless"),
    _item("T08", "off-shoulder top", "top", "red", 3, coverage="sleeveless"),
    _item("T09", "cotton kurti", "top", "green", 2),
    _item("T10", "turtleneck sweater", "top", "grey", 2, warmth=3),
    _item("B01", "jeans", "bottom", "blue", 1),
    _item("B02", "denim shorts", "bottom", "blue", 1, coverage="short_hem"),
    _item("B03", "linen trousers", "bottom", "beige", 2),
    _item("B04", "tailored trousers", "bottom", "black", 4),
    _item("B05", "pencil skirt", "bottom", "grey", 4),
    _item("B06", "floral midi skirt", "bottom", "orange", 2),
    _item("B07", "palazzo pants", "bottom", "cream", 3),
    _item("B08", "cargo pants", "bottom", "beige", 1),
    _item("B09", "satin midi skirt", "bottom", "maroon", 3),
    _item("D01", "floral sundress", "dress", "yellow", 1, coverage="sleeveless"),
    _item("D02", "cotton maxi dress", "dress", "teal", 2, coverage="sleeveless"),
    _item("D03", "shirt dress", "dress", "blue", 2),
    _item("D04", "wrap dress", "dress", "black", 3),
    _item("D05", "cocktail dress", "dress", "red", 4, coverage="sleeveless"),
    _item("D06", "sheath dress", "dress", "navy", 4),
    _item("D07", "evening gown", "dress", "emerald", 5, coverage="sleeveless"),
    _item("D08", "velvet gown", "dress", "black", 5, warmth=2),
    _item("D09", "midi dress", "dress", "pink", 3),
    _item("D10", "lace dress", "dress", "white", 4),
    _item("R01", "Kanchipuram silk saree", "traditional", "maroon", 5),
    _item("R02", "Kandyan osariya", "traditional", "purple", 5),
    _item("R03", "handloom cotton saree", "traditional", "orange", 3),
    _item("R04", "georgette party saree", "traditional", "pink", 4),
    _item("R05", "kurta set", "traditional", "green", 2),
    _item("R06", "batik saree", "traditional", "blue", 3),
    _item("S01", "patent pumps", "shoes", "black", 4, shoe_type="heels"),
    _item("S02", "stilettos", "shoes", "gold", 5, shoe_type="heels"),
    _item("S03", "strappy heels", "shoes", "silver", 5, shoe_type="heels"),
    _item("S04", "block heels", "shoes", "beige", 4, shoe_type="heels"),
    _item("S05", "wedges", "shoes", "brown", 3, shoe_type="heels"),
    _item("S06", "leather loafers", "shoes", "brown", 3, shoe_type="flats"),
    _item("S07", "ballet flats", "shoes", "black", 2, shoe_type="flats"),
    _item("S08", "leather sneakers", "shoes", "white", 2, shoe_type="sneakers"),
    _item("S09", "canvas sneakers", "shoes", "navy", 1, shoe_type="sneakers"),
    _item("S10", "flat sandals", "shoes", "brown", 2, shoe_type="sandals"),
    _item("S11", "flip-flops", "shoes", "black", 1, shoe_type="sandals"),
    _item("S12", "hiking boots", "shoes", "brown", 1, shoe_type="boots"),
    _item("S13", "embellished sandals", "shoes", "gold", 4, shoe_type="sandals"),
    _item("O01", "blazer", "outerwear", "black", 4, warmth=2),
    _item("O02", "trench coat", "outerwear", "beige", 3, warmth=2, waterproof=True),
    _item("O03", "cashmere evening wrap", "outerwear", "cream", 5, warmth=2),
    _item("O04", "velvet evening coat", "outerwear", "navy", 5, warmth=3),
    _item("O05", "wool coat", "outerwear", "grey", 4, warmth=3),
    _item("O06", "cardigan", "outerwear", "cream", 2, warmth=2),
    _item("O07", "pashmina shawl", "outerwear", "maroon", 3, warmth=2),
    _item("O08", "denim jacket", "outerwear", "blue", 1, warmth=2),
    _item("O09", "rain poncho", "outerwear", "yellow", 1, waterproof=True),
    _item(
        "O10", "padded rain jacket", "outerwear", "navy", 1, warmth=2, waterproof=True
    ),
    _item("O11", "windbreaker", "outerwear", "green", 2, waterproof=True),
    _item("O12", "fleece hoodie", "outerwear", "grey", 1, warmth=3),
    _item(
        "O13", "waterproof jacket", "outerwear", "black", 2, warmth=2, waterproof=True
    ),
]

COLOR_RULES = {
    "neutrals": [
        "black",
        "white",
        "navy",
        "grey",
        "beige",
        "brown",
        "cream",
        "gold",
        "silver",
    ],
    "clashes": [
        ["red", "orange"],
        ["red", "pink"],
        ["orange", "pink"],
        ["purple", "orange"],
        ["green", "red"],
        ["yellow", "pink"],
        ["maroon", "red"],
    ],
    "max_accent_colors": 2,
}

# mean temp and rain % for (morning, afternoon, evening)
CLIMATE = {
    "Colombo": ((27, 31, 28), (25, 45, 50)),
    "Kandy": ((22, 28, 23), (20, 45, 40)),
    "Galle": ((27, 30, 28), (25, 40, 45)),
    "Nuwara Eliya": ((12, 18, 11), (30, 50, 45)),
    "Ella": ((17, 24, 18), (25, 45, 40)),
}

# guaranteed hard cases
PINNED = {
    ("Colombo", "friday", "evening"): {"temp_c": 27, "rain_pct": 80},
    ("Colombo", "saturday", "evening"): {"temp_c": 26, "rain_pct": 75},
    ("Galle", "sunday", "afternoon"): {"temp_c": 33, "rain_pct": 10},
    ("Galle", "saturday", "morning"): {"temp_c": 28, "rain_pct": 70},
    ("Nuwara Eliya", "saturday", "evening"): {"temp_c": 9, "rain_pct": 60},
    ("Kandy", "saturday", "morning"): {"temp_c": 23, "rain_pct": 70},
    ("Ella", "saturday", "morning"): {"temp_c": 15, "rain_pct": 65},
}

# ---- phrasings: train and test never share a template ----
FULL_Q = {
    "train": [
        "What should I wear to {event} at {venue} {when}?",
        "I'm going to {event} at {venue} {when}. Pick an outfit from my wardrobe.",
        "Help me choose an outfit for {event} at {venue} {when}.",
        "Can you style me for {event} at {venue} {when}?",
        "I have {event} at {venue} {when}. What do I wear?",
    ],
    "test": [
        "Got {event} at {venue} {when} - dress me from my closet.",
        "Could you put together a look for {event} at {venue} {when}?",
        "Need an outfit: {event}, {venue}, {when}.",
    ],
}
# last phrase is test-only
EVENT_WORDS = {
    "interview": ["a job interview", "an interview", "an interview for a new job"],
    "wedding": ["a wedding", "my cousin's wedding", "a friend's wedding"],
    "gala": ["a gala", "a charity gala", "an awards gala night"],
    "dinner": ["a dinner", "dinner with friends", "a dinner date"],
    "brunch": ["brunch", "a brunch with friends", "a birthday brunch"],
    "day_out": ["a day out", "a relaxed day out", "a casual outing"],
    "trip": ["a trip", "a sightseeing trip", "an excursion"],
}
DAY_WORDS = {"train": ["on {D}", "this {D}"], "test": ["{D}", "coming {D}"]}
TIME_WORDS = {
    "train": {
        "morning": "in the morning",
        "afternoon": "in the afternoon",
        "evening": "in the evening",
    },
    "test": {"morning": "morning", "afternoon": "afternoon", "evening": "night"},
}

VENUE_Q = {
    "train": [
        "What's the dress code for {event} at {venue}?",
        "How formal should I be for {event} at {venue}?",
    ],
    "test": ["Any dress rules for {event} at {venue}?"],
}
WEATHER_Q = {
    "train": ["What's the weather in {city} {when}?", "Will it rain in {city} {when}?"],
    "test": ["Forecast for {city} {when}?"],
}
SEARCH_Q = {
    "train": ["Which {level} {cat} do I have?", "Show me my {level} {cat}."],
    "test": ["List the {level} {cat} in my closet."],
}
SEARCH_SPECIAL_Q = {
    "train": [
        ("Do I have any waterproof jackets?", {"waterproof": True}),
        ("What warm layers do I own?", {"min_warmth": 2}),
    ],
    "test": [
        ("Anything in my wardrobe that keeps the rain off?", {"waterproof": True})
    ],
}
COLOR_Q = {
    "train": ["Do {ids} go together?", "Check the colors of {ids}."],
    "test": ["Will {ids} match?"],
}
LEVELS = {
    "casual": (1, 2),
    "smart casual": (2, 3),
    "smart": (3, 4),
    "formal": (4, 5),
    "black tie": (5, 5),
}
CAT_WORDS = {
    "top": "tops",
    "bottom": "skirts and trousers",
    "dress": "dresses",
    "traditional": "sarees and traditional outfits",
    "shoes": "shoes",
    "outerwear": "jackets and layers",
}

SLOTS = {
    "fabric": ["silk", "linen", "cotton", "chiffon", "georgette"],
    "garment": ["saree", "blouse", "dress", "shirt"],
    "n": [3, 4, 5],
    "tone": ["warm", "cool", "olive", "deep"],
}
NO_TOOL = {
    "train": [
        (
            "How do I stop my {fabric} {garment} from wrinkling?",
            "Hang it up right after wearing, steam it instead of ironing on high heat, and give it space in the wardrobe so the {fabric} can breathe.",
        ),
        (
            "How do I wash a {fabric} {garment}?",
            "Hand wash the {fabric} {garment} in cold water with a mild detergent, don't wring it, and dry it flat in the shade.",
        ),
        (
            "What's the difference between smart casual and formal?",
            "Smart casual is polished but relaxed, like neat trousers or a midi skirt with a nice top. Formal means tailored pieces, dresses or sarees in richer fabrics, with dressier shoes.",
        ),
        (
            "How should I pack for a {n}-day trip?",
            "Pack pieces that mix and match: {n} tops, two bottoms, one dress, comfortable walking shoes and one light layer. Rolling clothes saves space.",
        ),
        (
            "Any tips for dressing in humid weather?",
            "Choose breathable fabrics like cotton and linen, loose fits and lighter colors, and skip heavy layers.",
        ),
        (
            "How do I drape a saree neatly?",
            "Make even pleats, tuck them firmly at the waist, pin the pallu at the shoulder, and use a few safety pins so everything stays in place.",
        ),
        (
            "What colors suit a {tone} skin tone?",
            "Many {tone} skin tones look great in jewel tones and earthy shades. Try colors near your face in daylight and keep the ones that make you look brighter.",
        ),
        (
            "What does black tie mean?",
            "Black tie is the most formal evening dress code: floor-length gowns or rich silk sarees with elegant heels.",
        ),
        (
            "Hi!",
            "Hi! Tell me your event, venue, day and time, and I'll pick an outfit from your wardrobe.",
        ),
        ("Thanks for the help!", "You're welcome, enjoy your event!"),
        (
            "Who are you?",
            "I'm your personal stylist. Tell me where you're going and when, and I'll build an outfit from your wardrobe.",
        ),
    ],
    "test": [
        (
            "Is {fabric} a good choice for a hot day?",
            "Light, breathable fabrics work best in the heat; if the {fabric} is thin and loose it can be comfortable, otherwise choose cotton or linen.",
        ),
        (
            "How can I make a simple dress look dressier?",
            "Add statement jewellery, heels and a structured layer like a blazer or an elegant wrap.",
        ),
        (
            "How should I store {fabric} {garment}s?",
            "Store {fabric} {garment}s clean and fully dry, folded in breathable cotton bags away from direct sunlight.",
        ),
        (
            "What's a cocktail dress code?",
            "Cocktail is between smart and formal: a knee or midi length dress or a party saree with dressy shoes.",
        ),
        (
            "Good morning!",
            "Good morning! Where are you heading? I can put an outfit together for you.",
        ),
        ("Cheers, that was useful.", "Glad it helped, have a great time!"),
        (
            "What jewellery goes well with a {fabric} saree?",
            "Gold or antique-finish pieces suit most {fabric} sarees; keep it to one statement piece so the saree stays the focus.",
        ),
        (
            "Should my belt match my shoes?",
            "It looks polished when the belt and shoes share a color family, but it isn't a strict rule for casual outfits.",
        ),
        (
            "How do I keep white clothes bright?",
            "Wash whites separately in cool water, avoid overloading the machine, and dry them in indirect sunlight.",
        ),
        (
            "What's the best way to fold a {garment} for travel?",
            "Fold the {garment} along its natural seams with tissue paper between folds, or roll it loosely to avoid sharp creases.",
        ),
        (
            "How do I pick the right handbag size?",
            "Choose a bag in proportion to your frame and the occasion: a small clutch for evening events, a larger tote for day trips.",
        ),
        (
            "Hello there!",
            "Hello! Tell me about your plans and I'll put an outfit together from your wardrobe.",
        ),
    ],
}
