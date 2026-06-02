# Hybrid LLM evaluation (session-driven, free)

The 19 **LLM-judgment variables** (quotability, content substance, YMYL,
insightfulness, original research, brand sentiment, topic depth, etc.) genuinely
need an LLM , they can't be deterministic. The native auditor can do them via
the paid Anthropic API, but audits are Claude-session-driven, so a session can
evaluate them **for free** against each variable's rubric and merge the verdicts
into a native audit. This is the canonical way to fill those 19.

The 19 are `seomate.brief.LLM_JUDGMENT_VARIABLES`. A test
(`tests/test_extractor_audit.py::test_llm_judgment_vars_are_real_and_llm_dependent`)
keeps that list in sync with the extractors that read `site.llm_evaluations`.

## Workflow

1. **Run a native audit** (deterministic vars; the 19 land unmeasurable):
   ```
   seomate audit -c configs/<site>.yml
   ```
2. **Export the scoped brief** , ONLY the 19 LLM-judgment vars, each with its
   definition + Step 1.5 rubric:
   ```
   seomate export-brief --llm-only -o llm-brief.json
   ```
3. **The Claude session evaluates** each of the 19 against its rubric, using the
   site's page content (from `seomate gather` cache / the live pages), and emits
   an ingest document of CaptureRecords , one per variable, with a real
   `status` (passed/failed/partial), `value`, `rules`, and `evidence_weight`.
   Scope discipline: evaluate ONLY these 19, each strictly against its rubric.
   Do NOT re-judge other variables (that freehand path caused the June-2026
   mislabels). See `docs/ingest-contract.md` for the capture shape.
4. **Merge the verdicts** into the native audit (replaces those 19 in place and
   recomputes the audit's outcome counts , does NOT create a new audit):
   ```
   seomate ingest --file llm-evals.json --merge-into <native_audit_id>
   ```

## Why merge, not a new audit

The native run owns the ~207 deterministic captures. Merging keeps a single
authoritative audit per run (native data + session LLM verdicts) instead of two
half-audits. The merge is scoped by `variable_id`, so it only touches the
variables the session actually evaluated.

## Headless fallback

For a fully-headless weekly cron run (no session), set `ANTHROPIC_API_KEY` and
the native `_run_llm_evaluators` phase fills the 19 via the API instead. The
session/merge path is preferred when a session is driving the audit (free, and
the session's judgement is at least as good as Haiku's for these rubrics).
