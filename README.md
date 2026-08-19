# Voice Command Shopping Assistant

A voice-driven shopping list. Speak naturally — *"I need two litres of milk"*,
*"find toothpaste under $5"*, *"remove milk from my list"* — and the app works
out what you meant, does it, and tells you exactly what it understood.

Built with **FastAPI + Python** for all the logic, and a small vanilla-JS
frontend for speech capture and UI. No build step, no database, no API keys.

---

## Table of contents

- [What it does](#what-it-does)
- [Quick start](#quick-start)
- [Architecture](#architecture)
- [How the command parser works](#how-the-command-parser-works)
- [Multilingual support](#multilingual-support-and-its-limits)
- [How recommendations work](#how-recommendations-work)
- [Voice browser support](#voice-browser-support)
- [Testing](#testing)
- [Deployment](#deployment)
- [Project layout](#project-layout)
- [Known limitations](#known-limitations)
- [Future improvements](#future-improvements)

---

## What it does

### Voice input
- Speak a command; the app shows a live transcript as you talk.
- Three-line feedback on every command: **what you said**, **what it
  understood**, **what it did**. Nothing happens invisibly.
- Works in English, Hindi and Spanish (see
  [multilingual support](#multilingual-support-and-its-limits)).
- A text box is always available and does exactly the same thing, so the app is
  fully usable without a microphone.

### Natural-language commands
Not string matching. All of these reach the same intent:

| You say | Intent | Extracted |
|---|---|---|
| "Add milk" | `ADD_ITEM` | item=milk |
| "I need apples" | `ADD_ITEM` | item=apples |
| "I want to buy bananas" | `ADD_ITEM` | item=bananas |
| "Put eggs on my shopping list" | `ADD_ITEM` | item=eggs |
| "I need 2 litres of milk" | `ADD_ITEM` | item=milk, qty=2, unit=litre |
| "Please add five apples" | `ADD_ITEM` | item=apples, qty=5 |
| "Add two and a half kg of potatoes" | `ADD_ITEM` | item=potatoes, qty=2.5, unit=kg |
| "Take eggs off my list" | `REMOVE_ITEM` | item=eggs |
| "Change milk to almond milk" | `UPDATE_ITEM` | item=milk, replacement=almond milk |
| "Change milk to 2 litres" | `UPDATE_ITEM` | item=milk, qty=2, unit=litre |
| "Find organic apples under five dollars" | `SEARCH_PRODUCT` | item=apples, attributes=[organic], max_price=5 |
| "Show me Colgate under $5" | `SEARCH_PRODUCT` | brand=Colgate, max_price=5 |
| "Find a 1 litre bottle of milk" | `SEARCH_PRODUCT` | item=milk, qty=1, unit=litre |
| "Clear my list" | `CLEAR_LIST` | *(asks for confirmation first)* |

### Shopping list
Add, remove, edit, set quantities and units, tick items off, undo, clear
completed. Items are **categorised automatically** (milk → Dairy, toothpaste →
Personal Care) and the list is grouped by aisle. State persists in
`localStorage`.

### Voice search
Product search with **brand**, **price** and **attribute** filters, over a
147-product sample catalogue. The interpreted query is always shown as chips
("Searching for: toothpaste · Brand: Colgate · Max price: $5") so you can see
why you got those results. Price grammar covers *under / below / less than /
cheaper than / over / above / at least / between X and Y / up to*.

### Smart suggestions
Every suggestion card says **why** it is there — "Bought 4 times in the last
month", "In season right now", "Goes well with Penne Pasta on your list",
"Whole Milk 1L is unavailable — try this instead".

### Substitutes
Products carry an alternatives graph. When something is out of stock the app
offers in-stock replacements inline: *"Whole Milk 1L isn't available. Try these
instead: Almond Milk · Oat Milk · Soy Milk."*

---

## Quick start

Requires **Python 3.11+**. No Node, no build step.

```bash
python -m venv .venv
```

```bash
source .venv/bin/activate
```

On Windows use `.venv\Scripts\activate` instead.

```bash
pip install -r requirements-dev.txt
```

```bash
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. Interactive API docs are at `/docs`.

> **Microphone note:** browsers only allow speech recognition on `https://` or
> on `localhost`. `127.0.0.1` and `localhost` both count as secure origins, so
> local development works. Accessing a dev server over a LAN IP will not.

### Environment variables

**None are required.** There is no database, no API key and no third-party
service. See [`.env.example`](.env.example) for the two optional knobs (`PORT`,
`LOG_LEVEL`) that hosting platforms normally set for you.

---

## Architecture

```
        Browser                                  Python (FastAPI)
┌────────────────────────┐              ┌──────────────────────────────┐
│  Web Speech API        │              │                              │
│      ↓ transcript      │              │   normalize                  │
│  speech.js             │              │      ↓                       │
│      ↓                 │  POST /parse │   intent detection           │
│  app.js  ──────────────┼─────────────▶│      ↓                       │
│      ↑                 │              │   price → quantity → brand   │
│      │  ParsedCommand  │              │      → attributes → item     │
│      │  + search hits  │◀─────────────┤      ↓                       │
│      ↓                 │              │   categorize                 │
│  intent dispatch       │              │      ↓                       │
│      ↓                 │              │   catalog search  ───────────┤
│  store.js              │              │   recommendations ───────────┤
│   (localStorage)       │              │                              │
│      ↓                 │              │   147-product JSON catalogue │
│  ui.js  → render       │              │                              │
└────────────────────────┘              └──────────────────────────────┘
```

### Why this shape

**The server is stateless.** The browser owns the shopping list; history and
current items travel with each request. That means no database, no accounts, no
sessions and no personal data at rest — and deployment is a single process.

**Speech capture is the only thing in JavaScript that has to be.** The Web
Speech API is a browser capability with no Python equivalent, so it is isolated
behind a four-method wrapper in `web/js/speech.js`. Everything interesting —
parsing, search, ranking, recommendations — is Python, which makes it
`pytest`-testable.

**One service serves the API and the frontend.** No CORS setup, no separate
frontend build, no second deployment.

**Layer boundaries.** `nlp/` never imports `recommend/`. `catalog/` knows
nothing about HTTP. UI components hold no business logic. Swapping the JSON
catalogue for a real retailer API would touch only `app/catalog/data.py`.

---

## How the command parser works

`app/nlp/parser.py` runs a fixed, deterministic pipeline. Each stage removes
the text span it consumed, so whatever survives to the end is the item name.

```
normalize → intent detection → price → quantity/unit → brand
          → attributes → item → category → confidence
```

**Order matters.** Price is extracted before quantity because *"toothpaste
under $5"* contains a number that belongs to the price, not to the toothpaste.
Item extraction runs last precisely because it is the leftovers.

**Intent detection** matches cue patterns anywhere in the utterance and scores
by matched-span length, so a specific cue beats a shorter one nested inside it
("I want to buy" > "buy"; "remove everything" is `CLEAR_LIST`, not a removal of
an item called "everything"). Every cue belonging to the winning intent is
stripped, which is how English separable verbs work: *"take eggs **off my
list**"* has the removal cue in two pieces around the item.

**Confidence** is reported on every command. Below `0.45` the UI asks *"Did you
mean…?"* rather than acting. Destructive commands always confirm, regardless of
confidence.

### Why not an LLM?

The grammar of a shopping command is small and closed. A dictionary-driven
parser is:

- **Deterministic** — the same utterance always gives the same result, which
  is what makes the 200+ tests meaningful.
- **Free and offline** — no API key, no per-request cost, no rate limit.
- **Fast** — sub-millisecond, no network hop on the critical path.
- **Debuggable** — when it gets something wrong you can point at the rule.

An LLM would be the right call for genuinely open-ended phrasing. If added, it
belongs behind an adapter at the `parse()` boundary, as a fallback for
`Intent.UNKNOWN`, so the app keeps working when the key is missing or the
service is down.

---

## Multilingual support, and its limits

**This is real, not a dropdown that only changes the speech locale.**

Each language is a self-contained pack in `app/nlp/lexicons/` supplying its own
intent cues, numerals, units, price grammar, attribute adjectives, stopwords
and grocery vocabulary. The parser pipeline itself contains no
language-specific logic. Adding a language means adding one module and
registering it.

| | English | Hindi | Spanish |
|---|---|---|---|
| Speech locale | `en-US` | `hi-IN` | `es-ES` |
| Intent cues | ✅ | ✅ | ✅ |
| Spelled-out numerals | ✅ | ✅ (+ Devanagari digits ०-९) | ✅ |
| Units | ✅ | ✅ | ✅ |
| Price filters | ✅ | ✅ (postpositional) | ✅ |
| Attributes | ✅ | ✅ | ✅ |
| Catalogue search | ✅ | ✅ (via vocabulary map) | ✅ |

Two structural differences are handled explicitly:

- **Hindi is verb-final.** "दूध डालो" is literally *milk add*. Because cues are
  matched anywhere and then removed, word order needs no special handling.
- **Hindi price comparatives are postpositional.** "5 डॉलर से कम" is literally
  *5 dollars from less*, so the Hindi pack sets `price_cue_position="both"`.

**Display vs. lookup.** The catalogue is authored in English. Each non-English
pack carries a dictionary of common grocery nouns (दूध → milk, leche → milk),
so a Hindi utterance can search an English catalogue. Your own words are what
appear on your list; the English term is only used for lookup and
categorisation.

### The honest limitations

- **Three languages, not "multilingual".** English, Hindi and Spanish are
  implemented and tested. Other locales fall back to the English parser rather
  than erroring — best-effort, not support.
- **The vocabulary map covers common groceries, roughly 60–90 nouns per
  language.** It is not a translator. An unusual Hindi or Spanish item name
  will still be added to your list correctly, but may not match a catalogue
  product or categorise correctly.
- **Hindi fractional numerals are partial.** डेढ़ (1.5) and ढाई (2.5) work as
  number words; the prefix construction साढ़े तीन (3.5) does not.
- **Browser speech quality varies by locale** and is outside the app's control.

---

## How recommendations work

`app/recommend/engine.py`. A weighted sum of five signals — **not** a machine
learning model, and it does not claim to be:

| Signal | Weight | Meaning |
|---|---|---|
| `frequent` | 2.2 × min(count, 5) | How often you have bought it |
| `recent` | 3.0 × e^(−days/14) | Exponential decay; two weeks ≈ ⅓ score |
| `seasonal` | 2.6 | In season this calendar month |
| `complementary` | 3.0 | Pairs with something already on your list |
| `substitute` | 4.0 | Replaces a list item that is unavailable |

Scores sum, so several weak signals can outrank one strong one. The card shows
the single **strongest** reason as its explanation.

Items already on your list, and out-of-stock products, are never suggested. A
brand-new user with no history still sees staples, so the rail is never empty.

**Why heuristics.** Explainability is worth more than accuracy at this scale. A
user can read "Bought 4 times in the last month" and immediately judge whether
the suggestion is sensible. A learned model would need purchase data this
application does not have, and could not justify itself to the person reading
it.

---

## Voice browser support

Speech recognition uses the Web Speech API (`SpeechRecognition` /
`webkitSpeechRecognition`), which is **not universally available**:

| Browser | Support |
|---|---|
| Chrome (desktop & Android) | ✅ Yes — audio is sent to Google's servers |
| Edge | ✅ Yes — cloud-based |
| Safari (macOS & iOS) | ✅ Yes |
| Firefox | ❌ No |
| Most in-app/embedded browsers | ⚠️ Unreliable |

**The app degrades gracefully and this is tested, not assumed.** When the API
is missing, a banner explains it, the text input takes over, and every other
feature — parsing, search, suggestions, substitutes, persistence — works
identically. Every command in the QA pass was driven through the text path.

Handled failures: API unavailable, microphone permission denied, no microphone,
no speech detected, network loss, language not supported by the engine. Each
produces a plain-English message; none produce a stack trace.

**HTTPS is required** in production. All the deployment targets below provide it
automatically.

---

## Testing

```bash
pytest
```

**264 tests, all passing**, covering the logic that would actually break:

| File | Tests | Covers |
|---|---|---|
| `test_parser_en.py` | 77 | Intents, phrasings, quantities, units, prices, brands, attributes, confidence, hostile input |
| `test_parser_multilingual.py` | 58 | Hindi & Spanish intents, numerals, units, price grammar, locale fallback |
| `test_search.py` | 27 | Keyword relevance, brand/price/attribute/category filters, combined filters, no-result fallbacks |
| `test_catalog.py` | 51 | Catalogue integrity (every alternative/complement id resolves), categorisation, compound-name collisions |
| `test_recommend.py` | 18 | Frequency, recency decay, seasonality, complements, substitutes, exclusions |
| `test_api.py` | 33 | Every endpoint, validation errors, 404s, static asset serving |

Several tests are named regressions for bugs found during development — for
example `test_query_category_outranks_incidental_word_match` (searching "milk"
used to return *Milk Chocolate Bar* first) and
`test_hindi_combining_marks_survive_normalization` (a `\w`-based strip silently
turned "मुझे" into "म झ").

Run a subset:

```bash
pytest tests/test_parser_en.py -v
```

---

## Deployment

> **Not deployed.** No hosting credentials were available in this environment,
> so there is no live URL. The production build **has** been verified locally:
> a clean virtualenv with production-only dependencies, started with the exact
> command below, serving every route correctly.

### Render — recommended, ~2 minutes

Simplest reliable option for a Python service: free tier, no container, HTTPS
included. [`render.yaml`](render.yaml) is committed, so:

1. Push this repository to GitHub.
2. Render → **New** → **Blueprint** → select the repo.
3. Deploy. Render reads `render.yaml` and needs no further configuration.

### Vercel

[`vercel.json`](vercel.json) and [`api/index.py`](api/index.py) are committed.

```bash
npx vercel --prod
```

### Railway / Fly / any Procfile host

[`Procfile`](Procfile) is committed.

### Google Cloud Run — no Dockerfile needed

```bash
gcloud run deploy voice-shopping --source . --allow-unauthenticated
```

Cloud Run's buildpacks detect `requirements.txt` and `Procfile` automatically.

### Manual

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Deployment checklist

- [x] Production build verified from a clean environment
- [x] Production dependencies pinned (`requirements.txt`)
- [x] Python version pinned (`runtime.txt`, `render.yaml`)
- [x] Health check endpoint (`/healthz`) for platform probes
- [x] No development-only assumptions (no `--reload`, no debug flags)
- [x] No secrets in the repository; none required
- [x] Static assets served by the same process
- [x] HTTPS provided by every target platform (required for microphone access)

---

## Project layout

```
app/
  main.py                  FastAPI app; serves the API and the frontend
  models.py                Pydantic schemas — the whole data contract
  api/routes.py            HTTP endpoints
  nlp/
    normalize.py           Unicode-safe text normalisation
    numbers.py             Numerals, digits and words, any language
    price.py               Price constraint extraction
    quantity.py            Quantity and unit extraction
    parser.py              The pipeline
    translate.py           Item name → catalogue vocabulary
    lexicons/
      base.py              The shape of a language pack
      en.py  hi.py  es.py  The three packs
  catalog/
    products.json          147 sample products
    data.py                Loading and lookup indexes
    categorize.py          Automatic categorisation
    search.py              Relevance scoring and filters
  recommend/engine.py      Explainable recommendation scoring
web/
  index.html  styles.css   Mobile-first UI, no framework
  js/
    speech.js              Web Speech API wrapper (the only browser-only part)
    api.js                 Fetch client with timeouts and readable errors
    store.js               localStorage-backed list, history and undo
    ui.js                  Rendering
    format.js              Shared display formatting
    app.js                 Orchestration and intent dispatch
tests/                     264 tests
```

---

## Known limitations

Being straight about what this is and is not:

1. **Not deployed.** No hosting credentials were available. Config is committed
   and the production build is verified locally, but there is no live URL.
2. **Three languages**, not general multilingual support. Everything else falls
   back to English parsing.
3. **The product catalogue is sample data** — 147 hand-authored items with
   plausible US prices. It is not a real retailer feed, and stock status is
   fixed rather than live.
4. **Purchase history is seeded demo data** on first load, clearly labelled in
   the UI and resettable. Real history accumulates as you add items.
5. **The list is per-browser.** `localStorage` means no sync across devices and
   no sharing. That is a deliberate trade-off against building accounts.
6. **`days_ago` in history does not advance.** It is recorded when an item is
   added and not aged by a background job, so recency scores drift over a long
   session.
7. **No LLM.** Genuinely novel phrasing outside the cue dictionaries returns
   `UNKNOWN` with a helpful prompt rather than a guess.
8. **Speech accuracy is the browser's**, and varies considerably by locale,
   accent and background noise.
9. **No authentication or rate limiting.** Appropriate for a stateless demo
   with no user data; not for production traffic.
10. **The frontend has no automated tests.** Business logic lives in Python and
    is well covered; the UI was verified through scripted manual QA.

---

## Future improvements

Roughly in the order I would actually do them:

1. **LLM fallback behind an adapter** for `UNKNOWN` intents only, keeping the
   deterministic parser as the fast path and the LLM as a safety net.
2. **Accounts and a real database** (Postgres), turning the stateless design
   into a syncing one — the API shape barely changes, since history is already
   an explicit request parameter.
3. **Real catalogue integration** via a retailer API, replacing
   `app/catalog/data.py` behind its existing interface.
4. **Frontend tests** with Playwright for the journeys currently covered by
   manual QA.
5. **Learned recommendations** once real purchase data exists, keeping the
   heuristic scores as explainable features rather than replacing them.
6. **Offline support** via a service worker — the parser is server-side today,
   which is the one thing standing between this and a fully offline PWA.
7. **More languages**, which is now a data task rather than an engineering one.

---

## Licence

Sample project built for a technical assessment. Product data is fictional.
