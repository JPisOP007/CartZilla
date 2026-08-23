"""The documentation has to stay true.

The README's test count drifted across three revisions, each time getting
further from reality. A number that is wrong in the README is worse than no
number: it is the first thing a reader checks and the first thing that
undermines the rest of the document.

The per-file breakdown in the README is left to human maintenance; this guards
the headline totals, which are the ones anyone actually reads.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

README = Path(__file__).resolve().parent.parent / "README.md"

#: Below this, the run is a single file rather than the whole suite, and the
#: collected count says nothing about the project total.
_FULL_SUITE_THRESHOLD = 100


def _claimed_counts(text: str) -> list[int]:
    """Every "N tests" claim in the README."""
    return [int(match) for match in re.findall(r"\b(\d{2,5}) tests\b", text)]


def test_readme_exists_and_names_the_project() -> None:
    text = README.read_text(encoding="utf-8")
    assert text.startswith("# CartZilla")
    assert "cartzilla-admk.onrender.com" in text


def test_readme_test_counts_match_reality(request: pytest.FixtureRequest) -> None:
    """Every "N tests" claim in the README must equal the real total."""
    collected = len(request.session.items)
    if collected < _FULL_SUITE_THRESHOLD:
        pytest.skip("only meaningful when the whole suite is collected")

    claims = _claimed_counts(README.read_text(encoding="utf-8"))
    assert claims, "the README no longer states a test count"
    wrong = [claim for claim in claims if claim != collected]
    assert not wrong, (
        f"README claims {wrong} tests but the suite collects {collected}. "
        "Update the count, or drop the number from that sentence."
    )


def test_approach_writeup_is_within_the_word_limit() -> None:
    """The brief caps the write-up at 200 words, and it is easy to drift over."""
    path = README.parent / "APPROACH.md"
    text = path.read_text(encoding="utf-8")

    stated = re.search(r"\*(\d+) words\.\*", text)
    assert stated, "APPROACH.md no longer states its own word count"

    body = text.split("words.*", 1)[1]
    actual = len(re.findall(r"[A-Za-z0-9$£€]+(?:['’-][A-Za-z0-9]+)*", body))

    assert actual <= 200, f"write-up is {actual} words, over the 200 limit"
    assert actual == int(stated.group(1)), (
        f"APPROACH.md says {stated.group(1)} words but contains {actual}"
    )


def test_env_example_documents_the_optional_key_without_containing_one() -> None:
    """The file should explain GROQ_API_KEY and never carry a real value."""
    text = (README.parent / ".env.example").read_text(encoding="utf-8")
    assert "GROQ_API_KEY" in text
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        _, _, value = stripped.partition("=")
        assert not value.strip(), f"{stripped!r} has a value; .env.example must not"
