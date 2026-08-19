# Approach

*196 words.*

The core problem is trust: a voice app that acts on a misheard command is worse
than one that does nothing. So every command shows what was heard, what was
understood, and what was done, and anything destructive or uncertain asks first.

Speech capture must live in the browser, so I put it behind a small wrapper and
kept everything else — parsing, search, ranking — in Python, where it is
testable. FastAPI serves both the API and the static frontend; the server is
stateless, with the list in `localStorage` and history travelling with each
request. No database, no accounts, one deployable process.

The parser is deterministic: a staged pipeline of normalize, intent, price,
quantity, brand, attributes, item. Price is extracted before quantity because
"under $5" contains a number that isn't a quantity. An optional Groq fallback
runs only when those rules return UNKNOWN, is off without a key, and its
results are always offered for confirmation rather than applied — so the fast
path stays free, offline and reproducible.

Multilingual support is structural: each language is a pack of cues, numerals,
units and price grammar, so Hindi's and Tamil's verb-final order and
postpositional prices work.

347 tests pass.
