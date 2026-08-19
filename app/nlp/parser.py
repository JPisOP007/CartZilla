"""Intent and entity extraction.

The pipeline, in order:

    normalize -> intent detection -> price -> quantity/unit -> brand ->
    attributes -> item -> category -> confidence

Order matters. Price runs before quantity because "toothpaste under $5"
contains a number that belongs to the price, not to the toothpaste. Item
extraction runs last and simply takes whatever text survived, which is why
each earlier stage removes the span it consumed.

There is no LLM here on purpose: the grammar of a shopping command is small
and closed, so a dictionary-driven parser is faster, free, offline, fully
deterministic, and - most importantly - unit-testable.
"""

from __future__ import annotations

import re
from functools import lru_cache

from app.catalog.categorize import categorize
from app.catalog.data import known_brands
from app.models import (
    DESTRUCTIVE_INTENTS,
    LOW_CONFIDENCE,
    Category,
    Intent,
    ParsedCommand,
)
from app.nlp.lexicons import Lexicon, get_lexicon
from app.nlp.lexicons.base import (
    WORD_END,
    WORD_START,
    alternation,
    compile_cues,
)
from app.nlp.normalize import normalize, remove_span, trim_edges
from app.nlp.numbers import collapse_compounds
from app.nlp.price import extract_price
from app.nlp.quantity import extract_quantity, strip_leading_unit
from app.nlp.translate import canonicalize

#: Intent precedence when two cues match spans of equal length. Earlier wins.
#: Destructive and more specific intents come first so that "remove everything"
#: is a CLEAR_LIST rather than a REMOVE_ITEM of an item called "everything".
_PRECEDENCE: tuple[Intent, ...] = (
    Intent.CLEAR_LIST,
    Intent.SHOW_LIST,
    Intent.UPDATE_ITEM,
    Intent.COMPLETE_ITEM,
    Intent.REMOVE_ITEM,
    Intent.SEARCH_PRODUCT,
    Intent.ADD_ITEM,
)

#: Confidence given to a bare product name ("milk" with no verb). Derived from
#: LOW_CONFIDENCE rather than written as a literal so it stays strictly below
#: the threshold: the intent is a guess, and the UI must ask before acting.
_BARE_ITEM_CONFIDENCE = round(LOW_CONFIDENCE - 0.05, 2)

#: Longest utterance still treated as a bare product name. The fallback exists
#: so that saying "milk" works; without a bound it also turns "we are running
#: low on that sourdough" into an item literally called that, because the
#: phrase happens to contain a word the categorizer recognises. Anything longer
#: stays UNKNOWN, which is both more honest and the case the optional LLM
#: fallback is there to pick up.
_MAX_BARE_ITEM_TOKENS = 3

#: Intents that are complete without an item.
_ITEMLESS: frozenset[Intent] = frozenset({
    Intent.SHOW_LIST, Intent.CLEAR_LIST, Intent.CONFIRM, Intent.CANCEL,
})


@lru_cache(maxsize=32)
def _intent_patterns(lexicon: Lexicon) -> tuple[tuple[Intent, tuple[re.Pattern[str], ...]], ...]:
    cue_sets = {
        Intent.CLEAR_LIST: lexicon.clear_cues,
        Intent.SHOW_LIST: lexicon.show_cues,
        Intent.UPDATE_ITEM: lexicon.update_cues,
        Intent.COMPLETE_ITEM: lexicon.complete_cues,
        Intent.REMOVE_ITEM: lexicon.remove_cues,
        Intent.SEARCH_PRODUCT: lexicon.search_cues,
        Intent.ADD_ITEM: lexicon.add_cues,
    }
    return tuple(
        (intent, tuple(compile_cues(cue_sets[intent]))) for intent in _PRECEDENCE
    )


@lru_cache(maxsize=32)
def _attribute_patterns(lexicon: Lexicon) -> tuple[tuple[re.Pattern[str], str], ...]:
    """Attribute surface forms, longest first so "low fat" beats "low"."""
    surfaces = sorted(lexicon.attributes, key=len, reverse=True)
    return tuple(
        (
            re.compile(rf"{WORD_START}{re.escape(surface)}{WORD_END}"),
            lexicon.attributes[surface],
        )
        for surface in surfaces
    )


@lru_cache(maxsize=1)
def _brand_patterns() -> tuple[tuple[re.Pattern[str], str], ...]:
    return tuple(
        (re.compile(rf"{WORD_START}{re.escape(brand.lower())}{WORD_END}"), brand)
        for brand in known_brands()
    )


@lru_cache(maxsize=32)
def _replacement_patterns(lexicon: Lexicon) -> tuple[re.Pattern[str], ...]:
    ordered = sorted(lexicon.replacement_cues, key=len, reverse=True)
    return tuple(
        re.compile(rf"{WORD_START}(?:{cue}){WORD_END}") for cue in ordered
    )


@lru_cache(maxsize=32)
def _short_word_pattern(lexicon: Lexicon) -> re.Pattern[str] | None:
    """Matches an utterance that is nothing but a confirm/cancel word."""
    words = lexicon.confirm_words | lexicon.cancel_words
    if not words:
        return None
    return re.compile(rf"^(?:{alternation(words)})$")


def _detect_intent(
    text: str, lexicon: Lexicon
) -> tuple[Intent, list[tuple[int, int]]]:
    """Find the best intent in ``text`` and every cue span belonging to it.

    The winning intent is scored by matched-span length, so a specific
    multi-word cue ("I want to buy") beats the shorter cue nested inside it
    ("buy"). Ties break on :data:`_PRECEDENCE`.

    Every cue of the winning intent is returned, not just the longest, because
    English has separable verbs: "take eggs off my list" carries the removal
    cue in two pieces around the item. Stripping both leaves "eggs"; stripping
    only the longest would leave "take eggs" or "my list".
    """
    best_intent = Intent.UNKNOWN
    best_length = 0

    for intent, patterns in _intent_patterns(lexicon):
        for pattern in patterns:
            match = pattern.search(text)
            if not match:
                continue
            length = match.end() - match.start()
            if length > best_length:
                best_intent, best_length = intent, length

    if best_intent is Intent.UNKNOWN:
        return best_intent, []

    spans: list[tuple[int, int]] = []
    for intent, patterns in _intent_patterns(lexicon):
        if intent is not best_intent:
            continue
        for pattern in patterns:
            for match in pattern.finditer(text):
                spans.append(match.span())

    return best_intent, _merge_spans(spans)


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Collapse overlapping cue spans into a minimal, ordered set."""
    if not spans:
        return []
    ordered = sorted(set(spans))
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _remove_spans(text: str, spans: list[tuple[int, int]]) -> str:
    """Cut every span out of ``text``, right to left so indices stay valid."""
    for span in sorted(spans, reverse=True):
        text = remove_span(text, span)
    return text


def _extract_attributes(text: str, lexicon: Lexicon) -> tuple[list[str], str]:
    """Pull canonical attribute tags out of ``text``, returning the remainder."""
    found: list[str] = []
    for pattern, canonical in _attribute_patterns(lexicon):
        match = pattern.search(text)
        if match:
            if canonical not in found:
                found.append(canonical)
            text = remove_span(text, match.span())
    return found, text


def _extract_brand(text: str) -> tuple[str | None, str]:
    """Pull a known catalog brand out of ``text``, returning the remainder."""
    for pattern, brand in _brand_patterns():
        match = pattern.search(text)
        if match:
            return brand, remove_span(text, match.span())
    return None, text


def _split_replacement(text: str, lexicon: Lexicon) -> tuple[str, str]:
    """Split "milk to almond milk" into its target and its replacement.

    Returns ``(target, replacement_text)``; ``replacement_text`` is empty when
    no usable split exists, which is the "change it to 2 litres" case.
    """
    for pattern in _replacement_patterns(lexicon):
        match = pattern.search(text)
        if not match:
            continue
        left = text[: match.start()].strip()
        right = text[match.end():].strip()
        if left and right:
            return left, right
    return text, ""


def _clean_item(text: str, lexicon: Lexicon) -> str | None:
    """Reduce leftover text to an item name, or None if nothing is left."""
    cleaned = trim_edges(text.strip(), lexicon.stopwords)
    cleaned = strip_leading_unit(cleaned, lexicon)
    cleaned = trim_edges(cleaned, lexicon.stopwords)
    return cleaned or None


def _confidence(command: ParsedCommand) -> float:
    """Explainable confidence score in [0, 1].

    Intents that need no item are near-certain once their cue matched. For the
    rest, having identified an item is what separates an actionable command
    from a cue word floating on its own.
    """
    if command.intent is Intent.UNKNOWN:
        return 0.0
    if command.intent in _ITEMLESS:
        return 0.9

    has_filters = bool(
        command.brand
        or command.attributes
        or command.min_price is not None
        or command.max_price is not None
    )
    # A search is actionable without an item name - "show me Colgate under $5"
    # is a complete query. Add/remove/update genuinely need something to act on.
    actionable = bool(command.item) or (
        command.intent is Intent.SEARCH_PRODUCT and has_filters
    )

    score = 0.5
    score += 0.3 if actionable else -0.25
    if command.quantity is not None:
        score += 0.08
    if command.brand or command.attributes:
        score += 0.08
    if command.min_price is not None or command.max_price is not None:
        score += 0.08
    if command.replacement:
        score += 0.05
    return round(max(0.0, min(0.99, score)), 2)


def _needs_clarification(command: ParsedCommand) -> bool:
    """Whether the UI should ask "did you mean...?" before acting.

    An unknown intent is not a clarification case: there is nothing to confirm.
    A destructive intent already has its own confirmation step.
    """
    if command.intent is Intent.UNKNOWN or command.requires_confirmation:
        return False
    return command.confidence < LOW_CONFIDENCE


def parse(transcript: str, language: str = "en-US") -> ParsedCommand:
    """Turn one utterance into a structured command.

    Never raises: an unparseable utterance comes back as ``Intent.UNKNOWN``
    with confidence 0, which the UI renders as "I didn't catch that".
    """
    command = _parse(transcript, language)
    # Applied here, at the single exit, rather than at each of the several
    # returns inside _parse - one place to get right instead of four.
    command.needs_clarification = _needs_clarification(command)
    return command


def _parse(transcript: str, language: str = "en-US") -> ParsedCommand:
    """Run the extraction pipeline. See :func:`parse` for the public entry."""
    lexicon = get_lexicon(language)
    normalized = collapse_compounds(normalize(transcript), lexicon)

    command = ParsedCommand(
        transcript=transcript,
        normalized=normalized,
        language=language,
    )
    if not normalized:
        return command

    # A bare "yes"/"cancel" answers a pending confirmation and nothing else.
    short_word = _short_word_pattern(lexicon)
    if short_word is not None and short_word.match(normalized):
        command.intent = (
            Intent.CONFIRM
            if normalized in lexicon.confirm_words
            else Intent.CANCEL
        )
        command.confidence = 0.9
        return command

    intent, spans = _detect_intent(normalized, lexicon)
    remainder = _remove_spans(normalized, spans)

    if intent in (Intent.SHOW_LIST, Intent.CLEAR_LIST):
        command.intent = intent
        command.requires_confirmation = intent in DESTRUCTIVE_INTENTS
        command.confidence = _confidence(command)
        return command

    if intent is Intent.UNKNOWN:
        # No cue matched. If the whole utterance looks like a product, treat it
        # as an add - "milk" is a perfectly ordinary thing to say to a shopping
        # list - but at a confidence low enough that the UI asks first.
        candidate = _clean_item(remainder, lexicon)
        canonical = canonicalize(candidate, lexicon)
        short_enough = bool(candidate) and len(candidate.split()) <= _MAX_BARE_ITEM_TOKENS
        if short_enough and canonical and categorize(canonical) is not Category.OTHER:
            command.intent = Intent.ADD_ITEM
            command.item = candidate
            command.canonical_item = canonical
            command.category = categorize(canonical)
            command.confidence = _BARE_ITEM_CONFIDENCE
        return command

    command.intent = intent

    price = extract_price(remainder, lexicon)
    command.min_price = price.min_price
    command.max_price = price.max_price
    remainder = price.text

    replacement_text = ""
    if intent is Intent.UPDATE_ITEM:
        remainder, replacement_text = _split_replacement(remainder, lexicon)

    # For an update, the quantity belongs to the replacement clause
    # ("change milk to 2 litres"), so parse that side first.
    quantity_source = replacement_text if replacement_text else remainder
    quantity = extract_quantity(quantity_source, lexicon)
    command.quantity = quantity.value
    command.unit = quantity.unit
    if replacement_text:
        replacement_text = quantity.text
    else:
        remainder = quantity.text

    brand, remainder = _extract_brand(remainder)
    if replacement_text and brand is None:
        brand, replacement_text = _extract_brand(replacement_text)
    command.brand = brand

    command.attributes, remainder = _extract_attributes(remainder, lexicon)

    command.item = _clean_item(remainder, lexicon)
    command.canonical_item = canonicalize(command.item, lexicon)
    if replacement_text:
        command.replacement = _clean_item(replacement_text, lexicon)
        command.canonical_replacement = canonicalize(command.replacement, lexicon)

    if command.canonical_item:
        category = categorize(command.canonical_item)
        command.category = category if category is not Category.OTHER else None

    command.requires_confirmation = intent in DESTRUCTIVE_INTENTS
    command.confidence = _confidence(command)
    return command
