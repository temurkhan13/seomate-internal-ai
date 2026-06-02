"""Audit orchestration.

The orchestrator is plain Python with ``asyncio`` — no LLM-driven control
flow, no Temporal, no agents. Determinism is the design constraint, per
docs/site-auditor-architecture.md §4.

Responsibilities:

1. Open a new ``audits`` row with ``status='running'``.
2. Snapshot the effective config and pin ``taxonomy_version``.
3. Build the variable execution plan respecting the configured scope.
4. Dispatch capture tasks in dependency order, parallel within bounds.
5. Persist captures and adapter-call telemetry as they complete.
6. Enforce the cost cap (hard halt at ``cost_cap_gbp``).
7. Close the audit with a final status (``completed`` / ``partial`` /
   ``cost_capped`` / ``failed``).

Foundation Day 3-4 ships a skeleton that does all of the above end-to-end
with a single fake extractor. H1a replaces the fake extractor with real
pillar-module dispatch.
"""
from __future__ import annotations

import asyncio
import inspect
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar
from uuid import UUID, uuid4

from sqlalchemy import update

from seomate.adapters import (
    AdapterContext,
    DataForSEOAdapter,
    EmbeddingsAdapter,
    EmbeddingsNotConfigured,
    KnowledgeGraphAdapter,
    LlmAdapter,
    PSIAdapter,
    PSINotConfigured,
    WikidataAdapter,
    WikipediaAdapter,
)
from seomate.config import SeoMateConfig
from seomate.data_contract import (
    AuditStatus,
    CaptureRecord,
    CaptureStatus,
    EvidenceWeight,
    SubjectType,
)
from seomate.pillars import (
    EXTRACTOR_REGISTRY,
    BrandIdentity,
    PageAudit,
    SiteData,
    normalise_instant_page_response,
)
from seomate.storage import AdapterCall, Audit, Capture, session_scope
from seomate.taxonomy import Catalog
from seomate.utils.cost_tracker import CostCapExceeded, CostTracker
from seomate.utils.html_fetch import fetch_html_pages
from seomate.utils.link_graph import build_link_graph
from seomate.utils.llm_evaluation import (
    BrandHallucinationEvaluator,
    BrandSentimentEvaluator,
    ContentSubstanceEvaluator,
    DefinitionalClarityEvaluator,
    ExpertQuoteEvaluator,
    HeadlineAccuracyEvaluator,
    InsightfulnessEvaluator,
    LlmEvaluator,
    OriginalResearchEvaluator,
    QuotabilityEvaluator,
    SchemaVisibleMatchEvaluator,
    TimeSensitivityClassifier,
    TopicDepthEvaluator,
    YmylClassifier,
    run_evaluator,
)
from seomate.utils.logging import get_logger
from seomate.utils.sitemap import discover_urls
from seomate.utils.structured_data import parse_structured_data
from seomate.utils.text_extraction import extract_main_text

if TYPE_CHECKING:
    from seomate.adapters import AdapterCallRecord

logger = get_logger(__name__)


class AuditOrchestrator:
    """Drive the lifecycle of one audit run."""

    def __init__(
        self,
        config: SeoMateConfig,
        *,
        catalog: Catalog | None = None,
    ) -> None:
        self.config = config
        self.audit_id: UUID = uuid4()
        self.catalog: Catalog = catalog if catalog is not None else Catalog.from_file()
        self.cost_tracker = CostTracker(
            cap_gbp=config.run.cost_cap_gbp,
            warn_fraction=config.run.cost_warn_fraction,
        )
        self.adapter_ctx = AdapterContext(
            audit_id=self.audit_id,
            cost_tracker=self.cost_tracker,
            taxonomy_version=self.catalog.version,
        )
        self._log = logger.bind(
            audit_id=str(self.audit_id),
            site=self.config.audit.site.domain,
        )

    async def run(self) -> UUID:
        """Run the audit end-to-end. Returns the audit_id."""
        await self._open_audit()
        self._log.info(
            "audit.started",
            cost_cap_gbp=self.config.run.cost_cap_gbp,
            scope_pillars=self.config.audit.scope.pillars,
            h1_stage=self.config.audit.scope.h1_stage,
        )

        captures: list[CaptureRecord] = []
        site_data: SiteData | None = None
        final_status = AuditStatus.COMPLETED

        try:
            captures, site_data = await self._dispatch_extractors()
            await self._persist_captures(captures)
            await self._persist_adapter_calls()
        except CostCapExceeded as exc:
            self._log.warning("audit.cost_capped", error=str(exc))
            final_status = AuditStatus.COST_CAPPED
            await self._persist_captures(captures)
            await self._persist_adapter_calls()
        except Exception:
            self._log.exception("audit.failed")
            final_status = AuditStatus.FAILED
            await self._persist_captures(captures)
            await self._persist_adapter_calls()
            await self._close_audit(captures, final_status)
            raise

        # If any capture itself errored, the audit is partial rather than completed.
        if final_status is AuditStatus.COMPLETED and any(
            r.status is CaptureStatus.ERROR for r in captures
        ):
            final_status = AuditStatus.PARTIAL

        # Completeness gate: detect silent data-loss patterns
        # (sparse embedding pass, failed-but-uncaught prefetch step, etc.)
        # that produce technically-complete audits but with bogus UNMEASURABLE
        # rows masking the regression. See seomate_anthropic_credits_low.md
        # for the precedent — silent regressions are the highest-cost class
        # of failure because they look like success.
        anomalies: list[dict[str, Any]] = []
        violations: list[dict[str, Any]] = []
        if final_status is AuditStatus.COMPLETED and site_data is not None:
            anomalies = self._check_audit_completeness(site_data, captures)
            violations = self._check_capture_consistency(captures, site_data)
            for a in anomalies:
                self._log.warning("audit.anomaly_detected", **a)
            for v in violations:
                self._log.warning("audit.consistency_violation", **v)
            if anomalies or violations:
                final_status = AuditStatus.COMPLETED_WITH_ANOMALIES

        await self._close_audit(captures, final_status, anomalies, violations)
        self._log.info(
            "audit.finished",
            status=final_status.value,
            captures=len(captures),
            cost_gbp=self.cost_tracker.total,
            anomaly_count=len(anomalies),
            consistency_violation_count=len(violations),
        )
        return self.audit_id

    # ─── Lifecycle steps ────────────────────────────────────────────────────

    async def _open_audit(self) -> None:
        async with session_scope() as s:
            audit = Audit(
                audit_id=self.audit_id,
                site_domain=self.config.audit.site.domain,
                config_snapshot=self.config.model_dump(mode="json"),
                taxonomy_version=self.catalog.version,
                status=AuditStatus.RUNNING.value,
            )
            s.add(audit)

    async def _discover_urls(self) -> list[str]:
        """Discover URLs for the audited site (sitemap-based)."""
        primary_url = self.config.audit.site.primary_url
        try:
            urls = await discover_urls(primary_url)
        except Exception:  # noqa: BLE001 - fall back to homepage-only
            self._log.exception("audit.site_discovery_failed")
            urls = []
        if not urls:
            urls = [primary_url]
            self._log.info("audit.site_discovery", source="primary_url_only", count=1)
        else:
            self._log.info("audit.site_discovery", source="sitemap", count=len(urls))
        return urls

    async def _prefetch_page_audits(
        self,
        urls: list[str],
        dataforseo: DataForSEOAdapter,
        *,
        concurrency: int = 8,
    ) -> tuple[dict[str, PageAudit], dict[str, str]]:
        """Fetch DataForSEO Instant Pages for every URL in parallel.

        Each URL is one Instant Pages call (per the adapter contract);
        bounded concurrency keeps us under DataForSEO's per-account rate
        limits. Returns ``(audits, errors)`` keyed by URL — one or the
        other is populated for every URL, never both.
        """
        if not urls:
            return {}, {}

        sem = asyncio.Semaphore(concurrency)
        audits: dict[str, PageAudit] = {}
        errors: dict[str, str] = {}

        async def _one(url: str) -> None:
            async with sem:
                try:
                    response = await dataforseo.on_page_instant_pages(url)
                except Exception as exc:  # noqa: BLE001 - failure is data
                    errors[url] = f"{type(exc).__name__}: {exc}"
                    return
            for pa in normalise_instant_page_response(response):
                # DataForSEO sometimes returns the canonicalised URL rather
                # than the input URL; key on the input URL so extractors
                # can find what they asked for.
                audits[url] = pa
                return
            errors[url] = "DataForSEO returned no usable item"

        await asyncio.gather(*[_one(u) for u in urls])
        self._log.info(
            "audit.prefetch_complete",
            requested=len(urls),
            successful=len(audits),
            failed=len(errors),
        )
        return audits, errors

    async def _dispatch_extractors(self) -> tuple[list[CaptureRecord], SiteData | None]:
        """Pre-fetch shared site data, then dispatch every registered extractor.

        Variables in the catalog without a registered extractor are
        silently skipped — H1a–H1d add them stage by stage.
        """
        self.cost_tracker.assert_under_cap()

        urls = await self._discover_urls()
        order = self.catalog.topological_order()
        scope = self.config.audit.scope
        skipped = set(scope.skip_variables)
        only = set(scope.only_variables)
        if only:
            self._log.info(
                "audit.only_mode_enabled",
                only_variables=sorted(only),
                count=len(only),
            )

        captures: list[CaptureRecord] = []
        async with (
            DataForSEOAdapter(self.adapter_ctx) as dataforseo,
            KnowledgeGraphAdapter(self.adapter_ctx) as kg,
            WikipediaAdapter(self.adapter_ctx) as wikipedia,
            WikidataAdapter(self.adapter_ctx) as wikidata,
            EmbeddingsAdapter(self.adapter_ctx) as embeddings,
            PSIAdapter(self.adapter_ctx) as psi,
            LlmAdapter(self.adapter_ctx) as llm,
        ):
            audits, audit_errors = await self._prefetch_page_audits(urls, dataforseo)
            ranked_kw, domain_rank = await self._prefetch_keyword_data(dataforseo)
            brand_volumes = await self._prefetch_brand_volumes(dataforseo)
            gbp_info, gbp_method = await self._prefetch_gbp(dataforseo)
            # Competitor SERP-discovery is wired (see _prefetch_competitors)
            # but disabled by default. SERP-overlap-on-our-ranked-keywords
            # only finds competitors for the narrow topic cluster our
            # current keywords surface on — not the brand's actual
            # competitive set. Revisit when the UI lets the user declare
            # strategic aspirations + we do dedicated keyword research
            # per category. Keeping the helper in place; not calling it.
            competitors: list[str] = []
            competitor_method = "deferred_pending_strategic_input"
            serp_results = await self._prefetch_top_serps(dataforseo, ranked_kw)
            business_reviews = await self._prefetch_business_reviews(
                dataforseo, gbp_info
            )
            backlinks_summary, referring_domains, backlinks_anchors, backlinks_timeseries = (
                await self._prefetch_backlinks(dataforseo)
            )
            bulk_pages_backlinks = await self._prefetch_bulk_pages_summary(
                dataforseo, urls
            )
            html_pages = await fetch_html_pages(urls)
            structured = {
                url: parse_structured_data(html.html, url=html.url)
                for url, html in html_pages.items()
            }
            link_graph = build_link_graph(
                {
                    url: page.html
                    for url, page in html_pages.items()
                    if page.fetch_error is None and page.status_code < 400
                },
                site_host=self.config.audit.site.domain,
            )
            text_content = {
                url: extract_main_text(page.html, url=page.url)
                for url, page in html_pages.items()
                if page.fetch_error is None and page.status_code < 400
            }
            page_embeddings = await self._embed_pages(embeddings, text_content)
            psi_results = await self._run_psi(psi)
            self._log.info(
                "audit.html_prefetch_complete",
                requested=len(urls),
                successful=sum(
                    1
                    for h in html_pages.values()
                    if h.fetch_error is None and h.status_code < 400
                ),
                schema_blocks_total=sum(len(s.blocks) for s in structured.values()),
                link_graph_pages=link_graph.page_count,
                link_graph_outbound_total=sum(
                    len(v) for v in link_graph.outbound.values()
                ),
                text_pages=len(text_content),
                embeddings_configured=embeddings.is_configured,
                pages_embedded=len(page_embeddings),
            )
            site_data = SiteData(
                domain=self.config.audit.site.domain,
                primary_url=self.config.audit.site.primary_url,
                urls=urls,
                page_audits=audits,
                page_audit_errors=audit_errors,
                brand=BrandIdentity(
                    name=self.config.audit.brand.name,
                    aliases=tuple(self.config.audit.brand.aliases),
                    legal_entities=tuple(self.config.audit.brand.legal_entities),
                ),
                html_pages=html_pages,
                structured_data=structured,
                link_graph=link_graph,
                text_content=text_content,
                embeddings=page_embeddings,
                embeddings_configured=embeddings.is_configured,
                ranked_keywords=ranked_kw,
                domain_rank_overview=domain_rank,
                brand_keyword_volumes=brand_volumes,
                gbp_info=gbp_info,
                gbp_discovery_method=gbp_method,
                competitors=competitors,
                competitor_discovery_method=competitor_method,
                serp_results=serp_results,
                business_reviews=business_reviews,
                backlinks_summary=backlinks_summary,
                referring_domains=referring_domains,
                backlinks_anchors=backlinks_anchors,
                backlinks_timeseries=backlinks_timeseries,
                bulk_pages_backlinks=bulk_pages_backlinks,
                psi_results=psi_results,
                psi_configured=psi.is_configured,
                llm_configured=llm.is_configured,
            )

            available_adapters = {
                "dataforseo": dataforseo,
                "kg": kg,
                "wikipedia": wikipedia,
                "wikidata": wikidata,
                "embeddings": embeddings,
                "psi": psi,
                "llm": llm,
            }

            # Skip the (slow, expensive) LLM evaluator phase if only-mode
            # is active and none of the requested vars actually depend
            # on it. Saves ~3-5 min per validation run.
            if only and not self._only_needs_llm(only):
                self._log.info(
                    "audit.llm_evaluators_skipped",
                    reason="only-mode; no requested var depends on LLM",
                )
                site_data.llm_evaluations = {}
                site_data.llm_evaluations_skipped = True
            else:
                site_data.llm_evaluations = await self._run_llm_evaluators(
                    llm, site_data
                )
            self._log.info(
                "audit.adapters_ready",
                kg_configured=kg.is_configured,
            )

            for variable_id in order:
                if variable_id in skipped:
                    continue
                if only and variable_id not in only:
                    continue
                if scope.pillars != "all":
                    pillar = variable_id.split("-", 1)[0]
                    if pillar not in scope.pillars:
                        continue
                extractor = EXTRACTOR_REGISTRY.get(variable_id)
                if extractor is None:
                    continue  # not yet implemented; skip without error
                self.cost_tracker.assert_under_cap()
                self._log.info("extractor.start", variable_id=variable_id)
                try:
                    kwargs = self._adapter_kwargs_for(extractor, available_adapters)
                    record = await extractor(
                        self.adapter_ctx,
                        site_data,
                        **kwargs,
                    )
                    captures.append(record)
                    self._log.info(
                        "extractor.complete",
                        variable_id=variable_id,
                        status=record.status.value,
                        cost_gbp=record.cost_incurred_gbp,
                    )
                except Exception as exc:  # noqa: BLE001 - failure is data
                    self._log.exception(
                        "extractor.failed",
                        variable_id=variable_id,
                    )
                    captures.append(
                        self._error_record(variable_id, site_data, exc)
                    )

        return captures, site_data

    async def _prefetch_gbp(
        self,
        dataforseo: DataForSEOAdapter,
    ) -> tuple[dict | None, str]:
        """Find the audited brand's Google Business Profile.

        If ``config.audit.gbp.place_id`` is set, treat that as authoritative
        and look it up directly. Otherwise auto-discover by searching brand
        name + variants and taking the top hit. Cached on SiteData so every
        P5 extractor reads from one source.

        Returns (gbp_item_dict_or_None, discovery_method_label).
        """
        brand = self.config.audit.brand
        # Try the canonical brand name first; fall back to aliases.
        candidates = [brand.name, *brand.aliases, *brand.legal_entities]
        for candidate in candidates:
            if not candidate:
                continue
            try:
                resp = await dataforseo.google_my_business_info(candidate)
            except Exception:  # noqa: BLE001
                self._log.exception("audit.gbp_lookup_failed", keyword=candidate)
                continue
            result = (resp.get("tasks") or [{}])[0].get("result") or [{}]
            items = (result[0].get("items") or []) if result else []
            if not items:
                continue
            # Pick the first item whose domain matches the audited domain.
            audited = self.config.audit.site.domain.lower().removeprefix("www.")
            for item in items:
                gbp_domain = (item.get("domain") or "").lower().removeprefix("www.")
                if audited and audited in gbp_domain:
                    self._log.info(
                        "audit.gbp_discovered",
                        keyword=candidate,
                        place_id=item.get("place_id"),
                        title=item.get("title"),
                        method="brand_search_domain_match",
                    )
                    return item, "brand_search_domain_match"
            # If no domain match, accept the top hit but flag the method.
            top = items[0]
            self._log.info(
                "audit.gbp_discovered",
                keyword=candidate,
                place_id=top.get("place_id"),
                title=top.get("title"),
                method="brand_search_top_hit_no_domain_match",
            )
            return top, "brand_search_top_hit_no_domain_match"

        self._log.info("audit.gbp_not_found")
        return None, "not_found"

    # Domains we always exclude when computing competitor frequency —
    # they appear on most SERPs but aren't direct competitors of any
    # individual brand. Keep this list conservative; if anything, miss
    # a generalist site rather than mistake it for a competitor.
    _COMPETITOR_EXCLUSION_HOSTS: ClassVar[frozenset[str]] = frozenset(
        {
            "wikipedia.org", "wikimedia.org",
            "reddit.com", "old.reddit.com",
            "quora.com",
            "youtube.com", "youtu.be",
            "linkedin.com", "facebook.com", "twitter.com", "x.com",
            "instagram.com", "pinterest.com", "tiktok.com",
            "medium.com",
            "amazon.com", "amazon.co.uk", "ebay.com", "ebay.co.uk",
            "indeed.com", "glassdoor.com", "crunchbase.com",
            "github.com", "stackoverflow.com",
            "google.com", "bing.com", "yahoo.com",
            "apple.com",
            "yelp.com", "tripadvisor.com",
            "bbc.co.uk", "bbc.com", "theguardian.com", "nytimes.com",
            "forbes.com", "businessinsider.com", "techcrunch.com",
            "wired.com", "wsj.com", "ft.com",
        }
    )

    @staticmethod
    def _normalise_competitor_host(host: str) -> str:
        """Lowercase + strip leading www. — for dedup & exclusion matching."""
        h = (host or "").strip().lower()
        return h[4:] if h.startswith("www.") else h

    async def _prefetch_competitors(
        self,
        dataforseo: DataForSEOAdapter,
        ranked_keywords: list[dict],
        *,
        top_keywords: int = 15,
        top_competitors: int = 5,
        organic_depth: int = 20,
    ) -> tuple[list[str], str]:
        """Discover direct competitors via SERP overlap on our top keywords.

        Filters seed keywords to commercial / transactional intent only
        so the SERPs we query surface service competitors rather than
        Wikipedia-tier authority sites that dominate informational SERPs.
        Brand-named queries are also excluded (they surface our own page).

        Cost: ``top_keywords`` × ~$0.0006/call (= ~$0.009 for default 15).
        For each commercial-intent seed, fetch the Google SERP and
        collect every non-excluded domain in the organic results.
        Rank by frequency across the seed set; the most-frequent
        domains are the most direct competitors.

        Returns ``(competitor_hosts, discovery_method)``. Empty list +
        a descriptive method string when no commercial-intent seeds
        exist to pivot on.
        """
        from seomate.utils.intent import is_commercial_intent

        if not ranked_keywords:
            self._log.info("audit.competitor_discovery_skipped", reason="no ranked_keywords")
            return [], "not_attempted"

        # Pick top-N by search volume. ranked_keywords come pre-sorted
        # desc on search_volume from _prefetch_keyword_data, but we re-
        # sort defensively in case the upstream order ever changes.
        def _kw_volume(item: dict) -> int:
            return int(
                (
                    ((item.get("keyword_data") or {}).get("keyword_info") or {}).get(
                        "search_volume"
                    )
                    or 0
                )
            )

        brand = self.config.audit.brand
        brand_variants = tuple(
            v for v in (brand.name, *brand.aliases, *brand.legal_entities) if v
        )

        sorted_items = sorted(ranked_keywords, key=_kw_volume, reverse=True)
        seeds: list[str] = []
        rejected: list[dict[str, Any]] = []
        seen_seeds: set[str] = set()
        for item in sorted_items:
            kw = ((item.get("keyword_data") or {}).get("keyword") or "").strip()
            if not kw or kw.lower() in seen_seeds:
                continue
            seen_seeds.add(kw.lower())
            # Filter: only commercial / transactional intent seeds
            if not is_commercial_intent(kw, brand_variants):
                if len(rejected) < 15:
                    rejected.append({"keyword": kw, "reason": "not_commercial_intent"})
                continue
            seeds.append(kw)
            if len(seeds) >= top_keywords:
                break

        if not seeds:
            self._log.warning(
                "audit.competitor_discovery_no_commercial_seeds",
                ranked_keywords_count=len(ranked_keywords),
                rejected_examples=[r["keyword"] for r in rejected[:10]],
            )
            return [], "no_commercial_intent_seeds"

        self._log.info(
            "audit.competitor_discovery_seeds_selected",
            seeds=seeds,
            rejected_non_commercial=len(rejected),
        )

        our_host = self._normalise_competitor_host(
            self.config.audit.site.domain
        )

        domain_counts: dict[str, int] = {}
        domain_examples: dict[str, list[str]] = {}
        api_errors: list[str] = []
        for kw in seeds:
            try:
                resp = await dataforseo.serp_google_organic(
                    kw, depth=organic_depth
                )
            except Exception as exc:  # noqa: BLE001
                api_errors.append(f"{kw}: {type(exc).__name__}")
                continue
            tasks = resp.get("tasks") or []
            if not tasks:
                continue
            result = (tasks[0].get("result") or [{}])[0]
            for item in (result.get("items") or []):
                if item.get("type") != "organic":
                    continue
                host = self._normalise_competitor_host(item.get("domain") or "")
                if not host or host == our_host:
                    continue
                # Strip exact-match + suffix exclusions (e.g., en.wikipedia.org -> wikipedia.org)
                base = ".".join(host.split(".")[-2:]) if "." in host else host
                if host in self._COMPETITOR_EXCLUSION_HOSTS or base in self._COMPETITOR_EXCLUSION_HOSTS:
                    continue
                domain_counts[host] = domain_counts.get(host, 0) + 1
                if len(domain_examples.setdefault(host, [])) < 3:
                    domain_examples[host].append(kw)

        if not domain_counts:
            self._log.warning(
                "audit.competitor_discovery_empty",
                seeds_attempted=len(seeds),
                api_errors=len(api_errors),
            )
            return [], "serp_overlap_no_results"

        ranked_competitors = sorted(
            domain_counts.items(), key=lambda kv: kv[1], reverse=True
        )
        top = [h for h, _ in ranked_competitors[:top_competitors]]
        self._log.info(
            "audit.competitor_discovery_complete",
            seeds=len(seeds),
            unique_competitors_seen=len(domain_counts),
            top_competitors=[
                {"host": h, "frequency": c, "appears_for": domain_examples.get(h, [])}
                for h, c in ranked_competitors[:top_competitors]
            ],
            api_errors=len(api_errors),
        )
        return top, "serp_overlap"

    async def _prefetch_backlinks(
        self,
        dataforseo: DataForSEOAdapter,
        *,
        top_referring_domains: int = 100,
        top_anchors: int = 100,
        timeseries_months: int = 12,
    ) -> tuple[dict | None, list[dict], list[dict], list[dict]]:
        """Fetch backlinks-pillar data via DataForSEO Backlinks API.

        Four calls per audit:
        1. ``backlinks_summary`` — aggregate metrics (one row per target).
           Feeds P3-01, P3-04, P3-05, P3-17, P3-18, others.
        2. ``referring_domains`` — top-N referring domains with rank.
           Feeds P3-02 (DR distribution), P3-03 (linking domain age),
           P3-06 (.gov/.edu), P3-22 (TLD), P3-23 (IP diversity), etc.
        3. ``backlinks_anchors`` — top-N anchor texts with frequency.
           Feeds P3-12, P3-32, etc.
        4. ``timeseries_summary`` — monthly snapshots over a 12-month
           window. Feeds P3-24 (positive velocity / gains) and
           P3-25 (negative velocity / loss rate).

        Cost: roughly ~£0.05 per audit (summary + referring + anchors
        ~£0.04 plus timeseries ~£0.005), drawn from the Backlinks API
        subscription.

        Returns (summary, referring_domains_items, anchor_items, timeseries_items).
        Empty / None on any per-call failure — the pillar's extractors
        return UNMEASURABLE in that case rather than crashing.
        """
        from datetime import datetime, timedelta, timezone

        target = self.config.audit.site.domain
        summary: dict | None = None
        ref_domains: list[dict] = []
        anchors: list[dict] = []
        timeseries: list[dict] = []

        try:
            resp = await dataforseo.backlinks_summary(target)
            result = (resp.get("tasks") or [{}])[0].get("result") or []
            if result and isinstance(result[0], dict):
                summary = result[0]
        except Exception:  # noqa: BLE001
            self._log.exception("audit.backlinks_summary_failed")

        try:
            resp = await dataforseo.referring_domains(
                target, limit=top_referring_domains
            )
            result = (resp.get("tasks") or [{}])[0].get("result") or []
            if result and isinstance(result[0], dict):
                ref_domains = result[0].get("items") or []
        except Exception:  # noqa: BLE001
            self._log.exception("audit.referring_domains_failed")

        try:
            resp = await dataforseo.backlinks_anchors(
                target, limit=top_anchors
            )
            result = (resp.get("tasks") or [{}])[0].get("result") or []
            if result and isinstance(result[0], dict):
                anchors = result[0].get("items") or []
        except Exception:  # noqa: BLE001
            self._log.exception("audit.backlinks_anchors_failed")

        try:
            now = datetime.now(timezone.utc)
            date_to = now.strftime("%Y-%m-%d")
            date_from = (now - timedelta(days=timeseries_months * 31)).strftime(
                "%Y-%m-%d"
            )
            resp = await dataforseo.backlinks_timeseries_summary(
                target, date_from=date_from, date_to=date_to, group_range="month"
            )
            result = (resp.get("tasks") or [{}])[0].get("result") or []
            if result and isinstance(result[0], dict):
                timeseries = result[0].get("items") or []
        except Exception:  # noqa: BLE001
            self._log.exception("audit.backlinks_timeseries_failed")

        self._log.info(
            "audit.backlinks_prefetch_complete",
            summary_returned=summary is not None,
            referring_domains_returned=len(ref_domains),
            anchors_returned=len(anchors),
            timeseries_points=len(timeseries),
        )
        return summary, ref_domains, anchors, timeseries

    async def _prefetch_bulk_pages_summary(
        self,
        dataforseo: DataForSEOAdapter,
        urls: list[str],
    ) -> list[dict]:
        """Per-URL backlinks + rank for the audited site's own pages.

        Feeds P3-10 (page-level PageRank distribution across our own
        pages). One call to DataForSEO ``bulk_pages_summary`` covers
        up to 1000 URLs. Cost is bundled at ~£0.005 for our 58 URLs.
        """
        if not urls:
            return []
        try:
            resp = await dataforseo.bulk_pages_summary(urls)
            result = (resp.get("tasks") or [{}])[0].get("result") or []
            items: list[dict] = []
            if result and isinstance(result[0], dict):
                items = result[0].get("items") or []
            self._log.info(
                "audit.bulk_pages_prefetch_complete",
                urls_submitted=len(urls),
                items_returned=len(items),
            )
            return items
        except Exception:  # noqa: BLE001
            self._log.exception("audit.bulk_pages_summary_failed")
            return []

    async def _prefetch_business_reviews(
        self,
        dataforseo: DataForSEOAdapter,
        gbp_info: dict | None,
        *,
        depth: int = 50,
    ) -> list[dict]:
        """Fetch GBP reviews via DataForSEO Business Data Reviews endpoint.

        Uses the GBP place_id from the prefetched gbp_info; falls back
        to brand-name keyword if no place_id is available. Returns the
        flat list of review records (each with rating, text, time
        offsets, owner-response if present). Empty list when no GBP is
        discoverable.

        Cost: ~£0.02-0.03 per audit for depth=50 reviews. Drawn from
        the main DataForSEO pay-as-you-go balance. Task-based endpoint
        polls for ~10-30s.
        """
        if gbp_info is None:
            self._log.info("audit.reviews_prefetch_skipped", reason="no GBP discovered")
            return []
        place_id = (gbp_info.get("place_id") or "").strip()
        brand = self.config.audit.brand
        keyword = brand.name if (brand and brand.name) else None
        if not place_id and not keyword:
            self._log.info("audit.reviews_prefetch_skipped", reason="no place_id or brand")
            return []
        try:
            resp = await dataforseo.google_reviews(
                place_id=place_id or None,
                keyword=None if place_id else keyword,
                depth=depth,
            )
        except Exception:  # noqa: BLE001
            self._log.exception("audit.reviews_prefetch_failed")
            return []
        # Parse out the review items
        tasks = resp.get("tasks") or []
        if not tasks:
            self._log.warning(
                "audit.reviews_prefetch_empty",
                reason="no tasks in response",
            )
            return []
        result = (tasks[0].get("result") or [{}])
        if not result or not isinstance(result[0], dict):
            return []
        items = result[0].get("items") or []
        out = [it for it in items if isinstance(it, dict)]
        self._log.info(
            "audit.reviews_prefetch_complete",
            reviews_returned=len(out),
            place_id=place_id or None,
            keyword=keyword if not place_id else None,
        )
        return out

    async def _prefetch_top_serps(
        self,
        dataforseo: DataForSEOAdapter,
        ranked_keywords: list[dict],
        *,
        top_n: int = 10,
        organic_depth: int = 20,
    ) -> dict[str, dict]:
        """Fetch DataForSEO SERPs for brand-name + top-N ranked-keyword queries.

        Seeds: brand canonical name first (unlocks P6-13/14/16 brand
        presence on Reddit/YouTube/news), then top-N ranked keywords
        by volume (unlocks P0-05/P1-10/P6-25). Stored on
        SiteData.serp_results keyed by query.

        Cost (advanced SERP tier at ~$0.002/call): ~£0.018 per audit
        for default top_n=10 + 1 brand seed.
        """
        seeds: list[str] = []
        seen: set[str] = set()

        # Brand-name seed first (cheap insurance for GEO vars)
        brand = self.config.audit.brand
        if brand and brand.name:
            seeds.append(brand.name)
            seen.add(brand.name.lower())

        if not ranked_keywords and not seeds:
            self._log.info("audit.serp_prefetch_skipped", reason="no seeds")
            return {}

        def _kw_volume(item: dict) -> int:
            return int(
                (
                    ((item.get("keyword_data") or {}).get("keyword_info") or {}).get(
                        "search_volume"
                    )
                    or 0
                )
            )

        sorted_items = sorted(ranked_keywords or [], key=_kw_volume, reverse=True)
        for item in sorted_items:
            kw = ((item.get("keyword_data") or {}).get("keyword") or "").strip()
            if not kw or kw.lower() in seen:
                continue
            seen.add(kw.lower())
            seeds.append(kw)
            if len(seeds) >= top_n + 1:  # +1 to account for the brand seed
                break

        out: dict[str, dict] = {}
        api_errors: list[str] = []
        for kw in seeds:
            try:
                resp = await dataforseo.serp_google_organic(
                    kw, depth=organic_depth
                )
            except Exception as exc:  # noqa: BLE001
                api_errors.append(f"{kw}: {type(exc).__name__}")
                continue
            tasks = resp.get("tasks") or []
            if not tasks:
                continue
            result = (tasks[0].get("result") or [{}])[0]
            out[kw] = result
        self._log.info(
            "audit.serp_prefetch_complete",
            seeds=len(seeds),
            successful=len(out),
            api_errors=len(api_errors),
        )
        return out

    async def _prefetch_brand_volumes(
        self,
        dataforseo: DataForSEOAdapter,
    ) -> list[dict]:
        """Search-volume lookup for every brand variant.

        Used by P0-15 (brand search volume). The same Keyword Data
        endpoint also returns CPC + competition, which downstream
        variables can use without re-querying.
        """
        brand = self.config.audit.brand
        keywords = list({k for k in (brand.name, *brand.aliases, *brand.legal_entities) if k})
        if not keywords:
            return []
        try:
            resp = await dataforseo.keywords_search_volume(keywords)
        except Exception:  # noqa: BLE001
            self._log.exception("audit.brand_volume_lookup_failed")
            return []
        results = (resp.get("tasks") or [{}])[0].get("result") or []
        out = [r for r in results if isinstance(r, dict)]
        self._log.info(
            "audit.brand_volume_prefetch_complete",
            variants=len(keywords),
            results=len(out),
        )
        return out

    async def _prefetch_keyword_data(
        self,
        dataforseo: DataForSEOAdapter,
    ) -> tuple[list[dict], dict | None]:
        """Pre-fetch DataForSEO Labs keyword + domain-rank data once.

        Returns ``(ranked_keywords_items, domain_rank_overview_first_item)``.
        Failures degrade gracefully — the orchestrator passes empty data
        through to extractors which then report ``unmeasurable``.
        """
        domain = self.config.audit.site.domain
        ranked_items: list[dict] = []
        rank_overview: dict | None = None
        try:
            rk = await dataforseo.ranked_keywords(domain, limit=200)
            result = (rk.get("tasks") or [{}])[0].get("result") or [{}]
            ranked_items = (result[0].get("items") or []) if result else []
        except Exception:  # noqa: BLE001 - failure is data
            self._log.exception("audit.ranked_keywords_failed")
        try:
            ov = await dataforseo.domain_rank_overview(domain)
            ov_result = (ov.get("tasks") or [{}])[0].get("result") or [{}]
            ov_items = (ov_result[0].get("items") or []) if ov_result else []
            rank_overview = ov_items[0] if ov_items else None
        except Exception:  # noqa: BLE001 - failure is data
            self._log.exception("audit.domain_rank_overview_failed")
        self._log.info(
            "audit.keyword_prefetch_complete",
            ranked_keywords=len(ranked_items),
            has_domain_rank=rank_overview is not None,
        )
        return ranked_items, rank_overview

    async def _run_llm_evaluators(
        self,
        llm: LlmAdapter,
        site_data: SiteData,
    ) -> dict[str, dict[str, Any]]:
        """Run every registered LLM evaluator once at audit start.

        Returns ``{eval_type: {page_url: LlmEvaluation}}`` so the
        SiteData cache mirrors the per-evaluator shape downstream
        extractors expect. Empty dict when LLM is not configured.
        """
        if not llm.is_configured:
            self._log.info("audit.llm_disabled", reason="no ANTHROPIC_API_KEY")
            return {}

        evaluators: list[LlmEvaluator] = [
            SchemaVisibleMatchEvaluator(),
            HeadlineAccuracyEvaluator(),
            ContentSubstanceEvaluator(),
            QuotabilityEvaluator(),
            DefinitionalClarityEvaluator(),
            InsightfulnessEvaluator(),
            YmylClassifier(),
            OriginalResearchEvaluator(),
            BrandHallucinationEvaluator(),
            TopicDepthEvaluator(),
            BrandSentimentEvaluator(),
            TimeSensitivityClassifier(),
            ExpertQuoteEvaluator(),
        ]
        out: dict[str, dict[str, Any]] = {}
        for evaluator in evaluators:
            items = evaluator.collect_items(site_data)
            if not items:
                self._log.info(
                    "audit.llm_evaluator_skipped",
                    eval_type=evaluator.eval_type,
                    reason="no eligible pages",
                )
                continue
            self._log.info(
                "audit.llm_evaluator_start",
                eval_type=evaluator.eval_type,
                eligible_pages=len(items),
                batch_size=evaluator.batch_size,
            )
            try:
                results = await run_evaluator(evaluator, site_data, llm)
            except Exception:  # noqa: BLE001 - failure is data
                self._log.exception(
                    "audit.llm_evaluator_failed",
                    eval_type=evaluator.eval_type,
                )
                continue
            out[evaluator.eval_type] = results
            self._log.info(
                "audit.llm_evaluator_complete",
                eval_type=evaluator.eval_type,
                pages_evaluated=len(results),
                failed=sum(1 for r in results.values() if r.error),
            )
        return out

    async def _run_psi(
        self,
        psi: PSIAdapter,
    ) -> dict[str, Any]:
        """Run PageSpeed Insights on the homepage for mobile + desktop.

        We deliberately limit the URL set: PSI runs a real Lighthouse
        audit on Google's servers (~20-40s per call), so a per-page
        sweep on a 58-page site would take 20+ minutes. Sampling the
        homepage gives a representative read for the headline P2-08…14
        captures; future H1b work can add a sample of deep pages.

        Returns ``{f"{strategy}|{url}": PSIResult}`` keyed for stable
        lookup by extractors.
        """
        if not psi.is_configured:
            return {}
        primary = self.config.audit.site.primary_url
        out: dict[str, Any] = {}
        for strategy in ("mobile", "desktop"):
            try:
                result = await psi.run_pagespeed(primary, strategy=strategy)
            except PSINotConfigured:
                return {}
            except Exception:  # noqa: BLE001 - failure is data
                self._log.exception(
                    "audit.psi_failed", url=primary, strategy=strategy
                )
                continue
            out[f"{strategy}|{primary}"] = result
            self._log.info(
                "audit.psi_complete",
                url=primary,
                strategy=strategy,
                status=result.fetch_status,
                performance_score=result.performance_score,
                lcp_ms=result.lcp_ms,
            )
        return out

    async def _embed_pages(
        self,
        embeddings: EmbeddingsAdapter,
        text_content: dict[str, Any],
        *,
        retry_passes: int = 2,
        between_pass_wait_seconds: float = 30.0,
    ) -> dict[str, Any]:
        """Embed every page's main text with multi-pass retry.

        The Gemini free tier rate-limits aggressively (~100 RPM for the
        embeddings model). A single sequential pass may still trip 429s
        mid-audit when bursts coincide with quota windows resetting.
        We do up to ``retry_passes`` passes: a first pass attempts every
        eligible page; subsequent passes retry only the URLs that failed.
        Between passes we sleep ``between_pass_wait_seconds`` (~60s
        comfortably covers a per-minute quota window).
        """
        if not embeddings.is_configured:
            return {}

        eligible = {
            url: page_text
            for url, page_text in text_content.items()
            if page_text.main_text
        }
        out: dict[str, Any] = {}
        remaining = dict(eligible)

        for pass_idx in range(retry_passes):
            failed_this_pass: list[str] = []
            for url, page_text in list(remaining.items()):
                try:
                    vec = await embeddings.embed(page_text.main_text)
                except EmbeddingsNotConfigured:
                    return out  # adapter unavailable; preserve any work done
                except Exception:  # noqa: BLE001 - embedding failure is data
                    self._log.exception(
                        "audit.embedding_failed",
                        url=url,
                        pass_idx=pass_idx,
                    )
                    failed_this_pass.append(url)
                    continue
                out[url] = vec
                remaining.pop(url, None)
            self._log.info(
                "audit.embedding_pass_complete",
                pass_idx=pass_idx,
                succeeded_pages=len(out),
                failed_this_pass=len(failed_this_pass),
                still_remaining=len(remaining),
            )
            if not remaining:
                break  # everything succeeded
            if pass_idx + 1 < retry_passes:
                self._log.info(
                    "audit.embedding_pass_pause",
                    pause_seconds=between_pass_wait_seconds,
                    queued_for_retry=len(remaining),
                )
                await asyncio.sleep(between_pass_wait_seconds)
        return out

    def _check_capture_consistency(
        self,
        captures: list[CaptureRecord],
        site: SiteData,
    ) -> list[dict[str, Any]]:
        """Cross-extractor consistency rules.

        Codified invariants that any internally-consistent audit must
        satisfy. Each rule reports a violation as a dict (same shape
        as completeness anomalies). Empty list = no contradictions.

        Distinct from the completeness gate: completeness checks
        prefetch data integrity ("did we collect enough?"); consistency
        checks that extractors produced internally coherent outputs
        ("do our verdicts agree with each other?").
        """
        violations: list[dict[str, Any]] = []
        by_var: dict[str, CaptureRecord] = {c.variable_id: c for c in captures}

        # --- Rule 1: P3-34 hub vs P3-36 guest-post-network contradiction
        # Same referring domain shouldn't be classified as both a hub
        # page AND a paid-guest-post network with high confidence.
        # When both LLM-based extractors flag the same domain, it
        # surfaces the LLM-classifier inconsistency we observed with
        # techreviewer.co.
        p3_34 = by_var.get("P3-34")
        p3_36 = by_var.get("P3-36")
        if (
            p3_34 is not None and p3_36 is not None
            and p3_34.status in (CaptureStatus.PASSED, CaptureStatus.FAILED)
            and p3_36.status in (CaptureStatus.PASSED, CaptureStatus.FAILED)
        ):
            hub_doms = {
                e.get("domain")
                for e in (p3_34.value or {}).get("hub_examples", [])
                if (e.get("confidence") or 0) >= 0.7
            }
            gp_doms = {
                e.get("domain")
                for e in (p3_36.value or {}).get("guest_post_examples", [])
                if (e.get("confidence") or 0) >= 0.7
            }
            overlap = (hub_doms & gp_doms) - {None, ""}
            if overlap:
                violations.append(
                    {
                        "check": "p3_34_vs_p3_36_classification_overlap",
                        "severity": "warning",
                        "domains_classified_both": sorted(overlap),
                        "explanation": (
                            "These referring domains were classified at "
                            ">=0.7 confidence as BOTH a hub/resource page "
                            "(P3-34) AND a guest-post network (P3-36). "
                            "Both can't be true; one of the LLM "
                            "classifications is wrong. Inspect the "
                            "domain types manually and consider tuning "
                            "the prompts."
                        ),
                    }
                )

        # --- Rule 2: P0-07 / P0-08 must have matching status
        # Both extractors compute from the same embeddings dict; if
        # one's UNMEASURABLE the other must be too. Divergence = bug.
        p0_07 = by_var.get("P0-07")
        p0_08 = by_var.get("P0-08")
        if p0_07 is not None and p0_08 is not None:
            sa, sb = p0_07.status, p0_08.status
            sa_unmeas = (sa == CaptureStatus.UNMEASURABLE)
            sb_unmeas = (sb == CaptureStatus.UNMEASURABLE)
            if sa_unmeas != sb_unmeas:
                violations.append(
                    {
                        "check": "p0_07_vs_p0_08_status_divergence",
                        "severity": "critical",
                        "p0_07_status": sa.value if hasattr(sa, "value") else sa,
                        "p0_08_status": sb.value if hasattr(sb, "value") else sb,
                        "explanation": (
                            "P0-07 (site focus score) and P0-08 (site "
                            "radius) are math-derived from the same "
                            "embeddings dict. Their UNMEASURABLE state "
                            "must match. Divergence means one extractor "
                            "has stale or incorrect input-validation logic."
                        ),
                    }
                )

        # --- Rule 3: P3-01 captured count must match summary count
        # P3-01 reports referring_main_domains. backlinks_summary's
        # referring_main_domains field is the source. If P3-01's value
        # doesn't match the summary, the extractor is reading the
        # wrong field or there's a stale prefetch.
        p3_01 = by_var.get("P3-01")
        if (
            p3_01 is not None
            and p3_01.status in (CaptureStatus.PASSED, CaptureStatus.FAILED)
            and site.backlinks_summary is not None
        ):
            summary_count = int(
                site.backlinks_summary.get("referring_main_domains") or 0
            )
            value = p3_01.value or {}
            reported_count = None
            for key in (
                "referring_main_domains",
                "referring_main_domains_count",
                "referring_root_domains_count",
            ):
                if key in value:
                    try:
                        reported_count = int(value[key])
                        break
                    except (TypeError, ValueError):
                        continue
            if reported_count is not None and reported_count != summary_count:
                violations.append(
                    {
                        "check": "p3_01_vs_summary_count_mismatch",
                        "severity": "critical",
                        "summary_referring_main_domains": summary_count,
                        "p3_01_reported_count": reported_count,
                        "explanation": (
                            "P3-01's reported count of referring main "
                            "domains diverges from the source "
                            "backlinks_summary value. Indicates extractor "
                            "reading the wrong field or operating on stale "
                            "data."
                        ),
                    }
                )

        return violations

    def _check_audit_completeness(
        self,
        site: SiteData,
        captures: list[CaptureRecord],
    ) -> list[dict[str, Any]]:
        """Detect silent data-loss patterns in a freshly-completed audit.

        Returns a list of anomaly dicts. Each entry carries ``check``
        (the rule name), ``severity`` ('warning' or 'critical'), and
        evidence fields. Empty list means the audit passed completeness
        checks.

        The checks are intentionally conservative — they fire only when
        an audit's data-collection layer produced obviously incomplete
        input. They don't second-guess extractor logic; they catch the
        class of bug where the prefetch landed 1-of-58 items and 20
        downstream variables reported UNMEASURABLE.
        """
        anomalies: list[dict[str, Any]] = []

        # --- Embedding pass coverage ---
        # Eligible-page count: pages with main_text. If <90% of those
        # produced an embedding, embedding-dependent vars (P0-07/08,
        # P1-35, etc.) will all silently UNMEASURABLE — this is the
        # exact failure mode that surfaced today.
        eligible_text_pages = sum(
            1
            for p in (site.text_content or {}).values()
            if getattr(p, "main_text", "")
        )
        embedded = len(site.embeddings or {})
        if eligible_text_pages >= 3:
            coverage = embedded / eligible_text_pages
            if coverage < 0.9:
                anomalies.append(
                    {
                        "check": "embedding_pass_under_coverage",
                        "severity": "critical",
                        "eligible_pages": eligible_text_pages,
                        "embedded_pages": embedded,
                        "coverage_pct": round(coverage * 100, 1),
                        "threshold_pct": 90,
                        "downstream_impact": (
                            "embedding-dependent variables (P0-07, P0-08, "
                            "P1-35, P6-21, etc.) will return UNMEASURABLE "
                            "without this signal. Re-run after the "
                            "embeddings adapter recovers / rate-limit "
                            "windows reset."
                        ),
                    }
                )

        # --- HTML fetch coverage ---
        # Pages we fetched directly (not via DataForSEO instant_pages).
        # Used by extract_main_text → embeddings → downstream vars.
        html_total = len(site.html_pages or {})
        html_ok = sum(
            1
            for h in (site.html_pages or {}).values()
            if h.fetch_error is None and h.status_code < 400
        )
        if html_total > 0:
            html_coverage = html_ok / html_total
            if html_coverage < 0.8:
                anomalies.append(
                    {
                        "check": "html_fetch_under_coverage",
                        "severity": "critical",
                        "urls_fetched": html_total,
                        "urls_ok": html_ok,
                        "coverage_pct": round(html_coverage * 100, 1),
                        "threshold_pct": 80,
                        "downstream_impact": (
                            "direct-HTML extractors (P1-20 canonical, "
                            "schema parsers, link graph, embeddings) lose "
                            "fidelity below this threshold"
                        ),
                    }
                )

        # --- Internal consistency: summary says X domains, prefetch
        # returned Y. Catches the case where summary call succeeds but
        # referring_domains call failed silently, producing an audit
        # that claims 274 main_domains but has 0 sampled refs.
        if site.backlinks_summary is not None:
            claimed = int(site.backlinks_summary.get("referring_main_domains") or 0)
            sampled = len(site.referring_domains or [])
            if claimed > 50 and sampled == 0:
                anomalies.append(
                    {
                        "check": "backlinks_referring_domains_empty_despite_summary",
                        "severity": "critical",
                        "summary_main_domains": claimed,
                        "sampled_referring_domains": sampled,
                        "downstream_impact": (
                            "P3-02 / P3-03 / P3-06 / P3-22 / P3-29 / etc. "
                            "depend on the sampled list and will all "
                            "UNMEASURABLE"
                        ),
                    }
                )

        # --- Adapter call success-rate floor ---
        # Drain the tracker rather than touching the DB (drain_calls
        # is called by _persist_adapter_calls; we read from a snapshot
        # captured before that drain) — but at this point in run() the
        # calls have already been persisted. Re-query the captures'
        # data_sources_used aggregations instead.
        if site.embeddings_configured and embedded == 0 and eligible_text_pages > 0:
            anomalies.append(
                {
                    "check": "embeddings_configured_but_zero_embedded",
                    "severity": "critical",
                    "downstream_impact": (
                        "embeddings adapter reported configured but no "
                        "vectors landed. Likely Gemini quota / billing / "
                        "auth issue."
                    ),
                }
            )

        # --- LLM evaluator coverage floor ---
        # When LLM is configured AND the eval phase wasn't deliberately
        # skipped, evaluators should produce SOME results. Zero results
        # = silent LLM failure (the credit-balance regression).
        if site.llm_configured and not getattr(site, "llm_evaluations_skipped", False):
            llm_results_total = sum(
                len(per_eval) for per_eval in (site.llm_evaluations or {}).values()
            )
            if llm_results_total == 0:
                anomalies.append(
                    {
                        "check": "llm_configured_but_zero_evaluations",
                        "severity": "warning",
                        "downstream_impact": (
                            "LLM-dependent variables (~15 across P1/P4/P6) "
                            "will UNMEASURABLE. Check Anthropic billing "
                            "balance and ANTHROPIC_API_KEY workspace alignment."
                        ),
                    }
                )

        return anomalies

    def _only_needs_llm(self, only_variables: set[str]) -> bool:
        """Return True if any var in the only-list declares the llm adapter.

        Inspects each requested extractor's signature for an ``llm``
        keyword parameter. Lets only-mode skip the slow LLM evaluator
        phase when nothing requested actually depends on it.
        """
        for vid in only_variables:
            extractor = EXTRACTOR_REGISTRY.get(vid)
            if extractor is None:
                continue
            sig = inspect.signature(extractor)
            if "llm" in sig.parameters:
                return True
        return False

    @staticmethod
    def _adapter_kwargs_for(
        extractor: Any,
        available_adapters: dict[str, Any],
    ) -> dict[str, Any]:
        """Pass only the adapters this extractor declares in its signature.

        Lets us add new adapter types (Wikipedia, Wikidata, KG) without
        rewriting every existing extractor's signature. Each extractor
        declares the adapters it needs as keyword-only parameters; the
        orchestrator inspects the signature and supplies just those.
        """
        sig = inspect.signature(extractor)
        return {
            name: adapter
            for name, adapter in available_adapters.items()
            if name in sig.parameters
        }

    def _error_record(
        self,
        variable_id: str,
        site: SiteData,
        exc: BaseException,
    ) -> CaptureRecord:
        """Build a CaptureRecord representing an extractor crash."""
        var = self.catalog.get(variable_id)
        weight = (
            var.evidence_weight if var and var.evidence_weight else EvidenceWeight.CONSENSUS
        )
        pillar = variable_id.split("-", 1)[0]
        return CaptureRecord(
            audit_id=self.audit_id,
            variable_id=variable_id,
            pillar=pillar,
            captured_at=datetime.now(timezone.utc),
            taxonomy_version=self.catalog.version,
            subject_type=SubjectType.SITE,
            subject_id=site.domain,
            status=CaptureStatus.ERROR,
            value=None,
            rules=None,
            evidence_weight=weight,
            data_sources_used=[],
            cost_incurred_gbp=0.0,
            errors=[f"{type(exc).__name__}: {exc}"],
        )

    async def _persist_captures(self, captures: list[CaptureRecord]) -> None:
        if not captures:
            return
        async with session_scope() as s:
            for record in captures:
                s.add(_capture_orm_from_record(record))

    async def _persist_adapter_calls(self) -> None:
        calls = self.adapter_ctx.drain_calls()
        if not calls:
            return
        async with session_scope() as s:
            for call in calls:
                s.add(_adapter_call_orm_from_record(call, self.audit_id))

    async def _close_audit(
        self,
        captures: list[CaptureRecord],
        final_status: AuditStatus,
        anomalies: list[dict[str, Any]] | None = None,
        consistency_violations: list[dict[str, Any]] | None = None,
    ) -> None:
        counts: Counter[CaptureStatus] = Counter(r.status for r in captures)

        async with session_scope() as s:
            await s.execute(
                update(Audit)
                .where(Audit.audit_id == self.audit_id)
                .values(
                    status=final_status.value,
                    completed_at=datetime.now(timezone.utc),
                    total_cost_gbp=self.cost_tracker.total_decimal,
                    variables_attempted=len(captures),
                    variables_passed=counts[CaptureStatus.PASSED],
                    variables_failed=counts[CaptureStatus.FAILED],
                    variables_partial=counts[CaptureStatus.PARTIAL],
                    variables_errored=counts[CaptureStatus.ERROR],
                    variables_unmeasurable=counts[CaptureStatus.UNMEASURABLE],
                    anomalies=anomalies or [],
                    consistency_violations=consistency_violations or [],
                )
            )


# ─── ORM mapping helpers (kept private to the orchestrator for now) ─────────


def _capture_orm_from_record(record: CaptureRecord) -> Capture:
    """Map a CaptureRecord (Pydantic) to a Capture (SQLAlchemy ORM)."""
    return Capture(
        capture_id=record.capture_id,
        audit_id=record.audit_id,
        variable_id=record.variable_id,
        pillar=record.pillar,
        captured_at=record.captured_at,
        taxonomy_version=record.taxonomy_version,
        subject_type=record.subject_type.value,
        subject_id=record.subject_id,
        status=record.status.value,
        value=record.value,
        rules=[r.model_dump() for r in record.rules] if record.rules else None,
        evidence_weight=record.evidence_weight.value,
        data_sources_used=record.data_sources_used,
        cost_incurred_gbp=Decimal(str(record.cost_incurred_gbp)),
        staleness_seconds=record.staleness_seconds,
        errors=record.errors,
        raw_response_ref=record.raw_response_ref,
    )


def _adapter_call_orm_from_record(
    record: "AdapterCallRecord",
    audit_id: UUID,
) -> AdapterCall:
    return AdapterCall(
        audit_id=audit_id,
        adapter=record.adapter,
        endpoint=record.endpoint,
        started_at=record.started_at,
        duration_ms=record.duration_ms,
        cost_gbp=record.cost_gbp,
        status_code=record.status_code,
        error=record.error,
    )
