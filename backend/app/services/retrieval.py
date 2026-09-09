import re
import unicodedata
import logging
from collections import Counter
from math import log
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    EmbeddingServiceError,
    RetrievalServiceError,
    VectorStoreError,
)
from app.repositories.document import DocumentRepository
from app.schemas.retrieval import (
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
)
from app.services.embedding import EmbeddingService
from app.services.knowledge_base import KnowledgeBaseService
from app.services.reranking import RerankingService
from app.services.vector_store import VectorStoreService


_CANDIDATE_MULTIPLIER = 10
_MAX_CANDIDATES = 100
_RRF_K = 60
_ASCII_TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
_CJK_PATTERN = re.compile(r"[\u3400-\u9fff]+")
logger = logging.getLogger(__name__)


def _ascii_tokens(text: str) -> set[str]:
    tokens: set[str] = set()

    for token in _ASCII_TOKEN_PATTERN.findall(text):
        if len(token) < 2:
            continue

        tokens.add(token)

        # Match common singular/plural forms such as retriever/retrievers.
        if token.endswith("s") and len(token) > 4:
            tokens.add(token[:-1])

    return tokens


def _cjk_bigrams(text: str) -> set[str]:
    compact = "".join(_CJK_PATTERN.findall(text))
    return {
        compact[index:index + 2]
        for index in range(max(0, len(compact) - 1))
    }


def lexical_relevance(query: str, content: str) -> float:
    """Return query-term coverage for mixed Chinese/English text."""
    normalized_query = unicodedata.normalize("NFKC", query).casefold()
    normalized_content = unicodedata.normalize("NFKC", content).casefold()
    query_ascii = _ascii_tokens(normalized_query)
    query_cjk = _cjk_bigrams(normalized_query)
    scores: list[float] = []

    if query_ascii:
        content_ascii = _ascii_tokens(normalized_content)
        scores.append(
            len(query_ascii & content_ascii) / len(query_ascii)
        )

    if query_cjk:
        content_cjk = _cjk_bigrams(normalized_content)
        scores.append(
            len(query_cjk & content_cjk) / len(query_cjk)
        )

    if not scores:
        return 0.0

    # Give code identifiers and Chinese terms equal influence when both exist.
    return sum(scores) / len(scores)


def _lexical_terms(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    terms = list(_ASCII_TOKEN_PATTERN.findall(normalized))

    for sequence in _CJK_PATTERN.findall(normalized):
        terms.extend(
            sequence[index:index + 2]
            for index in range(max(0, len(sequence) - 1))
        )

    return [term for term in terms if len(term) >= 2]


def bm25_scores(query: str, contents: list[str]) -> list[float]:
    """Calculate BM25 scores over a retrieval candidate set."""
    if not contents:
        return []

    query_terms = set(_lexical_terms(query))
    document_terms = [_lexical_terms(content) for content in contents]

    if not query_terms:
        return [0.0] * len(contents)

    document_count = len(document_terms)
    average_length = sum(map(len, document_terms)) / document_count or 1.0
    document_frequency = Counter(
        term
        for terms in document_terms
        for term in set(terms) & query_terms
    )
    scores: list[float] = []
    k1 = 1.5
    b = 0.75

    for terms in document_terms:
        frequencies = Counter(terms)
        length_normalizer = 1 - b + b * len(terms) / average_length
        score = 0.0

        for term in query_terms:
            frequency = frequencies[term]
            if not frequency:
                continue

            inverse_frequency = log(
                1 + (
                    document_count - document_frequency[term] + 0.5
                ) / (document_frequency[term] + 0.5)
            )
            score += inverse_frequency * (
                frequency * (k1 + 1)
                / (frequency + k1 * length_normalizer)
            )

        scores.append(score)

    return scores


def reciprocal_rank_fusion(
    vector_count: int,
    lexical_scores: list[float],
) -> list[int]:
    """Fuse vector and lexical ranks without comparing score scales."""
    lexical_order = sorted(
        (
            index
            for index, score in enumerate(lexical_scores)
            if score > 0
        ),
        key=lambda index: (-lexical_scores[index], index),
    )
    lexical_ranks = {
        index: rank
        for rank, index in enumerate(lexical_order, start=1)
    }

    return sorted(
        range(vector_count),
        key=lambda index: (
            -(
                1 / (_RRF_K + index + 1)
                + (
                    1 / (_RRF_K + lexical_ranks[index])
                    if index in lexical_ranks
                    else 0
                )
            ),
            -lexical_scores[index],
            index,
        ),
    )


def fuse_ranked_results(
    vector_results: list,
    lexical_results: list,
) -> list:
    """Fuse two independently ranked result lists by stable chunk ID."""
    by_id = {
        result.chunk_id: result
        for result in [*vector_results, *lexical_results]
    }
    scores: dict = Counter()
    first_seen: dict = {}
    position = 0
    for results in (vector_results, lexical_results):
        for rank, result in enumerate(results, start=1):
            scores[result.chunk_id] += 1 / (_RRF_K + rank)
            if result.chunk_id not in first_seen:
                first_seen[result.chunk_id] = position
                position += 1
    return [
        by_id[chunk_id]
        for chunk_id in sorted(
            by_id,
            key=lambda item: (-scores[item], first_seen[item]),
        )
    ]
class RetrievalService:
    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStoreService | None = None,
        reranking_service: RerankingService | None = None,
    ) -> None:
        self.embedding_service = (
            embedding_service or EmbeddingService()
        )
        self.vector_store = (
            vector_store or VectorStoreService()
        )
        self.reranking_service = reranking_service or RerankingService()

    def search(
        self,
        session: Session,
        knowledge_base_id: UUID,
        request: RetrievalRequest,
    ) -> RetrievalResponse:
        # 先验证知识库存在，避免为无效请求调用嵌入 API。
        KnowledgeBaseService.get(
            session,
            knowledge_base_id,
        )

        try:
            query_vector = self.embedding_service.embed_texts(
                [request.query]
            )[0]

            candidate_limit = min(
                _MAX_CANDIDATES,
                request.limit * _CANDIDATE_MULTIPLIER,
            )
            vector_matches = self.vector_store.search(
                knowledge_base_id=knowledge_base_id,
                query_vector=query_vector,
                limit=candidate_limit,
            )
            lexical_matches = self.vector_store.search_lexical(
                knowledge_base_id=knowledge_base_id,
                query=request.query,
                query_vector=query_vector,
                limit=candidate_limit,
            )
            matches = list(vector_matches)
            seen_chunk_ids = {match.chunk_id for match in matches}
            matches.extend(
                match
                for match in lexical_matches
                if match.chunk_id not in seen_chunk_ids
            )

        except (
            EmbeddingServiceError,
            VectorStoreError,
        ) as exc:
            raise RetrievalServiceError(str(exc)) from exc

        documents = DocumentRepository.get_many_for_knowledge_base(
            session,
            knowledge_base_id,
            [match.document_id for match in matches],
        )
        documents_by_id = {
            document.id: document
            for document in documents
        }

        eligible_vector_matches = [
            match
            for match in vector_matches
            if match.document_id in documents_by_id
            and match.score >= request.min_score
        ]
        eligible_lexical_matches = [
            match
            for match in lexical_matches
            if match.document_id in documents_by_id
            and match.score >= request.min_score
        ]
        fused_matches = fuse_ranked_results(
            eligible_vector_matches,
            eligible_lexical_matches,
        )
        rerank_candidates = fused_matches[
            :settings.reranker_candidate_limit
        ]
        if settings.reranker_enabled and rerank_candidates:
            try:
                reranked_order = self.reranking_service.rank(
                    request.query,
                    [match.content for match in rerank_candidates],
                )
                rerank_candidates = [
                    rerank_candidates[index]
                    for index in reranked_order
                ]
            except Exception as exc:
                logger.warning("Reranker unavailable; using RRF order: %s", exc)

        results: list[RetrievalResult] = []

        for match in rerank_candidates[:request.limit]:
            document = documents_by_id[match.document_id]

            results.append(RetrievalResult(
                chunk_id=match.chunk_id,
                document_id=match.document_id,
                original_filename=document.original_filename,
                chunk_index=match.chunk_index,
                content=match.content,
                page_number=match.page_number,
                token_count=match.token_count,
                metadata=match.metadata,
                score=match.score,
            ))

        return RetrievalResponse(
            knowledge_base_id=knowledge_base_id,
            query=request.query,
            results=results,
            total=len(results),
        )
