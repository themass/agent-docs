"""高德 POI 查询适配器；HTTP client 可注入以便测试完全离线运行。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode

AMAP_TEXT_URL = "https://restapi.amap.com/v3/place/text"
AMAP_AROUND_URL = "https://restapi.amap.com/v3/place/around"


class PoiHttpClient(Protocol):
    async def get(self, url: str, *, params: Mapping[str, str]) -> tuple[int, bytes]: ...


class HttpxPoiClient:
    def __init__(self, timeout_s: float = 5.0) -> None:
        self._timeout_s = timeout_s

    async def get(self, url: str, *, params: Mapping[str, str]) -> tuple[int, bytes]:
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.get(url, params=params)
            return response.status_code, response.content


@dataclass(frozen=True)
class PoiSearchConfig:
    amap_key: str = ""
    client: PoiHttpClient | None = None
    result_limit: int = 10


class PoiSearchError(ValueError):
    """上游请求或响应无法用于可信 POI 结果。"""


class AmapPoiSearch:
    def __init__(self, config: PoiSearchConfig) -> None:
        self._config = config
        self._client = config.client or HttpxPoiClient()

    async def search(self, *, query: str, lat: float | None = None, lng: float | None = None,
                     radius_m: int | None = None) -> dict[str, Any]:
        if not self._config.amap_key.strip():
            return {"status": "not_configured", "message": "未接入地图服务", "pois": []}
        around = lat is not None and lng is not None
        endpoint = AMAP_AROUND_URL if around else AMAP_TEXT_URL
        params = {"key": self._config.amap_key, "keywords": query, "offset": str(self._config.result_limit),
                  "page": "1", "extensions": "base", "output": "JSON"}
        if around:
            params["location"] = f"{lng},{lat}"
            params["radius"] = str(max(100, min(radius_m or 3000, 50000)))
            params["sortrule"] = "distance"
        try:
            status, body = await self._client.get(endpoint, params=params)
            if status != 200:
                raise PoiSearchError(f"HTTP {status}")
            payload = json.loads(body)
            if not isinstance(payload, dict) or payload.get("status") != "1":
                raise PoiSearchError("provider rejected query")
            pois = payload.get("pois", [])
            if not isinstance(pois, list):
                raise PoiSearchError("invalid POI list")
            return {"status": "ok", "pois": [_poi(item) for item in pois[:self._config.result_limit]
                                                if isinstance(item, dict)]}
        except Exception as exc:  # noqa: BLE001 — upstream details must not reach model context
            raise PoiSearchError("地图查询失败") from exc


def _poi(item: dict[str, Any]) -> dict[str, Any]:
    distance = item.get("distance")
    try:
        distance = int(distance) if distance not in (None, "") else None
    except (TypeError, ValueError):
        distance = None
    return {"name": _text(item.get("name")), "address": _text(item.get("address")),
            "distance_m": distance, "category": _text(item.get("type"))}


def _text(value: Any) -> str:
    return value.strip()[:300] if isinstance(value, str) else ""
