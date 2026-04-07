from __future__ import annotations

import httpx
from fastmcp.exceptions import ToolError


class GennxApiClient:
    """Async HTTP client for GEN NX REST API."""

    def __init__(self, base_url: str, timeout: float = 30.0, mapi_key: str = ""):
        # Preserve any path in base_url (e.g., "https://host/gen") by ensuring it
        # ends with "/" so httpx joins request paths relatively rather than
        # treating absolute paths as a replacement for the base path.
        self._base_url = base_url.rstrip("/") + "/"
        headers = {}
        if mapi_key:
            headers["MAPI-Key"] = mapi_key
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers=headers,
        )

    async def request(
        self, method: str, endpoint: str, payload: dict | None = None
    ) -> dict:
        # Use a relative path (no leading slash) so httpx preserves the base_url
        # path component instead of overriding it.
        rel_endpoint = endpoint.lstrip("/")
        try:
            resp = await self._client.request(
                method, rel_endpoint, json=payload
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
