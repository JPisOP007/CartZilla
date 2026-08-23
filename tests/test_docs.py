"""The documentation has to stay true.

The README's test count drifted across three revisions, each time getting
further from reality. A number that is wrong in the README is worse than no
number: it is the first thing a reader checks, and the first thing that
undermines the rest of the document.

There are two suites with two counts - Python here, and the frontend suite run
with ``node --test`` - so each is matched by its own distinct phrasing rather
than by any "N tests" in the file.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
JS_SUITE = ROOT / "tests" / "js" / "store.test.mjs"

#: Below this, the run is a single file rather than the whole suite, and the
#: collected count says nothing about the project total.
_FULL_SUITE_THRESHOLD = 100


def _python_count_claims(text: str) -> list[int]:
    """Claims about the Python suite, matched by their full phrasing."""
    return [int(match) for match in re.findall(r"(\d{2,5}) tests, all passing", text)]


def _js_count_claim(text: str) -> int | None:
    """The count stated for the frontend suite, if any."""
    match = re.search(r"\*\*(\d{1,4}) tests\.\*\*", text)
    return int(match.group(1)) if match else None


def test_readme_exists_and_names_the_project() -> None:
    text = README.read_text(encoding="utf-8")
    assert text.startswith("# CartZilla")
    assert "cartzilla-admk.onrender.com" in text


def test_readme_python_test_count_matches_reality(
    request: pytest.FixtureRequest,
) -> None:
    """Every "N tests, all passing" claim must equal the real total."""
    collected = len(request.session.items)
    if collected < _FULL_SUITE_THRESHOLD:
        pytest.skip("only meaningful when the whole suite is collected")

    claims = _python_count_claims(README.read_text(encoding="utf-8"))
    assert claims, "the README no longer states a Python test count"

    wrong = [claim for claim in claims if claim != collected]
    assert not wrong, (
        f"README claims {wrong} tests but the suite collects {collected}. "
        "Update the count, or drop the number from that sentence."
    )


def test_readme_frontend_test_count_matches_the_js_suite() -> None:
    """The frontend count is maintained by hand, so guard it the same way."""
    assert JS_SUITE.is_file(), "the frontend suite has gone missing"

    actual = len(re.findall(r"^\s*it\(", JS_SUITE.read_text(encoding="utf-8"), re.M))
    claimed = _js_count_claim(README.read_text(encoding="utf-8"))

    assert claimed is not None, "the README no longer states a frontend test count"
    assert claimed == actual, (
        f"README claims {claimed} frontend tests but the suite defines {actual}"
    )


def test_approach_writeup_is_within_the_word_limit() -> None:
    """The brief caps the write-up at 200 words, and it is easy to drift over."""
    text = (ROOT / "APPROACH.md").read_text(encoding="utf-8")

    stated = re.search(r"\*(\d+) words\.\*", text)
    assert stated, "APPROACH.md no longer states its own word count"

    body = text.split("words.*", 1)[1]
    actual = len(re.findall(r"[A-Za-z0-9$£€]+(?:['’-][A-Za-z0-9]+)*", body))

    assert actual <= 200, f"write-up is {actual} words, over the 200 limit"
    assert actual == int(stated.group(1)), (
        f"APPROACH.md says {stated.group(1)} words but contains {actual}"
    )


def test_env_example_documents_the_optional_key_without_containing_one() -> None:
    """The file should explain GROQ_API_KEY and never carry a real value.

    It was once deleted and pushed without anyone noticing, so its existence is
    asserted too.
    """
    path = ROOT / ".env.example"
    assert path.is_file(), ".env.example is missing"

    text = path.read_text(encoding="utf-8")
    assert "GROQ_API_KEY" in text
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        _, _, value = stripped.partition("=")
        assert not value.strip(), f"{stripped!r} has a value; .env.example must not"
