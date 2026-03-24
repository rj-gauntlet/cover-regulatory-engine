"""LA County GIS clients for parcel boundaries and building footprints."""
import logging
import math
import re
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

    async def get_parcel(self, lat: float, lng: float, address: str | None = None) -> dict | None:
        """Get the parcel containing the given point.

        When an address is provided, prefers the parcel whose SitusAddress
        matches the house number + street name. Falls back to closest centroid.
        """
        buffer = 0.0003
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

        best = self._find_best_match(features, lat, lng, address)
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

    def _find_best_match(
        self, features: list[dict], lat: float, lng: float, address: str | None
    ) -> dict | None:
        """Pick the best parcel: address match, then point-in-polygon, then centroid.

        When an address is provided the priority is:
        1. Exact situs address match (house number + street name)
        2. Parcel whose polygon contains the geocoded point
        3. None — no loose centroid fallback to avoid cross-street mismatches
        """
        valid = [f for f in features if f.get("geometry", {}).get("type") == "Polygon"
                 and f.get("geometry", {}).get("coordinates")]

        if not valid:
            return None

        if address:
            match = self._match_by_address(valid, address)
            if match:
                situs = (match.get("properties", {}).get("SitusAddress") or "").strip()
                logger.info(f"Parcel matched by address: '{situs}' for query '{address}'")
                return match

            pip_match = self._find_containing_parcel(valid, lat, lng)
            if pip_match:
                situs = (pip_match.get("properties", {}).get("SitusAddress") or "").strip()
                logger.info(f"Parcel matched by point-in-polygon: '{situs}' for query '{address}'")
                return pip_match

            logger.warning(f"No county parcel matches address '{address}'")
            return None

        return self._closest_by_centroid(valid, lat, lng)

    @staticmethod
    def _find_containing_parcel(features: list[dict], lat: float, lng: float) -> dict | None:
        """Find the parcel whose polygon contains the geocoded point."""
        point = (lng, lat)
        for f in features:
            if _point_in_polygon(point, f["geometry"]):
                return f
        return None

    def _match_by_address(self, features: list[dict], address: str) -> dict | None:
        """Find the parcel whose SitusAddress matches the searched address.

        Extracts the house number and street name from the query address and
        compares against each parcel's SitusAddress field.
        """
        house_num, street = self._parse_address(address)
        if not house_num:
            return None

        for f in features:
            situs = (f.get("properties", {}).get("SitusAddress") or "").strip().upper()
            if not situs:
                continue
            s_num, s_street = self._parse_address(situs)
            if s_num == house_num and street and s_street and street in s_street:
                return f

        return None

    @staticmethod
    def _parse_address(address: str) -> tuple[str, str]:
        """Extract (house_number, street_name) from an address string.

        '456 North June Street, Los Angeles, CA 90004' -> ('456', 'JUNE')
        '456  N JUNE ST' -> ('456', 'JUNE')
        """
        addr = address.upper().split(",")[0].strip()
        addr = re.sub(r"\s+", " ", addr)

        m = re.match(r"^(\d+)\s+(.+)$", addr)
        if not m:
            return ("", "")

        house_num = m.group(1)
        rest = m.group(2)

        direction_words = {"N", "S", "E", "W", "NORTH", "SOUTH", "EAST", "WEST",
                           "NE", "NW", "SE", "SW"}
        suffix_words = {"ST", "STREET", "AVE", "AVENUE", "BLVD", "BOULEVARD",
                        "DR", "DRIVE", "RD", "ROAD", "CT", "COURT", "PL", "PLACE",
                        "WAY", "LN", "LANE", "CIR", "CIRCLE", "TER", "TERRACE"}

        words = rest.split()
        street_words = [w for w in words if w not in direction_words and w not in suffix_words]
        street_name = " ".join(street_words) if street_words else rest

        return (house_num, street_name)

    @staticmethod
    def _closest_by_centroid(features: list[dict], lat: float, lng: float) -> dict | None:
        best = None
        best_dist = float("inf")
        for f in features:
            coords = f["geometry"]["coordinates"][0]
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

    async def get_buildings_for_parcel(
        self, parcel_geometry: dict | None, lat: float, lng: float
    ) -> list[dict]:
        """Get building footprints that overlap the parcel boundary.

        Uses the parcel bounding box to scope the ArcGIS query, then filters
        results to only buildings whose centroid falls within the parcel polygon.
        Falls back to a small buffer around the point if no parcel geometry.
        """
        if parcel_geometry and parcel_geometry.get("type") == "Polygon":
            coords = parcel_geometry["coordinates"][0]
            lngs = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            envelope = f"{min(lngs)},{min(lats)},{max(lngs)},{max(lats)}"
        else:
            buffer = 0.0002
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

            if parcel_geometry and parcel_geometry.get("type") == "Polygon":
                bld_centroid = _polygon_centroid(geom)
                if not _point_in_polygon(bld_centroid, parcel_geometry):
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


def _polygon_centroid(geom: dict) -> tuple[float, float]:
    """Compute centroid of a GeoJSON Polygon as (lng, lat)."""
    coords = geom.get("coordinates", [[]])[0]
    if not coords:
        return (0.0, 0.0)
    cx = sum(c[0] for c in coords) / len(coords)
    cy = sum(c[1] for c in coords) / len(coords)
    return (cx, cy)


def _point_in_polygon(point: tuple[float, float], polygon: dict) -> bool:
    """Ray-casting point-in-polygon test for a GeoJSON Polygon."""
    px, py = point
    ring = polygon.get("coordinates", [[]])[0]
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _min_dist_to_polygon(point: tuple[float, float], polygon: dict) -> float:
    """Minimum distance from a point to any edge of a GeoJSON Polygon."""
    px, py = point
    ring = polygon.get("coordinates", [[]])[0]
    if not ring:
        return float("inf")
    min_d = float("inf")
    n = len(ring)
    for i in range(n):
        ax, ay = ring[i][0], ring[i][1]
        bx, by = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            d = math.sqrt((px - ax) ** 2 + (py - ay) ** 2)
        else:
            t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
            nx, ny = ax + t * dx, ay + t * dy
            d = math.sqrt((px - nx) ** 2 + (py - ny) ** 2)
        if d < min_d:
            min_d = d
    return min_d
