"""Regression guard: pages the model silently skips must be re-asked.

Per-page rows are matched back to pages by ``page_index`` within a batch, so a
model that omits one entry (or mis-numbers it) orphans that page with
"evaluator returned no row for this page". The orphaned page then drops out of
the consuming rule entirely.

That is not cosmetic. On 2026-07-20 ``/custom-software-development-services``
was judged FAILING; on 2026-07-22 the same page returned no row, vanished from
the verdict, ``pages_failed`` went 1 -> 0, and both P1-22 and P6-19 flipped to
"passed" with no site change whatsoever.

``run_evaluator`` now re-asks for those pages one per call, where index
matching is unambiguous. These tests pin that behaviour.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from seomate.adapters.llm import LlmBatchResult
from seomate.utils.llm_evaluation import MAX_NO_ROW_RETRY_PAGES, run_evaluator


@dataclass
class _Evaluator:
    """Batches pages, returns one row per page_index the model supplied."""

    eval_type: str = "schema_visible_match"
    batch_size: int = 5
    urls: tuple[str, ...] = ()

    def collect_items(self, site: Any) -> list[tuple[str, dict[str, Any]]]:
        return [(u, {}) for u in self.urls]

    def build_prompt(self, batch):  # noqa: ANN001
        return ("sys", f"{len(batch)} pages")

    def parse_result(self, result: LlmBatchResult, batch):  # noqa: ANN001
        from seomate.utils.llm_evaluation import LlmEvaluation

        by_index = {
            it["page_index"]: it
            for it in (result.parsed or [])
            if isinstance(it.get("page_index"), int)
        }
        out = {}
        for idx, (url, _) in enumerate(batch, start=1):
            item = by_index.get(idx)
            if item is None:
                out[url] = LlmEvaluation(
                    page_url=url, eval_type=self.eval_type, passed=None,
                    confidence=0.0, error="evaluator returned no row for this page",
                )
            else:
                out[url] = LlmEvaluation(
                    page_url=url, eval_type=self.eval_type,
                    passed=bool(item["passes"]), confidence=1.0,
                )
        return out


@dataclass
class _FlakyLlm:
    """Drops the last row of any multi-page batch; answers single pages fully.

    This is the real-world failure: long batches lose an entry, single-page
    calls do not.
    """

    drop_verdict: bool = False
    calls: list[int] = field(default_factory=list)

    async def batch_evaluate(self, *, system_prompt: str, user_prompt: str,
                             max_tokens: int = 4096) -> LlmBatchResult:
        n = int(user_prompt.split()[0])
        self.calls.append(n)
        rows = [{"page_index": i, "passes": True} for i in range(1, n + 1)]
        if n > 1:
            rows = rows[:-1]  # silently drop the final page
        elif self.drop_verdict:
            rows = []  # even the retry fails
        return LlmBatchResult(
            raw_text="", parsed=rows, input_tokens=0, output_tokens=0, model="test"
        )


def _run(evaluator, llm, retry_missing=True):
    return asyncio.run(
        run_evaluator(evaluator, object(), llm, retry_missing=retry_missing)
    )


def test_skipped_page_is_re_asked_and_recovered():
    """The dropped page must come back with a real verdict, not an error."""
    ev = _Evaluator(urls=("https://ex.com/a", "https://ex.com/b", "https://ex.com/c"))
    llm = _FlakyLlm()
    out = _run(ev, llm)

    assert out["https://ex.com/c"].passed is True, (
        "the skipped page must be re-asked and recovered, otherwise it silently "
        "drops out of the rule and can invert the variable"
    )
    assert out["https://ex.com/c"].error is None
    assert 1 in llm.calls, "a single-page repair call should have been made"


def test_without_retry_the_page_is_lost():
    """Pins the old behaviour so the value of the retry stays visible."""
    ev = _Evaluator(urls=("https://ex.com/a", "https://ex.com/b"))
    out = _run(ev, _FlakyLlm(), retry_missing=False)
    assert out["https://ex.com/b"].passed is None
    assert "no row" in (out["https://ex.com/b"].error or "")


def test_retry_that_also_fails_stays_an_honest_error():
    """A page we genuinely cannot judge must stay unverdicted, never assumed."""
    ev = _Evaluator(urls=("https://ex.com/a", "https://ex.com/b"))
    out = _run(ev, _FlakyLlm(drop_verdict=True))
    assert out["https://ex.com/b"].passed is None, (
        "an unjudgeable page must not be silently coerced to a pass"
    )


def test_repair_pass_is_capped():
    """Many gaps means systemic failure; do not spend a call per page."""
    urls = tuple(f"https://ex.com/{i}" for i in range(60))
    ev = _Evaluator(urls=urls, batch_size=2)
    llm = _FlakyLlm(drop_verdict=True)
    _run(ev, llm)
    single_calls = [c for c in llm.calls if c == 1]
    assert len(single_calls) <= MAX_NO_ROW_RETRY_PAGES, (
        f"repair pass must cap at {MAX_NO_ROW_RETRY_PAGES} single-page calls"
    )
