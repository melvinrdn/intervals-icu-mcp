"""Async HTTP client for the Hevy API (fork-specific — not part of upstream)."""

from typing import Any

import httpx

from .auth import ICUConfig


class HevyAPIError(Exception):
    """Custom exception for Hevy API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        """Initialize API error.

        Args:
            message: Error message
            status_code: HTTP status code if available
        """
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class HevyClient:
    """Async HTTP client for the Hevy API with automatic error handling."""

    BASE_URL = "https://api.hevyapp.com/v1"

    def __init__(self, config: ICUConfig):
        """Initialize the Hevy API client.

        Args:
            config: ICUConfig with the hevy_api_key field populated
        """
        self.config = config
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "HevyClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=30.0,
            headers={"api-key": self.config.hevy_api_key},
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def _request(
        self, method: str, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make an HTTP request and handle errors uniformly.

        Args:
            method: HTTP method
            path: API path (relative to BASE_URL)
            params: Optional query parameters

        Returns:
            Parsed JSON response

        Raises:
            HevyAPIError: On HTTP or request errors
        """
        assert self._client is not None, "Client must be used as an async context manager"
        try:
            response = await self._client.request(method, path, params=params)
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        except httpx.HTTPStatusError as e:
            message = e.response.text
            try:
                body = e.response.json()
                message = body.get("error", message)
            except Exception:
                pass
            raise HevyAPIError(message, status_code=e.response.status_code) from e
        except httpx.RequestError as e:
            raise HevyAPIError(f"Request failed: {e}") from e

    async def get_workouts(self, page: int = 1, page_size: int = 10) -> dict[str, Any]:
        """Fetch a page of logged workouts, newest first."""
        return await self._request("GET", "/workouts", params={"page": page, "pageSize": page_size})

    async def get_workout(self, workout_id: str) -> dict[str, Any]:
        """Fetch one workout by ID, with full exercise/set detail."""
        return await self._request("GET", f"/workouts/{workout_id}")

    async def get_routines(self, page: int = 1, page_size: int = 10) -> dict[str, Any]:
        """Fetch a page of saved routine templates."""
        return await self._request("GET", "/routines", params={"page": page, "pageSize": page_size})

    async def get_exercise_templates(self, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        """Fetch a page of exercise template definitions (Hevy's exercise catalog)."""
        return await self._request(
            "GET", "/exercise_templates", params={"page": page, "pageSize": page_size}
        )
