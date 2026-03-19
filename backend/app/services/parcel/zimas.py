"""ZIMAS ArcGIS REST API client for LA City parcel data."""
import logging
import math
import re
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

ZONING_LAYER = 1102
LANDBASE_LAYER = 105


_client = httpx.AsyncClient(timeout=30)


class ZIMASClient:
    """Client for querying LA City ZIMAS ArcGIS REST services."""

    def __init__(self):
        self.base_url = settings.zimas_base_url

    async def query_by_point(
        self, lat: float, lng: float, layer_id: int, out_fields: str = "*"
    ) -> list[dict]:
        """Query a ZIMAS layer using a small envelope around the point.

        ZIMAS point-in-polygon queries return 0 results, but envelope
        queries work reliably, so we construct a tight bounding box.
        """
        url = f"{self.base_url}/{layer_id}/query"
        buffer = 0.0005  # ~50 meters
        envelope = f"{lng - buffer},{lat - buffer},{lng + buffer},{lat + buffer}"
        params = {
            "geometry": envelope,
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": out_fields,
            "returnGeometry": "true",
            "f": "json",
            "inSR": "4326",
            "outSR": "4326",
        }

        try:
            response = await _client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            features = data.get("features", [])
            return self._esri_to_geojson_features(features)
        except httpx.HTTPError as e:
            logger.error(f"ZIMAS query failed for layer {layer_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"ZIMAS parse error for layer {layer_id}: {e}")
            return []

    def _esri_to_geojson_features(self, features: list[dict]) -> list[dict]:
        """Convert Esri JSON features to GeoJSON-like features."""
        result = []
        for f in features:
            geojson_feature: dict[str, Any] = {
                "properties": f.get("attributes", {}),
            }
            geom = f.get("geometry")
            if geom and "rings" in geom:
                geojson_feature["geometry"] = {
                    "type": "Polygon",
                    "coordinates": geom["rings"],
                }
            elif geom and "x" in geom:
                geojson_feature["geometry"] = {
                    "type": "Point",
                    "coordinates": [geom["x"], geom["y"]],
                }
            else:
                geojson_feature["geometry"] = geom
            result.append(geojson_feature)
        return result

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

    async def get_parcel_boundary(self, lat: float, lng: float) -> dict | None:
        """Get the individual parcel lot boundary from the Landbase layer.

        Returns the parcel whose centroid is closest to the query point.
        """
        features = await self.query_by_point(lat, lng, LANDBASE_LAYER)
        if not features:
            return None

        best = None
        best_dist = float("inf")
        for f in features:
            geom = f.get("geometry")
            if not geom or geom.get("type") != "Polygon":
                continue
            coords = geom["coordinates"][0] if geom.get("coordinates") else []
            if not coords:
                continue
            cx = sum(p[0] for p in coords) / len(coords)
            cy = sum(p[1] for p in coords) / len(coords)
            dist = math.sqrt((cx - lng)**2 + (cy - lat)**2)
            if dist < best_dist:
                best_dist = dist
                best = f

        return best

    async def get_full_parcel_data(self, lat: float, lng: float) -> dict | None:
        """Get combined parcel boundary + zoning data for a point."""
        zoning = await self.get_zoning(lat, lng)
        if not zoning:
            return None

        parcel_feature = await self.get_parcel_boundary(lat, lng)

        parcel_geometry = None
        lot_area_sqft = None
        apn = str(zoning.get("properties", {}).get("OBJECTID", ""))

        if parcel_feature:
            parcel_geometry = parcel_feature.get("geometry")
            props = parcel_feature.get("properties", {})
            shape_area = self._safe_float(props.get("Shape_Area"))
            lot_area_sqft = round(shape_area, 1) if shape_area else None
            pin = props.get("PIN", "")
            if pin:
                apn = pin.strip()

        if not lot_area_sqft:
            shape_area = self._safe_float(zoning.get("properties", {}).get("Shape_Area"))
            lot_area_sqft = round(shape_area, 1) if shape_area else None

        if not parcel_geometry:
            parcel_geometry = zoning.get("geometry")

        lot_width_ft = None
        lot_depth_ft = None
        dimensions_estimated = False
        if lot_area_sqft:
            # Estimated from sqrt(area) assuming ~4:5 aspect ratio; not surveyed
            estimated_side = math.sqrt(lot_area_sqft)
            lot_width_ft = round(estimated_side * 0.8, 1)
            lot_depth_ft = round(estimated_side * 1.2, 1)
            dimensions_estimated = True
            logger.info(f"Lot dimensions estimated from area ({lot_area_sqft} sqft): {lot_width_ft}x{lot_depth_ft} ft")

        return {
            "apn": apn,
            "address": "",
            "zone_code": zoning.get("zone_code", ""),
            "zone_class": zoning.get("zone_class", ""),
            "height_district": zoning.get("height_district"),
            "specific_plan": zoning.get("specific_plan"),
            "overlay_zones": [zoning["overlay"]] if zoning.get("overlay") else [],
            "lot_area_sqft": lot_area_sqft,
            "lot_width_ft": lot_width_ft,
            "lot_depth_ft": lot_depth_ft,
            "geometry": parcel_geometry,
            "building_footprints": [],
            "centroid_lat": lat,
            "centroid_lng": lng,
            "community_plan_area": None,
        }

    def _extract_zone_class(self, zone_code: str) -> str:
        """Extract base zone class from full zone code (e.g., '[Q]R1-1' → 'R1')."""
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

    def _safe_float(self, val: Any) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
