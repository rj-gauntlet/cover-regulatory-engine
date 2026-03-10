from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMService(ABC):
    """Provider-agnostic interface for LLM operations.

    Swap providers by implementing this interface.
    Currently supported: OpenAI (default).
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> str:
        """Generate a completion from a list of messages."""
        ...

    @abstractmethod
    async def complete_stream(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream a completion token by token."""
        ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        ...

    @abstractmethod
    async def embed_single(self, text: str) -> list[float]:
        """Generate an embedding for a single text."""
        ...
