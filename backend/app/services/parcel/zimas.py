"""ZIMAS ArcGIS REST API client for LA City parcel data."""
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

ZONING_LAYER = 1102
PARCEL_LAYER = 14  # Parcels layer
BUILDING_LAYER = 28  # Building outlines


class ZIMASClient:
    """Client for querying LA City ZIMAS ArcGIS REST services."""

    def __init__(self):
        self.base_url = settings.zimas_base_url
        self.timeout = 30.0

    async def query_by_point(
        self, lat: float, lng: float, layer_id: int, out_fields: str = "*"
    ) -> list[dict]:
        """Query a ZIMAS layer by geographic point."""
        url = f"{self.base_url}/{layer_id}/query"
        params = {
            "geometry": f"{lng},{lat}",
            "geometryType": "esriGeometryPoint",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": out_fields,
            "returnGeometry": "true",
            "f": "geojson",
            "inSR": "4326",
            "outSR": "4326",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("features", [])
            except httpx.HTTPError as e:
                logger.error(f"ZIMAS query failed for layer {layer_id}: {e}")
                return []
            except Exception as e:
                logger.error(f"ZIMAS parse error for layer {layer_id}: {e}")
                return []

    async def get_zoning(self, lat: float, lng: float) -> dict | None:
        """Get zoning information for a point."""
        features = await self.query_by_point(lat, lng, ZONING_LAYER)
        if not features:
            return None

        props = features[0].get("properties", {})
        geometry = features[0].get("geometry")

        zone_code = props.get("ZONE_CMPLT", props.get("ZONE_CLASS", ""))
        zone_class = self._extract_zone_class(zone_code)

        return {
            "zone_code": zone_code,
            "zone_class": zone_class,
            "height_district": props.get("HEIGHT_DIST", ""),
            "specific_plan": props.get("SPECIFIC_PLAN", None),
            "overlay": props.get("OVERLAY", None),
            "geometry": geometry,
            "properties": props,
        }

    async def get_parcel_info(self, lat: float, lng: float) -> dict | None:
        """Get parcel information including geometry and dimensions."""
        features = await self.query_by_point(lat, lng, PARCEL_LAYER)
        if not features:
            return None

        props = features[0].get("properties", {})
        geometry = features[0].get("geometry")

        return {
            "apn": props.get("APN", props.get("AIN", "")),
            "address": props.get("SITUS_FULL", props.get("SITUSADDR", "")),
            "lot_area_sqft": self._safe_float(props.get("SHAPE_Area", props.get("LOT_AREA"))),
            "geometry": geometry,
            "properties": props,
        }

    async def get_buildings(self, lat: float, lng: float) -> list[dict]:
        """Get building footprints near a point."""
        features = await self.query_by_point(lat, lng, BUILDING_LAYER)
        return features

    async def get_full_parcel_data(self, lat: float, lng: float) -> dict | None:
        """Get combined parcel + zoning data for a point."""
        zoning = await self.get_zoning(lat, lng)
        parcel = await self.get_parcel_info(lat, lng)
        buildings = await self.get_buildings(lat, lng)

        if not zoning and not parcel:
            return None

        result = {
            "apn": "",
            "address": "",
            "zone_code": "",
            "zone_class": "",
            "height_district": None,
            "specific_plan": None,
            "overlay_zones": [],
            "lot_area_sqft": None,
            "lot_width_ft": None,
            "lot_depth_ft": None,
            "geometry": None,
            "building_footprints": [],
            "centroid_lat": lat,
            "centroid_lng": lng,
            "community_plan_area": None,
        }

        if parcel:
            result["apn"] = parcel.get("apn", "")
            result["address"] = parcel.get("address", "")
            result["lot_area_sqft"] = parcel.get("lot_area_sqft")
            result["geometry"] = parcel.get("geometry")

        if zoning:
            result["zone_code"] = zoning.get("zone_code", "")
            result["zone_class"] = zoning.get("zone_class", "")
            result["height_district"] = zoning.get("height_district")
            result["specific_plan"] = zoning.get("specific_plan")
            if zoning.get("overlay"):
                result["overlay_zones"] = [zoning["overlay"]]
            if not result["geometry"] and zoning.get("geometry"):
                result["geometry"] = zoning["geometry"]

        if buildings:
            result["building_footprints"] = [
                b.get("geometry") for b in buildings if b.get("geometry")
            ]

        if result["lot_area_sqft"] and not result["lot_width_ft"]:
            import math
            estimated_side = math.sqrt(result["lot_area_sqft"])
            result["lot_width_ft"] = round(estimated_side * 0.8, 1)
            result["lot_depth_ft"] = round(estimated_side * 1.2, 1)

        return result

    def _extract_zone_class(self, zone_code: str) -> str:
        """Extract base zone class from full zone code (e.g., 'R1-1' → 'R1')."""
        if not zone_code:
            return ""
        code = zone_code.upper().strip()
        for prefix in ["RE40", "RE20", "RE15", "RE11", "RE9", "RD1.5", "RD2", "RD3",
                        "RD4", "RD5", "RD6", "R1", "R2", "R3", "R4", "R5", "RS", "RE", "RU"]:
            if code.startswith(prefix):
                return prefix
        parts = code.split("-")
        return parts[0] if parts else code

    def _safe_float(self, val: Any) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
