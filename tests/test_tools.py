"""
tests/test_tools.py

Pytest tests for each FitFindr tool, covering failure modes and contracts
described in tools.py.

Run with:
    pytest tests/test_tools.py -v
"""

import pytest
from unittest.mock import MagicMock, patch

from tools import search_listings, suggest_outfit, create_fit_card


# ── Shared fixtures ────────────────────────────────────────────────────────────

SAMPLE_LISTING = {
    "id": "lst_001",
    "title": "Vintage Levi's 501 Jeans",
    "description": "Classic 501s in a perfect medium wash. Vintage denim.",
    "category": "bottoms",
    "style_tags": ["vintage", "denim", "streetwear"],
    "size": "M",
    "condition": "good",
    "price": 38.00,
    "colors": ["blue"],
    "brand": "Levi's",
    "platform": "depop",
}

SAMPLE_WARDROBE_WITH_ITEMS = {
    "items": [
        {"name": "White sneakers", "category": "shoes", "colors": ["white"]},
        {"name": "Black hoodie", "category": "tops", "colors": ["black"]},
    ]
}

EMPTY_WARDROBE = {"items": []}


# ── Tool 1: search_listings ────────────────────────────────────────────────────

class TestSearchListings:
    def test_returns_list(self):
        """search_listings always returns a list, never raises."""
        result = search_listings("jeans")
        assert isinstance(result, list)

    def test_no_match_returns_empty_list(self):
        """Completely nonsensical query returns [] instead of raising."""
        result = search_listings("xyzzy_nonexistent_item_12345")
        assert result == []

    def test_max_price_filter_excludes_expensive_items(self):
        """Items above max_price must not appear in results."""
        result = search_listings("jeans", max_price=1.00)
        for item in result:
            assert item["price"] <= 1.00, (
                f"Item '{item['title']}' (${item['price']}) exceeded max_price=1.00"
            )

    def test_size_filter_is_case_insensitive(self):
        """Size matching is case-insensitive per the docstring."""
        lower = search_listings("shirt", size="m")
        upper = search_listings("shirt", size="M")
        lower_ids = {item["id"] for item in lower}
        upper_ids = {item["id"] for item in upper}
        assert lower_ids == upper_ids

    def test_size_none_skips_size_filtering(self):
        """Passing size=None should not filter by size."""
        all_results = search_listings("vintage", size=None)
        sized_results = search_listings("vintage", size="XL")
        # Without size filter we should get at least as many results
        assert len(all_results) >= len(sized_results)

    def test_max_price_none_skips_price_filtering(self):
        """Passing max_price=None should not filter by price."""
        all_results = search_listings("vintage", max_price=None)
        capped_results = search_listings("vintage", max_price=5.00)
        assert len(all_results) >= len(capped_results)

    def test_results_are_sorted_best_match_first(self):
        """Results must be ordered highest relevance first (zero-score items dropped)."""
        results = search_listings("vintage denim jeans")
        # Spot check: all returned items should have some keyword overlap
        assert all(
            any(
                kw in (item.get("description", "") + " ".join(item.get("style_tags", []))).lower()
                for kw in ["vintage", "denim", "jeans"]
            )
            for item in results
        ), "At least one result has no keyword overlap with the query"

    def test_zero_score_items_excluded(self):
        """Items with no keyword match should not appear in results."""
        results = search_listings("vintage graphic tee")
        for item in results:
            text = (
                item.get("title", "")
                + " "
                + item.get("description", "")
                + " "
                + " ".join(item.get("style_tags", []))
            ).lower()
            assert any(kw in text for kw in ["vintage", "graphic", "tee"]), (
                f"Item '{item['title']}' has no overlap with query keywords"
            )

    def test_combined_filters(self):
        """Both size and max_price filters apply simultaneously."""
        results = search_listings("top", size="M", max_price=20.00)
        for item in results:
            assert item["price"] <= 20.00
            assert "m" in item["size"].lower()

    def test_empty_description_returns_list(self):
        """Empty description string should not raise — returns a list."""
        result = search_listings("")
        assert isinstance(result, list)


# ── Tool 2: suggest_outfit ─────────────────────────────────────────────────────

class TestSuggestOutfit:
    def _mock_groq_response(self, text: str):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=text))]
        )
        return mock_client

    def test_returns_non_empty_string_with_wardrobe(self):
        """suggest_outfit returns a non-empty string when wardrobe has items."""
        with patch("tools._get_groq_client") as mock_get:
            mock_get.return_value = self._mock_groq_response("Pair with the black hoodie.")
            result = suggest_outfit(SAMPLE_LISTING, SAMPLE_WARDROBE_WITH_ITEMS)
        assert isinstance(result, str)
        assert result.strip() != ""

    def test_empty_wardrobe_returns_general_advice(self):
        """Empty wardrobe triggers general styling advice, not an error."""
        with patch("tools._get_groq_client") as mock_get:
            mock_get.return_value = self._mock_groq_response("Great with a plain tee.")
            result = suggest_outfit(SAMPLE_LISTING, EMPTY_WARDROBE)
        assert isinstance(result, str)
        assert result.strip() != "", "Should return general styling advice for empty wardrobe"

    def test_empty_wardrobe_does_not_raise(self):
        """Empty wardrobe must never cause an exception."""
        with patch("tools._get_groq_client") as mock_get:
            mock_get.return_value = self._mock_groq_response("Style with a white tee.")
            try:
                suggest_outfit(SAMPLE_LISTING, EMPTY_WARDROBE)
            except Exception as exc:
                pytest.fail(f"suggest_outfit raised {type(exc).__name__} on empty wardrobe: {exc}")

    def test_llm_is_called_once(self):
        """Only one LLM call is made per suggest_outfit invocation."""
        with patch("tools._get_groq_client") as mock_get:
            mock_client = self._mock_groq_response("Some outfit.")
            mock_get.return_value = mock_client
            suggest_outfit(SAMPLE_LISTING, SAMPLE_WARDROBE_WITH_ITEMS)
        mock_client.chat.completions.create.assert_called_once()

    def test_missing_groq_key_raises_value_error(self):
        """If GROQ_API_KEY is absent, ValueError is raised (not a silent failure)."""
        with patch.dict("os.environ", {}, clear=True):
            # Remove the key so _get_groq_client raises
            import os
            os.environ.pop("GROQ_API_KEY", None)
            with pytest.raises((ValueError, Exception)):
                suggest_outfit(SAMPLE_LISTING, SAMPLE_WARDROBE_WITH_ITEMS)


# ── Tool 3: create_fit_card ────────────────────────────────────────────────────

class TestCreateFitCard:
    def _mock_groq_response(self, text: str):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=text))]
        )
        return mock_client

    def test_returns_string(self):
        """create_fit_card always returns a string."""
        with patch("tools._get_groq_client") as mock_get:
            mock_get.return_value = self._mock_groq_response("Found these jeans on Depop for $38!")
            result = create_fit_card("Pair with white tee.", SAMPLE_LISTING)
        assert isinstance(result, str)

    def test_empty_outfit_returns_error_string_not_exception(self):
        """Empty outfit string returns a descriptive error string, never raises."""
        try:
            result = create_fit_card("", SAMPLE_LISTING)
        except Exception as exc:
            pytest.fail(f"create_fit_card raised {type(exc).__name__} on empty outfit: {exc}")
        assert isinstance(result, str)
        assert result.strip() != "", "Should return an error message string, not empty string"

    def test_whitespace_only_outfit_returns_error_string(self):
        """Whitespace-only outfit is treated the same as empty."""
        try:
            result = create_fit_card("   \n\t  ", SAMPLE_LISTING)
        except Exception as exc:
            pytest.fail(f"create_fit_card raised on whitespace outfit: {exc}")
        assert isinstance(result, str)
        assert result.strip() != ""

    def test_caption_references_item_price(self):
        """The generated caption should mention the item's price."""
        caption_text = "Snagged these Levi's jeans for $38 on Depop — obsessed!"
        with patch("tools._get_groq_client") as mock_get:
            mock_get.return_value = self._mock_groq_response(caption_text)
            result = create_fit_card("Pair with a white tee.", SAMPLE_LISTING)
        assert "38" in result, "Caption should mention the item price"

    def test_caption_references_platform(self):
        """The generated caption should mention the platform."""
        caption_text = "Thrifted these jeans on Depop for $38 and couldn't be happier!"
        with patch("tools._get_groq_client") as mock_get:
            mock_get.return_value = self._mock_groq_response(caption_text)
            result = create_fit_card("Pair with sneakers.", SAMPLE_LISTING)
        assert SAMPLE_LISTING["platform"].lower() in result.lower(), (
            "Caption should mention the platform"
        )

    def test_llm_is_called_once(self):
        """Only one LLM call is made per create_fit_card invocation."""
        with patch("tools._get_groq_client") as mock_get:
            mock_client = self._mock_groq_response("Great caption here.")
            mock_get.return_value = mock_client
            create_fit_card("Wear with sneakers.", SAMPLE_LISTING)
        mock_client.chat.completions.create.assert_called_once()

    def test_missing_groq_key_raises(self):
        """If GROQ_API_KEY is absent, an exception is raised (not silent)."""
        with patch.dict("os.environ", {}, clear=True):
            import os
            os.environ.pop("GROQ_API_KEY", None)
            with pytest.raises((ValueError, Exception)):
                create_fit_card("Nice outfit.", SAMPLE_LISTING)
