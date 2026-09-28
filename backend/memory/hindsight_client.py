"""Small synchronous adapter around the official Hindsight Python client."""

from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from hindsight_client import Hindsight
from hindsight_client_api.exceptions import ApiException
from hindsight_client_api.models.recall_response import RecallResponse
from hindsight_client_api.models.reflect_response import ReflectResponse
from hindsight_client_api.models.retain_response import RetainResponse

from Hindsight.config import get_settings

ResponseT = TypeVar("ResponseT")
MemoryContent = str | list[dict[str, Any]]


class HindsightMemoryClientError(RuntimeError):
    """A Hindsight API request failed."""


class HindsightConfigurationError(HindsightMemoryClientError):
    """Required Hindsight connection settings are missing or invalid."""


class HindsightMemoryClient:
    """Reuse one configured Hindsight SDK client for memory operations."""

    def __init__(self, sdk_client: Hindsight | None = None) -> None:
        settings = get_settings()
        self._bank_id = settings.hindsight_bank_id.strip()
        if not self._bank_id:
            raise HindsightConfigurationError("HINDSIGHT_BANK_ID must not be empty.")

        if sdk_client is None:
            base_url = settings.hindsight_base_url.strip()
            if not base_url:
                raise HindsightConfigurationError(
                    "HINDSIGHT_BASE_URL must not be empty."
                )
            self._sdk_client = Hindsight(
                base_url=base_url,
                api_key=settings.hindsight_api_key,
            )
        else:
            self._sdk_client = sdk_client

    def retain_memory(
        self,
        content: MemoryContent,
        *,
        bank_id: str | None = None,
        timestamp: datetime | None = None,
        context: str | None = None,
        document_id: str | None = None,
        metadata: dict[str, str] | None = None,
        tags: list[str] | None = None,
        retain_async: bool = False,
    ) -> RetainResponse:
        """Store an interaction or fact in the selected Hindsight memory bank."""
        arguments: dict[str, Any] = {
            "bank_id": self._resolve_bank_id(bank_id),
            "content": content,
        }
        optional_arguments = {
            "timestamp": timestamp,
            "context": context,
            "document_id": document_id,
            "metadata": metadata,
            "tags": tags,
        }
        arguments.update(
            {key: value for key, value in optional_arguments.items() if value is not None}
        )
        if retain_async:
            arguments["retain_async"] = True

        return self._request("retain", lambda: self._sdk_client.retain(**arguments))

    def recall_memory(
        self,
        query: str,
        *,
        bank_id: str | None = None,
        types: list[str] | None = None,
        max_tokens: int = 4096,
        budget: str = "mid",
        tags: list[str] | None = None,
        include_chunks: bool = False,
    ) -> RecallResponse:
        """Find memories relevant to a deal or question."""
        arguments: dict[str, Any] = {
            "bank_id": self._resolve_bank_id(bank_id),
            "query": query,
            "max_tokens": max_tokens,
            "budget": budget,
            "include_chunks": include_chunks,
        }
        if types is not None:
            arguments["types"] = types
        if tags is not None:
            arguments["tags"] = tags

        return self._request("recall", lambda: self._sdk_client.recall(**arguments))

    def reflect_memory(
        self,
        query: str,
        *,
        bank_id: str | None = None,
        budget: str = "low",
        context: str | None = None,
        max_tokens: int | None = None,
        tags: list[str] | None = None,
        include_facts: bool = True,
    ) -> ReflectResponse:
        """Ask Hindsight to reason over memories and return supporting facts."""
        arguments: dict[str, Any] = {
            "bank_id": self._resolve_bank_id(bank_id),
            "query": query,
            "budget": budget,
            "include_facts": include_facts,
        }
        optional_arguments = {
            "context": context,
            "max_tokens": max_tokens,
            "tags": tags,
        }
        arguments.update(
            {key: value for key, value in optional_arguments.items() if value is not None}
        )

        return self._request("reflect", lambda: self._sdk_client.reflect(**arguments))

    def close(self) -> None:
        """Release the underlying SDK's HTTP resources."""
        self._request("close", self._sdk_client.close)

    def _resolve_bank_id(self, bank_id: str | None) -> str:
        resolved_bank_id = (bank_id or self._bank_id).strip()
        if not resolved_bank_id:
            raise HindsightConfigurationError("bank_id must not be empty.")
        return resolved_bank_id

    @staticmethod
    def _request(operation: str, request: Callable[[], ResponseT]) -> ResponseT:
        try:
            return request()
        except ApiException as exc:
            status = f" (HTTP {exc.status})" if exc.status is not None else ""
            raise HindsightMemoryClientError(
                f"Hindsight {operation} request failed{status}."
            ) from exc
        except Exception as exc:
            raise HindsightMemoryClientError(
                f"Hindsight {operation} request failed."
            ) from exc