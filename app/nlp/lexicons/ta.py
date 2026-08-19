"""Tamil language pack.

Tamil shares Hindi's two structural challenges and adds a third:

* **Verb-final.** "பால் சேர்" is literally *milk add*. Cues are matched
  anywhere and removed, so word order needs no special handling.
* **Postpositional price cues.** "5 டாலருக்கு கீழ்" is *5 to-dollars below*,
  hence ``price_cue_position="both"``.
* **Agglutination.** Tamil fuses case markers onto the noun, so "dollar"
  appears as டாலருக்கு ("to the dollar") rather than as a separate token.
  Both the bare and the case-marked forms are registered as currency words so
  the amount pattern consumes them and leaves the comparative behind.

Tamil vowel signs and the pulli are combining marks (Unicode Mc/Mn), which is
exactly what the category-based normalizer preserves and a ``\\w`` class would
have destroyed.
"""

from __future__ import annotations

from app.nlp.lexicons.base import Lexicon

_NUMBER_WORDS: dict[str, float] = {
    "பூஜ்யம்": 0,
    "ஒன்று": 1, "ஒரு": 1, "ஓர்": 1,
    "இரண்டு": 2, "இரு": 2,
    "மூன்று": 3, "மூணு": 3,
    "நான்கு": 4, "நாலு": 4,
    "ஐந்து": 5, "அஞ்சு": 5,
    "ஆறு": 6, "ஏழு": 7, "எட்டு": 8, "ஒன்பது": 9, "பத்து": 10,
    "பதினொன்று": 11, "பன்னிரண்டு": 12, "பன்னிரெண்டு": 12,
    "பதிமூன்று": 13, "பதினான்கு": 14, "பதினைந்து": 15,
    "இருபது": 20, "முப்பது": 30, "நாற்பது": 40, "ஐம்பது": 50,
    "நூறு": 100,
    "அரை": 0.5, "கால்": 0.25, "முக்கால்": 0.75,
    "ஒன்றரை": 1.5, "இரண்டரை": 2.5,
    "டஜன்": 12,
}

_UNITS: dict[str, str] = {
    "லிட்டர்": "litre", "லிட்டர்கள்": "litre", "லிட்டருக்கு": "litre",
    "மில்லி": "ml", "மில்லிலிட்டர்": "ml",
    "கிலோ": "kg", "கிலோகிராம்": "kg", "கிலோவுக்கு": "kg",
    "கிராம்": "g",
    "பாட்டில்": "bottle", "பாட்டில்கள்": "bottle", "புட்டி": "bottle",
    "பாக்கெட்": "packet", "பாக்கெட்டுகள்": "packet",
    "பொட்டலம்": "packet",
    "டப்பா": "box", "பெட்டி": "box", "பாக்ஸ்": "box",
    "கேன்": "can", "டின்": "tin",
    "பை": "bag", "கவர்": "bag",
    "டஜன்": "dozen",
    "துண்டு": "piece", "துண்டுகள்": "piece",
    "கட்டு": "bunch", "கொத்து": "bunch",
}

_ATTRIBUTES: dict[str, str] = {
    "ஆர்கானிக்": "organic", "இயற்கை": "organic", "ஆர்கானிக்கான": "organic",
    "புதிய": "fresh", "ஃப்ரெஷ்": "fresh", "பிரெஷ்": "fresh",
    "உறைந்த": "frozen", "ஃப்ரோஸன்": "frozen",
    "முழு": "whole", "முழுமையான": "whole",
    "வெள்ளை": "white", "பழுப்பு": "brown", "கருப்பு": "dark",
    "சிவப்பு": "red",
    "பச்சை": "green",
}

_ITEM_ALIASES: dict[str, str] = {
    # Everyday grocery vocabulary, mapped to the catalog's English terms.
    "பால்": "milk", "பாதாம் பால்": "almond milk", "சோயா பால்": "soy milk",
    "தயிர்": "yogurt", "மோர்": "buttermilk", "வெண்ணெய்": "butter",
    "நெய்": "butter", "பாலாடைக்கட்டி": "cheese", "சீஸ்": "cheese",
    "முட்டை": "eggs", "முட்டைகள்": "eggs",
    "ரொட்டி": "bread", "பிரெட்": "bread", "பாண்": "bread",
    "அரிசி": "rice", "மாவு": "flour", "கோதுமை": "wheat",
    "சர்க்கரை": "sugar", "உப்பு": "salt", "மிளகு": "pepper",
    "எண்ணெய்": "oil", "ஆலிவ் எண்ணெய்": "olive oil",
    "தேநீர்": "tea", "டீ": "tea", "காபி": "coffee", "கோப்பி": "coffee",
    "தண்ணீர்": "water", "தண்ணி": "water", "ஜூஸ்": "juice",
    "ஆப்பிள்": "apple", "வாழைப்பழம்": "banana", "வாழை": "banana",
    "ஆரஞ்சு": "orange", "எலுமிச்சை": "lemon", "மாம்பழம்": "mango",
    "திராட்சை": "grapes", "தர்பூசணி": "watermelon",
    "ஸ்ட்ராபெரி": "strawberries", "பழம்": "fruit",
    "தக்காளி": "tomatoes", "உருளைக்கிழங்கு": "potatoes",
    "வெங்காயம்": "onions", "பூண்டு": "garlic", "இஞ்சி": "ginger",
    "கேரட்": "carrots", "கீரை": "spinach", "வெள்ளரி": "cucumber",
    "முட்டைக்கோஸ்": "cabbage", "காளான்": "mushroom",
    "பட்டாணி": "peas", "பருப்பு": "lentils", "கடலை": "chickpeas",
    "காய்கறி": "vegetable",
    "கோழி": "chicken", "சிக்கன்": "chicken", "மட்டன்": "lamb",
    "மீன்": "fish", "இறால்": "shrimp", "இறைச்சி": "meat",
    "பாஸ்தா": "pasta", "நூடுல்ஸ்": "noodles", "ஓட்ஸ்": "oats",
    "தேன்": "honey", "ஜாம்": "jam", "சாக்லேட்": "chocolate",
    "பிஸ்கட்": "crackers", "சிப்ஸ்": "chips", "ஐஸ்கிரீம்": "ice cream",
    "பற்பசை": "toothpaste", "பல் துலக்கி": "toothbrush",
    "ஷாம்பு": "shampoo", "சோப்பு": "soap", "சவர்க்காரம்": "soap",
    "டிடர்ஜென்ட்": "detergent",
    "டாய்லெட் பேப்பர்": "toilet paper", "டிஷ்யூ": "tissue",
    "டயப்பர்": "diapers",
}

_STOPWORDS: frozenset[str] = frozenset({
    "என்", "எனக்கு", "எங்கள்", "எங்களுக்கு", "நான்", "நாங்கள்",
    "இந்த", "அந்த", "இது", "அது", "இதை", "அதை",
    "இல்", "இல்லிருந்து", "இருந்து", "ல்", "க்கு", "ஐ", "ஆக",
    "பட்டியல்", "பட்டியலில்", "பட்டியலிலிருந்து", "பட்டியலை",
    "லிஸ்ட்", "லிஸ்ட்டில்", "கார்ட்",
    "தயவுசெய்து", "ப்ளீஸ்", "கொஞ்சம்", "சிறிது",
    "செய்", "செய்யவும்", "பண்ணு", "பண்ணவும்", "வும்",
    "மற்றும்", "உள்ளது", "இருக்கு",
})

TAMIL = Lexicon(
    code="ta",
    label="தமிழ் (Tamil)",
    locales=("ta-IN", "ta-LK", "ta-SG"),
    default_locale="ta-IN",
    add_cues=(
        r"வாங்க\s*(?:வேண்டும்|ணும்)",
        r"சேர்க்க\s*(?:வும்|ணும்)?",
        r"சேர்த்து", r"சேர்", r"சேர்ப்பு",
        r"போட\s*(?:வும்|ு)?", r"போடு", r"போட்டு",
        r"வாங்க\s*(?:வும்|ு)?", r"வாங்கு",
        r"வேண்டும்", r"வேணும்", r"தேவை",
        r"ஆட்\s*(?:பண்ணு|செய்)",
        r"இணை\s*(?:க்க|வும்)?",
    ),
    remove_cues=(
        r"நீக்க\s*(?:வும்|ு)?", r"நீக்கு",
        r"எடுத்து\s*விடு", r"எடு\s*(?:க்கவும்)?",
        r"அகற்ற\s*(?:வும்|ு)?", r"அகற்று",
        r"வேண்டாம்", r"வேணாம்",
        r"ரிமூவ்\s*(?:பண்ணு)?", r"டெலீட்\s*(?:பண்ணு)?",
    ),
    update_cues=(
        r"மாற்ற\s*(?:வும்|ு)?", r"மாற்று", r"மாற்றி", r"மாத்து",
        r"அப்டேட்\s*(?:பண்ணு)?",
    ),
    complete_cues=(
        r"வாங்கி\s*விட்டேன்", r"வாங்கிட்டேன்",
        r"கிடைத்து\s*விட்டது", r"முடிந்தது",
    ),
    search_cues=(
        r"தேட\s*(?:வும்|ு)?", r"தேடு",
        r"கண்டுபிடி\s*(?:க்கவும்)?",
        r"தேடிப்பார்",
        r"சர்ச்\s*(?:பண்ணு)?",
        r"விலை\s+என்ன",
        r"எவ்வளவு\s+விலை",
    ),
    show_cues=(
        r"(?:பட்டியல்|பட்டியலை|லிஸ்ட்)\s+காட்ட\s*(?:வும்|ு)?",
        r"(?:பட்டியல்|பட்டியலை|லிஸ்ட்)\s+காட்டு",
        r"காட்டு\s+(?:என்\s+)?(?:பட்டியல்|லிஸ்ட்)",
        r"என்ன\s+வாங்க\s+வேண்டும்",
        r"^என்\s+(?:பட்டியல்|லிஸ்ட்)$",
    ),
    clear_cues=(
        r"(?:பட்டியல்|பட்டியலை|லிஸ்ட்)\s+(?:அழி|காலி\s+செய்)\s*(?:வும்|ு)?",
        r"(?:பட்டியலை|லிஸ்ட்டை)\s+காலி\s*(?:செய்|பண்ணு)?",
        r"எல்லாம்\s+(?:நீக்கு|அழி)\s*(?:வும்|ு)?",
        r"எல்லாவற்றையும்\s+நீக்கு",
        r"கிளியர்\s*(?:பண்ணு|செய்)?",
    ),
    confirm_words=frozenset({
        "ஆம்", "ஆமாம்", "சரி", "ஓகே", "நிச்சயம்", "செய்",
        "confirm", "yes", "ok",
    }),
    cancel_words=frozenset({
        "இல்லை", "வேண்டாம்", "வேணாம்", "நிறுத்து", "ரத்து", "விடு",
        "cancel", "no", "stop",
    }),
    number_words=_NUMBER_WORDS,
    tens_words={"இருபது": 20, "முப்பது": 30, "நாற்பது": 40, "ஐம்பது": 50},
    units=_UNITS,
    dozen_words=frozenset({"டஜன்"}),
    price_cue_position="both",
    max_price_cues=(
        r"கீழ்", r"கீழே", r"குறைவாக", r"குறைவான", r"வரை",
        r"விட\s+குறைவு", r"மலிவான",
        r"under", r"below",
    ),
    min_price_cues=(
        r"மேல்", r"மேலே", r"அதிகமாக", r"அதிகமான",
        r"விட\s+அதிகம்",
        r"over", r"above",
    ),
    range_cues=(r"இடையே", r"இடையில்", r"between"),
    range_join=("மற்றும்", "முதல்", "to", "and"),
    # Tamil fuses case markers onto nouns, so the dative form of "dollar" is a
    # single token. Both forms are listed so the amount pattern absorbs them.
    currency_words=(
        "டாலருக்கு", "டாலர்", "டாலர்கள்",
        "ரூபாய்க்கு", "ரூபாய்", "ரூபாய்கள்",
        "dollars", "rupees",
    ),
    attributes=_ATTRIBUTES,
    item_aliases=_ITEM_ALIASES,
    stopwords=_STOPWORDS,
    replacement_cues=(r"பதிலாக", r"ஆக", r"க்கு", r"என"),
    examples=(
        "எனக்கு இரண்டு லிட்டர் பால் வேண்டும்",
        "ஐந்து ஆப்பிள் சேர்",
        "பட்டியலிலிருந்து பால் நீக்கு",
        "ஆர்கானிக் ஆப்பிள் தேடு",
        "பற்பசை 5 டாலருக்கு கீழ் தேடு",
        "பட்டியல் காட்டு",
    ),
)
