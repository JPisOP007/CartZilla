"""Hindi and Spanish command parsing.

These tests exist to keep the multilingual claim honest. The language picker is
not a decoration: each language has its own cue set, numerals, units, price
grammar and grocery vocabulary, and this file exercises all of them.
"""

from __future__ import annotations

import pytest

from app.models import Intent
from app.nlp.lexicons import get_lexicon, supported_languages
from app.nlp.parser import parse

HINDI = "hi-IN"
SPANISH = "es-ES"


# --------------------------------------------------------------------------
# Hindi
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("utterance", "intent", "item"),
    [
        ("दूध डालो", Intent.ADD_ITEM, "दूध"),
        ("मुझे सेब चाहिए", Intent.ADD_ITEM, "सेब"),
        ("ब्रेड जोड़ो", Intent.ADD_ITEM, "ब्रेड"),
        ("सूची से दूध हटाओ", Intent.REMOVE_ITEM, "दूध"),
        ("अंडे निकालो", Intent.REMOVE_ITEM, "अंडे"),
        ("टूथपेस्ट ढूंढो", Intent.SEARCH_PRODUCT, "टूथपेस्ट"),
        ("चावल खोजो", Intent.SEARCH_PRODUCT, "चावल"),
    ],
)
def test_hindi_intents(utterance: str, intent: Intent, item: str) -> None:
    """Hindi is verb-final; the cue arrives last and must still be found."""
    command = parse(utterance, HINDI)
    assert command.intent is intent
    assert command.item == item


@pytest.mark.parametrize(
    ("utterance", "quantity", "unit", "item"),
    [
        ("मुझे दो लीटर दूध चाहिए", 2, "litre", "दूध"),
        ("पांच सेब जोड़ो", 5, None, "सेब"),
        ("2 बोतल पानी जोड़ो", 2, "bottle", "पानी"),
        ("दस अंडे चाहिए", 10, None, "अंडे"),
        ("एक किलो आलू डालो", 1, "kg", "आलू"),
    ],
)
def test_hindi_quantities(
    utterance: str, quantity: float, unit: str | None, item: str
) -> None:
    command = parse(utterance, HINDI)
    assert command.intent is Intent.ADD_ITEM
    assert command.quantity == quantity
    assert command.unit == unit
    assert command.item == item


def test_hindi_devanagari_digits() -> None:
    """Speech engines emit Devanagari numerals for hi-IN."""
    command = parse("५ सेब जोड़ो", HINDI)
    assert command.quantity == 5
    assert command.item == "सेब"


def test_hindi_postpositional_price() -> None:
    """"5 डॉलर से कम" is literally "5 dollars from less" - the cue trails."""
    command = parse("टूथपेस्ट 5 डॉलर से कम ढूंढो", HINDI)
    assert command.intent is Intent.SEARCH_PRODUCT
    assert command.max_price == 5
    assert command.item == "टूथपेस्ट"


def test_hindi_minimum_price() -> None:
    command = parse("पनीर 10 डॉलर से ज्यादा ढूंढो", HINDI)
    assert command.min_price == 10


@pytest.mark.parametrize(
    ("utterance", "intent"),
    [
        ("सूची दिखाओ", Intent.SHOW_LIST),
        ("मेरी सूची", Intent.SHOW_LIST),
        ("सूची खाली करो", Intent.CLEAR_LIST),
        ("सब कुछ हटाओ", Intent.CLEAR_LIST),
    ],
)
def test_hindi_list_intents(utterance: str, intent: Intent) -> None:
    assert parse(utterance, HINDI).intent is intent


def test_hindi_attributes_map_to_english_tags() -> None:
    """A Hindi adjective has to filter an English-tagged catalog."""
    command = parse("ऑर्गेनिक सेब ढूंढो", HINDI)
    assert command.attributes == ["organic"]


def test_hindi_item_is_canonicalised_for_lookup() -> None:
    """The user sees their own word; search and categorization see English."""
    command = parse("मुझे दूध चाहिए", HINDI)
    assert command.item == "दूध"
    assert command.canonical_item == "milk"
    assert command.category.value == "Dairy"


def test_hindi_combining_marks_survive_normalization() -> None:
    """Regression: a \\w-based strip would turn "मुझे" into "म झ"."""
    command = parse("मुझे टूथपेस्ट चाहिए", HINDI)
    assert command.item == "टूथपेस्ट"


# --------------------------------------------------------------------------
# Spanish
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("utterance", "intent", "item"),
    [
        ("Añade leche", Intent.ADD_ITEM, "leche"),
        ("Agrega pan", Intent.ADD_ITEM, "pan"),
        ("Necesito huevos", Intent.ADD_ITEM, "huevos"),
        ("Quiero comprar manzanas", Intent.ADD_ITEM, "manzanas"),
        ("Quita la leche de mi lista", Intent.REMOVE_ITEM, "leche"),
        ("Elimina el pan", Intent.REMOVE_ITEM, "pan"),
        ("Busca arroz", Intent.SEARCH_PRODUCT, "arroz"),
        ("Encuentra queso", Intent.SEARCH_PRODUCT, "queso"),
    ],
)
def test_spanish_intents(utterance: str, intent: Intent, item: str) -> None:
    command = parse(utterance, SPANISH)
    assert command.intent is intent
    assert command.item == item


@pytest.mark.parametrize(
    ("utterance", "quantity", "unit", "item"),
    [
        ("Necesito dos litros de leche", 2, "litre", "leche"),
        ("Añade 5 manzanas", 5, None, "manzanas"),
        ("Compra 2 botellas de agua", 2, "bottle", "agua"),
        ("Agrega tres cajas de cereal", 3, "box", "cereal"),
        ("Añade medio kilo de queso", 0.5, "kg", "queso"),
    ],
)
def test_spanish_quantities(
    utterance: str, quantity: float, unit: str | None, item: str
) -> None:
    command = parse(utterance, SPANISH)
    assert command.intent is Intent.ADD_ITEM
    assert command.quantity == quantity
    assert command.unit == unit
    assert command.item == item


def test_spanish_price_filter() -> None:
    command = parse("Busca pasta de dientes menos de $5", SPANISH)
    assert command.intent is Intent.SEARCH_PRODUCT
    assert command.max_price == 5
    assert command.canonical_item == "toothpaste"


def test_spanish_price_range() -> None:
    command = parse("Busca queso entre 3 y 8 dólares", SPANISH)
    assert command.min_price == 3
    assert command.max_price == 8


def test_spanish_replacement() -> None:
    command = parse("Cambia leche por leche de almendras", SPANISH)
    assert command.intent is Intent.UPDATE_ITEM
    assert command.item == "leche"
    assert command.replacement == "leche de almendras"
    assert command.canonical_replacement == "almond milk"


def test_spanish_attributes() -> None:
    command = parse("Busca manzanas orgánicas", SPANISH)
    assert command.attributes == ["organic"]


def test_spanish_works_without_accents() -> None:
    """Dictated and typed text disagree about accents more than about spelling."""
    with_accent = parse("Busca manzanas orgánicas", SPANISH)
    without = parse("Busca manzanas organicas", SPANISH)
    assert with_accent.attributes == without.attributes
    assert with_accent.item == without.item


@pytest.mark.parametrize(
    ("utterance", "intent"),
    [
        ("Muestra mi lista", Intent.SHOW_LIST),
        ("mi lista", Intent.SHOW_LIST),
        ("Vacía mi lista", Intent.CLEAR_LIST),
        ("Borra todo", Intent.CLEAR_LIST),
    ],
)
def test_spanish_list_intents(utterance: str, intent: Intent) -> None:
    assert parse(utterance, SPANISH).intent is intent


# --------------------------------------------------------------------------
# Locale resolution
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("locale", "code"),
    [
        ("en-US", "en"), ("en-GB", "en"), ("en", "en"),
        ("hi-IN", "hi"), ("hi", "hi"),
        ("es-ES", "es"), ("es-MX", "es"), ("es", "es"),
    ],
)
def test_locale_resolution(locale: str, code: str) -> None:
    assert get_lexicon(locale).code == code


@pytest.mark.parametrize("locale", ["", None, "fr-FR", "zz", "garbage"])
def test_unknown_locale_falls_back_to_english(locale: str | None) -> None:
    """An unsupported locale degrades to best-effort English, never an error."""
    assert get_lexicon(locale).code == "en"


def test_every_language_advertises_working_examples() -> None:
    """The example chips in the UI must actually parse in their own language."""
    for language in supported_languages():
        lexicon = get_lexicon(language["locale"])
        assert lexicon.examples, f"{language['code']} has no examples"
        for example in lexicon.examples:
            command = parse(example, language["locale"])
            assert command.intent is not Intent.UNKNOWN, (
                f"{language['code']} example did not parse: {example!r}"
            )
