from __future__ import annotations

import httpx
from fastmcp.exceptions import ToolError


class GennxApiClient:
    """Async HTTP client for GEN NX REST API."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
        )

    async def request(
        self, method: str, endpoint: str, payload: dict | None = None
    ) -> dict:
        try:
            resp = await self._client.request(
                method, f"/{endpoint}", json=payload
            )
        except httpx.TimeoutException:
            raise ToolError(f"GEN NX request timed out ({endpoint})")
        except httpx.ConnectError:
            raise ToolError(
                f"Cannot connect to GEN NX at {self._base_url}. "
                "Is the application running?"
            )
        if resp.status_code >= 400:
            raise ToolError(
                f"GEN NX error {resp.status_code}: {resp.text[:500]}"
            )
        return resp.json()

    async def post(self, endpoint: str, payload: dict) -> dict:
        return await self.request("POST", endpoint, payload)

    async def get(self, endpoint: str) -> dict:
        return await self.request("GET", endpoint)

    async def put(self, endpoint: str, payload: dict) -> dict:
        return await self.request("PUT", endpoint, payload)

    async def delete(self, endpoint: str, payload: dict) -> dict:
        return await self.request("DELETE", endpoint, payload)

    async def close(self):
        await self._client.aclose()
