import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from app.application.llm import LLMProvider
from app.application.prompting import PromptBuilder, PromptContext
from app.application.retrieval import RetrievalService
from app.core.logging import get_logger

logger = get_logger(__name__)
UNSUPPORTED_ANSWER = (
    "I could not find enough information in the selected documents to answer this question."
)


@dataclass(frozen=True)
class Citation:
    citation_id: str
    document_id: UUID
    original_filename: str
    chunk_id: UUID
    chunk_index: int
    page_number: int | None
    relevance_score: float
    excerpt: str


@dataclass(frozen=True)
class RAGAnswer:
    answer: str
    supported: bool
    provider: str
    model: str
    citations: list[Citation]
    source_count: int
    retrieval_metadata: dict[str, Any]
    request_id: UUID


class RAGService:
    def __init__(
        self,
        retrieval_service: RetrievalService,
        prompt_builder: PromptBuilder,
        provider: LLMProvider,
        temperature: float,
        timeout: float,
        citation_excerpt_length: int,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.prompt_builder = prompt_builder
        self.provider = provider
        self.temperature = temperature
        self.timeout = timeout
        self.citation_excerpt_length = citation_excerpt_length

    def answer(
        self,
        query: str,
        user_id: UUID,
        document_ids: list[UUID] | None,
        top_k: int,
        score_threshold: float | None,
    ) -> RAGAnswer:
        request_id = uuid4()
        log_context = {"request_id": str(request_id), "user_id": str(user_id)}
        logger.info("rag_request_started", extra=log_context)
        try:
            results = self.retrieval_service.search(
                query, user_id, document_ids, top_k, score_threshold
            )
            logger.info(
                "retrieval_completed",
                extra={**log_context, "retrieved_count": len(results)},
            )
            prompt = self.prompt_builder.build(query, results)
            logger.info(
                "context_assembled",
                extra={
                    **log_context,
                    "source_count": len(prompt.contexts),
                    "context_characters": prompt.context_characters,
                    "truncated": prompt.truncated,
                },
            )
            metadata = {
                "requested_top_k": top_k,
                "score_threshold": score_threshold,
                "retrieved_count": len(results),
                "context_source_count": len(prompt.contexts),
                "context_characters": prompt.context_characters,
                "context_truncated": prompt.truncated,
            }
            if not prompt.contexts:
                return self._unsupported(request_id, metadata, log_context)

            logger.info(
                "llm_request_started",
                extra={**log_context, "provider": self.provider.provider_name},
            )
            generation = self.provider.generate(
                prompt.system_prompt, prompt.user_prompt, self.temperature, self.timeout
            )
            logger.info(
                "llm_request_completed",
                extra={**log_context, "provider": self.provider.provider_name},
            )
            answer = generation.content.strip()
            if len(answer) < 2:
                return self._unsupported(request_id, metadata, log_context)
            citations = [self._citation(context) for context in prompt.contexts]
            return RAGAnswer(
                answer=answer,
                supported=True,
                provider=self.provider.provider_name,
                model=self.provider.model_name,
                citations=citations,
                source_count=len(citations),
                retrieval_metadata=metadata,
                request_id=request_id,
            )
        except Exception as exc:
            logger.error(
                "rag_request_failed",
                extra={**log_context, "error_type": type(exc).__name__},
            )
            raise

    def _unsupported(
        self, request_id: UUID, metadata: dict[str, Any], log_context: dict[str, str]
    ) -> RAGAnswer:
        logger.info("unsupported_answer_returned", extra=log_context)
        return RAGAnswer(
            answer=UNSUPPORTED_ANSWER,
            supported=False,
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            citations=[],
            source_count=0,
            retrieval_metadata=metadata,
            request_id=request_id,
        )

    def _citation(self, context: PromptContext) -> Citation:
        excerpt = re.sub(r"\s+", " ", context.included_content).strip()
        if len(excerpt) > self.citation_excerpt_length:
            excerpt = excerpt[: max(0, self.citation_excerpt_length - 1)].rstrip() + "…"
        result = context.result
        return Citation(
            citation_id=context.citation_id,
            document_id=result.document_id,
            original_filename=result.original_filename,
            chunk_id=result.chunk_id,
            chunk_index=result.chunk_index,
            page_number=result.page_number,
            relevance_score=result.score,
            excerpt=excerpt,
        )
