"""ZIMAS ArcGIS REST API client for LA City zoning data."""
import logging
import re
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

ZONING_LAYER = 1102

_client = httpx.AsyncClient(timeout=30)


class ZIMASClient:
    """Client for querying LA City ZIMAS zoning classification.

    Parcel geometry and building footprints are sourced from LA County GIS
    (see lacounty.py). ZIMAS is used only for zoning layer queries.
    """

    def __init__(self):
        self.base_url = settings.zimas_base_url

    async def get_zoning(self, lat: float, lng: float) -> dict | None:
        """Get zoning information for a point."""
        url = f"{self.base_url}/{ZONING_LAYER}/query"
        buffer = 0.0005
        envelope = f"{lng - buffer},{lat - buffer},{lng + buffer},{lat + buffer}"
        params = {
            "geometry": envelope,
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "false",
            "f": "json",
            "inSR": "4326",
            "outSR": "4326",
        }

        try:
            response = await _client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            features = data.get("features", [])
            if not features:
                return None
        except httpx.HTTPError as e:
            logger.error(f"ZIMAS zoning query failed: {e}")
            return None
        except Exception as e:
            logger.error(f"ZIMAS parse error: {e}")
            return None

        props = features[0].get("attributes", {})

        zone_code = props.get("ZONE_CMPLT", props.get("ZONE_CLASS", ""))
        zone_class = self._extract_zone_class(zone_code)

        return {
            "zone_code": zone_code,
            "zone_class": zone_class,
            "height_district": props.get("HEIGHT_DIST", ""),
            "specific_plan": props.get("SPECIFIC_PLAN", None),
            "overlay": props.get("OVERLAY", None),
            "community_plan_area": props.get("COMMUNITY_PLAN_AREA", None),
        }

    def _extract_zone_class(self, zone_code: str) -> str:
        """Extract base zone class from full zone code (e.g., '[Q]R1-1' -> 'R1')."""
        if not zone_code:
            return ""
        code = re.sub(r"^[\[\(][A-Z][\]\)]\s*", "", zone_code.upper().strip())
        for prefix in ["RE40", "RE20", "RE15", "RE11", "RE9", "RD1.5", "RD2", "RD3",
                        "RD4", "RD5", "RD6", "R1", "R2", "R3", "R4", "R5", "RS", "RE", "RU",
                        "C1", "C2", "C4", "C5", "CM", "CR", "M1", "M2", "M3", "MR",
                        "PF", "OS", "A1", "A2", "RA"]:
            if code.startswith(prefix):
                return prefix
        parts = code.split("-")
        return parts[0] if parts else code
