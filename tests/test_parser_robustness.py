"""Regressions for four parser bugs found in review.

Each was a case where the parser produced a confident, wrong answer rather than
admitting it did not understand - the worst failure mode for a voice app, since
it acts silently on a misreading.

  1. "add milk and eggs"           -> one item named "milk and eggs"
  2. "add half a kilo of tomatoes" -> 1 kg of "half of tomatoes"
  3. "actually make that three"    -> UPDATE on an item called "actually"
  4. "whats on my list"            -> UNKNOWN
"""

from __future__ import annotations

import pytest

from app.models import Intent
from app.nlp.parser import parse


# --------------------------------------------------------------------------
# 1. Several items in one command
# --------------------------------------------------------------------------


def test_two_items_are_two_items() -> None:
    command = parse("add milk and eggs")
    assert command.intent is Intent.ADD_ITEM
    assert [entry.item for entry in command.items] == ["milk", "eggs"]


def test_comma_separated_list() -> None:
    command = parse("add milk, eggs and bread")
    assert [entry.item for entry in command.items] == ["milk", "eggs", "bread"]


def test_each_item_keeps_its_own_quantity() -> None:
    """"2 litres of milk and 3 eggs" is not 2 of everything."""
    command = parse("add 2 litres of milk and 3 eggs")
    milk, eggs = command.items
    assert (milk.item, milk.quantity, milk.unit) == ("milk", 2, "litre")
    assert (eggs.item, eggs.quantity, eggs.unit) == ("eggs", 3, None)


def test_each_item_is_categorised_separately() -> None:
    command = parse("add milk and bread")
    assert [entry.category.value for entry in command.items] == ["Dairy", "Bakery"]


def test_removal_handles_several_items() -> None:
    command = parse("remove milk and eggs")
    assert command.intent is Intent.REMOVE_ITEM
    assert [entry.item for entry in command.items] == ["milk", "eggs"]


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("add milk plus eggs", ["milk", "eggs"]),
        ("add apples, bananas, oranges", ["apples", "bananas", "oranges"]),
        ("I need bread and butter", ["bread", "butter"]),
    ],
)
def test_conjunction_variants(utterance: str, expected: list[str]) -> None:
    assert [entry.item for entry in parse(utterance).items] == expected


def test_scalar_fields_mirror_the_first_item() -> None:
    """Callers that only understand one item still get a usable answer."""
    command = parse("add 2 litres of milk and 3 eggs")
    assert command.item == "milk"
    assert command.quantity == 2
    assert command.unit == "litre"


def test_single_item_commands_still_produce_one_item() -> None:
    for utterance in ["add milk", "add 2 litres of milk", "remove milk"]:
        assert len(parse(utterance).items) == 1


# --- the "and" that is not a list separator --------------------------------


def test_and_inside_a_quantity_is_not_a_separator() -> None:
    """Regression: "two and a half" was split, silently dropping the "two"."""
    command = parse("Add two and a half kg of potatoes")
    assert len(command.items) == 1
    assert command.quantity == 2.5
    assert command.item == "potatoes"


@pytest.mark.parametrize(
    ("utterance", "low", "high"),
    [
        ("Show me milk between $3 and $6", 3, 6),
        ("Find snacks between 2 and 5 dollars", 2, 5),
    ],
)
def test_price_range_and_is_not_a_separator(
    utterance: str, low: float, high: float
) -> None:
    """Price is extracted before splitting, so a range keeps its "and"."""
    command = parse(utterance)
    assert command.intent is Intent.SEARCH_PRODUCT
    assert (command.min_price, command.max_price) == (low, high)


def test_search_is_never_split() -> None:
    """"find milk and eggs" is one query, not two searches."""
    command = parse("find milk and eggs")
    assert command.intent is Intent.SEARCH_PRODUCT
    assert len(command.items) <= 1


def test_multi_item_commands_are_confident() -> None:
    """They must not land under the clarification threshold."""
    command = parse("add milk and eggs")
    assert command.needs_clarification is False


# --------------------------------------------------------------------------
# 2. Fractions of a unit
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("utterance", "quantity", "unit", "item"),
    [
        ("add half a kilo of tomatoes", 0.5, "kg", "tomatoes"),
        ("add quarter of a pound of cheese", 0.25, "lb", "cheese"),
        ("add half a litre of milk", 0.5, "litre", "milk"),
    ],
)
def test_fraction_of_a_unit(
    utterance: str, quantity: float, unit: str, item: str
) -> None:
    """Regression: the article rule read "a kilo" as 1 and stranded "half"."""
    command = parse(utterance)
    assert command.quantity == quantity
    assert command.unit == unit
    assert command.item == item


def test_plain_article_quantity_is_unaffected() -> None:
    command = parse("add a kilo of tomatoes")
    assert command.quantity == 1
    assert command.unit == "kg"
    assert command.item == "tomatoes"


# --------------------------------------------------------------------------
# 3. Discourse fillers
# --------------------------------------------------------------------------


def test_filler_before_a_correction_is_not_the_item() -> None:
    """"actually make that three" updates the last item, not one named
    "actually"."""
    command = parse("actually make that three")
    assert command.intent is Intent.UPDATE_ITEM
    assert command.item is None
    assert command.quantity == 3


@pytest.mark.parametrize(
    "utterance",
    [
        "um add milk",
        "just add milk please",
        "okay add milk",
        "so add milk",
        "actually add milk",
        "hey add milk thanks",
    ],
)
def test_fillers_are_stripped_from_item_names(utterance: str) -> None:
    command = parse(utterance)
    assert command.intent is Intent.ADD_ITEM
    assert command.item == "milk"


# --------------------------------------------------------------------------
# 4. Contractions without apostrophes
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "utterance",
    ["whats on my list", "what's on my list", "what is on my list"],
)
def test_apostrophe_is_optional(utterance: str) -> None:
    """Dictation and fast typing drop apostrophes constantly."""
    assert parse(utterance).intent is Intent.SHOW_LIST


@pytest.mark.parametrize(
    ("utterance", "item"),
    [
        ("dont forget the coffee", "coffee"),
        ("we're out of eggs", "eggs"),
        ("im out of milk", "milk"),
    ],
)
def test_apostrophe_less_contractions_in_commands(utterance: str, item: str) -> None:
    command = parse(utterance)
    assert command.intent is Intent.ADD_ITEM
    assert command.item == item


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # "were", "id" and "hes" are ordinary words. Expanding them would
        # corrupt real input, so they are deliberately not in the table even
        # though they are also apostrophe-less contractions.
        ("we were out of eggs", "we were out of eggs"),
        ("id number", "id number"),
    ],
)
def test_ambiguous_words_are_not_treated_as_contractions(
    text: str, expected: str
) -> None:
    from app.nlp.normalize import normalize

    assert normalize(text) == expected


# --------------------------------------------------------------------------
# 5. Mixed-intent utterances
# --------------------------------------------------------------------------


def test_two_different_instructions_are_not_one_command() -> None:
    """Regression introduced by the multi-item split itself.

    "remove milk and add eggs" was parsed as a two-item REMOVE, the second
    item being one literally named "add eggs" - which then got added to the
    list as a Dairy product, at a confidence high enough to act without
    asking. Acting silently on a misreading is precisely what this parser is
    built to avoid.
    """
    command = parse("remove milk and add eggs")

    assert command.intent is Intent.REMOVE_ITEM
    assert [entry.item for entry in command.items] == ["milk"]
    assert not any("add" in entry.item for entry in command.items)
    # The dropped clause is reported, not discarded in silence...
    assert command.unhandled == "add eggs"
    # ...and the command is held for confirmation rather than applied.
    assert command.needs_clarification is True


def test_the_other_ordering_too() -> None:
    command = parse("add milk and remove eggs")
    assert command.unhandled is not None
    assert command.needs_clarification is True
    assert not any("remove" in entry.item for entry in command.items)


def test_a_repeated_verb_is_still_one_instruction() -> None:
    """"add milk and add eggs" is a list, not a mixed intent."""
    command = parse("add milk and add eggs")
    assert command.intent is Intent.ADD_ITEM
    assert [entry.item for entry in command.items] == ["milk", "eggs"]
    assert command.unhandled is None
    assert command.needs_clarification is False


def test_ordinary_multi_item_commands_report_nothing_unhandled() -> None:
    for utterance in ["add milk and eggs", "add 2 litres of milk and 3 eggs"]:
        assert parse(utterance).unhandled is None


# --------------------------------------------------------------------------
# 6. Quantity sanity bound
# --------------------------------------------------------------------------


@pytest.mark.parametrize("quantity", [1001, 5000, 999999999])
def test_implausible_quantities_are_held_for_confirmation(quantity: int) -> None:
    """Speech recognition turns all sorts of things into long digit strings.

    The number is kept and shown, so the user can see what was misheard, but
    the command is not applied without asking.
    """
    command = parse(f"add {quantity} apples")
    assert command.intent is Intent.ADD_ITEM
    assert command.quantity == quantity
    assert command.needs_clarification is True


@pytest.mark.parametrize("quantity", [1, 2, 12, 50, 1000])
def test_ordinary_quantities_act_without_asking(quantity: int) -> None:
    command = parse(f"add {quantity} apples")
    assert command.quantity == quantity
    assert command.needs_clarification is False


def test_the_bound_applies_to_each_item_in_a_list() -> None:
    command = parse("add 2 apples and 999999999 bananas")
    assert len(command.items) == 2
    assert command.needs_clarification is True
