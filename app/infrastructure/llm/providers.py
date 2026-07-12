from typing import Any

import httpx

from app.application.llm import (
    LLMConfigurationError,
    LLMGeneration,
    LLMProvider,
    LLMProviderError,
    LLMTimeoutError,
)
from app.core.config import LLMProviderName, Settings


class DefaultLLMProviderFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self, provider: str | None = None) -> LLMProvider:
        selected = provider or self.settings.llm_provider.value
        if selected == LLMProviderName.OLLAMA:
            return OllamaLLMProvider(self.settings.ollama_base_url, self.settings.ollama_model)
        if selected == LLMProviderName.OPENAI:
            api_key = self.settings.openai_api_key.get_secret_value()
            if not api_key:
                raise LLMConfigurationError("openai_api_key_missing")
            return OpenAILLMProvider(api_key, self.settings.openai_model)
        raise LLMConfigurationError("unsupported_llm_provider")


class OllamaLLMProvider:
    provider_name = "ollama"

    def __init__(self, base_url: str, model_name: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name

    def generate(
        self, system_prompt: str, user_prompt: str, temperature: float, timeout: float
    ) -> LLMGeneration:
        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model_name,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "options": {"temperature": temperature},
                },
                timeout=timeout,
            )
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "")
            return LLMGeneration(content=str(content))
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("ollama_request_timed_out") from exc
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            raise LLMProviderError("ollama_generation_failed") from exc


class OpenAILLMProvider:
    provider_name = "openai"

    def __init__(
        self, api_key: str, model_name: str, base_url: str = "https://api.openai.com"
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")

    def generate(
        self, system_prompt: str, user_prompt: str, temperature: float, timeout: float
    ) -> LLMGeneration:
        try:
            response = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model_name,
                    "temperature": temperature,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
                timeout=timeout,
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            content = payload["choices"][0]["message"]["content"]
            return LLMGeneration(content=str(content))
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("openai_request_timed_out") from exc
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
            raise LLMProviderError("openai_generation_failed") from exc
