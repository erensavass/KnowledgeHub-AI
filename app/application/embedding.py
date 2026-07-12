from collections.abc import Sequence
from typing import Protocol


class EmbeddingError(Exception):
    """Safe application boundary for model and output failures."""


class EmbeddingModel(Protocol):
    def encode(self, sentences: list[str], **kwargs: object) -> object: ...


class EmbeddingService:
    def __init__(self, model_name: str, device: str = "cpu", batch_size: int = 32) -> None:
        if not model_name.strip() or not device.strip() or batch_size <= 0:
            raise ValueError("embedding service configuration is invalid")
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self._model: EmbeddingModel | None = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _load_model(self) -> EmbeddingModel:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            encoded = self._load_model().encode(
                list(texts),
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            vectors = encoded.tolist() if hasattr(encoded, "tolist") else encoded
            result = [[float(value) for value in vector] for vector in vectors]
        except Exception as exc:
            raise EmbeddingError("embedding_generation_failed") from exc
        if len(result) != len(texts) or not result or not result[0]:
            raise EmbeddingError("invalid_embedding_output")
        dimension = len(result[0])
        if any(len(vector) != dimension for vector in result):
            raise EmbeddingError("invalid_embedding_output")
        return result
