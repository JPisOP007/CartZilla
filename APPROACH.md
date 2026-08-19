# Approach

*197 words.*

The core problem is trust: a voice app that acts on a misheard command is worse
than one that does nothing. So every command shows what was heard, what was
understood, and what was done, and low-confidence or destructive commands ask
first.

Speech capture must live in the browser, so I put it behind a small wrapper and
kept everything else — parsing, search, ranking — in Python, where it is
testable. FastAPI serves both the API and the static frontend; the server is
stateless, with the list in `localStorage` and history travelling with each
request. No database, no accounts, one deployable process.

I chose a deterministic parser over an LLM. Shopping commands are a small,
closed grammar, so a staged pipeline — normalize, intent, price, quantity,
brand, attributes, item — is faster, free, offline, and reproducible enough to
test properly. Price is extracted before quantity because "under $5" contains a
number that isn't a quantity.

Multilingual support is real: each language is a pack of cues, numerals, units
and price grammar, so Hindi's verb-final order and postpositional prices work.
Recommendations are explainable heuristics; every card states why.

264 tests pass. Main tradeoff: novel phrasing returns UNKNOWN rather than a guess.
