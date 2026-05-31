"""Batched LLM evaluation utility (H1c).

Every LLM evaluator follows the same shape:

1. ``collect_items(site)`` returns the list of per-page inputs.
2. ``build_prompt(batch)`` produces a single Claude prompt that
   evaluates *N pages at once*, asking for a structured JSON array.
3. ``parse_result(parsed, batch)`` maps the JSON array back to per-page
   ``LlmEvaluation`` records.

The orchestrator runs each evaluator once at audit start, in fixed-size
batches, and caches results on ``SiteData.llm_evaluations``. Extractors
then read from the cache the same way they read DataForSEO Instant
Pages or Gemini embeddings — no per-extractor LLM calls.

Batching is mandatory (per Humza's 2Connect experience: single-page
calls truncate and oversimplify). Default batch size 5; tune per
evaluator if pages are unusually long.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlsplit

from seomate.adapters.llm import LlmAdapter, LlmBatchResult, LlmNotConfigured
from seomate.pillars._base import SiteData


# ─── Output dataclass ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class LlmEvaluation:
    """One per-page evaluation result.

    ``passed`` is the variable-aligned pass/fail. ``confidence`` is the
    evaluator's self-reported confidence (0.0–1.0). ``issues`` is a
    short list of concrete violations the evaluator surfaced so the
    extractor can write them straight into rule evidence.
    """

    page_url: str
    eval_type: str
    passed: bool | None
    confidence: float
    issues: tuple[str, ...] = ()
    rationale: str = ""
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


# ─── Evaluator protocol ─────────────────────────────────────────────────────


class LlmEvaluator(Protocol):
    """Per-evaluation-type batched evaluator."""

    eval_type: str
    batch_size: int

    def collect_items(self, site: SiteData) -> list[tuple[str, dict[str, Any]]]:
        """Return [(page_url, input_payload)] for every page to evaluate.

        Skip pages that the evaluator can't say anything useful about
        (e.g. no schema for SchemaVisibleMatch).
        """
        ...

    def build_prompt(
        self,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for one batch."""
        ...

    def parse_result(
        self,
        result: LlmBatchResult,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, LlmEvaluation]:
        """Map LLM output back to {page_url: LlmEvaluation}.

        Missing / malformed items must produce an LlmEvaluation with
        ``passed=None`` and a populated ``error`` rather than silently
        dropping the page.
        """
        ...


# ─── Orchestration ──────────────────────────────────────────────────────────


async def run_evaluator(
    evaluator: LlmEvaluator,
    site: SiteData,
    llm: LlmAdapter,
    *,
    concurrency: int = 3,
) -> dict[str, LlmEvaluation]:
    """Run one evaluator across all eligible pages in batches.

    Concurrency caps how many in-flight Claude calls we hold at once
    — Anthropic's free-tier rate limit is 50 RPM, so 3 in flight is
    comfortable. Returns ``{page_url: LlmEvaluation}``.
    """
    items = evaluator.collect_items(site)
    if not items:
        return {}

    sem = asyncio.Semaphore(concurrency)
    out: dict[str, LlmEvaluation] = {}

    async def _process_batch(
        batch: list[tuple[str, dict[str, Any]]],
    ) -> None:
        async with sem:
            system_prompt, user_prompt = evaluator.build_prompt(batch)
            try:
                result = await llm.batch_evaluate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
            except LlmNotConfigured:
                # Adapter unavailable mid-run; surface as error per page.
                for url, _ in batch:
                    out[url] = LlmEvaluation(
                        page_url=url,
                        eval_type=evaluator.eval_type,
                        passed=None,
                        confidence=0.0,
                        error="LLM not configured",
                    )
                return
            except Exception as exc:  # noqa: BLE001 - failure is data
                for url, _ in batch:
                    out[url] = LlmEvaluation(
                        page_url=url,
                        eval_type=evaluator.eval_type,
                        passed=None,
                        confidence=0.0,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                return

        per_page = evaluator.parse_result(result, batch)
        out.update(per_page)

    batches = [
        items[i : i + evaluator.batch_size]
        for i in range(0, len(items), evaluator.batch_size)
    ]
    await asyncio.gather(*[_process_batch(b) for b in batches])
    return out


# ─── Helpers reused by concrete evaluators ──────────────────────────────────


def _excerpt(text: str, *, words: int = 400) -> str:
    """Truncate text to roughly ``words`` words. Keep it cheap to tokenise."""
    if not text:
        return ""
    parts = text.split()
    return " ".join(parts[:words])


def _domain_only(url: str) -> str:
    return (urlsplit(url).netloc or "").lower()


# ─── Evaluator 1: schema content vs visible content match ───────────────────


class SchemaVisibleMatchEvaluator:
    """Detects 'hidden information' violations: schema claims that are
    not borne out in the visible page text.

    Drives:
    - P1-22 rule 7 ('Schema content matches visible content')
    - P6-19 rule 8 (same rule, site-wide aggregation)
    """

    eval_type = "schema_visible_match"
    batch_size = 5

    def collect_items(self, site: SiteData) -> list[tuple[str, dict[str, Any]]]:
        items: list[tuple[str, dict[str, Any]]] = []
        for url, sd in site.structured_data.items():
            if not sd.schema_org_blocks:
                continue
            text = site.text_content.get(url)
            if text is None or not text.main_text:
                continue
            # Trim each schema block to its top-level claim fields so
            # the prompt stays compact and focused.
            schema_summaries: list[dict[str, Any]] = []
            for block in sd.schema_org_blocks[:5]:  # cap blocks per page
                schema_summaries.append(
                    {
                        "types": list(block.types),
                        "key_fields": {
                            k: _stringify_value(v)
                            for k, v in block.raw.items()
                            if not k.startswith("@") and not _is_complex(v)
                        },
                    }
                )
            items.append(
                (
                    url,
                    {
                        "schema_blocks": schema_summaries,
                        "visible_text": _excerpt(text.main_text, words=400),
                    },
                )
            )
        return items

    def build_prompt(
        self,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> tuple[str, str]:
        system = (
            "You are an SEO auditor checking whether a page's structured-data "
            "claims (schema.org / JSON-LD) match what's actually visible on the "
            "page. Per Google's structured-data policies, every fact in schema "
            "must appear in the visible page content. Hidden information is a "
            "policy violation.\n\n"
            "You will receive a batch of pages. For each, return ONE JSON object "
            "with fields: page_index (int), passes (bool: true if schema "
            "content is borne out by visible text), confidence (float 0-1), "
            "issues (array of short strings describing any specific "
            "schema-claim that is not visible). "
            "Be conservative: missing a key fact in the excerpt is acceptable "
            "if the visible text is plausibly truncated; flag only clear "
            "contradictions or claims with no visible counterpart anywhere.\n\n"
            "Return ONLY a JSON array of N objects, in input order. No prose."
        )

        page_blocks: list[str] = []
        for idx, (url, payload) in enumerate(batch, start=1):
            page_blocks.append(
                f"--- PAGE {idx} ---\nURL: {url}\n"
                f"Schema blocks: {json.dumps(payload['schema_blocks'], ensure_ascii=False)[:1800]}\n"
                f"Visible text excerpt: {payload['visible_text'][:2000]}\n"
            )
        user = (
            f"Evaluate these {len(batch)} pages. Return the JSON array.\n\n"
            + "\n\n".join(page_blocks)
        )
        return system, user

    def parse_result(
        self,
        result: LlmBatchResult,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, LlmEvaluation]:
        out: dict[str, LlmEvaluation] = {}
        if result.error or result.parsed is None:
            for url, _ in batch:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error=result.error or "no parsed output",
                    raw={"raw_text_head": result.raw_text[:200]},
                )
            return out

        by_index: dict[int, dict[str, Any]] = {}
        for item in result.parsed:
            idx = item.get("page_index")
            if isinstance(idx, int):
                by_index[idx] = item

        for idx, (url, _) in enumerate(batch, start=1):
            item = by_index.get(idx)
            if item is None:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error="evaluator returned no row for this page",
                )
                continue
            passes = item.get("passes")
            confidence = float(item.get("confidence", 0.0))
            issues_raw = item.get("issues") or []
            issues = tuple(str(x) for x in issues_raw if isinstance(x, str))
            out[url] = LlmEvaluation(
                page_url=url,
                eval_type=self.eval_type,
                passed=bool(passes) if isinstance(passes, bool) else None,
                confidence=confidence,
                issues=issues,
                rationale=str(item.get("rationale", ""))[:500],
                raw=item,
            )
        return out


# ─── Evaluator 2: headline accuracy (no clickbait / exaggeration) ───────────


class HeadlineAccuracyEvaluator:
    """Detects misleading or clickbait headlines.

    Drives the new P4-23 extractor. A headline 'passes' when it
    accurately summarises the article's substance without exaggeration,
    sensationalism, or curiosity-gap tactics ('You won't believe...').
    """

    eval_type = "headline_accuracy"
    batch_size = 5

    def collect_items(self, site: SiteData) -> list[tuple[str, dict[str, Any]]]:
        items: list[tuple[str, dict[str, Any]]] = []
        for url, page_audit in site.page_audits.items():
            text = site.text_content.get(url)
            if not page_audit.title or text is None or not text.main_text:
                continue
            # Only evaluate article-like pages — homepage and category
            # pages have a different headline contract.
            path = (urlsplit(url).path or "/").lower()
            if not any(
                seg in path
                for seg in ("/blog/", "/news/", "/article/", "/post/", "/insights/", "/case-stud")
            ):
                continue
            items.append(
                (
                    url,
                    {
                        "title": page_audit.title,
                        "h1": page_audit.h1[0] if page_audit.h1 else "",
                        "visible_text": _excerpt(text.main_text, words=200),
                    },
                )
            )
        return items

    def build_prompt(
        self,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> tuple[str, str]:
        system = (
            "You are an editorial reviewer evaluating whether article "
            "headlines accurately represent their content. A headline 'passes' "
            "when it summarises the article's actual substance without "
            "exaggeration, sensationalism, or curiosity-gap clickbait "
            "('You won't believe...', 'This one trick...', 'Doctors hate this'). "
            "Hyperbole like 'best', 'ultimate', 'complete guide' is acceptable "
            "if the content actually delivers; flag only when the content "
            "clearly fails to substantiate the claim.\n\n"
            "You will receive a batch of pages. For each, return ONE JSON "
            "object with: page_index (int), passes (bool), confidence (0-1), "
            "issues (array of short strings naming specific problems: "
            "'clickbait', 'exaggeration', 'mismatch', 'misleading_number'), "
            "rationale (short string).\n\n"
            "Return ONLY a JSON array of N objects, in input order. No prose."
        )
        page_blocks: list[str] = []
        for idx, (url, payload) in enumerate(batch, start=1):
            page_blocks.append(
                f"--- PAGE {idx} ---\nURL: {url}\n"
                f"Title: {payload['title']}\n"
                f"H1: {payload['h1']}\n"
                f"Article excerpt: {payload['visible_text'][:2000]}\n"
            )
        user = (
            f"Evaluate these {len(batch)} article headlines. Return the JSON array.\n\n"
            + "\n\n".join(page_blocks)
        )
        return system, user

    def parse_result(
        self,
        result: LlmBatchResult,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, LlmEvaluation]:
        out: dict[str, LlmEvaluation] = {}
        if result.error or result.parsed is None:
            for url, _ in batch:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error=result.error or "no parsed output",
                    raw={"raw_text_head": result.raw_text[:200]},
                )
            return out

        by_index: dict[int, dict[str, Any]] = {}
        for item in result.parsed:
            idx = item.get("page_index")
            if isinstance(idx, int):
                by_index[idx] = item

        for idx, (url, _) in enumerate(batch, start=1):
            item = by_index.get(idx)
            if item is None:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error="evaluator returned no row for this page",
                )
                continue
            passes = item.get("passes")
            confidence = float(item.get("confidence", 0.0))
            issues_raw = item.get("issues") or []
            out[url] = LlmEvaluation(
                page_url=url,
                eval_type=self.eval_type,
                passed=bool(passes) if isinstance(passes, bool) else None,
                confidence=confidence,
                issues=tuple(str(x) for x in issues_raw if isinstance(x, str)),
                rationale=str(item.get("rationale", ""))[:500],
                raw=item,
            )
        return out


# ─── Internal utilities ─────────────────────────────────────────────────────


# ─── Evaluator 3: content substance (drives P4-07 + P4-21) ──────────────────


class ContentSubstanceEvaluator:
    """One per-page evaluation that produces multiple signals consumed by
    both P4-07 (originality) and P4-21 (mass-produced) extractors.

    Signals returned per page:
    - has_original_elements (bool)
    - shows_ai_boilerplate (bool)
    - has_padding (bool)
    - shows_templating_signs (bool)
    - has_first_hand_signals (bool)
    - confidence (float)
    """

    eval_type = "content_substance"
    batch_size = 5

    def collect_items(self, site: SiteData) -> list[tuple[str, dict[str, Any]]]:
        items: list[tuple[str, dict[str, Any]]] = []
        for url, text in site.text_content.items():
            if not text.main_text or text.word_count < 200:
                continue
            items.append(
                (
                    url,
                    {
                        "word_count": text.word_count,
                        "excerpt": _excerpt(text.main_text, words=500),
                    },
                )
            )
        return items

    def build_prompt(
        self,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> tuple[str, str]:
        system = (
            "You are evaluating web content for substance and originality "
            "signals. For each page, return ONE JSON object with these "
            "boolean signals:\n\n"
            "- has_original_elements: Does the page contain original "
            "  research, original data, named case study, named "
            "  interview, or substantive original analysis (not rehashed "
            "  from common knowledge)?\n"
            "- shows_ai_boilerplate: Does the writing show clear LLM "
            "  fingerprints? Formulaic intros ('In today's fast-paced "
            "  world...'), excessive 'In conclusion', repetitive "
            "  phrasing, generic examples that don't reference real "
            "  entities, 'as an AI' giveaways.\n"
            "- has_padding: Does the page have filler that exists only "
            "  to hit length? Repeated restatement of the same idea, "
            "  empty transition paragraphs, boilerplate sections.\n"
            "- shows_templating_signs: Does the page look like part of "
            "  a template family? Generic structure where only entity "
            "  names change, scripted hero + benefits + CTA pattern "
            "  with no specific information.\n"
            "- has_first_hand_signals: Does the page show first-hand "
            "  experience? Specific dates, named clients, internal "
            "  metrics, photos referenced, or named author opinions "
            "  backed by concrete examples.\n\n"
            "Return ONLY a JSON array of N objects with: page_index "
            "(int), has_original_elements, shows_ai_boilerplate, "
            "has_padding, shows_templating_signs, has_first_hand_signals, "
            "confidence (0-1), rationale (one sentence). No prose."
        )
        page_blocks: list[str] = []
        for idx, (url, payload) in enumerate(batch, start=1):
            page_blocks.append(
                f"--- PAGE {idx} ---\nURL: {url}\n"
                f"Word count: {payload['word_count']}\n"
                f"Excerpt: {payload['excerpt'][:2500]}\n"
            )
        user = (
            f"Evaluate these {len(batch)} pages. Return the JSON array.\n\n"
            + "\n\n".join(page_blocks)
        )
        return system, user

    def parse_result(
        self,
        result: LlmBatchResult,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, LlmEvaluation]:
        out: dict[str, LlmEvaluation] = {}
        if result.error or result.parsed is None:
            for url, _ in batch:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error=result.error or "no parsed output",
                    raw={"raw_text_head": result.raw_text[:200]},
                )
            return out
        by_index: dict[int, dict[str, Any]] = {}
        for item in result.parsed:
            idx = item.get("page_index")
            if isinstance(idx, int):
                by_index[idx] = item
        for idx, (url, _) in enumerate(batch, start=1):
            item = by_index.get(idx)
            if item is None:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error="evaluator returned no row for this page",
                )
                continue
            # Synthesise a single 'passed' (originality + substance):
            # passes only when no negative signals fire AND at least one
            # positive signal (original elements OR first-hand) fires.
            passes = bool(
                not item.get("shows_ai_boilerplate", False)
                and not item.get("has_padding", False)
                and not item.get("shows_templating_signs", False)
                and (
                    item.get("has_original_elements", False)
                    or item.get("has_first_hand_signals", False)
                )
            )
            out[url] = LlmEvaluation(
                page_url=url,
                eval_type=self.eval_type,
                passed=passes,
                confidence=float(item.get("confidence", 0.0)),
                rationale=str(item.get("rationale", ""))[:500],
                raw=item,
            )
        return out


# ─── Evaluator 4: quotability (P6-02) ───────────────────────────────────────


class QuotabilityEvaluator:
    """P6-02: does the page contain self-contained, specific, attributable
    claims that LLMs would cite verbatim?
    """

    eval_type = "quotability"
    batch_size = 5

    def collect_items(self, site: SiteData) -> list[tuple[str, dict[str, Any]]]:
        items: list[tuple[str, dict[str, Any]]] = []
        for url, text in site.text_content.items():
            if not text.main_text or text.word_count < 150:
                continue
            items.append(
                (
                    url,
                    {
                        "word_count": text.word_count,
                        "excerpt": _excerpt(text.main_text, words=500),
                    },
                )
            )
        return items

    def build_prompt(
        self,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> tuple[str, str]:
        system = (
            "You are evaluating web pages for 'quotability' — whether "
            "they contain self-contained factual claims that a generative "
            "AI engine would lift verbatim into an answer. Per the "
            "GEO research literature (Aggarwal et al. 2024), quotable "
            "phrasing lifts AI source visibility 30-40%.\n\n"
            "A quotable sentence is: (a) self-contained — readable "
            "without surrounding context; (b) specific — names figures, "
            "dates, entities, or conditions; (c) attributable — clear "
            "author or named-expert; (d) digestible — between 12 and "
            "35 words; (e) factual — not marketing puffery.\n\n"
            "For each page, return ONE JSON object with: page_index "
            "(int), passes (bool: at least 5 quotable sentences and "
            ">=60% are specific), self_contained_claim_count (int), "
            "specific_claim_count (int), has_marketing_puffery_in_"
            "quotable_positions (bool), confidence (0-1), "
            "rationale (one sentence).\n\n"
            "Return ONLY a JSON array of N objects, in input order."
        )
        page_blocks: list[str] = []
        for idx, (url, payload) in enumerate(batch, start=1):
            page_blocks.append(
                f"--- PAGE {idx} ---\nURL: {url}\n"
                f"Word count: {payload['word_count']}\n"
                f"Excerpt: {payload['excerpt'][:2500]}\n"
            )
        user = (
            f"Evaluate these {len(batch)} pages for quotability. "
            f"Return the JSON array.\n\n" + "\n\n".join(page_blocks)
        )
        return system, user

    def parse_result(
        self,
        result: LlmBatchResult,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, LlmEvaluation]:
        out: dict[str, LlmEvaluation] = {}
        if result.error or result.parsed is None:
            for url, _ in batch:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error=result.error or "no parsed output",
                    raw={"raw_text_head": result.raw_text[:200]},
                )
            return out
        by_index: dict[int, dict[str, Any]] = {}
        for item in result.parsed:
            idx = item.get("page_index")
            if isinstance(idx, int):
                by_index[idx] = item
        for idx, (url, _) in enumerate(batch, start=1):
            item = by_index.get(idx)
            if item is None:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error="evaluator returned no row for this page",
                )
                continue
            passes = item.get("passes")
            out[url] = LlmEvaluation(
                page_url=url,
                eval_type=self.eval_type,
                passed=bool(passes) if isinstance(passes, bool) else None,
                confidence=float(item.get("confidence", 0.0)),
                rationale=str(item.get("rationale", ""))[:500],
                raw=item,
            )
        return out


# ─── Evaluator 5: definitional clarity (P6-10) ──────────────────────────────


class DefinitionalClarityEvaluator:
    """P6-10: does the page open with a clear, canonical definition of
    its primary subject?
    """

    eval_type = "definitional_clarity"
    batch_size = 5

    def collect_items(self, site: SiteData) -> list[tuple[str, dict[str, Any]]]:
        items: list[tuple[str, dict[str, Any]]] = []
        for url, text in site.text_content.items():
            if not text.main_text or text.word_count < 150:
                continue
            page_audit = site.page_audits.get(url)
            title = page_audit.title if page_audit else None
            items.append(
                (
                    url,
                    {
                        "title": title or "",
                        "first_300_words": _excerpt(text.main_text, words=300),
                    },
                )
            )
        return items

    def build_prompt(
        self,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> tuple[str, str]:
        system = (
            "You are evaluating web pages for 'definitional clarity' — "
            "whether the page's primary subject is defined clearly near "
            "the top, in a canonical form that LLMs can extract and "
            "reuse.\n\n"
            "A passing page: (a) has a definitional sentence in the "
            "first ~200 words of body text identifying its primary "
            "subject; (b) uses the canonical '[X] is [Y]' pattern "
            "(subject + copula + category + distinguishing property), "
            "not a benefits-led opener; (c) makes the definition "
            "unambiguous (won't confuse with similarly-named entities); "
            "(d) avoids circular definitions ('SEO is the practice of "
            "doing SEO').\n\n"
            "For each page, return ONE JSON object with: page_index "
            "(int), passes (bool: all four criteria met), "
            "has_definitional_sentence (bool), uses_canonical_form "
            "(bool), is_unambiguous (bool), is_circular (bool), "
            "confidence (0-1), rationale (one sentence).\n\n"
            "Return ONLY a JSON array of N objects, in input order."
        )
        page_blocks: list[str] = []
        for idx, (url, payload) in enumerate(batch, start=1):
            page_blocks.append(
                f"--- PAGE {idx} ---\nURL: {url}\n"
                f"Title: {payload['title']}\n"
                f"First 300 words: {payload['first_300_words'][:2200]}\n"
            )
        user = (
            f"Evaluate these {len(batch)} pages for definitional clarity. "
            f"Return the JSON array.\n\n" + "\n\n".join(page_blocks)
        )
        return system, user

    def parse_result(
        self,
        result: LlmBatchResult,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, LlmEvaluation]:
        out: dict[str, LlmEvaluation] = {}
        if result.error or result.parsed is None:
            for url, _ in batch:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error=result.error or "no parsed output",
                    raw={"raw_text_head": result.raw_text[:200]},
                )
            return out
        by_index: dict[int, dict[str, Any]] = {}
        for item in result.parsed:
            idx = item.get("page_index")
            if isinstance(idx, int):
                by_index[idx] = item
        for idx, (url, _) in enumerate(batch, start=1):
            item = by_index.get(idx)
            if item is None:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error="evaluator returned no row for this page",
                )
                continue
            passes = item.get("passes")
            out[url] = LlmEvaluation(
                page_url=url,
                eval_type=self.eval_type,
                passed=bool(passes) if isinstance(passes, bool) else None,
                confidence=float(item.get("confidence", 0.0)),
                rationale=str(item.get("rationale", ""))[:500],
                raw=item,
            )
        return out


# ─── Evaluator 6: insightfulness (P4-09) ────────────────────────────────────


class InsightfulnessEvaluator:
    """P4-09: does the page deliver insightful analysis beyond surface
    observation? A passing page surfaces causal reasoning, non-obvious
    connections, contrarian observation, or substantive data
    interpretation — not just restating what the average reader
    already knows.
    """

    eval_type = "insightfulness"
    batch_size = 5

    def collect_items(self, site: SiteData) -> list[tuple[str, dict[str, Any]]]:
        items: list[tuple[str, dict[str, Any]]] = []
        for url, text in site.text_content.items():
            if not text.main_text or text.word_count < 300:
                continue
            path = (urlsplit(url).path or "/").lower()
            # Only evaluate article-like content; marketing pages have
            # a different content contract.
            if not any(
                seg in path
                for seg in ("/blog/", "/news/", "/article/", "/post/", "/insights/", "/research/", "/case-stud")
            ):
                continue
            items.append(
                (
                    url,
                    {
                        "word_count": text.word_count,
                        "excerpt": _excerpt(text.main_text, words=500),
                    },
                )
            )
        return items

    def build_prompt(
        self,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> tuple[str, str]:
        system = (
            "You are evaluating long-form article content for "
            "'insightfulness' — whether the page goes beyond surface-"
            "level observation to deliver real analysis. Per Google's "
            "Helpful Content guidance, 'insightful analysis beyond "
            "obvious observations' is a quality marker.\n\n"
            "Look for these depth signals: causal reasoning ('this "
            "happens because...'), non-obvious connections, contrarian "
            "framing backed by reasoning, substantive data interpretation, "
            "or expert framing that surfaces nuance.\n\n"
            "Failure modes: restating common knowledge, surface-level "
            "summary, listicle without analytical commentary on each "
            "item, generic advice that applies to any topic.\n\n"
            "For each page, return ONE JSON object with: page_index "
            "(int), passes (bool), depth_signals (array of strings "
            "from: 'causal_reasoning', 'non_obvious_connection', "
            "'contrarian_view', 'data_interpretation', 'expert_framing'), "
            "surface_level (bool), confidence (0-1), rationale (one "
            "sentence).\n\n"
            "Return ONLY a JSON array of N objects, in input order."
        )
        page_blocks: list[str] = []
        for idx, (url, payload) in enumerate(batch, start=1):
            page_blocks.append(
                f"--- PAGE {idx} ---\nURL: {url}\n"
                f"Word count: {payload['word_count']}\n"
                f"Excerpt: {payload['excerpt'][:2500]}\n"
            )
        user = (
            f"Evaluate these {len(batch)} pages for insightfulness. "
            f"Return the JSON array.\n\n" + "\n\n".join(page_blocks)
        )
        return system, user

    def parse_result(
        self,
        result: LlmBatchResult,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, LlmEvaluation]:
        out: dict[str, LlmEvaluation] = {}
        if result.error or result.parsed is None:
            for url, _ in batch:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error=result.error or "no parsed output",
                    raw={"raw_text_head": result.raw_text[:200]},
                )
            return out
        by_index: dict[int, dict[str, Any]] = {}
        for item in result.parsed:
            idx = item.get("page_index")
            if isinstance(idx, int):
                by_index[idx] = item
        for idx, (url, _) in enumerate(batch, start=1):
            item = by_index.get(idx)
            if item is None:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error="evaluator returned no row for this page",
                )
                continue
            passes = item.get("passes")
            out[url] = LlmEvaluation(
                page_url=url,
                eval_type=self.eval_type,
                passed=bool(passes) if isinstance(passes, bool) else None,
                confidence=float(item.get("confidence", 0.0)),
                rationale=str(item.get("rationale", ""))[:500],
                raw=item,
            )
        return out


# ─── Evaluator 12: time-sensitivity classifier (P6-23) ──────────────────────


class TimeSensitivityClassifier:
    """P6-23: classify each page's topic as very-fresh / fresh / evergreen.

    Per-page batched. The downstream extractor combines this with the
    page-modification dates already gathered via htmldate (P4-02) to
    judge whether each page's update cadence matches its topic
    sensitivity.
    """

    eval_type = "time_sensitivity"
    batch_size = 5

    def collect_items(self, site: SiteData) -> list[tuple[str, dict[str, Any]]]:
        items: list[tuple[str, dict[str, Any]]] = []
        for url, text in site.text_content.items():
            if not text.main_text or text.word_count < 200:
                continue
            page_audit = site.page_audits.get(url)
            title = page_audit.title if page_audit else ""
            items.append(
                (
                    url,
                    {
                        "title": title or "",
                        "excerpt": _excerpt(text.main_text, words=200),
                    },
                )
            )
        return items

    def build_prompt(
        self,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> tuple[str, str]:
        system = (
            "You are classifying web pages by topic time-sensitivity. "
            "Three classes:\n\n"
            "- very_fresh: current pricing, weekly stats, news events, "
            "  scheduled releases. Content stales within weeks if not "
            "  updated.\n"
            "- fresh: annual rankings, year-tagged guides ('2026 "
            "  best...'), version comparisons. Content stales within "
            "  ~12 months.\n"
            "- evergreen: definitions, fundamentals, conceptual "
            "  explanations. Stale only if the underlying field "
            "  changes (rare).\n\n"
            "For each page return ONE JSON object with: page_index "
            "(int), time_sensitivity (one of the three strings), "
            "confidence (0-1), rationale (one sentence).\n\n"
            "Return ONLY a JSON array of N objects, in input order."
        )
        page_blocks: list[str] = []
        for idx, (url, payload) in enumerate(batch, start=1):
            page_blocks.append(
                f"--- PAGE {idx} ---\nURL: {url}\n"
                f"Title: {payload['title']}\n"
                f"Excerpt: {payload['excerpt'][:1500]}\n"
            )
        user = (
            f"Classify these {len(batch)} pages by time-sensitivity. "
            f"Return the JSON array.\n\n" + "\n\n".join(page_blocks)
        )
        return system, user

    def parse_result(
        self,
        result: LlmBatchResult,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, LlmEvaluation]:
        out: dict[str, LlmEvaluation] = {}
        if result.error or result.parsed is None:
            for url, _ in batch:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error=result.error or "no parsed output",
                    raw={"raw_text_head": result.raw_text[:200]},
                )
            return out
        by_index: dict[int, dict[str, Any]] = {}
        for item in result.parsed:
            idx = item.get("page_index")
            if isinstance(idx, int):
                by_index[idx] = item
        for idx, (url, _) in enumerate(batch, start=1):
            item = by_index.get(idx)
            if item is None:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error="evaluator returned no row",
                )
                continue
            out[url] = LlmEvaluation(
                page_url=url,
                eval_type=self.eval_type,
                passed=True,  # 'passed' = 'classified'; sensitivity in raw
                confidence=float(item.get("confidence", 0.0)),
                rationale=str(item.get("rationale", ""))[:500],
                raw=item,
            )
        return out


# ─── Evaluator 13: direct quotes from named experts (P6-05) ─────────────────


class ExpertQuoteEvaluator:
    """P6-05: does the page include direct quotes from named experts with
    full attribution (name, title, affiliation)?

    Per-page batched. LLM detects substantive quotes from named
    speakers + verifies attribution completeness.
    """

    eval_type = "expert_quote"
    batch_size = 5

    def collect_items(self, site: SiteData) -> list[tuple[str, dict[str, Any]]]:
        items: list[tuple[str, dict[str, Any]]] = []
        for url, text in site.text_content.items():
            if not text.main_text or text.word_count < 300:
                continue
            path = (urlsplit(url).path or "/").lower()
            if not any(
                seg in path
                for seg in ("/blog/", "/news/", "/article/", "/post/", "/insights/", "/research", "/case-stud")
            ):
                continue
            items.append(
                (
                    url,
                    {
                        "word_count": text.word_count,
                        "excerpt": _excerpt(text.main_text, words=500),
                    },
                )
            )
        return items

    def build_prompt(
        self,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> tuple[str, str]:
        system = (
            "You are evaluating long-form web articles for direct "
            "quotes from named experts with full attribution. Named-"
            "expert quotes are particularly likely to be lifted into "
            "AI search answers because they are pre-formatted "
            "attributable material.\n\n"
            "A quote passes when ALL of: speaker is a named individual "
            "(not 'an industry source', 'one expert', 'we believe'); "
            "attribution includes title or affiliation (not just first "
            "name); content of the quote is substantive (a claim, "
            "recommendation, or interpretation — not filler like "
            "'we're excited about this development').\n\n"
            "For each page return ONE JSON object with: page_index "
            "(int), has_named_quote (bool: at least one quote meeting "
            "all three criteria), quote_count (int: total qualifying "
            "quotes found in excerpt), filler_quote_count (int: "
            "quotes that exist but are filler-level), confidence "
            "(0-1), rationale (one sentence).\n\n"
            "Return ONLY a JSON array of N objects, in input order."
        )
        page_blocks: list[str] = []
        for idx, (url, payload) in enumerate(batch, start=1):
            page_blocks.append(
                f"--- PAGE {idx} ---\nURL: {url}\n"
                f"Word count: {payload['word_count']}\n"
                f"Excerpt: {payload['excerpt'][:2500]}\n"
            )
        user = (
            f"Evaluate these {len(batch)} pages for direct-quote "
            f"authority. Return the JSON array.\n\n"
            + "\n\n".join(page_blocks)
        )
        return system, user

    def parse_result(
        self,
        result: LlmBatchResult,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, LlmEvaluation]:
        out: dict[str, LlmEvaluation] = {}
        if result.error or result.parsed is None:
            for url, _ in batch:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error=result.error or "no parsed output",
                    raw={"raw_text_head": result.raw_text[:200]},
                )
            return out
        by_index: dict[int, dict[str, Any]] = {}
        for item in result.parsed:
            idx = item.get("page_index")
            if isinstance(idx, int):
                by_index[idx] = item
        for idx, (url, _) in enumerate(batch, start=1):
            item = by_index.get(idx)
            if item is None:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error="evaluator returned no row",
                )
                continue
            out[url] = LlmEvaluation(
                page_url=url,
                eval_type=self.eval_type,
                passed=bool(item.get("has_named_quote")),
                confidence=float(item.get("confidence", 0.0)),
                rationale=str(item.get("rationale", ""))[:500],
                raw=item,
            )
        return out


# ─── Evaluator 11: brand sentiment in LLM (P6-28) ───────────────────────────


class BrandSentimentEvaluator:
    """P6-28: how does Claude describe the brand on its own initiative?

    Brand-level (single call, batch size 1). Asks Claude an open-ended
    'tell me about [brand]' prompt and a comparative prompt; rates the
    response sentiment + detects false negative claims + outdated
    anchoring + stability across phrasings. Same evaluator family as
    BrandHallucinationEvaluator but focused on tone/sentiment rather
    than factual accuracy.
    """

    eval_type = "brand_sentiment"
    batch_size = 1

    def collect_items(self, site: SiteData) -> list[tuple[str, dict[str, Any]]]:
        if site.brand is None or not site.brand.name:
            return []
        return [(site.domain, {"brand": site.brand.name})]

    def build_prompt(
        self,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> tuple[str, str]:
        url, payload = batch[0]
        brand = payload["brand"]
        system = (
            "You are evaluating LLM-generated brand descriptions for "
            "sentiment and trust signals. You will produce TWO open-"
            "ended descriptions of a brand (a direct description and "
            "a comparative description) and then self-evaluate them.\n\n"
            "Reply ONLY with a JSON array containing ONE object with: "
            "direct_description (string: short paragraph describing "
            "the brand from training-data knowledge alone, or hedged "
            "if no knowledge), comparative_description (string: how "
            "would you compare this brand to a typical competitor in "
            "its space, or hedged if unknown), sentiment_polarity "
            "(string: 'positive' / 'neutral' / 'negative'), "
            "explicit_negative_claims (array of strings: any specific "
            "negative claims made; empty if none), would_recommend_brand "
            "(string: 'yes' / 'neutral' / 'recommend_competitor'), "
            "outdated_anchoring (bool: true if the description anchors "
            "on historic events that may no longer apply), "
            "hedged (bool: true if you don't have enough knowledge to "
            "make confident claims), confidence (0-1)."
        )
        user = (
            f"Describe '{brand}' in a paragraph. Then say how you would "
            f"compare them to a typical competitor in their space. Then "
            f"self-evaluate the sentiment, negative claims, and "
            f"recommendation tone. Return the JSON array now."
        )
        return system, user

    def parse_result(
        self,
        result: LlmBatchResult,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, LlmEvaluation]:
        out: dict[str, LlmEvaluation] = {}
        url, _ = batch[0]
        if result.error or result.parsed is None or not result.parsed:
            out[url] = LlmEvaluation(
                page_url=url,
                eval_type=self.eval_type,
                passed=None,
                confidence=0.0,
                error=result.error or "no parsed output",
                raw={"raw_text_head": result.raw_text[:200]},
            )
            return out
        item = result.parsed[0]
        polarity = str(item.get("sentiment_polarity") or "").lower()
        recommend = str(item.get("would_recommend_brand") or "").lower()
        negatives = item.get("explicit_negative_claims") or []
        outdated = bool(item.get("outdated_anchoring"))
        hedged = bool(item.get("hedged"))
        # Passes when sentiment positive/neutral, no explicit negatives,
        # no outdated anchoring, AND not recommending competitor. Hedged
        # responses pass the polarity rule (no negative content claimed).
        passes = (
            polarity in {"positive", "neutral", ""}
            and not negatives
            and not outdated
            and recommend != "recommend_competitor"
        )
        out[url] = LlmEvaluation(
            page_url=url,
            eval_type=self.eval_type,
            passed=passes,
            confidence=float(item.get("confidence", 0.0)),
            issues=tuple(str(n) for n in negatives if isinstance(n, str)),
            rationale=(
                f"polarity={polarity} hedged={hedged} outdated={outdated} "
                f"recommend={recommend}"
            ),
            raw={
                "direct_description": str(item.get("direct_description", ""))[:600],
                "comparative_description": str(item.get("comparative_description", ""))[:600],
                "polarity": polarity,
                "hedged": hedged,
                "outdated_anchoring": outdated,
                "would_recommend_brand": recommend,
                "explicit_negative_claims": negatives,
            },
        )
        return out


# ─── Evaluator 10: topic depth (P6-22) ──────────────────────────────────────


class TopicDepthEvaluator:
    """P6-22: does the page cover the canonical subtopics of its topic
    substantively, address obvious comparisons, and acknowledge
    limitations?

    Single-pass evaluator: Claude both identifies what the page's main
    topic is AND judges coverage of canonical subtopics, in one call.
    Avoids needing a separate subtopic-list source.
    """

    eval_type = "topic_depth"
    batch_size = 4   # bigger payloads — keep batch tight

    def collect_items(self, site: SiteData) -> list[tuple[str, dict[str, Any]]]:
        items: list[tuple[str, dict[str, Any]]] = []
        for url, text in site.text_content.items():
            if not text.main_text or text.word_count < 400:
                continue
            path = (urlsplit(url).path or "/").lower()
            if not any(
                seg in path
                for seg in ("/blog/", "/news/", "/article/", "/post/", "/insights/", "/guide", "/learn", "/research")
            ):
                continue
            items.append(
                (
                    url,
                    {
                        "word_count": text.word_count,
                        "excerpt": _excerpt(text.main_text, words=700),
                    },
                )
            )
        return items

    def build_prompt(
        self,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> tuple[str, str]:
        system = (
            "You are evaluating long-form article pages for 'topic "
            "depth' — whether the page covers the canonical subtopics "
            "of its primary topic, addresses obvious comparisons, and "
            "acknowledges limitations or exceptions. Pages with high "
            "topic depth are preferentially cited by AI search engines "
            "because they provide complete answers.\n\n"
            "For each page, follow this process:\n"
            "1. Identify the page's primary topic (one short phrase).\n"
            "2. Enumerate 5-8 canonical subtopics for that primary "
            "   topic (what a comprehensive article would cover).\n"
            "3. Judge how many of those canonical subtopics the page "
            "   actually addresses substantively (not just a passing "
            "   mention).\n"
            "4. Note whether the page addresses obvious comparisons "
            "   ('X vs Y', 'alternatives to X').\n"
            "5. Note whether the page acknowledges limitations / "
            "   exceptions to its claims.\n\n"
            "Return ONE JSON object per page: page_index (int), "
            "primary_topic (string), canonical_subtopics (array of "
            "strings), subtopics_covered (array of strings), "
            "coverage_pct (int 0-100), addresses_comparisons (bool), "
            "acknowledges_limitations (bool), passes (bool: "
            "coverage_pct >= 75 AND addresses_comparisons AND "
            "acknowledges_limitations), confidence (0-1), rationale "
            "(one sentence).\n\n"
            "Return ONLY a JSON array of N objects, in input order."
        )
        page_blocks: list[str] = []
        for idx, (url, payload) in enumerate(batch, start=1):
            page_blocks.append(
                f"--- PAGE {idx} ---\nURL: {url}\n"
                f"Word count: {payload['word_count']}\n"
                f"Excerpt: {payload['excerpt'][:3500]}\n"
            )
        user = (
            f"Evaluate these {len(batch)} pages for topic depth. "
            f"Return the JSON array.\n\n" + "\n\n".join(page_blocks)
        )
        return system, user

    def parse_result(
        self,
        result: LlmBatchResult,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, LlmEvaluation]:
        out: dict[str, LlmEvaluation] = {}
        if result.error or result.parsed is None:
            for url, _ in batch:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error=result.error or "no parsed output",
                    raw={"raw_text_head": result.raw_text[:200]},
                )
            return out
        by_index: dict[int, dict[str, Any]] = {}
        for item in result.parsed:
            idx = item.get("page_index")
            if isinstance(idx, int):
                by_index[idx] = item
        for idx, (url, _) in enumerate(batch, start=1):
            item = by_index.get(idx)
            if item is None:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error="evaluator returned no row",
                )
                continue
            passes = item.get("passes")
            out[url] = LlmEvaluation(
                page_url=url,
                eval_type=self.eval_type,
                passed=bool(passes) if isinstance(passes, bool) else None,
                confidence=float(item.get("confidence", 0.0)),
                rationale=str(item.get("rationale", ""))[:500],
                raw=item,
            )
        return out


# ─── Evaluator 7: YMYL classification (P0-17) ───────────────────────────────


_YMYL_CATEGORIES = (
    "health_medical",
    "financial_legal",
    "civic_government",
    "safety",
    "news_important_events",
    "sensitive_groups",
    "none",
)


class YmylClassifier:
    """P0-17: per-page YMYL classification.

    Returns per-page: ymyl (bool), category (one of QRG buckets),
    borderline (bool), confidence. Site-level summary computed by
    the P0-17 extractor.
    """

    eval_type = "ymyl"
    batch_size = 5

    def collect_items(self, site: SiteData) -> list[tuple[str, dict[str, Any]]]:
        items: list[tuple[str, dict[str, Any]]] = []
        for url, text in site.text_content.items():
            if not text.main_text or text.word_count < 100:
                continue
            page_audit = site.page_audits.get(url)
            title = page_audit.title if page_audit else ""
            items.append(
                (
                    url,
                    {
                        "title": title or "",
                        "first_300_words": _excerpt(text.main_text, words=300),
                    },
                )
            )
        return items

    def build_prompt(
        self,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> tuple[str, str]:
        system = (
            "You are classifying web pages against Google's 'Your "
            "Money or Your Life' (YMYL) categories from the Quality "
            "Rater Guidelines. YMYL content could significantly affect "
            "a person's health, financial stability, safety, civic "
            "participation, or wellbeing. Such pages are held to "
            "higher quality standards.\n\n"
            "QRG YMYL categories:\n"
            "- health_medical: medical advice, treatments, prescriptions, mental health\n"
            "- financial_legal: investments, taxes, legal advice, insurance, contracts\n"
            "- civic_government: voting, elections, government services\n"
            "- safety: vehicle safety, child safety, home safety\n"
            "- news_important_events: breaking news, war, disasters\n"
            "- sensitive_groups: content about specific demographics that could harm\n"
            "- none: not YMYL\n\n"
            "For each page, return ONE JSON object with: page_index "
            "(int), is_ymyl (bool), category (one of the strings "
            "above), borderline (bool — true if the page is "
            "ambiguous, e.g. fitness blog touching diet), confidence "
            "(0-1), rationale (one sentence).\n\n"
            "Return ONLY a JSON array of N objects, in input order."
        )
        page_blocks: list[str] = []
        for idx, (url, payload) in enumerate(batch, start=1):
            page_blocks.append(
                f"--- PAGE {idx} ---\nURL: {url}\n"
                f"Title: {payload['title']}\n"
                f"First 300 words: {payload['first_300_words'][:2200]}\n"
            )
        user = (
            f"Classify these {len(batch)} pages for YMYL. Return the "
            f"JSON array.\n\n" + "\n\n".join(page_blocks)
        )
        return system, user

    def parse_result(
        self,
        result: LlmBatchResult,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, LlmEvaluation]:
        out: dict[str, LlmEvaluation] = {}
        if result.error or result.parsed is None:
            for url, _ in batch:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error=result.error or "no parsed output",
                    raw={"raw_text_head": result.raw_text[:200]},
                )
            return out
        by_index: dict[int, dict[str, Any]] = {}
        for item in result.parsed:
            idx = item.get("page_index")
            if isinstance(idx, int):
                by_index[idx] = item
        for idx, (url, _) in enumerate(batch, start=1):
            item = by_index.get(idx)
            if item is None:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error="evaluator returned no row",
                )
                continue
            # 'passed' for the classifier means "successfully classified".
            # Whether the page IS YMYL is in the raw payload.
            out[url] = LlmEvaluation(
                page_url=url,
                eval_type=self.eval_type,
                passed=True,
                confidence=float(item.get("confidence", 0.0)),
                rationale=str(item.get("rationale", ""))[:500],
                raw=item,
            )
        return out


# ─── Evaluator 8: original research (P6-07) ─────────────────────────────────


class OriginalResearchEvaluator:
    """P6-07: does the page present original research / primary data?

    Per-page: methodology_disclosed, has_primary_data, limitations_acknowledged,
    data_attributed_to_publisher. The page 'passes' when all four signals
    are true.
    """

    eval_type = "original_research"
    batch_size = 5

    def collect_items(self, site: SiteData) -> list[tuple[str, dict[str, Any]]]:
        items: list[tuple[str, dict[str, Any]]] = []
        for url, text in site.text_content.items():
            if not text.main_text or text.word_count < 300:
                continue
            path = (urlsplit(url).path or "/").lower()
            if not any(
                seg in path
                for seg in ("/blog/", "/news/", "/article/", "/post/", "/insights/", "/research", "/study", "/report")
            ):
                continue
            items.append(
                (
                    url,
                    {
                        "word_count": text.word_count,
                        "excerpt": _excerpt(text.main_text, words=500),
                    },
                )
            )
        return items

    def build_prompt(
        self,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> tuple[str, str]:
        system = (
            "You are evaluating whether long-form articles present "
            "ORIGINAL research or primary data — actual data the "
            "publisher collected — versus aggregating or restating "
            "research from elsewhere. Original research is a strong "
            "GEO signal because LLMs preferentially cite primary "
            "sources.\n\n"
            "For each page, judge four signals:\n"
            "- methodology_disclosed: page describes how data was "
            "  collected (sample size, sampling method, period, "
            "  instrument).\n"
            "- has_primary_data: numerical data, charts, or raw "
            "  tables are present in the excerpt (not just commentary).\n"
            "- limitations_acknowledged: page acknowledges sampling "
            "  limits, confounders, or scope boundaries.\n"
            "- data_attributed_to_publisher: explicit that the data "
            "  was collected by the publishing organisation.\n\n"
            "Return ONE JSON object per page: page_index (int), "
            "passes (bool: all four signals true), "
            "methodology_disclosed (bool), has_primary_data (bool), "
            "limitations_acknowledged (bool), "
            "data_attributed_to_publisher (bool), confidence (0-1), "
            "rationale (one sentence).\n\n"
            "Return ONLY a JSON array of N objects, in input order."
        )
        page_blocks: list[str] = []
        for idx, (url, payload) in enumerate(batch, start=1):
            page_blocks.append(
                f"--- PAGE {idx} ---\nURL: {url}\n"
                f"Word count: {payload['word_count']}\n"
                f"Excerpt: {payload['excerpt'][:2500]}\n"
            )
        user = (
            f"Evaluate these {len(batch)} pages for original research. "
            f"Return the JSON array.\n\n" + "\n\n".join(page_blocks)
        )
        return system, user

    def parse_result(
        self,
        result: LlmBatchResult,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, LlmEvaluation]:
        out: dict[str, LlmEvaluation] = {}
        if result.error or result.parsed is None:
            for url, _ in batch:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error=result.error or "no parsed output",
                    raw={"raw_text_head": result.raw_text[:200]},
                )
            return out
        by_index: dict[int, dict[str, Any]] = {}
        for item in result.parsed:
            idx = item.get("page_index")
            if isinstance(idx, int):
                by_index[idx] = item
        for idx, (url, _) in enumerate(batch, start=1):
            item = by_index.get(idx)
            if item is None:
                out[url] = LlmEvaluation(
                    page_url=url,
                    eval_type=self.eval_type,
                    passed=None,
                    confidence=0.0,
                    error="evaluator returned no row",
                )
                continue
            passes = item.get("passes")
            out[url] = LlmEvaluation(
                page_url=url,
                eval_type=self.eval_type,
                passed=bool(passes) if isinstance(passes, bool) else None,
                confidence=float(item.get("confidence", 0.0)),
                rationale=str(item.get("rationale", ""))[:500],
                raw=item,
            )
        return out


# ─── Evaluator 9: brand hallucination resistance (P6-31) ────────────────────


class BrandHallucinationEvaluator:
    """P6-31: does an LLM produce accurate facts about the brand?

    BRAND-level (single call, not per-page). We ask Claude to describe
    the brand using its training-data knowledge alone, then compare
    its response against ground-truth facts we already have from GBP /
    KG / site schema. Detects fabrication, conflation, and good
    hedging behaviour.
    """

    eval_type = "brand_hallucination"
    batch_size = 1

    def collect_items(self, site: SiteData) -> list[tuple[str, dict[str, Any]]]:
        if site.brand is None or not site.brand.name:
            return []
        ground_truth = self._ground_truth(site)
        # Skip the eval entirely if we have no ground truth to compare
        # against — there's nothing to verify Claude's claims against.
        if not any(ground_truth.values()):
            return []
        return [(site.domain, {"brand": site.brand.name, "ground_truth": ground_truth})]

    def _ground_truth(self, site: SiteData) -> dict[str, Any]:
        truth: dict[str, Any] = {}
        if site.gbp_info:
            truth["category"] = site.gbp_info.get("category")
            truth["address"] = site.gbp_info.get("address")
            truth["url"] = site.gbp_info.get("url")
            ai = site.gbp_info.get("address_info") or {}
            truth["country"] = ai.get("country_code")
        # Aspirational: KG types (we don't store them directly yet but
        # could). For now leave the placeholder.
        return truth

    def build_prompt(
        self,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> tuple[str, str]:
        url, payload = batch[0]
        brand = payload["brand"]
        truth = payload["ground_truth"]
        system = (
            "You are evaluating LLM hallucination resistance for a "
            "specific brand. You will be asked to describe the brand "
            "from training-data knowledge alone, and a downstream "
            "system will compare your response against ground-truth "
            "facts to detect fabrication or conflation with similarly-"
            "named entities.\n\n"
            "Reply ONLY with a JSON array containing ONE object with "
            "these fields: brand (string), category_described (string), "
            "headquarters_country (string or null), primary_products "
            "(array of strings), founded_year (int or null), "
            "named_executives (array of strings, leave empty if you "
            "don't know with confidence), known_with_confidence (bool: "
            "true if you have substantive specific knowledge of this "
            "brand from training; false if you're guessing or only "
            "have generic information), hedged (bool: true if you "
            "would hedge or decline rather than answer), confidence "
            "(0-1)."
        )
        user = (
            f"Describe the brand '{brand}'. What category? "
            f"Where headquartered? Primary products/services? Year "
            f"founded? Named executives? Be honest about what you "
            f"know with high confidence versus what you're inferring. "
            f"Return the JSON array now."
        )
        return system, user

    def parse_result(
        self,
        result: LlmBatchResult,
        batch: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, LlmEvaluation]:
        out: dict[str, LlmEvaluation] = {}
        url, payload = batch[0]
        if result.error or result.parsed is None or not result.parsed:
            out[url] = LlmEvaluation(
                page_url=url,
                eval_type=self.eval_type,
                passed=None,
                confidence=0.0,
                error=result.error or "no parsed output",
                raw={"raw_text_head": result.raw_text[:200]},
            )
            return out
        item = result.parsed[0]
        truth = payload["ground_truth"]
        # Verification logic: passes when LLM either knows the brand
        # with confidence AND matches the truth, OR when LLM correctly
        # hedges (acknowledges low confidence) rather than fabricating.
        issues: list[str] = []
        known = bool(item.get("known_with_confidence"))
        hedged = bool(item.get("hedged"))
        category = (item.get("category_described") or "").lower()
        truth_category = (truth.get("category") or "").lower()
        if known and truth_category:
            if truth_category and truth_category not in category and category not in truth_category:
                issues.append(f"category_mismatch: claimed='{category}' truth='{truth_category}'")
        if known and item.get("headquarters_country") and truth.get("country"):
            if (item.get("headquarters_country") or "").lower() != truth["country"].lower():
                issues.append(
                    f"country_mismatch: claimed='{item.get('headquarters_country')}' "
                    f"truth='{truth['country']}'"
                )
        executives = item.get("named_executives") or []
        if executives and known:
            # Any named executive is a fabrication risk; we don't have
            # ground truth on this so flag for human review only.
            issues.append(
                f"executives_claimed_for_human_review: {executives[:3]}"
            )
        passes = (
            (known and not issues)
            or hedged
        )
        out[url] = LlmEvaluation(
            page_url=url,
            eval_type=self.eval_type,
            passed=passes,
            confidence=float(item.get("confidence", 0.0)),
            issues=tuple(issues),
            rationale=(
                f"known={known} hedged={hedged} issues_count={len(issues)}"
            ),
            raw={"llm_response": item, "ground_truth": truth},
        )
        return out


def _is_complex(value: Any) -> bool:
    """A schema property is 'complex' if it nests dicts / large lists."""
    if isinstance(value, dict):
        return True
    if isinstance(value, list) and len(value) > 5:
        return True
    return False


def _stringify_value(value: Any) -> str:
    if isinstance(value, str):
        return value[:200]
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(str(v)[:60] for v in value[:5])
    return str(value)[:200]
