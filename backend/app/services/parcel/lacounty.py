"""LA County GIS clients for parcel boundaries and building footprints."""
import logging
import math
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = httpx.AsyncClient(timeout=30)

COUNTY_PARCEL_URL = settings.lacounty_parcel_url
BUILDING_FOOTPRINT_URL = settings.lacounty_buildings_url


def _esri_to_geojson_features(features: list[dict]) -> list[dict]:
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


async def _query_layer(
    base_url: str,
    envelope: str,
    out_fields: str = "*",
    extra_params: dict | None = None,
) -> list[dict]:
    """Query an ArcGIS REST layer with an envelope geometry."""
    url = f"{base_url}/query"
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
    if extra_params:
        params.update(extra_params)

    try:
        response = await _client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return _esri_to_geojson_features(data.get("features", []))
    except httpx.HTTPError as e:
        logger.error(f"LA County query failed ({base_url}): {e}")
        return []
    except Exception as e:
        logger.error(f"LA County parse error ({base_url}): {e}")
        return []


class LACountyParcelClient:
    """Client for LA County Assessor parcel boundaries.

    Returns authoritative parcel polygons with APN, address, lot area,
    existing structure info (year built, bedrooms, sqft), and legal description.
    """

    async def get_parcel(self, lat: float, lng: float) -> dict | None:
        """Get the parcel containing the given point.

        Returns the parcel whose centroid is closest to the query point
        when multiple parcels intersect the search envelope.
        """
        buffer = 0.0003  # ~33 meters — tighter than ZIMAS for precision
        envelope = f"{lng - buffer},{lat - buffer},{lng + buffer},{lat + buffer}"
        out_fields = (
            "APN,AIN,SitusAddress,SitusFullAddress,SitusCity,SitusZIP,"
            "UseType,UseDescription,YearBuilt1,Bedrooms1,Bathrooms1,SQFTmain1,"
            "Units1,CENTER_LAT,CENTER_LON,Shape.STArea(),Shape.STLength()"
        )

        features = await _query_layer(COUNTY_PARCEL_URL, envelope, out_fields)
        if not features:
            logger.info(f"No County parcels at ({lat}, {lng}), widening search")
            buffer = 0.0006
            envelope = f"{lng - buffer},{lat - buffer},{lng + buffer},{lat + buffer}"
            features = await _query_layer(COUNTY_PARCEL_URL, envelope, out_fields)
            if not features:
                return None

        best = self._find_closest(features, lat, lng)
        if not best:
            return None

        props = best.get("properties", {})

        # Shape.STArea() is in square feet (source CRS is CA State Plane Zone 5)
        lot_area_sqft = self._safe_float(props.get("Shape.STArea()"))

        lot_width_ft = None
        lot_depth_ft = None
        dimensions_estimated = False
        if lot_area_sqft:
            estimated_side = math.sqrt(lot_area_sqft)
            lot_width_ft = round(estimated_side * 0.8, 1)
            lot_depth_ft = round(estimated_side * 1.2, 1)
            dimensions_estimated = True

        apn = (props.get("APN") or props.get("AIN") or "").strip()

        return {
            "apn": apn,
            "situs_address": (props.get("SitusFullAddress") or props.get("SitusAddress") or "").strip(),
            "geometry": best.get("geometry"),
            "lot_area_sqft": round(lot_area_sqft, 1) if lot_area_sqft else None,
            "lot_width_ft": lot_width_ft,
            "lot_depth_ft": lot_depth_ft,
            "dimensions_estimated": dimensions_estimated,
            "year_built": props.get("YearBuilt1"),
            "bedrooms": props.get("Bedrooms1"),
            "bathrooms": props.get("Bathrooms1"),
            "sqft": props.get("SQFTmain1"),
            "units": props.get("Units1"),
            "use_type": props.get("UseType"),
            "use_description": props.get("UseDescription"),
            "center_lat": self._safe_float(props.get("CENTER_LAT")),
            "center_lon": self._safe_float(props.get("CENTER_LON")),
        }

    def _find_closest(self, features: list[dict], lat: float, lng: float) -> dict | None:
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
            dist = math.sqrt((cx - lng) ** 2 + (cy - lat) ** 2)
            if dist < best_dist:
                best_dist = dist
                best = f
        return best

    def _safe_float(self, val: Any) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None


class LACountyBuildingClient:
    """Client for LARIAC 2020 building footprints.

    Returns building polygons with heights for structures within a parcel area.
    """

    async def get_buildings(self, lat: float, lng: float, buffer: float = 0.0005) -> list[dict]:
        """Get building footprints near a point.

        Returns a list of GeoJSON features with building polygons and metadata.
        """
        envelope = f"{lng - buffer},{lat - buffer},{lng + buffer},{lat + buffer}"
        out_fields = "BLD_ID,HEIGHT,ELEV,CODE,STATUS,AREA,Shape_Area"

        features = await _query_layer(BUILDING_FOOTPRINT_URL, envelope, out_fields)
        if not features:
            return []

        buildings = []
        for f in features:
            geom = f.get("geometry")
            if not geom or geom.get("type") != "Polygon":
                continue
            props = f.get("properties", {})
            buildings.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "bld_id": props.get("BLD_ID"),
                    "height_ft": self._safe_float(props.get("HEIGHT")),
                    "elevation_ft": self._safe_float(props.get("ELEV")),
                    "area_sqft": self._safe_float(props.get("AREA") or props.get("Shape_Area")),
                    "code": props.get("CODE"),
                    "status": props.get("STATUS"),
                },
            })

        return buildings

    def _safe_float(self, val: Any) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
