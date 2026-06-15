"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()
print(os.getenv("GROQ_API_KEY"))


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    # Load all listings
    all_listings = load_listings()
    
    # Step 1: Filter by max_price
    filtered_listings = []
    for listing in all_listings:
        # Skip if price is above max_price
        if max_price is not None and listing['price'] > max_price:
            continue
        
        # Skip if size doesn't match (case-insensitive)
        if size is not None:
            # Convert both to uppercase for case-insensitive comparison
            listing_size_upper = listing['size'].upper()
            size_upper = size.upper()
            
            # Check if size is contained in listing's size field
            # (handles cases like "S/M" containing "M")
            if size_upper not in listing_size_upper:
                continue
        
        filtered_listings.append(listing)
    
    # Step 2: Score each listing by keyword overlap with description
    # Convert description to lowercase and split into keywords
    keywords = description.lower().split()
    
    scored_listings = []
    for listing in filtered_listings:
        score = 0
        
        # Combine text fields to search
        searchable_text = " ".join([
            listing['title'].lower(),
            listing['description'].lower(),
            " ".join(listing['style_tags']).lower(),
            (listing['brand'] or '').lower(),
            listing['category'].lower()
        ])
        
        # Count keyword matches
        for keyword in keywords:
            if keyword in searchable_text:
                score += 1
        
        # Only keep listings with at least one keyword match
        if score > 0:
            scored_listings.append((score, listing))
    
    # Step 3: Sort by score (highest first) and return just the listing dicts
    scored_listings.sort(key=lambda x: x[0], reverse=True)
    return [listing for score, listing in scored_listings]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    # Initialize grop api key from .env and create a client
    client = _get_groq_client()
    
    # Extract new item details for the prompt
    item_title = new_item.get('title', 'this item')
    item_brand = new_item.get('brand', '')
    item_colors = ', '.join(new_item.get('colors', []))
    item_style_tags = ', '.join(new_item.get('style_tags', []))
    item_category = new_item.get('category', 'clothing item')
    item_condition = new_item.get('condition', '')
    
    # Build item description string
    item_desc = f"{item_title}"
    if item_brand:
        item_desc += f" by {item_brand}"
    if item_colors:
        item_desc += f" in {item_colors}"
    if item_style_tags:
        item_desc += f" ({item_style_tags} style)"
    if item_condition:
        item_desc += f", {item_condition} condition"
    
    # Check if wardrobe is empty
    wardrobe_items = wardrobe.get('items', [])
    
    if not wardrobe_items:
        # Empty wardrobe case - general styling advice
        prompt = f"""You are a fashion stylist. Someone just found this item: {item_desc} (category: {item_category}).

Their wardrobe is currently empty. Suggest 1-2 outfit ideas using this item as the centerpiece. 
Recommend what types of other clothing pieces (jeans, shoes, jackets, accessories) would pair well with it, 
what colors to look for, and what overall vibe or aesthetic this item suits.

Keep suggestions practical, friendly, and specific. Return just the outfit suggestions as a short paragraph."""
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  
            messages=[
                {"role": "system", "content": "You are a helpful fashion stylist."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        return response.choices[0].message.content.strip()
    
    else:
        # Wardrobe has items - suggest specific combinations
        # Format wardrobe items for the prompt
        wardrobe_text = []
        for item in wardrobe_items[:15]:  # Limit to 15 items to avoid token issues
            item_name = item.get('name', 'unnamed item')
            item_category = item.get('category', '')
            item_colors = ', '.join(item.get('colors', []))
            item_style = item.get('style_tags', [])
            item_style_str = ', '.join(item_style) if item_style else 'no specific style'
            
            wardrobe_text.append(f"- {item_name} ({item_category}, {item_colors}, {item_style_str})")
        
        wardrobe_summary = "\n".join(wardrobe_text)
        
        prompt = f"""You are a fashion stylist. Someone just found this new thrifted item: {item_desc} (category: {item_category}).

Here is their current wardrobe:
{wardrobe_summary}

Suggest 1-2 complete outfits using the new item combined with pieces from their existing wardrobe.
For each outfit, name the specific pieces (using the names from the wardrobe list) and explain why it works.
Be practical, specific, and friendly. Return just the outfit suggestions as a short paragraph or two."""

        response = client.chat.completions.create(
            model="groq/compound-mini",
            messages=[
                {"role": "system", "content": "You are a helpful fashion stylist."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=250
        )
        
        return response.choices[0].message.content.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
        # Guard against empty outfit
    if not outfit or not outfit.strip():
        return "Couldn't generate a fit card — no outfit suggestion was available. Try styling this piece with your wardrobe basics!"
    
    # Initialize Groq client
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    # Extract item details
    item_title = new_item.get('title', 'this thrifted find')
    item_price = new_item.get('price', '')
    item_platform = new_item.get('platform', 'Depop/Poshmark')
    item_brand = new_item.get('brand', '')
    item_style_tags = new_item.get('style_tags', [])
    
    # Format price string
    price_str = f"${item_price}" if item_price else "a great price"
    
    # Build prompt for LLM
    prompt = f"""You're a fashion influencer writing an Instagram caption for an outfit post.

Item info:
- Name: {item_title}
- Brand: {item_brand if item_brand else 'vintage find'}
- Price: {price_str}
- Platform: {item_platform}
- Style vibes: {', '.join(item_style_tags) if item_style_tags else 'timeless'}

How they styled it:
{outfit}

Write a 2-4 sentence caption that:
- Sounds authentic and casual (like a real OOTD post, not an ad)
- Naturally mentions the item, price, and platform once
- Captures the specific vibe (90s grunge, minimalist, streetwear, etc.)
- Uses casual punctuation (lowercase sometimes, no periods, emojis welcome)
- Feels different for each outfit (avoid generic templates)

Examples of good vibes:
- "thrifted this vintage band tee for $22 on depop and it's literally perfect with my wide-leg jeans 🖤"
- "copped these leather pants for $45 on poshmark — finally figured out the perfect silhouette 🤍"
- "found the coziest cardigan for $18 and layered it over everything in my closet 🔥"

Return ONLY the caption text, no explanations, no quotes around it."""
    
    try:
        response = client.chat.completions.create(
            model="groq/compound-mini",
            messages=[
                {"role": "system", "content": "You are a fashion influencer writing authentic outfit captions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.9,  # Higher temperature for more variety
            max_tokens=150
        )
        
        caption = response.choices[0].message.content.strip()
        
        # Ensure caption isn't empty
        if not caption:
            return f"just thrifted this {item_title.lower()} — perfect for my wardrobe 🖤 #fitcheck"
        
        return caption
        
    except Exception as e:
        # Fallback generic caption if LLM call fails
        return f"just thrifted this {item_title.lower()} for {price_str} on {item_platform} and styled it with my go-to pieces 🔥 what do we think?"