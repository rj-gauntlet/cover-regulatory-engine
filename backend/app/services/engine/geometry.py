"""Geometry engine: compute setback polygons and buildable area from parcel + rules."""
import logging
import json

from shapely.geometry import shape, mapping, Polygon, MultiPolygon
from shapely.ops import unary_union
from shapely import affinity

from app.models.schemas import ConstraintSchema, ParcelSchema

logger = logging.getLogger(__name__)

FEET_TO_DEGREES_LAT = 1.0 / 364000.0  # ~1 ft in degrees latitude
FEET_TO_DEGREES_LNG = 1.0 / 288200.0  # ~1 ft in degrees longitude (at LA latitude ~34°N)


class GeometryEngine:
    """Compute setback polygons and buildable envelope from parcel geometry + constraints."""

    def compute_setbacks(
        self,
        parcel: ParcelSchema,
        constraints: list[ConstraintSchema],
    ) -> dict:
        """Compute setback geometries and buildable area.

        Returns a dict with:
        - setback_lines: GeoJSON FeatureCollection of individual setback areas
        - buildable_area: GeoJSON of the buildable envelope
        - parcel_area_sqft: computed parcel area
        """
        if not parcel.geometry_geojson:
            return {"setback_lines": None, "buildable_area": None}

        try:
            parcel_geom = shape(parcel.geometry_geojson)
        except Exception as e:
            logger.error(f"Invalid parcel geometry: {e}")
            return {"setback_lines": None, "buildable_area": None}

        if not parcel_geom.is_valid:
            parcel_geom = parcel_geom.buffer(0)

        setback_values = self._extract_setback_values(constraints)
        setback_features = []
        buildable = parcel_geom

        front = setback_values.get("front_setback", 20.0)
        rear = setback_values.get("rear_setback", 15.0)
        side = setback_values.get("side_setback", 5.0)

        front_buffer = self._create_setback_buffer(parcel_geom, front, "front")
        if front_buffer and not front_buffer.is_empty:
            setback_features.append({
                "type": "Feature",
                "properties": {
                    "setback_type": "front",
                    "distance_ft": front,
                    "label": f"Front: {front}ft",
                },
                "geometry": mapping(front_buffer),
            })
            buildable = buildable.difference(front_buffer)

        rear_buffer = self._create_setback_buffer(parcel_geom, rear, "rear")
        if rear_buffer and not rear_buffer.is_empty:
            setback_features.append({
                "type": "Feature",
                "properties": {
                    "setback_type": "rear",
                    "distance_ft": rear,
                    "label": f"Rear: {rear}ft",
                },
                "geometry": mapping(rear_buffer),
            })
            buildable = buildable.difference(rear_buffer)

        side_buffer = self._create_setback_buffer(parcel_geom, side, "side")
        if side_buffer and not side_buffer.is_empty:
            setback_features.append({
                "type": "Feature",
                "properties": {
                    "setback_type": "side",
                    "distance_ft": side,
                    "label": f"Side: {side}ft",
                },
                "geometry": mapping(side_buffer),
            })
            buildable = buildable.difference(side_buffer)

        overall_buffer = self._buffer_inward(parcel_geom, front, rear, side)
        if overall_buffer and not overall_buffer.is_empty and overall_buffer.is_valid:
            buildable = overall_buffer

        buildable_geojson = None
        if buildable and not buildable.is_empty:
            buildable_geojson = {
                "type": "Feature",
                "properties": {
                    "type": "buildable_area",
                    "label": "Buildable Area",
                },
                "geometry": mapping(buildable),
            }

        return {
            "setback_lines": {
                "type": "FeatureCollection",
                "features": setback_features,
            },
            "buildable_area": buildable_geojson,
        }

    def _extract_setback_values(self, constraints: list[ConstraintSchema]) -> dict:
        """Pull setback distances from constraints."""
        values = {}
        for c in constraints:
            if c.category == "setback" and c.numeric_value is not None:
                values[c.parameter] = c.numeric_value
        return values

    def _create_setback_buffer(
        self, parcel: Polygon, distance_ft: float, side: str
    ) -> Polygon | None:
        """Create a setback buffer zone inside the parcel boundary.

        Uses a simplified approach: buffer the entire parcel inward,
        then take the difference to get the setback area.
        """
        buffer_deg = distance_ft * FEET_TO_DEGREES_LAT

        try:
            inner = parcel.buffer(-buffer_deg)
            if inner.is_empty:
                return parcel
            setback_area = parcel.difference(inner)
            return setback_area if not setback_area.is_empty else None
        except Exception as e:
            logger.error(f"Setback buffer computation failed for {side}: {e}")
            return None

    def _buffer_inward(
        self,
        parcel: Polygon,
        front_ft: float,
        rear_ft: float,
        side_ft: float,
    ) -> Polygon | None:
        """Compute buildable area by buffering inward with the largest setback."""
        max_setback = max(front_ft, rear_ft, side_ft)
        buffer_deg = max_setback * FEET_TO_DEGREES_LAT

        try:
            inner = parcel.buffer(-buffer_deg)
            if inner.is_empty or not inner.is_valid:
                min_setback = min(front_ft, rear_ft, side_ft)
                inner = parcel.buffer(-min_setback * FEET_TO_DEGREES_LAT)
            return inner if not inner.is_empty else None
        except Exception as e:
            logger.error(f"Inward buffer failed: {e}")
            return None
