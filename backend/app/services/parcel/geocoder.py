"""Mapbox Geocoding API client."""
import logging
from urllib.parse import quote

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

MAPBOX_GEOCODE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places"

LA_BBOX = [-118.67, 33.70, -118.15, 34.34]

_client = httpx.AsyncClient(timeout=30)


async def geocode_address(address: str) -> dict | None:
    """Geocode an address to coordinates using Mapbox.

    Constrains results to Los Angeles area.
    Returns dict with lat, lng, full_address, and place_name.
    """
    if not settings.mapbox_access_token:
        logger.error("MAPBOX_ACCESS_TOKEN not configured")
        return None

    query = address
    if "los angeles" not in address.lower():
        query = f"{address}, Los Angeles, CA"

    url = f"{MAPBOX_GEOCODE_URL}/{quote(query)}.json"
    params = {
        "access_token": settings.mapbox_access_token,
        "types": "address",
        "bbox": ",".join(str(x) for x in LA_BBOX),
        "limit": 1,
    }

    try:
        response = await _client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as e:
        logger.error(f"Geocoding failed: {e}")
        return None

    features = data.get("features", [])
    if not features:
        logger.warning(f"No geocoding results for: {address}")
        return None

    feature = features[0]
    coords = feature["geometry"]["coordinates"]

    return {
        "lat": coords[1],
        "lng": coords[0],
        "full_address": feature.get("place_name", address),
        "place_name": feature.get("text", ""),
    }
