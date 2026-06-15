# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.

---

## AI Tool Usage

### Instance 1 — Implementing `search_listings`

**Input given to Claude:**
The Tool 1 spec from `planning.md` (input parameters, return type, failure mode — "returns `[]`, never raises"), plus the `load_listings()` signature from `utils/data_loader.py`, and the instruction that size matching must be case-insensitive and handle substrings like `"S/M"` containing `"M"`.

**What it produced:**
A working implementation that loaded listings, filtered by price and size, scored each listing by keyword overlap across `title`, `description`, and `style_tags`, dropped zero-score items, and sorted descending by score.

**What I changed:**
The generated code called `listing['brand'].lower()` without guarding against `None` (several listings have `"brand": null` in the JSON). This crashed immediately on the first real query. I overrode that line to `(listing['brand'] or '').lower()` before using the output. I also removed the `category` field from the searchable text the AI included — it matched too broadly (e.g., searching "top" returned every item in the `tops` category regardless of keyword relevance).

---

### Instance 2 — Implementing `run_agent` (planning loop)

**Input given to Claude:**
The 7 numbered steps in the `run_agent` docstring in `agent.py`, the `_new_session` dict definition showing all session fields, and the instruction to use regex parsing for Step 2 (no extra LLM call) and to return early with `session["error"]` set if `search_listings` returns an empty list.

**What it produced:**
A complete planning loop: regex extraction of `max_price` (handling `under $30`, `max $50`, `$25` patterns) and `size` (handling `size M` and standalone tokens like `XS`, `S/M`, `XXL`), the early-return no-results branch, and sequential calls to `suggest_outfit` and `create_fit_card` with session dict state passed between them.

**What I changed:**
The initial regex for `max_price` matched the first number it found in the query, which caused `"size XXS under $5"` to parse `max_price=5` correctly but also matched the `5` in `XXS` if the order was reversed. I verified this with the no-results test case and confirmed the regex order was safe for the test inputs. I also added explicit `id()` checks and spy wrappers during testing to confirm `session["selected_item"]` was the same object passed into `suggest_outfit` — not a copy — since the AI's description said "passes state between tools" but I wanted to verify no intermediate re-fetching was happening.
