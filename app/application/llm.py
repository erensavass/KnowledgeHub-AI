from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


class LLMError(Exception):
    """Safe boundary for language-model failures."""


class LLMConfigurationError(LLMError):
    """Raised when a selected provider is not configured."""


class LLMTimeoutError(LLMError):
    """Raised when a provider request exceeds its deadline."""


class LLMProviderError(LLMError):
    """Raised when a provider cannot return a usable response."""


@dataclass(frozen=True)
class LLMGeneration:
    content: str


class LLMProvider(Protocol):
    provider_name: str
    model_name: str

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        timeout: float,
    ) -> LLMGeneration: ...

    def stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        timeout: float,
    ) -> AsyncIterator[str]: ...


class LLMProviderFactory(Protocol):
    def create(self, provider: str | None = None) -> LLMProvider: ...
