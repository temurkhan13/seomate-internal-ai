"""External service adapters.

Every external API (DataForSEO, GSC, GBP, Knowledge Graph, Wikipedia,
Reddit, etc.) and every LLM provider used for evaluation is wrapped in
an adapter inheriting from :class:`BaseAdapter`.

Adapters are populated stage-by-stage:

- H1a: dataforseo, gsc, gbp, google_kg, wikipedia, wikidata
- H1b: embeddings (Gemini / OpenAI)
- H1c: llm (Anthropic / OpenAI)
- H1d: backlinks (DataForSEO Backlinks), newsapi, reddit, stack_exchange,
       youtube, listen_notes, common_crawl, perplexity
"""
from seomate.adapters._base import (
    AdapterCallRecord,
    AdapterContext,
    BaseAdapter,
    rate_limited,
    retry_transient,
    tracked,
)
from seomate.adapters.dataforseo import DataForSEOAdapter, DataForSEOSettings
from seomate.adapters.embeddings import (
    Embedding,
    EmbeddingsAdapter,
    EmbeddingsNotConfigured,
    EmbeddingsSettings,
    cosine_similarity,
)
from seomate.adapters.knowledge_graph import (
    KGNotConfigured,
    KGSearchHit,
    KGSettings,
    KnowledgeGraphAdapter,
)
from seomate.adapters.llm import (
    LlmAdapter,
    LlmBatchResult,
    LlmNotConfigured,
    LlmSettings,
)
from seomate.adapters.psi import (
    PSIAdapter,
    PSINotConfigured,
    PSIResult,
    PSISettings,
    PSIStrategy,
)
from seomate.adapters.wikidata import WikidataAdapter, WikidataEntity
from seomate.adapters.wikipedia import (
    WikipediaAdapter,
    WikipediaArticle,
    WikipediaSearchHit,
)

__all__ = [
    "AdapterCallRecord",
    "AdapterContext",
    "BaseAdapter",
    "DataForSEOAdapter",
    "DataForSEOSettings",
    "Embedding",
    "EmbeddingsAdapter",
    "EmbeddingsNotConfigured",
    "EmbeddingsSettings",
    "KGNotConfigured",
    "KGSearchHit",
    "KGSettings",
    "KnowledgeGraphAdapter",
    "LlmAdapter",
    "LlmBatchResult",
    "LlmNotConfigured",
    "LlmSettings",
    "PSIAdapter",
    "PSINotConfigured",
    "PSIResult",
    "PSISettings",
    "PSIStrategy",
    "WikidataAdapter",
    "WikidataEntity",
    "WikipediaAdapter",
    "WikipediaArticle",
    "WikipediaSearchHit",
    "cosine_similarity",
    "rate_limited",
    "retry_transient",
    "tracked",
]
