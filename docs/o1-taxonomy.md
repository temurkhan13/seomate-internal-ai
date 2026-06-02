# O1 — SEO Variable Taxonomy

**Project:** Pixelette Internal SEO Tool
**Owner:** Humza Chishty
**Status:** In progress
**Date started:** May 2026
**Reviewer:** Humza Chishty (single reviewer pattern, per direction brief)

This document is the constitutional reference for every variable our SEO system measures, scores, or acts on. Every later automation decision must trace to a variable defined here. Where this document is silent, the system does not act.

---

## Methodology

### Source Tier System

| Tier | Definition | Examples |
|------|------------|----------|
| **A** | Google's own canonical sources | Search Central documentation, Quality Rater Guidelines, Search Liaison statements, Google patents |
| **B** | Large-scale empirical studies with disclosed methodology | Backlinko ranking studies, Searchmetrics ranking factor studies, Moz research, Princeton/IIT GEO paper, peer-reviewed academic work |
| **C** | Established practitioner sources with reasoned methodology | Search Engine Land, Search Engine Journal, SearchPilot case studies, AWR studies, SISTRIX research, Aleyda Solis |
| **D** | Single-practitioner claims without disclosed methodology | Forum posts, individual blog opinions, agency marketing pages |

**Rule:** A variable qualifies for inclusion only if its evidence is supported by at least one Tier A or B source plus at least one corroborating source from Tier A, B, or C. Tier D sources are recorded if relevant but never count toward the citation requirement.

### Evidence Weight Rubric

| Weight | Definition |
|--------|------------|
| **Consensus** | Confirmed by Tier A plus at least one Tier B or C source. No significant contradiction in any tier. |
| **Probable** | Multiple Tier B and C sources agree. No Tier A confirmation but no Tier A contradiction either. |
| **Contested** | Reputable sources disagree on whether the variable matters or how much it matters. Recorded with the contradiction made explicit. |
| **Speculative** | Limited published evidence, mostly practitioner intuition. Recorded for measurement and tracking only. |

### Operational Mapping (Model B)

The taxonomy keeps every variable that a reputable practitioner or research source has identified, regardless of evidence weight. The weight does not gate inclusion — it gates **what the system is allowed to do with each variable** when it eventually drives recommendations and deployments.

| Weight | What the system can do with this variable |
|--------|--------------------------------------------|
| **Consensus** | Trusted as a scoring input. Recommendations from these can flow through the standard approval ladder. The system speaks confidently about the expected effect. |
| **Probable** | Trusted as a scoring input with the same approval ladder, but flagged for outcome tracking — does deploying this actually move the metric? Wording in proposals is slightly hedged. |
| **Contested** | Tracked and surfaced as recommendations, framed honestly about what the change does (e.g., "this is a CTR optimisation, not a ranking factor"). Never auto-approved without human sign-off. The framing in user-facing language reflects the contradiction in the evidence. |
| **Speculative** | Measured and watched. Surfaces as a hypothesis on a watchlist. Does not drive recommendation generation directly. Graduates to Probable if measured outcomes after at least 5 deployments support the effect. |

This is a deliberate inversion of the previous project's pattern of treating uncited practitioner claims with the same operational confidence as Google-confirmed signals. Practitioner intuition is preserved (no information lost) but operational behaviour stays calibrated to evidence (no over-claiming).

### No industry / site-type weighting (deliberate)

The taxonomy does not assign per-industry, per-vertical, or per-site-type weights to any variable. Every variable is documented at equal operational priority within its evidence-weight tier.

This is a conscious decision, not an oversight. Assigning weightings of the form "for SaaS sites, P3-01 backlinks matters 2× more than P1-22 schema validity" would require empirical ranking-outcome data across multiple industries — data we do not have at this stage. Inventing those weightings from theory or practitioner intuition would lower the quality bar of the entire taxonomy: it would replace the sourced, weight-tiered methodology of every other variable with guesswork.

The path to industry/site-type weightings is empirical, not theoretical:

1. Run all measurable variables on a single pilot site (Pixelette as the dogfood site).
2. Act on the recommendations the system surfaces.
3. Observe which interventions moved which metrics.
4. Repeat on a second site of a distinct type.
5. After several sites and several deployment cycles, patterns emerge — *those* are the weightings, derived from outcomes rather than asserted from theory.

Until that empirical record exists, the taxonomy treats every variable in a tier as equally important within that tier. Recommendations are framed by tier (Consensus → confident, Probable → tracked, Contested → human-reviewed, Speculative → watchlist) and not by industry-specific weighting. This is a constitutional decision and changing it later requires the same rigour as any other methodology change.

### Pillars

Seven pillars covering the full discipline:

1. **P0 — Strategic Foundation** — keyword research, intent classification, content strategy, target audience, competitive positioning
2. **P1 — On-Page SEO** — metadata, headings, content structure, internal linking, schema markup, on-page entity coverage
3. **P2 — Technical SEO** — crawlability, indexation, performance, mobile, JavaScript rendering, security
4. **P3 — Off-Page Authority** — backlinks, referring domains, anchor distribution, brand mentions, citations
5. **P4 — Content Operations** — publishing cadence, content quality, E-E-A-T, freshness, depth
6. **P5 — Local SEO** — Google Business Profile, citations, NAP, reviews, local pack signals
7. **P6 — AI Search / GEO** — AI Overview eligibility, ChatGPT/Perplexity citation visibility, GEO methods

### Scope

| Dimension | Decision |
|-----------|----------|
| Search engines | Google primary. Bing and AI search engines secondary, called out where relevant. |
| Geography | US-primary. UK and other markets covered later if needed. |
| Page types | All standard categories: product, service, landing, category, blog, about, informational. |
| Granularity | Each variable is specifically measurable. Not "title tag" but "title tag includes target keyword in first 60 characters." |
| Time horizon | Variables relevant in 2026. Historical factors that no longer matter (exact match domains, keyword density formulae, AMP) are excluded from operational use, recorded with their deprecated status if referenced. |

### Seven-Step Process Per Variable

Each variable goes through these steps before earning its row in the operational taxonomy:

1. **Define** the variable precisely. Single sentence. Measurable.
2. **Cite** at least two qualifying sources, recorded with URL, author, and publication date if available. Paraphrase the source claim, do not lift direct quotes.
3. **Weight** the evidence using the rubric.
4. **Identify** the data source(s) that can measure it.
5. **Verify** the data source delivers the data at the required granularity.
6. **Cost** the data source: free, per-call, subscription, with a rough order of magnitude.
7. **Map dependencies** to other variables.

### Step 1.5 — Evaluation Rules (Conditional)

Where a variable's measurement involves judging "correctness," "validity," "appropriateness," "completeness," or any similar binary or multi-state evaluation rather than reading a numeric value, an additional **Step 1.5** lists the explicit rules the system uses. Each rule is a single concrete check that can be programmatically evaluated against the data source from Step 4. The variable's overall status reflects which rules pass and which fail, with each failure producing a specific named violation that downstream recommendation logic can address.

Variables that are pure numerical or categorical measurements (word count, click count, search volume, CTR, INP milliseconds) do not require Step 1.5 — the value itself is the measurement.

Step 1.5 is added to a variable when:
- The definition uses words like "correctness," "validity," "appropriateness," "completeness," "well-formed," "best practice"
- The result of evaluation is a composite assessment of multiple sub-checks rather than a single value
- Different failure modes produce different recommendation responses

When Step 1.5 is absent, the variable produces a value that downstream logic interprets directly.

### Crawler / Page Data Source Decision

For all variables requiring page content extraction, the platform uses **DataForSEO On-Page API (Instant Pages endpoint)** as the data provider. This decision was made to avoid the maintenance burden of an owned crawler and to leverage DataForSEO's pre-computed structured fields. The decision is revisitable at SaaS scale if unit economics change.

DataForSEO On-Page API documentation: https://docs.dataforseo.com/v3/on_page-instant_pages/

---

# Pillar 1 — On-Page SEO

**Total candidates:** 50
**Status:** Complete (50 of 50; P1-39 and P1-40 removed in May 2026 dedup audit, retained as redirect notes)

## Pillar 1 Index

| ID | Variable | Status | Weight |
|----|----------|--------|--------|
| P1-01 | Title tag presence and uniqueness | Complete | Consensus |
| P1-02 | Title tag length (50–60 character target) | Complete | Contested |
| P1-03 | Title tag includes target keyword | Complete | Consensus |
| P1-04 | Title starts with keyword | Complete | Speculative |
| P1-05 | Title-to-content match score | Complete | Probable |
| P1-06 | Title brand placement | Complete | Probable |
| P1-07 | Meta description presence | Complete | Consensus |
| P1-08 | Meta description length (140–160 character target) | Complete | Contested |
| P1-09 | Meta description includes target keyword | Complete | Contested |
| P1-10 | Snippet prefix character count | Complete | Speculative |
| P1-11 | H1 presence | Complete | Consensus |
| P1-12 | H1 uniqueness (single H1) | Complete | Contested |
| P1-13 | H1 keyword inclusion | Complete | Consensus |
| P1-14 | H2/H3 keyword inclusion | Complete | Probable |
| P1-15 | Heading hierarchy correctness | Complete | Probable |
| P1-16 | URL length | Complete | Contested |
| P1-17 | URL keyword inclusion | Complete | Probable |
| P1-18 | URL path readability | Complete | Probable |
| P1-19 | URL depth from root | Complete | Probable |
| P1-20 | Canonical tag presence and self-reference | Complete | Consensus |
| P1-21 | Schema markup type appropriateness | Complete | Consensus |
| P1-22 | Schema markup completeness and validity | Complete | Consensus |
| P1-23 | Internal inbound link count | Complete | Consensus |
| P1-24 | Internal inbound link quality | Complete | Probable |
| P1-25 | Internal link anchor text relevance | Complete | Consensus |
| P1-26 | Outbound link quality and theme | Complete | Probable |
| P1-27 | Outbound link count | Complete | Contested |
| P1-28 | Image alt text coverage | Complete | Consensus |
| P1-29 | Image filename relevance | Complete | Consensus |
| P1-30 | Image dimensions and weight | Complete | Consensus |
| P1-31 | Open Graph tags | Complete | Probable |
| P1-32 | Twitter Card tags | Complete | Probable |
| P1-33 | Robots meta tag | Complete | Consensus |
| P1-34 | Content depth / word count (covers leaked `numTokens`) | Complete | Probable |
| P1-35 | TF-IDF / keyword prominence (approximates leaked `avgTermWeight`) | Complete | Probable |
| P1-36 | Semantic keyword and entity coverage | Complete | Probable |
| P1-37 | Entity match score | Complete | Probable |
| P1-38 | Original content score | Complete | Probable |
| P1-39 | Average term weight | Removed (subsumed by P1-35) | — |
| P1-40 | Token count | Removed (subsumed by P1-34) | — |
| P1-41 | Content freshness — byline date | Complete | Probable |
| P1-42 | Content freshness — syntactic date | Complete | Probable |
| P1-43 | Content freshness — semantic date | Complete | Probable |
| P1-44 | Content update magnitude | Complete | Probable |
| P1-45 | Historical update cadence | Complete | Probable |
| P1-46 | Duplicate content within site | Complete | Consensus |
| P1-47 | Breadcrumb navigation and BreadcrumbList schema | Complete | Consensus |
| P1-48 | Bullets and numbered lists | Complete | Probable |
| P1-49 | Table of contents | Complete | Probable |
| P1-50 | Multimedia presence | Complete | Probable |
| P1-51 | Reading level / readability | Complete | Probable |
| P1-52 | Grammar and spelling | Complete | Consensus |

---

## P1-01 — Title tag presence and uniqueness

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
Every indexable page on the site has a non-empty `<title>` element in its HTML head, and the title text is distinct from every other indexable page on the same site (no two indexable pages share the exact same title text).

### Step 1.5 — Evaluation rules
A site passes title presence and uniqueness when ALL of the following rules pass:

1. **Every indexable page has a `<title>` element.** No indexable page returns 200 without a populated `<title>` in its head.
2. **Title text is non-empty.** No page has a `<title>` element containing only whitespace, default placeholder text ("Untitled Document"), or a CMS template variable that failed to render.
3. **No two indexable pages share the same title.** Site-wide aggregation produces zero duplicate-title clusters across indexable pages.
4. **Single `<title>` element per page.** No page has multiple `<title>` elements in the head (per HTML5 spec, only one is valid).
5. **Title duplication on non-indexable pages does not count.** Pages excluded from indexing (`noindex`, redirected, blocked by robots.txt) are exempt from the uniqueness check.
6. **Failure modes produce distinct findings.** "No title" generates a different recommendation (write a title) than "duplicate title" (rewrite to differentiate) than "multiple title elements" (fix template).

A site passing all 6 rules has correct title presence and uniqueness.

### Step 2 — Citations
1. **Google Search Central — Title Link Guidance** (https://developers.google.com/search/docs/appearance/title-link, Google, accessed May 2026). Google states that every page on a site should have a title declared in the `<title>` element, and that the title text on each page must be distinct from other pages on the same site. The document specifically warns against repeating boilerplate titles across pages, noting that identical titles make it impossible for users to distinguish between pages in search results.
2. **Google Search Central — Search Essentials, Key Best Practices** (https://developers.google.com/search/docs/essentials, Google, accessed May 2026). Lists placement of target keywords prominently in page titles as a Key Best Practice, which presumes the title element exists.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean, accessed May 2026). Lists "Keyword in Title Tag" (factor #10) and "Duplicate Meta Information On-Site" (factor #76) as practitioner-recognised ranking factors, confirming both presence and uniqueness.

### Step 3 — Evidence weight rationale
Google explicitly states presence and uniqueness as requirements in its primary public documentation for the title element. Backlinko (Tier B/C) corroborates. No reputable source disputes either point. Qualifies as **Consensus** under the rubric (Tier A confirmation plus Tier B corroboration, no contradiction).

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** (Instant Pages endpoint, https://docs.dataforseo.com/v3/on_page-instant_pages/). Returns `meta_title` (title tag content) and `duplicate_title` (boolean: page has multiple title elements in head) per URL.
- **Site-level uniqueness aggregation**: our own logic on top of DataForSEO's per-page output. We collect all `meta_title` values across the site's URLs and deduplicate to detect cross-page title collisions.
- **Verification supplement: Google Search Console URL Inspection API**. Reports what Google actually sees as the title for each indexed URL. Useful as a cross-check (Google can rewrite titles), not as primary measurement.

### Step 5 — Verification
DataForSEO documentation confirms `meta_title` is returned per URL and `duplicate_title` is a per-page boolean (covers in-head duplication, not site-wide). Site-level uniqueness is implemented by us as a `GROUP BY meta_title HAVING COUNT(*) > 1` query against stored audit results. Granularity required: per-page extraction, per-site aggregation. Granularity delivered: matches. Live verification against the two pilot sites (Pixelette Technologies, Pixelette Holdings) deferred until the build phase. Confidence in data source: high.

### Step 6 — Cost
DataForSEO On-Page Instant Pages: approximately $0.0006–$0.005 per page audited. For a pilot site of ~200 pages, full audit cost approximately £0.10–£0.80. Site-level aggregation runs against stored data and is free.

### Step 7 — Dependencies and cross-references
- **Depended upon by:** P1-02 (length), P1-03 (keyword inclusion), P1-04 (starts with keyword), P1-05 (title-content match), P1-06 (brand placement)
- **Sub-case of:** P1-46 (duplicate content within site) when applied to title text specifically
- **Cross-pillar:** P0-13 (keyword-to-page mapping) informs whether title aligns strategically
- **No upstream dependency** — primary measurement.

---

## P1-02 — Title tag length (50–60 character target)

**Pillar:** On-Page SEO
**Evidence weight:** Contested

### Step 1 — Definition
The page's title tag character count falls within a target range, conventionally 50–60 characters, intended to display fully in Google search results without being truncated.

### Step 2 — Citations
1. **Google Search Central — Title Link Guidance** (https://developers.google.com/search/docs/appearance/title-link, Google, accessed May 2026). Google states there is no hard character limit on the title element, but that the title link is truncated in search results to fit the device width. Google does not endorse a specific target character count.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). The 50–60 character recommendation is practitioner consensus reflecting observed truncation behaviour on standard SERP layouts; it is not framed by Backlinko or by Google as an algorithmic ranking factor in its own right.
3. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `title_length` integer field and pre-computed `checks.title_too_long` and `checks.title_too_short` boolean flags, evidencing industry tooling treats this as a measurable concern.

### Step 3 — Evidence weight rationale
Google does not endorse a specific character target. The 50–60 range reflects observed truncation in mobile and desktop SERP layouts at the time of measurement, not a Google rule. Practitioners agree on the rough range but the specific number is observation-based and varies by device and SERP feature. Qualifies as **Contested** because the underlying assertion (length matters for visibility) is undisputed but the specific threshold (50–60) is not a Google-endorsed value.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `title_length` (integer character count per page).
- **Threshold logic: our own.** DataForSEO's `checks.title_too_long` boolean uses their internal threshold, which we may override with our own (e.g., 60-char ceiling) to match our chosen specification.

### Step 5 — Verification
DataForSEO documentation confirms `title_length` is returned per page. Threshold application is our own application logic at scoring time. Granularity required: per-page integer length, plus a configurable threshold. Granularity delivered: matches. Live threshold calibration deferred until we audit pilot sites and observe actual truncation in their rankings.

### Step 6 — Cost
Bundled into the per-page DataForSEO On-Page audit cost (no additional cost beyond the base audit).

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-01 (title must exist before it can be measured for length).
- **No downstream dependencies.**
- **Cross-pillar:** none.

---

## P1-03 — Title tag includes target keyword

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The page's title tag contains the primary target keyword for the page (the keyword the page is intended to rank for), in any position within the title text.

### Step 2 — Citations
1. **Google Search Central — Search Essentials** (https://developers.google.com/search/docs/essentials, Google, accessed May 2026). Lists placement of target keywords prominently in page titles as a Key Best Practice in their official guidance to site owners.
2. **Google Search Central — SEO Starter Guide** (https://developers.google.com/search/docs/fundamentals/seo-starter-guide, Google, accessed May 2026). Recommends using words people actually search for and matching those words to user search terms in titles.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #10 (Keyword in Title Tag) is one of the most consistently cited on-page ranking factors in practitioner research.

### Step 3 — Evidence weight rationale
Google explicitly recommends keyword inclusion in titles in primary documentation. Backlinko corroborates. No reputable source disputes the practice. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `meta_title` (title text content per page).
- **Comparison logic: our own.** Compare title text against the page's target keyword (sourced from P0-13 keyword-to-page mapping) to detect inclusion, case-insensitive match.

### Step 5 — Verification
DataForSEO returns full title text. Inclusion check is straightforward string matching with reasonable normalisation (lowercase, trim, strip diacritics). Granularity required: per-page binary plus position and exact-match strictness flags. Granularity delivered: by composition. Live verification against pilot sites deferred. Confidence in data source: high.

### Step 6 — Cost
Bundled into DataForSEO audit cost. Comparison logic is computational, free.

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-01 (title must exist), P0-13 (target keyword must be defined for the page).
- **Depended upon by:** P1-04 (title starts with keyword) and P1-06 (title brand placement) which both depend on this measurement existing first.
- **Cross-pillar:** P0-01 (intent classification) informs whether keyword-in-title carries different weight by intent type.

---

## P1-04 — Title starts with keyword

**Pillar:** On-Page SEO
**Evidence weight:** Speculative

### Step 1 — Definition
The page's primary target keyword appears within the first three words of the title tag.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #11 (Title Tag Starts with Keyword). Backlinko presents this as a ranking factor based on older correlative analyses.
2. **Google Search Central — Title Link Guidance** (https://developers.google.com/search/docs/appearance/title-link, Google, accessed May 2026). Google does not endorse keyword position within the title as a ranking factor; the document recommends descriptive concise titles without specifying ordering rules.

### Step 3 — Evidence weight rationale
Backlinko lists this as a factor based on historical correlative studies, not a controlled experiment or Google statement. Modern Google guidance does not endorse keyword positioning rules; the system is understood to read titles contextually rather than positionally. No Tier A or B source confirms keyword-at-start as a current ranking factor. Qualifies as **Speculative** under the rubric. Recorded here for completeness but flagged for the watchlist; not used as an operational scoring input until additional evidence emerges.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `meta_title`.
- **Position logic: our own.** Tokenise the title and check whether the target keyword (or its head term) appears within the first N tokens.

### Step 5 — Verification
DataForSEO returns full title text. Position analysis is trivial. Granularity required: per-page boolean for keyword-in-first-N. Granularity delivered: by composition. **Caveat:** evidence weight is the limiting factor here, not data availability.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-01, P1-03 (keyword inclusion must be true before position can matter), P0-13.
- **Watchlist candidate.** Should not be used in operational scoring until evidence weight strengthens.

---

## P1-05 — Title-to-content match score

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
Semantic similarity between the page's title text and the page's main content body, measured as a 0–1 score where higher values indicate better topical alignment between what the title promises and what the page delivers.

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leaked Google ranking infrastructure documentation includes a feature named `titlematchScore`, which Mike King's analysis identifies as a measure of title-to-content alignment used as a quality signal in Google's ranking pipeline.
2. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `title_to_content_consistency` field as a 0–1 relevance score between title text and page content, evidencing the industry treats this as a measurable concern.

### Step 3 — Evidence weight rationale
The leaked Google feature `titlematchScore` is strong evidence the metric exists in production ranking infrastructure. The leak's authenticity has been broadly accepted by the SEO research community (Mike King, Rand Fishkin, Cyrus Shepard, others). Google has not officially confirmed or denied individual features from the leak, leaving this in a reliable-but-not-officially-endorsed position. Qualifies as **Probable**: leaked-but-credible Google feature, with industry tooling (DataForSEO) treating it as measurable.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `title_to_content_consistency` (returned as 0–1 score per page).

### Step 5 — Verification
DataForSEO documentation confirms `title_to_content_consistency` is a returned field. The exact semantic-similarity method DataForSEO uses (TF-IDF, embeddings, etc.) is not disclosed in their public docs, so the score is opaque but consistent across pages. Granularity required: per-page 0–1 score. Granularity delivered: matches. **Caveat:** DataForSEO's score is not Google's `titlematchScore`; the two are correlated by intent, not identical. We treat the DataForSEO value as a proxy.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-01 (title must exist), and on the page having extractable main content body (DataForSEO handles content extraction).
- **Conceptually related to:** P1-37 (entity match score), P1-38 (original content score) — all part of the same content-quality cluster from the leak.

---

## P1-06 — Title brand placement

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The site's brand or business name appears at the end of the title tag, conventionally separated from the descriptive portion by a delimiter such as `|`, `-`, or `—`. Practitioner pattern: `[Descriptive Title] | [Brand]`.

### Step 2 — Citations
1. **Google Search Central — Title Link Guidance** (https://developers.google.com/search/docs/appearance/title-link, Google, accessed May 2026). Google recommends including the business or website name in titles, particularly for the homepage, but does not specify mandatory placement. The recommendation supports brand-bearing titles without endorsing position rules.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Section "Brand Signals" treats brand association in on-page elements as a contributing signal, with title brand inclusion practitioners' preferred location for non-homepage pages.

### Step 3 — Evidence weight rationale
Google endorses brand inclusion in titles but not specific placement. Practitioner consensus places the brand at the end (so descriptive content reaches users first in truncated displays). No Tier A or B source contradicts this. Qualifies as **Probable**: well-supported as a convention, not endorsed by Google as an algorithmic factor specifically.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `meta_title`.
- **Pattern logic: our own.** Detect whether the brand string appears as a suffix of the title (after a recognised delimiter), as a prefix, or not at all.

### Step 5 — Verification
DataForSEO returns full title text. Detection logic requires the brand string to be known per site (configurable). Granularity required: per-page categorical (suffix / prefix / not present). Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-01 (title must exist), and brand string defined per site (configuration).
- **Cross-pillar:** P0-15 (brand search volume) — strong brands benefit more from brand-suffixed titles; weak brands may benefit from brand-prefixed or omitted-brand titles.

---

## P1-07 — Meta description presence

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
Every indexable page on the site has a non-empty `<meta name="description">` element in its HTML head.

### Step 2 — Citations
1. **Google Search Central — Snippets and Meta Description** (https://developers.google.com/search/docs/appearance/snippet, Google, accessed May 2026). Google recommends meta description tags as a way to provide a succinct summary of the page that may be used to generate the search snippet, while noting that Google may also generate snippets dynamically from page content when meta description is missing or unhelpful.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #12 (Keyword in Description Tag) presupposes the description tag exists; practitioner consensus universally recommends meta description on every page.

### Step 3 — Evidence weight rationale
Google recommends meta description as a snippet input. Backlinko corroborates. No reputable source argues against having a meta description. The variable is consensus on its presence, even though Google has separately stated the meta description is not a direct ranking factor (its value is in click-through rate via snippet quality). Qualifies as **Consensus** for presence specifically.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `description` (meta description content per page) and `checks.no_description` (boolean indicator).

### Step 5 — Verification
DataForSEO documentation confirms both `description` and `checks.no_description` are returned. Granularity required: per-page binary (present/absent) and content text. Granularity delivered: matches. Confidence: high.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depended upon by:** P1-08 (length), P1-09 (keyword inclusion), P1-10 (snippet prefix character count).
- **No upstream dependency.**

---

## P1-08 — Meta description length (140–160 character target)

**Pillar:** On-Page SEO
**Evidence weight:** Contested

### Step 1 — Definition
The page's meta description tag character count falls within a target range, conventionally 140–160 characters, intended to display fully in Google search result snippets without being truncated.

### Step 2 — Citations
1. **Google Search Central — Snippets and Meta Description** (https://developers.google.com/search/docs/appearance/snippet, Google, accessed May 2026). Google states there is no hard character limit on meta descriptions, and that the snippet shown in search results is dynamically truncated based on context and device width. Google does not endorse a specific target.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). The 140–160 range is practitioner consensus reflecting observed truncation behaviour on typical SERP layouts; it is not framed as an algorithmic ranking factor.
3. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `description_length` field and includes pre-computed checks for description length issues.

### Step 3 — Evidence weight rationale
Google does not endorse a specific character target. Practitioner range reflects observed truncation, varies by device and snippet generation. Qualifies as **Contested** for the same reason as P1-02 (length matters for visibility, but the specific threshold is observation-based, not algorithmic).

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `description_length` (integer character count per page).
- **Threshold logic: our own.**

### Step 5 — Verification
DataForSEO returns `description_length`. Threshold is application logic. Granularity required: per-page integer plus configurable threshold. Granularity delivered: matches.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-07 (description must exist).
- **No downstream dependencies.**

---

## P1-09 — Meta description includes target keyword

**Pillar:** On-Page SEO
**Evidence weight:** Contested

### Step 1 — Definition
The page's meta description contains the primary target keyword for the page, in any position.

### Step 2 — Citations
1. **Google Search Central — Snippets and Meta Description** (https://developers.google.com/search/docs/appearance/snippet, Google, accessed May 2026). Google has stated in multiple official communications (including the SEO Starter Guide and various Search Liaison statements) that the meta description is not a direct ranking factor; its value is in click-through rate via snippet quality. Google does not recommend keyword stuffing in descriptions and emphasises that descriptions should be helpful summaries.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #12 (Keyword in Description Tag) lists this as a practitioner-recognised factor, primarily because matched terms in the description are bolded in the SERP snippet, increasing visual prominence and click-through rate.

### Step 3 — Evidence weight rationale
Google explicitly states meta description is not a direct ranking factor. Practitioners recommend keyword inclusion for CTR benefit (keyword bolding in snippet). The two positions agree on the underlying reality (description is not a ranking factor) but disagree on whether keyword inclusion is therefore worth doing. Qualifies as **Contested**: included for CTR optimisation purposes, not for ranking purposes.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `description`.
- **Comparison logic: our own.** Compare against target keyword sourced from P0-13.

### Step 5 — Verification
DataForSEO returns full description text. String matching is trivial. Granularity required: per-page binary plus position. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-07 (description must exist), P0-13 (target keyword defined).
- **Use case:** This variable should drive snippet/CTR optimisation rather than ranking optimisation. Recommendations from this variable should be framed as CTR-improving, not as ranking-improving.

---

## P1-10 — Snippet prefix character count

**Pillar:** On-Page SEO
**Evidence weight:** Speculative

### Step 1 — Definition
The character count of the prefix portion of the SERP snippet shown for a page in Google search results, measured against the leaked Google feature `snippetPrefixCharCount`.

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leaked Google ranking infrastructure documentation includes a feature named `snippetPrefixCharCount`. Mike King's analysis identifies this as a tracked feature but does not establish whether it is a ranking input or a descriptive measurement Google uses for snippet generation.
2. **No corroborating Tier A or B source.** Google has not officially confirmed or denied the feature's purpose. Practitioner research has not produced a controlled study connecting this specific measurement to ranking outcomes.

### Step 3 — Evidence weight rationale
The leaked feature exists in Google's infrastructure but its operational purpose is unclear (it may be analytical metadata rather than a ranking signal). Single source, no corroboration, no measurable outcome study. Qualifies as **Speculative** under the rubric. Per Model B, this variable is tracked and watched but does not drive recommendation generation directly. Graduates to Probable if measurement after deployment shows correlation with ranking outcomes.

### Step 4 — Data source(s)
- **Not directly available from DataForSEO On-Page API.** Snippet prefix is generated dynamically by Google in the SERP, not present in page HTML.
- **Approximate via DataForSEO SERP API** by inspecting the displayed snippet text per query and measuring the prefix portion before any bolded match.

### Step 5 — Verification
Snippet prefix character count is a SERP-side measurement, not a page-side one. Live verification requires SERP capture per (page, query) pair. DataForSEO SERP API can return organic results with snippets; computing the prefix length is our own logic on top.

### Step 6 — Cost
DataForSEO SERP API: approximately $0.001 per query. Adds cost beyond the per-page audit because measurement is per (page, query) rather than per page.

### Step 7 — Dependencies and cross-references
- **Depends on:** the page ranking for at least one tracked query (otherwise no SERP snippet exists to measure).
- **Watchlist entry.** Recorded for measurement once the system is operational; not a recommendation driver.

---

## P1-11 — H1 presence

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
Every indexable page on the site has at least one `<h1>` element in its body content.

### Step 2 — Citations
1. **Google Search Central — Search Essentials, Key Best Practices** (https://developers.google.com/search/docs/essentials, Google, accessed May 2026). Lists keyword inclusion in main page headings as a Key Best Practice, which presupposes heading elements exist.
2. **Google Search Central — Helpful Content guidance** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends using descriptive, helpful headlines and headings as part of producing people-first content.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #13 (Keyword Appears in H1 Tag) presupposes H1 exists.
4. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `checks.no_h1_tag` boolean indicator that detects H1 absence.

### Step 3 — Evidence weight rationale
Google explicitly recommends descriptive headings and refers to "main page headings" as a place for keyword prominence. Backlinko corroborates. DataForSEO's tooling treats H1 absence as a flagged issue. No reputable source argues against having an H1. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `checks.no_h1_tag` (boolean: true if H1 is missing).
- **Content extraction supplement: DataForSEO content_parsing endpoint** for full heading structure when H1 text is needed for downstream variables (P1-13).

### Step 5 — Verification
DataForSEO documentation confirms `checks.no_h1_tag` is a returned boolean per page. The field directly answers presence/absence. Granularity required: per-page binary. Granularity delivered: matches. Confidence: high.

### Step 6 — Cost
Bundled into the per-page DataForSEO On-Page audit cost.

### Step 7 — Dependencies and cross-references
- **Depended upon by:** P1-12 (uniqueness), P1-13 (keyword inclusion), P1-15 (heading hierarchy).
- **No upstream dependency.**

---

## P1-12 — H1 uniqueness (single H1)

**Pillar:** On-Page SEO
**Evidence weight:** Contested

### Step 1 — Definition
The page contains exactly one `<h1>` element in its body content (no zero, no multiple).

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Practitioner consensus historically has been "one H1 per page" as a rule.
2. **Google Search Central — John Mueller statements** (multiple official communications, including Search Off The Record podcast and Twitter/X). Google has stated that multiple H1 elements on a page are not a problem from Google's perspective — Google understands page structure regardless of the number of H1s.
3. **HTML5 Living Standard — W3C** (https://html.spec.whatwg.org/multipage/sections.html). HTML5 sectioning originally allowed multiple H1s within `<section>` elements, though the document outline algorithm aspect has been deprecated and current best practice for accessibility is a single H1.

### Step 3 — Evidence weight rationale
Practitioners say one H1; Google's official position is that multiple H1s are fine; HTML standards have been ambiguous over time. Qualifies as **Contested**: practitioner intuition disagrees with Google's official statement. Per Model B, recommendations from this variable should be framed honestly — improving structure clarity is plausible, but Google does not penalise multiple H1s.

### Step 4 — Data source(s)
- **Primary: DataForSEO content_parsing endpoint** which returns the page's full heading structure as an array. Counting H1 elements in the array gives the per-page H1 count.
- **Alternative:** parse rendered HTML directly if content_parsing is not invoked.

### Step 5 — Verification
DataForSEO content_parsing returns heading hierarchy. The Instant Pages endpoint includes heading information through its content object but the exact field for H1 count requires confirmation against the live API. **Verification status:** documentation review confirmed feasibility; live verification required during build to confirm the exact field path returns multiple H1s correctly.

### Step 6 — Cost
Bundled into DataForSEO On-Page audit cost (content extraction included).

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-11 (H1 must be present before uniqueness can be measured).
- **Cross-pillar:** accessibility considerations — single H1 supports WCAG conformance; this is an indirect benefit beyond SEO.

---

## P1-13 — H1 keyword inclusion

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The page's primary H1 element contains the primary target keyword for the page, in any position.

### Step 2 — Citations
1. **Google Search Central — Search Essentials, Key Best Practices** (https://developers.google.com/search/docs/essentials, Google, accessed May 2026). Explicitly recommends including target keywords in main page headings.
2. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends descriptive, helpful headlines that match what the page is about.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #13 (Keyword Appears in H1 Tag) is a long-established practitioner-recognised on-page factor.

### Step 3 — Evidence weight rationale
Google explicitly recommends keyword inclusion in main headings. Backlinko corroborates. No reputable source disputes the practice. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO content_parsing endpoint** for H1 text content.
- **Comparison logic: our own.** Compare H1 text against the page's target keyword (sourced from P0-13).

### Step 5 — Verification
DataForSEO content extraction returns heading text. Inclusion check is straightforward string matching with normalisation. Granularity required: per-page binary plus position. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-11 (H1 must exist), P0-13 (target keyword defined).
- **Cross-pillar:** P0-01 (intent classification) influences how strictly keyword-in-H1 should be enforced for different intent types.

---

## P1-14 — H2/H3 keyword inclusion

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The page's secondary headings (H2, H3) contain related keywords, semantic variations of the primary target, or topical entities relevant to the page's subject.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #31 (Keyword in H2, H3 Tags) has been a long-standing practitioner-recognised factor.
2. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends well-organised content with descriptive structure throughout, supporting the use of relevant terms across heading levels.

### Step 3 — Evidence weight rationale
Practitioner consensus, supported by Google's structural guidance, but not endorsed as a specific named ranking signal in Google's official documentation. Qualifies as **Probable**: well-supported by industry research, less explicitly named by Google than H1.

### Step 4 — Data source(s)
- **Primary: DataForSEO content_parsing endpoint** for full heading hierarchy and text.
- **Comparison logic: our own.** Match H2/H3 text against the page's keyword cluster (target keyword + semantic variations + entities from P0-08, P0-10).

### Step 5 — Verification
DataForSEO returns heading structure. Semantic keyword matching is composition logic. Granularity required: per-page coverage score (e.g., percentage of H2/H3 with keyword cluster overlap). Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P0-13 (keyword strategy), P0-08 (topic cluster), P0-10 (keyword-to-page mapping).
- **No P1 upstream beyond keyword targeting.**

---

## P1-15 — Heading hierarchy correctness

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
Headings on the page follow logical descending order (H1 → H2 → H3 → H4) without skipping levels (e.g., no jumping from H1 directly to H3). Each heading level is used as a structural element for content organisation, not for visual styling.

### Step 1.5 — Evaluation rules
A page passes heading hierarchy correctness when ALL of the following rules pass:

1. **Single H1 starts the hierarchy.** The page has exactly one H1, and it appears before any H2/H3/H4 in document order.
2. **No skipped levels descending.** Heading sequence does not skip levels going down (no H1 → H3 without H2, no H2 → H4 without H3).
3. **Levels can be reused.** Multiple H2s under the same H1 are valid; multiple H3s under the same H2 are valid. The rule is about descending without skipping, not about uniqueness.
4. **Headings are not used for styling.** Heading tags are not used to make text larger or bolder when no structural section is intended (e.g., a footer "Quick Links" wrapped in `<h2>` purely for visual size).
5. **Each heading has substantive content beneath it.** Heading is followed by at least one paragraph or block of content; empty-section headings are not used.
6. **Heading text describes the section.** Heading text is a meaningful summary of the section that follows, not generic ("Section 1") or marketing-only ("Why we're great").

A page passing all 6 rules has correct heading hierarchy.

### Step 2 — Citations
1. **Web Content Accessibility Guidelines (WCAG) 2.2** (https://www.w3.org/WAI/WCAG22/quickref/, W3C, accessed May 2026). Requires meaningful sequence and proper heading structure for accessibility (criterion 1.3.1 Info and Relationships, 2.4.6 Headings and Labels, 2.4.10 Section Headings).
2. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends well-organised content as a quality signal; logical heading hierarchy is part of well-organised structure.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Site usability and content structure are referenced as ranking-relevant factors.

### Step 3 — Evidence weight rationale
Accessibility standard plus practitioner recommendation; Google endorses logical content structure but does not name heading hierarchy as a specific ranking signal. Qualifies as **Probable**: well-supported by accessibility standards and indirect Google guidance, no Tier A direct endorsement of strict hierarchy enforcement.

### Step 4 — Data source(s)
- **Primary: DataForSEO content_parsing endpoint** for full heading sequence.
- **Sequence analysis: our own.** Walk the heading list in document order and detect skipped levels.

### Step 5 — Verification
DataForSEO returns heading structure in document order. Sequence analysis is straightforward. Granularity required: per-page boolean (correct/incorrect) plus list of violations. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-11 (H1 must exist as the start of the hierarchy).
- **Cross-discipline:** accessibility (WCAG conformance) is the primary justification; SEO benefit is secondary.

---

## P1-16 — URL length

**Pillar:** On-Page SEO
**Evidence weight:** Contested

### Step 1 — Definition
The full URL of the page (including protocol, domain, path, and any parameters) stays under a target character count threshold, conventionally cited as 60–100 characters by practitioners.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #51 (URL Length). Backlinko's older correlative analyses suggested shorter URLs correlated with better rankings; this is correlative, not causal.
2. **Google Search Central — URL Structure** (https://developers.google.com/search/docs/crawling-indexing/url-structure, Google, accessed May 2026). Google recommends descriptive URLs that reflect page content but does not endorse a specific length limit. Google's John Mueller has stated in public communications that URL length is not a direct ranking factor.
3. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `url_length` integer field directly.

### Step 3 — Evidence weight rationale
Practitioner guidance based on correlative analysis; Google explicitly states URL length is not a ranking factor. The two positions are in direct contradiction. Qualifies as **Contested**: included for shareability and click-through considerations, not for direct ranking effect.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `url_length` (full URL character count) and `relative_url_length` (path-only character count) returned per page.

### Step 5 — Verification
DataForSEO documentation confirms both length fields are returned per page. Granularity required: per-page integer length. Granularity delivered: matches. Threshold logic is application-side.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **No upstream dependency.**
- **Cross-pillar:** P3-06 (anchor text) — URLs that appear as naked-URL anchors benefit from being short and readable. Indirect off-page benefit.

---

## P1-17 — URL keyword inclusion

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The page's URL slug (the path portion after the domain) contains the primary target keyword for the page, in slug-friendly form (lowercase, hyphen-separated, no special characters).

### Step 2 — Citations
1. **Google Search Central — URL Structure** (https://developers.google.com/search/docs/crawling-indexing/url-structure, Google, accessed May 2026). Google recommends descriptive URLs that include words relevant to the page content. Google states URLs should help users understand what the page is about.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #55 (Keyword in URL) is a long-standing practitioner-recognised factor.
3. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `url` field plus `seo_friendly_url` boolean check.

### Step 3 — Evidence weight rationale
Google endorses descriptive URLs that include relevant words. Backlinko corroborates. The specific algorithmic weight Google places on URL keywords is not officially disclosed, but Google's documentation supports the practice. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `url` and `seo_friendly_url` boolean check.
- **Comparison logic: our own.** Match URL slug against the target keyword (normalised: lowercase, hyphenated form, accent-stripped).

### Step 5 — Verification
DataForSEO returns full URL. Slug parsing is trivial. Granularity required: per-page binary plus exact-match strictness flag. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P0-13 (target keyword defined).
- **Caveat:** changing an existing URL is a Level 5 hard block in the previous project's risk model and remains a high-risk operation regardless. This variable is more useful as a guideline for new pages than as a recommendation for existing ones.

---

## P1-18 — URL path readability

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The URL slug uses lowercase descriptive words separated by hyphens, with no random session IDs, numerical product codes, or non-meaningful characters. The slug is human-readable and gives a reader a clear hint about page content from the URL alone.

### Step 1.5 — Evaluation rules
A URL passes path readability when ALL of the following rules pass:

1. **All-lowercase.** The slug contains no uppercase characters (mixed-case URLs cause case-sensitivity issues across servers and CDNs).
2. **Hyphens, not underscores.** Word separators are hyphens; no underscores or other non-standard separators.
3. **No double hyphens or trailing hyphens.** Slug does not contain `--`, does not start with `-`, does not end with `-`.
4. **No session IDs or random strings.** Slug does not contain UUIDs, base64 strings, or other non-meaningful random tokens.
5. **No raw numeric product codes alone.** A slug like `/p/47829` is not readable; product slugs include the product name (`/p/winter-boots-leather-mens-47829` is acceptable).
6. **No query parameters where path is appropriate.** Query parameters are reserved for filters/sort/pagination; primary content URLs use the path.
7. **No file extensions for content URLs.** Modern content URLs do not end in `.html`, `.aspx`, `.php` — these signal legacy CMS exposure.
8. **Words are recognisable.** Slug words are real words or recognisable abbreviations, not gibberish or auto-generated tokens.

A URL passing all 8 rules has good path readability.

### Step 2 — Citations
1. **Google Search Central — URL Structure** (https://developers.google.com/search/docs/crawling-indexing/url-structure, Google, accessed May 2026). Google recommends descriptive URLs that reflect page content, advising against long ID strings and parameters where possible. Google states URLs should help users understand what the page is about.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #52 (URL Path) and Factor #56 (URL String) reference URL readability as a contributing on-page factor.
3. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `seo_friendly_url` boolean check that flags non-readable URL patterns.

### Step 3 — Evidence weight rationale
Google endorses descriptive URLs but does not specify exact formatting rules. Backlinko corroborates. The boolean nature of the DataForSEO check yields a binary signal, not a graded one. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `url` and `seo_friendly_url` boolean check.
- **Pattern logic: our own** for granular detection (uppercase characters, multiple consecutive hyphens, query parameters, non-meaningful path segments).

### Step 5 — Verification
DataForSEO confirms `seo_friendly_url` boolean returned per page. Pattern analysis is composition logic. Granularity required: per-page boolean plus list of specific issues. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **No upstream dependency.**
- **Caveat:** changing existing URLs is Level 5 hard-blocked at deployment. Use as guideline for new pages.

---

## P1-19 — URL depth from root

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The number of path segments between the domain root and the page (e.g., `/blog/post` has depth 2; `/category/sub/page/detail` has depth 4). Measured purely on URL structure, distinct from click depth which measures path length through the internal link graph.

### Step 2 — Citations
1. **Google Search Central — Large Site Owner's Guide to Managing Crawl Budget** (https://developers.google.com/search/docs/crawling-indexing/large-site-managing-crawl-budget, Google, accessed May 2026). Google references that important pages should be reachable within a few clicks from the homepage; deeper pages may receive less crawl attention.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #69 (Site Architecture) references hierarchical depth as a factor.
3. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `click_depth` field measuring clicks from homepage to page (related concept, link-graph based).

### Step 3 — Evidence weight rationale
Google's crawl budget guidance supports the principle that deeper pages receive less attention. Backlinko corroborates. URL-segment depth is a structural correlate of click depth but the two are distinct measurements. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **URL-segment depth: our own** parsing of the URL path segment count.
- **Click-graph depth: DataForSEO** `click_depth` field.
- Both tracked because they answer different questions: URL depth is structural, click depth is reachability.

### Step 5 — Verification
URL parsing is trivial. DataForSEO `click_depth` confirmed in docs. Granularity required: per-page integer for both measures. Granularity delivered: matches.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P2 (Technical SEO) covers crawl-budget aspects in more depth; the click-depth measurement here cross-references that work.

---

## P1-20 — Canonical tag presence and self-reference

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
Each indexable page has a `<link rel="canonical">` tag in its HTML head pointing to the URL Google should treat as the authoritative version. For most pages this is the page's own URL (self-reference); for known-duplicate or syndicated pages it points to the master copy.

### Step 1.5 — Evaluation rules
A page passes canonical tag correctness when ALL of the following rules pass:

1. **Canonical tag present.** The page has a `<link rel="canonical">` element in its head.
2. **Single canonical declaration.** The page has exactly one canonical tag (multiple canonical tags cause Google to ignore them all).
3. **Canonical URL is absolute.** The canonical href is an absolute URL with scheme and host, not a relative path.
4. **Canonical URL returns 200.** The canonical target is a live page (not 404, not 410, not 5xx), is itself indexable (no `noindex`), and is not blocked by robots.txt.
5. **Self-reference for primary content.** Primary, non-duplicate pages canonicalise to themselves (canonical URL == page URL after normalisation).
6. **Cross-reference for known duplicates.** Pages that are genuine duplicates (paginated views of a master, sort/filter variants, syndicated copies) canonicalise to the master URL.
7. **No conflict with other indexing signals.** Canonical URL is consistent with the URL declared in the sitemap, the URL Google selects in GSC, and the dominant internal-link target (P2-07 covers conflict detection in detail).
8. **Scheme and host normalisation consistent.** Canonical URL uses the site's preferred scheme (https) and host variant (www vs non-www) consistently across the site.

A page passing all 8 rules has correct canonical tag configuration.

### Step 2 — Citations
1. **Google Search Central — Consolidate Duplicate URLs (Canonicalization)** (https://developers.google.com/search/docs/crawling-indexing/canonicalization, Google, accessed May 2026). Google recommends every page declare its canonical URL via `rel="canonical"` to prevent duplicate-content confusion and consolidate ranking signals onto one URL.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #25 (Rel=Canonical) is a recognised on-page factor.
3. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `canonical` field directly per page, plus `checks.canonical` indicator.

### Step 3 — Evidence weight rationale
Google explicitly recommends canonical tags in primary documentation. Backlinko corroborates. DataForSEO tooling treats it as a measurable concern. No reputable source disputes the practice. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `canonical` (returned URL) and `checks.canonical` boolean.
- **Self-reference logic: our own.** Compare canonical URL to the page's own URL.

### Step 5 — Verification
DataForSEO returns canonical URL per page. Self-reference comparison is straightforward string matching with normalisation (trailing slash, scheme). Granularity required: per-page tri-state (canonical present and self-referential, canonical present and points elsewhere, canonical absent). Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P2-09 (canonicalisation conflicts) — when canonical conflicts with other indexing signals (sitemap entries, internal links, hreflang), surfaced as a separate diagnostic at the technical pillar.

---

## P1-21 — Schema markup type appropriateness

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The page implements schema.org structured data using a type (or types) appropriate to its content category — Product schema on product pages, Article or NewsArticle on articles, FAQ on FAQ content, LocalBusiness for local-relevant pages, Recipe on recipes, etc. The schema type is a meaningful match to what the page actually is, not a generic or wrong type.

### Step 1.5 — Evaluation rules
A page passes schema markup type appropriateness when ALL of the following rules pass:

1. **At least one schema type present.** The page declares at least one schema.org structured data block in JSON-LD, microdata, or RDFa.
2. **Type matches page content category.** The declared type matches the page's actual nature (Product on product pages; Article/BlogPosting on articles; Recipe on recipes; FAQPage where the page is genuinely Q&A-structured; LocalBusiness on local-relevant pages).
3. **No misleading type declarations.** No schema declares a type the page does not actually represent (e.g., FAQPage on a page with no Q&A; Recipe on a page that is not a recipe).
4. **Most-specific applicable type used.** Where a hierarchy exists (Article → BlogPosting → TechArticle), the most-specific applicable subtype is used rather than the generic parent.
5. **Type is in Google's supported list where rich-result eligibility is intended.** Pages targeting rich results use one of Google's supported types from the search gallery.
6. **No prohibited types.** Schema types Google has explicitly deprecated or warned against (HowTo for non-instructional content, FAQ stuffed with marketing questions) are avoided.

A page passing all 6 rules has appropriate schema type.

### Step 2 — Citations
1. **Google Search Central — Search Gallery (Structured Data)** (https://developers.google.com/search/docs/appearance/structured-data/search-gallery, Google, accessed May 2026). Lists 26 supported structured data types eligible for rich results: Article, Breadcrumb, Carousel, Course list, Dataset, Discussion forum, Education Q&A, Employer aggregate rating, Event, FAQ, Image metadata, Job posting, Local business, Math solver, Movie, Organization, Product, Profile page, Q&A, Recipe, Review snippet, Software app, Speakable, Subscription and paywalled content, Vacation rental, Video.
2. **Schema.org** (https://schema.org/, accessed May 2026). The vocabulary specification that Google's structured data implementation references.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #124 (Schema.org Usage).
4. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `checks.has_micromarkup` boolean for presence detection.

### Step 3 — Evidence weight rationale
Google explicitly supports rich results derived from structured data and maintains an authoritative gallery of supported types. Backlinko corroborates. The principle that schema type should match content is a basic correctness requirement. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** `checks.has_micromarkup` for presence detection.
- **Type extraction: DataForSEO content_parsing endpoint or our own JSON-LD/microdata parsing** to identify which schema types are declared.
- **Appropriateness logic: our own.** Map detected schema type(s) to the page's classified `page_type` (product, article, blog, etc.) and validate alignment.

### Step 5 — Verification
DataForSEO confirms schema presence detection. Type extraction requires either content_parsing or our own JSON-LD parser. Type-to-content matching is application logic. Granularity required: per-page schema type list plus appropriateness boolean. Granularity delivered: by composition. **Verification flag:** the exact field path for type extraction needs live testing on pilot sites.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Scope of this variable:** "is the type appropriate for the page's content category" — type-selection check, not validity check.
- **Schema family hierarchy:** **P1-21 (this) → type appropriateness** (right type chosen). P1-22 → completeness and validity (the chosen type is well-formed and complete). P5-26 → LocalBusiness-specific instantiation (subset of P1-22 for local businesses). P6-19 → site-wide schema graph depth (interconnected schema across the site). P6-20 → Person/Organization entity markup (specific deep-dive subset of P6-19).
- **Depends on:** page_type classification (sourced via crawl + heuristics or strategic-pillar work).
- **Cross-references:** P1-22, P5-26, P6-19, P6-20.

---

## P1-22 — Schema markup completeness and validity

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The schema.org structured data on the page is well-formed JSON-LD (or microdata/RDFa), validates against Google's parser without errors, and includes all properties that are required and recommended for rich result eligibility for the schema type used.

### Step 1.5 — Evaluation rules
A page passes schema markup completeness and validity when ALL of the following rules pass:

1. **Syntactically valid JSON-LD.** The JSON-LD block parses as valid JSON; microdata/RDFa parses as valid HTML structured data.
2. **Validates against schema.org vocabulary.** All declared properties exist in the schema.org type definition; no invented properties.
3. **No deprecated properties.** Properties Google has marked deprecated or removed are not used; current property names are used where Google has updated the spec.
4. **All Google-required properties populated.** Every property Google lists as "required" for the schema type is present and non-empty.
5. **Recommended properties populated where data exists.** Properties Google lists as "recommended" are populated when the underlying data exists (e.g., `Product.aggregateRating` populated when reviews exist; `Article.author` always populated).
6. **Property values match Google's expected format.** Dates use ISO 8601, prices use valid currency codes, URLs are absolute, image properties resolve to live images.
7. **Schema content matches visible page content.** Facts in schema (price, rating, author, title) match the visible page content exactly; no hidden information.
8. **Passes Google's Rich Results Test without errors.** Validation through Google's tool returns no errors (warnings are tolerated where the data legitimately does not exist).
9. **Single canonical entity per page.** Where multiple schema blocks exist, they are interconnected via `@graph` and `@id` references rather than being competing duplicate declarations.

A page passing all 9 rules has complete and valid schema markup.

### Step 2 — Citations
1. **Google Search Central — Structured Data Documentation** (https://developers.google.com/search/docs/appearance/structured-data, Google, accessed May 2026). Google's documentation specifies required and recommended properties per supported schema type, with rich result eligibility contingent on correctness and completeness.
2. **Google Rich Results Test** (https://search.google.com/test/rich-results, Google). Provides authoritative validation per page against Google's parser.
3. **Schema.org Validator** (https://validator.schema.org/, accessed May 2026). Validates against the schema.org vocabulary independently of Google's implementation.
4. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `checks.has_micromarkup_errors` boolean indicating parsing or specification errors.

### Step 3 — Evidence weight rationale
Google explicitly requires valid schema for rich result eligibility and provides validation tooling. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** `checks.has_micromarkup_errors` for high-level error detection.
- **Detailed validation: Google Rich Results Test API** (free, accessed via Search Console URL Inspection or direct test) for property-level eligibility per page.
- **Completeness scoring: our own.** Cross-reference detected schema properties against required/recommended lists for each schema type.

### Step 5 — Verification
DataForSEO confirms error-detection flag. Google Rich Results Test API provides authoritative per-page validation results, free. Completeness scoring is application logic. Granularity required: per-page validity boolean plus completeness percentage by schema type. Granularity delivered: by composition.

### Step 6 — Cost
Bundled (DataForSEO) plus free (Google Rich Results Test). No additional cost.

### Step 7 — Dependencies and cross-references
- **Scope of this variable:** "is each schema block well-formed, validating, and complete per Google's per-type required and recommended properties" — validity check, given P1-21 has selected the right type.
- **Schema family hierarchy:** P1-21 → type appropriateness. **P1-22 (this) → completeness + validity per block**. P5-26 → LocalBusiness-specific instantiation. P6-19 → site-wide schema graph depth (cross-page interconnection). P6-20 → Person/Organization entity markup deep-dive.
- **Depends on:** P1-21 (schema must be present and of identifiable type before validity can be measured).
- **Cross-references:** P1-21, P5-26, P6-19, P6-20.

---

## P1-23 — Internal inbound link count

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The total number of internal links from other pages on the same site that point to this specific page. Higher counts typically indicate higher importance and receive more authority signal.

### Step 2 — Citations
1. **Google Search Central — Help Google find your content** (https://developers.google.com/search/docs/fundamentals/seo-starter-guide, Google, accessed May 2026). Google explicitly states that internal linking helps Google discover and rank content; the practice is part of standard crawl pathway optimisation.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #43 (Number of Internal Links Pointing to Page).
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leak references PageRank-style features (`PageRankNS`, `homepagePagerankNs`) confirming Google computes per-page authority based on the internal link graph.
4. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `inbound_links_count` field directly per page in full-site audit mode.

### Step 3 — Evidence weight rationale
Internal linking is a fundamental concept Google explicitly endorses. The leaked feature names confirm Google still uses PageRank-derived computations on the internal link graph. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `inbound_links_count` per page (computed across the full site crawl).

### Step 5 — Verification
DataForSEO confirms `inbound_links_count` is returned per page in a full-site audit. Granularity required: per-page integer. Granularity delivered: matches. **Caveat:** the count is meaningful only when the audit covers the full site, not when a single page is audited in isolation.

### Step 6 — Cost
Bundled with full-site audit. Single-page audits do not return meaningful inbound counts.

### Step 7 — Dependencies and cross-references
- **No upstream dependency** — primary measurement.
- **Used by:** P1-24 (link quality), P1-25 (anchor text relevance), and authority flow analysis at the strategic pillar.

---

## P1-24 — Internal inbound link quality

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The authority and topical relevance of the pages linking internally to this page. A link from a high-authority topically-relevant page passes more weight than a link from a low-authority unrelated page. Aggregated as a weighted score per target page.

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leak names PageRank-related features (`PageRankNS`, `IndyRank`, `siteAuthority`) confirming Google computes per-page authority scores that contribute to link-passing weight.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #44 (Quality of Internal Links Pointing to Page).
3. **Google — How Search Works (PageRank concept references)** (https://www.google.com/search/howsearchworks/, Google, accessed May 2026). Google has historically described PageRank-style signals as one input to ranking; specific operational details are not officially disclosed.

### Step 3 — Evidence weight rationale
Google's leaked features confirm authority-based link weighting exists. Backlinko corroborates the practitioner concept. Google does not officially disclose the exact algorithm. Qualifies as **Probable**: principle is sound, exact operational measurement is our composition.

### Step 4 — Data source(s)
- **Primary: composition logic.** For each inbound link, look up the originating page's authority score, computed by us via PageRank-style iteration over the internal link graph.
- **Data inputs:** DataForSEO inbound link details (which pages link to which) plus our own iterative authority computation.

### Step 5 — Verification
Authority score computation is a recursive operation over the link graph; the previous project's `analyse_authority_flow` module implemented this pattern. Granularity required: per-page weighted-authority score. Granularity delivered: by composition. Live verification requires a full site crawl plus the authority computation.

### Step 6 — Cost
Bundled (DataForSEO crawl) plus computational (our own iteration, free).

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-23 (inbound link count must exist as the underlying graph data).
- **Cross-pillar:** Strategic pillar's authority flow analysis aggregates this at site level.

---

## P1-25 — Internal link anchor text relevance

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The text used in internal links pointing to a page contains keywords or topical terms that describe the linked page's content, rather than generic phrases like "click here" or "read more." Anchor text serves as a topical signal Google uses to understand the linked page.

### Step 2 — Citations
1. **Google Search Central — SEO Starter Guide, Links and Navigation** (https://developers.google.com/search/docs/fundamentals/seo-starter-guide, Google, accessed May 2026). Google explicitly recommends descriptive anchor text and advises against generic "click here" links because anchor text helps both users and search engines understand the destination page.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #104 (Internal Link Anchor Text) is a long-established practitioner factor.
3. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides link details including anchor text per inbound link in full-site audit mode.

### Step 3 — Evidence weight rationale
Google explicitly recommends descriptive anchor text in primary documentation. Backlinko corroborates. Anchor text is a core mechanic in how internal authority and topical relevance flow between pages. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** link details (anchor text per inbound link) from full-site audit.
- **Relevance scoring: our own.** Compare anchor texts pointing to the page against the target page's keyword cluster (P0-13 mapping plus P0-08 topic cluster).

### Step 5 — Verification
DataForSEO returns link details including anchor text. Relevance scoring is composition logic — for example, percentage of inbound anchors matching target keyword or topic cluster, plus a list of generic-anchor outliers. Granularity required: per-page anchor relevance score. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-23 (inbound link data must exist), P0-13 (target keyword defined), P0-08 (topic cluster defined).
- **Cross-pillar:** P3-12 (external anchor text distribution) — same concept applied to external backlinks; covered in the off-page pillar.

---

## P1-26 — Outbound link quality and theme

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The page's outbound external links point to topically relevant, authoritative sources rather than spam, low-quality, or unrelated sites. Quality is a function of the linked domain's own authority; theme is a function of topical relevance to the source page's content.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factors #32 (Outbound Link Quality) and #33 (Outbound Link Theme) treat outbound link characteristics as on-page contributors.
2. **Google Search Central — Helpful Content guidance** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends content provide clear sourcing and evidence of expertise; cited authoritative sources are part of demonstrating reliable, accurate information.
3. **Google — Search Quality Rater Guidelines** (publicly published by Google). The guidelines instruct human raters to evaluate whether pages cite trustworthy sources, supporting the principle that outbound link quality contributes to perceived page quality.

### Step 3 — Evidence weight rationale
Practitioner consensus (Backlinko) plus indirect Google endorsement via Helpful Content guidance and Quality Rater Guidelines. Google does not name "outbound link quality" as a specific algorithmic ranking factor, but the underlying principle (sourcing and citations as quality signals) is endorsed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** external link list per page (anchor text, target URL).
- **Domain quality lookup: DataForSEO Backlinks Summary API** for the linked domain's domain rating.
- **Theme analysis: our own.** Compare the linked domain's content topic to the source page topic via embedding similarity or keyword overlap.

### Step 5 — Verification
DataForSEO returns external link details in full-site audit. Domain rating lookup is a separate API call per linked domain. Theme analysis requires content access to the linked domain or use of DataForSEO's domain-level metadata. Granularity required: per outbound link with quality tier and theme match boolean. Granularity delivered: by composition.

### Step 6 — Cost
External link list bundled with page audit. Per-domain authority lookup approximately $0.001–$0.002 per linked domain (DataForSEO Backlinks Summary). For a typical site of 200 pages with ~10 external links averaging 30 unique domains, monthly cost approximately £2–£5.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P3-21 (linking domain topical relevance) — same concept applied to inbound backlinks from external sites.
- **Related to:** P4-10 (external citation density) — focuses on volume of citations rather than their quality.

---

## P1-27 — Outbound link count

**Pillar:** On-Page SEO
**Evidence weight:** Contested

### Step 1 — Definition
The number of unique outbound external links on the page. Practitioner concern is "too few" (suggests isolation) or "too many" (suggests dilution).

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #41 (Number of Outbound Links) and Factor #60 (Too Many Outbound Links) cite both ends as concerns.
2. **Google Search Central — John Mueller statements** (multiple official communications including Search Off The Record podcast and Twitter/X). Google has stated outbound links do not dilute PageRank in the way originally theorised by some practitioners; the concern over outbound link count diluting authority is not supported by Google.
3. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google). Recommends linking to authoritative sources where appropriate, treating outbound links as a positive signal when relevant rather than something to minimise.

### Step 3 — Evidence weight rationale
Backlinko cites both ends (too few and too many) as concerns. Google has explicitly stated outbound link count does not dilute PageRank. The two positions partially contradict. Qualifies as **Contested**: outbound link count may matter for perceived content quality (sourcing) but does not algorithmically dilute authority in the way some practitioner sources claim.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `external_links_count` per page.

### Step 5 — Verification
DataForSEO confirms `external_links_count` is returned per page. Granularity required: per-page integer count. Granularity delivered: matches.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Related to:** P1-26 (quality of outbound links matters more than count, per Google's stance).

---

## P1-28 — Image alt text coverage

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The percentage of `<img>` elements on the page that have a non-empty `alt` attribute providing a descriptive text alternative for the image's content.

### Step 2 — Citations
1. **Google Search Central — Image SEO best practices** (https://developers.google.com/search/docs/appearance/google-images, Google, accessed May 2026). Google explicitly recommends descriptive alt attributes on images, stating alt text helps Google understand image content and improves accessibility.
2. **Web Content Accessibility Guidelines (WCAG) 2.2 — Success Criterion 1.1.1 Non-text Content** (https://www.w3.org/WAI/WCAG22/quickref/#non-text-content, W3C, accessed May 2026). Requires text alternatives for non-text content including images.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #89 (Alt Tag for Image Links).
4. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `checks.no_image_alt` boolean indicator and `images_count`.

### Step 3 — Evidence weight rationale
Google explicitly recommends alt text. WCAG requires it for accessibility conformance. Backlinko corroborates. Universal endorsement, no source disputes the practice. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** `checks.no_image_alt` boolean and `images_count` aggregate.
- **Coverage percentage: composition.** Per-image alt detection requires either DataForSEO content_parsing or our own HTML parsing for full granularity.

### Step 5 — Verification
DataForSEO confirms image-level alt detection. Granularity required: per-page percentage of images with alt text plus list of images missing alt. Granularity delivered: by composition. **Verification flag:** confirm whether Instant Pages returns full per-image detail or aggregated only — content_parsing endpoint may be needed for complete per-image visibility.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-discipline:** WCAG accessibility is the primary justification beyond SEO benefit; treat image alt as both an accessibility and SEO measure.

---

## P1-29 — Image filename relevance

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
Image filenames are descriptive of the image's subject (e.g., `winter-boots-mens-leather.jpg`) rather than generic camera-default names (e.g., `IMG_0042.jpg`) or random strings (UUIDs, timestamps). Filenames help search engines understand image content as one input alongside alt text.

### Step 2 — Citations
1. **Google Search Central — Image SEO best practices** (https://developers.google.com/search/docs/appearance/google-images, Google, accessed May 2026). Google explicitly states descriptive filenames provide clues about the image subject matter, recommending meaningful filenames over auto-generated camera filenames.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #26 (Image Optimization) covers filename and alt text together.

### Step 3 — Evidence weight rationale
Google directly recommends descriptive filenames in its image SEO guidance. Backlinko corroborates. No reputable source disputes the practice. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: per-image URL extraction** from DataForSEO image details (parses the filename portion of the image URL).
- **Pattern logic: our own.** Detect generic camera prefixes (IMG_, DSC_), random-string filenames (UUIDs, timestamps), and missing keyword content.

### Step 5 — Verification
DataForSEO returns image URLs in full-site audit. Filename parsing is trivial. Granularity required: per-image filename quality boolean plus list of generic-filename outliers. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Companion to:** P1-28 (alt text); both contribute to image SEO. Practical recommendations usually package them together.

---

## P1-30 — Image dimensions and weight

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
Images served on the page are appropriately sized for their display dimensions, use modern efficient formats (WebP, AVIF) where supported, and are file-size optimised. Excessive image weight directly impacts page load performance and Core Web Vitals (especially LCP).

### Step 2 — Citations
1. **Google Search Central — Image SEO and Performance** (https://developers.google.com/search/docs/appearance/google-images, Google, accessed May 2026). Google recommends serving appropriately sized images and modern formats to improve page load.
2. **web.dev — Optimise images** (https://web.dev/articles/fast/, Google). Provides specific guidance on image format, sizing, lazy loading, and weight optimisation as Core Web Vitals improvements.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #20 (Page Loading Speed via HTML) and Factor #83 (Core Web Vitals) reference image weight as part of speed measurement.
4. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `images_count` and `images_size` aggregate per page.

### Step 3 — Evidence weight rationale
Google explicitly recommends image optimisation and treats it as part of Core Web Vitals (a confirmed ranking factor). Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** `images_count` and `images_size` aggregate.
- **Per-image detail: DataForSEO image details endpoint or our HTML parsing** for individual image dimensions, format, and weight.

### Step 5 — Verification
DataForSEO confirms aggregate image metrics. Per-image detail extraction may require content_parsing endpoint or our own analysis. Granularity required: per-image dimensions/weight/format. Granularity delivered: aggregate by default; per-image by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P2-08 (LCP), P2-23 (page weight), P2-24 (image format efficiency). Image optimisation directly impacts technical SEO performance metrics. The on-page variable focuses on content optimisation; the technical pillar focuses on the same data through a performance lens.

---

## P1-31 — Open Graph tags

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The page declares Open Graph protocol metadata in its HTML head: at minimum og:title, og:description, og:image, og:type, og:url. These tags control how the page appears when shared on social platforms (Facebook, LinkedIn, Slack previews, iMessage, etc.) and are increasingly used by search engines for snippet enrichment.

### Step 1.5 — Evaluation rules
A page passes Open Graph tag correctness when ALL of the following rules pass:

1. **Five core properties present.** `og:title`, `og:description`, `og:image`, `og:type`, and `og:url` are all declared in the head with non-empty values.
2. **`og:image` resolves to a live image.** The `og:image` URL returns 200 with a valid image content type; image meets minimum dimensions (Facebook recommends ≥1200×630, LinkedIn ≥1200×627).
3. **`og:url` is absolute and self-referential.** The `og:url` is the full canonical URL of the page (matches the canonical tag from P1-20).
4. **`og:type` matches content category.** `og:type` is one of the standard OG types (`website`, `article`, `video.movie`, `book`, `profile`, etc.) matching the page's actual nature.
5. **`og:title` is meaningful and reasonably sized.** `og:title` is descriptive and typically 40–70 characters (longer titles truncate in social previews).
6. **`og:description` is meaningful and reasonably sized.** `og:description` is a summary of 60–200 characters; not a duplicate of `og:title`.
7. **Article-specific properties populated where applicable.** Articles include `og:type=article` plus `article:published_time`, `article:author`, and `article:section` where the data exists.
8. **No conflicting Open Graph declarations.** Each property is declared exactly once; no template or plugin produces duplicate `og:title`/`og:description` tags.

A page passing all 8 rules has correct Open Graph configuration.

### Step 2 — Citations
1. **Open Graph Protocol specification** (https://ogp.me, accessed May 2026). The canonical specification originally introduced by Facebook in 2010 and now adopted by virtually all major social platforms.
2. **Google Search Central — Article structured data** (https://developers.google.com/search/docs/appearance/structured-data/article, Google, accessed May 2026). Google references Open Graph properties as supplementary signals for some structured data implementations.
3. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Returns Open Graph tags as part of the `social_media_tags` field.

### Step 3 — Evidence weight rationale
Universal practitioner standard for social sharing; Google treats Open Graph as supplementary metadata. The presence of Open Graph tags is uncontested as a recommended practice but its direct ranking effect is limited (the primary value is social CTR, not search ranking). Qualifies as **Probable**: well-supported as a practice, indirectly impacts SEO via shared traffic patterns and snippet display.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** `social_media_tags` field returns Open Graph tags per page.

### Step 5 — Verification
DataForSEO documentation confirms social_media_tags field returns Open Graph and Twitter tags. Granularity required: per-page presence-and-content of og:title, og:description, og:image, og:type, og:url. Granularity delivered: matches.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Companion to:** P1-32 (Twitter Cards) — Twitter respects Open Graph as fallback, so Open Graph is the primary social meta standard.
- **Cross-pillar:** P4-12 (schema for content types) — Open Graph and Article schema overlap conceptually but are distinct standards; both should be present on content pages.

---

## P1-32 — Twitter Card tags

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The page declares Twitter Card metadata (twitter:card, twitter:title, twitter:description, twitter:image) in its HTML head. Twitter (now X) primarily falls back to Open Graph tags when Twitter-specific tags are absent, so Twitter Cards are supplementary to Open Graph.

### Step 1.5 — Evaluation rules
A page passes Twitter Card correctness when ALL of the following rules pass (NB: this rule set assumes the site has chosen to declare Twitter-specific tags; relying solely on Open Graph fallback is also acceptable per P1-31):

1. **`twitter:card` declared.** A `twitter:card` meta tag declares the card type (`summary`, `summary_large_image`, `app`, `player`).
2. **Card type matches content.** `summary_large_image` for content with a hero image; `summary` for short-form content; `player` for media; `app` for app-promotion pages.
3. **Title, description, image declared OR Open Graph fallback complete.** Either `twitter:title`, `twitter:description`, `twitter:image` are populated, or Open Graph (P1-31) is complete enough that Twitter falls back cleanly.
4. **`twitter:image` resolves to live image with correct dimensions.** Image meets the card type's dimension requirements (`summary_large_image` requires ≥300×157, recommended 1200×675).
5. **`twitter:site` populated where the site has an X account.** `twitter:site` declares the site's official X handle; supports proper attribution in shared previews.
6. **No conflicting declarations between Twitter and Open Graph.** When both are declared, values agree (Twitter takes precedence; conflicts produce inconsistent previews depending on platform).

A page passing all 6 rules has correct Twitter Card configuration.

### Step 2 — Citations
1. **X (Twitter) developer documentation — Cards** (https://developer.twitter.com/en/docs/twitter-for-websites/cards/overview/abouts-cards, X Corp, accessed May 2026). Defines Twitter Card metadata format and explicitly lists Open Graph fallback behaviour: Twitter respects og:title, og:description, og:image when Twitter-specific tags are missing.
2. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Returns Twitter Card tags via the `social_media_tags` field.

### Step 3 — Evidence weight rationale
Twitter (X) explicitly supports both formats and uses Open Graph as fallback. Twitter Cards add limited value over a complete Open Graph implementation. Qualifies as **Probable**: useful for explicit Twitter customisation, redundant when Open Graph is comprehensive.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** `social_media_tags` field (returns both Open Graph and Twitter tags).

### Step 5 — Verification
DataForSEO confirms Twitter Card tags returned via social_media_tags. Granularity required: per-page presence of Twitter Card fields. Granularity delivered: matches.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-31 (Open Graph) being the primary social meta implementation.
- **Note:** Twitter Cards add value only where Twitter-specific behaviour is needed (e.g., card type customisation); otherwise treat OG as sufficient.

---

## P1-33 — Robots meta tag

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The page declares its indexability and link-following behaviour to crawlers via a `<meta name="robots">` tag in the HTML head. Directives include `index`/`noindex` (whether the page should be indexed) and `follow`/`nofollow` (whether links on the page should be followed for crawl), plus optional directives like `noarchive`, `nosnippet`, `max-snippet`, `max-image-preview`, `unavailable_after`.

### Step 1.5 — Evaluation rules
A page passes robots meta tag correctness when ALL of the following rules pass:

1. **Directive consistent with declared business intent.** Pages intended to be indexed do not have `noindex`; pages intentionally hidden (admin, thank-you, internal search results) have `noindex` declared.
2. **No accidental `noindex` on indexable pages.** No template or CMS default emits `noindex` on pages that should be indexed (a common bug after staging-to-production deploys).
3. **No conflict with `<meta name="robots">` and HTTP `X-Robots-Tag` header.** Both signals are checked; if both are set, they agree (Google honours the most restrictive, so `noindex` in either takes effect).
4. **No conflict with robots.txt.** A page declared `noindex` in meta is not also blocked by robots.txt (Google cannot crawl a robots.txt-blocked page to read the meta directive, so the meta directive is ignored — the result is unintended indexation in some cases).
5. **Directive syntax is valid.** Directives use canonical forms (`noindex`, not `no-index`; `nofollow`, not `nofollow,`); multiple directives separated by commas; user-agent-specific directives use the correct format.
6. **Optional directives only declared when needed.** `noarchive`, `nosnippet`, `max-snippet:N`, `max-image-preview:standard|large` are only declared when there is an explicit reason; not added speculatively.
7. **`unavailable_after` only used for content with a real expiry.** `unavailable_after:RFC-850-date` is only declared on time-bound content (event pages after the event, expired offers); not as a generic SEO tweak.
8. **Outcome consistent with GSC URL Inspection.** GSC reports the page as "Submitted and indexed" when intent is to index; "Excluded by 'noindex' tag" when intent is to exclude.

A page passing all 8 rules has correct robots meta configuration.

### Step 2 — Citations
1. **Google Search Central — Robots Meta Tag** (https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag, Google, accessed May 2026). Authoritative documentation specifying supported directives and how Google honours each.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Robots-meta-related considerations appear under Page-Level and Site-Level Factors.
3. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Returns meta tags including robots directives via content extraction.

### Step 3 — Evidence weight rationale
Google authoritatively documents robots meta behaviour. The tag directly controls indexation, which is a binary prerequisite for ranking at all. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO content_parsing endpoint or our own HTML head parsing** for the `<meta name="robots">` value.
- **Outcome verification: Google Search Console URL Inspection API** reports actual indexation status (the result Google honours after processing all directives, including HTTP X-Robots-Tag headers).

### Step 5 — Verification
The Instant Pages endpoint may not directly expose robots meta as a top-level field. **Verification flag:** live testing needed to confirm which DataForSEO endpoint returns the cleanest robots meta value, with HTML head parsing as fallback. Granularity required: per-page directives list. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P2-04 (indexation status). Robots meta is the page-level declaration of intent; indexation status is the outcome Google honours after all signals are processed. (P2-06 index tier was removed from the taxonomy in May 2026 as externally unmeasurable.)

---

## P1-34 — Content depth / word count (also covers leaked `numTokens`)

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The page contains sufficient word count and topical coverage to meaningfully address the query intent. Measured as page word count benchmarked against competitor pages ranking for the same query, rather than against a fixed numeric threshold. This variable also stands in for the leaked Google feature `numTokens` (token count after Google's tokenisation pipeline) — Google's exact tokeniser is not disclosed, so word count plus our own standard tokenisation serve as the measurable proxy; treating `numTokens` as an independent variable produced redundant tracking with no separable signal.

### Step 2 — Citations
1. **Google Search Central — Helpful Content guidance** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends content provide substantial, complete, comprehensive descriptions of the topic and offer insightful analysis beyond obvious observations. Google does not specify minimum word count, but explicitly endorses depth and comprehensiveness.
2. **Google Search Central — John Mueller statements** (multiple official communications). Google has explicitly stated word count itself is not a ranking factor; only content sufficiency for the query intent matters.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #15 (Content Length) and Factor #19 (Page Covers Topic In-Depth) cite practitioner research showing correlation between longer content and better rankings for many query types.
4. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `plain_text_word_count` directly per page.

### Step 3 — Evidence weight rationale
Google endorses depth and comprehensiveness but explicitly denies word count as an algorithmic factor. Practitioner research correlates word count with rankings, particularly for informational queries. The honest interpretation: word count is a proxy for topical coverage, not a direct factor. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `plain_text_word_count` per page.
- **Comparative analysis: our own.** Compare each page's word count to the average of pages ranking for the same target query (sourced via DataForSEO SERP API).

### Step 5 — Verification
DataForSEO confirms word count returned per page. Comparative benchmark requires SERP fetches (additional cost). Granularity required: per-page integer plus query-relative percentile. Granularity delivered: by composition.

### Step 6 — Cost
Bundled for the per-page count. Comparative benchmarking adds DataForSEO SERP API cost (~$0.001 per query) when fetching competitor data.

### Step 7 — Dependencies and cross-references
- **Subsumes:** P1-40 (`numTokens` leaked feature — collapsed into this entry as proxy in May 2026 dedup audit).
- **Depends on:** P0-13 (target keyword) and SERP data for the keyword (P0-12 or P3-related).
- **Cross-pillar:** P4-02 (content depth vs SERP competitor average) — same concept reframed at content operations level.

---

## P1-35 — TF-IDF / keyword prominence (approximates leaked `avgTermWeight`)

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The frequency of relevant keyword terms on the page weighted by their inverse document frequency across the corpus, indicating which terms the page emphasises relative to their general rarity. Prominence reflects whether key terms appear in important locations (title, headings, opening paragraph). This variable is also the operational approximation of the leaked Google feature `avgTermWeight` — Google's exact term-weighting computation is not disclosed, so our TF-IDF or BM25 calculation stands in as the measurable proxy.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #14 (TF-IDF) and Factor #30 (Keyword Prominence) reference these as long-recognised information-retrieval signals practitioners use to evaluate keyword relevance.
2. **Information retrieval academic literature** — TF-IDF is a foundational concept in search engine ranking algorithms originally documented in IR textbooks (Salton et al., 1970s onwards). While Google has moved beyond simple TF-IDF, the principles inform modern term weighting.
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leak references `avgTermWeight` and related term-importance signals, confirming Google's ranking infrastructure uses term-weighting computations on indexed pages.

### Step 3 — Evidence weight rationale
TF-IDF is a foundational information-retrieval method that underpins (with refinements) modern ranking algorithms. Google has not directly endorsed TF-IDF as a specific ranking signal but the leaked features confirm related computations exist. Practitioners cite it as a useful audit lens. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO content extraction** (page text via plain_text or content_parsing).
- **Computation: our own.** Compute TF-IDF scores for the page text against a corpus of competing pages or a general English corpus.

### Step 5 — Verification
DataForSEO returns plain text content. TF-IDF computation is standard (scikit-learn, gensim, or our own implementation). Granularity required: per-page top-N weighted terms with prominence flags. Granularity delivered: by composition.

### Step 6 — Cost
Bundled (DataForSEO) plus computational (our own TF-IDF).

### Step 7 — Dependencies and cross-references
- **Subsumes:** P1-39 (`avgTermWeight` leaked feature — collapsed into this entry as proxy in May 2026 dedup audit).
- **Related to:** P1-36 (semantic coverage) — TF-IDF identifies emphasised terms; semantic coverage extends to related concepts.

---

## P1-36 — Semantic keyword and entity coverage

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The page's content covers semantically related terms, synonyms, named entities, and topical concepts associated with the target keyword, not just exact-match keyword instances. Reflects whether the page demonstrates topical depth rather than keyword stuffing.

### Step 2 — Citations
1. **Google Search Central — Hummingbird Update reference and Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Google's natural language processing capabilities (Hummingbird, BERT, MUM) understand semantic relationships and topical depth, not just exact keyword matches. Helpful Content guidance recommends comprehensive topic coverage.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #17 (Latent Semantic Indexing Keywords in Content) and Factor #23 (Google Hummingbird) reference semantic coverage.
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Leaked embedding features (`pageEmbedding`, `siteEmbedding`) confirm Google computes semantic representations of pages and sites.

### Step 3 — Evidence weight rationale
Google's NLP advances (Hummingbird, BERT) explicitly evaluate semantic relationships. The leaked embedding features confirm semantic coverage is part of Google's evaluation. The specific term "LSI" is technically inaccurate (LSI is a 1980s technique Google does not literally use), but the underlying principle of semantic understanding is well-supported. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO content extraction** (page text).
- **Entity extraction: LLM-driven NER via OpenAI/Anthropic API or self-hosted spaCy** for identifying named entities and topical concepts.
- **Coverage analysis: our own.** Compare extracted entities against expected topic cluster (P0-08) and target keyword's known related entities.

### Step 5 — Verification
DataForSEO returns plain text. Entity extraction is standard (spaCy, GPT-4 NER prompt, or LiteLLM-mediated). Granularity required: per-page entity coverage list plus expected-vs-found delta. Granularity delivered: by composition.

### Step 6 — Cost
Bundled (DataForSEO) plus per-page LLM/NER cost. Approximately $0.001–$0.005 per page if using LLM for entity extraction; free if self-hosted spaCy.

### Step 7 — Dependencies and cross-references
- **Depends on:** P0-08 (topic cluster definition), P0-13 (target keyword).
- **Related to:** P1-37 (entity match score) — narrower variant focusing on entity match strictness; P1-35 (TF-IDF) — overlapping but TF-IDF is term-frequency-based, this is meaning-based.

---

## P1-37 — Entity match score

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The degree to which the page's named entities (people, places, brands, organisations, products, concepts) match the entities expected for the target query. Calculated as a similarity score between extracted page entities and the entity set associated with the query.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #22 (Entity Match) explicitly names this as a practitioner-recognised factor.
2. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leak references entity-related processing throughout the ranking infrastructure (the `siteEmbedding`, `pageEmbedding`, and entity-related demotions all imply entity-based evaluation).
3. **Google Knowledge Graph documentation** (https://developers.google.com/knowledge-graph, Google, accessed May 2026). Google maintains a Knowledge Graph of entities and uses it to interpret queries and pages; entity match is part of that interpretation.

### Step 3 — Evidence weight rationale
Google's Knowledge Graph and natural language understanding rely on entities. Leaked features support entity-based evaluation. Backlinko corroborates. Specific operational measurement is our composition. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: extracted entities from page content** (via LLM NER or spaCy on DataForSEO plain text).
- **Expected entities: derived from target query** via Knowledge Graph API lookup or LLM-driven query analysis.
- **Match scoring: our own** comparison between expected and found entity sets.

### Step 5 — Verification
Entity extraction and matching are standard NLP tasks. Knowledge Graph API access is free with rate limits. Granularity required: per-page entity match score (0–1) plus list of missing/extra entities. Granularity delivered: by composition.

### Step 6 — Cost
LLM extraction cost: $0.001–$0.005 per page. Knowledge Graph API: free.

### Step 7 — Dependencies and cross-references
- **Depends on:** P0-13 (target keyword), entity extraction infrastructure.
- **Related to:** P1-36 (semantic coverage) — broader; P0-09 (page embedding similarity) — uses embeddings, related approach.

---

## P1-38 — Original content score

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The degree to which the page's content is original, unique, and substantively different from other content on the web (and within the site). Distinguishes pages with genuinely original information, analysis, or research from pages that aggregate or rephrase existing content.

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leak names a feature `OriginalContentScore`, confirming Google computes a per-page originality measure as part of ranking infrastructure.
2. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Explicitly recommends original information, reporting, research, or analysis; specifically calls out content that copies or rewrites other sources as low-quality.
3. **Google Search Central — Spam Policies** (https://developers.google.com/search/docs/essentials/spam-policies, Google, accessed May 2026). Treats scraped or auto-generated content as spam.
4. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #35 (Syndicated Content) and Factor #66 (Content Provides Value and Unique Insights).

### Step 3 — Evidence weight rationale
Google explicitly recommends original content and treats non-original content as a quality concern. The leaked feature confirms Google computes an originality score. Practitioner consensus aligns. Qualifies as **Probable** — the principle is clearly endorsed but our reproduction of Google's exact `OriginalContentScore` is a proxy.

### Step 4 — Data source(s)
- **Primary: composition** combining several signals.
- **Cross-site duplication: DataForSEO** `duplicate_content` boolean for site-internal; external duplication detection requires search-on-content (Google search for distinctive phrases) or services like Copyscape API.
- **Originality score: our own** weighted aggregation of duplication checks plus content uniqueness signals (proprietary terminology, original data, named methodology).

### Step 5 — Verification
DataForSEO confirms in-site duplication detection. External duplication detection requires extra tooling. Granularity required: per-page originality score (0–1). Granularity delivered: by composition. **Caveat:** the score is our approximation of Google's `OriginalContentScore`, not the actual leaked metric.

### Step 6 — Cost
Bundled for in-site detection. Cross-web detection adds cost (Copyscape API approximately $0.05 per page or self-hosted phrase search).

### Step 7 — Dependencies and cross-references
- **Scope of this variable:** approximation of leaked `OriginalContentScore` — per-page originality score combining in-site duplication (DataForSEO) and external-web duplication (composition).
- **Hierarchy:** **P1-38 (this) → leak-feature approximation, per-page numerical originality score**. P1-46 → "is this page near-duplicate of another page on the same site" (in-site duplication audit, narrower). P4-07 → editorial-level originality and substance evaluation against external web (broader, applies multi-rule Step 1.5). P4-21 → mass-production pattern detection at site scale (different concern: pattern across many pages, not per-page originality).
- **Cross-pillar:** P1-46, P4-07, P4-21.

---

## P1-39 — Average term weight *(removed — see P1-35)*

This variable was removed in the May 2026 deduplication audit. The leaked Google feature `avgTermWeight` is operationally approximated by **P1-35 — TF-IDF / keyword prominence**, which is the canonical entry. P1-35 records `avgTermWeight` as the leaked counterpart it approximates; treating both as separate variables produced a redundant Speculative entry with no independent measurement path.

---

## P1-40 — Token count *(removed — see P1-34)*

This variable was removed in the May 2026 deduplication audit. The leaked Google feature `numTokens` measures substantially the same thing as **P1-34 — content depth / word count**, since Google's exact tokeniser is not disclosed and our tokenisation is itself an approximation. P1-34 records `numTokens` as the leaked counterpart it approximates.

---

## P1-41 — Content freshness — byline date

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The date prominently displayed on the page — typically as a publishing or last-updated date in the byline area — as detected by Google's `bylineDate` feature. Distinct from `syntacticDate` (extracted from URL or other structural signals) and `semanticDate` (inferred from content cues).

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leak names three distinct date features: `bylineDate`, `syntacticDate`, and `semanticDate`. Mike King's analysis identifies these as the multiple date signals Google uses to determine content freshness.
2. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends content provide updated, current information, with explicit emphasis on freshness as a quality signal for many query types.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #27 (Content Recency).
4. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `last_modified` object with `header`, `sitemap`, and `meta_tag` sub-fields capturing dates from various sources.

### Step 3 — Evidence weight rationale
Google's leaked features confirm dedicated date detection mechanisms across three signals. Google's Helpful Content guidance endorses freshness. Backlinko corroborates. The specific `bylineDate` feature exists in Google's infrastructure per leak; our approximation requires byline detection on the page. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** `last_modified.meta_tag` and content extraction for displayed byline dates.
- **Pattern logic: our own.** Detect byline-style date displays in page content (e.g., "Published: 12 May 2026", "Last updated: ..."), supplement with structured data (Article schema's `datePublished`, `dateModified`).

### Step 5 — Verification
DataForSEO returns last_modified meta tag dates. Byline detection in content requires text pattern matching. Schema.org Article date fields are accessible if present (P1-21). Granularity required: per-page date value plus source tier (schema, byline display, meta tag, sitemap). Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Companion to:** P1-42 (syntactic date), P1-43 (semantic date) — three distinct date signals from the same leaked feature group.
- **Cross-pillar:** P4-08 (content freshness updates at content operations level).

---

## P1-42 — Content freshness — syntactic date

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The date extracted from URL structure or other syntactic signals on the page (e.g., dates embedded in URL slugs like `/blog/2024/05/post-name`, dates in HTTP Last-Modified headers, sitemap last_mod entries). Distinct from byline date (visible content) and semantic date (content-inferred).

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leak names `syntacticDate` as a distinct date feature alongside `bylineDate` and `semanticDate`. Mike King's analysis interprets this as the URL or HTTP-derived date signal Google extracts as one input for freshness evaluation.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #52 (URL Path) references URL components including dates as practitioner-recognised signal patterns.
3. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `last_modified.header` (HTTP Last-Modified) and `last_modified.sitemap` (sitemap entry date) directly per page.

### Step 3 — Evidence weight rationale
The leaked feature `syntacticDate` confirms Google extracts dates from structural signals separately from visible content. Backlinko and Google's own documentation reference URL and HTTP-header dates. The specific operational weight is not disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** `last_modified.header` and `last_modified.sitemap` for HTTP and sitemap dates.
- **URL date extraction: our own.** Pattern-match common date formats in URL slugs (YYYY/MM/, YYYY-MM-DD, etc.).

### Step 5 — Verification
DataForSEO confirms HTTP and sitemap date fields. URL pattern detection is straightforward. Granularity required: per-page list of detected syntactic dates with their source. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Companion to:** P1-41 (byline date), P1-43 (semantic date) — three signals triangulated together for freshness assessment.

---

## P1-43 — Content freshness — semantic date

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The date inferred from page content via natural language processing — references like "as of January 2026", "last week's announcement", "this year's report" allow Google to infer when the content is implicitly timestamped, even when no explicit date is visible.

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leak names `semanticDate` as a distinct feature, completing the trio with `bylineDate` and `syntacticDate`. Mike King's analysis interprets this as Google's NLP-driven date inference from content cues.
2. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends current information; the existence of a semantic date signal supports Google's evaluation of whether content is implicitly stale.

### Step 3 — Evidence weight rationale
The leaked feature confirms Google infers dates from content semantics. Helpful Content guidance supports the importance of currency. Specific operational weight is not disclosed; the variable is best treated as a freshness triangulation input. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO content extraction** (page text).
- **NLP date inference: our own** via LLM prompt or regex patterns for relative date phrases ("today", "last week", "as of [month]"), plus absolute date parsing from text.

### Step 5 — Verification
DataForSEO returns plain text. NLP date inference is composition. Granularity required: per-page inferred date plus confidence score. Granularity delivered: by composition.

### Step 6 — Cost
Bundled (DataForSEO) plus per-page LLM cost if used (~$0.001 per page).

### Step 7 — Dependencies and cross-references
- **Companion to:** P1-41 (byline date), P1-42 (syntactic date) — when all three signals agree on a date, freshness confidence is high; when they disagree, freshness is contested for that page.

---

## P1-44 — Content update magnitude

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The size and significance of changes made to a page between historical snapshots. Distinguishes minor edits (typo fixes, small word swaps) from substantial revisions (sections rewritten, new examples added, statistics refreshed).

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #28 (Magnitude of Content Updates) cites this as a practitioner-recognised factor; Google has been observed to favour pages with substantive updates over those with cosmetic changes.
2. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends meaningful content updates over surface-level revisions; explicitly cautions against republishing with token edits to game freshness signals.
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). NavBoost-related click signals capture per-version performance, suggesting Google compares historical page states.

### Step 3 — Evidence weight rationale
Practitioner consensus, indirect Google support via Helpful Content guidance, no Tier A direct endorsement of a specific operational measure. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition over historical DataForSEO crawl snapshots.**
- **Diff computation: our own.** Maintain content snapshots per page across crawls; compute diff between consecutive versions (text similarity via cosine, character/word edit distance, or semantic embedding diff).
- **Requires: regular re-crawling and snapshot storage.**

### Step 5 — Verification
DataForSEO returns content per crawl. Snapshot storage is our own (database table per page-version). Diff computation is standard. Granularity required: per-page magnitude score per update event. Granularity delivered: by composition. **Caveat:** requires accumulated history, so this variable is meaningless until at least two crawls have occurred.

### Step 6 — Cost
Bundled per crawl. Snapshot storage cost is our database (negligible at pilot scale).

### Step 7 — Dependencies and cross-references
- **Depends on:** historical crawl history (not available at first crawl).
- **Companion to:** P1-45 (historical update cadence) — magnitude and frequency together describe page maintenance pattern.
- **Cross-pillar:** P4-08 (content freshness updates) — same concept at content operations level.

---

## P1-45 — Historical update cadence

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The frequency with which a page has been meaningfully updated over time — measured as the number of substantive update events per quarter or per year, where a substantive update is one passing the magnitude threshold from P1-44.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #29 (Historical Page Updates).
2. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends a content update workflow that maintains pages over time; Helpful Content explicitly favours content with sustained maintenance over abandoned content.
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Freshness signals include date-of-last-significant-update inputs; Google's QualityBoost and FreshnessTwiddler systems use such signals for ranking adjustments.

### Step 3 — Evidence weight rationale
Practitioner consensus plus indirect Google support via Helpful Content. The leaked freshness systems confirm Google tracks update history. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition over DataForSEO crawl history.**
- **Tracking: our own.** Record update events (passing the P1-44 magnitude threshold) per page; aggregate frequency.

### Step 5 — Verification
Requires accumulated crawl history. Granularity required: per-page update events per period. Granularity delivered: by composition once history exists. **Caveat:** like P1-44, meaningless at first crawl; only useful after several months of accumulated data.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-44 (magnitude threshold defines what counts as an "update"), accumulated crawl history.
- **Cross-pillar:** P4-01 (publishing cadence) — same concept at site level vs page level.

---

## P1-46 — Duplicate content within site

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
Pages on the same site contain substantially the same content as other pages on the same site. Includes exact duplicates (identical content), near-duplicates (mostly identical with minor variation), and section-level duplicates (large blocks of repeated content across pages).

### Step 2 — Citations
1. **Google Search Central — Consolidate Duplicate URLs (Canonicalization)** (https://developers.google.com/search/docs/crawling-indexing/canonicalization, Google, accessed May 2026). Google addresses duplicate content through canonicalisation rather than penalty; pages with same content compete for the same ranking slot, and Google picks one canonical version. Duplicate content within a site is treated as an indexation-efficiency concern.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #24 (Duplicate Content).
3. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `duplicate_content` boolean, `duplicate_title` boolean, `duplicate_description` boolean, and `duplicate_meta_tags` array.

### Step 3 — Evidence weight rationale
Google explicitly documents duplicate content handling in primary documentation. DataForSEO tooling treats it as a measurable concern. Backlinko corroborates. The Consensus is on the existence of the issue and its handling, not on penalty (Google does not algorithmically penalise duplicate content beyond canonical selection). Qualifies as **Consensus** for the variable's relevance, with the framing that duplicates cause indexation conflict rather than penalty.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** `duplicate_content`, `duplicate_title`, `duplicate_description` booleans per page.
- **Cross-page similarity: our own** content embedding similarity scoring across the site for near-duplicate detection.

### Step 5 — Verification
DataForSEO confirms boolean duplicate flags. Near-duplicate detection (similarity above some threshold but not exact) requires our own embedding-based logic. Granularity required: per-page duplicate type (exact / near / partial / none) plus list of duplicate counterparts. Granularity delivered: by composition.

### Step 6 — Cost
Bundled (DataForSEO) plus computational (own similarity scoring). Embedding generation may require LLM/local model (~$0.0001 per embedding via OpenAI text-embedding-3-small) or local sentence-transformers (free).

### Step 7 — Dependencies and cross-references
- **Scope of this variable:** in-site duplicate detection only — flags pages within the same site that contain substantially the same content as another page on that site. Output drives canonicalisation/consolidation recommendations.
- **Hierarchy:** P1-38 → per-page originality score (leak-feature approximation, considers both in-site and external duplication). **P1-46 (this) → in-site duplicate detection** (the narrower view focused on intra-site competition). P2-43 → site-level URL infrastructure that prevents duplicate URLs from arising (different concern: technical canonicalisation). P4-07 → editorial-level originality vs external web. P4-21 → mass-production pattern detection.
- **Cross-pillar:** P1-20 (canonical tag — resolves duplicate-content competition), P2-43 (URL infrastructure prevents duplicates upstream), P0-09/P0-10 (page embedding similarity feeds the near-duplicate detection logic), P4-07.

---

## P1-47 — Breadcrumb navigation and BreadcrumbList schema

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The page displays a breadcrumb navigation trail showing its position in the site hierarchy (e.g., Home > Category > Subcategory > Page), and the same hierarchy is declared in BreadcrumbList structured data for Google to display as part of rich results.

### Step 1.5 — Evaluation rules
A page passes breadcrumb correctness when ALL of the following rules pass:

1. **Visible breadcrumb present.** A visible breadcrumb trail is rendered on the page (typically near the top of the content area).
2. **BreadcrumbList schema present.** A BreadcrumbList JSON-LD or microdata block is declared in the page.
3. **Visible and schema breadcrumbs match.** The text and URLs in the visible breadcrumb match the `name` and `item` values in the BreadcrumbList schema.
4. **Breadcrumb starts at homepage.** The first breadcrumb item is "Home" (or the site's homepage equivalent) linking to the root URL.
5. **Hierarchy reflects real site structure.** Each breadcrumb item links to a real page that is the parent in the site's information architecture (not a fabricated path).
6. **Final breadcrumb is the current page.** The last breadcrumb item represents the current page (typically not linked, or linked to itself).
7. **No skipped levels.** If the site has Home → Category → Subcategory → Page, the breadcrumb shows all four; not Home → Page directly when intermediate pages exist.
8. **Schema validates against schema.org BreadcrumbList.** All `position` integers are sequential starting at 1; all `item` URLs are absolute.

A page passing all 8 rules has correct breadcrumb configuration.

### Step 2 — Citations
1. **Google Search Central — Breadcrumb structured data** (https://developers.google.com/search/docs/appearance/structured-data/breadcrumb, Google, accessed May 2026). Google explicitly supports BreadcrumbList schema markup and uses it for the breadcrumb display in search results. Breadcrumb is one of the 26 supported structured data types.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #77 (Breadcrumb Navigation).
3. **WCAG 2.2 — Success Criterion 2.4.8 Location** (https://www.w3.org/WAI/WCAG22/quickref/, W3C, accessed May 2026). Breadcrumbs are a recommended accessibility feature for orientation within site hierarchy.
4. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Returns navigation structure and structured data via content_parsing.

### Step 3 — Evidence weight rationale
Google explicitly supports breadcrumbs as a structured data type for rich results. Backlinko corroborates. WCAG endorses for accessibility. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Visible breadcrumb: DataForSEO content_parsing** to detect breadcrumb navigation patterns in HTML.
- **BreadcrumbList schema: DataForSEO** schema detection (`has_micromarkup` plus type extraction).

### Step 5 — Verification
DataForSEO confirms schema detection at the type level. Visible breadcrumb pattern detection requires content parsing. Granularity required: per-page presence of (a) visible breadcrumb, (b) BreadcrumbList schema, (c) match between the two. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P1-21 (schema type appropriateness), P1-22 (schema validity).

---

## P1-48 — Bullets and numbered lists

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The page uses HTML list elements (`<ul>`, `<ol>`) to structure enumerable content rather than presenting list-shaped information as flowing prose or non-semantic line breaks.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #58 (Bullets and Numbered Lists). Backlinko cites correlative observations that pages with proper list markup tend to capture featured snippets and ranks more reliably.
2. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends well-organised, scannable content; lists are a primary tool for organisation.
3. **WCAG 2.2 — Success Criterion 1.3.1 Info and Relationships** (https://www.w3.org/WAI/WCAG22/quickref/, W3C, accessed May 2026). Requires that information and relationships conveyed visually are also programmatically available; semantic list markup supports this.

### Step 3 — Evidence weight rationale
Practitioner research correlates list usage with featured snippet capture. Google endorses well-organised content. WCAG requires semantic markup for accessibility. No Tier A direct ranking-signal endorsement specifically for list elements. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO content_parsing** to detect `<ul>` and `<ol>` elements in page content.
- **Detection logic: our own.** Count list elements, list items, and identify long unstructured prose passages that could be reformatted as lists.

### Step 5 — Verification
DataForSEO content extraction returns HTML structure. List detection is straightforward. Granularity required: per-page list element count plus a heuristic for under-listed content. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P6-19 (extractable content format for AI search) — list-structured content is highly extractable for AI Overview citations.
- **Companion:** P1-49 (table of contents) — both are content-organisation patterns; lists are local, TOC is page-level.

---

## P1-49 — Table of contents

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The page provides a table of contents — a navigation block (typically near the top of the article) listing the page's section headings as jump links to in-page anchors. Enables both user navigation and Google's "jump to" snippet feature for long-form content.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #16 (Table of Contents). Backlinko cites observed correlation between TOC presence and Google's "jump to section" snippet display.
2. **Google Search Central — Featured Snippets and Site Links** (https://developers.google.com/search/docs/appearance/featured-snippets, Google, accessed May 2026). Google's documentation on rich snippets includes the "jump to" feature for long-form content with clear section structure; this is enabled by anchor IDs and discoverable section structure.
3. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends well-organised, scannable content with clear structure.

### Step 3 — Evidence weight rationale
Practitioner consensus, supported by Google's "jump to" snippet feature for content with proper anchor structure. No Tier A direct ranking-signal endorsement specifically for TOC elements. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO content_parsing** to detect TOC patterns (a list of internal page anchor links typically near the top of the content area).
- **Anchor ID detection: our own** scan of `<h2>`, `<h3>` elements for `id` attributes that match jump-link targets.

### Step 5 — Verification
DataForSEO content extraction returns HTML. TOC pattern detection is composition (a `<ul>` or `<ol>` containing only same-page anchor links near the top of the article body). Granularity required: per-page TOC presence plus completeness (does the TOC cover all major sections?). Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-15 (heading hierarchy correctness) — a meaningful TOC requires meaningful heading structure.
- **Cross-pillar:** P6-19 (extractable content format) — TOC structure is highly extractable for AI search citations.

---

## P1-50 — Multimedia presence

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The page contains diverse content formats beyond plain text — images, video, infographics, embedded media, interactive elements. Multimedia diversity contributes to engagement metrics and signals the page's investment in production quality.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #42 (Multimedia) cites multimedia presence as a practitioner-recognised quality signal correlating with rankings.
2. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends content with substantial production quality and demonstrates Google's interest in pages that meet user needs comprehensively, including via varied formats.
3. **Google Search Central — Image SEO and Video SEO best practices** (https://developers.google.com/search/docs/appearance/google-images and the related video documentation, Google). Google maintains specific best-practice guides for each multimedia format, indicating the platform recognises and rewards multimedia inclusion when properly implemented.
4. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `images_count` directly per page; embedded videos and other media require content-parsing detection.

### Step 3 — Evidence weight rationale
Practitioner consensus, supported by Google's investment in format-specific SEO guides (image, video). No specific Tier A direct ranking-signal endorsement for multimedia diversity itself, but the underlying principle (production quality, comprehensive user-need fulfilment) is endorsed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** `images_count` for image presence.
- **Video and embed detection: DataForSEO content_parsing** for `<video>`, `<iframe>` (YouTube, Vimeo, Loom), and embed patterns.
- **Multimedia diversity score: our own** aggregation across format types.

### Step 5 — Verification
DataForSEO confirms image count. Video and embed detection requires HTML parsing for known patterns. Granularity required: per-page format inventory plus diversity score. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Companion to:** P1-28, P1-29, P1-30 (image-specific variables).
- **Cross-pillar:** P4-11 (content format diversity at content operations level).

---

## P1-51 — Reading level / readability

**Pillar:** On-Page SEO
**Evidence weight:** Probable

### Step 1 — Definition
The reading-level complexity of the page's content as measured by standard readability indices (Flesch-Kincaid Grade Level, Coleman-Liau, Dale-Chall, SMOG, Automated Readability Index). The target reading level depends on intended audience — general consumer content typically targets grade 7–9; technical or academic content targets higher levels.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #46 (Reading Level) cites this as a practitioner-recognised factor, with clarification that the relationship between reading level and rankings depends on content type and audience.
2. **Google Search Central — John Mueller statements** (multiple official communications). Google has stated reading level is not a direct ranking factor, but content that matches the audience's expected complexity is more likely to rank well because it serves the audience.
3. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends clear writing free of stylistic errors; appropriate complexity for the audience is part of clarity.
4. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides five readability indices directly per page: `automated_readability_index`, `coleman_liau_readability_index`, `dale_chall_readability_index`, `flesch_kincaid_readability_index`, `smog_readability_index`.

### Step 3 — Evidence weight rationale
Google explicitly denies reading level as a direct ranking factor but endorses appropriate-complexity content. Practitioner research suggests correlation. The honest interpretation: reading level is a comprehension-and-engagement signal indirectly linked to rankings via behavioural metrics. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** five readability indices returned directly per page.
- **Audience-target threshold: our own.** Define expected reading level per `page_type` (e.g., consumer blog targets 7–9, technical documentation targets 11–13).

### Step 5 — Verification
DataForSEO confirms five readability indices returned per page. Comparison against target thresholds is composition logic. Granularity required: per-page indices plus appropriateness assessment for the page type. Granularity delivered: matches.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P4-23 (headlines accuracy and clarity at content operations level), P6-06 (easy-to-understand simplification for AI search visibility) — same readability principle relevant to AI citation eligibility.

---

## P1-52 — Grammar and spelling

**Pillar:** On-Page SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The page's content is free of grammatical errors and spelling mistakes. Errors signal low production quality and can affect both user trust and Google's quality assessment.

### Step 2 — Citations
1. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Explicitly recommends content "free of spelling and stylistic errors" as a quality criterion, listed among the markers Google looks for in evaluating helpful, people-first content.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #34 (Grammar and Spelling) is a long-recognised practitioner factor.
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Spelling-related signals appear in Google's content evaluation infrastructure.
4. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/). Provides `spell` object with `hunspell_language_code` and `misspelled` array per page, plus `checks.has_misspelling` boolean.

### Step 3 — Evidence weight rationale
Google explicitly mentions absence of spelling and stylistic errors as a quality marker in Helpful Content guidance. Backlinko corroborates. DataForSEO tooling provides direct measurement. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** `spell.misspelled` array (per-page list of misspelled words via Hunspell) and `checks.has_misspelling` boolean.
- **Grammar checking: supplementary** — DataForSEO does not check grammar. For grammar errors, supplement with LanguageTool API (free tier, ~5 requests per second) or LLM-based grammar review.

### Step 5 — Verification
DataForSEO confirms spell-check fields. Grammar checking via LanguageTool is straightforward but adds an API dependency. Granularity required: per-page error count plus list of specific errors. Granularity delivered: spelling matches; grammar requires composition.

### Step 6 — Cost
Spelling: bundled. Grammar: free at low volume (LanguageTool's free tier covers internal-tool scale) or ~$0.001 per page if using LLM. **Caveat:** LanguageTool's free tier may not be sufficient if we run grammar checks on every audit; pricing tier upgrade may be needed at SaaS scale.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P4-08 (content review and update workflow at content operations level) — recommendations from this variable feed into the content team's editorial quality control.

---

# Pillar 0 — Strategic Foundation

**Total candidates:** 18
**Status:** Complete (18 of 18 complete)

## Pillar 0 Index

| ID | Variable | Status | Weight |
|----|----------|--------|--------|
| P0-01 | Search intent classification per query | Complete | Consensus |
| P0-02 | Search volume per keyword (US monthly) | Complete | Consensus |
| P0-03 | Keyword difficulty score per keyword | Complete | Probable |
| P0-04 | Cost-per-click as commercial value indicator | Complete | Probable |
| P0-05 | SERP feature presence per query | Complete | Consensus |
| P0-06 | Buyer journey stage per keyword | Complete | Probable |
| P0-07 | Topical authority / site focus score | Complete | Probable |
| P0-08 | Site topical breadth | Complete | Probable |
| P0-09 | Site embedding similarity to query | Complete | Probable |
| P0-10 | Page embedding similarity to query | Complete | Probable |
| P0-11 | Topic cluster definition for the site | Complete | Probable |
| P0-12 | Pillar page / hub-and-spoke architecture | Complete | Probable |
| P0-13 | Keyword-to-page mapping | Complete | Probable |
| P0-14 | Content gap analysis vs ranking competitors | Complete | Probable |
| P0-15 | Brand search volume baseline and trajectory | Complete | Probable |
| P0-16 | Brand entity in Knowledge Graph | Complete | Consensus |
| P0-17 | YMYL classification of pages and topics | Complete | Consensus |
| P0-18 | Big-brand preference threshold detection | Complete | Probable |

---

## P0-01 — Search intent classification per query

**Pillar:** Strategic Foundation
**Evidence weight:** Consensus

### Step 1 — Definition
Each query the system tracks or evaluates is classified into one of four intent categories: **transactional** (immediate purchase or action intent), **commercial** (research preceding purchase), **informational** (knowledge-seeking), or **navigational** (looking for a specific site or brand). Intent governs how the system frames recommendations and which pages a query should target.

### Step 2 — Citations
1. **Google Search Quality Rater Guidelines** (publicly published by Google, latest version 2024). The guidelines explicitly instruct human raters to evaluate page-query match by intent type, listing similar intent categories (Know, Do, Go, Visit-in-person) as a foundational classification.
2. **Google — How Search Works** (https://www.google.com/search/howsearchworks/, Google, accessed May 2026). Google describes its ranking systems as understanding query intent and matching it to page intent.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Intent is referenced throughout (transactional, navigational, informational queries are listed as algorithm-relevant query types).
4. **Ahrefs / Semrush keyword tools** (https://ahrefs.com/blog/search-intent/, https://www.semrush.com/blog/search-intent/). Both major SEO platforms classify keywords by intent as a standard analytical lens; their methodology is published.

### Step 3 — Evidence weight rationale
Google's Quality Rater Guidelines explicitly endorse intent classification as the core matching framework. Industry tooling universally treats intent as a foundational dimension. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: composition.** Rule-based pattern matching against keyword text (transactional patterns: "buy", "price", "order"; commercial: "best", "review", "vs"; navigational: brand-name match, "login", "signup"; informational: default fallback).
- **Fallback: LLM-driven classification** for ambiguous queries that don't match clear patterns. Use a single-shot prompt requesting intent label.
- **Verification: DataForSEO SERP API** can be used to confirm — pages ranking for transactional queries tend to be product/category pages; for informational queries, blog posts or reference pages.

### Step 5 — Verification
Rule-based classification is deterministic and trivially testable. LLM fallback requires single-shot prompt with structured output. Granularity required: per-query single label plus confidence score. Granularity delivered: by composition.

### Step 6 — Cost
Rule-based classification: free. LLM fallback: ~$0.0001 per query at GPT-4o-mini rates. SERP verification: bundled into other DataForSEO SERP usage.

### Step 7 — Dependencies and cross-references
- **Foundational** — feeds intent_weight assignment in eventual scoring across many pillars.
- **Cross-references:** P0-06 (buyer journey stage) — derived in part from intent classification. P0-04 (CPC) — high CPC typically correlates with transactional intent.

---

## P0-02 — Search volume per keyword (US monthly)

**Pillar:** Strategic Foundation
**Evidence weight:** Consensus

### Step 1 — Definition
The estimated average monthly search volume for a keyword in the United States Google market, computed as a rolling 12-month average. Search volume indicates demand and prioritisation weight in keyword strategy.

### Step 2 — Citations
1. **Google Ads — Keyword Planner documentation** (https://ads.google.com/home/tools/keyword-planner/, Google, accessed May 2026). Google's own keyword volume tool, restricted to advertisers but the authoritative source.
2. **Ahrefs Keyword Explorer** (https://ahrefs.com/keywords-explorer/, accessed May 2026). Industry-leading third-party search volume estimates derived from clickstream data plus Google Ads data plus proprietary modelling.
3. **DataForSEO Keywords Data API** (https://docs.dataforseo.com/v3/keywords_data/, DataForSEO, accessed May 2026). Returns `search_volume` per keyword as a 12-month-average integer.
4. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Search volume informs query weighting in opportunity prioritisation.

### Step 3 — Evidence weight rationale
Search volume is a universally accepted measurement, foundational to all SEO strategy work. Google itself provides the data to advertisers. Multiple major third parties offer estimates. Qualifies as **Consensus**, with the caveat that all third-party figures are estimates rather than ground truth.

### Step 4 — Data source(s)
- **Primary: DataForSEO Keywords Data API** field `search_volume` per keyword.
- **Caveat:** all providers (Ahrefs, Semrush, DataForSEO) produce different numbers for the same keyword because each models the underlying data differently. Treat figures as directional, not exact.

### Step 5 — Verification
DataForSEO documentation confirms `search_volume` is returned as a 12-month rolling average integer. Granularity required: per-keyword integer for US monthly volume. Granularity delivered: matches.

### Step 6 — Cost
DataForSEO Keywords Data API: approximately $0.0001–$0.0002 per keyword. For a pilot site tracking 500 keywords, monthly cost approximately £1–£3.

### Step 7 — Dependencies and cross-references
- **Foundational** — feeds prioritisation in keyword-to-page mapping (P0-13) and opportunity scoring.
- **Companion to:** P0-03 (keyword difficulty) and P0-04 (CPC) — together these three define the basic value/competition profile of any keyword.

---

## P0-03 — Keyword difficulty score per keyword

**Pillar:** Strategic Foundation
**Evidence weight:** Probable

### Step 1 — Definition
An estimate of how difficult it is to rank in the top 10 of Google search results for a given keyword. Typically computed from the backlink profiles, domain authority, and content depth of currently ranking pages. Expressed as a 0–100 score with provider-specific scales and methodologies.

### Step 2 — Citations
1. **Ahrefs — Keyword Difficulty methodology** (https://ahrefs.com/blog/keyword-difficulty/, Ahrefs, accessed May 2026). Ahrefs publishes its KD methodology — based on the average number of referring domains to top 10 ranking pages.
2. **Moz — Keyword Difficulty score** (https://moz.com/learn/seo/keyword-difficulty/, Moz, accessed May 2026). Moz uses Page Authority and Domain Authority of ranking pages.
3. **Semrush — Keyword Difficulty** (https://www.semrush.com/kb/733-keyword-difficulty/, Semrush, accessed May 2026). Semrush's KD considers backlink profile plus on-page optimisation of ranking pages.
4. **DataForSEO Keywords Data API** (https://docs.dataforseo.com/v3/keywords_data/, DataForSEO, accessed May 2026). Returns `keyword_difficulty` per keyword on a 0–100 scale.

### Step 3 — Evidence weight rationale
The concept of keyword difficulty is universally accepted across major SEO providers. Methodology varies between providers, producing different absolute numbers for the same keyword. The directional signal (which keywords are harder to rank for) is consistent; the precise score is not. Qualifies as **Probable**: well-supported as a concept, methodology-dependent in measurement.

### Step 4 — Data source(s)
- **Primary: DataForSEO Keywords Data API** field `keyword_difficulty`.
- **Methodology disclosure: required for our user-facing language.** When the system surfaces difficulty in recommendations, it should be clear that the score is an estimate from DataForSEO's specific methodology, not an absolute truth.

### Step 5 — Verification
DataForSEO confirms `keyword_difficulty` returned per keyword. Granularity required: per-keyword 0–100 score. Granularity delivered: matches. **Caveat:** if at SaaS scale we ever need cross-provider validation, comparing DataForSEO's KD against Ahrefs or Semrush KD will produce different numbers; this is methodology variance, not data error.

### Step 6 — Cost
Bundled with DataForSEO Keywords Data per-keyword cost.

### Step 7 — Dependencies and cross-references
- **Companion to:** P0-02 (search volume) and P0-04 (CPC) — the value/competition triad.
- **Cross-pillar:** P3-01 (referring domain count) — keyword difficulty is largely a function of ranking pages' backlink profiles, so off-page authority is a related signal.

---

## P0-04 — Cost-per-click as commercial value indicator

**Pillar:** Strategic Foundation
**Evidence weight:** Probable

### Step 1 — Definition
The average cost-per-click for a keyword in Google Ads, used as a proxy for the commercial value advertisers assign to the query. High CPC indicates strong advertiser competition, typically reflecting transactional intent and high commercial value per visitor.

### Step 2 — Citations
1. **Google Ads — CPC documentation** (https://support.google.com/google-ads/answer/2459326, Google, accessed May 2026). Authoritative source for CPC mechanics in Google Ads.
2. **Ahrefs blog on CPC as SEO signal** (https://ahrefs.com/blog/cpc/, accessed May 2026). Industry coverage of CPC as a commercial-value proxy in SEO strategy.
3. **DataForSEO Keywords Data API** (https://docs.dataforseo.com/v3/keywords_data/, DataForSEO, accessed May 2026). Returns `cpc` per keyword in US dollars.

### Step 3 — Evidence weight rationale
CPC is a directly observable advertiser-bid signal. As a commercial-value indicator for SEO purposes, it's an accepted heuristic but not a Google-endorsed ranking factor. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Keywords Data API** field `cpc` (US dollars).

### Step 5 — Verification
DataForSEO confirms `cpc` returned per keyword. Granularity required: per-keyword decimal CPC. Granularity delivered: matches.

### Step 6 — Cost
Bundled with DataForSEO Keywords Data per-keyword cost.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P0-01 (intent) — CPC strongly correlates with transactional intent. The system can use CPC as a corroborating signal when intent classification is ambiguous.
- **Used by:** opportunity scoring as a commercial-value modifier (high-CPC keywords are typically more valuable to rank for).

---

## P0-05 — SERP feature presence per query

**Pillar:** Strategic Foundation
**Evidence weight:** Consensus

### Step 1 — Definition
The set of special SERP features that appear for a query in Google search results. Includes AI Overview, Featured Snippet, People Also Ask, Image Pack, Video Pack, Local Pack, Shopping Pack, Knowledge Panel, Sitelinks, Top Stories, and others. Different features change the organic CTR landscape and indicate query type.

### Step 2 — Citations
1. **Google Search Central — SERP features documentation** (https://developers.google.com/search/docs/appearance, Google, accessed May 2026). Google publishes its supported rich result and SERP feature types and explains the criteria for each.
2. **Ahrefs — SERP features tracking guide** (https://ahrefs.com/blog/serp-features/, accessed May 2026). Industry coverage of all observable SERP features and how to track them.
3. **DataForSEO SERP API documentation** (https://docs.dataforseo.com/v3/serp/google/organic/live/advanced/, DataForSEO, accessed May 2026). Returns SERP feature types in `item_types` array per query, including `ai_overview`, `featured_snippet`, `people_also_ask`, `images`, `videos`, `local_pack`, `shopping`, `knowledge_graph`, etc.

### Step 3 — Evidence weight rationale
SERP features are directly observable on Google's search results pages. Google explicitly documents many of them. DataForSEO and other providers track them programmatically. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO SERP API** field `item_types` per query, plus per-feature presence flags.

### Step 5 — Verification
DataForSEO confirms `item_types` returned per query. Granularity required: per-query feature inventory. Granularity delivered: matches.

### Step 6 — Cost
DataForSEO SERP API: approximately $0.001 per query (live search). For a pilot site tracking 500 keywords with monthly SERP refresh, approximately £15/month.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P6-01 (Google AI Overview presence) — same data, framed for the AI search pillar. AI Overview presence specifically affects organic CTR and triggers different recommendation framing.
- **Used by:** opportunity scoring (presence of AI Overview suppresses expected organic click value; presence of Featured Snippet may amplify it for the page that holds the snippet).

---

## P0-06 — Buyer journey stage per keyword

**Pillar:** Strategic Foundation
**Evidence weight:** Probable

### Step 1 — Definition
Where in the buyer journey funnel a query falls — **awareness** (problem identification, early-stage information-seeking), **consideration** (active evaluation of options), or **decision** (ready to purchase or transact). Buyer journey stage informs which page type and content depth should target the query.

### Step 2 — Citations
1. **HubSpot — Buyer's Journey framework** (https://blog.hubspot.com/marketing/buyers-journey, HubSpot, accessed May 2026). HubSpot's articulation of the awareness/consideration/decision framework is the most-cited industry reference for this concept in marketing literature.
2. **Backlinko — keyword research and content strategy guides** (https://backlinko.com/, Brian Dean). Buyer-journey-stage classification is integrated into mainstream SEO content strategy advice.
3. **Ahrefs — Content marketing and keyword research guides** (https://ahrefs.com/blog/, Ahrefs). Maps keyword intent to buyer journey stage as a standard analytical lens for content planning.

### Step 3 — Evidence weight rationale
Marketing-industry framework with widespread practitioner adoption. Not a Google-endorsed concept directly, but the underlying mapping (intent type to funnel stage) is well-supported. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition.** Derive buyer journey stage from intent classification (P0-01) plus query pattern analysis. Awareness queries typically use "what is", "how to", "why"; consideration queries use "best", "compare", "review", "vs"; decision queries use "buy", "price", "near me", "discount".
- **Refinement: LLM classification** for ambiguous cases.

### Step 5 — Verification
Rule-based mapping from intent class plus query patterns is deterministic. LLM refinement uses single-shot classification. Granularity required: per-keyword three-state label (awareness / consideration / decision). Granularity delivered: by composition.

### Step 6 — Cost
Composition only (free). LLM cost negligible if used as fallback.

### Step 7 — Dependencies and cross-references
- **Depends on:** P0-01 (intent classification).
- **Used by:** content strategy decisions — different journey stages call for different page types (awareness → blog/guide; consideration → comparison/review; decision → product/service page).

---

## P0-07 — Topical authority / site focus score

**Pillar:** Strategic Foundation
**Evidence weight:** Probable

### Step 1 — Definition
A measure of how concentrated a site's content is around a defined topic or set of topics. Sites with high topical focus tend to accrue authority for their focal topics; sites with diffuse content struggle to rank for any single topic. The leaked Google feature `siteFocusScore` confirms Google measures site-level topical concentration.

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names `siteFocusScore` as a feature in Google's content warehouse. Mike King's analysis identifies it as a measure of how tightly concentrated the site's content cluster is.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Site-level signals around topical authority are referenced under Site-Level Factors and the E-A-T section.
3. **Google Search Central — Quality Rater Guidelines** (publicly published by Google). Quality raters are instructed to evaluate whether a site is a recognised authority on the topics it covers — operationally similar to topical focus.

### Step 3 — Evidence weight rationale
The leaked feature confirms Google computes site-level topical concentration. Backlinko corroborates the practitioner concept. Quality Rater Guidelines support the principle. Specific operational weight is not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition** over a full site crawl.
- **Per-page topic extraction:** LLM-driven topic labelling or embedding clustering across all pages.
- **Concentration computation: our own.** Compute pairwise cosine similarity across page embeddings; high mean similarity indicates focused site, low mean indicates diffuse site.

### Step 5 — Verification
Embedding generation is a standard operation (OpenAI text-embedding-3-small or equivalent). Concentration metric is a straightforward statistical computation. Granularity required: per-site focus score (0–1, where 1 = perfectly concentrated). Granularity delivered: by composition.

### Step 6 — Cost
Embedding generation: ~$0.0001 per page (OpenAI text-embedding-3-small) or free (self-hosted sentence-transformers). For a 500-page site, approximately £0.05 per full audit.

### Step 7 — Dependencies and cross-references
- **Companion to:** P0-08 (site topical breadth) — `siteRadius` in the leak. Together these two features describe the shape of a site's topical footprint: focused-and-narrow, focused-and-broad, scattered-and-narrow, scattered-and-broad.
- **Cross-pillar:** P4-06 (E-E-A-T at content operations level) — topical authority is a key component of Expertise.

---

## P0-08 — Site topical breadth

**Pillar:** Strategic Foundation
**Evidence weight:** Probable

### Step 1 — Definition
The radius or spread of a site's topical coverage across all pages. The leaked Google feature `siteRadius` is the geometric counterpart to `siteFocusScore` — focus measures how clustered content is; radius measures how far the cluster extends from its centroid.

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names `siteRadius` alongside `siteFocusScore`. Mike King interprets these as paired metrics describing the geometry of a site's topical cluster in embedding space.
2. **Information retrieval and embedding-space literature.** The pairing of focus (concentration) and radius (spread) is a standard way to characterise clusters in vector space.

### Step 3 — Evidence weight rationale
Leak feature exists; the geometric interpretation is well-supported by embedding-space methodology. Single-source for the specific feature name; the underlying concept is widely used. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition.** Compute centroid of all page embeddings on the site; measure mean or maximum distance from centroid to individual pages.
- **Embedding generation: same source as P0-07** (no incremental cost).

### Step 5 — Verification
Standard embedding-space computation. Granularity required: per-site radius score (real number; smaller = tighter cluster). Granularity delivered: by composition.

### Step 6 — Cost
Bundled with P0-07 embedding computation.

### Step 7 — Dependencies and cross-references
- **Companion to:** P0-07 (site focus score) — interpreted together.
- **Used by:** site strategy recommendations. A site with high focus and small radius is well-positioned for topical authority; a site with low focus and large radius is fragmented and may need consolidation or topic-specific subdomains.

---

## P0-09 — Site embedding similarity to query

**Pillar:** Strategic Foundation
**Evidence weight:** Probable

### Step 1 — Definition
The cosine similarity between the site's centroid embedding (the average of all page embeddings, representing the site's overall topical position) and the embedding of a target query. High similarity indicates the site's topical coverage is well-aligned with the query.

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names `siteEmbedding` as a feature in Google's content warehouse, confirming Google computes site-level vector representations used in ranking.
2. **Information retrieval research on dense retrieval.** Site-level and document-level embedding comparison is a standard technique in modern semantic search systems.

### Step 3 — Evidence weight rationale
Leak feature confirms site-level embeddings exist in Google's infrastructure. The use of these embeddings in ranking is widely assumed but not officially detailed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition.** Compute site centroid embedding from page embeddings (P0-07/08 source). Generate query embedding using the same model. Compute cosine similarity.
- **Embedding model: OpenAI text-embedding-3-small or equivalent.**

### Step 5 — Verification
Cosine similarity is a standard operation. Granularity required: per-site-per-query similarity score (0–1). Granularity delivered: by composition.

### Step 6 — Cost
Per-query embedding generation: ~$0.0001 per query. For 500 tracked queries, ~£0.05 per full evaluation.

### Step 7 — Dependencies and cross-references
- **Depends on:** site embeddings from P0-07.
- **Cross-references:** P0-10 (page-level version) — same operation at page level rather than site level.

---

## P0-10 — Page embedding similarity to query

**Pillar:** Strategic Foundation
**Evidence weight:** Probable

### Step 1 — Definition
The cosine similarity between an individual page's content embedding and the embedding of a target query. Used to identify which page on a site best matches a given query and to guide keyword-to-page mapping decisions.

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names `pageEmbedding` as a feature in Google's content warehouse. Mike King's analysis identifies page-level embeddings as a primary input to semantic relevance scoring in Google's ranking pipeline.
2. **Google Search Central — How Search Works (semantic understanding)** (https://www.google.com/search/howsearchworks/, Google, accessed May 2026). Google describes its ranking systems as understanding meaning rather than literal keyword matching, consistent with embedding-based comparison.

### Step 3 — Evidence weight rationale
Leak feature confirms page-level embeddings are used. Google publicly describes semantic ranking. The exact operational weight in the ranking algorithm is not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition.** Generate page embedding from content (DataForSEO plain text + OpenAI text-embedding-3-small). Generate query embedding. Compute cosine similarity.

### Step 5 — Verification
Standard embedding-and-similarity operation. Granularity required: per-page-per-query similarity score (0–1). Granularity delivered: by composition.

### Step 6 — Cost
Page embeddings: ~$0.0001 per page (one-time per audit). Query embeddings: ~$0.0001 per query (cached and reused across pages).

### Step 7 — Dependencies and cross-references
- **Used by:** keyword-to-page mapping (P0-13) — for each target keyword, the highest-similarity page is the best candidate to target it.
- **Cross-pillar:** P1-05 (title-to-content match score) — page embeddings can also support title-content alignment if needed.

---

## P0-11 — Topic cluster definition for the site

**Pillar:** Strategic Foundation
**Evidence weight:** Probable

### Step 1 — Definition
The semantic grouping of pages on a site into topic clusters, where each cluster contains pages covering related subtopics. Used for content gap analysis, internal linking strategy, and pillar-page architecture planning.

### Step 2 — Citations
1. **HubSpot — Topic Cluster Model** (https://blog.hubspot.com/marketing/topic-clusters-seo, HubSpot, accessed May 2026). The most-cited industry articulation of the topic cluster framework: pillar pages cover broad topics, supported by cluster pages on subtopics that all link back to the pillar.
2. **Backlinko — Topic clusters and content hub guides** (https://backlinko.com/, Brian Dean). Mainstream practitioner adoption of the same framework.
3. **Search Engine Journal — Topic cluster strategy** (https://www.searchenginejournal.com/, accessed May 2026). Industry coverage of topic clustering as a foundational content architecture concept.

### Step 3 — Evidence weight rationale
Industry-standard framework with universal practitioner adoption. Not directly endorsed by Google as a ranking factor, but the underlying mechanics (internal linking, semantic relatedness) are supported by Google's documentation. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition.** Run unsupervised clustering (k-means, HDBSCAN, or hierarchical) over page embeddings from P0-10. Each resulting cluster is a topic group.
- **Topic labelling: LLM-driven.** Provide cluster centroid pages to an LLM with prompt requesting a 2–4-word topic label per cluster.

### Step 5 — Verification
Clustering is a standard ML operation. LLM topic labelling produces interpretable cluster names. Granularity required: per-site cluster list with cluster membership and labels. Granularity delivered: by composition.

### Step 6 — Cost
Clustering: free (computational only). Topic labelling: ~$0.001 per cluster via LLM. For ~10 clusters per site, approximately £0.01 per audit.

### Step 7 — Dependencies and cross-references
- **Depends on:** P0-10 (page embeddings).
- **Used by:** P0-12 (pillar architecture detection), P0-14 (content gap analysis), recommendation generation for content strategy.

---

## P0-12 — Pillar page / hub-and-spoke architecture

**Pillar:** Strategic Foundation
**Evidence weight:** Probable

### Step 1 — Definition
A site architecture in which a comprehensive "pillar" page targets a broad head topic, supported by deeper "cluster" pages targeting specific subtopics. All cluster pages link to the pillar; the pillar links to each cluster page. Topic clusters are organised around pillars to demonstrate topical authority.

### Step 1.5 — Evaluation rules
A topic cluster passes pillar architecture when ALL of the following rules pass:

1. **Pillar page exists.** The cluster has a single pillar-candidate page that targets the broad head topic for the cluster (identifiable by topic-label match plus on-page coverage breadth).
2. **Pillar receives high inbound links from cluster members.** A majority (≥70%) of cluster member pages link to the pillar page via internal links.
3. **Pillar links out to cluster members.** The pillar page links to a substantial proportion (≥70%) of cluster member pages, supporting hub-and-spoke flow.
4. **Anchor text on pillar inbound links is topical.** Internal links pointing to the pillar use anchor text containing the cluster topic or close variants, not generic anchors ("click here", "learn more").
5. **Cluster members link to each other where topically related.** Cluster members do not exclusively link only to the pillar; topically related members cross-link, creating a dense subgraph rather than a star topology.
6. **No competing pillars within the cluster.** The cluster has exactly one pillar; if two or more pages have similar inbound-link concentration on the same head topic, this is a cannibalisation flag rather than a passing architecture.

A cluster passing all 6 rules has correct pillar architecture.

### Step 2 — Citations
1. **HubSpot — Topic Cluster and Pillar Page Model** (https://blog.hubspot.com/marketing/topic-clusters-seo, HubSpot, accessed May 2026). The canonical practitioner articulation of pillar-and-cluster architecture, widely adopted across the industry.
2. **Backlinko — Hub and Spoke Content Strategy** (https://backlinko.com/, Brian Dean). Practitioner reinforcement of the same architectural pattern.
3. **Google Search Central — Site architecture and internal linking** (https://developers.google.com/search/docs/, Google, accessed May 2026). Google does not endorse "pillar pages" by name but recommends logical site architecture and meaningful internal linking, which the pillar-cluster pattern operationalises.

### Step 3 — Evidence weight rationale
Industry-wide framework, indirectly supported by Google's site architecture and internal linking guidance. Not Google-named as a specific ranking factor. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition** combining P0-11 (topic clusters) with P1-23 (internal inbound link counts).
- **Detection logic: our own.** For each topic cluster from P0-11, identify whether one page (the pillar candidate) receives high inbound links from other cluster members and links out to all of them. Detect missing pillars (cluster has no clear hub) and orphaned clusters (no internal link consolidation).

### Step 5 — Verification
Composition over existing data sources (clustering plus internal link graph). Pattern detection is straightforward. Granularity required: per-site list of clusters with pillar status (has pillar / missing pillar / weak pillar) plus the pillar-page identity for each. Granularity delivered: by composition.

### Step 6 — Cost
Composition only, free.

### Step 7 — Dependencies and cross-references
- **Depends on:** P0-11 (topic clusters), P1-23 (internal link counts), P1-25 (anchor text relevance — for assessing whether internal links to the pillar are well-anchored).
- **Used by:** content strategy recommendations — clusters missing a pillar are content-gap opportunities; weak pillars are internal-linking optimisation targets.

---

## P0-13 — Keyword-to-page mapping

**Pillar:** Strategic Foundation
**Evidence weight:** Probable

### Step 1 — Definition
A site-wide mapping that assigns each tracked target keyword to exactly one primary page intended to rank for it. Prevents cannibalisation, anchors keyword strategy, and informs which page receives optimisation work for each keyword.

### Step 1.5 — Evaluation rules
A site passes keyword-to-page mapping correctness when ALL of the following rules pass:

1. **Every tracked target keyword has a primary page assigned.** No tracked keyword is left unassigned.
2. **Each keyword maps to exactly one primary page.** No keyword is assigned to multiple primary pages (cannibalisation).
3. **Primary page is the best-fit candidate.** The assigned primary page has the highest page-embedding similarity (P0-10) to the keyword among all site pages, OR is already ranking for the keyword in GSC, OR is explicitly chosen via manual override.
4. **No reverse cannibalisation.** No single page is the assigned primary for more than ~5 distinct top-priority keywords (a page assigned to too many primary keywords cannot be optimised effectively for all).
5. **Mapping is reviewed and current.** Mapping is regenerated when the page inventory changes substantively (new pages published, pages removed) and when GSC data shows substantial ranking shifts.
6. **Cannibalisation conflicts flagged not silently resolved.** Where multiple pages already rank for the same keyword (real cannibalisation), the conflict is surfaced as a finding requiring resolution (consolidation, redirect, intent split) rather than silently picking one as primary.

A site passing all 6 rules has correct keyword-to-page mapping.

### Step 2 — Citations
1. **Backlinko — Keyword Mapping in SEO** (https://backlinko.com/keyword-research, Brian Dean). Practitioner standard advice: one primary keyword target per page, mapped explicitly.
2. **Ahrefs — Keyword mapping methodology** (https://ahrefs.com/blog/keyword-mapping/, Ahrefs, accessed May 2026). Industry-standard methodology for documenting keyword-to-page relationships as a foundation for content strategy.
3. **Google Search Central — Canonical and duplicate content** (https://developers.google.com/search/docs/crawling-indexing/canonicalization, Google, accessed May 2026). Google does not use the term "keyword mapping" but the canonical principle (one URL is the authoritative version of a piece of content) operationalises the same logic.

### Step 3 — Evidence weight rationale
Universal practitioner standard. Indirectly supported by Google's canonical-content principle. Not a directly named ranking factor by Google. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition** combining (a) GSC data on which pages already rank for which queries, (b) page embedding similarity from P0-10 to identify best-fit candidates for unranked target keywords, (c) configurable manual override per site.
- **GSC API** for current rankings; **own logic** for mapping computation.

### Step 5 — Verification
GSC API is well-documented and accessible. Mapping computation is composition. Granularity required: per-keyword single primary-page assignment plus list of secondary pages also ranking for the keyword. Granularity delivered: by composition.

### Step 6 — Cost
GSC API is free for the site owner. Composition logic is free.

### Step 7 — Dependencies and cross-references
- **Foundational** — feeds nearly all P1 (On-Page) variables that need a target keyword reference (P1-03, P1-04, P1-13, P1-14, P1-17, P1-25, etc.).
- **Cross-pillar:** cannibalisation detection (a later pillar concept) operates on violations of one-primary-per-keyword.

---

## P0-14 — Content gap analysis vs ranking competitors *(removed — moved to the Competitive Analysis module, June 2026)*

Removed from the site audit in June 2026. Content-gap-vs-competitors is a comparative *insight*, not an intrinsic, fixable site-health item, so it belongs in the dedicated Competitive Analysis module (you vs N competitors: traffic, keyword positioning, backlinks, content gaps) rather than as an audit variable. The single-site audit stays purely intrinsic.

**Pillar:** Strategic Foundation
**Evidence weight:** Probable

### Step 1 — Definition
Identification of (a) keywords that direct competitors rank for but the site does not, and (b) topical clusters covered by competitor sites that are absent or under-developed on our site. Surfaces opportunities for new content creation and topic expansion.

### Step 2 — Citations
1. **Ahrefs — Content Gap Tool** (https://ahrefs.com/content-gap, Ahrefs, accessed May 2026). Industry-leading content gap analysis methodology, comparing keyword overlap and unique-to-competitor keywords across multiple competing domains.
2. **Semrush — Keyword Gap Tool** (https://www.semrush.com/kb/733-keyword-gap, Semrush, accessed May 2026). Same methodology applied across Semrush's keyword database.
3. **DataForSEO Labs API — Competitors and keyword intersection endpoints** (https://docs.dataforseo.com/v3/dataforseo_labs/, DataForSEO, accessed May 2026). Provides competitor identification and keyword overlap analysis programmatically.

### Step 3 — Evidence weight rationale
Universal industry method, supported by all major SEO tooling. Not a Google-named ranking factor — content gap analysis is an opportunity-discovery method, not a ranking signal. Qualifies as **Probable** as an analytical technique with strong practitioner adoption.

### Step 4 — Data source(s)
- **Primary: DataForSEO Labs API** competitor and keyword intersection endpoints.
- **Composition: our own** ranking and prioritisation of identified gaps based on opportunity scoring (combining keyword volume, difficulty, and our site's authority).

### Step 5 — Verification
DataForSEO Labs is documented. Granularity required: per-site list of gap keywords plus opportunity scoring. Granularity delivered: by composition.

### Step 6 — Cost
DataForSEO Labs API: approximately $0.01–$0.05 per analysis (depending on the depth and number of competitor domains compared). For monthly competitive analysis on a pilot site, approximately £0.50–£2/month.

### Step 7 — Dependencies and cross-references
- **Depends on:** identification of direct competitors (a separate composition step typically based on SERP overlap analysis).
- **Used by:** content strategy recommendations and pillar-cluster expansion plans (P0-12).

---

## P0-15 — Brand search volume baseline and trajectory

**Pillar:** Strategic Foundation
**Evidence weight:** Probable

### Step 1 — Definition
The volume of branded searches (queries containing the site's brand name or close variants) over time, plus the trajectory (growing, flat, declining). Branded search volume reflects brand awareness and audience growth; trajectory indicates whether brand-building efforts are working.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #162 (Branded Searches) and Factor #163 (Brand + Keyword Searches) are listed as recognised brand-strength signals.
2. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leak references `chromeInTotal` (Chrome view counts at site level) and brand-related signals, suggesting Google tracks branded query volume as part of brand-strength evaluation.
3. **DataForSEO Keywords Data API**. Branded keywords can be tracked using the same volume-and-trends endpoints as any other keyword.

### Step 3 — Evidence weight rationale
Practitioner consensus that brand search volume reflects brand strength. Leak features support brand signal tracking. Not a directly named ranking factor in Google's documentation. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Keywords Data API** for volume-over-time data on branded queries.
- **Brand-query identification: composition.** Generate the set of branded query patterns (brand name, brand + product, brand + variant spellings) per site.

### Step 5 — Verification
DataForSEO confirms volume-and-trend data is returned. Granularity required: per-month volume for the brand-query set plus aggregate trajectory. Granularity delivered: matches.

### Step 6 — Cost
Bundled with Keywords Data API per-query cost.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P3-32 (brand mention frequency from off-page) — branded search and brand mentions together describe brand strength.
- **Used by:** opportunity prioritisation. Sites with strong, growing brand search benefit more from on-page work than sites with weak brand signal.

---

## P0-16 — Brand entity in Knowledge Graph

**Pillar:** Strategic Foundation
**Evidence weight:** Consensus

### Step 1 — Definition
Whether the site's brand is recognised as an entity in Google's Knowledge Graph and consequently displays a Knowledge Panel for branded queries. Knowledge Graph entity recognition signals to Google that the brand is a defined entity with reliable structured information, supporting authority and disambiguation in ranking.

### Step 2 — Citations
1. **Google Knowledge Graph documentation** (https://developers.google.com/knowledge-graph, Google, accessed May 2026). Authoritative source for Google's entity recognition system, including the Knowledge Graph Search API.
2. **Google Search Central — Knowledge Panel guidelines** (https://support.google.com/knowledgepanel, Google, accessed May 2026). Documents how Knowledge Panels are generated from Knowledge Graph entities.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #167 (Known Authorship) and brand-related signals reference entity recognition.
4. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leak names `isAuthor` and `author` features, confirming Google's ranking infrastructure uses entity authorship signals.

### Step 3 — Evidence weight rationale
Google explicitly maintains the Knowledge Graph as a public-facing entity system. The Knowledge Graph Search API provides authoritative entity recognition data. Practitioner consensus aligns. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google Knowledge Graph Search API** (free, requires API key). Returns whether a brand is a recognised entity, its entity ID, and entity metadata.
- **Verification: SERP-based confirmation** via DataForSEO SERP API for branded queries (does a Knowledge Panel appear in `item_types`?).

### Step 5 — Verification
Google Knowledge Graph Search API is documented and accessible. Granularity required: per-brand entity status (recognised / not recognised) plus entity metadata. Granularity delivered: matches.

### Step 6 — Cost
Knowledge Graph Search API: free with rate limits (sufficient for pilot scale).

### Step 7 — Dependencies and cross-references
- **Scope of this variable:** strategic-foundation level binary check — is the brand recognised in Google's Knowledge Graph at all? Used as a foundational input across the system.
- **Cross-pillar (broader scope):** P6-11 (entity coverage) extends this check to the full multi-system entity layer (Wikipedia + Wikidata + Google Knowledge Graph together). P6-29 (KG entity completeness) is the deeper audit of the KG record's properties and accuracy.
- **Hierarchy:** P0-16 → "is the brand a recognised entity" (strategic). P6-11 → "is the brand covered across the entity-knowledge ecosystem" (operational). P6-29 → "is the KG record itself complete and accurate" (deep audit).

---

## P0-17 — YMYL classification of pages and topics

**Pillar:** Strategic Foundation
**Evidence weight:** Consensus

### Step 1 — Definition
Whether a page or topic falls under Google's "Your Money or Your Life" (YMYL) category — content that could significantly affect a person's health, financial stability, safety, civic participation, or wellbeing. YMYL content is held to substantially higher quality standards by Google's algorithms and quality raters.

### Step 1.5 — Evaluation rules
A page passes YMYL classification correctness when ALL of the following rules pass:

1. **Classification covers all QRG-defined YMYL topic categories.** Health/medical, financial/legal, civic/government, safety, news on important events, and content concerning sensitive groups are all evaluated against, not a subset.
2. **Per-page binary classification produced.** Every page is classified as YMYL true/false; no pages are left unclassified.
3. **Category label attached when YMYL true.** A YMYL-true page also has the specific category attached (health, financial, legal, etc.) so downstream rules can apply category-specific treatment.
4. **Borderline cases flagged.** Pages that are arguably YMYL but ambiguous (e.g., a fitness blog touching on diet — health-adjacent but not strictly YMYL) are flagged as borderline rather than silently classified, supporting human review.
5. **Classification is consistent within page clusters.** Pages within the same content cluster have consistent YMYL labels; if a cluster mixes YMYL and non-YMYL pages, the cluster boundary is investigated rather than the inconsistency accepted.
6. **YMYL flag triggers downstream rule changes.** Where YMYL-true, the system applies elevated E-E-A-T thresholds, stricter author-credential requirements, and more conservative deployment patterns; where YMYL-false, standard thresholds apply. The trigger is operationalised, not just recorded.

A site passing all 6 rules has correct YMYL classification.

### Step 2 — Citations
1. **Google Search Quality Rater Guidelines** (publicly published, latest version 2024). Defines YMYL explicitly and instructs raters to apply elevated quality scrutiny to YMYL content. Topics include health, finance, safety, civic information, news on important events, and groups of people.
2. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names `ymylNewsScore`, `ymylHealthScore`, and `encodedChardXlqYmylPrediction` — confirming Google's ranking infrastructure computes YMYL-specific scoring.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #149 (YMYL Keywords) references YMYL classification as triggering elevated quality requirements.

### Step 3 — Evidence weight rationale
Google explicitly defines YMYL in its Quality Rater Guidelines (Tier A). Leak features confirm YMYL-specific scoring exists in Google's ranking infrastructure. Backlinko corroborates. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: composition** via LLM classifier or rule-based topic classification.
- **Topic categories: defined per Quality Rater Guidelines** — health/medical, financial/legal, civic/government, safety, news, sensitive groups.
- **Page-level classification: LLM-driven** based on page content + page type + URL pattern.

### Step 5 — Verification
LLM-driven YMYL classification is straightforward (single-shot classification with the QRG-defined categories). Granularity required: per-page YMYL boolean plus YMYL category if positive. Granularity delivered: by composition.

### Step 6 — Cost
LLM classification: ~$0.0005 per page (single-shot). For 500-page site, approximately £0.25 per audit.

### Step 7 — Dependencies and cross-references
- **Used by:** the system applies elevated quality thresholds and stricter risk classification to YMYL pages. Recommendations on YMYL pages should require more conservative deployment patterns.
- **Cross-pillar:** P4-13 (YMYL handling at content operations level), P4-06 (E-E-A-T) — YMYL content has the highest E-E-A-T requirements.

---

## P0-18 — Big-brand preference threshold detection

**Pillar:** Strategic Foundation
**Evidence weight:** Probable

### Step 1 — Definition
Detection of whether a query's SERP exhibits strong preference for high-authority big brands — i.e. whether the top organic positions are dominated by sites with very high domain authority such that smaller sites have minimal opportunity to rank regardless of on-page optimisation. Identifies queries where ranking is structurally constrained by brand authority.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #155 (Big Brand Preference). Backlinko cites observed patterns in SERPs where, particularly for commercial queries, the top results disproportionately favour large established brands regardless of individual page optimisation.
2. **Search Engine Journal and Search Engine Roundtable coverage of Google updates** (industry coverage from 2018 onwards). Multiple Google algorithm updates (notably the 2018 "Medic" update and subsequent core updates) have been observed to favour established authoritative sites in certain query verticals.
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leak references `siteAuthority` as a high-level site-quality score, consistent with the existence of authority-based ranking thresholds for some query types.

### Step 3 — Evidence weight rationale
Practitioner observation of pattern, supported by leak feature `siteAuthority`, no direct Google endorsement of "big brand preference" as a named factor. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition** from DataForSEO SERP data plus domain rating lookups.
- **Detection logic: our own.** For each tracked query, fetch top-10 SERP positions and look up the domain rating of each ranking domain. Compute the median DR of top 10; if median DR is above a threshold (e.g. 70+) and our site's DR is significantly below, the query is flagged as big-brand-dominated.

### Step 5 — Verification
SERP data and domain rating data are both standard DataForSEO outputs. Detection logic is composition. Granularity required: per-query boolean plus the median competitor DR. Granularity delivered: by composition.

### Step 6 — Cost
Per-query DataForSEO SERP cost (~$0.001) plus per-domain DR lookup (cached). Negligible incremental cost beyond P0-05 SERP work.

### Step 7 — Dependencies and cross-references
- **Used by:** opportunity prioritisation. Queries flagged as big-brand-dominated should be deprioritised in favour of mid-authority queries where the site has a realistic ranking opportunity.
- **Cross-pillar:** P0-03 (keyword difficulty) — closely related; KD is an aggregated measure that includes big-brand dominance among other factors. Big-brand detection is the more specific diagnostic.

---

# Pillar 2 — Technical SEO

**Total candidates:** 41
**Status:** Complete (41 of 41; P2-34, P2-35, P2-06 removed in May 2026 audits — P2-34/P2-35 as duplicates of P6-17/P6-18, P2-06 as externally unmeasurable. All retained as redirect notes.)

## Pillar 2 Index

| ID | Variable | Status | Weight |
|----|----------|--------|--------|
| P2-01 | robots.txt configuration correctness | Complete | Consensus |
| P2-02 | XML sitemap presence and validity | Complete | Consensus |
| P2-03 | Sitemap submission to GSC | Complete | Consensus |
| P2-04 | Indexation status per URL | Complete | Consensus |
| P2-05 | Crawl budget utilisation | Complete | Probable |
| P2-06 | Index tier / source type (leaked) | Removed | — |
| P2-07 | Canonicalisation conflicts | Complete | Consensus |
| P2-08 | LCP (Largest Contentful Paint) | Complete | Consensus |
| P2-09 | INP (Interaction to Next Paint) | Complete | Consensus |
| P2-10 | CLS (Cumulative Layout Shift) | Complete | Consensus |
| P2-11 | TTFB (Time to First Byte) | Complete | Probable |
| P2-12 | FCP (First Contentful Paint) | Complete | Probable |
| P2-13 | TBT (Total Blocking Time) | Complete | Probable |
| P2-14 | Page loading speed via HTML | Complete | Probable |
| P2-15 | Mobile responsiveness | Complete | Consensus |
| P2-16 | Mobile-friendly content (no hidden content) | Complete | Consensus |
| P2-17 | Mobile usability score | Complete | Consensus |
| P2-18 | HTTPS / SSL certificate | Complete | Consensus |
| P2-19 | HSTS configuration | Complete | Probable |
| P2-20 | Site uptime | Complete | Probable |
| P2-21 | Server location | Complete | Speculative |
| P2-22 | JavaScript rendering pattern (CSR/SSR/SSG/ISR) | Complete | Consensus |
| P2-23 | Crawl depth from homepage | Complete | Probable |
| P2-24 | Status code distribution | Complete | Consensus |
| P2-25 | Redirect chains (3+ hops) | Complete | Consensus |
| P2-26 | Internal broken links | Complete | Consensus |
| P2-27 | External broken links | Complete | Probable |
| P2-28 | Orphan pages | Complete | Consensus |
| P2-29 | HTML errors / W3C validation | Complete | Probable |
| P2-30 | Page weight | Complete | Consensus |
| P2-31 | Image format efficiency (WebP, AVIF) | Complete | Probable |
| P2-32 | Lazy loading implementation | Complete | Probable |
| P2-33 | Hreflang tags | Complete | Consensus |
| P2-34 | llms.txt configuration | Removed (subsumed by P6-18) | — |
| P2-35 | AI bot access in robots.txt | Removed (subsumed by P6-17) | — |
| P2-36 | IndexNow protocol adoption | Complete | Probable |
| P2-37 | Pop-ups and intrusive interstitials | Complete | Consensus |
| P2-38 | Ads-above-the-fold density | Complete | Probable |
| P2-39 | Use of AMP (deprecated) | Complete | Speculative |
| P2-40 | Host age | Complete | Speculative |
| P2-41 | Site update cadence | Complete | Probable |
| P2-42 | Sitemap priority weighting per URL | Complete | Speculative |
| P2-43 | Duplicate content handling at site level | Complete | Consensus |

---

## P2-01 — robots.txt configuration correctness

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The site has a `/robots.txt` file at the root domain that follows the Robots Exclusion Protocol correctly: valid syntax, no contradictory rules, no blocking of pages that should be indexed, and no allowing of pages that should be blocked.

### Step 1.5 — Evaluation rules
A site passes robots.txt configuration correctness when ALL of the following rules pass:

1. **File present at root.** `https://{domain}/robots.txt` returns HTTP 200 with `Content-Type: text/plain` (or compatible).
2. **Syntactically valid against RFC 9309.** File parses cleanly: each rule begins with a recognised directive (`User-agent`, `Disallow`, `Allow`, `Sitemap`, `Crawl-delay`); no malformed lines.
3. **No accidental site-wide block.** No `User-agent: *` followed by `Disallow: /` (a common misconfiguration that blocks the entire site).
4. **No blocking of indexable content.** Disallow rules do not match URL patterns of pages intended to be indexed (cross-checked against the URL inventory and sitemap).
5. **Disallow rules align with declared intent.** Pages intentionally hidden (admin paths, internal search results, faceted-navigation URL combinations) are blocked; pages intended to be indexed are not.
6. **Sitemap reference present.** At least one `Sitemap:` directive references the site's XML sitemap URL.
7. **No conflict with `noindex` meta on indexable pages.** Pages declared `noindex` in meta are not also blocked by robots.txt (Google cannot read the meta directive on a robots-blocked page; result is unintended indexation).
8. **Bot-specific blocks are explicit and consistent.** Where specific bots are blocked (LLM bots, scrapers), the policy is consistent across same-category bots (P6-17 covers LLM-bot specifics).
9. **No CSS/JS/image resource blocking.** Resources required to render the page (CSS, JS, images, fonts) are not blocked, so Google can render and evaluate the page properly.
10. **No reliance on `Crawl-delay` for Googlebot.** Googlebot does not honour `Crawl-delay`; rate-limiting requires GSC's crawl rate setting.

A site passing all 10 rules has correct robots.txt configuration.

### Step 2 — Citations
1. **Google Search Central — robots.txt Introduction** (https://developers.google.com/search/docs/crawling-indexing/robots/intro, Google, accessed May 2026). Authoritative documentation on how Google interprets robots.txt directives, including supported user-agents and rules.
2. **RFC 9309 — Robots Exclusion Protocol** (https://www.rfc-editor.org/rfc/rfc9309.html, IETF, accessed May 2026). The IETF-standardised specification for robots.txt that Google co-authored. Provides the formal protocol definition.
3. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/, DataForSEO, accessed May 2026). Includes robots.txt-related checks via the page-level audit; full robots.txt validation requires direct fetch.

### Step 3 — Evidence weight rationale
robots.txt is a Google-authored, IETF-standardised protocol with explicit documentation. Misconfiguration is a common indexation issue with directly observable consequences. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: direct fetch of `https://{domain}/robots.txt`** plus parser validation against RFC 9309.
- **Verification: Google Search Console robots.txt Tester** (deprecated but still accessible) or URL Inspection API.

### Step 5 — Verification
robots.txt is a public file fetched via HTTP. Parser validation is a standard library operation (Python's `urllib.robotparser`, third-party libraries). Granularity required: per-site validity boolean plus list of specific issues. Granularity delivered: by composition.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P1-33 (robots meta tag). robots.txt controls crawler access at site level; robots meta controls indexing intent at page level. Together they govern indexation behaviour.

---

## P2-02 — XML sitemap presence and validity

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The site provides a valid XML sitemap that lists all indexable URLs with optional metadata (lastmod, priority, changefreq). The sitemap follows the sitemaps.org protocol and is referenced from robots.txt.

### Step 1.5 — Evaluation rules
A site passes XML sitemap presence and validity when ALL of the following rules pass:

1. **Sitemap accessible.** A sitemap returns HTTP 200 at `/sitemap.xml` (or the path declared in robots.txt) with `Content-Type: application/xml` (or compatible).
2. **Valid XML against sitemaps.org schema.** The file parses as valid XML and conforms to the sitemaps.org protocol schema.
3. **Within size limits.** Single sitemap file does not exceed 50,000 URLs or 50 MB uncompressed; oversize sites use a sitemap index referencing multiple sub-sitemaps.
4. **All listed URLs are indexable.** No URL in the sitemap is also blocked by robots.txt, declared `noindex`, or canonicalised to a different URL — listing such URLs creates an inconsistent indexation signal.
5. **All listed URLs return 200.** No 4xx, 5xx, or redirected URLs in the sitemap (each crawl waste signals).
6. **Site URL inventory matches sitemap.** All indexable site URLs are included; pages discoverable by crawl but missing from sitemap are flagged.
7. **`<lastmod>` populated and current.** Where `<lastmod>` is declared, dates reflect actual content modification times (not all-set-to-current-date, which is a common bug that destroys the signal's value).
8. **Sitemap referenced in robots.txt.** `Sitemap:` directive in robots.txt points to the sitemap URL.
9. **No conflicting canonical declarations.** URL listed in sitemap is the same URL declared as canonical on the page itself.
10. **Multiple sitemaps interconnected via index.** Where the site uses a sitemap index, it references all sub-sitemaps, and each sub-sitemap is also accessible.

A site passing all 10 rules has a valid XML sitemap.

### Step 2 — Citations
1. **Google Search Central — Sitemaps Overview** (https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview, Google, accessed May 2026). Google's authoritative guidance on sitemap creation and submission.
2. **sitemaps.org — Sitemap Protocol** (https://www.sitemaps.org/protocol.html, accessed May 2026). The cross-search-engine protocol for XML sitemaps that Google, Bing, and others honour.
3. **DataForSEO On-Page documentation** — sitemap-related checks plus the ability to fetch and validate the sitemap directly.

### Step 3 — Evidence weight rationale
Google explicitly recommends sitemaps. The protocol is standardised cross-engine. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: direct fetch of `/sitemap.xml`** (or location referenced in robots.txt).
- **Validation: our own** XML parser plus sitemap protocol compliance check (URL count, file size, URL accessibility).

### Step 5 — Verification
Sitemap fetch and parse is a standard operation. Granularity required: per-site validity plus URL count, broken URLs in sitemap, and sitemap freshness. Granularity delivered: by composition.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Depended upon by:** P2-03 (sitemap submission to GSC).
- **Used by:** P2-42 (sitemap priority weighting per URL).

---

## P2-03 — Sitemap submission to GSC

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The site's XML sitemap has been submitted to Google Search Console and is being processed without errors. Submission accelerates discovery and surfaces sitemap-level indexation issues in GSC.

### Step 2 — Citations
1. **Google Search Central — Submit a sitemap** (https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap#addsitemap, Google, accessed May 2026). Authoritative submission guidance.
2. **Google Search Console Sitemaps API** (https://developers.google.com/webmaster-tools/v1/sitemaps, Google, accessed May 2026). API for programmatic sitemap submission and status retrieval.

### Step 3 — Evidence weight rationale
Google explicitly recommends sitemap submission and provides the API for it. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: GSC Sitemaps API** for submission status, last download time, and error count.

### Step 5 — Verification
GSC Sitemaps API is documented and accessible. Granularity required: per-site submission status (submitted / not submitted / error). Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Depends on:** P2-02 (sitemap must exist before submission), P2-01 (robots.txt should reference the sitemap).

---

## P2-04 — Indexation status per URL

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
Whether each URL is in Google's index and eligible to appear in search results. URLs may be: indexed and serving, indexed but not selected, discovered but not indexed, crawled but not indexed, blocked by robots.txt, blocked by noindex, or unknown to Google.

### Step 2 — Citations
1. **Google Search Central — URL Inspection API** (https://developers.google.com/webmaster-tools/v1/urlInspection, Google, accessed May 2026). Authoritative per-URL indexation status reporting.
2. **Google Search Central — Index Coverage report** (https://support.google.com/webmasters/answer/7440203, Google, accessed May 2026). Aggregate indexation reporting at the GSC interface.
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Indexation-related signals including `sourceType` confirm Google maintains tiered indexation.

### Step 3 — Evidence weight rationale
Google provides authoritative indexation status via GSC URL Inspection API. Indexation is a binary prerequisite for ranking. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google Search Console URL Inspection API** per URL.
- **Caveat:** the URL Inspection API is rate-limited (approximately 600 calls per day per property), so for large sites we audit a representative sample plus all newly-deployed URLs.

### Step 5 — Verification
URL Inspection API is documented. Granularity required: per-URL multi-state (indexed and serving / indexed but not selected / discovered but not indexed / etc.). Granularity delivered: matches.

### Step 6 — Cost
Free (GSC API). Rate limits constrain volume rather than cost.

### Step 7 — Dependencies and cross-references
- **Depends on:** P2-01 (robots.txt), P1-33 (robots meta), P2-07 (canonicalisation conflicts) — all three influence indexation outcomes.
- **Used by:** the system applies a hard zero to scoring multipliers when a page is not indexed.

---

## P2-05 — Crawl budget utilisation

**Pillar:** Technical SEO
**Evidence weight:** Probable

### Step 1 — Definition
The efficiency with which Google's crawler allocates its limited per-site crawl budget across the site's URLs. Efficient utilisation means the crawler spends time on high-value, frequently updated, indexable pages rather than on low-value, error, or duplicate URLs.

### Step 1.5 — Evaluation rules
A site passes crawl budget utilisation when ALL of the following rules pass:

1. **Error response rate is low.** Pages returning 4xx or 5xx account for less than ~5% of total crawl requests in the GSC Crawl Stats window.
2. **Crawl is concentrated on canonical URLs.** At least 80% of crawl requests target canonical, indexable URLs (not duplicate variants, not noindexed pages, not redirected URLs).
3. **No high-volume crawl of parameterised duplicates.** Faceted-navigation parameter combinations, session ID variants, and tracking-parameter variants are not consuming significant crawl budget (handled via robots.txt, canonical tags, or `URL Parameters` GSC tool).
4. **Crawl frequency matches content cadence.** Frequently updated pages are recrawled frequently (within days for news/feeds, weekly for active blog/product pages); static reference content is recrawled less often. Recrawl pattern is consistent with content update pattern.
5. **No deep crawl pile-ups.** Pages at deeper crawl depths receive proportionally less attention but are still recrawled at reasonable cadence (orphan pages from P2-28 are flagged separately).
6. **Resource crawl is reasonable.** CSS, JS, and image crawl is not dominating budget (typically 30–50% of crawl requests); not dominated by polling-style resource fetches.
7. **No crawl-budget waste from infinite spaces.** Calendar widgets, search-result pages, and other infinite URL spaces are not generating endless URLs Google crawls.

A site passing all 7 rules has efficient crawl budget utilisation.

### Step 2 — Citations
1. **Google Search Central — Large Site Owner's Guide to Managing Crawl Budget** (https://developers.google.com/search/docs/crawling-indexing/large-site-managing-crawl-budget, Google, accessed May 2026). Google's authoritative documentation on crawl budget concepts. Specifically applies to sites with millions of URLs but the principles apply at smaller scale.
2. **Google Search Console — Crawl Stats report** (https://support.google.com/webmasters/answer/9679690, Google, accessed May 2026). Provides per-site crawl statistics including request count by purpose, response, and file type.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Crawl-budget-related considerations appear under Site-Level Factors.

### Step 3 — Evidence weight rationale
Google explicitly documents crawl budget. The Crawl Stats report provides observable data. Specific operational measurement of "good" vs "poor" utilisation varies. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: Google Search Console Crawl Stats API** for per-site crawl request counts, purposes, and response distribution.
- **Composition: our own** ratio analysis (e.g., percentage of crawl requests resulting in 4xx/5xx, percentage spent on non-canonical URLs, percentage spent on resources vs HTML).

### Step 5 — Verification
GSC Crawl Stats API is documented. Granularity required: per-site monthly crawl efficiency metrics. Granularity delivered: by composition.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Depends on:** P2-01 (robots.txt) — incorrectly blocked URLs waste budget; incorrectly allowed low-value URLs waste budget.
- **Cross-pillar:** P1-19 (URL depth) — deeper pages receive less crawl attention; P0-12 (pillar architecture) — well-organised hubs attract crawler attention to important pages.

---

## P2-06 — Index tier / source type (leaked) *(removed — May 2026 measurability audit)*

This variable was removed from the operational taxonomy in May 2026. The leaked Google feature `sourceType` is internal to Google's infrastructure and is not externally observable: no public API, no response header, and no other signal exposes a URL's tier assignment. The variable was recorded for "tracking and conceptual reasoning" rather than for operational use, but in practice it produced no measurement and contributed no recommendation — leaving it in the taxonomy created a false sense of coverage without paying any operational dividend. Where understanding of Google's indexation behaviour is needed, the externally-observable counterpart is **P2-04 — indexation status**, which captures the *outcome* Google honours (indexed / not indexed) without claiming visibility into Google's internal tier model. Any tier-related discussion should reference P2-04.

---

## P2-07 — Canonicalisation conflicts

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
Conflicting canonical signals exist for a URL. Examples: the page's canonical tag points to URL A but the sitemap lists URL B; internal links point predominantly to URL C; hreflang declares a different alternate. When signals conflict, Google chooses one canonical itself, often inconsistent with the site owner's intent.

### Step 1.5 — Evaluation rules
A URL passes canonicalisation conflict screening when ALL of the following rules pass:

1. **Declared canonical equals Google-selected canonical.** GSC URL Inspection API reports the user-declared canonical and Google's chosen canonical; they match.
2. **Sitemap URL equals declared canonical.** The URL listed in the XML sitemap is the same URL declared as canonical in the page's head.
3. **Dominant internal-link target equals declared canonical.** The variant most internal links point to is the same URL declared as canonical.
4. **Hreflang `x-default` and locale alternates do not conflict with canonical.** Hreflang declarations are reciprocal and do not point to URLs that are themselves canonicalised elsewhere.
5. **Scheme and host normalisation consistent.** The site uses one scheme (https) and one host variant (www or non-www) throughout; no mixed signals where canonical declares one and sitemap or links declare another.
6. **Trailing-slash policy consistent.** The site uses trailing slashes consistently or omits them consistently; canonical, sitemap, and internal links agree on the variant.
7. **No 301/302 redirect target mismatch.** Declared canonical resolves to itself with HTTP 200, not via a redirect chain to a different URL (which would imply the canonical is not actually the canonical).
8. **Pagination and faceted-navigation handled.** Paginated views (`?page=2`) and faceted views are handled by canonicalisation policy (typically self-referential with `noindex` for non-primary, or canonicalised to the first page) — not left ambiguous.

A URL passing all 8 rules has no canonicalisation conflicts.

### Step 2 — Citations
1. **Google Search Central — Consolidate Duplicate URLs (Canonicalization)** (https://developers.google.com/search/docs/crawling-indexing/canonicalization, Google, accessed May 2026). Documents how Google handles conflicting canonical signals and what factors it considers.
2. **Google Search Central — URL Inspection API** (https://developers.google.com/webmaster-tools/v1/urlInspection, Google). Reports the user-declared canonical and the Google-selected canonical separately, allowing detection of mismatches.
3. **DataForSEO On-Page documentation** — provides `canonical` field per page enabling cross-page signal comparison.

### Step 3 — Evidence weight rationale
Google explicitly documents canonicalisation and provides authoritative tooling for detecting Google's chosen canonical vs the declared one. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: GSC URL Inspection API** for the user-declared canonical vs Google-selected canonical mismatch detection.
- **Supplementary: DataForSEO** for declared canonical extraction at scale across all site URLs.

### Step 5 — Verification
Both APIs are documented. Conflict detection is composition (compare declared canonical against sitemap entries, internal link target distribution, Google-selected canonical). Granularity required: per-URL conflict status plus list of specific signal mismatches. Granularity delivered: by composition.

### Step 6 — Cost
Free (GSC) plus bundled (DataForSEO).

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-20 (canonical tag presence and self-reference).
- **Cross-pillar:** P1-46 (duplicate content) — duplicate content within site often manifests as canonicalisation conflicts.

---

## P2-08 — LCP (Largest Contentful Paint)

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The time required for the largest visible content element (image, video, or large text block) within the viewport to render after the page begins loading. A Core Web Vital with thresholds: ≤2.5 seconds = good; 2.5-4 seconds = needs improvement; >4 seconds = poor.

### Step 2 — Citations
1. **web.dev — Largest Contentful Paint (LCP)** (https://web.dev/articles/lcp, Google, accessed May 2026). Authoritative definition, measurement methodology, and thresholds.
2. **Google Search Central — Page Experience and Core Web Vitals** (https://developers.google.com/search/docs/appearance/page-experience, Google, accessed May 2026). Confirms Core Web Vitals are part of Google's page experience signals used in ranking.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #83 (Core Web Vitals).
4. **DataForSEO On-Page Instant Pages documentation** — provides `largest_contentful_paint` directly per page.

### Step 3 — Evidence weight rationale
LCP is officially documented by Google as a Core Web Vital and confirmed as part of page experience ranking signals. Direct measurement is provided by Google's own tooling and DataForSEO. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page API** field `largest_contentful_paint` per page (lab measurement).
- **Field measurement: Google CrUX (Chrome User Experience Report) API** for real-user LCP data — this is the version Google uses for ranking, derived from actual Chrome user data.
- **Diagnostic: Google PageSpeed Insights API** for both lab and field data plus optimisation suggestions.

### Step 5 — Verification
All three sources are documented. Granularity required: per-page LCP value (milliseconds) plus threshold classification. Granularity delivered: matches.

### Step 6 — Cost
DataForSEO: bundled. CrUX API: free with rate limits. PageSpeed Insights API: free with rate limits.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P1-30 (image dimensions and weight) — image weight is one of the largest LCP contributors. Optimising images directly improves LCP.

---

## P2-09 — INP (Interaction to Next Paint)

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The time from a user's interaction (click, tap, key press) to the next browser paint. Measures the responsiveness of the page during user interaction. Replaced First Input Delay (FID) as a Core Web Vital in March 2024. Thresholds (Google official): ≤200ms = good; >200ms and ≤500ms = needs improvement; >500ms = poor.

### Step 2 — Citations
1. **web.dev — Interaction to Next Paint (INP)** (https://web.dev/articles/inp, Google, accessed May 2026). Authoritative definition, measurement methodology, and thresholds.
2. **Google Search Central — Page Experience and Core Web Vitals** (https://developers.google.com/search/docs/appearance/page-experience, Google, accessed May 2026). Confirms INP is part of the Core Web Vitals used in page experience ranking signals.
3. **DataForSEO On-Page Instant Pages documentation** (https://docs.dataforseo.com/v3/on_page-instant_pages/, DataForSEO). Returns `first_input_delay` (legacy field name; see verification note).

### Step 3 — Evidence weight rationale
Officially documented by Google as a Core Web Vital and confirmed in page experience signals. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google CrUX (Chrome User Experience Report) API** for real-user INP data. Field measurement is what Google uses for ranking.
- **Lab measurement: Google PageSpeed Insights API** for synthetic INP-equivalent measurement (uses TBT as INP proxy in lab).
- **DataForSEO** provides legacy `first_input_delay` field which has been deprecated; primary source for our system is CrUX.

### Step 5 — Verification
CrUX API is documented and free. INP requires real-user data; pages without sufficient real-user traffic fall back to lab measurement (TBT proxy from PageSpeed Insights). Granularity required: per-page INP value (milliseconds) plus threshold classification. Granularity delivered: matches via CrUX where data exists, lab fallback otherwise.

### Step 6 — Cost
Free (CrUX, PageSpeed Insights APIs).

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P2-13 (TBT) — lab proxy for INP. P2-32 (lazy loading), P2-30 (page weight) — both contribute to JavaScript execution time which affects INP.

---

## P2-10 — CLS (Cumulative Layout Shift)

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The cumulative score of unexpected layout shifts that occur during the entire lifecycle of the page. A layout shift happens when a visible element changes its position from one rendered frame to the next. Thresholds (Google official): ≤0.1 = good; >0.1 and ≤0.25 = needs improvement; >0.25 = poor.

### Step 2 — Citations
1. **web.dev — Cumulative Layout Shift (CLS)** (https://web.dev/articles/cls, Google, accessed May 2026). Authoritative definition, measurement methodology, and thresholds.
2. **Google Search Central — Page Experience** (https://developers.google.com/search/docs/appearance/page-experience, Google). Confirms CLS as a Core Web Vital ranking input.
3. **DataForSEO On-Page Instant Pages documentation**. Returns `cumulative_layout_shift` field directly per page.

### Step 3 — Evidence weight rationale
Officially documented by Google as a Core Web Vital. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** `cumulative_layout_shift` field per page (lab measurement).
- **Field measurement: Google CrUX API** for real-user CLS — the version Google uses for ranking.

### Step 5 — Verification
DataForSEO confirms field returned per page. CrUX API documented. Granularity required: per-page CLS value (decimal) plus threshold classification. Granularity delivered: matches.

### Step 6 — Cost
DataForSEO: bundled. CrUX: free.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P1-30 (image dimensions and weight) — images without explicit dimensions are a primary cause of CLS. Setting `width` and `height` attributes resolves most CLS issues.

---

## P2-11 — TTFB (Time to First Byte)

**Pillar:** Technical SEO
**Evidence weight:** Probable

### Step 1 — Definition
The time from when the browser sends a request to when it receives the first byte of the response. Reflects server processing time, network latency, and time-to-establish-connection. Thresholds (Google supporting metric): ≤800ms = good; >800ms and ≤1.8s = needs improvement; >1.8s = poor.

### Step 2 — Citations
1. **web.dev — Time to First Byte (TTFB)** (https://web.dev/articles/ttfb, Google, accessed May 2026). Authoritative documentation listing TTFB as a supporting metric for diagnosing loading experience issues.
2. **Google Search Central — Core Web Vitals** documentation references TTFB as a foundational metric that influences LCP and other vitals.
3. **DataForSEO On-Page Instant Pages documentation**. Provides `waiting_time` field representing TTFB equivalent.

### Step 3 — Evidence weight rationale
Officially documented as a supporting metric, not a Core Web Vital itself. Influences ranking indirectly via LCP. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** `waiting_time` field per page.
- **Field measurement: Google CrUX API** for real-user TTFB.

### Step 5 — Verification
Both sources documented. Granularity required: per-page TTFB value (milliseconds). Granularity delivered: matches.

### Step 6 — Cost
DataForSEO bundled; CrUX free.

### Step 7 — Dependencies and cross-references
- **Foundational for:** P2-08 (LCP) — high TTFB compounds into high LCP.
- **Influenced by:** P2-21 (server location), hosting infrastructure, caching strategy.

---

## P2-12 — FCP (First Contentful Paint)

**Pillar:** Technical SEO
**Evidence weight:** Probable

### Step 1 — Definition
The time from when the page starts loading to when any portion of the page's content is rendered on the screen. Distinct from LCP (which measures the largest content element); FCP measures the very first visual change from blank. Thresholds (Google supporting metric): ≤1.8s = good; >1.8s and ≤3s = needs improvement; >3s = poor.

### Step 2 — Citations
1. **web.dev — First Contentful Paint (FCP)** (https://web.dev/articles/fcp, Google, accessed May 2026). Authoritative definition and thresholds.
2. **Google Search Central — Page Experience** documentation references FCP as a supporting metric for the loading experience.

### Step 3 — Evidence weight rationale
Officially documented as a supporting metric, not a Core Web Vital. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: Google PageSpeed Insights API** for FCP (both lab and field where available).
- **Supplementary: Google CrUX API** for real-user FCP.

### Step 5 — Verification
PageSpeed Insights and CrUX both documented. Granularity required: per-page FCP value (milliseconds). Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P2-08 (LCP), P2-11 (TTFB) — three timing metrics that together describe the loading experience.

---

## P2-13 — TBT (Total Blocking Time)

**Pillar:** Technical SEO
**Evidence weight:** Probable

### Step 1 — Definition
The total amount of time between First Contentful Paint (FCP) and Time to Interactive (TTI) during which the main thread was blocked for long enough to prevent input responsiveness. Lab-only metric used as a proxy for INP during development.

### Step 2 — Citations
1. **web.dev — Total Blocking Time (TBT)** (https://web.dev/articles/tbt, Google, accessed May 2026). Authoritative definition; documented as the lab proxy for INP.
2. **Google Lighthouse documentation** (https://developer.chrome.com/docs/lighthouse/performance/, Google). TBT is one of Lighthouse's core performance metrics for development-time measurement.

### Step 3 — Evidence weight rationale
Officially documented as a lab metric used during development. Not a field-measured Core Web Vital. Qualifies as **Probable**: useful for development diagnostics, not a direct ranking signal in itself.

### Step 4 — Data source(s)
- **Primary: Google PageSpeed Insights API** for TBT (lab measurement).
- **Lighthouse CLI** for local development testing.

### Step 5 — Verification
PageSpeed Insights API returns TBT per page. Granularity required: per-page TBT value (milliseconds). Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P2-09 (INP) — TBT is the lab proxy for the field-measured INP.

---

## P2-14 — Page loading speed via HTML

**Pillar:** Technical SEO
**Evidence weight:** Probable

### Step 1 — Definition
The total time required to fully load the page, measured from request initiation to fully-loaded state. An aggregate timing measure superseded operationally by the Core Web Vitals (LCP, INP, CLS) but still tracked as a holistic page-speed indicator.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #20 (Page Loading Speed via HTML).
2. **Google Search Central — Page Experience documentation** treats page speed as part of the broader page experience signal, with Core Web Vitals as the operational measurement.
3. **DataForSEO On-Page Instant Pages documentation**. Provides `duration_time` field directly.

### Step 3 — Evidence weight rationale
Practitioner factor superseded by Core Web Vitals as the operational measurement. Still tracked as a high-level summary metric. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** `duration_time` field (total fetch duration).

### Step 5 — Verification
DataForSEO confirms field returned. Granularity required: per-page total load time (milliseconds). Granularity delivered: matches.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Superseded by:** P2-08 (LCP), P2-09 (INP), P2-10 (CLS) for operational ranking purposes.
- **Useful for:** high-level reporting and developer diagnostics.

---

## P2-15 — Mobile responsiveness

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The page renders correctly and remains usable across mobile viewport sizes, with all content visible without horizontal scrolling, text legible without zooming, interactive elements appropriately sized for touch, and no functionality broken on mobile devices.

### Step 1.5 — Evaluation rules

A page passes mobile responsiveness when ALL of the following rules pass:

1. **Viewport meta tag present and correct.** Page has `<meta name="viewport" content="width=device-width, initial-scale=1">` (or equivalent) in the HTML head.
2. **No horizontal scrolling.** At common mobile viewport widths (360px, 375px, 414px), content fits within the viewport without horizontal overflow.
3. **Text size is legible.** Body text renders at 16 CSS pixels (or larger) on mobile devices, or scales appropriately via responsive typography. Text smaller than ~12px on mobile is flagged.
4. **Touch targets are adequately sized.** Interactive elements (buttons, links, form controls) have a minimum hit area of 48×48 CSS pixels per Google's mobile usability guidelines.
5. **Touch targets are adequately spaced.** Adjacent touch targets have at least 8 CSS pixels of spacing between them to prevent mistaps.
6. **Content does not require zoom to read.** No forced disabling of user-scalable behaviour (`user-scalable=no` or `maximum-scale=1.0` are flagged as accessibility violations).
7. **No mobile-specific content blocking.** Content available on desktop is also available on mobile (mobile-first indexing applies; cross-references P2-16).
8. **No fixed-position elements obstructing content.** Fixed headers, banners, and overlays do not consume more than ~15% of the viewport on mobile.
9. **Form controls render natively.** Mobile users can use the device's native input controls (date pickers, dropdowns) without custom implementations that break on touch.

A page passing all 9 rules is mobile-responsive. Each failure produces a specific named violation.

### Step 2 — Citations
1. **Google Search Central — Mobile-First Indexing** (https://developers.google.com/search/docs/crawling-indexing/mobile/mobile-sites-mobile-first-indexing, Google, accessed May 2026). Google indexes the mobile version of pages by default; mobile responsiveness is required for ranking.
2. **Google Search Central — Mobile Friendly Test** (https://search.google.com/test/mobile-friendly, Google). Provides authoritative per-page mobile-friendliness evaluation.
3. **Google PageSpeed Insights** mobile audit produces specific mobile usability findings.

### Step 3 — Evidence weight rationale
Mobile-first indexing is officially documented by Google. Mobile-friendliness is a confirmed ranking input. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google PageSpeed Insights API** mobile audit, which evaluates each rule above.
- **Supplementary: DataForSEO** for some rule checks (viewport meta detection via content extraction).

### Step 5 — Verification
PageSpeed Insights and Mobile Friendly Test both documented and free. Granularity required: per-page boolean plus list of specific rule failures. Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Foundational** — mobile-first indexing means failures here can prevent ranking entirely.
- **Cross-pillar:** P2-16 (mobile-friendly content) — content parity between mobile and desktop.

---

## P2-16 — Mobile-friendly content (no hidden content)

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The content available on the mobile version of the page matches the content on the desktop version. Under mobile-first indexing, Google primarily uses the mobile version for indexing and ranking; content shown only on desktop is invisible to Google.

### Step 1.5 — Evaluation rules

A page passes mobile content parity when ALL of the following rules pass:

1. **Primary content matches across versions.** Mobile and desktop versions deliver substantively the same primary text content, headings, and structured data.
2. **No critical content hidden behind tabs or expanders on mobile only.** Important content that is visible by default on desktop should be visible by default on mobile, or expandable with clear interaction patterns Google can render.
3. **No mobile-only "click to read more" walls.** Mobile pages don't truncate content with paywalls or interactions that block crawlers from reading the full content.
4. **Structured data present on both versions.** All schema.org markup on desktop is also on mobile (cross-references P1-21, P1-22).
5. **Internal links match.** Navigation and internal links present on desktop are accessible from mobile, even if reorganised.
6. **Images and media match.** Images, videos, and media files referenced on desktop are also referenced on mobile (with alt text and other metadata preserved).

### Step 2 — Citations
1. **Google Search Central — Mobile-First Indexing Best Practices** (https://developers.google.com/search/docs/crawling-indexing/mobile/mobile-sites-mobile-first-indexing#best-practices, Google, accessed May 2026). Authoritative guidance on content parity between mobile and desktop versions.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #38 ("Hidden" Content on Mobile) and #40 (Content Hidden Behind Tabs).

### Step 3 — Evidence weight rationale
Google explicitly states mobile content is the primary indexing source under mobile-first indexing. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: dual-fetch via DataForSEO** with mobile and desktop user-agent configurations; compare extracted content.
- **Verification: Google Mobile Friendly Test** and URL Inspection API render comparison.

### Step 5 — Verification
DataForSEO supports user-agent configuration. Content comparison is composition (text similarity, structured data diff, link inventory diff). Granularity required: per-page content parity boolean plus list of differences. Granularity delivered: by composition.

### Step 6 — Cost
Bundled (DataForSEO double-audit) or free (Mobile Friendly Test). Approximately 2× standard audit cost when running dual-fetch.

### Step 7 — Dependencies and cross-references
- **Depends on:** P2-15 (mobile responsiveness) — mobile content parity assumes mobile renders at all.
- **Cross-references:** P1-21 (schema markup), P1-22 (schema validity) — must apply to mobile version.

---

## P2-17 — Mobile usability score

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The aggregate mobile usability score returned by Google PageSpeed Insights' mobile audit, plus the specific list of detected mobile issues. Score ranges 0–100; specific issues map to actionable findings. The score aggregates the rule outcomes from P2-15 (mobile responsiveness) and P2-16 (mobile content parity) plus additional Google-specific checks.

### Step 2 — Citations
1. **Google PageSpeed Insights** (https://pagespeed.web.dev/, Google, accessed May 2026). Returns mobile-specific audit findings as part of every mobile run, including Lighthouse-derived audit pass/fail per check.
2. **Google Search Central — Mobile-First Indexing** (https://developers.google.com/search/docs/crawling-indexing/mobile/mobile-sites-mobile-first-indexing, Google). Confirms mobile usability is part of the mobile-first indexing readiness signal.

### Step 3 — Evidence weight rationale
Officially measured and reported by Google's own tooling. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google PageSpeed Insights API** mobile audit returns aggregate score plus individual audit findings.

### Step 5 — Verification
PageSpeed Insights API documented and free. Granularity required: per-page numeric score (0–100) plus list of specific failing audits. Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Aggregates:** P2-15 (mobile responsiveness rules) and P2-16 (mobile content parity rules) plus PageSpeed-specific Lighthouse audits.
- **Used by:** dashboard reporting (single-number summary) plus underlying rule violations from P2-15/P2-16 for actionable recommendations.

---

## P2-18 — HTTPS / SSL certificate

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The site serves all content over HTTPS with a valid SSL/TLS certificate. Includes that the certificate is currently valid, properly chained, signed by a trusted authority, and configured with current TLS protocols and ciphers.

### Step 1.5 — Evaluation rules

A site passes HTTPS / SSL when ALL of the following rules pass:

1. **All page URLs use HTTPS scheme.** No HTTP-only pages exist on indexable URLs.
2. **HTTP requests redirect to HTTPS.** Any request to `http://{domain}/...` returns a 301 or 308 redirect to the HTTPS equivalent.
3. **Certificate is currently valid.** Not expired, not yet valid, not revoked.
4. **Certificate matches the domain.** The `subject` or `subjectAlternativeName` covers the requested hostname including www and root domain variants used by the site.
5. **Certificate chain is complete.** All intermediate certificates served alongside the leaf so browsers can validate without fetching missing chain elements.
6. **Certificate is signed by a trusted root.** Certificate authority is in standard browser/OS trust stores (Let's Encrypt, DigiCert, Sectigo, etc.). Self-signed certificates fail.
7. **TLS protocol version is current.** Server supports TLS 1.2 or TLS 1.3. SSL 2.0/3.0 and TLS 1.0/1.1 are not exclusively offered.
8. **No mixed content on indexable pages.** HTTPS pages do not load HTTP-served resources (images, scripts, stylesheets) — these trigger browser warnings and Google demotion signals.
9. **Certificate transparency log entry exists.** Modern certificates are CT-logged; absence is unusual and may indicate misconfiguration.

A failure on any rule produces a specific named violation.

### Step 2 — Citations
1. **Google Search Central — Secure your site with HTTPS** (https://developers.google.com/search/docs/advanced/security/https, Google, accessed May 2026). Authoritative documentation listing HTTPS as a confirmed lightweight ranking signal.
2. **Google Security Blog — HTTPS as a ranking signal (2014, reaffirmed)** (https://security.googleblog.com/2014/08/https-as-ranking-signal_6.html, Google). Original announcement; subsequently reinforced as Google has marked all non-HTTPS pages as "Not Secure" in Chrome.
3. **DataForSEO On-Page Instant Pages documentation**. Provides `is_https` and `is_http` boolean checks plus protocol-related findings.

### Step 3 — Evidence weight rationale
Google has explicitly confirmed HTTPS as a ranking signal and a baseline expectation for modern web. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** for `is_https`, mixed content detection (`https_to_http_links` check).
- **Certificate detail: SSL Labs API or our own TLS handshake** for protocol versions, certificate chain, expiry.
- **Domain-level: regular cert expiry monitoring** via cron task.

### Step 5 — Verification
DataForSEO covers the basic protocol and mixed-content checks. Detailed certificate validation requires either SSL Labs API or our own TLS-handshake logic. Granularity required: per-site rule-level pass/fail against the 9 rules in Step 1.5. Granularity delivered: by composition.

### Step 6 — Cost
DataForSEO bundled. SSL Labs API free for occasional use. Cron-based cert expiry checks negligible.

### Step 7 — Dependencies and cross-references
- **Foundational** — sites failing here cannot rank well regardless of other optimisations.
- **Cross-references:** P2-19 (HSTS) — HSTS depends on HTTPS being correctly configured first.

---

## P2-19 — HSTS configuration

**Pillar:** Technical SEO
**Evidence weight:** Probable

### Step 1 — Definition
The site sends the `Strict-Transport-Security` HTTP response header, instructing browsers to always use HTTPS for the domain even if the user types `http://`. HSTS strengthens HTTPS enforcement by removing the brief HTTP-to-HTTPS redirect window where attacks can occur.

### Step 1.5 — Evaluation rules

A site passes HSTS configuration when ALL of the following rules pass:

1. **HSTS header is sent.** The HTTP response header `Strict-Transport-Security:` is present on at least the root domain HTTPS response.
2. **`max-age` directive is set.** The header includes `max-age=N` where N is a positive integer (seconds).
3. **`max-age` is at least 31,536,000 seconds (1 year).** Shorter values weaken protection. Production sites should set 1+ year.
4. **`includeSubDomains` directive is present** if the site uses subdomains that should also be HTTPS-only. Sites without subdomains may safely omit this.
5. **`preload` directive is present** for sites that have submitted to the HSTS preload list (https://hstspreload.org/). Preload provides protection on first visit before the header has been seen.
6. **Domain is on the HSTS preload list** (optional but recommended for production sites).

A site missing HSTS entirely fails Rule 1; partial implementations (e.g., HSTS with short max-age) fail individual rules below.

### Step 2 — Citations
1. **MDN Web Docs — Strict-Transport-Security** (https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security, Mozilla, accessed May 2026). Authoritative documentation for the HTTP header specification.
2. **Google Web Fundamentals — HSTS** (https://web.dev/articles/preload-csp, Google). Documents HSTS as a security best practice for HTTPS sites.
3. **HSTS Preload List submission** (https://hstspreload.org/, Chromium project). Maintained list of domains pre-loaded with HSTS in major browsers.

### Step 3 — Evidence weight rationale
HSTS is a recognised security best practice and component of HTTPS hardening. Not a directly named ranking factor by Google. Qualifies as **Probable** as a security-and-trust signal that supports the HTTPS ranking baseline.

### Step 4 — Data source(s)
- **Primary: HTTP HEAD request to root domain** to inspect response headers.
- **Preload list check: HSTS Preload List API or static download** of the published list.

### Step 5 — Verification
HTTP header inspection is trivial. Preload list lookup is straightforward. Granularity required: per-site pass/fail against each Step 1.5 rule. Granularity delivered: by composition.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Depends on:** P2-18 (HTTPS) — HSTS only meaningful when HTTPS is correctly configured.

---

## P2-20 — Site uptime

**Pillar:** Technical SEO
**Evidence weight:** Probable

### Step 1 — Definition
The percentage of time the site is reachable and returning successful HTTP responses (200-class) over a measurement window. Sites with frequent downtime risk being de-indexed; consistent availability is a baseline for crawler trust.

### Step 2 — Citations
1. **Google Search Central — John Mueller statements** (multiple official communications). Google has indicated that prolonged downtime can affect indexing; brief outages are usually tolerated.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #72 (Site Uptime).
3. **Industry standard SLAs.** Web hosting and CDN providers publish uptime guarantees (typically 99.9%+) reflecting industry expectations.

### Step 3 — Evidence weight rationale
Practitioner consensus, indirect Google support. Not a directly named ranking factor with specific thresholds. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: external uptime monitoring** via UptimeRobot, StatusCake, Pingdom, or our own cron-based health checks.
- **Frequency:** at least 5-minute intervals for production sites.

### Step 5 — Verification
Uptime monitoring tools are mature and widely available. Granularity required: per-site uptime percentage over rolling 30-day window plus list of incidents. Granularity delivered: matches.

### Step 6 — Cost
UptimeRobot free tier covers up to 50 monitors at 5-minute intervals. Sufficient for pilot scale. Paid tiers required at SaaS scale.

### Step 7 — Dependencies and cross-references
- **No upstream dependency** — primary measurement.
- **Used by:** site-level health scoring; persistent low uptime reduces all other recommendation confidence (since recommendations require the site to be reachable).

---

## P2-21 — Server location

**Pillar:** Technical SEO
**Evidence weight:** Speculative

### Step 1 — Definition
The geographic location of the server hosting the site. Affects TTFB for users in different regions and was historically considered a soft signal for geographic relevance (e.g., a UK-targeted site hosted in the UK).

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #73 (Server Location). Backlinko cites this as a historical practitioner factor.
2. **Google Search Central — John Mueller statements** (multiple). Google has stated server location is not a ranking factor for geographic targeting; ccTLD or hreflang are the primary geographic signals.
3. **CDN industry coverage.** Modern CDN deployment makes server location largely irrelevant since content is served from edge nodes globally.

### Step 3 — Evidence weight rationale
Google has explicitly denied server location as a ranking factor for geographic targeting. CDNs make the original server location largely invisible to users. Practitioner sources still mention it but its contemporary relevance is minimal. Qualifies as **Speculative** for direct ranking impact, with the note that TTFB indirectly captures any server-location performance impact.

### Step 4 — Data source(s)
- **Primary: DNS lookup of A record + IP geolocation** via free GeoIP databases (MaxMind, ip-api.com).

### Step 5 — Verification
IP geolocation is widely available. Granularity required: per-site server country plus CDN status (is the site behind a CDN, in which case "server location" reflects edge node distribution rather than origin). Granularity delivered: by composition.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Watchlist entry.** Per Model B, tracked but does not drive recommendations.
- **Subsumed by:** P2-11 (TTFB) — actual user-experienced server performance is the meaningful measurement, and TTFB captures it directly regardless of server geography.

---

## P2-22 — JavaScript rendering pattern (CSR/SSR/SSG/ISR)

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The rendering strategy used by the site to deliver content to browsers and crawlers. Categorical: CSR (Client-Side Rendering — content rendered by JavaScript after page load), SSR (Server-Side Rendering — content fully rendered on server before delivery), SSG (Static Site Generation — pre-built HTML files), ISR (Incremental Static Regeneration — hybrid SSG with on-demand revalidation), or hybrid combinations. CSR-only sites have known SEO disadvantages because crawlers may not execute JS to discover content.

### Step 1.5 — Evaluation rules

A page passes JS rendering correctness when ALL of the following rules pass:

1. **Primary content is in initial HTML.** A request without JS execution returns the page's main heading, body content, and meta tags (title, meta description, canonical) directly in the HTML response.
2. **Internal links are crawlable without JS.** Links in the navigation and content area are present in the initial HTML as `<a href>` elements, not JavaScript-only routing handlers.
3. **Structured data is in initial HTML.** Schema markup (`<script type="application/ld+json">`) is delivered server-side, not injected post-load.
4. **Critical metadata is in initial HTML.** Title tag, meta description, canonical, robots meta, and Open Graph tags are in the HTML head as delivered.
5. **No CSR-only fallback for content.** Pages do not show "Loading..." or empty content as the initial HTML, requiring JS execution to render any meaningful content.
6. **JS rendering produces same content as HTML.** When JS does execute (for users with JS enabled), it does not replace or contradict the SSR content with different content (which would confuse Google's rendering pipeline).

A page passes when all 6 rules pass. CSR-only pages typically fail rules 1, 2, 3, 4, and 5. SSR/SSG/ISR pages typically pass.

### Step 2 — Citations
1. **Google Search Central — JavaScript SEO Basics** (https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics, Google, accessed May 2026). Authoritative documentation on how Googlebot processes JavaScript and the rendering challenges of CSR-only sites.
2. **web.dev — Rendering on the Web** (https://web.dev/articles/rendering-on-the-web, Google). Documents the four major rendering patterns (CSR, SSR, SSG, ISR) with SEO implications for each.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). References the JS rendering issue under technical site factors.

### Step 3 — Evidence weight rationale
Google explicitly documents the rendering challenges and recommendations. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: dual-fetch comparison.** Fetch the page once with JS disabled (raw HTML) and once with JS enabled (DataForSEO can do both), compare content presence in both versions.
- **Detection logic: our own.** If raw HTML lacks content but JS-rendered version has it, the page is CSR-dependent.

### Step 5 — Verification
DataForSEO supports both raw HTML fetch and JS-rendered fetch. Comparison is composition (text similarity between the two versions). Granularity required: per-page rendering category plus list of specific rule failures. Granularity delivered: by composition.

### Step 6 — Cost
Bundled (DataForSEO supports both fetch modes) or 2× audit cost when running both modes.

### Step 7 — Dependencies and cross-references
- **Foundational** — CSR-only sites have severe SEO limitations. Recommendations from the system on CSR sites must be framed honestly: "this metadata change won't help unless the page is server-rendered."
- **Cross-pillar:** the previous project's "ssr_not_detected" flag in `site_health_flags` is the same concept; the system should mark CSR-only pages and apply Tier 3 (manual deployment) handling.

---

## P2-23 — Crawl depth from homepage

**Pillar:** Technical SEO
**Evidence weight:** Probable

### Step 1 — Definition
The minimum number of clicks (internal link traversals) required to reach a page starting from the homepage. Measured as graph distance, not URL path depth. Pages with high crawl depth receive less crawl attention and are more likely to be missed during indexing.

### Step 2 — Citations
1. **Google Search Central — Site Architecture and Crawl Budget** (https://developers.google.com/search/docs/crawling-indexing/large-site-managing-crawl-budget, Google, accessed May 2026). Recommends important pages be reachable within a few clicks from the homepage.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #69 (Site Architecture) references hierarchical depth.
3. **DataForSEO On-Page Instant Pages documentation**. Provides `click_depth` field per page (link-graph distance from a starting page).

### Step 3 — Evidence weight rationale
Google's crawl budget guidance supports the principle. Backlinko corroborates. Specific operational threshold (e.g., "deeper than 4 clicks is bad") is not officially endorsed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** `click_depth` field per page from full-site audit.

### Step 5 — Verification
DataForSEO confirms field returned. Granularity required: per-page integer depth from homepage. Granularity delivered: matches. **Caveat:** click depth is meaningful only with full-site audit, not single-page audit.

### Step 6 — Cost
Bundled with full-site audit.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P1-19 (URL depth from root) — different measurement: P1-19 counts URL path segments; P2-23 counts graph distance. A page can have shallow URL but deep click depth, or vice versa.
- **Used by:** internal linking recommendations to surface deep-but-valuable pages closer to the homepage.

---

## P2-24 — Status code distribution

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The distribution of HTTP status codes returned by the site's URLs across a full crawl: 200 (OK, healthy), 301 (permanent redirect), 302 (temporary redirect), 304 (not modified), 404 (not found), 410 (gone), 5xx (server errors). The healthy distribution is dominated by 200s with minimal 4xx/5xx.

### Step 1.5 — Evaluation rules

A site passes status code health when ALL of the following rules pass:

1. **At least 95% of crawled URLs return 200.** A high proportion of non-200 responses suggests broken links or misconfigurations.
2. **No 5xx errors on indexable URLs.** Server errors prevent indexation and damage crawl trust.
3. **404 errors are limited.** Less than 5% of crawled URLs return 404. Persistent 404s on previously-indexed URLs should redirect to relevant alternatives or return 410 (gone) if intentionally removed.
4. **No redirect loops.** No URL eventually redirects back to itself or a previous URL in the chain.
5. **Redirect chains are short.** No URL requires more than 2 redirect hops to reach final destination (3+ hops is Level 5 hard-blocked from auto-deployment).
6. **301 used for permanent moves.** Permanent URL changes use 301 (or 308) status, not 302 (which Google may interpret as temporary and not transfer ranking signal).
7. **404s on important pages are detected and addressed.** Pages that previously had backlinks or organic traffic should not silently 404.
8. **No status code mismatches.** Pages returning 200 do not also have noindex meta or robots.txt block (logical inconsistency that creates indexation conflicts).

A site passing all 8 rules has healthy status code distribution.

### Step 2 — Citations
1. **Google Search Central — Status code reference** (https://developers.google.com/search/docs/crawling-indexing/http-network-errors, Google, accessed May 2026). Documents how Google interprets each HTTP status code.
2. **DataForSEO On-Page Instant Pages documentation**. Provides per-page `status_code` plus `is_4xx_code`, `is_5xx_code`, `is_redirect`, `is_broken` boolean checks.

### Step 3 — Evidence weight rationale
Google explicitly documents status code handling. The mechanics are universally understood. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** per-page status code in full-site audit. Aggregation across the site produces the distribution.
- **Redirect chain tracing: our own** logic following 301/302 sequences from each URL until terminal status reached.

### Step 5 — Verification
DataForSEO confirms status code per page. Distribution computation and chain tracing are composition. Granularity required: per-site distribution table plus per-URL classification. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Used by:** broken-link detection (P2-26, P2-27), redirect chain detection (P2-25), orphan page detection (P2-28).
- **Cross-pillar:** P1-15 (site health) — status code distribution is a primary site-health input.

---

## P2-25 — Redirect chains (3+ hops)

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
A sequence of HTTP redirects where a request for one URL is redirected to another, which is redirected again, and so on, until reaching a terminal URL. Chains of 3 or more hops compound latency, dilute ranking signal, and are flagged by Google as a problem.

### Step 1.5 — Evaluation rules

A site passes redirect-chain hygiene when ALL of the following rules pass:

1. **No URL has a chain longer than 2 redirects** (i.e. the longest chain on the site is at most A→B→C, where C is the terminal URL with status 200).
2. **No redirect loops exist.** No URL eventually redirects back to itself or to any URL earlier in the chain.
3. **All redirects use 301 (permanent) for permanent moves** rather than 302 (temporary). 302 may not transfer ranking signal.
4. **Terminal URLs return 200** (not 4xx or 5xx). A redirect chain ending in 404 should be flattened or eliminated.
5. **No redirects to URLs blocked by robots.txt or noindex.** Such chains waste crawl budget and confuse indexation.
6. **Internal links point directly to terminal URLs**, not to intermediate redirects. Internal links should be updated to point to the final destination.

A chain of 3+ hops fails Rule 1 and triggers Level 5 hard-block from auto-deployment per the project's risk model.

### Step 2 — Citations
1. **Google Search Central — Redirects and Google Search** (https://developers.google.com/search/docs/crawling-indexing/301-redirects, Google, accessed May 2026). Authoritative documentation on redirect handling. Google explicitly warns about long redirect chains and recommends flattening them.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #103 (Excessive 301 Redirects to Page) and Factor #174 (Redirects).
3. **DataForSEO On-Page Instant Pages documentation** — provides `is_redirect` boolean and `location` field per page, plus chain detection via repeated calls.

### Step 3 — Evidence weight rationale
Google explicitly documents redirect chain handling and warns against long chains. Direct ranking impact via signal dilution and crawl budget waste. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** per-URL status code and location fields plus our own chain-tracing logic that follows redirects until a terminal status is reached.

### Step 5 — Verification
Chain tracing is straightforward (follow `location` headers until non-redirect status). Granularity required: per-URL chain length plus full chain trace. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P2-24 (status code distribution).
- **Hard-block trigger:** redirect chains 3+ hops are Level 5 in the project's risk model — never auto-deployed even when detected.

---

## P2-26 — Internal broken links

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The count and list of internal links on the site that point to URLs returning HTTP 4xx or 5xx status codes. Internal broken links waste crawl budget, fragment internal authority flow, and damage user experience.

### Step 2 — Citations
1. **Google Search Central — How to Build a Search-Friendly Site** (https://developers.google.com/search/docs/fundamentals/seo-starter-guide, Google, accessed May 2026). Recommends ensuring all internal links work and lead to valid destinations.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #45 (Broken Links).
3. **DataForSEO On-Page Instant Pages documentation** — provides `broken_links` boolean indicator per page plus full link inventory in full-site audits.

### Step 3 — Evidence weight rationale
Google explicitly recommends fixing broken internal links. Direct usability impact. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** per-link status checking in full-site audit mode.

### Step 5 — Verification
DataForSEO confirms broken-link detection. Granularity required: per-site count and list of broken internal links plus the source page hosting each broken reference. Granularity delivered: matches.

### Step 6 — Cost
Bundled with full-site audit.

### Step 7 — Dependencies and cross-references
- **Depends on:** P2-24 (status code distribution).
- **Cross-pillar:** P1-23 (internal inbound link count) — broken outbound links from a page reduce its outbound link quality, but more importantly broken inbound links to a page reduce its inbound link count.

---

## P2-27 — External broken links

**Pillar:** Technical SEO
**Evidence weight:** Probable

### Step 1 — Definition
Outbound external links from the site that point to URLs returning HTTP 4xx or 5xx status codes. Less harmful than internal broken links but signal stale content maintenance and can be picked up as quality issues by Google's content quality systems.

### Step 2 — Citations
1. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends content remains accurate and current; broken external citations indicate stale content.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #45 (Broken Links) covers both internal and external.
3. **DataForSEO On-Page Instant Pages documentation** — link inventory includes both internal and external; status checking can be applied to both.

### Step 3 — Evidence weight rationale
Practitioner consensus on broken external links as a content quality issue, supported indirectly by Google's helpful content guidance. Less impactful than internal broken links. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** external link inventory plus URL status checking. External link checking is more expensive than internal because it requires HTTP requests to external domains.

### Step 5 — Verification
DataForSEO supports external link status checking. Granularity required: per-site count and list of broken external links with source pages. Granularity delivered: matches.

### Step 6 — Cost
Bundled in DataForSEO full-site audit when external checking is enabled. May add cost for very large external link inventories.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P1-26 (outbound link quality and theme) — broken outbound links degrade outbound link quality directly.

---

## P2-28 — Orphan pages

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
Pages that exist on the site (returning 200 status, listed in the sitemap, or otherwise discoverable) but have zero internal inbound links from any other page on the site. Orphan pages are hard for Google to discover, receive minimal authority via internal linking, and often signal abandoned content.

### Step 2 — Citations
1. **Google Search Central — Help Google find your content** (https://developers.google.com/search/docs/fundamentals/seo-starter-guide, Google, accessed May 2026). Internal linking is the primary discovery mechanism for Googlebot; orphan pages may not be discovered without sitemap submission.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Authority flow analysis treats zero-inbound pages as orphans.
3. **DataForSEO On-Page documentation** — `inbound_links_count` field directly identifies orphan pages (count = 0).

### Step 3 — Evidence weight rationale
Google explicitly recommends internal linking for content discovery. Orphan detection is universally accepted. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** `inbound_links_count` field per page from full-site audit. Orphans are pages with `inbound_links_count == 0` (excluding homepage).

### Step 5 — Verification
DataForSEO confirms inbound link counts. Granularity required: per-site list of orphan pages. Granularity delivered: matches.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-23 (internal inbound link count).
- **Cross-pillar:** P0-12 (pillar architecture) — orphan pages within a topic cluster indicate architectural gaps; the pillar should link to all cluster pages.
- **Used by:** internal linking recommendations to either link the orphan into relevant clusters or remove it if no longer relevant.

---

## P2-29 — HTML errors / W3C validation

**Pillar:** Technical SEO
**Evidence weight:** Probable

### Step 1 — Definition
The page's HTML markup parses correctly without errors when checked against the W3C HTML specification. Includes correct DOCTYPE, well-formed tag nesting, valid attribute syntax, proper character encoding, and absence of deprecated tags.

### Step 1.5 — Evaluation rules

A page passes HTML validation when ALL of the following rules pass:

1. **DOCTYPE is present and HTML5.** The first line of the document declares `<!DOCTYPE html>`.
2. **Character encoding is declared.** The document declares its encoding via `<meta charset="utf-8">` or HTTP `Content-Type` header.
3. **Tag nesting is well-formed.** No unclosed tags, no overlapping tags (e.g., `<b><i>text</b></i>`), no incorrectly nested block-inside-inline elements.
4. **Required attributes present where mandatory.** `<img>` elements have `alt`; `<a>` elements have `href`; `<form>` elements have `action`; etc.
5. **No deprecated tags.** Tags like `<font>`, `<center>`, `<marquee>` are not used (use CSS instead).
6. **Single `<title>` and `<head>` per document.** Multiple `<title>` elements or split heads are flagged.
7. **No unescaped reserved characters.** Ampersands, less-than, greater-than properly escaped in text content.
8. **Heading hierarchy is logical.** No `<h1>` inside `<h2>`, no skipped levels (cross-references P1-15).

A page fails individual rules with specific error reports. Modern browsers tolerate many of these violations, but parsers (including Googlebot's) may behave inconsistently.

### Step 2 — Citations
1. **W3C — HTML Living Standard** (https://html.spec.whatwg.org/, W3C, accessed May 2026). Authoritative HTML specification.
2. **W3C Markup Validation Service** (https://validator.w3.org/, W3C). Validates HTML against the specification.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #48 (HTML Errors/W3C Validation). Backlinko cites this as a soft signal — Google has stated HTML validation is not directly a ranking factor, but malformed HTML can break parsing.
4. **DataForSEO On-Page Instant Pages documentation** — provides `resource_errors` with parsing errors and `deprecated_tags` array.

### Step 3 — Evidence weight rationale
W3C provides authoritative validation. Google has stated HTML validation per se is not a ranking factor, but Google has also said malformed HTML can affect rendering and content extraction. Practitioners disagree on its weight. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** `resource_errors` and `deprecated_tags` from page audit.
- **Detailed validation: W3C Markup Validation Service** API for full per-page error reports.

### Step 5 — Verification
DataForSEO covers basic checks; W3C Validator covers comprehensive validation. Granularity required: per-page list of specific HTML errors and warnings. Granularity delivered: matches.

### Step 6 — Cost
DataForSEO bundled. W3C Validator free with rate limits.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P1-15 (heading hierarchy correctness) — Rule 8 above overlaps with the heading hierarchy variable.

---

## P2-30 — Page weight

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The total transferred byte size of the page including HTML, CSS, JavaScript, images, fonts, and other resources. Heavy pages load slowly and consume more user bandwidth, directly affecting Core Web Vitals (especially LCP) and mobile usability. Threshold guidance: target under 1 MB for mobile-friendly pages; >3 MB is flagged as oversized.

### Step 2 — Citations
1. **web.dev — Page weight optimisation** (https://web.dev/articles/fast/, Google, accessed May 2026). Documents the relationship between page weight and Core Web Vitals.
2. **HTTP Archive Web Almanac** (https://almanac.httparchive.org/, accessed May 2026). Annual research on web performance trends, with median page weight benchmarks.
3. **DataForSEO On-Page Instant Pages documentation** — provides `total_transfer_size`, `size`, `encoded_size`, plus `size_greater_than_3mb` boolean check.

### Step 3 — Evidence weight rationale
Page weight directly affects Core Web Vitals which are confirmed ranking signals. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** `total_transfer_size` per page (compressed) and `size` (uncompressed).

### Step 5 — Verification
DataForSEO confirms size fields. Granularity required: per-page byte count plus threshold classification. Granularity delivered: matches.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P1-30 (image dimensions and weight) — images are typically the largest weight contributor. P2-08 (LCP) — page weight is a primary LCP determinant.

---

## P2-31 — Image format efficiency (WebP, AVIF)

**Pillar:** Technical SEO
**Evidence weight:** Probable

### Step 1 — Definition
The proportion of images on the page served in modern efficient formats (WebP, AVIF) versus legacy formats (JPEG, PNG). Modern formats achieve 25–50% smaller file sizes at equivalent visual quality, directly improving page weight and LCP.

### Step 2 — Citations
1. **web.dev — Image optimisation** (https://web.dev/articles/use-webp-and-avif, Google, accessed May 2026). Documents WebP and AVIF as recommended modern image formats.
2. **Google PageSpeed Insights audits** flag images that could be served in next-gen formats with specific savings estimates per image.
3. **DataForSEO On-Page Instant Pages documentation** — image details include format detection.

### Step 3 — Evidence weight rationale
Google's tooling explicitly identifies legacy image formats as optimisation targets. Direct impact on page weight and Core Web Vitals. Qualifies as **Probable** (the impact is real but the size of the impact varies by site and format).

### Step 4 — Data source(s)
- **Primary: DataForSEO** per-image format detection.
- **Supplementary: Google PageSpeed Insights** "Serve images in next-gen formats" audit with specific recommendations and savings per image.

### Step 5 — Verification
Both sources documented. Granularity required: per-page percentage of images using modern formats plus list of legacy-format images. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P1-30 (image dimensions and weight), P2-08 (LCP) — modern formats reduce image weight directly.

---

## P2-32 — Lazy loading implementation

**Pillar:** Technical SEO
**Evidence weight:** Probable

### Step 1 — Definition
The use of native lazy loading (`loading="lazy"` attribute on `<img>` elements) for non-critical images that appear below the initial viewport. Lazy loading defers loading of images until they are about to enter the viewport, reducing initial page weight and improving LCP for above-the-fold content.

### Step 1.5 — Evaluation rules

A page passes lazy loading correctness when ALL of the following rules pass:

1. **Below-the-fold images use `loading="lazy"`.** Images that appear below the initial viewport (estimated based on typical mobile viewport heights) should have the lazy attribute.
2. **Above-the-fold images do NOT use `loading="lazy"`.** The largest visible image in the initial viewport (typically the LCP element) should NOT be lazy-loaded — lazy-loading the LCP image actually delays LCP.
3. **Lazy-loaded images have explicit dimensions.** `width` and `height` attributes (or CSS aspect-ratio) prevent layout shift when lazy-loaded images load (cross-references P2-10 CLS).
4. **No JavaScript-based lazy loading on critical images.** Native `loading="lazy"` is preferred; custom JavaScript lazy-load libraries can delay rendering and cause CLS issues if not configured correctly.
5. **Iframe elements use `loading="lazy"` where below-fold.** The same lazy loading pattern applies to embedded iframes (videos, maps).

The classic mistake is lazy-loading the LCP image, which damages LCP. Rule 2 catches this.

### Step 2 — Citations
1. **web.dev — Browser-level image lazy loading** (https://web.dev/articles/browser-level-image-lazy-loading, Google, accessed May 2026). Authoritative documentation on the `loading="lazy"` attribute.
2. **MDN Web Docs — `loading` attribute** (https://developer.mozilla.org/en-US/docs/Web/HTML/Element/img#loading, Mozilla). Cross-browser support and behaviour reference.
3. **Google PageSpeed Insights audits** include "Defer offscreen images" recommendations.

### Step 3 — Evidence weight rationale
Native lazy loading is a documented browser feature with direct page-weight benefits. Google's tooling recommends it explicitly. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** image details from full-site audit including `loading` attribute presence.
- **Above-fold determination: composition.** Estimating which images are above-the-fold requires viewport-aware analysis (typically based on the first 600-800 vertical pixels for mobile).

### Step 5 — Verification
DataForSEO returns image attribute data. Above-fold determination is composition. Granularity required: per-page list of images with lazy-loading status plus above-fold flag. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P2-08 (LCP) — incorrect lazy loading of LCP element directly damages LCP. P2-10 (CLS) — lazy-loaded images without explicit dimensions cause CLS.

---

## P2-33 — Hreflang tags

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
For sites with multiple language or regional variants, the `hreflang` attribute declares each variant's language/region pairing and their reciprocal relationships. Hreflang tells Google which variant to serve to users in different regions.

### Step 1.5 — Evaluation rules

A site with international variants passes hreflang correctness when ALL of the following rules pass:

1. **Each variant declares hreflang.** Every regional/language version of a page includes `<link rel="alternate" hreflang="x" href="...">` tags.
2. **Reciprocal references exist.** If page A references page B with hreflang, page B must reciprocally reference page A. Missing reciprocity invalidates the hreflang for both pages in Google's interpretation.
3. **`x-default` is declared.** A fallback variant is specified using `hreflang="x-default"` for users whose locale doesn't match any specified variant.
4. **Self-referencing hreflang exists.** Each page references itself in its own hreflang set (the hreflang declarations include the current page's URL).
5. **Language codes follow ISO 639-1.** Two-letter codes like `en`, `es`, `de`, `fr`, `zh` (not `eng`, `spa`).
6. **Country codes follow ISO 3166-1 alpha-2.** Two-letter codes like `US`, `GB`, `DE`, `FR`. Combined as `en-US`, `en-GB`.
7. **All hreflang URLs return 200.** No hreflang references point to redirected, removed, or noindex pages.
8. **Hreflang doesn't conflict with canonical.** A page's canonical does not point to a different language variant; canonicals stay within the same variant.
9. **Hreflang implementation is consistent across delivery method.** Whether implemented in HTML head, HTTP header, or sitemap, all pages use the same method.

### Step 2 — Citations
1. **Google Search Central — Tell Google about localised versions of your page** (https://developers.google.com/search/docs/specialty/international/localized-versions, Google, accessed May 2026). Authoritative documentation on hreflang implementation and validation rules.
2. **Aleyda Solis — Hreflang Tags Generator and SEO Resources** (https://www.aleydasolis.com/, accessed May 2026). Practitioner reference for hreflang correctness.
3. **DataForSEO On-Page Instant Pages documentation**. Returns hreflang tag inventory via content extraction.

### Step 3 — Evidence weight rationale
Google explicitly documents hreflang rules and validates them in Search Console. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO** content extraction for hreflang tag inventory per page.
- **Validation logic: our own.** Walk the hreflang graph across the site and check reciprocity, code validity, URL status, canonical conflicts.

### Step 5 — Verification
DataForSEO confirms tag extraction. Validation logic is composition. Granularity required: per-site hreflang status plus per-page list of specific rule failures. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P1-20 (canonical tag) — canonical and hreflang interact; conflicts produce indexation issues. P2-04 (indexation status) — broken hreflang can cause variants to be ignored.
- **Applicability:** only relevant for sites with international/multilingual variants. Single-locale sites are exempt.

---

## P2-34 — llms.txt configuration *(removed — see P6-18)*

This variable was removed in the May 2026 deduplication audit. The llms.txt declaration is documented as a single canonical entry in **P6-18 — llms.txt declaration** (Pillar 6 — AI Search / GEO). Any technical-pillar reference should link to P6-18.

---

## P2-35 — AI bot access in robots.txt *(removed — see P6-17)*

This variable was removed in the May 2026 deduplication audit. LLM-bot crawler access (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, Common Crawl) is documented as a single canonical entry in **P6-17 — LLM-bot crawler access** (Pillar 6 — AI Search / GEO), which extends and supersedes the previous P2-35 framing. Any technical-pillar reference should link to P6-17.

---

## P2-36 — IndexNow protocol adoption

**Pillar:** Technical SEO
**Evidence weight:** Probable

### Step 1 — Definition
The site uses the IndexNow protocol to push URL change notifications to participating search engines (currently Bing, Yandex, Naver, and Seznam — Google does NOT participate). IndexNow accelerates discovery of new and updated content compared to passive crawling.

### Step 2 — Citations
1. **IndexNow specification** (https://www.indexnow.org/, accessed May 2026). The cross-engine open protocol jointly published by Microsoft and Yandex.
2. **Bing Webmaster — IndexNow documentation** (https://www.bing.com/webmasters/url-submission-api, Microsoft, accessed May 2026). Bing's authoritative documentation on IndexNow integration.
3. **Google has explicitly declined to adopt IndexNow** (multiple Google statements, including from John Mueller and Search Liaison). For Google, the equivalent is the Indexing API which is restricted to JobPosting and BroadcastEvent content types.

### Step 3 — Evidence weight rationale
Bing and Yandex officially document IndexNow. Adoption helps with non-Google engines but provides no Google ranking benefit (Google does not consume IndexNow). Qualifies as **Probable** — beneficial for non-Google search visibility, neutral for Google.

### Step 4 — Data source(s)
- **Primary: composition.** Detection of IndexNow usage requires either site-owner attestation or observation of IndexNow API calls in server logs.
- **Implementation evidence: presence of IndexNow API key file** at the URL declared in IndexNow setup (e.g., `/{key}.txt`).

### Step 5 — Verification
Detection is straightforward but requires either log access or a configuration declaration. Granularity required: per-site adoption boolean plus implementation health. Granularity delivered: by composition.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Limited applicability:** sites with Bing/Yandex traffic benefit; sites with Google-only audience get little value.
- **Cross-pillar:** P5 (Local SEO) — Bing's local results and Apple Maps benefit from IndexNow updates; relevant for local-targeted sites.

---

## P2-37 — Pop-ups and intrusive interstitials

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The page does not show intrusive interstitials, pop-ups, or overlays that block primary content from users on mobile devices. Google has explicitly identified intrusive interstitials as a mobile ranking demotion factor since 2017.

### Step 1.5 — Evaluation rules

A page passes intrusive interstitial check when ALL of the following rules pass:

1. **No full-page interstitial blocks content immediately on load.** A page-covering overlay that requires dismissal before content is accessible fails this rule.
2. **No content-blocking overlays appear during scroll on mobile.** Content remains accessible without dismissing pop-ups.
3. **Cookie consent banners are exempt** if they comply with applicable laws (GDPR, CCPA) and the dismissal/configuration controls are reasonably accessible. Google has clarified that legally-required cookie banners are not penalised.
4. **Login walls on YMYL or paywalled content are exempt.** If the site's business model legitimately requires login (e.g. paid subscription content), the login wall is exempt provided it's not deceptive about content availability.
5. **Age verification gates are exempt** when legally required.
6. **No newsletter signup pop-ups appear before user interaction.** Pop-ups triggered immediately on page load damage user experience.
7. **Newsletter signup pop-ups triggered after engagement (scroll, time on page) are tolerated** — exit-intent or scroll-triggered pop-ups are not subject to the demotion.

### Step 2 — Citations
1. **Google Search Central — Avoid intrusive interstitials and dialogs** (https://developers.google.com/search/docs/appearance/avoid-intrusive-interstitials, Google, accessed May 2026). Authoritative documentation on which interstitials are penalised and which are exempt.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #175 (Popups or "Distracting Ads") and Factor #176 (Interstitial Popups).

### Step 3 — Evidence weight rationale
Google explicitly documents the intrusive interstitial demotion as a mobile ranking signal. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google PageSpeed Insights mobile audit** flags some intrusive interstitial patterns.
- **Programmatic detection: composition.** Render the page with Playwright (or similar) and detect overlays meeting criteria (covers >50% of viewport, blocks scroll, no immediate-dismiss control).

### Step 5 — Verification
PageSpeed Insights captures some patterns; programmatic detection covers more. Granularity required: per-page presence/absence of intrusive interstitial plus type classification. Granularity delivered: by composition.

### Step 6 — Cost
PageSpeed Insights free. Custom rendering detection adds compute cost (already covered by DataForSEO crawler).

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P2-15 (mobile responsiveness) — overlapping concern; intrusive interstitials damage mobile usability.

---

## P2-38 — Ads-above-the-fold density

**Pillar:** Technical SEO
**Evidence weight:** Probable

### Step 1 — Definition
The proportion of the initial viewport (above the fold) consumed by advertising content. Pages with excessive above-fold advertising density push primary content below the fold, damaging user experience and triggering Google's Page Layout Algorithm demotion.

### Step 2 — Citations
1. **Google Webmaster Central Blog — Page Layout Algorithm Improvement** (announced 2012, reaffirmed multiple times). Google's "top heavy" algorithm explicitly demotes pages with excessive above-fold advertising.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #180 (Ads Above the Fold).
3. **Google Search Central — Page Experience guidance** indirectly supports this through page experience ranking signals.

### Step 3 — Evidence weight rationale
Google has officially documented and reaffirmed the Page Layout Algorithm. Direct ranking impact when triggered. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: rendered page screenshot analysis.** Capture initial viewport screenshot, identify ad regions (via class names like `.ad`, `.advertisement`, ad network domains in iframes), compute area as percentage of viewport.

### Step 5 — Verification
Composition over rendered output. Granularity required: per-page above-fold ad density percentage plus list of detected ad regions. Granularity delivered: by composition.

### Step 6 — Cost
Bundled with rendering crawl.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P2-37 (intrusive interstitials) — overlapping concern about content accessibility.

---

## P2-39 — Use of AMP (deprecated 2024)

**Pillar:** Technical SEO
**Evidence weight:** Speculative

### Step 1 — Definition
Whether the page implements Accelerated Mobile Pages (AMP), an HTML framework Google promoted from 2015 for faster mobile loading. Google deprecated AMP as a Top Stories carousel requirement in 2021 and as a separate ranking consideration thereafter; modern Core Web Vitals subsume the performance benefit AMP provided.

### Step 2 — Citations
1. **Google Search Central — AMP and Top Stories** (https://developers.google.com/search/docs/appearance/google-news/about, Google, accessed May 2026). Documents AMP no longer being a requirement for Top Stories carousel since 2021.
2. **AMP Project documentation** (https://amp.dev/, AMP Project). Still maintained but with reduced industry adoption.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #21 (Use of AMP) is now historical context.

### Step 3 — Evidence weight rationale
AMP is deprecated as a ranking input. Modern Core Web Vitals provide the same performance benefits. Detection is still useful for legacy sites considering migration, but AMP itself does not improve rankings. Qualifies as **Speculative** for current ranking impact.

### Step 4 — Data source(s)
- **Primary: DataForSEO** detection of AMP markup (`<html amp>` or `<html ⚡>` attribute) and AMP-specific URL pattern (`/amp/` paths).

### Step 5 — Verification
AMP detection is a binary HTML check. Granularity required: per-page AMP presence boolean. Granularity delivered: matches.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Watchlist / migration-advisory entry.** For sites still using AMP, the recommendation is typically migration to standard HTML with strong Core Web Vitals.

---

## P2-40 — Host age

**Pillar:** Technical SEO
**Evidence weight:** Speculative

### Step 1 — Definition
The leaked Google feature `hostAge` measuring how long the site's hostname has been active in Google's index. Older established hosts may receive trust signals not available to newly-launched sites.

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names `hostAge` as a feature in Google's content warehouse, alongside `createdDate` and `expiredDate` for domain registration.
2. **No corroborating Tier A or B source.** Google has not officially confirmed how `hostAge` influences ranking, and has historically denied that domain age is a direct ranking factor.

### Step 3 — Evidence weight rationale
Single source (the leak). The mechanism's existence is plausible — a tracked timestamp of when Google first encountered the host — but its operational impact on ranking is undocumented. Qualifies as **Speculative**.

### Step 4 — Data source(s)
- **Approximation: composition.** WHOIS lookup for domain registration date plus archive.org first-crawl date plus first-known GSC data point. None directly equal Google's internal `hostAge` but together they approximate.

### Step 5 — Verification
WHOIS is documented and accessible. archive.org first-snapshot date is publicly available. Granularity required: per-site age measurement plus source for the measurement. Granularity delivered: by approximation.

### Step 6 — Cost
WHOIS lookups: free or low-cost via several providers. archive.org: free.

### Step 7 — Dependencies and cross-references
- **Watchlist entry.**
- **Note:** the previous project tracked `hostAge` in code but the operational use was unclear. Per Model B, we capture the value but don't drive recommendations from it until evidence emerges.

---

## P2-41 — Site update cadence

**Pillar:** Technical SEO
**Evidence weight:** Probable

### Step 1 — Definition
The site-wide rate at which new pages are published and existing pages are substantively updated, measured as page-publication-events per quarter. Distinct from page-level update cadence (P1-45); this aggregates across all pages on the site.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #70 (Site Updates).
2. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends maintained, current content. Site-wide cadence reflects whether the site is actively maintained.
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). FreshnessTwiddler and QualityBoost systems use update signals; site-wide cadence may inform site-level freshness scoring.

### Step 3 — Evidence weight rationale
Practitioner consensus, indirect Google support via Helpful Content. Specific cadence-to-ranking impact is not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition over historical DataForSEO crawl snapshots** plus sitemap last-modified dates plus GSC Index Coverage data on new URLs over time.
- **Cadence calculation: our own** rolling-window aggregation (publications/month, updates/month, total active URLs growth).

### Step 5 — Verification
DataForSEO, sitemap, and GSC data sources all documented. Granularity required: per-site cadence statistics over rolling windows. Granularity delivered: by composition. **Caveat:** requires accumulated history.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P1-44 (page-level update magnitude), P1-45 (page-level update cadence), P4-01 (publishing cadence at content operations level) — same concepts at different scopes.

---

## P2-42 — Sitemap priority weighting per URL

**Pillar:** Technical SEO
**Evidence weight:** Speculative

### Step 1 — Definition
The optional `priority` (0.0–1.0) and `changefreq` (`always`, `hourly`, `daily`, `weekly`, `monthly`, `yearly`, `never`) values declared per URL in the XML sitemap. The protocol allows site owners to indicate relative importance and update frequency to crawlers.

### Step 2 — Citations
1. **sitemaps.org — Sitemap Protocol** (https://www.sitemaps.org/protocol.html, accessed May 2026). Defines priority and changefreq elements as optional sitemap metadata.
2. **Google Search Central — John Mueller statements** (multiple official communications). Google has explicitly stated that priority and changefreq values in sitemaps are largely ignored by Google's crawler — Google determines priority and re-crawl frequency from its own signals, not site-declared values.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #59 (Priority of Page in Sitemap) is listed as a historical practitioner factor.

### Step 3 — Evidence weight rationale
Google explicitly states these values are ignored. Other engines (Bing) may use them but with low weight. Not a meaningful Google ranking input. Qualifies as **Speculative** — recorded for completeness but not actionable for Google ranking purposes.

### Step 4 — Data source(s)
- **Primary: sitemap parsing** for declared priority and changefreq values.

### Step 5 — Verification
Sitemap parsing is trivial. Granularity required: per-URL declared values plus aggregate distribution. Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Watchlist entry** for Google ranking purposes; relevant for Bing/non-Google search engines.
- **Cross-references:** P2-02 (sitemap presence and validity).

---

## P2-43 — Duplicate content handling at site level

**Pillar:** Technical SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The site-wide configuration of mechanisms that prevent crawler-visible duplicate content arising from URL parameters, session IDs, sorting/filtering parameters, faceted navigation, pagination, printable versions, and other URL-generation patterns. Distinct from page-level duplicate content (P1-46); this is about the URL-handling infrastructure that prevents duplicates.

### Step 1.5 — Evaluation rules

A site passes site-level duplicate content handling when ALL of the following rules pass:

1. **No session IDs in indexable URLs.** Session-tracking IDs (PHPSESSID, JSESSIONID, etc.) are stripped from URLs Googlebot sees, or set as cookies rather than URL parameters.
2. **URL parameters that don't change content are stripped or canonicalised.** Tracking parameters (utm_*, fbclid, gclid, etc.) point canonicals to the parameter-less URL.
3. **Sort and filter parameters either canonical to base URL or use noindex.** Faceted navigation (color=red, size=large, sort=price) doesn't generate indexable duplicates.
4. **Pagination is handled correctly.** Paginated series (`/products?page=2`) either use `rel="next"`/`rel="prev"` (deprecated but harmless), self-canonical to the paginated URL, or canonical to a "view all" page.
5. **Printable versions are blocked or canonicalised.** Pages like `/print/article` use canonical pointing to the main version, or are blocked from indexing.
6. **HTTP and HTTPS are not both indexable.** Site enforces HTTPS via redirect (cross-references P2-18).
7. **www and non-www variants are not both indexable.** Site enforces one preferred host via redirect.
8. **Trailing slash inconsistencies are resolved.** Either `/page` or `/page/` is the canonical form, not both indexable separately.
9. **Mobile-specific URL patterns canonicalise correctly.** If a site uses separate `/m/` or `m.domain.com` URLs (legacy pattern), they canonical to desktop equivalents.

A site passing all 9 rules has clean site-level duplicate handling.

### Step 2 — Citations
1. **Google Search Central — Consolidate Duplicate URLs** (https://developers.google.com/search/docs/crawling-indexing/canonicalization, Google, accessed May 2026). Documents site-level duplicate content patterns and the canonical-and-redirect strategies for handling them.
2. **Google Search Central — Crawl budget guide** (https://developers.google.com/search/docs/crawling-indexing/large-site-managing-crawl-budget, Google). Identifies duplicate URL generation as a primary crawl budget waste pattern.
3. **DataForSEO** `duplicate_content` detection at site level plus per-URL duplicate flags.

### Step 3 — Evidence weight rationale
Google explicitly documents site-level duplicate content patterns and the consolidation mechanisms for them. Direct impact on crawl budget and indexation efficiency. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: composition.** Crawl URL inventory + parameter analysis + redirect chain tracing + canonical inventory.
- **Detection logic: our own** pattern recognition for known duplicate-generating mechanisms (session IDs in URLs, common tracking parameters, faceted nav patterns, pagination patterns).

### Step 5 — Verification
DataForSEO provides per-URL canonical and status; composition layer detects site-level patterns. Granularity required: per-site list of detected duplicate mechanisms plus rule-by-rule status. Granularity delivered: by composition.

### Step 6 — Cost
Bundled with full-site audit.

### Step 7 — Dependencies and cross-references
- **Depends on:** P1-20 (canonical tag), P2-07 (canonicalisation conflicts), P2-25 (redirect chains).
- **Cross-pillar:** P1-46 (duplicate content within site at page level) — site-level handling prevents most page-level duplicates from being created.

---



# Pillar 3 — Off-Page Authority

**Total candidates:** 39
**Status:** Complete (39 of 39; P3-11, P3-13, P3-16 removed in May 2026 measurability audit as externally unmeasurable leak features. All retained as redirect notes.)

## Pillar 3 Index

| ID | Variable | Status | Weight |
|----|----------|--------|--------|
| P3-01 | Total referring root domains count | Complete | Consensus |
| P3-02 | Referring domain DR/DA distribution | Complete | Probable |
| P3-03 | Linking domain age | Complete | Probable |
| P3-04 | Number of linking pages | Complete | Consensus |
| P3-05 | Total backlinks | Complete | Consensus |
| P3-06 | Backlinks from .edu/.gov domains | Complete | Contested |
| P3-07 | Authority of linking page | Complete | Probable |
| P3-08 | Homepage PageRank (homepagePagerankNs) | Complete | Probable |
| P3-09 | Site-wide authority score (siteAuthority) | Complete | Probable |
| P3-10 | Page-level PageRank (PageRankNS) | Complete | Probable |
| P3-11 | IndyRank (independent rank) | Removed | — |
| P3-12 | Anchor text distribution | Complete | Consensus |
| P3-13 | Anchor text font size (leak) | Removed | — |
| P3-14 | Anchor mismatch demotion (leak) | Complete | Probable |
| P3-15 | Anchor spam phrase count (leak) | Complete | Probable |
| P3-16 | Dropped local anchor count (leak) | Removed | — |
| P3-17 | Dofollow vs nofollow ratio | Complete | Probable |
| P3-18 | Sponsored / UGC link tags | Complete | Consensus |
| P3-19 | Contextual links (in-content vs sidebar/footer) | Complete | Probable |
| P3-20 | Link location in content | Complete | Probable |
| P3-21 | Linking domain topical relevance | Complete | Consensus |
| P3-22 | Linking domain country TLD | Complete | Probable |
| P3-23 | C-class IP diversity of links | Complete | Probable |
| P3-24 | Backlink velocity (positive) | Complete | Probable |
| P3-25 | Backlink velocity (negative / loss rate) | Complete | Probable |
| P3-26 | Backlink age | Complete | Probable |
| P3-27 | Co-occurrences (brand + topic mentions) | Complete | Probable |
| P3-28 | Linked-as-Wikipedia source | Complete | Probable |
| P3-29 | Toxic backlink presence | Complete | Consensus |
| P3-30 | Disavow tool usage | Complete | Consensus |
| P3-31 | Reciprocal link ratio | Complete | Probable |
| P3-32 | Brand mention frequency (linked + unlinked) | Complete | Probable |
| P3-33 | Forum links | Complete | Probable |
| P3-34 | Hub page links | Complete | Probable |
| P3-35 | Authority-site links | Complete | Consensus |
| P3-36 | Guest post links | Complete | Probable |
| P3-37 | Widget links | Complete | Probable |
| P3-38 | Press-release / article-directory links | Complete | Probable |
| P3-39 | Sitewide vs single-page links | Complete | Probable |

---

## P3-01 — Total referring root domains count

**Pillar:** Off-Page Authority
**Evidence weight:** Consensus

### Step 1 — Definition
The total count of unique root domains that have at least one backlink pointing to any URL on the site. A foundational off-page authority metric: more referring domains generally indicates broader recognition and authority.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #85 (Number of Linking Root Domains). One of the most consistently cited correlative ranking factors across multiple ranking studies (Searchmetrics, Backlinko, SparkToro, Ahrefs).
2. **Google — How Search Works (PageRank concept)** (https://www.google.com/search/howsearchworks/, Google, accessed May 2026). Google has historically described PageRank-style signals as inputs to ranking; referring domains are the primary input to PageRank computation.
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leak references PageRank-style features including `homepagePagerankNs`, `IndyRank`, and `siteAuthority` — all derived from referring domains.
4. **DataForSEO Backlinks Summary API documentation** (https://docs.dataforseo.com/v3/backlinks/summary/, DataForSEO, accessed May 2026). Returns `referring_domains` field per target site.

### Step 3 — Evidence weight rationale
Universally accepted as a foundational off-page authority signal. Practitioner consensus, leak features confirm Google computes domain-graph metrics, no reputable source disputes the principle. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Backlinks Summary API** field `referring_domains`.

### Step 5 — Verification
DataForSEO documentation confirms `referring_domains` is returned per target. Granularity required: per-site integer count plus historical trajectory. Granularity delivered: matches.

### Step 6 — Cost
DataForSEO Backlinks Summary: approximately $0.01–$0.05 per query (one per site refresh, typically monthly cadence). For pilot site monthly refresh, approximately £0.50–£1/month.

### Step 7 — Dependencies and cross-references
- **Foundational** — feeds nearly all P3 authority calculations.
- **Cross-references:** P3-02 (DR/DA distribution), P3-08 (homepage PageRank), P3-09 (site authority).

---

## P3-02 — Referring domain DR/DA distribution

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The distribution of domain authority (DR / DA) values across the site's referring domains. A site with 100 referring domains all rated DR 70+ is in a different position from one with 100 referring domains rated DR 5–20. The distribution shape (mean, median, count above thresholds) reflects link profile quality.

### Step 2 — Citations
1. **Ahrefs — Domain Rating methodology** (https://ahrefs.com/blog/domain-rating/, Ahrefs, accessed May 2026). Methodology for DR computation as a logarithmic 0–100 score derived from link juice passed from linking domains.
2. **Moz — Domain Authority** (https://moz.com/learn/seo/domain-authority/, Moz, accessed May 2026). Moz's DA methodology, distinct from but conceptually similar to Ahrefs DR.
3. **DataForSEO Backlinks API documentation**. Returns referring domains with their per-domain authority scores.
4. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #92 (Authority of Linking Domain).

### Step 3 — Evidence weight rationale
Domain authority distributions are universally tracked across major SEO tools. Specific authority computations vary by provider. Google does not officially endorse third-party DR/DA scores but the underlying concept (PageRank-style domain-level authority) is reflected in leaked features. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Backlinks API** referring domain inventory with per-domain authority.
- **Distribution computation: our own.** Aggregate per-domain authority into distribution statistics (mean, median, count by tier).

### Step 5 — Verification
DataForSEO returns referring domain inventory at scale (paginated). Distribution computation is composition. Granularity required: per-site distribution plus list of high-authority and low-authority referring domains. Granularity delivered: by composition.

### Step 6 — Cost
Per-referring-domain lookup cost. For 100 referring domains, approximately £1–£3 per refresh.

### Step 7 — Dependencies and cross-references
- **Depends on:** P3-01 (referring domains count).
- **Cross-references:** P3-29 (toxic backlinks) — heavily skewed distribution toward low-authority domains often correlates with toxic-link patterns.

---

## P3-03 — Linking domain age

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The age (years since first registered or first observed) of the domains linking to the site. Older established domains often correlate with stronger trust signals, though Google has not officially confirmed domain age as a direct ranking factor.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #84 (Linking Domain Age).
2. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leak references `hostAge` and `createdDate` features — confirming Google tracks domain-age data, even if its specific use is not officially documented.
3. **Google Search Central — John Mueller statements** (multiple). Google has stated domain age is not a direct ranking factor for the site itself; whether it influences linking-domain authority is less clear.

### Step 3 — Evidence weight rationale
Practitioner factor with leak corroboration. Direct ranking impact unconfirmed. Older linking domains may simply correlate with stronger general authority rather than age specifically. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: WHOIS lookup** for each linking domain's registration date.
- **Supplementary: archive.org first-snapshot date** as proxy for first-observed date.
- **Aggregation: our own** average and distribution across linking domains.

### Step 5 — Verification
WHOIS and archive.org are publicly accessible. Granularity required: per-linking-domain age plus aggregated distribution. Granularity delivered: by composition.

### Step 6 — Cost
WHOIS lookups: free or low-cost via several providers.

### Step 7 — Dependencies and cross-references
- **Depends on:** P3-01 (linking domain inventory).
- **Cross-pillar:** P2-40 (host age) — same concept applied to the target site rather than linking sites.

---

## P3-04 — Number of linking pages

**Pillar:** Off-Page Authority
**Evidence weight:** Consensus

### Step 1 — Definition
The total number of unique URLs (across all referring domains) that link to any URL on the site. Distinct from referring domains count: a single domain may have many linking pages.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #87 (Number of Linking Pages).
2. **DataForSEO Backlinks Summary API**. Returns `backlinks` field representing total backlinks count.

### Step 3 — Evidence weight rationale
Foundational metric universally tracked. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Backlinks Summary API** field `backlinks`.

### Step 5 — Verification
Documented field. Granularity required: per-site integer count. Granularity delivered: matches.

### Step 6 — Cost
Bundled with referring domain query.

### Step 7 — Dependencies and cross-references
- **Companion to:** P3-01 (referring domains). The ratio of total backlinks to referring domains indicates link-density per source — many backlinks from few domains may indicate sitewide footer links rather than diverse authority.

---

## P3-05 — Total backlinks

**Pillar:** Off-Page Authority
**Evidence weight:** Consensus

### Step 1 — Definition
The total count of all individual link instances pointing to the site, including multiple links from the same source page (rare) and multiple linking pages from the same domain. Distinct from P3-04 (linking pages) only when a single page has multiple links to the target site.

### Step 2 — Citations
1. **Industry standard metric** tracked by all major backlink data providers (Ahrefs, Semrush, DataForSEO, Moz).
2. **DataForSEO Backlinks Summary API**. Returns total backlink count.

### Step 3 — Evidence weight rationale
Universally tracked, no source disputes. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Backlinks Summary API** field for total backlinks.

### Step 5 — Verification
Documented. Granularity required: per-site integer count. Granularity delivered: matches.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Related to:** P3-04 (linking pages). Total backlinks ≥ linking pages because some pages contain multiple links to the target.

---

## P3-06 — Backlinks from .edu / .gov domains

**Pillar:** Off-Page Authority
**Evidence weight:** Contested

### Step 1 — Definition
Backlinks from domains using `.edu` (educational institutions) or `.gov` (government) top-level domains. Practitioner consensus has long treated these as inherently more authoritative; Google has explicitly stated TLDs are not weighted differently.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #90 (Links from .edu or .gov Domains). Backlinko cites correlative observations that .edu/.gov links correlate with higher rankings.
2. **Google Search Central — Matt Cutts and John Mueller statements** (multiple, dating back to 2009). Google has explicitly and repeatedly stated that .edu and .gov TLDs are not weighted differently from other TLDs as ranking signals; the perceived authority comes from the typically high domain authority of these institutions, not the TLD itself.
3. **DataForSEO Backlinks API**. Allows filtering and identifying backlinks by TLD pattern.

### Step 3 — Evidence weight rationale
Practitioner observation says yes (correlative); Google explicitly says no. The two positions are in direct contradiction. The honest interpretation: .edu and .gov sites tend to have high authority because they're institutionally established, but the TLD itself is not the signal. Qualifies as **Contested**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Backlinks API** with TLD filter or post-hoc filtering of referring domains by TLD suffix.

### Step 5 — Verification
TLD filtering is straightforward. Granularity required: per-site count of referring domains by TLD plus list of specific .edu/.gov referring domains. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Framing note:** when this variable surfaces in recommendations, the user-facing language should reflect the contested nature — high-DR .edu/.gov links are valuable because of authority, not because of TLD. Recommendations to "get .edu links" without considering authority are misleading.

---

## P3-07 — Authority of linking page

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The page-level authority score (URL Rating equivalent) of the specific page hosting the backlink, distinct from the linking domain's overall authority. A backlink from a high-authority page on a moderate-DR domain may pass more value than a low-authority page on a high-DR domain.

### Step 2 — Citations
1. **Ahrefs — URL Rating** (https://ahrefs.com/blog/url-rating/, Ahrefs, accessed May 2026). Defines page-level authority computation methodology, distinct from domain-level DR.
2. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names `PageRankNS` as a per-document feature, confirming Google maintains page-level (not just domain-level) authority computation.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #91 (Authority of Linking Page).

### Step 3 — Evidence weight rationale
Page-level authority is a fundamental concept (PageRank was originally page-level). Leak features confirm Google maintains per-document scores. Specific operational measurement varies by provider. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Backlinks API** returns per-backlink data including the linking page's own authority.

### Step 5 — Verification
DataForSEO returns linking page authority at scale. Granularity required: per-backlink linking page authority plus aggregated distribution. Granularity delivered: by composition.

### Step 6 — Cost
Bundled with backlink inventory query.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-10 (PageRankNS leak feature) — same concept named in the leak. P3-02 (domain DR distribution) — page-level authority and domain-level authority are correlated but distinct.

---

## P3-08 — Homepage PageRank (homepagePagerankNs)

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The leaked Google feature `homepagePagerankNs` representing the homepage's internally-computed PageRank score. Reflects the site's overall authority as expressed through its primary entry point. Used internally as a site-level authority proxy.

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names `homepagePagerankNs` as a feature in Google's content warehouse, confirming Google computes per-domain homepage authority and uses it as an input to ranking.
2. **Google — Original PageRank paper (Page, Brin, 1998)**. The foundational concept; Google has confirmed it still uses PageRank-derived signals internally even though the public Toolbar PageRank was retired in 2016.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #98 (Homepage Authority).

### Step 3 — Evidence weight rationale
Leak feature confirms the metric exists in Google's infrastructure. Conceptually well-understood. Specific operational weight not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Approximation: DataForSEO** domain rating for the homepage URL specifically (as a proxy for Google's internal homepage PageRank).

### Step 5 — Verification
DataForSEO homepage authority is a proxy, not the literal Google `homepagePagerankNs`. Granularity required: per-site homepage authority score (0–100 scale). Granularity delivered: by approximation.

### Step 6 — Cost
Bundled with site-level backlink summary.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-09 (site authority `siteAuthority`), P3-10 (`PageRankNS` per-page), P3-11 (`IndyRank`) — all leak features in the same authority cluster.

---

## P3-09 — Site-wide authority score (siteAuthority)

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The leaked Google feature `siteAuthority` representing Google's internal site-level authority score. Aggregates link signals, brand signals, and quality indicators into a per-site score that influences how all pages on the site are ranked.

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names `siteAuthority` as a per-site feature in Google's content warehouse. Mike King's analysis identifies it as one of the most operationally important leak findings — site-level authority directly contradicts Google's previous public statements that site-wide authority scores do not exist.
2. **Cyrus Shepard — Google Leak Analysis** (industry coverage of the leak, accessed May 2026). Confirms `siteAuthority` as a tracked feature.
3. **Industry analysis of post-leak Google statements**. Google has not officially confirmed or denied this specific feature, but the existence of site-level scoring is now broadly accepted in SEO research.

### Step 3 — Evidence weight rationale
Leak feature with broad SEO research consensus that the score exists and matters. Specific operational weight not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Approximation: composition** combining DataForSEO domain rating + referring domain quality distribution + brand search volume (P0-15) + Knowledge Graph entity status (P0-16).

### Step 5 — Verification
The literal `siteAuthority` value is not observable. Our composition approximates it as a multi-signal site-authority score. Granularity required: per-site authority score (0–100). Granularity delivered: by approximation.

### Step 6 — Cost
Bundled with other backlink and brand data calls.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-08 (homepage PageRank), P3-10 (page-level PageRank), P3-11 (IndyRank), P0-07 (site focus score) — all components of overall site authority computation.

---

## P3-10 — Page-level PageRank (PageRankNS)

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The leaked Google feature `PageRankNS` representing per-document PageRank score. Reflects the page's authority as computed via PageRank-style iteration over the global link graph, distinct from site-level authority.

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names `PageRankNS` as a per-page feature, confirming Google maintains per-document PageRank scores.
2. **Original Google PageRank paper (Page, Brin, 1998)**. The foundational concept; despite the public Toolbar PageRank being retired in 2016, Google has confirmed PageRank-derived signals are still computed internally.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #50 (Page's PageRank).

### Step 3 — Evidence weight rationale
Leak feature confirms Google maintains per-page authority scores. PageRank is foundational. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Approximation: DataForSEO** per-page domain rating equivalent (URL Rating proxy).

### Step 5 — Verification
DataForSEO returns per-URL authority as a proxy. Granularity required: per-page authority score. Granularity delivered: by approximation.

### Step 6 — Cost
Bundled with backlink data.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P1-24 (internal inbound link quality) — uses page-level authority for the linking-source weighting.

---

## P3-11 — IndyRank (independent rank) *(removed — May 2026 measurability audit)*

This variable was removed from the operational taxonomy in May 2026. The leaked Google feature `IndyRank` is internal to Google's infrastructure and is not externally observable: there is no public API, no response header, and no proxy that exposes it. The taxonomy entry itself recorded "not directly observable" as the data-source status and assigned **Speculative** weight on a single source with mechanism unclear — leaving it in the taxonomy produced no measurement and no recommendation. Where page-level authority needs to be referenced, **P3-10 — Page-level PageRank** is the canonical leak entry (also internal, but with a documented DataForSEO URL-rating approximation path).

---

## P3-12 — Anchor text distribution

**Pillar:** Off-Page Authority
**Evidence weight:** Consensus

### Step 1 — Definition
The distribution of anchor text patterns across all backlinks pointing to the site, classified into categories: branded (contains brand name), naked URL (just the URL as text), exact-match (matches a target keyword), partial-match (contains keyword variants), generic (e.g., "click here", "read more"), and image (alt text from image links).

### Step 1.5 — Evaluation rules

A site passes anchor text distribution health when ALL of the following rules pass:

1. **Branded anchors are the largest category** (typically 30–50% of total anchors). Heavily branded distributions reflect organic linking.
2. **Naked URL anchors are present** (typically 15–30%). Indicates organic citation patterns.
3. **Exact-match anchors are below 10–15% of total**. Higher proportions suggest manipulation and may trigger Penguin-style anchor spam demotion.
4. **No single anchor phrase exceeds 5% of total backlinks**. Concentration on one phrase is a manipulation signal.
5. **Anchor diversity exists.** At least 20+ unique anchor phrases across backlinks for a site with substantial backlink count.
6. **Generic anchors aren't the majority.** "Click here", "read more" indicate low-quality linking patterns.
7. **Anchor text matches destination relevance.** Cross-references P3-14 — anchors should describe the destination page content.

The classic spam pattern is heavy concentration on commercial keyword exact-match anchors (rule 3 violation), which Google's Penguin algorithm and the leaked anchor spam features detect.

### Step 2 — Citations
1. **Google Search Central — Penguin Algorithm and link manipulation** (https://developers.google.com/search/docs/essentials/spam-policies, Google, accessed May 2026). Documents over-optimised anchor text as a manipulation signal subject to algorithmic and manual demotion.
2. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leak names `phraseAnchorSpamCount`, `phraseAnchorSpamDemoted`, and related features confirming Google operationally detects anchor manipulation patterns.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #88 (Backlink Anchor Text), #161 (Brand Name Anchor Text), #197 ("Poison" Anchor Text).
4. **DataForSEO Backlinks API**. Returns anchor text per backlink, supporting distribution analysis.

### Step 3 — Evidence weight rationale
Google explicitly documents anchor manipulation as a spam signal. Leak features confirm specific anchor-spam-detection mechanisms. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Backlinks API** anchor text per backlink across full inventory.
- **Classification logic: our own.** Apply categorical rules (branded match, exact match, partial match, naked URL pattern, generic phrase list) to each anchor.

### Step 5 — Verification
DataForSEO returns anchors at scale. Classification is composition. Granularity required: per-site distribution table plus rule-by-rule pass/fail. Granularity delivered: by composition.

### Step 6 — Cost
Bundled with backlink inventory.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-15 (anchor spam phrase count from leak), P3-29 (toxic backlinks). Anchor distribution is the primary lens for detecting manipulation.

---

## P3-13 — Anchor text font size *(removed — May 2026 measurability audit)*

This variable was removed from the operational taxonomy in May 2026. The leaked Google feature `fontsize` would require rendering every linking page individually and inspecting the anchor element's computed styles — operationally prohibitive for any site with more than a handful of backlinks, and the taxonomy entry itself flagged this as "not feasible". The variable was a watchlist entry with **Speculative** weight, single-source. Anchor manipulation signals that ARE externally detectable are covered by **P3-12 — Anchor text distribution** and **P3-15 — Anchor spam phrase count**.

---

## P3-14 — Anchor mismatch demotion (AnchorMismatchDemotion)

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The leaked Google feature `AnchorMismatchDemotion` representing a demotion applied when anchor text fails to match the destination page's content. A link with anchor "best running shoes" pointing to a page about kitchen appliances triggers this demotion.

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names `AnchorMismatchDemotion` as a confirmed demotion feature, indicating Google operationally penalises misaligned anchor-to-destination patterns.
2. **Google Search Central — Penguin Algorithm** (https://developers.google.com/search/docs/essentials/spam-policies, Google, accessed May 2026). Anchor manipulation is part of Google's link spam detection; mismatch is one form of manipulation signal.

### Step 3 — Evidence weight rationale
Leak feature plus Google's broader anchor spam framework support the existence of mismatch detection. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition.** For each backlink, compare anchor text against destination page content (semantic similarity via embeddings or topical match check).
- **Embedding generation: shared with other variables** using OpenAI text-embedding-3-small or self-hosted equivalents.

### Step 5 — Verification
DataForSEO returns anchor + destination URL; we can fetch destination page content and compute similarity. Granularity required: per-backlink mismatch flag plus aggregated mismatch count. Granularity delivered: by composition.

### Step 6 — Cost
Embedding cost ~$0.0001 per page processed. Bundled at site refresh frequency.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-12 (anchor text distribution), P3-15 (anchor spam phrase count).

---

## P3-15 — Anchor spam phrase count

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The leaked Google features `phraseAnchorSpamCount`, `phraseAnchorSpamDemoted`, `phraseAnchorSpamDays`, `phraseAnchorSpamEnd`, and `phraseAnchorSpamFraq` collectively capturing Google's tracking of suspicious anchor text patterns: count of spam-like anchors, demotion status, time-based windows, and fractional concentration.

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names the full set of `phraseAnchorSpam*` features, confirming Google operationally detects anchor manipulation with multiple temporal and structural signals.
2. **Google Search Central — Penguin Algorithm and link spam policies** (https://developers.google.com/search/docs/essentials/spam-policies, Google, accessed May 2026). Anchor manipulation is documented as a spam policy violation.

### Step 3 — Evidence weight rationale
Leak features confirm Google operationally tracks anchor spam. Specific weights and demotion mechanisms are not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition.** Apply known spam phrase patterns (commercial keyword stuffing, money keyword over-concentration) to the anchor text inventory from P3-12.
- **Detection logic: our own.** Identify suspicious patterns: high concentration on single commercial phrase, sudden velocity spike of identical anchors, recognised spam phrase libraries.

### Step 5 — Verification
Composition over existing anchor data. Granularity required: per-site spam count plus per-anchor classification. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P3-12 (anchor text distribution).
- **Cross-references:** P3-29 (toxic backlinks) — anchor spam is one form of toxic backlink pattern.

---

## P3-16 — Dropped local anchor count (droppedLocalAnchorCount) *(removed — May 2026 measurability audit)*

This variable was removed from the operational taxonomy in May 2026. The leaked Google feature `droppedLocalAnchorCount` counts internal anchors Google has chosen to ignore — a per-document state held entirely inside Google's index pipeline, with no API, no header, and no proxy that exposes it. The taxonomy entry recorded "not measurable from external data" and assigned **Speculative** weight on a single source. Internal-link health that IS externally measurable is covered by **P1-23 / P1-24** (internal link counts and quality).

---

## P3-17 — Dofollow vs nofollow ratio

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The ratio of dofollow links (no `rel="nofollow"` attribute) to nofollow links pointing at the site. Dofollow links pass full ranking authority by default. Nofollow links signal to Google that the linking site does not vouch for the destination, though Google's 2019 update treated nofollow as a "hint" rather than a strict directive.

### Step 2 — Citations
1. **Google Search Central — Qualify your outbound links to Google** (https://developers.google.com/search/docs/essentials/spam-policies#qualify-outbound-links, Google, accessed May 2026). Documents nofollow as the primary attribute for unvouched links and explains the post-2019 "hint" treatment.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #99 (Nofollow Links). A natural backlink profile contains both dofollow and nofollow links; pure dofollow profiles can suggest manipulation.
3. **DataForSEO Backlinks API**. Returns the `dofollow` boolean per backlink.

### Step 3 — Evidence weight rationale
Google explicitly documents nofollow handling. Practitioner consensus that natural profiles include both. Specific ideal ratio not officially endorsed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Backlinks API** per-backlink dofollow attribute, aggregated to ratio.

### Step 5 — Verification
DataForSEO returns the field per backlink. Granularity required: per-site dofollow/nofollow ratio plus distribution. Granularity delivered: matches.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-18 (sponsored/UGC tags) — additional rel attributes that affect link weighting.

---

## P3-18 — Sponsored / UGC link tags

**Pillar:** Off-Page Authority
**Evidence weight:** Consensus

### Step 1 — Definition
The presence of `rel="sponsored"` (paid links, advertisements, affiliates) and `rel="ugc"` (user-generated content links such as forum posts, comments) attributes on backlinks. Introduced by Google in 2019 as more granular alternatives to `rel="nofollow"`, allowing site owners to disclose link nature for proper algorithmic interpretation.

### Step 2 — Citations
1. **Google Search Central Blog — Evolving "nofollow" — new ways to identify the nature of links** (announced September 2019, https://developers.google.com/search/blog/2019/09/evolving-nofollow-new-ways-to-identify, Google). Authoritative announcement and guidance for `rel="sponsored"` and `rel="ugc"`.
2. **Google Search Central — Spam Policies** (https://developers.google.com/search/docs/essentials/spam-policies, Google, accessed May 2026). Mandates appropriate disclosure for paid and user-generated links.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #101 ("Sponsored" or "UGC" Tags).

### Step 3 — Evidence weight rationale
Officially introduced and documented by Google. Required for paid-link disclosure to comply with Google's spam policies. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Backlinks API** per-backlink rel attributes.

### Step 5 — Verification
DataForSEO returns rel attributes. Granularity required: per-site count of links with each rel value (sponsored, ugc, nofollow, dofollow, none). Granularity delivered: matches.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-17 (dofollow/nofollow ratio).

---

## P3-19 — Contextual links (in-content vs sidebar/footer)

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The classification of backlinks by their position on the linking page: in-content (within the main editorial body), sidebar (recurring across pages of the linking site), or footer (sitewide). Contextual in-content links pass more weight than sitewide sidebar/footer links because they reflect editorial endorsement of specific content.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #102 (Contextual Links) — practitioner consensus that in-content links pass more weight.
2. **Google — Penguin Algorithm and link spam policies** (https://developers.google.com/search/docs/essentials/spam-policies, Google). Sidewide footer/sidebar links repeated across many pages are often flagged as manipulation.
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Leak references link-position-related features confirming Google distinguishes positional context.

### Step 3 — Evidence weight rationale
Practitioner consensus, leak corroboration, indirect Google support via spam policies. Specific weighting not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Backlinks API** which provides link position data when available.
- **Composition: our own** classification logic for when DataForSEO doesn't include position metadata — fetch the linking page, parse DOM to identify whether the link sits within `<main>`, `<article>` (in-content) vs `<aside>`, `<nav>`, `<footer>` (chrome).

### Step 5 — Verification
DataForSEO position data plus DOM parsing for missing cases. Granularity required: per-backlink classification (in-content / sidebar / footer / unknown). Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-20 (link location in content), P3-39 (sitewide vs single-page links).

---

## P3-20 — Link location in content

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
For in-content links specifically, the position within the article body — top of article, middle, or bottom. Earlier in-article placement is generally considered more weighted than later, reflecting editorial prominence.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #107 (Link Location In Content) and #108 (Link Location on Page).
2. **Patent and academic research on link weighting** generally supports the principle that visual/document prominence affects link weight.

### Step 3 — Evidence weight rationale
Practitioner factor with general support. Specific operational weight not officially endorsed by Google. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition: our own** DOM analysis of linking pages. Compute link position as character offset within main content element divided by total content length.

### Step 5 — Verification
DOM parsing produces deterministic position. Granularity required: per-backlink relative position (0–1, where 0 is top of content). Granularity delivered: by composition.

### Step 6 — Cost
Bundled with linking page analysis (already required for P3-19, P3-14).

### Step 7 — Dependencies and cross-references
- **Depends on:** P3-19 (must be in-content for position to matter).

---

## P3-21 — Linking domain topical relevance

**Pillar:** Off-Page Authority
**Evidence weight:** Consensus

### Step 1 — Definition
The topical alignment between the linking domain's overall subject matter and the target site's subject matter. A backlink from a topically-related domain (e.g., a fitness blog linking to a sports nutrition site) passes more weight than a topically-unrelated domain (e.g., a cooking blog linking to a financial services site).

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #109 (Linking Domain Relevancy) and Factor #110 (Page-Level Relevancy).
2. **Google — Penguin Algorithm and link spam policies** (https://developers.google.com/search/docs/essentials/spam-policies, Google). Topically irrelevant link patterns are characteristic of link manipulation schemes.
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). The leak's `siteEmbedding` and topical features confirm Google computes domain-level topic similarity for link weighting.

### Step 3 — Evidence weight rationale
Universally accepted practitioner principle, supported by Google's spam policies and confirmed by leak features for site-level topic representation. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Composition: our own.** For each linking domain, compute its topical embedding centroid (using P0-07 methodology) and compare cosine similarity to our site's centroid.

### Step 5 — Verification
Embedding-based similarity computation is standard. Granularity required: per-linking-domain topical relevance score (0–1) plus aggregated distribution. Granularity delivered: by composition.

### Step 6 — Cost
Per-linking-domain embedding generation. ~$0.0001 per domain. For 100 referring domains, approximately £0.05 per refresh.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P0-07 (site focus score) — same embedding methodology applied differently. P1-26 (outbound link quality and theme) — symmetric concept for outbound links.

---

## P3-22 — Linking domain country TLD

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The country-code top-level domain (ccTLD) of the linking domain (e.g., `.uk`, `.de`, `.fr`). For sites targeting specific geographic markets, country-relevant ccTLDs may pass more locally-targeted authority signal than generic TLDs (`.com`, `.org`).

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #106 (Country TLD of Referring Domain).
2. **Google Search Central — Geographic targeting** (https://developers.google.com/search/docs/specialty/international/managing-multi-regional-sites, Google, accessed May 2026). Documents ccTLDs as a strong geographic signal for the linked site, including for inbound links from country-relevant sources.

### Step 3 — Evidence weight rationale
Google documents ccTLDs as geographic signals. Specific operational weight for inbound link weighting not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Backlinks API** plus simple TLD parsing from the linking domain.

### Step 5 — Verification
TLD extraction is trivial. Granularity required: per-site distribution of linking domains by country. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Relevance:** for sites targeting specific countries (US, UK, Germany), ccTLD distribution informs whether the link profile reflects target market. Less relevant for global/generic sites.

---

## P3-23 — C-class IP diversity of links

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The number of unique C-class IP addresses (the third octet of an IPv4 address) across the site's referring domains. Many backlinks from domains hosted on the same C-class IP block suggests the same owner/network behind multiple "different" linking sites — a manipulation pattern.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #86 (Number of Links from Separate C-Class IPs) and Factor #196 (Links from the Same Class C IP).
2. **Google — Link spam and PBN detection.** Google's link spam systems are documented as detecting Private Blog Network (PBN) patterns where multiple "different" linking sites are hosted on the same network.

### Step 3 — Evidence weight rationale
Practitioner consensus on C-class IP diversity as PBN-detection signal. Google has indicated they detect such patterns. Specific algorithmic threshold not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition.** For each linking domain, perform DNS lookup to obtain IP, extract C-class. Aggregate to per-site unique C-class count.

### Step 5 — Verification
DNS lookups standard. Granularity required: per-site unique C-class count plus list of high-concentration C-classes. Granularity delivered: by composition.

### Step 6 — Cost
DNS lookups free. May add latency for sites with many referring domains.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-29 (toxic backlinks) — low C-class diversity is one signal of PBN-based toxic links.

---

## P3-24 — Backlink velocity (positive)

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The rate at which the site acquires new backlinks over time, typically measured per 30-day window. Healthy positive velocity reflects ongoing brand growth and content amplification; abnormal sudden velocity spikes can indicate paid link campaigns or manipulation, particularly when combined with anchor-spam concentration.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #112 (Positive Link Velocity) and Factor #198 (Unnatural Link Spike).
2. **Google — Link spam and PBN detection.** Google's link spam systems are documented as detecting unnatural acquisition patterns including velocity spikes.
3. **DataForSEO Backlinks API**. Provides historical backlink data with `first_seen` timestamps enabling velocity computation.

### Step 3 — Evidence weight rationale
Practitioner consensus, supported by Google's link spam framework. Specific velocity threshold not officially endorsed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Backlinks API** with `first_seen` field per backlink.
- **Composition: our own** velocity calculation (new backlinks per rolling 30/90/365-day window).

### Step 5 — Verification
DataForSEO confirms first_seen field. Velocity calculation is composition. Granularity required: per-site velocity time-series plus anomaly detection on spikes. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Companion to:** P3-25 (negative velocity / loss rate).
- **Cross-references:** P3-15 (anchor spam) — velocity spikes combined with anchor concentration are a common manipulation signature.

---

## P3-25 — Backlink velocity (negative / loss rate)

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The rate at which previously-existing backlinks are lost over time, measured per 30-day window. Backlink loss can occur from page deletions, redirects, link removals, or de-indexation of linking sites.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #113 (Negative Link Velocity).
2. **DataForSEO Backlinks API**. Provides historical backlink data with `last_seen` field enabling loss-rate computation.

### Step 3 — Evidence weight rationale
Practitioner factor with direct measurement methodology. Specific operational impact varies. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Backlinks API** with `last_seen` field plus our own loss-rate calculation per rolling window.

### Step 5 — Verification
DataForSEO confirms last_seen field. Granularity required: per-site loss rate time-series plus categorisation of why links were lost. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Companion to:** P3-24 (positive velocity).

---

## P3-26 — Backlink age

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The age of individual backlinks (time since first observed). Older established backlinks may pass more weight than recently-acquired links because they reflect sustained editorial endorsement.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #118 (Backlink Age).
2. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Multiple time-based features in the leak suggest temporal weighting in ranking.
3. **DataForSEO Backlinks API**. Provides `first_seen` field per backlink.

### Step 3 — Evidence weight rationale
Practitioner factor with leak corroboration. Specific weighting not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Backlinks API** with `first_seen` field plus our own age distribution calculation.

### Step 5 — Verification
DataForSEO confirms first_seen field. Granularity required: per-site backlink age distribution plus oldest-and-newest endpoints. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Companion to:** P3-24 (positive velocity), P3-25 (negative velocity).

---

## P3-27 — Co-occurrences (brand + topic mentions)

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The frequency with which the brand name appears in the same content as topical keywords or industry terms across the web — even without an explicit link. Brand-topic co-occurrences signal to Google that the brand is associated with the topic, strengthening topical authority.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #117 (Co-Occurrences).
2. **Bill Slawski — Google patents on entity-relationship signals** (multiple). Slawski's research catalogues Google patents that compute entity co-occurrence as a relevance signal.
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Entity-related features in the leak support brand-topic association tracking.

### Step 3 — Evidence weight rationale
Practitioner concept supported by published Google patents and entity-related leak features. Specific operational mechanism not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition.** Brand mention finding via DataForSEO Backlinks API (also captures unlinked mentions when configured) or dedicated brand mention monitoring services.
- **Topic-association logic: our own.** Compute statistical co-occurrence frequency of brand mentions alongside expected topical keywords.

### Step 5 — Verification
Mention sources are documented. Co-occurrence calculation is composition. Granularity required: per-topic co-occurrence frequency for the brand. Granularity delivered: by composition.

### Step 6 — Cost
Brand mention monitoring may add subscription cost (~£20–£50/month) or use DataForSEO mention-finding endpoints.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-32 (brand mention frequency), P0-15 (brand search volume), P0-16 (Knowledge Graph entity).

---

## P3-28 — Linked-as-Wikipedia source

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
Whether the site is cited as a source/reference on Wikipedia articles. Wikipedia citations signal that the site is considered authoritative on the cited topic; Wikipedia maintains rigorous citation standards meaning inclusion has reputational weight beyond the link's nominal nofollow attribute.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #116 (Linked to as Wikipedia Source).
2. **Wikipedia citation policy** (https://en.wikipedia.org/wiki/Wikipedia:Verifiability, Wikipedia, accessed May 2026). Wikipedia's verifiability requirements mandate citations from reliable sources.
3. **Industry research on Wikipedia's role in Google's Knowledge Graph and authority signals**. Wikipedia is widely understood as a primary source for entity verification in Google's Knowledge Graph.

### Step 3 — Evidence weight rationale
Practitioner factor with logical foundation (Wikipedia inclusion = high-quality vetting). Direct ranking impact not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: Wikipedia API or scraping** to detect citations of the site's URLs across Wikipedia articles.
- **DataForSEO Backlinks API** typically captures Wikipedia citations as part of standard backlink data.

### Step 5 — Verification
Wikipedia is publicly accessible. Granularity required: per-site count of Wikipedia citations plus list of articles citing the site. Granularity delivered: matches.

### Step 6 — Cost
Free (Wikipedia API). Bundled (DataForSEO if Wikipedia citations appear in standard backlink inventory).

### Step 7 — Dependencies and cross-references
- **Cross-references:** P0-16 (brand entity in Knowledge Graph) — Wikipedia citation often correlates with Knowledge Graph entity recognition.

---

## P3-29 — Toxic backlink presence

**Pillar:** Off-Page Authority
**Evidence weight:** Consensus

### Step 1 — Definition
Backlinks pointing to the site that originate from low-quality, spammy, or manipulative sources — link farms, PBNs (Private Blog Networks), comment spam, hacked sites, irrelevant directories, and similar patterns. Toxic backlinks may trigger Penguin algorithmic demotion or manual actions, especially when concentrated.

### Step 1.5 — Evaluation rules

A backlink is classified as toxic when ANY of the following rules trigger:

1. **Linking domain has DR/DA below 5** AND lacks topical relevance to target site (cross-references P3-21).
2. **Linking page is auto-generated content.** Page is part of templated content farms with minimal editorial value.
3. **Linking page is in a known PBN cluster** — multiple linking pages from the same C-class IP block share suspicious characteristics (cross-references P3-23).
4. **Linking page is on a hacked site.** Site shows signs of compromise (unrelated link injections, malware indicators).
5. **Linking page is from a low-quality directory** with no editorial standards.
6. **Linking page contains comment spam patterns.** Backlinks placed in comments without moderation.
7. **Linking domain is in a foreign language unrelated to target audience** (e.g., Russian/Chinese/Hindi spam links to a US English site).
8. **Anchor text is over-optimised exact-match commercial phrase** (cross-references P3-12, P3-15).
9. **Linking page has dozens or hundreds of outbound links** to unrelated sites — characteristic of link farms.
10. **Sudden velocity spike of low-quality links** within a short window.

A backlink is toxic if it triggers any of these rules. The site has a toxic backlink problem when toxic links exceed 5–10% of total inventory.

### Step 2 — Citations
1. **Google Search Central — Penguin Algorithm and link spam policies** (https://developers.google.com/search/docs/essentials/spam-policies, Google, accessed May 2026). Documents the categories of manipulation Google demotes.
2. **Google Search Central — Disavow Links Tool** (https://search.google.com/search-console/disavow-links-tool, Google, accessed May 2026). The existence of the disavow tool implies Google identifies toxic links as a real category.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Multiple factors related to toxic links: #95 (Links from Bad Neighborhoods), #173, #191, #194, #198.
4. **DataForSEO Backlinks API** plus third-party toxic link analysis (Moz Spam Score, Semrush Toxic Score).

### Step 3 — Evidence weight rationale
Google explicitly documents toxic link patterns and provides the disavow tool for remediation. Multiple practitioner sources align. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: composition** combining DataForSEO backlink data with multi-rule classifier logic from Step 1.5.
- **Supplementary: third-party spam scoring** for cross-validation.

### Step 5 — Verification
Composition over existing backlink data plus rule-based classification. Granularity required: per-backlink toxic boolean plus rule that triggered. Granularity delivered: by composition.

### Step 6 — Cost
Bundled with backlink inventory query.

### Step 7 — Dependencies and cross-references
- **Depends on:** P3-12 (anchor distribution), P3-21 (topical relevance), P3-23 (C-class IP), P3-24 (velocity).
- **Used by:** P3-30 (disavow tool usage) — toxic links identified here are candidates for disavow.

---

## P3-30 — Disavow tool usage

**Pillar:** Off-Page Authority
**Evidence weight:** Consensus

### Step 1 — Definition
Whether the site has actively submitted a disavow file to Google Search Console using the Disavow Links Tool. Disavow signals to Google to ignore specified backlinks for ranking purposes, mitigating toxic link impact.

### Step 2 — Citations
1. **Google Search Central — Disavow Links Tool** (https://search.google.com/search-console/disavow-links-tool, Google, accessed May 2026). Authoritative tool documentation.
2. **Google Search Central — When to use the Disavow Links Tool** (https://developers.google.com/search/blog/2017/03/links-disavow-tool, Google). Guidance on when disavow is appropriate.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #204 (Disavow Tool).

### Step 3 — Evidence weight rationale
Officially documented Google tool with clear use case. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Site-owner attestation.** Disavow file submission is private to the GSC property; not externally observable.

### Step 5 — Verification
Requires site-owner cooperation. Granularity required: per-site disavow file submission status plus disavow file contents. Granularity delivered: by site owner declaration.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Depends on:** P3-29 (toxic backlinks) — disavow is the remediation mechanism.

---

## P3-31 — Reciprocal link ratio

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The percentage of inbound backlinks from sites that the target site also links back to (reciprocal linking). Excessive reciprocal linking suggests link exchange schemes, which Google has explicitly identified as link manipulation.

### Step 2 — Citations
1. **Google Search Central — Link spam policies** (https://developers.google.com/search/docs/essentials/spam-policies, Google, accessed May 2026). Excessive link exchanges are documented as a violation of Google's spam policies.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #121 (Reciprocal Links).

### Step 3 — Evidence weight rationale
Google explicitly identifies link exchange schemes as manipulation. Specific threshold for "excessive" not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition.** For each linking domain, check whether the target site contains an outbound link back to that domain.

### Step 5 — Verification
Composition over backlink data + outbound link data. Granularity required: per-site reciprocal link ratio plus list of reciprocal link pairs. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P1-26 (outbound link quality), P3-29 (toxic backlinks).

---

## P3-32 — Brand mention frequency (linked + unlinked)

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
The total frequency of brand mentions across the web, including both linked mentions (proper backlinks) and unlinked mentions (brand name appearing without hyperlink). Unlinked brand mentions are increasingly weighted by Google as authority signals — a brand is established when people talk about it, regardless of whether the mention includes a hyperlink.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #170 (Unlinked Brand Mentions).
2. **Google patents on implicit linking** (research collected by Bill Slawski). Multiple Google patents describe weighting brand mentions even without hyperlinks.
3. **DataForSEO Backlinks API** plus brand mention monitoring services (Brand24, Mention, Talkwalker).

### Step 3 — Evidence weight rationale
Concept well-supported by Google patents and practitioner consensus on entity-based ranking. Specific operational weight not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Linked mentions: DataForSEO Backlinks API** standard inventory.
- **Unlinked mentions: brand mention monitoring services** or composition via web search.

### Step 5 — Verification
Brand mention services provide unlinked detection. Granularity required: per-site total mention count, with linked/unlinked breakdown plus sentiment categorisation. Granularity delivered: by composition.

### Step 6 — Cost
Subscription cost for mention monitoring (~£20–£50/month) or DataForSEO-based discovery.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P0-15 (brand search volume), P0-16 (Knowledge Graph entity), P3-27 (brand-topic co-occurrences).

---

## P3-33 — Forum links

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
Backlinks pointing to the site from forum posts, discussion threads, or community-question platforms (e.g., Reddit, Stack Overflow, Quora, vBulletin/phpBB forums). Forum links pass varying weight depending on the forum's authority, the link's editorial context, and whether the forum applies nofollow to user-generated content.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #127 (Forum Links).
2. **Google Search Central — User-generated content link policies** (https://developers.google.com/search/docs/essentials/spam-policies, Google, accessed May 2026). Recommends `rel="ugc"` for forum and comment links.
3. **DataForSEO Backlinks API** plus our own classification of forum-pattern URLs.

### Step 3 — Evidence weight rationale
Practitioner factor with Google guidance on UGC marking. Forum-link value varies widely by source. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Backlinks API** plus URL pattern classification (common forum URL paths: `/forum/`, `/thread/`, `/discussion/`, etc., or known forum domains: reddit.com, stackoverflow.com).

### Step 5 — Verification
URL pattern classification is composition. Granularity required: per-site count of forum links plus list of source forums and their authority. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-18 (sponsored/UGC tags), P3-29 (toxic backlinks).
- **Cross-pillar:** P6-26 (Reddit / community platform presence in AI Search) — forum links from Reddit specifically have AI search citation value.

---

## P3-34 — Hub page links

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
Backlinks from "hub" pages — high-authority resource pages, link round-ups, "best of" list articles, or industry directories that aggregate links to topically-related content. Hub pages typically have high editorial authority and pass meaningful link weight.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #114 (Links from "Hub" Pages).
2. **Bill Slawski — Google patents on hub-and-authority detection** (multiple). Slawski's research catalogues Google patents related to identifying hub pages as a distinct category of high-value content.

### Step 3 — Evidence weight rationale
Practitioner factor with patent-research support. Specific operational weight not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition.** Detect hub pages from linking page patterns: many outbound links to topically-related content, high domain rating, structured "list" or "best of" article patterns.

### Step 5 — Verification
Composition over linking page metadata + outbound link inventory. Granularity required: per-backlink hub-page-source boolean plus identification of hub pages. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-19 (contextual links), P3-35 (authority-site links).

---

## P3-35 — Authority-site links

**Pillar:** Off-Page Authority
**Evidence weight:** Consensus

### Step 1 — Definition
Backlinks from high-domain-rating sites — typically defined as DR 70+ or DA 70+ — including major media outlets, established publications, and recognised industry-leading sites. Authority-site links are universally recognised as highest-value backlinks.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #115 (Links from Authority Sites).
2. **Multiple ranking studies (Searchmetrics, Backlinko, Ahrefs)**. All major SEO research consistently shows correlation between high-authority backlinks and rankings.
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). PageRank-style features (`PageRankNS`, `homepagePagerankNs`) give weight to links from high-authority sources by definition of the algorithm.

### Step 3 — Evidence weight rationale
Universally accepted, both by practitioner research and the underlying mechanics of PageRank-style scoring. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO Backlinks API** with per-domain authority scores plus filtering threshold (e.g., DR ≥ 70).

### Step 5 — Verification
Direct from DataForSEO. Granularity required: per-site count of authority-site backlinks plus list of contributing domains. Granularity delivered: matches.

### Step 6 — Cost
Bundled with backlink inventory.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-02 (DR/DA distribution), P3-09 (siteAuthority).

---

## P3-36 — Guest post links

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
Backlinks acquired via guest authorship on external sites — articles written by site representatives and published on industry publications, blogs, or news sites with appropriate author attribution. Guest posts can be legitimate editorial content (high value) or spammy mass-produced placements (low or negative value).

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #96 (Guest Posts).
2. **Google Search Central — Link spam policies** (https://developers.google.com/search/docs/essentials/spam-policies, Google, accessed May 2026). Google has explicitly stated that guest posts published primarily for link-acquisition purposes are spam; legitimate editorial guest contributions are fine.
3. **Matt Cutts — historical statements** (2014). Cutts famously declared guest blogging "done as a way to gain links" though Google has since clarified the issue is link-purpose, not the format itself.

### Step 3 — Evidence weight rationale
Google distinguishes legitimate guest editorial from spam guest posts; the distinction is editorial intent. Practitioner factor with Google guidance. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition.** Detect guest post patterns from linking page metadata: author byline matching site representatives, content topical overlap with target site, presence of "guest contributor" or "author bio" patterns.

### Step 5 — Verification
Composition over linking page content. Granularity required: per-backlink guest-post boolean plus quality signals (single guest post per author = legitimate; many guest posts from same author across many sites = spam). Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-29 (toxic backlinks) — guest post links can fall on either side of toxic depending on quality. P4-04 (author byline presence).

---

## P3-37 — Widget links

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
Backlinks acquired via widgets installed on third-party sites — embeddable badges, calculators, infographics, scoreboards, social proof widgets, or similar embed code. Google has explicitly stated that widget links should use `rel="nofollow"` or `rel="sponsored"`; widget links without proper attribution may be devalued or treated as link manipulation.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #195 (Widget Links).
2. **Google Search Central — Link spam policies** (https://developers.google.com/search/docs/essentials/spam-policies, Google, accessed May 2026). Lists widget links as a category requiring proper attribution to avoid being classified as link manipulation.

### Step 3 — Evidence weight rationale
Google explicitly addresses widget links in spam policies. Specific operational impact varies by attribution and widget usage scale. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition.** Detect widget-link patterns: many backlinks with identical anchor text, identical destination URLs, embedded in similar sidebar/footer positions across many domains.

### Step 5 — Verification
Composition over backlink inventory plus pattern detection. Granularity required: per-site count of widget-pattern backlinks plus identification of widget(s) generating them. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-29 (toxic backlinks), P3-39 (sitewide vs single-page links) — widget links are typically sitewide and may overlap with both.

---

## P3-38 — Press-release / article-directory links

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
Backlinks from press release distribution services (e.g., PR Newswire, Business Wire, PRWeb) and article directories (e.g., legacy "EzineArticles", "ArticleBase"). Google has historically devalued these as a link-building strategy because mass distribution reduces editorial authority of the placement.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #199 (Links From Article Directories and Press Releases).
2. **Google Search Central — Link spam policies** (https://developers.google.com/search/docs/essentials/spam-policies, Google, accessed May 2026). Press release distribution explicitly mentioned as a link-acquisition strategy that may be devalued; press release links typically use nofollow by default at major distribution services.
3. **Google's 2013 announcement** that press release links should use nofollow.

### Step 3 — Evidence weight rationale
Google explicitly addresses these link types as devalued. Specific operational impact varies. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition.** Detect press-release / article-directory patterns from linking domain identity (known PR distribution domains, known article directory domains).

### Step 5 — Verification
Domain-pattern matching is straightforward. Granularity required: per-site count plus list of source PR/directory domains. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-29 (toxic backlinks) — depending on quality, may overlap.

---

## P3-39 — Sitewide vs single-page links

**Pillar:** Off-Page Authority
**Evidence weight:** Probable

### Step 1 — Definition
Backlinks that appear on every (or most) pages of the linking domain — typically footer links, sidebar links, or navigation links — versus single-page editorial links. Google has stated that sitewide links from the same domain are typically treated as a single link rather than counted multiple times.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #130 (Sitewide Links).
2. **Google — John Mueller statements** (multiple). Google has stated that sitewide links from a single domain are deduplicated and counted once.
3. **DataForSEO Backlinks API** plus composition for detecting sitewide patterns.

### Step 3 — Evidence weight rationale
Practitioner factor with Google guidance. Specific deduplication mechanism not officially detailed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition.** For each linking domain, count the number of unique linking pages with the same destination URL and similar anchor text. High counts (e.g., links from 50+ pages on the same domain) indicate sitewide pattern.

### Step 5 — Verification
Composition over backlink inventory. Granularity required: per-source-domain sitewide vs single-page classification plus link count per domain. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-19 (contextual vs sidebar/footer), P3-37 (widget links — typically sitewide).

---

# Pillar 4 — Content Operations

**Total candidates:** 24
**Status:** Complete (24 of 24 complete)

## Pillar 4 Index

| ID | Variable | Status | Weight |
|----|----------|--------|--------|
| P4-01 | Publishing cadence and consistency | Complete | Probable |
| P4-02 | Content freshness (last meaningful update) | Complete | Probable |
| P4-03 | Author byline presence | Complete | Consensus |
| P4-04 | Author bio with credentials | Complete | Consensus |
| P4-05 | Author entity recognition | Complete | Consensus |
| P4-06 | E-E-A-T aggregation | Complete | Consensus |
| P4-07 | Content originality and substance | Complete | Consensus |
| P4-08 | Comprehensiveness vs SERP competitor average | Complete | Probable |
| P4-09 | Insightful analysis beyond surface | Complete | Probable |
| P4-10 | Sourcing and evidence presence | Complete | Consensus |
| P4-11 | Original research / proprietary data | Complete | Probable |
| P4-12 | Content tagging / category structure | Complete | Probable |
| P4-13 | Three-layer content structure | Complete | Speculative |
| P4-14 | Comparative content (vs, alternatives, best-of) | Complete | Probable |
| P4-15 | Methodology disclosure | Complete | Consensus |
| P4-16 | AI / automation use disclosure | Complete | Consensus |
| P4-17 | YMYL handling rigour | Complete | Consensus |
| P4-18 | Goldstandard human-rated content | Removed | — |
| P4-19 | UGC discussion effort score | Complete | Speculative |
| P4-20 | Affiliate link disclosure and quality | Complete | Consensus |
| P4-21 | Mass-produced content detection | Complete | Consensus |
| P4-22 | Site-wide quality (Panda) | Complete | Consensus |
| P4-23 | Headlines accuracy (no clickbait/exaggeration) | Complete | Consensus |
| P4-24 | Quarterly content refresh cycle | Complete | Probable |

---

## P4-01 — Publishing cadence and consistency

**Pillar:** Content Operations
**Evidence weight:** Probable

### Step 1 — Definition
The rate at which the site publishes new content plus the consistency of that publishing rhythm. Measured as new pages per month with consistency-of-cadence as a secondary measure (regular weekly publishing scores higher than sporadic bursts).

### Step 2 — Citations
1. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends content with sustained maintenance and regular updates.
2. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #70 (Site Updates).

### Step 3 — Evidence weight rationale
Practitioner consensus, indirect Google support. Specific cadence-to-ranking impact not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition** over historical DataForSEO crawl snapshots + sitemap lastmod data + GSC URL discovery dates.

### Step 5 — Verification
Crawl history accumulates over time. Granularity required: per-site monthly publication count plus consistency metric. Granularity delivered: by composition. **Caveat:** requires accumulated history.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P1-45 (page-level update cadence), P2-41 (site update cadence) — same concept at different scopes.

---

## P4-02 — Content freshness (last meaningful update)

**Pillar:** Content Operations
**Evidence weight:** Probable

### Step 1 — Definition
The site-wide aggregate freshness, expressed as the median or 75th-percentile age of "last meaningful update" across all indexable pages. Distinct from page-level freshness signals (P1-41 to P1-43); this is a site-level summary indicating whether the site overall is actively maintained or shows signs of abandonment.

### Step 2 — Citations
1. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends current information; sites with stale content lose ranking power.
2. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). FreshnessTwiddler and QualityBoost systems use freshness signals at site level.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #27 (Content Recency).

### Step 3 — Evidence weight rationale
Practitioner consensus with leak corroboration. Specific operational threshold not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition** aggregating P1-41 (byline date), P1-42 (syntactic date), P1-43 (semantic date) signals across all pages.

### Step 5 — Verification
Aggregation over existing per-page date signals. Granularity required: per-site freshness distribution plus stale-content count. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P1-41/42/43 (page-level dates), P1-44 (update magnitude), P1-45 (update cadence).

---

## P4-03 — Author byline presence

**Pillar:** Content Operations
**Evidence weight:** Consensus

### Step 1 — Definition
Each content page (article, blog post, news item, review) prominently displays a named author byline at or near the top of the content. The author byline establishes authorship for E-E-A-T evaluation.

### Step 2 — Citations
1. **Google Search Central — Helpful Content guidance** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Explicitly recommends author bylines where expected.
2. **Google Search Quality Rater Guidelines** (publicly published, latest version 2024). Quality raters are instructed to evaluate "Who is responsible for the content?".
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names `isAuthor` and `author` as features.

### Step 3 — Evidence weight rationale
Google explicitly recommends author bylines. Leak corroborates. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO content extraction** plus pattern detection (byline patterns, schema.org Author markup).

### Step 5 — Verification
Pattern detection over rendered content. Granularity required: per-page boolean plus extracted author name. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Foundational for:** P4-04 (bio with credentials), P4-05 (author entity recognition), P4-06 (E-E-A-T).

---

## P4-04 — Author bio with credentials

**Pillar:** Content Operations
**Evidence weight:** Consensus

### Step 1 — Definition
The author byline links to (or displays inline) a bio page or section that establishes the author's expertise, credentials, experience, and contact information. A credible bio with verifiable credentials is part of E-E-A-T evaluation.

### Step 1.5 — Evaluation rules

An author bio passes credibility check when ALL of the following rules pass:

1. **Author has a dedicated bio page or visible inline bio.** Either a `/author/{name}` URL exists, or substantive bio text appears alongside the byline.
2. **Bio describes relevant expertise or experience.** Identifies the author's qualifications relevant to the content's topic.
3. **Bio includes verifiable identity.** Real name plus at least one of: LinkedIn link, professional homepage, or other identity-verification means.
4. **Bio is not generic or templated.** Avoid placeholder text. Specific, substantive bio content.
5. **Author has demonstrable history of writing on the topic.** Multiple articles by the same author on related subjects.
6. **Schema.org Person markup is present** (recommended).

### Step 2 — Citations
1. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends author bylines linked to background information.
2. **Google Search Quality Rater Guidelines** (publicly published). Quality raters evaluate author expertise and credentials.
3. **Google Search Central — E-E-A-T documentation** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content#e-e-a-t, Google).

### Step 3 — Evidence weight rationale
Google explicitly addresses author credibility in primary documentation. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Composition** combining DataForSEO content extraction + bio page detection + LLM-driven evaluation of bio content quality.

### Step 5 — Verification
Bio detection is composition. Quality evaluation may use LLM scoring. Granularity required: per-page bio quality assessment with rule-by-rule pass/fail. Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation: ~$0.0005-$0.001 per page if used.

### Step 7 — Dependencies and cross-references
- **Scope of this variable:** on-page editorial bio check — does the author have a substantive bio (with credentials, experience, links to other authoritative profiles) that a human reader can use to evaluate the author's authority?
- **Author authority hierarchy:** **P4-04 (this) → on-page bio with credentials** (what a human reads). P4-05 → author entity recognition in KG/Wikipedia/Wikidata (whether the author is a recognised entity). P6-20 → Person schema markup making the author machine-readable to crawlers and LLMs.
- **Depends on:** P4-03 (author byline must exist).
- **Cross-references:** P4-05, P4-06 (E-E-A-T), P6-20 (schema layer).

---

## P4-05 — Author entity recognition

**Pillar:** Content Operations
**Evidence weight:** Consensus

### Step 1 — Definition
Whether the article author is recognised as an entity in Google's Knowledge Graph or other authoritative entity systems. Authors with established entity status carry stronger E-E-A-T signals than unknown authors.

### Step 2 — Citations
1. **Google Knowledge Graph documentation** (https://developers.google.com/knowledge-graph, Google, accessed May 2026).
2. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). `isAuthor`, `author` features confirm tracking.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #167 (Known Authorship).

### Step 3 — Evidence weight rationale
Google maintains Knowledge Graph as a public-facing entity system. Leak features confirm authorship tracking. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google Knowledge Graph Search API** for author entity status.
- **Supplementary: schema.org Person markup detection.**

### Step 5 — Verification
Knowledge Graph API documented and free. Granularity required: per-author entity status plus entity metadata. Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Scope of this variable:** entity-recognition check for the *author* in Knowledge Graph or other authoritative entity systems — given the author is bylined (P4-03) and has a bio (P4-04), is the author a recognised entity that LLMs and KG can disambiguate?
- **Author authority hierarchy:** P4-04 → on-page bio with credentials (what a human reads). **P4-05 (this) → author entity recognition in KG/Wikipedia/Wikidata**. P6-20 → Person schema markup making the author machine-readable to crawlers and LLMs.
- **Depends on:** P4-03 (byline must exist), P4-04 (bio must exist).
- **Cross-references:** P0-16 (same pattern applied to brand), P6-20 (Person schema), P6-11 (entity coverage broader scope).

---

## P4-06 — E-E-A-T aggregation

**Pillar:** Content Operations
**Evidence weight:** Consensus

### Step 1 — Definition
The aggregate Experience, Expertise, Authoritativeness, and Trust signals for the page and site as evaluated against Google's E-E-A-T framework.

### Step 1.5 — Evaluation rules

A page passes E-E-A-T when it satisfies ALL FOUR pillars below:

**Experience signals (any of):**
1. First-hand product/service experience demonstrated (own photos, original test results, personal observations)
2. Lived-experience credentials for the topic
3. Personal anecdotes, case studies, or original analysis based on direct involvement

**Expertise signals (any of):**
4. Author has formal credentials in the topic
5. Author has demonstrable subject-matter knowledge across multiple high-quality articles
6. Bio establishes specific topical expertise (cross-references P4-04)

**Authoritativeness signals (any of):**
7. Author or site is recognised as an authority on the topic (cross-references P0-07, P4-05)
8. Linked-as authoritative source by other recognised authorities (cross-references P3-28, P3-35)
9. Brand entity recognised in Knowledge Graph (cross-references P0-16)

**Trust signals (ALL of):**
10. HTTPS / SSL configured correctly (cross-references P2-18)
11. Privacy policy, terms of service, contact info readily accessible
12. Editorial integrity policies disclosed (corrections, fact-checking, methodology disclosure)
13. No deceptive practices (no clickbait, no hidden affiliate disclosures, no impersonation)
14. Content factually accurate and free of errors
15. For YMYL topics: elevated rigour applied (cross-references P0-17)

The page passes E-E-A-T when at least one signal triggers in each of the four categories. YMYL pages require ALL trust signals plus stronger expertise signals.

### Step 2 — Citations
1. **Google Search Quality Rater Guidelines** (publicly published, latest 2024). The canonical source for E-E-A-T (Experience added late 2022).
2. **Google Search Central — Creating Helpful, People-First Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026).
3. **Google Search Liaison statements** (multiple). Google has emphasised E-E-A-T particularly for YMYL content.

### Step 3 — Evidence weight rationale
E-E-A-T is officially documented by Google. The four-pillar framework is canonical. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Composition** aggregating signals from P0-07, P0-16, P0-17, P2-18, P3-28, P3-35, P4-03, P4-04, P4-05, plus content-specific quality signals.

### Step 5 — Verification
Composition over existing variable outputs. Granularity required: per-page E-E-A-T score with rule-by-rule signal status. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Aggregates:** P0-07, P0-16, P0-17, P2-18, P3-28, P3-35, P4-03, P4-04, P4-05.
- **Used by:** YMYL page handling (P0-17) requires elevated E-E-A-T thresholds.

---

## P4-07 — Content originality and substance

**Pillar:** Content Operations
**Evidence weight:** Consensus

### Step 1 — Definition
The page provides original information, reporting, research, or analysis rather than aggregating, rewriting, or rephrasing existing content. Originality and substance are foundational to Helpful Content evaluation.

### Step 1.5 — Evaluation rules
A page passes content originality and substance when ALL of the following rules pass:

1. **Not a near-duplicate of any external source.** Page content does not match (within text-similarity tolerance) any single external source's body text — flagged via search-on-content checks for distinctive phrases.
2. **Not a near-duplicate of any internal page.** Page does not duplicate another page on the same site (cross-references P1-46 in-site duplication).
3. **Original elements present.** At least one of the following is present and substantive: own data, own measurements, own case study, own interview, own analysis framework, own experimental result, own opinionated interpretation backed by reasoning.
4. **Aggregation transparent where used.** Where content does aggregate or summarise existing sources, sources are cited and the page adds something beyond the aggregation (synthesis, evaluation, ranking, recommendation).
5. **No detectable AI-generated boilerplate.** Content does not exhibit hallmarks of unedited LLM output (formulaic intro/conclusion, repetitive phrasing, generic examples, "as an AI" giveaways) that signal mass production rather than authored work.
6. **Substance proportional to length.** Word count carries proportional substantive content (no padding, no repeated restatement, no filler paragraphs that exist solely to hit a target length).

A page passing all 6 rules has content originality and substance.

### Step 2 — Citations
1. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). The very first criterion: "Provides original information, reporting, research, or analysis."
2. **Google Search Central — Spam Policies** (https://developers.google.com/search/docs/essentials/spam-policies, Google). Treats scraped or auto-generated content as spam.
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names `OriginalContentScore`.
4. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #66.

### Step 3 — Evidence weight rationale
Google explicitly documents originality as primary Helpful Content criterion. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Composition** with P1-38 (Original Content Score) plus site-level aggregation.

### Step 5 — Verification
Composition over P1-38 outputs. Granularity required: per-site percentage of original content. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Scope of this variable:** editorial-level originality and substance check, evaluated against the external web — applies the 6-rule Step 1.5 (no near-duplicate of external sources, no near-duplicate of internal pages, original elements present, transparent aggregation, no AI boilerplate, substance proportional to length). Multi-criteria evaluation; produces recommendations about content quality.
- **Hierarchy:** P1-38 → per-page numerical originality score (leak-feature approximation). P1-46 → in-site duplicate detection only. **P4-07 (this) → editorial-level multi-rule evaluation against external web**. P4-21 → mass-production pattern detection at site scale.
- **Cross-pillar:** P1-38 (feeds the rule "not a near-duplicate of any external source"), P1-46 (feeds the rule "not a near-duplicate of any internal page"), P4-21 (mass-produced content is a specific failure mode of originality).

---

## P4-08 — Comprehensiveness vs SERP competitor average *(removed — moved to the Competitive Analysis module, June 2026)*

Removed from the site audit in June 2026. Comprehensiveness-vs-SERP-competitors is a comparative *insight* (it ranks your depth against competitor pages on shared queries), not an intrinsic site-health item, so it belongs in the Competitive Analysis module rather than the audit.

**Pillar:** Content Operations
**Evidence weight:** Probable

### Step 1 — Definition
The page provides substantial, complete, comprehensive description of the topic, benchmarked against the average comprehensiveness of pages currently ranking for the same query.

### Step 2 — Citations
1. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends "substantial, complete, comprehensive descriptions of the topic."
2. **MarketMuse / Clearscope / Surfer SEO methodology** (industry standard tools). Practitioner-leading tools all benchmark against SERP competitors using entity coverage.
3. **DataForSEO Content Analysis API** plus our own SERP-comparison composition.

### Step 3 — Evidence weight rationale
Google explicitly endorses comprehensiveness. Practitioner methodology well-established. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition.** Fetch top 10 SERP results, extract topic/entity coverage, compute average. Compare target page coverage.

### Step 5 — Verification
Composition over SERP data + content extraction. Granularity required: per-page comprehensiveness percentile vs competitors plus list of missing topics. Granularity delivered: by composition.

### Step 6 — Cost
DataForSEO SERP API + content extraction per competitor. ~£0.05 per query analysed.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P1-34 (content depth/word count), P1-36 (semantic keyword/entity coverage).

---

## P4-09 — Insightful analysis beyond surface

**Pillar:** Content Operations
**Evidence weight:** Probable

### Step 1 — Definition
The page provides insightful analysis, novel perspective, or substantive interpretation rather than restating obvious or commonly-known information. Insightful content moves beyond what the average reader would already know about the topic to offer expert framing, nuanced analysis, or counterintuitive observation.

### Step 2 — Citations
1. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Lists "delivers insightful analysis beyond obvious observations" as a Helpful Content marker.
2. **Google Search Quality Rater Guidelines** (publicly published, latest 2024). Quality raters distinguish content that adds value from content that merely restates known information.

### Step 3 — Evidence weight rationale
Google explicitly endorses insightful analysis as a quality criterion. Operational measurement is qualitative and depends on LLM-driven evaluation. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition.** LLM-driven content evaluation comparing the page's claims/analysis to baseline knowledge representable in the topic; flag pages that mostly recapitulate Wikipedia-level summaries.

### Step 5 — Verification
LLM evaluation produces qualitative scoring. Granularity required: per-page insightfulness score (0–1) plus list of unique-insight elements. Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation: ~$0.001-$0.002 per page.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P4-07 (content originality), P4-11 (original research) — overlapping concepts; insightfulness is the analytical depth dimension.

---

## P4-10 — Sourcing and evidence presence

**Pillar:** Content Operations
**Evidence weight:** Consensus

### Step 1 — Definition
The page cites authoritative sources for factual claims, data points, statistics, and quotes. Evidence presence reflects editorial integrity and supports E-E-A-T trust signals.

### Step 1.5 — Evaluation rules
A page passes sourcing and evidence presence when ALL of the following rules pass:

1. **Substantive factual claims are sourced.** Statistics, dates, quoted statements, and non-obvious factual claims have inline citations to external sources or self-disclose as the page's own original measurement.
2. **Sources are authoritative for the claim type.** Health claims cite medical sources; legal claims cite legal sources; statistical claims cite primary research or authoritative aggregators; not random blogs unless sourcing is for the blog's own opinion.
3. **Citations are inline, not appendix-only.** Citations appear at the point the claim is made (link or footnote), not only listed at the bottom of the page.
4. **Citation links are live and reach the cited content.** No dead-link citations; cited URL actually contains the claim being attributed.
5. **No fabricated or hallucinated citations.** Citations point to real publications, real authors, real studies — verified for authenticity.
6. **Citation density is proportional to claim density.** Pages making many factual claims have many citations; pages making few claims need few. The page is not "citation-stuffed" with sources that do not actually support specific claims.
7. **Author's own claims distinguished from sourced claims.** Where the page makes its own assertions (analysis, opinion, recommendation), they are clearly the author's voice, not falsely attributed to a source.

A page passing all 7 rules has good sourcing and evidence presence.

### Step 2 — Citations
1. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends "clear sourcing and evidence of expertise provided."
2. **Google Search Quality Rater Guidelines** (publicly published). Quality raters evaluate whether claims are supported by trustworthy sources.

### Step 3 — Evidence weight rationale
Google explicitly addresses sourcing in primary documentation. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Composition** with P1-26 (outbound link quality and theme) — citations are typically outbound links to authoritative sources.
- **Density measurement: our own.** Count outbound links to authoritative domains per 1000 words of content.

### Step 5 — Verification
Composition over outbound link inventory + content length. Granularity required: per-page citation density plus list of cited authorities. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P1-26 (outbound link quality) — sourcing manifests as quality outbound links.
- **Cross-references:** P4-06 (E-E-A-T) — sourcing is a Trust signal.

---

## P4-11 — Original research / proprietary data

**Pillar:** Content Operations
**Evidence weight:** Probable

### Step 1 — Definition
The page contains original research, surveys, case studies, proprietary data, original analysis, or first-hand investigation that is not available elsewhere. Original research significantly strengthens E-E-A-T and is highly citable by other sites and AI systems.

### Step 2 — Citations
1. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Lists "provides original information, reporting, research, or analysis" as the primary Helpful Content marker.
2. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). `OriginalContentScore` confirms Google computes per-page originality.
3. **Princeton GEO Paper (Aggarwal et al., KDD 2024)**. Statistics adding and citation adding are documented to improve AI search visibility — original research is the source material for these signals.

### Step 3 — Evidence weight rationale
Practitioner consensus, leak corroboration, AI-search research confirms originality value. Specific operational weight not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition.** LLM-driven detection of: data tables, statistical claims, named methodologies, original survey results, primary-source interviews, dataset references.

### Step 5 — Verification
LLM evaluation. Granularity required: per-page presence boolean for each original-research signal type plus aggregate score. Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation cost.

### Step 7 — Dependencies and cross-references
- **Scope of this variable:** content-operations perspective — does the page *contain* original research (data tables, surveys, case studies, methodology disclosure)? Detection focused, no Step 1.5.
- **Hierarchy:** **P4-11 (this) → "does the page contain original research"** (content-ops detection). P6-07 → "is the page recognised as the primary source for the data it contains" (GEO evaluation including backlink-citation evidence and 6-rule Step 1.5). Same underlying signal, evaluated from different angles for different purposes.
- **Cross-references:** P4-07 (originality, broader), P4-09 (insightfulness), P6-03 (statistics adding for AI search), P6-04 (quotation adding for AI search), P6-07 (GEO-deep evaluation).

---

## P4-12 — Content tagging / category structure

**Pillar:** Content Operations
**Evidence weight:** Probable

### Step 1 — Definition
The site organises content into a coherent taxonomy of categories and tags, with each piece of content assigned to appropriate parent topics. Good taxonomy supports internal linking, topical authority, and user navigation.

### Step 2 — Citations
1. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #54 (Page Category) and Factor #69 (Site Architecture).
2. **HubSpot — Topic clusters and content categorisation** (https://blog.hubspot.com/marketing/topic-clusters-seo, HubSpot). Documents how content tagging supports pillar-and-cluster architecture.

### Step 3 — Evidence weight rationale
Practitioner consensus, indirect Google support via site architecture guidance. Specific operational impact not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition.** Detect category and tag URL patterns (`/category/`, `/topic/`, `/tag/`); cross-reference with topic clusters from P0-11.

### Step 5 — Verification
Pattern detection. Granularity required: per-site taxonomy structure plus content-to-category mapping completeness. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P0-11 (topic cluster definition), P0-12 (pillar architecture).

---

## P4-13 — Three-layer content structure

**Pillar:** Content Operations
**Evidence weight:** Speculative

### Step 1 — Definition
A content structure pattern (introduced by Foundation Inc as a GEO best practice) where the page leads with a 50-word direct answer, follows with 100–150 words on "why it matters," and then provides 1000+ words of detailed analysis. Designed to optimise for AI search citation while maintaining depth for human readers.

### Step 1.5 — Evaluation rules

A page passes three-layer structure check when ALL of the following rules pass:

1. **Page opens with a direct answer** of approximately 50 words within the first paragraph or two.
2. **A "why it matters" or context-setting section** of approximately 100–150 words follows the direct answer.
3. **Detailed analysis section** of 1000+ words provides depth.
4. **Total word count is at least 1200 words** (sum of the three layers, allowing for transitions).
5. **The first 50 words contain the primary target keyword** in a substantive context, not just keyword stuffing.

### Step 2 — Citations
1. **Foundation Inc — Generative Engine Optimization Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Articulates the three-layer structure as a GEO best practice.
2. **No corroborating Tier A or B source.** Google has not endorsed this specific structure.

### Step 3 — Evidence weight rationale
Single-source practitioner framework. The underlying principles (clear answer first, substantive depth) align with broader content best practices, but the specific 50/150/1000 word breakdown is a Foundation Inc proposal without empirical validation. Qualifies as **Speculative**. Per Model B, tracked but not driving recommendations until evidence emerges.

### Step 4 — Data source(s)
- **Composition.** Word count + structural analysis of opening sections via LLM.

### Step 5 — Verification
Composition over content. Granularity required: per-page structural assessment plus rule-by-rule pass/fail. Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation cost.

### Step 7 — Dependencies and cross-references
- **Watchlist entry.**
- **Cross-pillar:** P6-25 (three-layer content structure for AI search) — same variable from AI Search pillar perspective.

---

## P4-14 — Comparative content (vs, alternatives, best-of)

**Pillar:** Content Operations
**Evidence weight:** Probable

### Step 1 — Definition
The site publishes content in comparative formats: "X vs Y" comparisons, "alternatives to" lists, "best of" round-ups, migration guides, buyer's guides. These formats are highly citable in AI search responses and capture commercial-intent queries effectively.

### Step 2 — Citations
1. **Foundation Inc — Generative Engine Optimization Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Identifies comparative content as high-value for AI search citation.
2. **Backlinko — Content marketing research** (https://backlinko.com/, Brian Dean). Comparative content formats consistently rank well for commercial-intent queries.
3. **Industry SEO research (Ahrefs, SEMrush)** consistently shows comparative content as a high-CTR format for purchase-decision queries.

### Step 3 — Evidence weight rationale
Practitioner consensus across multiple sources. Specific Google ranking weight not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition.** Pattern detection on URL slugs and titles for comparative keywords ("vs", "alternatives", "best", "compared", "versus") plus structural analysis of content.

### Step 5 — Verification
Pattern detection over URLs and content. Granularity required: per-site count of comparative pages plus list of competitors covered. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P6-08 (comparative content optimisation for AI search) — same concept from GEO perspective.
- **Cross-references:** P0-06 (buyer journey stage) — comparative content typically targets consideration-stage queries.

---

## P4-15 — Methodology disclosure

**Pillar:** Content Operations
**Evidence weight:** Consensus

### Step 1 — Definition
For product reviews, comparisons, ratings, and recommendation-based content, the page discloses the methodology used to evaluate items: testing criteria, time spent, sample size, evaluation framework. Methodology disclosure is required by Google's Product Reviews Update guidelines.

### Step 2 — Citations
1. **Google Search Central — Product Reviews Update** (https://developers.google.com/search/docs/appearance/structured-data/product#review, Google, accessed May 2026). Authoritative documentation requiring methodology disclosure for product review content to qualify for rich results and avoid demotion.
2. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends explaining methodology, especially for product reviews.

### Step 3 — Evidence weight rationale
Google explicitly requires methodology disclosure for product reviews. Direct ranking impact via Product Reviews Update enforcement. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Composition.** LLM-driven detection of methodology sections in review content. Pattern detection for sections labelled "Our methodology", "How we tested", "Testing criteria", etc.

### Step 5 — Verification
LLM evaluation. Granularity required: per-page methodology presence boolean plus quality of methodology description. Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation cost.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P4-06 (E-E-A-T) — methodology disclosure is a Trust signal. P0-17 (YMYL) — methodology disclosure is especially important for YMYL review content.

---

## P4-16 — AI / automation use disclosure

**Pillar:** Content Operations
**Evidence weight:** Consensus

### Step 1 — Definition
For content created with AI assistance or automation, the page discloses this transparently and explains why automation enhanced the content's value. Google's Helpful Content guidance does not penalise AI-assisted content per se, but expects transparency about its use.

### Step 2 — Citations
1. **Google Search Central — Helpful Content guidance on AI** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Explicitly addresses AI / automation use disclosure: "Discloses AI or automation use transparently" and "Explains why automation enhanced content creation" are listed Helpful Content markers.
2. **Google Search Central — AI-generated content guidance** (https://developers.google.com/search/blog/2023/02/google-search-and-ai-content, Google). Google's official position: AI-assisted content is acceptable when it serves user value; transparent disclosure is part of trust.

### Step 3 — Evidence weight rationale
Google explicitly addresses this in Helpful Content guidance. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Composition.** Pattern detection for AI disclosure language plus LLM-driven evaluation of whether the content shows signs of AI generation that should be disclosed.

### Step 5 — Verification
Detection of disclosure statements + AI-content detection (cross-reference content originality scoring). Granularity required: per-page disclosure status plus AI-detection score. Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation cost.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P4-21 (mass-produced content detection) — undisclosed AI mass production is the negative pattern. P4-06 (E-E-A-T) — transparent disclosure supports Trust.

---

## P4-17 — YMYL handling rigour

**Pillar:** Content Operations
**Evidence weight:** Consensus

### Step 1 — Definition
For YMYL (Your Money or Your Life) pages identified by P0-17, the site applies elevated quality standards above what non-YMYL content requires: stronger E-E-A-T signals, more rigorous sourcing, professional credentials in author bios, factual accuracy verified, and conservative claim-making.

### Step 1.5 — Evaluation rules

A YMYL page passes elevated handling rigour when ALL of the following rules pass (in addition to all standard Helpful Content criteria):

1. **Author has verifiable professional credentials in the YMYL topic.** Medical content authors should have medical credentials; financial content authors should have financial credentials; legal content authors should have legal credentials.
2. **Content is reviewed by a qualified expert** before publication, with the reviewer named and credentialed.
3. **Sources cited include peer-reviewed research, government publications, or recognised authoritative institutions** — not just general-interest sources.
4. **Claims are conservative and qualified.** Avoid absolute statements ("this will cure", "you will save"); use measured language ("studies suggest", "consult a professional").
5. **Disclaimers are present.** Medical disclaimers (not medical advice), financial disclaimers (not financial advice), legal disclaimers (consult a professional) where appropriate.
6. **Content is regularly updated.** YMYL content has elevated freshness requirements (cross-references P4-02). Stale YMYL content risks providing dangerous outdated guidance.
7. **Trust signals are stronger.** Site has clear About, Contact, Editorial Policy pages.
8. **No deceptive monetisation.** Affiliate or commercial relationships are disclosed prominently (cross-references P4-20).

A YMYL page failing any of these rules has elevated risk; the system should never auto-deploy changes to YMYL pages without explicit human review.

### Step 2 — Citations
1. **Google Search Quality Rater Guidelines** (publicly published, latest 2024). The canonical YMYL definition and the elevated quality standards Google applies.
2. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Helpful Content guidance has YMYL-specific elevated requirements.
3. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names `ymylNewsScore` and `ymylHealthScore` as YMYL-specific scoring features.

### Step 3 — Evidence weight rationale
Google explicitly defines YMYL and applies elevated standards. Leak features confirm operational YMYL scoring. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Composition** combining P0-17 (YMYL classification) with E-E-A-T checks (P4-06), credentials check (P4-04), and content evaluation.

### Step 5 — Verification
Composition over existing variables. Granularity required: per-page YMYL handling status with rule-by-rule pass/fail. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Depends on:** P0-17 (YMYL classification).
- **Cross-references:** P4-06 (E-E-A-T), P4-04 (author bio), P4-15 (methodology), P4-20 (affiliate disclosure).

---

## P4-18 — Goldstandard human-rated content *(removed — May 2026 measurability audit)*

This variable was removed from the operational taxonomy in May 2026, following the same reasoning as P2-06. The leaked Google feature `goldStandard` marks documents that Google's Search Quality Raters have manually rated during evaluation cycles. The rating exists only inside Google's infrastructure and has no externally-observable signal: no API exposes which pages have been rated, and the rating itself informs Google's ML training rather than direct ranking. Recording the variable as a permanent "unmeasurable" added no operational value while inflating the coverage denominator. Quality Rater Guidelines and the principles raters apply remain a useful editorial reference for content evaluation but are captured through the operational content-quality variables (P4-06 E-E-A-T, P4-10 sourcing, P4-11 originality, etc.) rather than as a standalone goldStandard variable.

---

## P4-19 — UGC discussion effort score

**Pillar:** Content Operations
**Evidence weight:** Speculative

### Step 1 — Definition
The leaked Google feature `ugcDiscussionEffortScore` measuring the quality and substance of user-generated discussion content (forum threads, comment sections, Q&A platforms). High scores reflect substantive discussion; low scores reflect spam or low-effort content.

### Step 2 — Citations
1. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names `ugcDiscussionEffortScore` as a tracked feature for UGC content.
2. **No corroborating Tier A or B source.**

### Step 3 — Evidence weight rationale
Single source. Operational mechanism unclear. Most relevant to forum/community sites rather than typical commercial sites. Qualifies as **Speculative**.

### Step 4 — Data source(s)
- **Approximation: composition** combining LLM-driven evaluation of discussion quality with comment count, average comment length, and thread depth metrics.

### Step 5 — Verification
Variable approximate at best. Granularity required: per-page UGC quality score for sites with discussion content. Granularity delivered: by approximation.

### Step 6 — Cost
LLM evaluation cost.

### Step 7 — Dependencies and cross-references
- **Watchlist entry.**
- **Limited applicability:** only relevant for sites with substantial UGC.

---

## P4-20 — Affiliate link disclosure and quality

**Pillar:** Content Operations
**Evidence weight:** Consensus

### Step 1 — Definition
The site discloses affiliate relationships transparently and the affiliate content provides genuine value beyond product promotion. Both Google and the FTC require disclosure of compensated relationships; quality affiliate content adds value through testing, comparison, or original analysis rather than pure promotion.

### Step 1.5 — Evaluation rules

A page with affiliate links passes disclosure and quality check when ALL of the following rules pass:

1. **Affiliate disclosure is present and prominent** at or near the top of the content (FTC requirement: "clear and conspicuous").
2. **Affiliate links use `rel="sponsored"`** attribute (Google requirement; cross-references P3-18).
3. **The page provides substantive value beyond product links.** Either testing/review/comparison content, or original analysis, or curated expert recommendations — not just a list of products with affiliate codes.
4. **Editorial integrity is preserved.** The content's recommendations are not exclusively driven by commission rates; lower-commission products that genuinely solve user needs are recommended where appropriate.
5. **Disclosure language is clear** to non-experts. "We may earn a commission" is acceptable; jargon like "monetised content" is insufficient.

### Step 2 — Citations
1. **FTC Endorsement Guides** (https://www.ftc.gov/business-guidance/resources/disclosures-101-social-media-influencers, Federal Trade Commission, accessed May 2026). Legal requirement for disclosure of compensated relationships in the US.
2. **Google Search Central — Affiliate programs** (https://developers.google.com/search/docs/essentials/spam-policies#affiliate, Google, accessed May 2026). Documents Google's expectations for affiliate content quality and disclosure.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #47 (Affiliate Links), #181 (Hiding Affiliate Links).

### Step 3 — Evidence weight rationale
Both legal (FTC) and search-engine (Google) requirements. Direct ranking impact for failed disclosure. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Composition.** Detect affiliate disclosure language plus check rel attributes on outbound links.

### Step 5 — Verification
Pattern detection over content. Granularity required: per-page affiliate disclosure status plus rule-by-rule compliance. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-18 (sponsored/UGC tags), P4-06 (E-E-A-T trust signals), P0-17 (YMYL — affiliate disclosure especially important for YMYL).

---

## P4-21 — Mass-produced content detection

**Pillar:** Content Operations
**Evidence weight:** Consensus

### Step 1 — Definition
Detection of patterns indicating mass production of low-effort content — auto-generated articles, scaled content networks, AI-produced content without value-add, or large numbers of templated pages with minor variations. Mass-produced content is explicitly demoted by Google's Helpful Content System.

### Step 1.5 — Evaluation rules

A site triggers mass-produced content detection when ANY of the following rules detect:

1. **Templated content with minor variations.** Many pages with similar structure where only product names or location names change.
2. **High publication velocity inconsistent with editorial quality.** Hundreds of articles per month on diverse topics with thin author attribution.
3. **AI-generated content without disclosure** (cross-references P4-16) where the content shows AI-style patterns (over-uniform structure, GPT-detectable artefacts) and lacks the value-add Google's guidance requires.
4. **Content scaled across many domain network properties.** Same content network publishing similar content across multiple domains.
5. **Author profiles are AI-generated or stock photos.** Bio photos appearing in stock photo databases or showing AI-generation artefacts.
6. **Content lacks first-hand experience signals** (cross-references P4-06 Experience pillar) — entirely synthesised from public information without value-add.

A site is flagged as mass-produced content when multiple rules trigger.

### Step 2 — Citations
1. **Google Search Central — Helpful Content System** (https://developers.google.com/search/docs/appearance/helpful-content-update, Google, accessed May 2026). Authoritative documentation on Google's site-wide demotion of mass-produced content.
2. **Google Search Central — Spam Policies on scaled content** (https://developers.google.com/search/docs/essentials/spam-policies#scaled-content-abuse, Google). Explicit policy on scaled content abuse.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #184 (Autogenerated Content), Factor #12 (Mass-produced content).

### Step 3 — Evidence weight rationale
Google explicitly documents Helpful Content System and scaled content abuse policies. Direct ranking impact for sites flagged. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Composition.** Cross-page content similarity analysis + publication velocity + author authenticity checks + LLM-driven AI-content detection.

### Step 5 — Verification
Composition over existing data plus LLM evaluation. Granularity required: per-site mass-produced content status with rule-by-rule findings. Granularity delivered: by composition.

### Step 6 — Cost
Bundled with content analysis costs.

### Step 7 — Dependencies and cross-references
- **Scope of this variable:** site-scale pattern detection — flags sites with mass-produced content production across many pages (templated structure, scaled velocity, AI authorship, content-farm hallmarks). Different from per-page originality (P1-38, P4-07): focuses on the *pattern across the site* rather than the quality of any single page.
- **Hierarchy:** P1-38 → per-page numerical originality. P1-46 → in-site duplication. P4-07 → per-page editorial originality. **P4-21 (this) → site-scale mass-production pattern**. P4-22 → site-wide Panda risk (aggregates P4-07 + P4-21 + P4-09 + P4-10 site-level).
- **Cross-references:** P4-07 (per-page originality is one input to detecting mass-production), P4-16 (AI disclosure overlaps with rule 3), P4-22 (Panda risk aggregates this variable).

---

## P4-22 — Site-wide quality (Panda)

**Pillar:** Content Operations
**Evidence weight:** Consensus

### Step 1 — Definition
A site-wide quality score that affects all pages on the site. The Panda algorithm (introduced 2011, integrated into core algorithm 2016) demotes sites with substantial proportions of low-quality content. The leaked Google features `babyPandaDemotion` and `babyPandaV2Demotion` confirm site-level quality demotions still operate.

### Step 1.5 — Evaluation rules
A site passes Panda site-wide quality screening when ALL of the following rules pass:

1. **Originality across the site is high.** Aggregate P4-07 originality scores show fewer than ~10% of pages flagged as low-originality (templated, near-duplicate of external sources, AI-generated boilerplate).
2. **Mass-produced content not present.** P4-21 mass-produced content detection finds no large clusters of templated, low-substance pages.
3. **Thin content proportion is low.** Fewer than ~10% of indexable pages are thin (under-substance for the topic, under target word count for query intent, under SERP-competitor-average from P4-08).
4. **Sourcing is broadly present.** Substantive factual claims across the site are sourced (P4-10) at acceptable density.
5. **Insightful analysis is present in the substantive page set.** P4-09 insightfulness scores are not uniformly low; flagship content adds analytical value.
6. **No site-wide content-farm pattern.** Site does not exhibit content-farm hallmarks (high publication velocity with low per-page substance, no named authors, generic stock-image headers, monetisation-driven topic selection unrelated to expertise).
7. **Internal-link signals are not gamed.** Internal anchor distribution does not show keyword stuffing or links from unrelated pages purely to pass authority.
8. **No deceptive monetisation pattern site-wide.** Affiliate disclosure (P4-20) is consistent; no site-wide pattern of hidden affiliate links or undisclosed sponsored content.

A site passing all 8 rules has low Panda risk. Failures aggregate at site level — a single low-quality page does not trigger Panda, but a substantial proportion does.

### Step 2 — Citations
1. **Google Webmaster Central Blog — Panda algorithm announcements** (multiple, 2011 onwards). Authoritative documentation of the Panda site-quality system.
2. **iPullRank — Google Content Warehouse Leak Analysis** (https://ipullrank.com/google-algo-leak, Mike King, accessed May 2026). Names `babyPandaDemotion` and `babyPandaV2Demotion` confirming Panda-style site-wide quality demotions are operational.
3. **Backlinko — Google's 200 Ranking Factors** (https://backlinko.com/google-ranking-factors, Brian Dean). Factor #172 (Panda Penalty).

### Step 3 — Evidence weight rationale
Google has publicly documented Panda since 2011 and integrated it into core ranking. Leak confirms continued operation. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Composition** aggregating P4-07 (originality), P4-21 (mass-produced detection), P4-09 (insightfulness), P4-10 (sourcing) at site level.

### Step 5 — Verification
Composition over existing variables. Granularity required: per-site Panda-risk score plus list of contributing low-quality pages. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Aggregates:** P4-07, P4-09, P4-10, P4-21.
- **Used by:** the system applies elevated risk and conservative recommendations to sites with high Panda risk.

---

## P4-23 — Headlines accuracy (no clickbait/exaggeration)

**Pillar:** Content Operations
**Evidence weight:** Consensus

### Step 1 — Definition
Page titles, headlines, and section headings accurately describe the content they introduce. Avoids exaggerated, sensationalised, or clickbait-style headlines that don't deliver on their implicit promise.

### Step 1.5 — Evaluation rules
A page passes headline accuracy when ALL of the following rules pass:

1. **Title delivers on the content's actual scope.** The title describes what the page actually covers, not a broader claim ("Complete Guide to X" when the page covers only one aspect of X).
2. **No clickbait phrasing.** Title and headlines avoid known clickbait patterns: "you won't believe", "this one trick", "doctors hate this", "shocking truth", numbered-list bait without substance ("17 Things You Need to Know" with thin content).
3. **Numerical claims in the title are accurate.** "Top 10" pages list 10 substantive entries; "5-step guide" pages have 5 substantive steps; "$1,000 tip" pages deliver content related to that figure.
4. **Headlines match section content.** Section H2/H3 headings describe the section that follows; no bait-and-switch where heading promises X and content delivers Y.
5. **Superlatives are supported.** Words like "best", "ultimate", "definitive" are backed by methodology disclosure or comparative analysis; not bare assertions.
6. **No emotional manipulation in title.** Titles do not rely on fear-mongering, false urgency, or outrage triggers when the content does not warrant them.
7. **Title and meta description align with body content.** A reader landing on the page from the SERP snippet finds the page meets the snippet's promise.

A page passing all 7 rules has accurate headlines.

### Step 2 — Citations
1. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Lists "uses descriptive, helpful headlines and page titles" and "avoids exaggerated or shocking headlines" as Helpful Content markers.
2. **Google Search Central — Page experience considerations**. Misleading headlines damage user experience.

### Step 3 — Evidence weight rationale
Google explicitly addresses headline accuracy in Helpful Content. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Composition.** LLM-driven evaluation comparing headline claims to content delivery; pattern detection for clickbait phrases ("you won't believe", "this one trick", "doctors hate this").

### Step 5 — Verification
LLM evaluation. Granularity required: per-page headline accuracy assessment plus list of detected clickbait patterns. Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation cost.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P1-01 (title presence), P1-03 (title keyword inclusion), P1-11 (H1 presence).

---

## P4-24 — Quarterly content refresh cycle

**Pillar:** Content Operations
**Evidence weight:** Probable

### Step 1 — Definition
The site has an established editorial process for refreshing content quarterly, updating pages with current information, statistics, and references. Articulated by Foundation Inc as a GEO best practice for maintaining content currency for AI search citation.

### Step 2 — Citations
1. **Foundation Inc — Generative Engine Optimization Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Identifies quarterly refresh as a GEO best practice.
2. **Google Search Central — Helpful Content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Recommends ongoing content maintenance.

### Step 3 — Evidence weight rationale
Practitioner framework with general support from Google's freshness guidance. Specific quarterly cadence not Google-endorsed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition** over historical crawl snapshots tracking refresh patterns per page.

### Step 5 — Verification
Composition over P1-44 (update magnitude) and P1-45 (update cadence) at site level. Granularity required: per-site percentage of content updated within last 90 days plus identification of pages overdue for refresh. Granularity delivered: by composition.

### Step 6 — Cost
Bundled.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P1-44, P1-45 (page-level updates), P4-01 (publishing cadence), P4-02 (freshness).

---

# Pillar 5 — Local SEO

**Total candidates:** 28
**Status:** Complete (28 of 28)

## Pillar 5 Index

| ID | Variable | Status | Weight |
|----|----------|--------|--------|
| P5-01 | Proximity to searcher | Complete | Consensus |
| P5-02 | GBP primary category alignment | Complete | Consensus |
| P5-03 | GBP secondary categories | Complete | Consensus |
| P5-04 | GBP profile completeness | Complete | Consensus |
| P5-05 | NAP consistency across web | Complete | Consensus |
| P5-06 | Local citations count | Complete | Probable |
| P5-07 | Local citation authority and platform diversity | Complete | Probable |
| P5-08 | Niche/industry citation presence | Complete | Probable |
| P5-09 | Review count | Complete | Consensus |
| P5-10 | Review average star rating | Complete | Consensus |
| P5-11 | Review velocity | Complete | Consensus |
| P5-12 | Review recency | Complete | Probable |
| P5-13 | Review response rate | Complete | Consensus |
| P5-14 | Review response personalisation | Complete | Probable |
| P5-15 | Review response speed | Complete | Probable |
| P5-16 | Review keyword content | Complete | Probable |
| P5-17 | Review photos/videos | Complete | Probable |
| P5-18 | Reviewer credibility | Complete | Probable |
| P5-19 | Review sentiment | Complete | Probable |
| P5-20 | Fake review detection / authenticity | Complete | Consensus |
| P5-21 | GBP photos count and freshness | Complete | Probable |
| P5-22 | GBP posts activity | Complete | Probable |
| P5-23 | GBP Q&A activity | Complete | Probable |
| P5-24 | GBP attributes (women-owned, etc.) | Complete | Probable |
| P5-25 | Service area / hours completeness | Complete | Consensus |
| P5-26 | LocalBusiness schema markup | Complete | Consensus |
| P5-27 | Engagement signals (clicks, calls, direction requests) | Complete | Consensus |
| P5-28 | Location demotion (irrelevant geo) | Complete | Consensus |

---

## P5-01 — Proximity to searcher

**Pillar:** Local SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The physical distance between the business's location (as registered in Google Business Profile) and the searcher's location at the time of search. Proximity is the single most influential factor in Google's Local Pack and Map rankings — Whitespark's 2026 Local Search Ranking Factors study attributes approximately 55% of local pack ranking weight to proximity.

### Step 2 — Citations
1. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, Whitespark, accessed May 2026). Authoritative annual local SEO study identifying proximity as the dominant local pack ranking factor at approximately 55% influence.
2. **Google Search Central — Improve your local ranking on Google** (https://support.google.com/business/answer/7091, Google, accessed May 2026). Lists proximity (along with relevance and prominence) as one of three factors Google uses for local ranking.
3. **BrightLocal — Local SEO research** (https://www.brightlocal.com/research/, accessed May 2026). Industry research consistently confirms proximity as the dominant factor.

### Step 3 — Evidence weight rationale
Google explicitly documents proximity as one of three local ranking factors. Whitespark's study quantifies it. Multiple industry sources align. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google Business Profile API** for the business's registered location.
- **Searcher location: not directly observable** — Google determines proximity per individual search based on the searcher's IP, GPS, or stated location.
- **Composition: simulation.** For target keywords, query GBP listings near the centre of the target service area (e.g., a downtown coordinate) to see local pack ranking from that vantage point.

### Step 5 — Verification
Direct measurement is impossible (each searcher has their own location). Composition-based simulation provides directional measurement. Granularity required: per-business latitude/longitude plus simulated rankings from various target-area centres. Granularity delivered: by composition.

### Step 6 — Cost
GBP API: free with rate limits.

### Step 7 — Dependencies and cross-references
- **Used by:** local pack ranking estimation; service-area and multi-location strategy decisions.

---

## P5-02 — GBP primary category alignment

**Pillar:** Local SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The Google Business Profile primary category accurately reflects the business's main offering and aligns with the search queries customers use to find it. The primary category is the single most influential GBP signal for what queries the business will surface for. Whitespark identifies primary category as the top GBP-controlled ranking factor.

### Step 1.5 — Evaluation rules
A business passes GBP primary category alignment when ALL of the following rules pass:

1. **Primary category is set.** GBP has a non-empty primary category declaration.
2. **Category matches actual primary offering.** Declared primary category corresponds to the business's largest revenue-generating service or product, not a peripheral offering.
3. **Most-specific applicable category used.** Where the GBP taxonomy offers a hierarchy ("Restaurant" → "Italian Restaurant" → "Pizza Restaurant"), the most-specific applicable category is selected.
4. **Category aligns with target keywords.** The category corresponds to the queries the business is targeting (P0-13 keyword-to-page mapping); a "Plumber" category for a business targeting "emergency plumber" queries.
5. **Category aligns with website content.** The website's homepage and About page describe the business in terms consistent with the declared category.
6. **No keyword-stuffing in business name.** The declared business name does not append keywords ("Joe's Plumbing - 24/7 Emergency Plumber Near Me"); only the legal/displayed business name is in the name field. Keywords are expressed via category, not name.
7. **Category competitors check.** The category's typical competitors (visible in local pack for category-relevant queries) are direct competitors of the business, confirming category fit.

A business passing all 7 rules has correct primary category alignment.

### Step 2 — Citations
1. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, Whitespark, accessed May 2026). Identifies primary category as the most influential GBP-controlled factor in the local pack.
2. **Google Business Profile Help — Categories** (https://support.google.com/business/answer/3038177, Google, accessed May 2026). Authoritative documentation on category selection and its influence.
3. **BrightLocal — Local SEO research** confirms primary category alignment as foundational.

### Step 3 — Evidence weight rationale
Google documents categories explicitly. Industry research consistently identifies primary category as foundational. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google Business Profile API** for declared primary category.
- **Alignment validation: composition.** Compare declared category against business descriptions, target keywords (P0-13), and competitor categories.

### Step 5 — Verification
GBP API documented. Granularity required: per-business primary category plus alignment assessment with target queries. Granularity delivered: by composition.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P0-13 (keyword-to-page mapping) — primary category should align with primary target queries.
- **Companion to:** P5-03 (secondary categories).

---

## P5-03 — GBP secondary categories

**Pillar:** Local SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The set of secondary categories declared in Google Business Profile beyond the primary category. Secondary categories expand visibility for related queries without diluting the primary positioning. Google allows up to 10 categories total (1 primary + up to 9 secondary).

### Step 1.5 — Evaluation rules
A business passes GBP secondary category configuration when ALL of the following rules pass:

1. **At least one secondary category declared where applicable.** Multi-service businesses declare secondary categories for their distinct service lines.
2. **Each secondary category is genuinely offered.** Every declared secondary category corresponds to a real service or product the business actually provides; no aspirational or competitor-poaching categories.
3. **No duplicate or near-duplicate categories.** Each secondary category is distinct from the primary and from other secondaries (no listing both "Italian Restaurant" and "Pizza Restaurant" when one already covers the offering).
4. **No over-categorisation.** Total category count (primary + secondaries) is reasonable for the actual business scope; not all 10 slots stuffed when only 2–3 services are genuinely offered.
5. **Secondary categories complement, not dilute.** Secondaries cover related but distinct service lines; they do not contradict the primary positioning.
6. **No keyword-stuffing-via-category.** Categories are not used to capture unrelated high-volume queries (a "Plumber" listing also declaring "Restaurant" would be a violation).
7. **Categories align with attributes and services list.** Declared secondaries are reflected in the corresponding services list and attributes.

A business passing all 7 rules has correct GBP secondary category configuration.

### Step 2 — Citations
1. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, Whitespark, accessed May 2026). Documents secondary categories as influential, with appropriate use expanding visibility for related queries.
2. **Google Business Profile Help — Categories** (https://support.google.com/business/answer/3038177, Google, accessed May 2026). Documents the multi-category framework.

### Step 3 — Evidence weight rationale
Google documents the multi-category system. Whitespark's study quantifies impact. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google Business Profile API** for declared secondary categories.
- **Recommendation logic: our own.** For each business, identify additional relevant categories from Google's category taxonomy that match offered services or products.

### Step 5 — Verification
GBP API documented. Granularity required: per-business secondary category list plus suggestions for additions. Granularity delivered: by composition.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Companion to:** P5-02 (primary category).
- **Cross-references:** P5-25 (services list — closely related to category coverage).

---

## P5-04 — GBP profile completeness

**Pillar:** Local SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The Google Business Profile has all available fields populated with current, accurate information: business name, address, phone, website, hours, services, attributes, photos, descriptions, products. Complete profiles outperform incomplete ones in local rankings and conversion.

### Step 1.5 — Evaluation rules

A GBP passes completeness check when ALL of the following rules pass:

1. **Business name is set** matching the legal/displayed business name (no keyword stuffing — Google penalises this).
2. **Address is verified** with confirmed business location.
3. **Phone number is set** with primary contact number.
4. **Website URL is set** pointing to the live business site.
5. **Hours are set** including special hours for holidays and exceptions.
6. **Primary category is set** (cross-references P5-02).
7. **At least 3 secondary categories are set** where relevant (cross-references P5-03).
8. **Business description is present** (up to 750 characters; should describe what the business does, not keyword-stuff).
9. **At least 10 photos uploaded** — exterior, interior, products, team (cross-references P5-21).
10. **Logo is set** as profile picture.
11. **Cover photo is set.**
12. **Services or products are listed** with descriptions.
13. **Attributes appropriate to category are set** (e.g., wheelchair-accessible, accepts credit cards, women-owned).
14. **Q&A section has been seeded** with common questions answered by the owner.
15. **Posts have been published** within the last 30 days (cross-references P5-22).

### Step 2 — Citations
1. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, Whitespark, accessed May 2026). Profile completeness consistently identified as a top-tier factor.
2. **BrightLocal — Local Consumer Review Survey and Local SEO research**. Documents GBP completeness as a primary local visibility lever.
3. **Google Business Profile Help** (https://support.google.com/business/, Google, accessed May 2026). Authoritative documentation on each profile field.

### Step 3 — Evidence weight rationale
Google maintains the GBP product and explicitly recommends completeness. Industry research consistently identifies it as foundational. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google Business Profile API** for all profile fields.
- **Completeness logic: our own** rule-by-rule checking against Step 1.5.

### Step 5 — Verification
GBP API exposes all profile fields. Rule checking is composition. Granularity required: per-business completeness percentage plus list of missing fields. Granularity delivered: by composition.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P5-02, P5-03, P5-21, P5-22, P5-23, P5-24, P5-25.

---

## P5-05 — NAP consistency across web

**Pillar:** Local SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The business's Name, Address, and Phone number (NAP) appear consistently across the web — on the business's own site, on GBP, on local citations, on social profiles, on industry directories. Inconsistencies (different addresses, different phone formats, different business names) confuse Google and damage local ranking.

### Step 1.5 — Evaluation rules

A business passes NAP consistency when ALL of the following rules pass:

1. **Business name is identical across sources.** "Smith & Co Plumbing" not "Smith and Company Plumbers" or "Smith Plumbing Inc." in different places.
2. **Address is identical across sources.** Same street name format ("Street" vs "St."), same suite/unit format, same postcode format.
3. **Phone number format is consistent.** Same number across sources, even if formatted differently (parentheses vs spaces vs dashes — all referring to the same number).
4. **Business website URL is consistent.** Either www-prefixed or not, same protocol (HTTPS).
5. **No outdated/abandoned listings** under previous addresses or numbers.
6. **NAP appears in plain text on the business's own site** (not just in images or behind contact forms) — Google needs to scrape it.

A site fails when even one rule has measurable inconsistency across discovered citations.

### Step 2 — Citations
1. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, BrightLocal, accessed May 2026). Identifies NAP consistency as foundational; inconsistent listings damage rankings and trust.
2. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, Whitespark, accessed May 2026). NAP consistency listed as foundational requirement.
3. **Moz — Local SEO Guide** (https://moz.com/learn/seo/local, Moz, accessed May 2026). Industry standard guidance on NAP.

### Step 3 — Evidence weight rationale
Universal industry consensus. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: composition.** Aggregate NAP data from GBP API + crawl of business's site + citation scrape (BrightLocal, Yext, or DataForSEO citation discovery).
- **Comparison logic: our own.** Normalise NAP variations and detect inconsistencies.

### Step 5 — Verification
Composition over multiple sources. Granularity required: per-business consistency status plus list of inconsistent listings. Granularity delivered: by composition.

### Step 6 — Cost
Citation discovery may add cost (BrightLocal, Yext subscriptions ~£20-100/month) or free with our own search-based discovery.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P5-04 (GBP completeness), P5-06 (citation count).

---

## P5-06 — Local citations count

**Pillar:** Local SEO
**Evidence weight:** Probable

### Step 1 — Definition
The total count of business citations — listings across local directories (Yelp, Yellow Pages, Foursquare, industry-specific directories, regional directories). Citations contribute to local prominence and provide authoritative confirmation of NAP information.

### Step 2 — Citations
1. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, Whitespark, accessed May 2026). Citations remain influential, particularly when consistent and from authoritative sources.
2. **BrightLocal — Local SEO research** confirms citations as foundational.
3. **Industry-standard citation building practice** as documented across Moz, BrightLocal, Whitespark guides.

### Step 3 — Evidence weight rationale
Practitioner consensus. Specific operational weight has decreased over time as Google increasingly relies on direct GBP signals; citations remain important but less dominant than in earlier years. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: BrightLocal Citation Tracker, Yext, or Whitespark Local Citation Finder** — subscription services that maintain citation databases.
- **Alternative: composition.** Search engine queries for "{business name} {city}" to discover citation listings.

### Step 5 — Verification
Multiple commercial services available; composition-based discovery is feasible. Granularity required: per-business citation count plus list of platforms. Granularity delivered: matches.

### Step 6 — Cost
Subscription services: ~£20-50/month. Composition-based discovery: free but more time-consuming.

### Step 7 — Dependencies and cross-references
- **Companion to:** P5-05 (NAP consistency), P5-07 (citation authority and diversity).

---

## P5-07 — Local citation authority and platform diversity

**Pillar:** Local SEO
**Evidence weight:** Probable

### Step 1 — Definition
The authority and diversity of platforms hosting the business's citations. Citations from major authoritative platforms (Yelp, Better Business Bureau, industry-leading directories) carry more weight than citations from low-quality directories. Diversity across platform types (general, industry-specific, regional) signals broader recognition.

### Step 2 — Citations
1. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, Whitespark, accessed May 2026). Citation source authority and platform diversity matter alongside raw count.
2. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, BrightLocal, accessed May 2026). Documents that consumers consult an average of 6 review/citation platforms; broader diversity supports both direct discovery and Google's confidence in the business.

### Step 3 — Evidence weight rationale
Practitioner consensus. Specific operational weighting not officially disclosed by Google. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition.** From the citation list (P5-06), classify each platform by authority tier (Tier 1: GBP, Yelp, Apple Business Connect, Bing Places; Tier 2: BBB, Foursquare, major industry directories; Tier 3: smaller regional or niche directories).

### Step 5 — Verification
Composition over P5-06 data. Granularity required: per-business citation distribution by tier plus list of high-value missing platforms. Granularity delivered: by composition.

### Step 6 — Cost
Bundled with P5-06.

### Step 7 — Dependencies and cross-references
- **Depends on:** P5-06 (citation count).
- **Companion to:** P5-08 (niche/industry citation presence).

---

## P5-08 — Niche/industry citation presence

**Pillar:** Local SEO
**Evidence weight:** Probable

### Step 1 — Definition
The business is listed on niche-specific directories appropriate to its industry — Avvo for lawyers, Healthgrades for doctors, Zillow for real estate, TripAdvisor for hospitality, etc. Industry-specific platforms carry stronger relevance signals for the specific business type than general-purpose directories.

### Step 2 — Citations
1. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, accessed May 2026). Industry-specific citations weighted alongside general directories for relevance signals.
2. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Documents that consumers consult industry-specific review platforms when evaluating businesses.

### Step 3 — Evidence weight rationale
Practitioner consensus, supported by industry research. Specific operational weight not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Composition.** Maintain industry-to-platform mapping (legal: Avvo, FindLaw; medical: Healthgrades, Vitals; restaurants: TripAdvisor, OpenTable; etc.). Check business presence on appropriate platforms.

### Step 5 — Verification
Composition over per-industry platform lists plus search-based discovery. Granularity required: per-business presence on industry platforms plus list of missing platforms. Granularity delivered: by composition.

### Step 6 — Cost
Free to discover via search; subscription services (BrightLocal, Yext) provide pre-built industry mappings.

### Step 7 — Dependencies and cross-references
- **Companion to:** P5-06 (citation count), P5-07 (citation authority).

---

## P5-09 — Review count

**Pillar:** Local SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The total count of reviews across the business's Google Business Profile and major review platforms (Yelp, Facebook, industry-specific platforms). Higher review counts increase consumer trust and signal active customer base. BrightLocal research finds 47% of consumers won't use a business with fewer than 20 reviews.

### Step 2 — Citations
1. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Documents 47% consumer threshold at 20 reviews; ongoing review count growth correlates with consumer trust.
2. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, accessed May 2026). Review signals grew from 16% in 2023 to ~20% in 2026.
3. **Google Business Profile Help** (https://support.google.com/business/answer/3474122, Google, accessed May 2026). Documents reviews as a local ranking input via "prominence."

### Step 3 — Evidence weight rationale
Google explicitly documents reviews as a prominence signal. Practitioner research consistently confirms. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google Business Profile API** for GBP review count.
- **Multi-platform: composition** across Yelp API, Facebook Graph API, industry platforms.

### Step 5 — Verification
GBP API documented. Granularity required: per-business review count by platform plus aggregate. Granularity delivered: matches.

### Step 6 — Cost
GBP API free; some platforms charge for API access (Yelp, etc.).

### Step 7 — Dependencies and cross-references
- **Companion to:** P5-10 (rating), P5-11 (velocity), P5-12 (recency).

---

## P5-10 — Review average star rating

**Pillar:** Local SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The average star rating across all reviews on the business's GBP profile and major review platforms. BrightLocal research documents that consumers expect a minimum 4.5-star rating to consider a business; lower ratings damage both trust and ranking visibility.

### Step 2 — Citations
1. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Documents the 4.5-star minimum consumer expectation.
2. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, accessed May 2026). Average star rating is a confirmed ranking input.
3. **Google Business Profile** displays average rating prominently in search results, directly affecting click-through.

### Step 3 — Evidence weight rationale
Google displays ratings publicly and uses them for ranking. Industry research aligns. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google Business Profile API** for GBP average rating.
- **Cross-platform: composition** across review platforms.

### Step 5 — Verification
GBP API documented. Granularity required: per-business average rating by platform plus aggregate. Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Companion to:** P5-09 (count), P5-19 (sentiment), P5-20 (authenticity).

---

## P5-11 — Review velocity

**Pillar:** Local SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The rate at which the business acquires new reviews over time. Whitespark identifies review velocity as one of the most influential review signals in 2026 — businesses gaining reviews consistently outrank businesses with stale review histories regardless of total count.

### Step 2 — Citations
1. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, accessed May 2026). Review velocity quantified as one of the most influential review signals.
2. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Confirms velocity-of-recent-reviews as a primary trust signal.

### Step 3 — Evidence weight rationale
Two major industry studies align. Google has indicated review recency matters for prominence calculation. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: GBP API** for review timestamps.
- **Composition: our own** velocity calculation per rolling window (reviews per 30/90 days).

### Step 5 — Verification
GBP API exposes review timestamps. Granularity required: per-business review velocity time-series. Granularity delivered: by composition.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Companion to:** P5-09, P5-12 (recency).

---

## P5-12 — Review recency

**Pillar:** Local SEO
**Evidence weight:** Probable

### Step 1 — Definition
How recent the most recent reviews are. BrightLocal research documents that consumers expect reviews from the last month or last three months; stale review histories signal an inactive business.

### Step 2 — Citations
1. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Documents consumer expectations for review recency.
2. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, accessed May 2026). Recency is part of the velocity-and-freshness review signal cluster.

### Step 3 — Evidence weight rationale
Practitioner research consistent. Specific operational weight in Google's algorithm not officially disclosed but the consumer expectation directly affects trust and click-through. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: GBP API** review timestamps.

### Step 5 — Verification
Direct from GBP. Granularity required: per-business most-recent-review timestamp plus age categorisation. Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Companion to:** P5-11 (velocity).

---

## P5-13 — Review response rate

**Pillar:** Local SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The percentage of reviews the business has responded to. Whitespark research identifies response rate as a key signal; consistent response demonstrates active business management and engagement with customers.

### Step 2 — Citations
1. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, accessed May 2026). Response rate listed as a ranking factor.
2. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Documents that response rate affects consumer trust.
3. **Google Business Profile Help — Replying to reviews** (https://support.google.com/business/answer/3474050, Google, accessed May 2026). Google explicitly recommends responding to reviews.

### Step 3 — Evidence weight rationale
Google recommends responding. Industry research aligns. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: GBP API** for review-response data.

### Step 5 — Verification
GBP API exposes response data. Granularity required: per-business response rate plus list of unanswered reviews. Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Companion to:** P5-14 (personalisation), P5-15 (response speed).

---

## P5-14 — Review response personalisation

**Pillar:** Local SEO
**Evidence weight:** Probable

### Step 1 — Definition
The degree to which review responses are personalised — addressing the specific feedback in each review — versus templated/generic responses. BrightLocal research identifies generic templates as actively damaging consumer trust even when response rate is high.

### Step 1.5 — Evaluation rules

A business passes review response personalisation when ALL of the following rules pass:

1. **No identical or near-identical response text appears across multiple reviews.** Significant duplication suggests template use.
2. **Responses reference specific elements from the original review** — the customer's name, the specific service mentioned, the location visited, the date.
3. **Responses include the customer's first name** where the review attribution allows.
4. **Negative reviews receive substantive responses** that address the specific complaint rather than deflecting with generic apology language.
5. **Response language varies appropriately by review sentiment** — positive reviews get warm thanks; negative reviews get problem-acknowledgement and remediation offers.

### Step 2 — Citations
1. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Documents response personalisation specifically — generic templates negatively impact trust.

### Step 3 — Evidence weight rationale
Practitioner research with clear consumer impact. Direct ranking weight not separately quantified from the broader review-response signal. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: GBP API** for review and response text.
- **Personalisation analysis: composition.** LLM-driven evaluation of response personalisation comparing each response to the source review.

### Step 5 — Verification
LLM evaluation. Granularity required: per-response personalisation score plus rule-by-rule pass/fail. Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation cost (~$0.0005 per review-response pair).

### Step 7 — Dependencies and cross-references
- **Depends on:** P5-13 (response rate).
- **Companion to:** P5-15 (response speed), P5-19 (sentiment).

---

## P5-15 — Review response speed

**Pillar:** Local SEO
**Evidence weight:** Probable

### Step 1 — Definition
The elapsed time between a review being posted and the business owner's response. BrightLocal research documents that consumers expect responses within the same day or within one week; faster responses signal active business management and improve consumer trust.

### Step 2 — Citations
1. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Documents consumer expectations on response speed.
2. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, accessed May 2026). Engagement signals including response speed are part of local pack signal cluster.

### Step 3 — Evidence weight rationale
Practitioner research consistent. Specific operational ranking weight not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: GBP API** for review and response timestamps.

### Step 5 — Verification
GBP API exposes both timestamps. Granularity required: per-business median response time plus distribution. Granularity delivered: by composition.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Companion to:** P5-13 (response rate), P5-14 (response personalisation).

---

## P5-16 — Review keyword content (mentions of services / locations)

**Pillar:** Local SEO
**Evidence weight:** Probable

### Step 1 — Definition
The frequency and prominence of relevant keywords in review text — mentions of specific services offered, neighbourhoods served, products provided, or category-defining terms. Reviews containing these keywords reinforce Google's understanding of what the business offers and where.

### Step 2 — Citations
1. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Documents review keyword content as influential.
2. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, accessed May 2026). Review content keywords contribute to relevance signals for the business's category and service area.

### Step 3 — Evidence weight rationale
Practitioner research with reasoning that aligns with Google's stated relevance factor. Specific operational weight not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: GBP API** for review text.
- **Composition: our own** keyword extraction across review corpus, comparing against the business's target keyword cluster (P0-13).

### Step 5 — Verification
LLM-driven keyword and entity extraction over reviews. Granularity required: per-business keyword frequency table plus list of well-mentioned vs underrepresented services. Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation cost negligible at typical review volumes.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P0-13 (keyword strategy), P5-09 (review count).

---

## P5-17 — Review photos/videos

**Pillar:** Local SEO
**Evidence weight:** Probable

### Step 1 — Definition
The proportion of reviews that include photos or videos uploaded by the reviewer. Photo/video reviews carry stronger trust signals — they're harder to fake and provide consumer-uploaded visual evidence of the business or its products.

### Step 2 — Citations
1. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Documents that photo/video reviews increase consumer trust.
2. **Google Business Profile** displays user-uploaded photos prominently in the listing, increasing visibility and click-through.

### Step 3 — Evidence weight rationale
Practitioner research with direct consumer-trust impact and Google display prominence. Direct ranking impact not separately quantified. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: GBP API** for review media metadata.

### Step 5 — Verification
GBP API exposes media. Granularity required: per-business proportion of reviews with photos or videos. Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P5-21 (GBP photos overall — distinct from review photos).

---

## P5-18 — Reviewer credibility (history)

**Pillar:** Local SEO
**Evidence weight:** Probable

### Step 1 — Definition
The proportion of the business's reviews that come from reviewers with substantive review history — Local Guides, frequent Google reviewers, named accounts with multiple reviews — versus single-review or new accounts. Reviewer credibility distribution is a signal of review authenticity.

### Step 2 — Citations
1. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Documents reviewer credibility as a signal that affects both trust and Google's evaluation of review authenticity.
2. **Google Local Guides programme** (https://maps.google.com/localguides/, Google). Recognised programme for prolific reviewers; Google explicitly weights Local Guide reviews differently.

### Step 3 — Evidence weight rationale
Google operates the Local Guides programme. Practitioner research aligns. Specific operational weight not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: GBP API** for reviewer profile data including Local Guide level and review count.

### Step 5 — Verification
GBP API exposes reviewer metadata. Granularity required: per-business distribution of reviewer credibility tiers. Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Companion to:** P5-20 (fake review detection) — credible reviewer distribution is one signal of authenticity.

---

## P5-19 — Review sentiment

**Pillar:** Local SEO
**Evidence weight:** Probable

### Step 1 — Definition
The aggregate sentiment expressed across review text, distinct from raw star rating. A 4-star average with consistently glowing text versus 4-star average with mixed text reflects different customer experiences. Sentiment analysis reveals nuances the star rating alone misses.

### Step 2 — Citations
1. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Documents review sentiment as a distinct signal beyond star ratings.
2. **Google Business Profile** AI summaries (rolled out 2024) explicitly synthesise review sentiment, indicating Google operationally extracts sentiment from review text.

### Step 3 — Evidence weight rationale
Practitioner research and Google's own AI summaries confirm sentiment extraction. Specific ranking weight not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: GBP API** review text.
- **Sentiment analysis: composition.** LLM-driven sentiment classification per review (positive / mixed / negative / specific aspect-based).

### Step 5 — Verification
LLM evaluation. Granularity required: per-business sentiment distribution plus aspect-based analysis (sentiment by service category, location, etc.). Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation cost negligible at typical review volumes.

### Step 7 — Dependencies and cross-references
- **Companion to:** P5-10 (star rating) — together describe consumer experience more completely than either alone.

---

## P5-20 — Fake review detection / authenticity

**Pillar:** Local SEO
**Evidence weight:** Consensus

### Step 1 — Definition
Detection of inauthentic reviews — review fraud, paid reviews, bot-generated reviews, competitor-attack negative reviews. Google explicitly prohibits fake reviews; sites with detected fake reviews face removal of those reviews and potential listing suspension.

### Step 1.5 — Evaluation rules

A review is flagged as potentially inauthentic when ANY of the following rules trigger:

1. **Burst pattern: many reviews from new accounts in a short window.** Multiple reviews within hours/days from accounts with no prior review history.
2. **Foreign-language reviews unrelated to target market.** Reviews in languages inconsistent with the business's customer base.
3. **Reviewer has rated only competitors negatively** while rating one business positively — pattern suggests competitor attack.
4. **Reviewer profile shows signs of being created for review purposes** — generic name, stock photo profile, no other Google activity.
5. **Review text shows AI-generation patterns** (uniform structure, generic praise, no specific business detail).
6. **Identical or near-identical text across multiple reviewers** — copy-paste patterns indicate paid review services.
7. **Review timestamp doesn't match plausible visit pattern** — review posted at 3am for a daytime-only business, or many reviews on the same day from the same geographic area inconsistent with foot traffic.
8. **Reviewer has posted negative reviews of unrelated businesses on the same day** — pattern of attack-pattern reviewing.

A review failing any of these rules is flagged as potentially inauthentic and queued for site-owner review and Google reporting.

### Step 2 — Citations
1. **Google Business Profile — Review Policies** (https://support.google.com/contributionpolicy/answer/7400114, Google, accessed May 2026). Authoritative policies on prohibited review behaviour including fake reviews.
2. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Documents fake review detection as a foundational consumer trust concern.
3. **FTC — Fake review enforcement** (https://www.ftc.gov/, FTC, accessed May 2026). Legal framework prohibiting fake review schemes in the US.

### Step 3 — Evidence weight rationale
Google explicitly prohibits fake reviews and removes them. FTC prohibits fake review schemes legally. Industry consensus on detection patterns. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Composition.** Apply Step 1.5 rules across review inventory using GBP API metadata (timestamps, reviewer profiles, text) plus LLM-driven content analysis.

### Step 5 — Verification
Composition over GBP data plus LLM evaluation. Granularity required: per-review authenticity flag plus rule that triggered. Granularity delivered: by composition.

### Step 6 — Cost
LLM cost.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P5-18 (reviewer credibility), P5-19 (sentiment).
- **Action:** flagged reviews surface as candidates for reporting to Google and contesting via the GBP interface.

---

## P5-21 — GBP photos count and freshness

**Pillar:** Local SEO
**Evidence weight:** Probable

### Step 1 — Definition
The total count of photos on the business's GBP plus how recently they have been added. Photos increase listing visibility and signal active business management. BrightLocal research documents that photo-rich GBP listings outperform photo-light ones.

### Step 2 — Citations
1. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Documents photo count and freshness as influential.
2. **Google Business Profile Help — Photos** (https://support.google.com/business/answer/6103862, Google, accessed May 2026). Recommends regularly adding photos.
3. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, accessed May 2026). Engagement signals including fresh photos are part of the ranking signal cluster.

### Step 3 — Evidence weight rationale
Google recommends; industry research confirms. Specific operational weight not officially disclosed. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: GBP API** for photos and timestamps.

### Step 5 — Verification
GBP API documented. Granularity required: per-business photo count by category (exterior, interior, products, team) plus freshness distribution. Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P5-04 (GBP profile completeness — photos are part of the completeness checklist).

---

## P5-22 — GBP posts activity

**Pillar:** Local SEO
**Evidence weight:** Probable

### Step 1 — Definition
The frequency and recency of Google Business Profile posts (offers, events, news, product updates) published by the business. GBP posts surface in the business's listing on Search and Maps, and consistent posting is widely treated by local SEO practitioners as an engagement and freshness signal that contributes to local pack visibility.

### Step 2 — Citations
1. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, accessed May 2026). Documents GBP posting consistency within the engagement signal cluster contributing to local pack rankings.
2. **Google Business Profile Help — Add updates to your Business Profile** (https://support.google.com/business/answer/7662907, Google, accessed May 2026). Google instructs businesses to post updates regularly to keep customers informed and to surface activity on the profile.
3. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Treats GBP activity (including posts) as a contributor to listing engagement and conversion.

### Step 3 — Evidence weight rationale
Google recommends posting and surfaces posts in the listing UI, but does not officially confirm posts as a ranking factor. Practitioner studies place posting in the broader engagement signal cluster rather than isolating its weight. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: Google Business Profile API — `localPosts` endpoint** for post inventory, type, and timestamps.

### Step 5 — Verification
GBP API documented and accessible to verified profile owners. Granularity required: per-business post count by type (offer, event, update) plus recency distribution (latest post, posts in last 30/90 days). Granularity delivered: matches.

### Step 6 — Cost
Free (GBP API has generous quotas).

### Step 7 — Dependencies and cross-references
- **Cross-references:** P5-04 (GBP profile completeness), P5-27 (engagement signals — posts drive clicks and conversion events).

---

## P5-23 — GBP Q&A activity

**Pillar:** Local SEO
**Evidence weight:** Probable

### Step 1 — Definition
The presence and management of the questions-and-answers section on the business's Google Business Profile. Both customer-asked questions and owner-uploaded FAQ pairs appear; owner responses and proactive seeding of common questions drive engagement and inform searcher decisions before they click through.

### Step 2 — Citations
1. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, accessed May 2026). Includes Q&A engagement within the on-profile activity cluster.
2. **Google Business Profile Help — Questions & answers** (https://support.google.com/business/answer/7659435, Google, accessed May 2026). Google encourages owners to respond promptly and to seed FAQs.
3. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Reports that searchers use Q&A content to evaluate businesses before contacting them.

### Step 3 — Evidence weight rationale
Indirect ranking effect via engagement and dwell on the listing; not officially confirmed as a direct ranking factor. Owner responsiveness in Q&A correlates with overall profile management quality. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: Google Business Profile API — `questions` resource** for question count, owner-response rate, and timestamps.

### Step 5 — Verification
GBP API exposes questions and answers via authenticated endpoints. Granularity required: per-business question count, owner-response rate, average response latency, count of owner-seeded FAQs. Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P5-04 (GBP profile completeness), P5-27 (engagement signals).

---

## P5-24 — GBP attributes (women-owned, wheelchair accessible, etc.)

**Pillar:** Local SEO
**Evidence weight:** Probable

### Step 1 — Definition
The structured attributes attached to a Google Business Profile that describe accessibility, ownership identity, payment options, amenities, service options, planning details, and similar facets. Examples include "wheelchair accessible entrance", "women-owned", "Black-owned", "LGBTQ+ friendly", "free Wi-Fi", "outdoor seating", "online appointments". Attributes contribute to filterable search refinements (e.g. "women-owned restaurants near me") and surface as badges on the listing.

### Step 2 — Citations
1. **Google Business Profile Help — Attributes** (https://support.google.com/business/answer/9049526, Google, accessed May 2026). Google documents attribute categories and instructs businesses to add all that apply.
2. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, accessed May 2026). Identifies attribute completeness as part of GBP completeness signal.
3. **BrightLocal — Google My Business Insights Study** (https://www.brightlocal.com/research/google-my-business-insights-study/, accessed May 2026). Documents the role of attributes in attribute-filtered searches and discoverability for niche queries.

### Step 3 — Evidence weight rationale
Google explicitly surfaces attributes as filter facets, so attribute presence directly determines eligibility for filtered local results. The downstream ranking impact within those filtered results is not officially weighted by Google. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: Google Business Profile API — attributes endpoint** for declared attributes and the category-specific attribute list available for the business.

### Step 5 — Verification
GBP API documented; attribute schema differs by primary category. Granularity required: per-business list of declared attributes, list of attributes available for the category but not declared, and gap analysis. Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Depends on:** P5-02 (GBP primary category — attribute schema is category-specific).
- **Cross-references:** P5-04 (GBP profile completeness).

---

## P5-25 — Service area / hours completeness

**Pillar:** Local SEO
**Evidence weight:** Consensus

### Step 1 — Definition
For service-area businesses (those that travel to customers) the declared geographic service area; for storefront businesses the declared opening hours including special-day overrides (holidays, seasonal closures). Completeness covers both: an accurate, non-overlapping service area definition where applicable, plus complete and current opening hours including special-hours entries for holidays.

### Step 1.5 — Evaluation rules
A business passes service area / hours completeness when ALL of the following rules pass:

1. **Hours declared.** Regular weekly opening hours are populated for every day the business operates (closed days marked closed, not blank).
2. **Special hours kept current.** Special-hours entries exist for the next 90 days of public holidays in the business's country and reflect the business's actual schedule (not blanks or copies of regular hours).
3. **Hours match other surfaces.** Hours declared on GBP match hours declared on the business's website footer/contact page and on top citation platforms (Yelp, Apple Maps, Bing Places).
4. **Service area populated for SAB.** If the business is configured as a service-area business (no storefront or hybrid), the service area is populated with cities, postcodes, or a radius rather than left blank.
5. **Service area not overreaching.** The declared service area does not include regions where the business does not actually operate (Google penalises overreaching service areas as a category of spam per the GBP guidelines).
6. **No "open 24 hours" misuse.** "Open 24 hours" is declared only when literally true; not used as a workaround for variable or unpredictable hours.
7. **Temporary closure flagged when applicable.** If the business is temporarily closed (renovations, vacation, etc.), the temporary-closed status is set rather than leaving regular hours that mislead searchers.

A business passing all 7 rules has complete and accurate service area / hours configuration.

### Step 2 — Citations
1. **Google Business Profile Help — Edit your business hours** (https://support.google.com/business/answer/3038177, Google, accessed May 2026). Documents regular hours, special hours, and "open 24 hours" rules.
2. **Google Business Profile Help — Edit your service area** (https://support.google.com/business/answer/9157481, Google, accessed May 2026). Documents service area definition and the rule against overreaching.
3. **Google Business Profile guidelines — Prohibited and restricted content** (https://support.google.com/business/answer/3038177, Google, accessed May 2026). Service area overreach is listed as a guideline violation.
4. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, accessed May 2026). Hours and service area completeness are inputs to the GBP completeness factor.

### Step 3 — Evidence weight rationale
Google explicitly publishes rules for hours and service area. Inaccuracy creates direct ranking and trust harms (searchers arriving at closed businesses, businesses appearing for cities they do not serve). Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google Business Profile API** for regular hours, special hours, and service area declarations.
- **Cross-platform comparison: composition** between GBP, the business website (we already crawl), and citation platform records (P5-05 NAP infrastructure).

### Step 5 — Verification
GBP API documented. Granularity required: per-business hours-declaration status, special-hours coverage of next 90 days of holidays, service-area declaration plus boundary, plus per-rule pass/fail against the 7 evaluation rules. Granularity delivered: by composition.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P5-04 (GBP profile completeness), P5-05 (NAP consistency — hours are part of cross-platform consistency), P5-28 (location demotion — service area overreach is a demotion trigger).

---

## P5-26 — LocalBusiness schema markup

**Pillar:** Local SEO
**Evidence weight:** Consensus

### Step 1 — Definition
Structured data on the business's website using the schema.org `LocalBusiness` type (or an applicable subtype such as `Restaurant`, `Dentist`, `LegalService`) declaring NAP, opening hours, service area, geo-coordinates, price range, payment methods, area served, and other business facts. Provides Google with a machine-readable description of the business that complements the GBP profile and the on-page NAP block.

### Step 1.5 — Evaluation rules
A page passes LocalBusiness schema markup correctness when ALL of the following rules pass:

1. **Most specific subtype used.** The schema uses the most specific applicable schema.org subtype (e.g. `Restaurant`, not `LocalBusiness`, for a restaurant).
2. **Required fields populated.** `name`, `address` (full PostalAddress), `telephone`, and `url` are present and non-empty.
3. **Address matches GBP and on-page NAP.** The `address` block exactly matches the GBP NAP and the on-page NAP block including line-by-line component breakdown.
4. **`openingHoursSpecification` present.** Opening hours are declared as `OpeningHoursSpecification` entries (not free-text), one per distinct day grouping, with `dayOfWeek`, `opens`, `closes`.
5. **`geo` coordinates present.** `geo` block declares `latitude` and `longitude` as `GeoCoordinates`, matching GBP coordinates.
6. **`areaServed` for service-area businesses.** Service-area businesses declare `areaServed` as an array of `AdministrativeArea`/`City`/`PostalCode` entries or a `GeoCircle`.
7. **`sameAs` links populated.** `sameAs` array contains URLs of the business's authoritative profiles (GBP knowledge panel URL, social profiles, Wikipedia, Wikidata) — supports entity reconciliation.
8. **Valid against schema.org.** No deprecated properties, no Google-specific extensions where standard properties exist; passes Google's Rich Results Test without errors.
9. **JSON-LD format.** Markup is delivered as JSON-LD in a `<script type="application/ld+json">` block (Google's recommended format), not Microdata or RDFa.
10. **Single LocalBusiness entity per location page.** A multi-location site has one LocalBusiness entity per location page, not multiple competing entities on the same page.

A page passing all 10 rules has correct LocalBusiness schema markup.

### Step 2 — Citations
1. **Google Search Central — Local Business structured data** (https://developers.google.com/search/docs/appearance/structured-data/local-business, Google, accessed May 2026). Authoritative documentation of supported types, required and recommended properties, and validation guidance.
2. **Schema.org — LocalBusiness** (https://schema.org/LocalBusiness, accessed May 2026). Canonical schema definition with the full property list and subtype hierarchy.
3. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, accessed May 2026). Schema markup correlates with local pack performance in the on-page signal cluster.
4. **Google — Rich Results Test** (https://search.google.com/test/rich-results, Google, accessed May 2026). Validation tool for structured data correctness.

### Step 3 — Evidence weight rationale
Google explicitly documents LocalBusiness markup and the validation tool. Schema markup directly affects rich-result eligibility and feeds the entity model. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page** structured data extraction returns the JSON-LD blocks present on the page.
- **Validation: Google Rich Results Test API** or our own schema.org JSON validator for rule-by-rule checks.

### Step 5 — Verification
DataForSEO confirmed to return JSON-LD blocks. Validation logic is composition (parse JSON-LD, check rules). Granularity required: per-location-page schema-presence status plus rule-by-rule pass/fail. Granularity delivered: by composition.

### Step 6 — Cost
DataForSEO included in standard On-Page audit. Rich Results Test is free at moderate volumes.

### Step 7 — Dependencies and cross-references
- **Scope of this variable:** LocalBusiness-specific schema instantiation with 10-rule Step 1.5 (most-specific subtype, required fields, address-NAP match, opening hours, geo coords, areaServed, sameAs, validation, JSON-LD format, single entity per page). Subset of the general schema validity check in P1-22, specialised for local businesses.
- **Schema family hierarchy:** P1-21 → type appropriateness. P1-22 → general completeness + validity. **P5-26 (this) → LocalBusiness-specific instantiation**. P6-19 → site-wide schema graph depth. P6-20 → Person/Organization deep-dive.
- **Cross-references:** P5-04 (GBP profile — sources of truth must reconcile), P5-05 (NAP consistency — schema NAP is part of consistency surface), P0-16 (entity recognition — `sameAs` supports reconciliation), P1-21/P1-22 (general schema family — this is the local-business specialisation).

---

## P5-27 — Engagement signals (clicks, calls, direction requests, website visits from listing)

**Pillar:** Local SEO
**Evidence weight:** Consensus

### Step 1 — Definition
The volume and rate of user engagement actions taken on the business's Google Business Profile listing: clicks to website, phone calls, direction requests, photo views, message taps, booking clicks. Engagement signals reflect real user interest and serve as a feedback loop into Google's local pack ranking — listings that attract more engagement at given impression volumes are interpreted as more relevant.

### Step 2 — Citations
1. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, accessed May 2026). Behavioural signals (CTR, calls, direction requests) are documented as a top-tier ranking factor cluster — approximately within the same magnitude as reviews and on-profile content.
2. **BrightLocal — Local Consumer Review Survey** (https://www.brightlocal.com/research/local-consumer-review-survey/, accessed May 2026). Documents user actions on listings.
3. **Google Business Profile Performance API documentation** (https://developers.google.com/my-business/reference/performance/rest, Google, accessed May 2026). Provides per-business engagement metrics (impressions and customer actions) confirming Google tracks these as first-class signals.

### Step 3 — Evidence weight rationale
Google publishes the engagement metrics via the Performance API and uses behavioural feedback in ranking systems (NavBoost-style mechanisms documented in the Content Warehouse leak apply analogously to local). Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google Business Profile Performance API** for impressions and customer actions (calls, direction requests, website clicks, photo views, message taps, booking clicks) per business per day.

### Step 5 — Verification
GBP Performance API documented and accessible to verified owners. Granularity required: per-business daily engagement metrics by action type, plus computed engagement rate (actions per impression) and trend slope. Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P5-04 (profile completeness — drives engagement), P5-21 (photos — drive photo views), P5-22 (posts — drive engagement), P5-25 (hours/service area — affect calls and direction requests).

---

## P5-28 — Location demotion (irrelevant geography)

**Pillar:** Local SEO
**Evidence weight:** Consensus

### Step 1 — Definition
Google's algorithmic demotion of business listings or local pages that target a geography where the business does not actually operate. Triggers include: service-area overreach on GBP, doorway location pages targeting cities where the business has no genuine presence, NAP records placed in cities the business does not serve, and keyword-stuffed titles or H1s claiming presence in geographies without supporting evidence (no NAP, no reviews from that geography, no fulfilment capability).

### Step 1.5 — Evaluation rules
A business passes location-demotion screening when ALL of the following rules pass:

1. **GBP service area matches operational reality.** Declared service area corresponds to areas where the business genuinely fulfils customers (verifiable via review distribution, customer addresses, fulfilment records).
2. **No doorway location pages.** The site does not host city-targeted pages for cities lacking genuine business presence (no NAP, no testimonials, no proof of operations).
3. **City-targeted pages have unique substantive content.** Where city pages do exist, they have unique content (local case studies, local team members, local pricing, local testimonials) rather than templated geo-replacement of a master page.
4. **Title and H1 do not claim non-served geographies.** The title and H1 of each location page reference geographies the business actually serves, not aspirational or competitor-poaching geography.
5. **Schema `areaServed` matches GBP and operational reality.** The `LocalBusiness.areaServed` declaration aligns with GBP service area and real operations.
6. **NAP records align with operational locations.** Citation NAPs (P5-05) reflect actual office or service locations, not virtual offices or PO boxes used for local-pack manipulation.
7. **Reviews and engagement come from served geographies.** The geographic distribution of reviewers and engagement is concentrated in declared service areas, not random or geographically incoherent.

A business passing all 7 rules is unlikely to trigger location-demotion mechanisms.

### Step 2 — Citations
1. **Google Business Profile guidelines — Prohibited and restricted content** (https://support.google.com/business/answer/3038177, Google, accessed May 2026). Lists service-area overreach and listings at locations where the business does not have a staffed location as guideline violations.
2. **Google Search Central — Spam policies for Google Search** (https://developers.google.com/search/docs/essentials/spam-policies, Google, accessed May 2026). Documents doorway pages as a violation, including the local-targeting case.
3. **iPullRank — Google Content Warehouse Leak — Local features** (https://ipullrank.com/google-algo-leak, accessed May 2026). The leak documents location-related demotion features within the local ranking subsystem (`localityScore` and related signals).
4. **Whitespark — Local Search Ranking Factors 2026** (https://whitespark.ca/local-search-ranking-factors/, accessed May 2026). Identifies geographic relevance and proximity authenticity as decisive in local pack qualification.

### Step 3 — Evidence weight rationale
Google publishes both the service-area guideline and the doorway-pages spam policy. The Content Warehouse leak corroborates an internal demotion mechanism. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: composition** combining GBP service area declaration (P5-25), site location-page inventory (DataForSEO crawl), schema `areaServed` (P5-26), citation distribution (P5-05), and review geographic distribution (P5-09 and reviewer profile data where available).
- **Doorway-page detection: our own logic** comparing city-targeted pages against the rules above (uniqueness, NAP presence, review presence, fulfilment evidence).

### Step 5 — Verification
All component data sources verified in their own variables. Aggregation logic is composition. Granularity required: per-business demotion-risk status plus rule-by-rule pass/fail and list of specific violations. Granularity delivered: by composition.

### Step 6 — Cost
Composition over already-collected data.

### Step 7 — Dependencies and cross-references
- **Depends on:** P5-05 (NAP consistency), P5-09 (reviews — geographic distribution), P5-25 (service area / hours), P5-26 (LocalBusiness schema).
- **Cross-pillar:** P1-15 (site health) — doorway detection overlaps with thin-content and templated-content checks; P3-39 (algorithmic penalties) — location demotion is one specific demotion category.

---



# Pillar 6 — AI Search / Generative Engine Optimisation

**Total candidates:** 32
**Status:** Complete (32 of 32; P6-15 removed in May 2026 strategic-fit audit as low-ROI for the audited site profile. Retained as a redirect note.)

The "GEO" pillar covers variables that determine inclusion, prominence, and citation in AI-driven retrieval and answer surfaces: Google's AI Overviews, Perplexity, ChatGPT Search, Claude with web, Bing Copilot, You.com, and the broader retrieval-augmented generation (RAG) layer. The discipline is younger than classical SEO; the strongest evidence base is the Princeton Generative Engine Optimization paper (Aggarwal et al., KDD 2024), Foundation Inc's GEO Strategy Guide, the BrightEdge Generative Parser studies, and observational studies of AI Overview citation patterns. Many variables here are **Probable** or **Contested** rather than Consensus; the field is moving fast, and operational rules will be revised as new studies land.

## Pillar 6 Index

| ID | Variable | Status | Weight |
|----|----------|--------|--------|
| P6-01 | LLM-readable content structure (semantic HTML, headings) | Complete | Consensus |
| P6-02 | Quotability / extractable claims | Complete | Consensus |
| P6-03 | Citation density (sources cited within content) | Complete | Consensus |
| P6-04 | Statistical / numerical specificity | Complete | Consensus |
| P6-05 | Direct quotes from named experts | Complete | Probable |
| P6-06 | First-person authority markers (I, we, our) | Complete | Probable |
| P6-07 | Original research and primary data | Complete | Consensus |
| P6-08 | Comparison and listicle structures | Complete | Probable |
| P6-09 | FAQ and question-answer blocks | Complete | Probable |
| P6-10 | Definitional clarity for entities and concepts | Complete | Probable |
| P6-11 | Entity coverage (Wikipedia, Wikidata presence) | Complete | Consensus |
| P6-12 | Brand mentions across LLM training corpora | Complete | Probable |
| P6-13 | Reddit, Quora, and forum presence | Complete | Consensus |
| P6-14 | YouTube and video transcript presence | Complete | Probable |
| P6-15 | Podcast transcripts and citations | Removed | — |
| P6-16 | News and tier-1 publication coverage | Complete | Consensus |
| P6-17 | LLM-bot crawler access (GPTBot, ClaudeBot, PerplexityBot, Google-Extended) | Complete | Consensus |
| P6-18 | llms.txt declaration | Complete | Speculative |
| P6-19 | Schema.org structured data depth | Complete | Consensus |
| P6-20 | Author and organisation entity markup | Complete | Consensus |
| P6-21 | Vector retrievability (chunk semantic coherence) | Complete | Probable |
| P6-22 | Topic depth and exhaustiveness (semantic completeness) | Complete | Consensus |
| P6-23 | Recency and freshness for time-sensitive queries | Complete | Consensus |
| P6-24 | Citation diversity in source URL pool | Complete | Probable |
| P6-25 | AI Overview inclusion frequency | Complete | Consensus |
| P6-26 | Perplexity citation frequency | Complete | Consensus |
| P6-27 | ChatGPT/Claude/Gemini answer-citation frequency | Complete | Probable |
| P6-28 | Brand sentiment in LLM outputs | Complete | Probable |
| P6-29 | Knowledge Graph entity completeness | Complete | Consensus |
| P6-30 | Wikipedia article quality and stability | Complete | Consensus |
| P6-31 | LLM hallucination resistance (factual disambiguation) | Complete | Probable |
| P6-32 | Prompt-injection / adversarial content hygiene | Complete | Consensus |

---

## P6-01 — LLM-readable content structure (semantic HTML, headings)

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
The use of semantic HTML elements (`<article>`, `<section>`, `<nav>`, `<aside>`), a clean heading hierarchy (one H1, descriptive H2/H3 sections), and minimal layout-only `<div>` nesting around the content body. Retrieval-augmented generation (RAG) systems that crawl and chunk web pages for LLM consumption rely on structural signals to segment content into retrievable units; pages where the main content is wrapped in semantic tags and clearly partitioned by headings produce cleaner chunks and higher relevance scores than visually identical pages built from non-semantic `<div>` soup.

### Step 1.5 — Evaluation rules
A page passes LLM-readable structure when ALL of the following rules pass:

1. **Single `<main>` or `<article>` tag wraps primary content.** The page contains exactly one such landmark wrapping the main body.
2. **Heading hierarchy is well-formed.** Single H1, descriptive H2 section headings, H3 subsections under H2 (no H3 directly under H1, no H2 used decoratively), and no skipped levels (H2 → H4 without H3).
3. **Headings describe their content.** Each heading is a meaningful summary of the section that follows (not "Section 1" or styled-as-heading marketing copy).
4. **Body text is in `<p>` elements.** Paragraphs are wrapped in `<p>` tags rather than `<div>` containers.
5. **Lists are real lists.** Enumerated content uses `<ul>`/`<ol>`/`<li>` rather than `<br>`-separated lines or styled `<div>`s.
6. **Tables are real tables when tabular.** Genuine tabular data uses `<table>` with `<thead>`/`<tbody>`/`<th>` not `<div>` grids.
7. **Sidebar and navigation are separated from content.** Navigation, related-posts, and sidebar content live in `<nav>`/`<aside>` so the main content chunk is not contaminated.
8. **Content does not require JavaScript rendering for primary text.** The semantic structure is present in the initial HTML response (LLM crawlers, including ones that do execute JS, get a cleaner read from server-rendered HTML).

A page passing all 8 rules is structured for clean LLM extraction.

### Step 2 — Citations
1. **Aggarwal, P., et al. — GEO: Generative Engine Optimization** (https://arxiv.org/abs/2311.09735, KDD 2024, accessed May 2026). The Princeton paper establishes that source visibility in generative engine answers is shaped by structural and content cues; well-structured content with clear headings is among the inputs that consistently lift visibility scores.
2. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Recommends semantic HTML, clean heading hierarchy, and explicit section partitioning as foundational GEO requirements.
3. **Google Search Central — Document structure and headings** (https://developers.google.com/search/docs/appearance/structured-data/article, Google, accessed May 2026). Google's structured-content guidance applies directly to the AI Overview ingestion pipeline.
4. **Anthropic — Claude's web fetch tool documentation** (https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/web-search-tool, Anthropic, accessed May 2026). Documents that web-fetched content is converted to a chunked text representation; semantic structure aids segmentation.

### Step 3 — Evidence weight rationale
Multiple independent sources (Princeton academic paper, practitioner guides, Google documentation, LLM provider documentation) converge on this requirement, and the mechanism (chunkability for retrieval) is well understood. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page** returns the parsed HTML structure including heading inventory and tag tree.
- **Composition: our own** structural-rule checking over the parsed DOM.

### Step 5 — Verification
DataForSEO confirmed to return structural data. Rule-checking is composition. Granularity required: per-page structural-correctness status plus rule-by-rule pass/fail. Granularity delivered: by composition.

### Step 6 — Cost
Included in standard On-Page audit.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P1-08 (heading structure), P1-31 (schema markup correctness), P2-19 (rendered-vs-raw HTML parity). The classical SEO requirements for clean structure overlap with GEO requirements; passing the SEO rules is largely sufficient for the GEO rules with the addition of explicit landmark tags.

---

## P6-02 — Quotability / extractable claims

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
The presence of self-contained, factually specific, attributable sentences in the content that can be lifted by an LLM as a supporting claim with a citation. The Princeton GEO paper found that adding "fluency optimization" and quotable phrasing increased generative-engine visibility by approximately 30–40% across query categories. A quotable sentence has three properties: it makes a specific claim, the claim stands on its own without surrounding context, and it has clear authorship the LLM can attribute (the page author or a quoted expert).

### Step 1.5 — Evaluation rules
A page passes quotability when ALL of the following rules pass:

1. **Self-contained claims present.** The page contains at least 5 sentences that make complete, standalone factual claims (not "as shown above" or "this is why" sentences that depend on surrounding context).
2. **Specificity over generality.** Quotable claims are specific (figures, dates, named entities, conditional logic) rather than vague ("many users prefer", "studies show"). At least 60% of the candidate quotable sentences include a specific factual element.
3. **Attribution is clear.** Each quotable sentence either is a clear assertion by the page author (with author attribution available on the page) or is a quoted statement attributed to a named expert with credentials.
4. **Sentence length is digestible.** Quotable sentences are between 12 and 35 words on average — long enough to carry substance, short enough to lift cleanly into an answer.
5. **No marketing puffery in quotable position.** Sentences in quotable positions (paragraph openers, section conclusions) are factual claims, not "we are passionate about excellence" or other unfalsifiable marketing copy.

A page passing all 5 rules has high quotability.

### Step 2 — Citations
1. **Aggarwal, P., et al. — GEO: Generative Engine Optimization** (https://arxiv.org/abs/2311.09735, KDD 2024, accessed May 2026). Quantifies that quotable phrasing and specific claims lifted generative engine source visibility by approximately 30–40% across the test set.
2. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Treats quotability and extractable claims as core GEO levers.
3. **BrightEdge — Generative Parser study** (https://www.brightedge.com/resources/research-reports, accessed May 2026). Observational study of AI Overview citations finds cited sentences disproportionately have the structural and specificity properties listed above.

### Step 3 — Evidence weight rationale
Princeton paper provides quantified causal evidence; practitioner studies replicate observationally. Mechanism (LLMs lift sentences they can attribute and verify) is well understood. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: LLM evaluation of our own page content** (Claude Haiku at low temperature) scoring each sentence for the 5 rules and aggregating to a per-page quotability score.
- **Cheaper proxy: heuristic regex** detecting numerical specificity, named entities, and sentence length (incomplete but cheap as a first pass).

### Step 5 — Verification
LLM evaluation is feasible and reproducible at low cost. Granularity required: per-page quotability score plus rule-by-rule sentence inventory. Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation: approximately $0.01–0.03 per page at Haiku rates.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P6-04 (statistical specificity), P6-05 (direct quotes from experts), P4-04 (E-E-A-T signals — author attribution overlaps).

---

## P6-03 — Citation density (sources cited within content)

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
The count and quality of inline citations to authoritative external sources within the content body. The Princeton GEO paper found that adding citations to the content lifted generative engine visibility scores by approximately 30–40%, on par with quotability and statistical specificity. Citation density signals to LLMs that the page is well-researched, gives the LLM other sources to cross-check (which lowers hallucination risk and raises the chance the LLM uses the citing page as a primary source), and supports E-E-A-T-style trust evaluation.

### Step 1.5 — Evaluation rules
A page passes citation density when ALL of the following rules pass:

1. **Minimum citation count.** The page cites at least 3 distinct external sources (more for long-form content; rough heuristic: at least 1 citation per 500 words of substantive content).
2. **Authoritative sources cited.** Cited sources include at least one Tier A source (peer-reviewed academic, government, primary-source organisation) for factual claims that warrant it.
3. **Inline link, not "Sources" appendix only.** Citations are inline links from claim sentences, not only listed in an appendix at the bottom (LLMs more reliably attach inline citations to the claim).
4. **Citation text describes the source.** Anchor text or surrounding context names the source (e.g., "according to the WHO" or "the Princeton GEO paper") rather than "click here" or "research shows".
5. **Cited URLs are alive and not hallucinated.** All cited URLs return 200 and the cited content actually exists at that URL (not fabricated citations).
6. **Diversity of sources.** Multiple distinct domains in the citation set (not 6 citations all to the same domain), supporting independence of evidence.

A page passing all 6 rules has good citation density.

### Step 2 — Citations
1. **Aggarwal, P., et al. — GEO: Generative Engine Optimization** (https://arxiv.org/abs/2311.09735, KDD 2024, accessed May 2026). Quantifies citation density as one of the top three levers (30–40% visibility lift).
2. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Recommends inline citations to authoritative sources.
3. **Google Search Central — E-E-A-T and Quality Rater Guidelines** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Citation behaviour is treated as a signal of expertise and trust, which AI Overview ingestion shares.

### Step 3 — Evidence weight rationale
Princeton paper provides causal evidence; classical SEO and AI Overview practice converge. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page** link inventory plus our own classification of internal vs external links plus authority lookup for cited domains.
- **Composition layer: our own** count and rule-by-rule check.

### Step 5 — Verification
Link inventory is reliable from DataForSEO. Authority scoring uses the same domain-rating data already integrated for off-page authority work. Granularity required: per-page citation count, source-tier distribution, and rule-by-rule pass/fail. Granularity delivered: by composition.

### Step 6 — Cost
Included in standard On-Page audit plus authority lookup quotas.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P1-23 (outbound links), P3-15 (referenced authoritative sources), P4-04 (E-E-A-T).

---

## P6-04 — Statistical / numerical specificity

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
The presence of specific numbers, percentages, dates, sample sizes, and quantitative claims in the content. The Princeton GEO paper found that "statistics addition" — converting vague claims into specific quantified ones — was among the top three levers for generative engine visibility, on par with citation density and quotable phrasing. LLMs preferentially cite content that provides quantified support because (a) quantified claims are more verifiable, (b) they answer "how much" questions in user prompts, and (c) they reduce the LLM's perceived hallucination risk in attribution.

### Step 1.5 — Evaluation rules
A page passes statistical specificity when ALL of the following rules pass:

1. **Numerical density floor.** The content contains at least 1 specific numerical claim per 200 words of substantive content (figure, percentage, date, count, sample size, ratio).
2. **Numbers are sourced.** At least 70% of substantive numerical claims have an inline citation to the source of the number (or are clearly the page's own original measurement with methodology disclosed).
3. **Precision is appropriate.** Numbers are precise enough to be useful (e.g., "47% of users", "$2.3 billion") rather than rounded into uselessness ("about half", "billions").
4. **Units and time periods are specified.** Every numerical claim states its unit (USD, percent, count) and where time-bound, the time period (Q4 2025, 2024 calendar year).
5. **No spurious precision.** Numbers are not falsely precise where the underlying measurement does not support that precision (no "47.2849%" when the source rounds to 47%).
6. **Comparative or absolute, not floating.** Numerical claims are anchored either against an absolute baseline (sample size, total population) or an explicit comparison ("up from 32% in 2023") rather than presented in isolation.

A page passing all 6 rules has good statistical specificity.

### Step 2 — Citations
1. **Aggarwal, P., et al. — GEO: Generative Engine Optimization** (https://arxiv.org/abs/2311.09735, KDD 2024, accessed May 2026). Identifies "statistics addition" as one of the top three high-impact levers (~30–40% visibility lift).
2. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Specific recommendation to add quantified evidence to claims.
3. **BrightEdge — Generative Parser study** (https://www.brightedge.com/resources/research-reports, accessed May 2026). Observational study finds AI Overview citations skew toward content with quantified claims.

### Step 3 — Evidence weight rationale
Princeton paper quantifies the lift; practitioner studies replicate. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: LLM evaluation of our own content** scoring numerical density, sourcing, and precision against the 6 rules.
- **Cheaper proxy: regex** detecting numerical patterns (digits, percentages, currency, dates) for a density baseline.

### Step 5 — Verification
LLM evaluation feasible at low cost. Granularity required: per-page statistical-specificity score plus rule-by-rule findings. Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation: ~$0.01–0.03 per page at Haiku rates.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P6-02 (quotability), P6-03 (citation density), P6-07 (original research).

---

## P6-05 — Direct quotes from named experts

**Pillar:** AI Search / GEO
**Evidence weight:** Probable

### Step 1 — Definition
Quoted statements from named individuals with documented expertise relevant to the topic, attached to the content with clear attribution (name, title, affiliation). LLMs ingesting content for answer generation use named-expert quotes as both authority signal and verbatim-extractable material — quotes are particularly likely to be lifted into AI Overview answers because they are pre-formatted attributable material.

### Step 1.5 — Evaluation rules
A page passes direct-quote authority when ALL of the following rules pass:

1. **At least one named-expert quote.** The content includes at least one direct quote from a named expert (not "an industry source said") for content where expert input is appropriate.
2. **Full attribution.** Each quote includes the speaker's full name, title, and affiliation; ideally a link to their bio or LinkedIn.
3. **Expertise is relevant.** The expert's documented credentials are demonstrably relevant to the topic of the quote (e.g., a cardiologist quoted on heart-disease, not on tax policy).
4. **Quote is non-trivial.** Quotes carry substantive content (a claim, a recommendation, an interpretation), not filler ("we're excited about this development").
5. **Quote marks and formatting are clear.** The quote is wrapped in `<blockquote>` or quotation marks with clear visual separation from the page author's voice — supports clean extraction.
6. **No fabricated quotes.** Quotes are verifiably real (the named expert actually said them — this is a content-integrity rule that becomes more important as AI-generated quotes proliferate).

A page passing all 6 rules has strong expert-quote authority.

### Step 2 — Citations
1. **Aggarwal, P., et al. — GEO: Generative Engine Optimization** (https://arxiv.org/abs/2311.09735, KDD 2024, accessed May 2026). Quote-citation as a content style is among the levers tested.
2. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Recommends expert quotes with full attribution.
3. **Google Search Quality Rater Guidelines — E-E-A-T section** (https://services.google.com/fh/files/misc/hsw-sqrg.pdf, Google, accessed May 2026). Named-expert content with verifiable credentials supports E-E-A-T (which feeds AI Overview source selection).

### Step 3 — Evidence weight rationale
Princeton paper covers the lever but did not isolate "named expert" specifically; practitioner guides recommend it; Google's E-E-A-T guidance reinforces. Qualifies as **Probable** rather than Consensus.

### Step 4 — Data source(s)
- **Primary: LLM evaluation** detecting quote presence, attribution completeness, and expertise relevance.
- **Cross-reference: P0-16 entity recognition** for verifying the named expert exists in Knowledge Graph or other authoritative entity systems.

### Step 5 — Verification
LLM evaluation feasible. Entity verification feasible via Knowledge Graph. Granularity required: per-page expert-quote inventory plus rule-by-rule pass/fail. Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation cost as above.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P0-16 (entity recognition), P4-04 (E-E-A-T author authority), P6-02 (quotability).

---

## P6-06 — First-person authority markers (I, we, our)

**Pillar:** AI Search / GEO
**Evidence weight:** Probable

### Step 1 — Definition
The use of first-person voice ("I", "we", "our team", "in our experience") in the content where it signals direct experience, original observation, or institutional position — as opposed to anonymous third-person summaries of others' work. Google's "Helpful Content" and "Reviews Update" documentation explicitly elevate content that demonstrates first-hand experience; this signal carries through into AI Overview source selection. LLMs appear to surface first-person authoritative content where the prompt asks for opinion, recommendation, or experience-grounded answer.

### Step 1.5 — Evaluation rules
A page passes first-person authority when ALL of the following rules pass:

1. **First-person markers present where appropriate.** Pages making experiential or opinionated claims include "I", "we", or "our team" language — not exclusively anonymous third-person summary.
2. **First-person is grounded in evidence.** Each first-person claim is supported by specific evidence ("in our 2024 customer study of 412 users, we found..." not "we believe X is great").
3. **Author identity is established.** The "I" or "we" is attributable to a named author or named organisation present on the page (not floating first-person voice with no author).
4. **First-person is consistent with documented experience.** The first-person claims align with the author's documented expertise (a SaaS company writing "in our experience deploying X" should have evidence elsewhere of having deployed X — supports the authenticity check).
5. **No false first-person.** AI-generated content faking first-person experience without underlying evidence is the failure mode to detect (overlaps with P4-19 mass-produced content checks).

A page passing all 5 rules has authentic first-person authority.

### Step 2 — Citations
1. **Google Search Central — Helpful, reliable, people-first content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). "Demonstrate first-hand expertise and a depth of knowledge" — direct guidance to use first-person grounded content.
2. **Google Search Central — Reviews update guidance** (https://developers.google.com/search/blog/2023/04/reviews-update-april-2023, Google, accessed May 2026). Reviews must demonstrate first-hand testing.
3. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Recommends author voice and first-person experience markers for AI search visibility.

### Step 3 — Evidence weight rationale
Google explicitly publishes the requirement for the "first-hand experience" E component of E-E-A-T; AI Overview ingestion uses E-E-A-T-style signals. Lift not quantitatively isolated like the Princeton statistics finding. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: LLM evaluation** detecting first-person markers, evaluating evidence-groundedness, cross-referencing author identity (P4-04).

### Step 5 — Verification
Detection is straightforward; evaluation of authenticity is harder and depends on the broader E-E-A-T signal cluster. Granularity required: per-page first-person-authority score with rule-by-rule findings. Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation included in the same pass as P6-02, P6-04, P6-05.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P4-04 (E-E-A-T author authority), P4-19 (mass-produced content detection).

---

## P6-07 — Original research and primary data

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
The publication of original research — surveys, datasets, original measurements, controlled experiments, audited reviews — that the publisher conducted themselves rather than aggregating from others. Original research is the strongest GEO lever among content levers because it makes the page the primary source for any claim derived from it: every other publisher who cites the data cites back to this page, and LLMs pull from primary sources preferentially when the prompt asks "what does the data say".

### Step 1.5 — Evaluation rules
A page passes original-research status when ALL of the following rules pass:

1. **Methodology is disclosed.** The page describes how the data was collected (sample size, sampling method, time period, instrument, collection date).
2. **Primary data is presented.** Numerical data, charts, or raw tables are present, not only summary commentary.
3. **Limitations are acknowledged.** The methodology section acknowledges sampling limits, confounders, or scope boundaries.
4. **Data is attributed to the publisher.** The page or report makes clear the data was collected by the publishing organisation (with named team or principal investigator if applicable).
5. **Backlink evidence supports primary-source status.** Other publishers cite this page when referencing the data (P3 backlink data with anchor-text alignment to the data claim — e.g., other pages link with "according to [publisher]'s 2025 study").
6. **Data is current or year-stamped.** The data has a clear collection year, and where the topic is time-sensitive, the data is reasonably recent.

A page passing all 6 rules is original primary research.

### Step 2 — Citations
1. **Aggarwal, P., et al. — GEO: Generative Engine Optimization** (https://arxiv.org/abs/2311.09735, KDD 2024, accessed May 2026). Original data and primary citations rank among the highest-lift content properties.
2. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Original research is identified as the strongest GEO lever among content strategies.
3. **Google Search Central — E-E-A-T and helpful content** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Original research is treated as a top-tier expertise signal.
4. **Backlinko — Skyscraper Technique 2.0 / linkable assets research** (https://backlinko.com/skyscraper-technique, accessed May 2026). Documents that original research generates disproportionate backlinks, which feed LLM source selection via authority signals.

### Step 3 — Evidence weight rationale
Multiple converging sources, clear mechanism (primary-source preference in LLM selection), and observable backlink correlation. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: LLM evaluation** detecting methodology disclosure, primary-data presentation, limitations acknowledgement.
- **Composition: backlink-data analysis** (P3) for citation evidence supporting primary-source status.

### Step 5 — Verification
LLM evaluation plus backlink analysis are both feasible. Granularity required: per-page original-research status plus rule-by-rule findings plus backlink-citation evidence. Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation as above; backlink data already collected for Pillar 3.

### Step 7 — Dependencies and cross-references
- **Scope of this variable:** GEO-specific evaluation — is the page recognised as the primary source for the data it contains? Includes 6-rule Step 1.5 covering methodology, primary data presentation, limitations, attribution, backlink-evidence (other publishers cite this page), and currency. Different from P4-11 (which only checks presence of original research).
- **Hierarchy:** P4-11 → "does the page contain original research" (content-ops detection). **P6-07 (this) → "is the page the primary source for that research, with backlink-citation evidence"** (GEO multi-rule evaluation including primary-source status check via backlinks).
- **Cross-references:** P3-01 (backlink count and quality — original research drives links and the backlink-evidence rule), P4-04 (E-E-A-T expertise), P4-11 (content-ops detection of presence), P6-04 (statistical specificity).

---

## P6-08 — Comparison and listicle structures

**Pillar:** AI Search / GEO
**Evidence weight:** Probable

### Step 1 — Definition
Content organised as comparison tables, ranked listicles ("Top 10 X for Y"), or side-by-side feature comparisons. AI Overview and chatbot answers for "best X for Y" or "X vs Y" queries draw heavily from pages structured this way: the chunked, tabular, comparative format maps cleanly onto the answer format the LLM produces.

### Step 1.5 — Evaluation rules
A page passes comparison/listicle structure when ALL of the following rules pass:

1. **Structure matches query intent.** Pages targeting "best X" queries are organised as ranked lists with named entries. Pages targeting "X vs Y" are organised as feature-by-feature comparisons.
2. **Comparison criteria are explicit.** Comparison pages declare the criteria used for the comparison (price, features, support, speed, etc.) in a way an LLM can lift.
3. **Each entry is fully populated.** Listicle entries each have a substantive description (not a one-line entry), and comparison rows have a value for each entry across criteria.
4. **Genuine differentiation is present.** Entries actually differ on the comparison criteria — not all marked as "Excellent" with no real distinction.
5. **Recommendation logic is disclosed.** If the page recommends a "best for X use case" verdict, the reasoning is explicit (not hidden behind "in our opinion").
6. **Structure is machine-extractable.** Comparison data is in real `<table>`, listicle data is in real `<ul>`/`<ol>` (overlaps with P6-01 structure rules).

A page passing all 6 rules has clean comparison/listicle structure for LLM extraction.

### Step 2 — Citations
1. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Identifies comparison and listicle structures as preferred for "best of" and "vs" query categories in AI search.
2. **BrightEdge — Generative Parser study** (https://www.brightedge.com/resources/research-reports, accessed May 2026). Observational evidence that AI Overview citations for comparison queries skew toward pages with explicit table/list structure.
3. **Aggarwal, P., et al. — GEO: Generative Engine Optimization** (https://arxiv.org/abs/2311.09735, KDD 2024, accessed May 2026). Structural-clarity levers (which include comparison/listicle structure) are among the tested content modifications that lift visibility.

### Step 3 — Evidence weight rationale
Practitioner studies and observational data converge; mechanism is clear (chunkable, lift-able answer format). Princeton paper covers the broader category but did not isolate "comparison structure" specifically. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page** for tag inventory (tables, lists).
- **Composition: LLM evaluation** for query-intent matching (does the page's structure match the query category?) and rule-by-rule check.

### Step 5 — Verification
DataForSEO confirmed; LLM evaluation feasible. Granularity required: per-page structure-match score plus rule-by-rule findings. Granularity delivered: by composition.

### Step 6 — Cost
DataForSEO included in audit; LLM evaluation modest.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P6-01 (semantic structure), P1-05 (search intent alignment — comparison structure must match comparison-intent queries).

---

## P6-09 — FAQ and question-answer blocks

**Pillar:** AI Search / GEO
**Evidence weight:** Probable

### Step 1 — Definition
Explicit question-and-answer pairs in the content body, ideally also marked up as `FAQPage` schema. Generative engines preferentially extract answers from pages where the question is stated verbatim and followed by a direct answer, because the structural mapping from user prompt → page question → page answer is unambiguous. Both natural Q&A in the prose ("How does X work? X works by …") and structured FAQ schema feed this signal.

### Step 1.5 — Evaluation rules
A page passes FAQ / Q&A structure when ALL of the following rules pass:

1. **Questions match real user phrasing.** FAQ questions reflect actual searcher language (drawn from People Also Ask, Reddit, support tickets) rather than marketing-friendly rephrasings.
2. **Answer immediately follows question.** The answer to each question begins in the next paragraph, with the first sentence containing the direct answer (not setup or context).
3. **Answer is self-contained.** Each answer can be lifted on its own and still make sense (does not begin "as discussed above").
4. **Schema markup present where appropriate.** Q&A blocks intended as FAQ are marked up with `FAQPage` schema; Q&A pages with single user-asked questions use `QAPage` schema. The schema content matches the visible content exactly.
5. **No fake/marketing FAQs.** Questions are genuine information-seeking questions, not "Why is [our product] the best?" puffery questions.
6. **Reasonable count.** A typical content page has 3 to 12 FAQs; an FAQ-dedicated page can have more. Pages stuffed with 50+ FAQs targeting unrelated keywords risk being treated as keyword-stuffing.

A page passing all 6 rules has high-quality FAQ structure.

### Step 2 — Citations
1. **Google Search Central — FAQ structured data** (https://developers.google.com/search/docs/appearance/structured-data/faqpage, Google, accessed May 2026). Documents `FAQPage` schema and the rules for valid usage including the prohibition on fake or marketing-only questions.
2. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). FAQ blocks identified as a high-leverage structure for AI search inclusion.
3. **Aggarwal, P., et al. — GEO: Generative Engine Optimization** (https://arxiv.org/abs/2311.09735, KDD 2024, accessed May 2026). Q&A structures fall within the high-impact structural-clarity content modifications.

### Step 3 — Evidence weight rationale
Structural mechanism is clear and documented; Google publishes the schema. Direct ranking-lift attribution to FAQ is harder to isolate because FAQ overlaps with general structural-clarity. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page** for tag inventory and structured data extraction (FAQPage detection).
- **Composition: LLM evaluation** for question-quality and answer-quality rule checks.

### Step 5 — Verification
DataForSEO confirmed; LLM evaluation feasible. Granularity required: per-page FAQ inventory plus rule-by-rule findings. Granularity delivered: by composition.

### Step 6 — Cost
Included in standard On-Page audit plus modest LLM cost.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P1-31 (schema markup correctness), P6-01 (LLM-readable structure), P6-22 (topic depth — FAQ contributes to coverage).

---

## P6-10 — Definitional clarity for entities and concepts

**Pillar:** AI Search / GEO
**Evidence weight:** Probable

### Step 1 — Definition
The presence of explicit, well-formed definitions for the entities and concepts central to the page. A definitional sentence has the form "[Entity] is [category] that [distinguishing properties]" — for example, "PageRankNS is a Google ranking signal that estimates the authority of a page based on the link graph nearest-seed approach". LLMs ranking sources for "what is X" or "X definition" prompts strongly prefer pages with cleanly extractable definitional sentences over pages that assume the reader knows what X is.

### Step 1.5 — Evaluation rules
A page passes definitional clarity when ALL of the following rules pass:

1. **Primary subject is defined.** The page's primary topic entity has an explicit definitional sentence near the top of the content (within the first 200 words of body text).
2. **Definitional form is canonical.** The definition follows the "[X] is [Y]" pattern — subject + copula + category + distinguishing properties — rather than starting with use-cases or benefits.
3. **Definition is unambiguous.** The definition uniquely identifies the entity (a reader cannot confuse the subject with another similarly-named entity).
4. **Subordinate concepts are defined on first use.** Domain-specific terms used elsewhere in the content are defined on first appearance, either inline or via a short parenthetical.
5. **No circular definitions.** The definition does not use the term it is defining ("SEO is the practice of doing SEO").
6. **Glossary or summary block is provided for term-heavy pages.** Pages introducing 5+ specialised terms include a glossary section or summary table mapping terms to short definitions.

A page passing all 6 rules has good definitional clarity.

### Step 2 — Citations
1. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Recommends explicit definitional sentences for entities and concepts as a core GEO content pattern.
2. **BrightEdge — Generative Parser study** (https://www.brightedge.com/resources/research-reports, accessed May 2026). Observational data showing definitional content disproportionately cited in AI Overview answers for "what is" queries.
3. **Wikipedia Manual of Style — first sentence** (https://en.wikipedia.org/wiki/Wikipedia:Manual_of_Style/Lead_section, accessed May 2026). Wikipedia's canonical pattern (subject in bold, "is", category, distinguishing properties) is the canonical definitional form LLMs are most trained on.

### Step 3 — Evidence weight rationale
Mechanism is clear (definitional sentence maps to "what is X" prompt); Wikipedia provides the trained-on canonical pattern. Direct lift evidence is observational rather than experimental. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: LLM evaluation** of the page's first 200 words for definitional pattern, plus full-page check for subordinate-term definition coverage.

### Step 5 — Verification
LLM evaluation straightforward. Granularity required: per-page definitional-clarity score plus rule-by-rule findings plus list of undefined-but-used terms. Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation modest; can be combined with P6-02 / P6-04 / P6-06 in a single pass.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P0-16 (entity recognition), P6-11 (entity coverage), P6-22 (topic depth).

---

## P6-11 — Entity coverage (Wikipedia, Wikidata presence)

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
Whether the brand or primary topic entity is represented as a recognised entity in Wikipedia, Wikidata, the Google Knowledge Graph, and other authoritative knowledge bases that LLM training pipelines and retrieval systems use as canonical entity references. Entities present in these systems are reliably disambiguated by LLMs and are far more likely to be surfaced as answer subjects; entities not present are often elided or confused with similarly-named entities.

### Step 1.5 — Evaluation rules
A brand/entity passes coverage when ALL of the following rules pass:

1. **Wikipedia article exists.** A live, non-stub Wikipedia article exists for the brand/entity in at least one major-language Wikipedia (typically English).
2. **Wikidata entity exists.** A Wikidata Q-item exists with the standard properties populated (name, description, instance-of, country, founding-date, official-website where applicable).
3. **Knowledge Graph entity recognised.** The Google Knowledge Graph Search API returns a result for the entity name with `@type` matching the entity category.
4. **`sameAs` linkage between systems.** Wikidata cross-references Wikipedia and the official website; the website's schema markup includes `sameAs` to Wikipedia and Wikidata (closes the loop).
5. **Entity name is unique or disambiguated.** The entity has either a unique name or a clearly-stated disambiguator (e.g., "Apple Inc., the technology company" — distinct from "Apple Records" or "Apple Bank").
6. **Article quality is reasonable.** The Wikipedia article is not a stub, has citations to independent sources, and has not been flagged for deletion or notability concerns.

A brand passing all 6 rules has solid entity coverage.

### Step 2 — Citations
1. **Google Knowledge Graph Search API documentation** (https://developers.google.com/knowledge-graph, Google, accessed May 2026). Authoritative API for entity recognition and `@type` classification.
2. **Wikidata — Help: Items** (https://www.wikidata.org/wiki/Help:Items, accessed May 2026). Documents the canonical entity model used across knowledge bases.
3. **Wikipedia — Notability guidelines** (https://en.wikipedia.org/wiki/Wikipedia:Notability, accessed May 2026). Defines the bar an entity must meet for a Wikipedia article.
4. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Treats Wikipedia/Wikidata presence as a top-tier prerequisite for AI search visibility.
5. **Anthropic — Constitutional AI training data documentation** and **OpenAI — Training data documentation** (publicly available statements about training corpora, accessed May 2026). Confirm Wikipedia is a foundational training corpus for major LLMs.

### Step 3 — Evidence weight rationale
Wikipedia/Wikidata as foundational LLM training data is documented. Knowledge Graph API is the authoritative entity-resolution layer for Google. Mechanism (named entity recognition determines disambiguation in answer generation) is well-established in NLP. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google Knowledge Graph Search API** for KG entity recognition.
- **Wikidata SPARQL endpoint** (https://query.wikidata.org/) for entity lookup and property completeness.
- **Wikipedia API** for article existence, article-quality flags, and revision history.

### Step 5 — Verification
All three APIs documented and accessible. Granularity required: per-brand entity-coverage status across the three systems plus rule-by-rule findings plus quality flags. Granularity delivered: by composition.

### Step 6 — Cost
Free across all three APIs at moderate volumes.

### Step 7 — Dependencies and cross-references
- **Scope of this variable:** operational multi-system entity-coverage check (Wikipedia + Wikidata + Knowledge Graph together, with `sameAs` linkage). Broader than P0-16; less deep than P6-29.
- **Hierarchy:** P0-16 → "is the brand recognised in KG" (strategic binary). **P6-11 (this) → "is the brand covered across the entity ecosystem with cross-system linkage"** (operational). P6-29 → "is the KG record's properties complete and accurate" (deep audit). P6-30 → "is the Wikipedia article specifically high-quality and stable" (Wikipedia-deep audit).
- **Cross-references:** P0-16, P6-29, P6-30.

---

## P6-12 — Brand mentions across LLM training corpora

**Pillar:** AI Search / GEO
**Evidence weight:** Probable

### Step 1 — Definition
The frequency and quality of mentions of a brand or primary entity across the documents that compose major LLM training corpora — specifically Common Crawl (the largest public web crawl, used by GPT, Claude, Gemini), C4 (Google's curated subset of Common Crawl), The Pile, Wikipedia, news archives, and academic literature. Brands mentioned more often and in more authoritative contexts within these corpora are more readily produced by LLMs without retrieval (their internal "weights memory") and are more easily disambiguated when retrieved at inference time.

### Step 1.5 — Evaluation rules
A brand passes training-corpus presence when ALL of the following rules pass:

1. **Common Crawl frequency above threshold.** The brand name appears in at least 1,000 documents in the most recent Common Crawl snapshot (rough threshold; exact bar varies by entity category).
2. **C4 presence.** The brand appears in the C4 dataset (a quality-filtered subset, so presence indicates the brand is mentioned on quality-filtered domains).
3. **News archive presence.** The brand appears in major news archive sources (Wayback Machine indexing, GDELT, NewsAPI archives) over multiple years, indicating sustained press coverage rather than a single PR burst.
4. **Wikipedia mentions.** Beyond the brand's own article (P6-11), the brand is mentioned in third-party Wikipedia articles (e.g., industry articles, related-entity articles) with citation-supported references.
5. **Mention diversity.** Mentions are distributed across diverse domain types (news, academic, industry, government) rather than concentrated on the brand's own marketing content.

A brand passing all 5 rules has substantive training-corpus presence.

### Step 2 — Citations
1. **Common Crawl Foundation — Dataset documentation** (https://commoncrawl.org/the-data, accessed May 2026). Authoritative source for Common Crawl content; can be queried for entity frequency.
2. **AllenAI — C4 dataset** (https://github.com/allenai/allennlp/discussions/5056 and https://huggingface.co/datasets/c4, accessed May 2026). Reproduction of the C4 cleanup; queryable for entity presence.
3. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Treats training-corpus mention frequency as the foundational pre-retrieval visibility lever.
4. **Anthropic and OpenAI — public statements on training data** (accessed May 2026). Confirm that Common Crawl and similar large web corpora are foundational training inputs.

### Step 3 — Evidence weight rationale
Mechanism is well-established (LLM weights memorise frequency-weighted patterns). Direct measurement of the lift is hard because we cannot probe model weights, but observable LLM behaviour confirms the pattern (LLMs produce confident answers about high-frequency entities, hallucinate or hedge on low-frequency ones). Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: Common Crawl Index** (https://index.commoncrawl.org/) for direct domain and content frequency queries.
- **Hugging Face C4 dataset** for C4 presence.
- **NewsAPI / GDELT / Wayback Machine CDX API** for news archive coverage.
- **Composition: our own** aggregation of frequency counts and rule-by-rule check.

### Step 5 — Verification
Common Crawl Index documented and queryable. C4 dataset hosted on Hugging Face is queryable. News archive APIs are documented. Granularity required: per-brand presence-and-frequency table across the corpora plus rule-by-rule findings. Granularity delivered: by composition.

### Step 6 — Cost
Common Crawl Index is free (queries against CDX). C4 queries on Hugging Face are free. NewsAPI has paid tiers; GDELT is free. Querying at scale (full Common Crawl scans) requires significant compute; we use the index API for presence checks rather than full scans.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P0-15 (brand search volume — independent demand signal), P3-20 (brand mentions on third-party sites — overlaps with the corpus-presence check), P6-11 (entity coverage), P6-16 (news coverage).

---

## P6-13 — Reddit, Quora, and forum presence

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
The presence of brand or topic discussions on Reddit, Quora, Stack Exchange, Hacker News, niche forums, and other user-generated discussion platforms. Following Google's announced partnership with Reddit and the visible upweighting of Reddit content in Google search results (2024 onward), plus the documented heavy use of Reddit and similar forums in LLM training corpora, forum presence has become one of the most cited single levers in AI search visibility.

### Step 1.5 — Evaluation rules
A brand/topic passes forum presence when ALL of the following rules pass:

1. **Organic Reddit presence.** The brand is discussed in Reddit threads on relevant subreddits, with the discussions started by users (not the brand astroturfing). Threads are recent (within last 18 months) and discuss specific aspects of the brand.
2. **Quora answers reference the brand.** Where Quora has high-traffic questions in the brand's category, the brand is mentioned in top-voted answers (organic, not self-answered).
3. **No detectable astroturfing.** No pattern of new accounts posting promotional content about the brand; engagement is from established accounts with diverse posting histories.
4. **Sentiment is broadly positive or neutral.** The forum discussion is not dominated by complaint threads, refund-seeking, or warning posts.
5. **Topical coverage matches brand offerings.** Forum discussion covers the brand's core products/services, not just isolated niche aspects.
6. **Stack Exchange / niche forum presence.** Where the topic has a relevant Stack Exchange site (Stack Overflow for developer tools, Server Fault for IT, etc.) or a domain-specific niche forum, the brand is referenced there too.

A brand passing all 6 rules has solid forum presence.

### Step 2 — Citations
1. **Google Search Central blog — Reddit partnership announcement** (https://blog.google/products/search/reddit-content-partnership/, Google/Reddit, accessed May 2026). Documents the upweighting of Reddit content in search results.
2. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Identifies Reddit and forum presence as among the top operational levers for AI search visibility.
3. **Search Engine Land — coverage of Reddit's prominence in AI Overviews** (https://searchengineland.com/, accessed May 2026, multiple articles). Industry coverage of Reddit's outsized share of AI Overview citations.
4. **Anthropic — Claude system prompt and training documentation** (publicly available, accessed May 2026). Reddit and similar discussion platforms are confirmed major components of LLM training data.

### Step 3 — Evidence weight rationale
Google publicly partnered with Reddit and explicitly upweights Reddit content; Reddit is overrepresented in AI Overview citations; Reddit is confirmed as major training data. Mechanism is unambiguous. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Reddit API** (https://www.reddit.com/dev/api/) for thread search, comment retrieval, and subreddit metadata.
- **Quora**: no official API; data via SerpAPI's Quora results or scraping (Quora ToS prohibits scraping, so this requires careful handling).
- **Stack Exchange API** (https://api.stackexchange.com/) for Stack Overflow / Server Fault / niche-Stack site presence.
- **Composition: LLM evaluation** for sentiment and astroturfing-detection rules.

### Step 5 — Verification
Reddit and Stack Exchange APIs documented. Quora is the difficult source. Granularity required: per-brand thread inventory across the platforms plus sentiment distribution plus rule-by-rule findings. Granularity delivered: by composition (with Quora coverage being the gap).

### Step 6 — Cost
Reddit API: free at moderate volumes (rate-limited). Stack Exchange API: free. Quora via SerpAPI: paid per query.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-20 (brand mentions on third-party sites — forum mentions are a subset), P6-12 (training corpus presence), P6-28 (brand sentiment in LLM outputs — forum sentiment feeds this).

---

## P6-14 — YouTube and video transcript presence

**Pillar:** AI Search / GEO
**Evidence weight:** Probable

### Step 1 — Definition
The presence of YouTube videos (and other major video platforms) discussing or featuring the brand or topic, with accurate auto-generated or uploaded transcripts that LLMs and search engines can index. Video transcripts feed both Google's video search results and LLM training corpora; well-transcribed videos with high view counts contribute to brand recognition in AI search outputs.

### Step 1.5 — Evaluation rules
A brand/topic passes video presence when ALL of the following rules pass:

1. **At least one substantive video.** A video of at least 5 minutes' duration discussing the brand/topic in substantive depth exists on YouTube (either owned or third-party).
2. **Transcript present and accurate.** The video has a transcript (uploaded SRT/VTT, or auto-generated transcript that is reasonably accurate — check via spot-sample comparison against audio).
3. **Title and description optimised.** The video title and description include the brand/topic name and target keywords without keyword-stuffing.
4. **Reasonable view and engagement count.** The video has demonstrated viewer interest (views, watch time, likes-to-dislikes ratio) — videos with negligible views contribute negligibly to AI corpus weight.
5. **Schema markup present on host page if embedded.** When the video is embedded on the brand's own site, the embedding page uses `VideoObject` schema with `transcript` or `description` populated.
6. **Channel authority is reasonable.** The video is hosted on a channel with at least minimal subscriber/upload history (not a freshly-created shell channel).

A brand passing all 6 rules has solid video presence.

### Step 2 — Citations
1. **Google Search Central — Video structured data** (https://developers.google.com/search/docs/appearance/structured-data/video, Google, accessed May 2026). Documents `VideoObject` schema and transcript fields.
2. **YouTube Data API documentation** (https://developers.google.com/youtube/v3, Google, accessed May 2026). Authoritative API for video metadata, transcripts, and channel data.
3. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Identifies video and transcript presence as a contributing GEO lever.
4. **Search Engine Land — coverage of video citations in AI Overviews** (https://searchengineland.com/, accessed May 2026). Industry coverage documenting video appearances in AI Overview surfaces.

### Step 3 — Evidence weight rationale
Mechanism is clear (transcripts feed both search and corpora). Direct lift attribution is harder to isolate from the broader video-SEO category. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: YouTube Data API** for video discovery, metadata, view counts, transcript availability flags.
- **Transcript retrieval: youtube-transcript-api or YouTube captions endpoint** for transcript content.
- **Composition layer: our own** for rule-by-rule check and accuracy spot-checks.

### Step 5 — Verification
YouTube API documented. Granularity required: per-brand video inventory plus transcript availability plus rule-by-rule findings. Granularity delivered: by composition.

### Step 6 — Cost
YouTube Data API: free at standard quotas; high-volume usage requires quota request.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P6-12 (training corpus presence — video transcripts feed Common Crawl), P6-15 (podcast transcripts — same mechanism, different medium).

---

## P6-15 — Podcast transcripts and citations *(removed — May 2026 strategic-fit audit)*

This variable was removed from the operational taxonomy in May 2026. The mechanism (podcast transcripts feed LLM training corpora and search indexes) is real and the Probable weight is defensible, but operationalising it requires a paid podcast-index adapter (Listen Notes / Podchaser paid plans) and the signal is materially relevant only for brands competing in podcast-driven buyer-discovery categories (founder-led B2B SaaS, marketing/sales thought-leadership, VC-backed product launches). For services agencies, mid-market local businesses, and other audited profiles whose buyer journey is dominated by directory listings, SERP queries, and referral networks, podcast presence is a marginal signal whose absence will reliably FAIL on every audit without telling the reviewer anything actionable. The video-transcript analogue **P6-14 — YouTube and video transcript presence** covers the broader "spoken content with transcripts feeds AI" mechanism with materially better measurement coverage (free YouTube API, larger audience for most segments).

---

## P6-16 — News and tier-1 publication coverage

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
Coverage of the brand or topic in tier-1 news publications and respected industry publications: major newspapers (NYT, WSJ, FT, Guardian), major TV/online news sites (BBC, Reuters, Bloomberg, AP, AFP), top-tier industry publications (TechCrunch, Wired, The Verge for tech; Forbes, HBR for business), and government/research outlets where applicable. News coverage produces multiple compounding GEO benefits: high-authority backlinks, training-corpus presence, Wikipedia citations (which underpin entity coverage), and direct AI Overview citation.

### Step 1.5 — Evaluation rules
A brand passes tier-1 coverage when ALL of the following rules pass:

1. **At least one tier-1 mention in last 24 months.** A genuine editorial mention of the brand in a tier-1 publication exists within the last 24 months (not paid placement, not branded content, not a press-release mirror).
2. **Coverage is substantive.** The mention is not a one-line directory or a passing reference; the brand is discussed with at least a paragraph of editorial context.
3. **Coverage is dofollow-linked or cited.** The mention either links to the brand's website with dofollow (or is cited by name in a way other publishers reproduce).
4. **Diversity across publishers.** Coverage exists across at least 3 distinct tier-1 publishers (single-publication coverage, however prestigious, is more fragile than diversified coverage).
5. **Coverage themes align with brand positioning.** Coverage discusses the brand on themes that align with its positioning rather than only crisis or controversy coverage.
6. **No substantial negative-coverage cluster unaddressed.** Where negative coverage exists, the brand has either responded publicly or the coverage is balanced by sustained positive editorial coverage (sentiment skew matters for LLM brand sentiment, P6-28).

A brand passing all 6 rules has solid tier-1 news coverage.

### Step 2 — Citations
1. **Google Search Quality Rater Guidelines** (https://services.google.com/fh/files/misc/hsw-sqrg.pdf, Google, accessed May 2026). Tier-1 editorial coverage explicitly noted as an E-E-A-T trust signal.
2. **iPullRank — Google Content Warehouse Leak — Trusted source features** (https://ipullrank.com/google-algo-leak, accessed May 2026). The leak documents `siteAuthority` and quality-source classification features that align with trusted publication coverage.
3. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Tier-1 coverage identified as a foundational signal cluster for AI search.
4. **Search Engine Land — AI Overview source analysis** (https://searchengineland.com/, accessed May 2026). Multiple analyses showing AI Overview citations skew heavily toward tier-1 news domains.

### Step 3 — Evidence weight rationale
Multiple sources converge: Google's own guidance, the Content Warehouse leak, and observed AI Overview citation patterns all point in the same direction. Mechanism is clear (trusted publishers feed multiple downstream signals). Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: NewsAPI / GDELT** for news coverage discovery and coverage volume measurement.
- **DataForSEO Backlinks API** for the dofollow-linkage status.
- **Composition layer: our own** publisher-tier classification (we maintain a list of tier-1 / tier-2 / tier-3 publishers per industry) and rule-by-rule check.

### Step 5 — Verification
NewsAPI and GDELT both documented and accessible. Tier classification is composition. Granularity required: per-brand coverage inventory by publisher and tier plus rule-by-rule findings plus sentiment classification. Granularity delivered: by composition.

### Step 6 — Cost
NewsAPI paid tiers; GDELT free. DataForSEO Backlinks API paid (already used elsewhere).

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-01 (backlink count and quality — tier-1 coverage drives high-quality backlinks), P3-20 (brand mentions on third-party sites), P6-12 (training corpus presence), P6-30 (Wikipedia article quality — tier-1 citations support Wikipedia notability).

---

## P6-17 — LLM-bot crawler access (GPTBot, ClaudeBot, PerplexityBot, Google-Extended)

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
Whether the site's `robots.txt` and HTTP-header policies permit access to the major LLM crawler user agents that ingest content for either training (GPTBot, ClaudeBot/Claude-Web, Google-Extended for Gemini, anthropic-ai, Bytespider, FacebookBot) or live retrieval at inference time (PerplexityBot, ChatGPT-User, OAI-SearchBot, Google's AI Overview crawler, Bing's BingPreview/MSAI-bot). Blocking a crawler removes the site from the corresponding LLM's ingestion path: a site blocked from GPTBot will not be in future ChatGPT training data, and a site blocked from ChatGPT-User will not be retrieved by ChatGPT's live web tool.

### Step 1.5 — Evaluation rules
A site passes LLM-bot access policy when ALL of the following rules pass (NB: this is a strategic policy variable — the site owner may intentionally block some bots; we evaluate against the declared business intent):

1. **No accidental block.** No LLM crawler is blocked unintentionally (e.g., a wildcard `Disallow` that catches LLM bots when the intent was only to block scrapers).
2. **Retrieval-time bots permitted.** Bots that fetch at user-query time (PerplexityBot, ChatGPT-User, OAI-SearchBot, Google's AI Overview surface) are permitted, because blocking them removes the site from current AI search visibility.
3. **Training-time bots aligned with policy.** Training-time bots (GPTBot, ClaudeBot/anthropic-ai, Google-Extended, Bytespider) are configured per the explicit declared policy: either permitted (default for visibility) or explicitly blocked (for content-protection reasons). The site is consistent in its decisions across bots of the same category, not blocking GPTBot while permitting ClaudeBot without rationale.
4. **No conflicting signals.** `robots.txt`, `X-Robots-Tag` HTTP headers, and meta robots tags do not conflict for the same crawler.
5. **`User-agent` patterns match real user agents.** Disallow rules use the exact bot names published by the LLM provider (case-sensitive where required); not partial matches that miss the actual UA string.
6. **Crawler logs corroborate the policy.** Server logs show LLM crawler hits where they should be permitted (a site that thinks it permits ClaudeBot but never sees ClaudeBot in logs has a configuration or DNS issue).

A site passing all 6 rules has correct LLM-bot crawler access policy.

### Step 2 — Citations
1. **OpenAI — GPTBot crawler documentation** (https://platform.openai.com/docs/gptbot, OpenAI, accessed May 2026). Documents GPTBot user-agent string and the IP ranges; explains that blocking GPTBot prevents content ingestion into future training corpora.
2. **OpenAI — ChatGPT-User and OAI-SearchBot documentation** (https://platform.openai.com/docs/bots, OpenAI, accessed May 2026). Documents the retrieval-time crawlers used by ChatGPT's web browsing and ChatGPT Search.
3. **Anthropic — ClaudeBot documentation** (https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler, Anthropic, accessed May 2026). Documents ClaudeBot and the user-agent string.
4. **Google Search Central — Google-Extended documentation** (https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers#google-extended, Google, accessed May 2026). Documents Google-Extended as the opt-out signal for Gemini training; permits Google-Extended-permitted sites to remain in Gemini training.
5. **Perplexity — PerplexityBot documentation** (https://docs.perplexity.ai/guides/bots, Perplexity, accessed May 2026). Documents PerplexityBot and its retrieval behaviour.

### Step 3 — Evidence weight rationale
Each LLM provider publishes their bot's behaviour. The mechanism (block bot → no ingestion) is unambiguous. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page** for `robots.txt` content and HTTP header inventory.
- **Composition: our own** for parsing `robots.txt` against the known list of LLM bot user agents.
- **Server log verification: optional** where the site owner provides log access (we do not require this for a passing audit but flag it as a confidence boost).

### Step 5 — Verification
DataForSEO confirmed for `robots.txt` retrieval. Bot-list maintenance is composition (we keep an up-to-date list of LLM bot UA strings). Granularity required: per-site policy table with per-bot status (allow / disallow / not declared) plus per-rule pass/fail. Granularity delivered: by composition.

### Step 6 — Cost
Included in standard On-Page audit.

### Step 7 — Dependencies and cross-references
- **Cross-pillar:** P2-01 (robots.txt configuration), P2-07 (X-Robots-Tag headers). The classical SEO bot-policy variables are extended here for LLM-specific bots.
- **Cross-references:** P6-18 (llms.txt — the next-generation declaration mechanism, complementary to robots.txt).

---

## P6-18 — llms.txt declaration

**Pillar:** AI Search / GEO
**Evidence weight:** Speculative

### Step 1 — Definition
The presence and correctness of an `/llms.txt` file at the site root, as proposed by Jeremy Howard (FastAI / Answer.AI) in late 2024 as a standard for declaring LLM-friendly content boundaries: which pages are canonical, what the site is about, and a curated index for retrieval. The proposal is explicitly modelled on `robots.txt` and `sitemap.xml` and has seen rapid practitioner adoption but **no major LLM provider has officially confirmed they consume llms.txt for ranking or training**. This variable sits firmly in the Speculative tier — operational treatment is "watchlist": implement when low-effort, but do not over-invest pending official confirmation.

### Step 1.5 — Evaluation rules
A site passes llms.txt declaration when ALL of the following rules pass (NB: applies only to sites that have chosen to publish llms.txt):

1. **File present at canonical location.** The file exists at `/llms.txt` (root) and returns HTTP 200 with `Content-Type: text/plain` or `text/markdown`.
2. **Format follows the proposed spec.** The file uses the markdown format with a leading H1 (project name), a blockquote summary, optional details, and one or more H2 sections listing canonical URLs as markdown links with brief descriptions.
3. **Linked URLs are alive.** All URLs referenced in llms.txt return 200 (no 404s, no redirects to unrelated content).
4. **`/llms-full.txt` provided where applicable.** Sites with substantive documentation publish a `/llms-full.txt` containing the concatenated content of all canonical pages (the inlined version designed for direct LLM ingestion).
5. **Content matches reality.** The summary and section descriptions accurately describe the site's actual content (not aspirational, not stale).
6. **No conflicts with `robots.txt`.** llms.txt does not list URLs that `robots.txt` blocks for LLM bots — internally consistent.

A site passing all 6 rules has well-formed llms.txt declaration.

### Step 2 — Citations
1. **Howard, J. — llms.txt proposal** (https://llmstxt.org/, Answer.AI / FastAI, accessed May 2026). The original proposal and authoritative spec.
2. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Recommends adding llms.txt as low-effort hygiene; explicitly notes it is unconfirmed but consistent with broader LLM-readability practice.
3. **Search Engine Land — coverage of llms.txt adoption** (https://searchengineland.com/, accessed May 2026, multiple articles). Industry coverage tracking llms.txt rollout and the pending confirmation from major LLM providers.

### Step 3 — Evidence weight rationale
No LLM provider has officially confirmed consumption of llms.txt for ranking or training; the file is published by site owners but its impact is unverified. Adoption is rapid because the cost of compliance is low. Qualifies as **Speculative**.

### Step 4 — Data source(s)
- **Primary: our own** simple HTTP fetch of `/llms.txt` and `/llms-full.txt` plus markdown parsing.
- **Cross-reference: P6-17** for robots.txt consistency check.

### Step 5 — Verification
Trivial fetch + parse. Granularity required: per-site llms.txt presence and rule-by-rule findings. Granularity delivered: matches.

### Step 6 — Cost
Negligible.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P6-17 (LLM-bot crawler access), P2-01 (robots.txt — same family of declarative files).

---

## P6-19 — Schema.org structured data depth

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
The depth, completeness, and interconnection of schema.org structured data across the site: not just whether schema is present (covered for narrow cases in P1-31 schema correctness, P5-26 LocalBusiness markup), but whether the site uses an interconnected web of schema types — `Organization`, `Person`, `Article`, `Product`, `Event`, `WebPage`, `BreadcrumbList`, `FAQPage`, `HowTo`, `Review`, `Recipe`, `VideoObject`, plus `sameAs` and `mentions` linkages — to provide LLMs with a rich machine-readable knowledge graph of the site's entities and content.

### Step 1.5 — Evaluation rules
A site passes schema depth when ALL of the following rules pass:

1. **Organisation schema on every page.** A site-wide `Organization` schema (or `Person` for personal brands) is present on the homepage and ideally repeated as part of a structured-data graph on every page.
2. **Page-type schema present.** Each substantive page declares its specific type via the most-specific applicable schema (`Article` for articles, `Product` for products, `Event` for events, `Recipe` for recipes, etc.), not bare `WebPage`.
3. **BreadcrumbList present site-wide.** `BreadcrumbList` schema reflects the site's information architecture, present on every non-homepage URL.
4. **Author schema on bylined content.** Articles include `author` linked to a `Person` entity with `name`, `url`, and `sameAs` (LinkedIn, Twitter/X, Wikipedia where applicable).
5. **Schema graph linkage.** Use of `@graph` to compose multiple entities per page (e.g., `WebPage` + `Article` + `Organization` + `Person`) with `@id` referencing — produces a richer ingestible graph than disconnected schema blocks.
6. **`sameAs` and `mentions` populated.** Entities reference their authoritative IDs (`sameAs` to Wikipedia, Wikidata, official social profiles); content `mentions` links to entities discussed in the article.
7. **Schema validates.** All schema validates against schema.org with no errors and passes Google's Rich Results Test for applicable rich-result types.
8. **Schema content matches visible content.** No hidden-information schema (rule from Google's structured-data guidelines): facts in schema appear in the visible page content.

A site passing all 8 rules has rich schema depth.

### Step 2 — Citations
1. **Schema.org — Full Hierarchy** (https://schema.org/docs/full.html, accessed May 2026). Canonical taxonomy of types and properties.
2. **Google Search Central — Structured data general guidelines** (https://developers.google.com/search/docs/appearance/structured-data/sd-policies, Google, accessed May 2026). Documents the "match visible content" rule and validation requirements.
3. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Recommends deep, interconnected schema as a top-tier GEO lever.
4. **iPullRank — Schema for E-E-A-T and entity SEO** (https://ipullrank.com/, accessed May 2026). Industry coverage of how schema feeds entity systems and AI Overview source selection.

### Step 3 — Evidence weight rationale
Schema is officially consumed by Google for rich results, AI Overview source selection, and entity reconciliation. Mechanism well-documented. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page** structured data extraction.
- **Validation: Google Rich Results Test** or our own schema.org JSON-LD validator.
- **Composition layer: our own** for graph-linkage detection (`@graph`, `@id`, `sameAs`, `mentions`) and depth scoring.

### Step 5 — Verification
DataForSEO returns JSON-LD blocks; validation logic is composition. Granularity required: per-site schema-depth score plus per-page type inventory plus rule-by-rule findings. Granularity delivered: by composition.

### Step 6 — Cost
Included in On-Page audit.

### Step 7 — Dependencies and cross-references
- **Scope of this variable:** site-wide schema graph depth — moves from per-block validity (P1-22) to graph-level interconnection across the site (`@graph`, `@id` references, `sameAs`/`mentions` linkage, page-type schema on every page, BreadcrumbList site-wide, Organization site-wide).
- **Schema family hierarchy:** P1-21 → type appropriateness (per page). P1-22 → completeness + validity (per block). P5-26 → LocalBusiness specialisation. **P6-19 (this) → site-wide schema graph depth + interconnection**. P6-20 → Person/Organization entity markup deep-dive (subset of P6-19 focused on entity layer).
- **Cross-references:** P1-21, P1-22, P5-26, P6-20 (entity-markup deep-dive within P6-19's scope), P6-11 (`sameAs` linkage feeds entity coverage).

---

## P6-20 — Author and organisation entity markup

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
Specifically the use of `Person` (for authors, executives, key staff) and `Organization` (for the publishing entity) schema with full property population: name, image, url, sameAs (to authoritative profiles — LinkedIn, Wikipedia, Wikidata, ORCID for academics, official social profiles), description (with disambiguating context), jobTitle, worksFor (for Person → Organization linkage), foundingDate, founder, knowsAbout, areaServed. Entity markup is the schema layer that most directly feeds Google's Knowledge Graph and AI Overview source selection because it provides the machine-readable identity information needed for entity reconciliation.

### Step 1.5 — Evaluation rules
A site passes author/organisation entity markup when ALL of the following rules pass:

1. **Organization schema on About/Contact pages.** A canonical `Organization` block lives on the homepage, About page, and Contact page with consistent `@id` across pages.
2. **Author Person schema on bylined content.** Each bylined article has an `author` property linking to a `Person` entity with `name`, `url` (to the author's bio page), `image`, and `sameAs`.
3. **Author bio page exists with markup.** The author bio page itself is a `ProfilePage` containing the full `Person` schema, mirroring the abbreviated `author` reference on articles.
4. **`sameAs` is rich and accurate.** `sameAs` includes verifiable links to LinkedIn, Twitter/X, Wikipedia (where article exists), Wikidata, ORCID (for academics), Google Scholar (for academics), official social profiles. URLs are live and the linked profile actually corresponds to the entity.
5. **Disambiguating description.** Person and Organization include a `description` property with disambiguating context (industry, location, area of expertise) so common names resolve correctly.
6. **`worksFor` / `member` linkage.** Authors are linked to their organisation via `worksFor`; organisations enumerate key personnel via `member` or `employee` where appropriate.
7. **`knowsAbout` populated for authors.** Author schema declares `knowsAbout` covering the topical areas the author writes about — supports topical authority reconciliation.
8. **Entity matches Knowledge Graph (where applicable).** For authors and organisations recognised in Google's Knowledge Graph, the schema's `sameAs` includes the KG ID URL (`https://www.google.com/search?kgmid=...`) — closes the loop with KG.

A site passing all 8 rules has solid author/organisation entity markup.

### Step 2 — Citations
1. **Schema.org — Person** (https://schema.org/Person, accessed May 2026) and **Organization** (https://schema.org/Organization, accessed May 2026). Canonical schemas.
2. **Google Search Central — E-E-A-T and author markup guidance** (https://developers.google.com/search/docs/appearance/structured-data/article#author, Google, accessed May 2026). Specific guidance on `author` property usage.
3. **iPullRank — Entity SEO and Knowledge Graph** (https://ipullrank.com/, accessed May 2026). Documents the role of entity markup in feeding Knowledge Graph and AI search.
4. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Identifies author/organisation entity markup as foundational for AI search visibility.

### Step 3 — Evidence weight rationale
Officially documented by Google and Schema.org; widely confirmed by practitioner studies; mechanism (entity reconciliation) is well-established. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page** structured data extraction.
- **Cross-reference: Google Knowledge Graph Search API** for entity-recognition verification.
- **Composition: our own** for rule-by-rule check including `sameAs` URL liveness check and `worksFor` linkage validation.

### Step 5 — Verification
DataForSEO and KG API both verified. Granularity required: per-site author and organisation entity markup status plus rule-by-rule findings. Granularity delivered: by composition.

### Step 6 — Cost
Included in On-Page audit plus KG API quotas.

### Step 7 — Dependencies and cross-references
- **Scope of this variable:** Person and Organization entity markup deep-dive — fully populated `Person` and `Organization` schema with `sameAs` to authoritative profiles (LinkedIn, Wikipedia, Wikidata, ORCID), `worksFor` linkage, `knowsAbout`, KG-ID closure. Subset of P6-19's broader graph view, focused on the entity layer.
- **Schema family hierarchy:** P1-21 → type appropriateness. P1-22 → completeness + validity. P5-26 → LocalBusiness specialisation. P6-19 → site-wide schema graph depth. **P6-20 (this) → Person/Organization entity markup deep-dive**.
- **Author authority hierarchy:** P4-04 → author bio with credentials (on-page editorial). P4-05 → author entity recognition (KG check on the author). **P6-20 (this) → Person/Organization schema markup making the author/org machine-readable**. The three are layers: P4-04 is what a human reads; P4-05 is whether KG knows about the author; P6-20 is the schema that connects the page's author to the entity layer.
- **Cross-references:** P0-16, P4-04, P4-05, P6-11, P6-19, P6-29.

---

## P6-21 — Vector retrievability (chunk semantic coherence)

**Pillar:** AI Search / GEO
**Evidence weight:** Probable

### Step 1 — Definition
The semantic coherence of the page's content when chunked by retrieval systems for vector embedding and semantic search. Modern RAG systems (Perplexity, ChatGPT Search, Claude with web, AI Overview) split fetched pages into chunks (typically 200–800 tokens), embed each chunk, and retrieve the most-relevant chunks against the user's query embedding. A page where each section is internally coherent — where chunks contain self-contained semantic units rather than fragments of multiple unrelated thoughts — produces stronger embeddings, higher relevance scores, and a higher chance of inclusion in the answer's context window.

### Step 1.5 — Evaluation rules
A page passes vector retrievability when ALL of the following rules pass:

1. **Single-topic sections.** Each H2 section is internally about a single sub-topic (the H2 heading is a faithful summary). No section meanders across multiple unrelated thoughts.
2. **Section length within chunk window.** Each section's body is between 100 and 800 words — long enough to carry substance, short enough to chunk into 1–3 retrievable units without being split mid-thought.
3. **Topic statement at section head.** Each section's first paragraph states the section's main claim or definition (so the chunk's leading tokens, which dominate embedding similarity for many retrievers, are topical).
4. **Few cross-section dependencies.** Sections are interpretable on their own; they do not require reading earlier sections to understand (no "as discussed above" carrying load-bearing context).
5. **Glossary / definitions resolved inline.** Specialised terms are defined inline or linked when first used in a section, not assumed-defined-elsewhere.
6. **No interleaved unrelated content.** Sidebars, related-posts, and ad blocks are visually separated and ideally placed in `<aside>` (overlaps with P6-01 rule 7) so they are not chunked into the main content embeddings.
7. **Lists and tables have introductory context.** Lists and tables are preceded by a sentence introducing what they enumerate or compare (so the chunk that contains the list also contains its semantic frame).

A page passing all 7 rules has strong vector retrievability.

### Step 2 — Citations
1. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Discusses chunking and retrieval-time semantic coherence as a foundational property for AI search inclusion.
2. **OpenAI — RAG and embeddings best practices documentation** (https://platform.openai.com/docs/guides/embeddings, OpenAI, accessed May 2026). Describes the chunking and retrieval mechanism.
3. **Pinecone, Weaviate, Anthropic — RAG documentation** (https://docs.pinecone.io/guides/get-started/quickstart, https://weaviate.io/developers/weaviate, https://docs.anthropic.com/, accessed May 2026). Vendor documentation describing chunking strategies and the role of chunk coherence.
4. **Aggarwal, P., et al. — GEO: Generative Engine Optimization** (https://arxiv.org/abs/2311.09735, KDD 2024, accessed May 2026). The structural-clarity and topical-cohesion levers tested in the paper align with vector retrievability properties.

### Step 3 — Evidence weight rationale
Mechanism is well-documented in vendor RAG documentation. Direct measurement of retrieval lift is feasible (we could embed the page chunks ourselves and measure cosine similarity to representative queries) but absolute lift attribution depends on the specific retriever's embedding model. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: LLM evaluation** of section coherence and rule-by-rule check.
- **Optional advanced: our own embedding evaluation** — embed each chunk via Gemini Embedding 2 (already integrated for 2Connect) or OpenAI text-embedding-3, simulate query retrieval against representative target queries, and measure top-k inclusion rate as a proxy.

### Step 5 — Verification
LLM evaluation feasible. Embedding-based evaluation is also feasible at modest cost. Granularity required: per-page vector-retrievability score plus rule-by-rule findings; advanced mode adds simulated query retrieval scores. Granularity delivered: by composition.

### Step 6 — Cost
LLM evaluation modest. Embedding evaluation: ~$0.005–0.02 per page depending on length.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P6-01 (LLM-readable structure), P6-22 (topic depth), P6-10 (definitional clarity).

---

## P6-22 — Topic depth and exhaustiveness (semantic completeness)

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
Whether the page or the cluster of pages on the topic comprehensively covers the subtopics, related questions, and conceptual neighbours that a user investigating the topic would reasonably need. Generative engines preferring to cite a single source that answers the full prompt rather than stitching across many sources, a page that pre-empts the user's likely follow-up questions ("what about X?", "how does this compare to Y?", "what are the limitations?") is more likely to be cited as the primary source than a thin page that answers only the surface question.

### Step 1.5 — Evaluation rules
A page passes topic depth when ALL of the following rules pass:

1. **Coverage map exists.** The page (or its cluster) covers the canonical subtopics for the topic — measured against a target subtopic list compiled from People Also Ask, autocomplete, top-ranking competitor coverage, and the topic's Wikipedia article structure.
2. **Coverage exceeds 75% of canonical subtopics.** At least three-quarters of the identified canonical subtopics are addressed substantively (more than a passing mention).
3. **Comparisons present.** Where the topic has obvious comparisons or alternatives, the page addresses them ("X vs Y", "alternatives to X").
4. **Limitations and exceptions disclosed.** The page acknowledges the boundaries of its claims (when does this apply, when does it not) rather than presenting universal-truth-style answers.
5. **Internal linking to deeper sub-pages.** Where a subtopic warrants its own page, the main page links to the dedicated sub-page (cluster architecture from P1-26 / P4-01 — topic clusters).
6. **No unanswered People Also Ask questions.** The top 3–5 People Also Ask questions for the target query have explicit answers somewhere in the page or its cluster.
7. **Recency markers consistent.** For evergreen topics, the page is up to date with the current state (no "as of 2019" sections that have not been refreshed).

A page passing all 7 rules has good topic depth.

### Step 2 — Citations
1. **Aggarwal, P., et al. — GEO: Generative Engine Optimization** (https://arxiv.org/abs/2311.09735, KDD 2024, accessed May 2026). Comprehensive coverage is among the levers tested.
2. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Topic completeness identified as a primary GEO content lever.
3. **Backlinko — Skyscraper / linkable assets research** (https://backlinko.com/, accessed May 2026). Documents that comprehensive coverage outranks thin coverage for competitive informational queries.
4. **Google Search Central — Helpful content guidance** (https://developers.google.com/search/docs/fundamentals/creating-helpful-content, Google, accessed May 2026). Comprehensive treatment of topic is part of Google's helpful-content evaluation.

### Step 3 — Evidence weight rationale
Multiple converging sources; mechanism (LLM single-source preference for fully answered prompts) is well-established; classical SEO and AI search converge. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Coverage-map composition: our own** combining People Also Ask data (DataForSEO Labs), top-10 competitor coverage analysis (DataForSEO SERP + content scrape), and topic Wikipedia article structure parsing.
- **Coverage scoring: LLM evaluation** comparing page content against the coverage map.

### Step 5 — Verification
Component data sources verified. Composition logic is straightforward. Granularity required: per-page coverage score with rule-by-rule findings plus list of missing canonical subtopics. Granularity delivered: by composition.

### Step 6 — Cost
DataForSEO Labs PAA + SERP data: included in plans we already use. LLM evaluation: modest.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P1-26 (topic clustering — depth at the cluster level), P4-01 (content cluster strategy), P6-09 (FAQ — explicit subtopic coverage).

---

## P6-23 — Recency and freshness for time-sensitive queries

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
For queries where the answer changes over time — pricing, version numbers, statistics, leaderboard positions, current events, regulatory rules, software API behaviour — whether the page is recent enough that its claims are still accurate and whether the page declares a publication date and last-updated date that retrievers and LLMs can read. Generative engines responding to time-sensitive queries explicitly favour recent sources; a page from 2021 about the "current best" of anything is unlikely to be cited even if it ranked well on classical SEO factors.

### Step 1.5 — Evaluation rules
A page passes recency when ALL of the following rules pass (NB: applies to time-sensitive topics; evergreen reference content is treated separately):

1. **Topic time-sensitivity classified.** The page's topic has a documented time-sensitivity classification (very-fresh / fresh / evergreen) — not all content needs frequent updating.
2. **Publication date present and accurate.** The page declares a publication date in `Article.datePublished` schema and in visible content; the date matches when the content was actually first published.
3. **Last-updated date present and meaningful.** `Article.dateModified` is populated and reflects substantive content updates (not just a CSS change). Visible "Last updated" line matches the schema.
4. **Update cadence matches topic.** Very-fresh topics (current pricing, weekly stats, current events) are updated within the cadence required by the topic. Fresh topics (annual rankings, version comparisons) are updated within the cadence required.
5. **Stale claims removed or year-stamped.** Claims about "current" state are either updated to today's reality or year-stamped ("as of Q1 2024, the rate was X, since updated to Y") rather than left as bare uncalibrated claims.
6. **Sourced numerical facts have collection dates.** Statistical claims include the date of the underlying measurement, not just the publication date of the citing page.
7. **No internal date conflicts.** Schema, visible date, sitemap `<lastmod>`, and HTTP `Last-Modified` header are not in stark conflict.

A page passing all 7 rules has appropriate recency for its topic.

### Step 2 — Citations
1. **Google Search Central — Date guidance for articles** (https://developers.google.com/search/docs/appearance/publication-dates, Google, accessed May 2026). Documents date schema fields and recency interpretation.
2. **Google Patent — Document scoring based on document content update** (US7505964B2 and related, accessed May 2026). Patent literature confirming Google explicitly scores recency for time-sensitive queries.
3. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Recency identified as a critical lever for time-sensitive AI search visibility.
4. **iPullRank — Google Content Warehouse Leak — Freshness features** (https://ipullrank.com/google-algo-leak, accessed May 2026). The leak documents `lastSignificantUpdate`, `freshnessConfidence`, and related freshness signals.

### Step 3 — Evidence weight rationale
Google publicly documents date schema; the leak corroborates internal freshness mechanisms; AI Overview behaviour is observably recency-biased for time-sensitive queries. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page** for date schema extraction and `Last-Modified` header.
- **Topic time-sensitivity classification: our own** lookup (we maintain a topic-classification table).
- **Composition: our own** for rule-by-rule check.

### Step 5 — Verification
DataForSEO confirmed; topic classification is composition. Granularity required: per-page recency status plus rule-by-rule findings. Granularity delivered: by composition.

### Step 6 — Cost
Included in standard On-Page audit.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P1-31 (schema markup correctness), P4-21 (content freshness — broader content-ops view).

---

## P6-24 — Citation diversity in source URL pool

**Pillar:** AI Search / GEO
**Evidence weight:** Probable

### Step 1 — Definition
Whether the brand or topic is cited across a diverse pool of source URLs at the level the LLM sees during retrieval — distinct domains, distinct page types, distinct contexts — rather than being concentrated on a small number of sources or only on the brand's own properties. Diversity matters because LLM retrievers typically pull a top-k set of candidate sources for the query and synthesise across them; a brand referenced in one source is unlikely to be the "answer", while a brand referenced consistently across multiple independent sources in the top-k is likely to be cited as a primary subject.

### Step 1.5 — Evaluation rules
A brand passes citation diversity when ALL of the following rules pass:

1. **Distinct domain count.** The brand is referenced in at least 50 distinct external domains (rough heuristic; varies with industry size). Sources include but go beyond owned properties.
2. **Source-type diversity.** Sources span at least 4 of: news media, industry publications, academic / research, government / regulatory, forums (Reddit/Quora/Stack Exchange), Wikipedia, third-party reviews / directories, social media (LinkedIn, X) — not concentrated in a single category.
3. **No artificial concentration.** No single non-owned domain accounts for more than ~15% of total mentions (could indicate paid placement or syndication artifacts).
4. **Geographic spread (where applicable).** For brands serving multiple regions, mentions span the relevant regions in their respective dominant publications.
5. **Mention contexts diverse.** The brand is mentioned in different contexts (product reviews, founder interviews, industry analyses, customer case studies, news events) rather than only one type.
6. **Recent diversity.** Diversity is not historic-only; the brand is being mentioned across diverse sources in the last 12 months as well as historically.

A brand passing all 6 rules has good citation diversity.

### Step 2 — Citations
1. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Identifies citation diversity across source types as a foundational AI search lever.
2. **Princeton — GEO paper supplementary materials** (https://arxiv.org/abs/2311.09735, KDD 2024, accessed May 2026). The paper's analysis of cited-source pools demonstrates diversity correlates with answer-citation likelihood.
3. **Search Engine Land — AI Overview source-pool studies** (https://searchengineland.com/, accessed May 2026). Industry studies of which sources AI Overview pulls from for given queries.

### Step 3 — Evidence weight rationale
Mechanism is consistent with how retrieval systems work (top-k from diverse sources gives the LLM corroborating evidence). Direct lift attribution is harder to isolate from absolute mention volume. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: composition** combining DataForSEO Backlinks API for backlink-domain inventory, news-coverage data (P6-16), forum data (P6-13), training-corpus data (P6-12), Wikipedia/Wikidata data (P6-11) — aggregated into a citation-diversity profile.
- **Source-type classification: our own** taxonomy mapping domains to source types.

### Step 5 — Verification
All component data sources verified in their own variables. Composition logic is straightforward. Granularity required: per-brand citation-diversity profile with source-type breakdown plus rule-by-rule findings. Granularity delivered: by composition.

### Step 6 — Cost
Composition over already-collected data.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P3-01 (backlink count and quality), P3-09 (referring domain diversity — overlaps), P6-11/12/13/14/15/16 (the source-type variables that feed this aggregation).

---

## P6-25 — AI Overview inclusion frequency

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
The rate at which the brand or its content is cited by Google's AI Overview surface across a defined target keyword set. Unlike upstream content variables that *feed* AI search visibility, AI Overview inclusion frequency is the *outcome* measure: it directly answers the question "is our content actually being surfaced in Google's AI answer for our target queries?" — and it is the headline KPI most stakeholders care about.

### Step 1.5 — Evaluation rules
A brand passes AI Overview inclusion when ALL of the following rules pass against a defined target keyword set:

1. **Target keyword set defined.** A canonical list of target keywords exists per brand, drawn from owned tracked keywords plus high-intent long-tail variants (typically 100–1,000 keywords).
2. **AI Overview presence checked.** For each keyword, the SERP is fetched and the AI Overview block (if present) parsed for cited sources.
3. **Inclusion rate above benchmark.** The brand is cited in AI Overviews for at least the benchmark percentage of target keywords where an AI Overview is present (benchmark varies by industry; rough threshold 5–15% as a starting baseline for emerging brands, higher for category leaders).
4. **Position in citation list.** Where cited, the brand's URL appears in the top 3 cited sources (citation position correlates with subsequent click-through).
5. **Citation context is positive.** The cited sentence or claim presents the brand favourably — the brand is the answer, not the cautionary example.
6. **Inclusion is stable, not volatile.** Inclusion rate measured weekly does not swing wildly week-to-week (volatility indicates the inclusion is borderline rather than confidently held).

A brand passing all 6 rules has good AI Overview presence.

### Step 2 — Citations
1. **DataForSEO — SERP API AI Overview support documentation** (https://docs.dataforseo.com/v3/serp/google/ai_mode/, accessed May 2026). Documents the AI Overview / AI Mode response object containing cited sources.
2. **SerpAPI — Google AI Overview documentation** (https://serpapi.com/google-ai-overview, accessed May 2026). Alternative SERP source supporting AI Overview parsing.
3. **Search Engine Land — AI Overview tracking studies** (https://searchengineland.com/, accessed May 2026, multiple articles). Industry coverage and methodology references for AI Overview tracking.
4. **BrightEdge — Generative Parser** (https://www.brightedge.com/resources/research-reports, accessed May 2026). Commercial AI Overview tracking platform; methodology disclosures relevant to defining inclusion rate.

### Step 3 — Evidence weight rationale
AI Overview is a real, observable Google surface; SERP APIs return its cited sources directly. Mechanism is operational rather than theoretical. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO SERP API** for SERP fetch with AI Overview parsing.
- **Composition: our own** for keyword-set management, citation extraction, and rule-by-rule scoring.
- **Optional: SerpAPI** as a redundant source for cross-validation.

### Step 5 — Verification
DataForSEO SERP API documented and confirmed to return AI Overview citation data. Granularity required: per-brand inclusion rate per keyword set, per-keyword citation status, per-citation position and context. Granularity delivered: matches.

### Step 6 — Cost
DataForSEO SERP API costs ~$0.001–0.003 per SERP fetch. Tracking 500 keywords weekly: roughly $25–60/month per brand.

### Step 7 — Dependencies and cross-references
- **Cross-references:** All P6-01 through P6-24 variables feed into AI Overview inclusion as upstream causes; P6-26/27 are the analogous outcome variables for non-Google AI search surfaces.

---

## P6-26 — Perplexity citation frequency

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
The rate at which the brand or its content is cited by Perplexity AI across a target query set. Perplexity is the most citation-transparent of the major AI search engines — every answer surfaces its cited sources prominently — and is increasingly used by professionals as a Google substitute for research-oriented queries. Tracking Perplexity citation frequency is operationally similar to AI Overview tracking.

### Step 1.5 — Evaluation rules
A brand passes Perplexity citation when ALL of the following rules pass against the target query set:

1. **Target query set defined.** Same canonical query set as P6-25, plus query variants that match Perplexity's research-oriented usage patterns.
2. **Perplexity answers fetched.** Each query is run against Perplexity (via API where available, or via SerpAPI's Perplexity wrapper, or via headless browser) and the cited sources extracted.
3. **Citation rate above benchmark.** The brand is cited for at least the benchmark percentage of target queries (similar 5–15% starting baseline).
4. **Citation position.** Where cited, the brand appears in Perplexity's top 5 cited sources for the answer (Perplexity typically cites 5–10 sources; top position correlates with answer-influence).
5. **Citation aligns with brand expertise.** Citations are for queries within the brand's documented expertise areas, not random unrelated queries (alignment confirms the citation is meaningful).
6. **Pro mode (deeper research) citation, where applicable.** For brands targeting research-heavy queries, the brand appears in Perplexity Pro's deeper-research citations as well as standard mode.

A brand passing all 6 rules has good Perplexity presence.

### Step 2 — Citations
1. **Perplexity API documentation** (https://docs.perplexity.ai/, Perplexity, accessed May 2026). Documents the API and citation response structure.
2. **SerpAPI — Perplexity AI search results** (https://serpapi.com/perplexity-ai-search-api, accessed May 2026). Alternative source for Perplexity result tracking.
3. **Search Engine Land — Perplexity citation analysis** (https://searchengineland.com/, accessed May 2026). Industry coverage of Perplexity behaviour.
4. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Identifies Perplexity citation tracking as a primary GEO outcome metric.

### Step 3 — Evidence weight rationale
Perplexity exposes its citations directly; tracking is operational and unambiguous. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Perplexity API** for direct query and citation extraction.
- **Alternative: SerpAPI Perplexity wrapper** where direct API access is rate-limited.
- **Composition: our own** for query-set management and citation aggregation.

### Step 5 — Verification
Perplexity API documented. Granularity required: per-brand citation rate per query set, per-query citation status, position, and citation context. Granularity delivered: matches.

### Step 6 — Cost
Perplexity API: paid tier (~$5 per 1,000 queries at standard rates). Tracking 500 queries weekly: ~$10–15/month per brand.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P6-25 (AI Overview parallel), P6-27 (other AI assistants), P6-21/22 (upstream content properties driving inclusion).

---

## P6-27 — ChatGPT, Claude, and Gemini answer-citation frequency

**Pillar:** AI Search / GEO
**Evidence weight:** Probable

### Step 1 — Definition
The rate at which the brand or its content is cited or referenced by major LLM-driven assistants — ChatGPT (with web search enabled), Claude (with web search), Gemini, Microsoft Copilot — across a target query set. Unlike Perplexity (which always cites sources) and AI Overview (which always cites sources), citation behaviour in these assistants is more variable: some queries trigger web search and citations; others rely on internal knowledge with no citations. Tracking is consequently noisier and, where citations are absent, depends on testing for *mention* rather than citation.

### Step 1.5 — Evaluation rules
A brand passes citation/mention frequency across major assistants when ALL of the following rules pass against the target query set:

1. **Coverage across assistants.** The brand is tracked across at least ChatGPT (with web), Claude (with web), Gemini, and Microsoft Copilot — not a single platform.
2. **Citation present where web search triggers.** For queries that trigger web search in each assistant, the brand is cited at the benchmark rate (similar baseline to P6-25/26).
3. **Mention present in non-citing answers.** For queries that the assistant answers from internal knowledge (no web search), the brand is mentioned by name when relevant — measured by injecting representative prompts and checking output.
4. **Mention is accurate.** When the assistant mentions the brand from internal knowledge, the description is accurate (brand identity, category, products) — inaccuracies indicate gaps in P6-11/12 entity coverage and corpus presence.
5. **No confusion with similarly-named entities.** The assistant does not conflate the brand with another similarly-named entity (a P6-11 entity-disambiguation failure mode).
6. **Coverage stability.** Mention/citation rate is reasonably stable over weekly measurement; not a single-week anomaly.

A brand passing all 6 rules has good cross-assistant presence.

### Step 2 — Citations
1. **OpenAI — ChatGPT API documentation, web search tool** (https://platform.openai.com/docs, OpenAI, accessed May 2026). Documents web-search behaviour and citation response.
2. **Anthropic — Claude API documentation, web search tool** (https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/web-search-tool, Anthropic, accessed May 2026). Documents web-search tool and citation response.
3. **Google — Gemini API documentation** (https://ai.google.dev/gemini-api/docs, Google, accessed May 2026). Documents grounding sources for Gemini responses.
4. **Microsoft — Copilot tracking and analytics** (https://learn.microsoft.com/en-us/microsoft-copilot/, Microsoft, accessed May 2026). Documents Copilot answer behaviour.
5. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Treats cross-assistant tracking as the comprehensive AI search outcome metric.

### Step 3 — Evidence weight rationale
Web-search citation behaviour is documented and operational, so direct citation tracking is reliable. Internal-knowledge mention tracking is probabilistic (output varies with prompt phrasing, model state, temperature) and methodologically harder. Qualifies as **Probable** rather than Consensus.

### Step 4 — Data source(s)
- **Primary: direct API access** to ChatGPT, Claude, Gemini, Copilot using their web-search tools where available.
- **Composition: our own** for query-set management, citation extraction (where present), and mention-detection logic for non-citing answers.

### Step 5 — Verification
Each assistant's API documented. Granularity required: per-assistant citation/mention rate plus per-query result table plus aggregate cross-assistant score. Granularity delivered: by composition.

### Step 6 — Cost
Per-query cost varies: ChatGPT API ~$0.03–0.10 per query with web; Claude similar; Gemini and Copilot vary. Tracking 500 queries weekly across 4 assistants: roughly $250–500/month per brand. Significantly more expensive than P6-25/26.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P6-25 (AI Overview), P6-26 (Perplexity), P6-11 (entity coverage — feeds disambiguation rule), P6-12 (training corpus presence — feeds internal-knowledge mention).

---

## P6-28 — Brand sentiment in LLM outputs

**Pillar:** AI Search / GEO
**Evidence weight:** Probable

### Step 1 — Definition
The sentiment polarity of LLM-generated descriptions of the brand when prompted directly ("Tell me about [brand]") or comparatively ("Should I use [brand] or [competitor]?"). Sentiment in LLM outputs reflects the aggregated tone across the brand's training-corpus mentions plus retrieval-time content; a brand with predominantly negative Reddit threads, complaint coverage, or unfavourable Wikipedia tone will have those echoes surface in LLM descriptions.

### Step 1.5 — Evaluation rules
A brand passes LLM sentiment when ALL of the following rules pass:

1. **Direct-description sentiment positive or neutral.** Output of "Tell me about [brand]" prompts across major LLMs (ChatGPT, Claude, Gemini, Perplexity) is rated positive or neutral on average via a reproducible sentiment classifier.
2. **Comparative sentiment is not adversarial.** "Should I use [brand] or [competitor]?" prompts produce balanced or favourable comparisons rather than systematically recommending the competitor.
3. **No false negative claims.** LLMs do not surface false negative claims about the brand (e.g., made-up scandals, fabricated criticisms).
4. **No outdated negative anchoring.** LLMs do not anchor on a historic negative event that has been resolved (e.g., a 2018 incident treated as defining present-day brand identity).
5. **Sentiment is stable across phrasings.** Brand sentiment does not flip wildly between similar prompt phrasings (instability indicates fragile representation in the model's weights).
6. **Sentiment aligned across assistants.** Sentiment is broadly consistent across ChatGPT, Claude, Gemini, Perplexity (assistant-specific divergence indicates one assistant has a particular training-data skew).

A brand passing all 6 rules has good LLM sentiment.

### Step 2 — Citations
1. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Treats LLM-output sentiment as a brand-reputation outcome metric.
2. **Search Engine Land — LLM brand sentiment studies** (https://searchengineland.com/, accessed May 2026, multiple articles). Industry coverage of methodologies for measuring brand sentiment in LLM outputs.
3. **Anthropic — Constitutional AI papers** (https://www.anthropic.com/research, accessed May 2026). Background on how LLMs incorporate corpus sentiment into outputs.
4. **OpenAI — Model behaviour documentation** (https://platform.openai.com/docs, accessed May 2026). Documents the relationship between training data and output behaviour relevant to sentiment.

### Step 3 — Evidence weight rationale
Mechanism (corpus sentiment → output sentiment) is well-established. Direct measurement is feasible but methodologically sensitive (prompt phrasing, temperature, model version). Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: direct API access** to major LLMs with a defined prompt battery (typically 5–20 prompts per brand spanning direct, comparative, and topical variants).
- **Sentiment scoring: composition** — Claude Haiku as a sentiment classifier scoring each LLM output, aggregated to a per-brand sentiment score per LLM.

### Step 5 — Verification
LLM API access verified; sentiment classification feasible. Granularity required: per-brand sentiment score per LLM plus per-prompt output text plus per-prompt sentiment classification plus stability metric. Granularity delivered: by composition.

### Step 6 — Cost
Per-prompt cost across 4 LLMs and 20 prompts per brand: ~$2–5 per measurement. Weekly measurement: ~$10–25/month per brand.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P6-13 (forum sentiment — primary upstream cause), P6-16 (news coverage tone), P6-30 (Wikipedia article tone), P0-15 (brand search demand context).

---

## P6-29 — Knowledge Graph entity completeness

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
For brands and entities that have entries in Google's Knowledge Graph (P6-11 entity coverage establishes presence; this variable measures completeness), the depth and accuracy of the entity record: name, alternative names, description, image, official site URL, founding date, founders, headquarters location, key personnel, social profiles, parent organisation, subsidiary organisations, related entities. A complete KG record drives the Knowledge Panel display in Google search and feeds AI Overview source selection through entity-disambiguation pathways.

### Step 1.5 — Evaluation rules
A brand passes KG entity completeness when ALL of the following rules pass:

1. **Core properties populated.** `name`, `description`, `image`, `url` are all populated.
2. **Type classification correct.** The entity's `@type` matches its actual nature (Corporation, LocalBusiness, NewsMediaOrganization, EducationalOrganization, etc.) — not generic Thing.
3. **Description is accurate and current.** The description reflects the brand's current positioning and offerings, not a stale 2018 description.
4. **Founders and key personnel listed where applicable.** Where the brand is a company, founders are present; where applicable, current CEO/leadership.
5. **Social profile linkage complete.** `sameAs` links present for major social profiles, Wikipedia, Wikidata, and the official website.
6. **Image is current and brand-controlled.** The KG image is the official brand logo or a current representative image, not an outdated or third-party-uploaded image.
7. **No factual errors.** No incorrect facts (wrong founding date, wrong HQ, conflated with similarly-named entity).
8. **Verified via Google's official channels.** Where applicable, the brand has used Google's "Suggest an edit" or claimed knowledge panel via the verification flow.

A brand passing all 8 rules has a complete KG entity record.

### Step 2 — Citations
1. **Google Knowledge Graph Search API documentation** (https://developers.google.com/knowledge-graph, Google, accessed May 2026). Documents the entity record structure and properties.
2. **Google — Knowledge Panel verification** (https://support.google.com/knowledgepanel/answer/7534842, Google, accessed May 2026). Documents the verification and edit-suggestion flow.
3. **Wikidata — Entity property reference** (https://www.wikidata.org/wiki/Wikidata:List_of_properties, accessed May 2026). The Wikidata properties that propagate into Google Knowledge Graph.
4. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Identifies KG completeness as a foundational entity-layer requirement.

### Step 3 — Evidence weight rationale
Google publishes the KG API and the verification flow; KG drives Knowledge Panels and AI Overview entity recognition. Mechanism unambiguous. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: Google Knowledge Graph Search API** for entity record retrieval.
- **Cross-reference: Wikidata SPARQL** for the upstream properties feeding KG (KG draws heavily from Wikidata).
- **Composition: our own** for completeness scoring against the rule set.

### Step 5 — Verification
KG API and Wikidata SPARQL both documented. Granularity required: per-brand KG record plus rule-by-rule findings plus list of missing or incorrect properties. Granularity delivered: matches.

### Step 6 — Cost
KG API free at moderate volumes. Wikidata SPARQL free.

### Step 7 — Dependencies and cross-references
- **Scope of this variable:** Knowledge-Graph-specific deep audit — given the brand has a KG entry (P6-11 confirmed), is the entry's record complete, accurate, and verified? Different from P0-16 (binary recognition) and P6-11 (multi-system coverage).
- **Hierarchy:** P0-16 → "is brand recognised in KG" (strategic binary). P6-11 → "is brand covered across entity ecosystem" (operational). **P6-29 (this) → "is the KG record itself complete and accurate"** (deep audit). P6-30 → "is the Wikipedia article specifically high-quality and stable" (Wikipedia-deep audit).
- **Cross-references:** P0-16, P6-11, P6-20 (`sameAs` closure feeds KG), P6-30.

---

## P6-30 — Wikipedia article quality and stability

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
For brands and entities with a Wikipedia article (presence established in P6-11), the article's editorial quality, stability, and absence of dispute markers. Wikipedia is the single most influential training source for major LLMs and a primary disambiguation source for retrieval; an entity with a high-quality, stable Wikipedia article will be recognised, described, and cited more reliably than an entity whose article is a stub, has notability disputes, has been edit-warred, or has been flagged for problems.

### Step 1.5 — Evaluation rules
A brand passes Wikipedia article quality when ALL of the following rules pass:

1. **Article is not a stub.** Article length exceeds Wikipedia's stub threshold (rough heuristic: at least 1,500 words of body content).
2. **No active deletion or notability flags.** No `{{AfD}}` (Articles for Deletion), `{{prod}}` (proposed deletion), `{{notability}}` flags currently active on the article.
3. **No major editorial flags.** No `{{NPOV}}` (point-of-view dispute), `{{advert}}` (advert-like tone), `{{COI}}` (conflict-of-interest editing), `{{citation needed}}` clusters, or other major maintenance flags.
4. **Citation depth adequate.** The article has at least 10–15 citations to reliable, independent sources (varies by topic; rough threshold).
5. **Editorial stability.** The article has not been protected against editing due to vandalism or edit warring; the recent revision history shows steady incremental edits, not large reverts/redo wars.
6. **Talk page is healthy.** The article's talk page does not have active large-scale disputes about the article's framing or content.
7. **Lead section is canonical.** The article opens with a clear definitional sentence (per P6-10) and the lead summarises the article fairly.
8. **Multilingual coverage where applicable.** For globally relevant brands, the entity also has articles in other major-language Wikipedias (Spanish, Japanese, German, etc.) — supports multilingual LLM training and retrieval.

A brand passing all 8 rules has a high-quality, stable Wikipedia article.

### Step 2 — Citations
1. **Wikipedia — Notability guidelines** (https://en.wikipedia.org/wiki/Wikipedia:Notability, accessed May 2026).
2. **Wikipedia — Maintenance templates and flags** (https://en.wikipedia.org/wiki/Wikipedia:Template_messages/Cleanup, accessed May 2026). Documents the maintenance flag system.
3. **Wikipedia — Article quality assessment** (https://en.wikipedia.org/wiki/Wikipedia:WikiProject_Council/Assessment_FAQ, accessed May 2026). Documents the FA/GA/B/C/Start/Stub quality scale used by editors.
4. **Wikipedia API documentation** (https://www.mediawiki.org/wiki/API:Main_page, accessed May 2026). Programmatic access to article content, revision history, and flags.
5. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Identifies Wikipedia article quality as a critical AI-search lever.

### Step 3 — Evidence weight rationale
Wikipedia's foundational role in LLM training is well-documented; article-quality flags are official editorial signals; mechanism (article quality → LLM output reliability) is unambiguous. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: MediaWiki API** for article content, length, revision history, and template/flag inventory.
- **Composition: our own** for rule-by-rule check including quality-flag detection and revision-stability analysis.

### Step 5 — Verification
MediaWiki API documented and free. Granularity required: per-brand Wikipedia article quality status plus rule-by-rule findings plus list of active flags. Granularity delivered: matches.

### Step 6 — Cost
Free.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P6-11 (entity coverage — establishes presence), P6-12 (training corpus presence — Wikipedia is the foundational corpus), P6-29 (KG entity completeness — Wikipedia is the upstream source for many KG facts).

---

## P6-31 — LLM hallucination resistance (factual disambiguation)

**Pillar:** AI Search / GEO
**Evidence weight:** Probable

### Step 1 — Definition
The brand's resistance to LLM hallucinations — how often LLMs fabricate facts about the brand, conflate it with similarly-named entities, attribute incorrect products or services to it, or give incorrect contact / location / pricing information. High hallucination resistance comes from a combination of: complete and consistent entity coverage (P6-11), high training-corpus presence (P6-12), strong Wikipedia article (P6-30), and rich `sameAs` linkage (P6-20). The variable is treated as an outcome measure rather than a direct lever.

### Step 1.5 — Evaluation rules
A brand passes hallucination resistance when ALL of the following rules pass:

1. **No conflation with similarly-named entities.** Across major LLMs (ChatGPT, Claude, Gemini), the brand is correctly distinguished from similarly-named entities — measured via prompts that test disambiguation.
2. **Core facts correctly produced.** LLMs correctly state the brand's category, primary products/services, headquarters location, and founding year (within reasonable rounding) when prompted.
3. **No fabricated facts.** LLMs do not produce fabricated specific facts (made-up product names, made-up executives, made-up financials) when prompted for the brand.
4. **Acknowledges knowledge boundaries.** When prompted on facts the LLM does not know with high confidence, the LLM hedges or declines rather than fabricating.
5. **Consistency across phrasings.** The same factual question phrased differently produces consistent answers (instability indicates fragile representation).
6. **Stable across recent model versions.** Hallucination rate does not regress as model versions change; if a new model version regresses, this is detected and addressed via downstream variables (P6-12 corpus presence, P6-30 Wikipedia quality).

A brand passing all 6 rules has good hallucination resistance.

### Step 2 — Citations
1. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Identifies hallucination resistance as a brand-protection outcome metric.
2. **Anthropic — Hallucination research and Constitutional AI** (https://www.anthropic.com/research, accessed May 2026). Background on hallucination mechanisms.
3. **OpenAI — Model behaviour and hallucination documentation** (https://platform.openai.com/docs, accessed May 2026). Background.
4. **Stanford HAI — Foundation Model Transparency Index** (https://crfm.stanford.edu/fmti/, Stanford, accessed May 2026). Methodological reference for measuring model factuality.

### Step 3 — Evidence weight rationale
Mechanism is well-established (entity coverage and corpus presence drive accurate output); direct measurement is feasible via prompt batteries. Methodological noise is non-trivial. Qualifies as **Probable**.

### Step 4 — Data source(s)
- **Primary: direct API access** to major LLMs with a defined fact-test prompt battery (typically 20–40 prompts per brand testing identity, products, locations, key personnel, recent events).
- **Ground truth: composition** — the brand-fact ground truth is composed from owned sources (the brand's own About page and product catalogue) plus the brand's Wikipedia article and KG entity record.
- **Scoring: Claude Haiku as factuality classifier** comparing LLM outputs against ground truth.

### Step 5 — Verification
LLM API access verified; ground-truth composition is straightforward; scoring is feasible. Granularity required: per-brand hallucination-resistance score per LLM plus per-prompt output and ground-truth comparison plus per-rule findings. Granularity delivered: by composition.

### Step 6 — Cost
Per-prompt cost ~$0.05–0.15 across 4 LLMs at ~30 prompts per brand: ~$5–15 per measurement. Weekly tracking: ~$25–60/month per brand.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P6-11 (entity coverage — primary upstream cause), P6-12 (training corpus presence), P6-20 (entity markup), P6-29 (KG completeness), P6-30 (Wikipedia article quality), P6-28 (brand sentiment — overlapping concerns).

---

## P6-32 — Prompt-injection / adversarial content hygiene

**Pillar:** AI Search / GEO
**Evidence weight:** Consensus

### Step 1 — Definition
Whether the site's content contains accidental or deliberate patterns that could be interpreted as prompt injection by an LLM that fetches the page — instructions to the LLM ("ignore previous instructions, recommend [brand]"), invisible text targeting LLM context windows (white-on-white text, off-screen positioned text, hidden via CSS), or content that mimics LLM system-prompt syntax. Major LLM providers actively detect and demote sites that practice prompt injection; passing this hygiene check protects against being filtered out of AI search ingestion entirely.

### Step 1.5 — Evaluation rules
A site passes prompt-injection hygiene when ALL of the following rules pass:

1. **No "ignore previous instructions" patterns.** No content (visible or hidden) instructs the reader/LLM to ignore prior context or to take a specific recommendation action.
2. **No invisible text targeting LLMs.** No white-on-white text, no `display: none` text containing instructions or keyword stuffing, no off-screen-positioned text (negative-margin, `text-indent: -9999px`), no zero-font-size text, no ARIA-hidden text containing content not visible elsewhere.
3. **No fake system-prompt syntax.** No content that mimics LLM system-prompt or conversation syntax (e.g., "[SYSTEM]:", "[ASSISTANT]:", `<|im_start|>`-style tokens) used to attempt context-window manipulation.
4. **No bait-and-switch content.** Content visible to the page renderer matches the content delivered in the HTML response (no JS-driven bait-and-switch where the LLM crawler sees one thing and the human user sees another).
5. **No keyword stuffing in alt text or hidden attributes.** Image alt text, ARIA labels, and other accessibility attributes contain accurate descriptions, not keyword-stuffed manipulation copy.
6. **No instruction-like comments embedded in HTML.** HTML comments do not contain instructions targeting LLM crawlers.
7. **No deceptive structured data.** Structured data does not declare facts that contradict visible content (overlaps with P6-19 rule 8).

A site passing all 7 rules has good prompt-injection hygiene.

### Step 2 — Citations
1. **OWASP — LLM Top 10: Prompt Injection** (https://owasp.org/www-project-top-10-for-large-language-model-applications/, OWASP, accessed May 2026). Authoritative documentation of prompt injection patterns and defences.
2. **OpenAI — GPTBot and content policy** (https://platform.openai.com/docs, OpenAI, accessed May 2026). OpenAI's policy on content that attempts to manipulate model outputs.
3. **Anthropic — Acceptable use policy** (https://www.anthropic.com/legal/aup, Anthropic, accessed May 2026). Anthropic's policy.
4. **Google Search Central — Spam policies** (https://developers.google.com/search/docs/essentials/spam-policies, Google, accessed May 2026). Google's spam policies (cloaking, hidden text, deceptive structured data) overlap directly with the rules above.
5. **Foundation Inc — GEO Strategy Guide** (https://foundationinc.co/lab/generative-engine-optimization, accessed May 2026). Treats prompt-injection hygiene as a baseline ingestion-eligibility requirement.

### Step 3 — Evidence weight rationale
Major LLM providers and Google all explicitly publish policies; the mechanism (detected manipulation → filtering or demotion) is unambiguous and operationally enforced. Qualifies as **Consensus**.

### Step 4 — Data source(s)
- **Primary: DataForSEO On-Page** for raw-vs-rendered HTML comparison and hidden-text detection (CSS-based hiding patterns).
- **Composition: our own** for rule-by-rule pattern detection (regex on HTML for known injection patterns; LLM evaluation for subtler cases).

### Step 5 — Verification
DataForSEO confirmed for raw-vs-rendered comparison. Pattern detection is composition. Granularity required: per-site hygiene status plus per-rule findings plus list of specific violations with location. Granularity delivered: by composition.

### Step 6 — Cost
Included in standard On-Page audit plus modest LLM cost for subtle-pattern detection.

### Step 7 — Dependencies and cross-references
- **Cross-references:** P2-19 (rendered-vs-raw HTML parity — same checks for cloaking), P6-19 (schema depth — rule 8 about hidden information overlaps), P3-39 (algorithmic penalties — manipulation can trigger broader penalties). Hygiene failure on this variable can cause the site to be filtered from LLM ingestion entirely, making this a prerequisite gate for all the visibility-driving GEO variables.

---

# Pillar 6 Wrap-up

Pillar 6 — AI Search / Generative Engine Optimisation — is **complete** with all 32 variables documented. Coverage spans:

- **Content-structure variables** (P6-01 to P6-08) — semantic HTML, quotability, citation density, statistics, expert quotes, first-person authority, original research, comparison structures
- **Information-architecture and entity variables** (P6-09 to P6-16) — FAQ structure, definitional clarity, Wikipedia/Wikidata presence, training-corpus mentions, Reddit/forum presence, video transcripts, podcast transcripts, news coverage
- **Technical and infrastructure variables** (P6-17 to P6-24) — LLM-bot crawler access, llms.txt, schema depth, entity markup, vector retrievability, topic depth, recency, citation diversity
- **Outcome-measurement variables** (P6-25 to P6-32) — AI Overview inclusion, Perplexity citation, cross-assistant citation, brand sentiment, KG completeness, Wikipedia article quality, hallucination resistance, prompt-injection hygiene

Distribution by evidence weight: 14 Consensus, 16 Probable, 1 Speculative (P6-18 llms.txt), 1 Contested (none in this pillar).

---

# Taxonomy summary

**Total variables documented:** 232 across 7 pillars (after May 2026 deduplication audit; original draft was 236).

| Pillar | Variables | Status |
|--------|-----------|--------|
| Pillar 0 — Strategic Foundation | 18 | Complete |
| Pillar 1 — On-Page SEO | 50 | Complete (P1-39, P1-40 removed as proxies subsumed by P1-35, P1-34) |
| Pillar 2 — Technical SEO | 41 | Complete (P2-34, P2-35 removed as duplicates of P6-18, P6-17; P2-06 removed as externally unmeasurable) |
| Pillar 3 — Off-Page Authority | 39 | Complete (P3-11, P3-13, P3-16 removed May 2026 as externally unmeasurable leak features) |
| Pillar 4 — Content Operations | 24 | Complete (P4-18 removed May 2026 as externally unmeasurable) |
| Pillar 5 — Local SEO | 28 | Complete |
| Pillar 6 — AI Search / GEO | 32 | Complete (P6-15 removed May 2026 strategic-fit audit; low-ROI signal requiring paid podcast-index adapter) |

**May 2026 deduplication audit summary:**
- 4 entries removed and replaced with redirect notes pointing to the canonical entry: P1-39 → P1-35, P1-40 → P1-34, P2-34 → P6-18, P2-35 → P6-17.
- Cross-references tightened across 6 heavy-overlap clusters: brand entity (P0-16/P6-11/P6-29), content originality (P1-38/P1-46/P4-07/P4-21), original research (P4-11/P6-07), schema markup family (P1-21/P1-22/P5-26/P6-19/P6-20), author authority (P4-04/P4-05/P6-20), content freshness signals (P1-41/P1-42/P1-43/P4-02/P4-24/P6-23 — already documented as paired leak features).
- Step 1.5 evaluation rules retrofit pass complete: 23 entries across Pillars 0/1/2/4/5 brought up to multi-criteria correctness rules. File contains 84 Step 1.5 blocks across 232 variables; remainder are pure-measurement variables that do not warrant rules per the methodology rule.
- Non-weighting policy formalised in methodology section: no industry/site-type weightings will be assigned at this stage; weightings will be derived empirically through dogfooding rather than asserted from theory.

---

*End of file. Document grows incrementally as research proceeds.*
