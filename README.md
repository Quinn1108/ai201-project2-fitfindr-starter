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

## Tools

### `search_listings(description, size, max_price)` — `tools.py`
Searches the mock listings dataset for secondhand items matching a natural language description, with optional size and price filters.

| Parameter | Type | Purpose |
|---|---|---|
| `description` | `str` | Free-text keywords describing the item (e.g. `"vintage graphic tee"`) |
| `size` | `str \| None` | Size to filter by — case-insensitive substring match (e.g. `"M"` matches `"S/M"`); `None` skips size filtering |
| `max_price` | `float \| None` | Maximum price inclusive in USD; `None` skips price filtering |

**Returns:** A list of listing dicts sorted by keyword relevance (highest first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand`, `platform`. Returns `[]` if nothing matches — never raises.

---

### `suggest_outfit(new_item, wardrobe)` — `tools.py`
Given the selected thrifted item and the user's wardrobe, calls the Groq LLM to suggest 1–2 complete outfits.

| Parameter | Type | Purpose |
|---|---|---|
| `new_item` | `dict` | A single listing dict from `search_listings` results |
| `wardrobe` | `dict` | Wardrobe dict with an `"items"` key containing a list of wardrobe item dicts |

**Returns:** A non-empty string with outfit suggestions. If the wardrobe is empty, returns general styling advice for the item instead of outfit combinations.

---

### `create_fit_card(outfit, new_item)` — `tools.py`
Generates a short, shareable Instagram/TikTok-style caption for the thrifted find.

| Parameter | Type | Purpose |
|---|---|---|
| `outfit` | `str` | The outfit suggestion string from `suggest_outfit` |
| `new_item` | `dict` | The selected listing dict (used for title, price, platform) |

**Returns:** A 2–4 sentence caption string that mentions the item name, price, and platform naturally. If `outfit` is empty or whitespace-only, returns a descriptive error string instead of raising.

---

## Planning Loop

The agent uses a fixed conditional pipeline — it does not call all three tools unconditionally:

1. **Parse** the user query with regex to extract `description`, `size`, and `max_price`. No LLM call at this step.
2. **Call `search_listings`** with the parsed parameters.
3. **Check results:** if the list is empty, set `session["error"]` to a message telling the user what to try next, and **return immediately** — `suggest_outfit` and `create_fit_card` are never called.
4. If results exist, **select `results[0]`** as `selected_item`.
5. **Call `suggest_outfit`** with `selected_item` and the user's wardrobe.
6. **Call `create_fit_card`** with the outfit string and `selected_item`.
7. Return the completed session.

The key decision point is step 3: the agent checks `len(search_results) == 0` and branches to an early return rather than proceeding with empty input.

---

## State Management

All state lives in a single session dict created at the start of each `run_agent()` call. No state persists between calls. Values are written once by each step and read by the next — no re-prompting or re-fetching:

| Field | Written by | Read by |
|---|---|---|
| `parsed` | Step 2 (regex parse) | Step 3 (`search_listings` args) |
| `search_results` | Step 3 (`search_listings`) | Step 3 (empty check), Step 4 (select item) |
| `selected_item` | Step 4 (assignment from `results[0]`) | Step 5 (`suggest_outfit`), Step 6 (`create_fit_card`) |
| `outfit_suggestion` | Step 5 (`suggest_outfit`) | Step 6 (`create_fit_card`), final output |
| `fit_card` | Step 6 (`create_fit_card`) | Final output |
| `error` | Step 3 (if no results) | Caller checks before reading other fields |

`selected_item` is the same dict object passed into both `suggest_outfit` and `create_fit_card` — verified with Python `id()` checks during testing to confirm no intermediate copying or re-fetching occurs.

---

## Error Handling

| Tool | Failure mode | Agent response |
|---|---|---|
| `search_listings` | Returns empty list (no keyword/price/size match) | Sets `session["error"]` with a specific message naming the query and suggesting what to broaden; returns immediately without calling the remaining tools |
| `suggest_outfit` | Wardrobe is empty (`wardrobe["items"] == []`) | Calls LLM with a general styling prompt instead of a wardrobe-specific one; still returns a non-empty string and continues to `create_fit_card` |
| `create_fit_card` | `outfit` is empty or whitespace-only | Returns a descriptive error string without calling the LLM; does not raise |

**Concrete example from testing:** running `run_agent("designer ballgown size XXS under $5", wardrobe)` returns:
```
session["error"] = "No listings found matching 'designer ballgown size XXS under $5'. Try broadening your search — different keywords, a higher price, or no size filter."
session["fit_card"] = None
```
`suggest_outfit` was not called — confirmed by running `python agent.py` and observing no LLM output between the two test case headers.

---

## Spec Reflection

**One way the spec helped:** Writing out the failure mode for `search_listings` before implementing it — "returns `[]`, never raises" — made the early-return branch in `run_agent` obvious. Without that constraint in the spec, the temptation would have been to raise an exception in the tool itself and catch it in the loop, which would have made the error message harder to customize.

**One divergence from the spec:** The planning.md spec says size defaults to `"M"` if not specified. The implementation sets size to `None` instead, which skips size filtering entirely. Defaulting to `"M"` would silently exclude results in other sizes when the user didn't ask for a size filter — `None` is more correct behavior and matches the `search_listings` docstring.

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
