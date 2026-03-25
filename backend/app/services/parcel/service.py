"""Parcel service: geocode → County parcel + ZIMAS zoning + LARIAC buildings → cache."""
import logging
import re
from datetime import timedelta

from app.models.database import _utcnow

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.database import Parcel, GeocodingCache
from app.models.schemas import ParcelSchema
from app.services.parcel.geocoder import geocode_address
from app.services.parcel.zimas import ZIMASClient
from app.services.parcel.lacounty import LACountyParcelClient, LACountyBuildingClient

_parse_address = LACountyParcelClient._parse_address

CACHE_TTL_DAYS = settings.parcel_cache_ttl_days

logger = logging.getLogger(__name__)


class ParcelService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.zimas = ZIMASClient()
        self.county_parcels = LACountyParcelClient()
        self.county_buildings = LACountyBuildingClient()

    @staticmethod
    def _normalize_address(address: str) -> str:
        """Normalize address for cache key: lowercase, collapse whitespace, strip trailing city/state."""
        key = address.strip().lower()
        key = re.sub(r"\s+", " ", key)
        key = re.sub(r",?\s*(los angeles|la),?\s*(ca|california)?\s*\d*$", "", key)
        return key

    async def _get_cached_geocode(self, address: str) -> dict | None:
        """Check geocoding cache for a previous result."""
        key = self._normalize_address(address)
        result = await self.db.execute(
            select(GeocodingCache).where(
                GeocodingCache.address_key == key,
                GeocodingCache.cached_at > _utcnow() - timedelta(days=30),
            ).limit(1)
        )
        cached = result.scalar_one_or_none()
        if cached:
            logger.info(f"Geocoding cache hit for '{key}'")
            return {
                "lat": cached.lat,
                "lng": cached.lng,
                "full_address": cached.full_address,
                "place_name": cached.place_name,
            }
        return None

    async def _cache_geocode(self, address: str, geocoded: dict) -> None:
        """Store geocoding result in cache."""
        key = self._normalize_address(address)
        existing = await self.db.execute(
            select(GeocodingCache).where(GeocodingCache.address_key == key)
        )
        entry = existing.scalar_one_or_none()
        if entry:
            entry.lat = geocoded["lat"]
            entry.lng = geocoded["lng"]
            entry.full_address = geocoded["full_address"]
            entry.place_name = geocoded.get("place_name", "")
            entry.cached_at = _utcnow()
        else:
            entry = GeocodingCache(
                address_key=key,
                lat=geocoded["lat"],
                lng=geocoded["lng"],
                full_address=geocoded["full_address"],
                place_name=geocoded.get("place_name", ""),
            )
            self.db.add(entry)
        await self.db.flush()

    async def get_by_address(
        self, address: str
    ) -> tuple[ParcelSchema | None, dict | None]:
        """Look up a parcel by street address.

        Returns (parcel, geocoded) where geocoded contains lat/lng/full_address
        even when the parcel itself is not found.
        """
        # Check geocoding cache first
        geocoded = await self._get_cached_geocode(address)
        if not geocoded:
            geocoded = await geocode_address(address)
            if not geocoded:
                logger.warning(f"Could not geocode address: {address}")
                return None, None
            await self._cache_geocode(address, geocoded)

        parcel = await self._get_or_fetch(
            lat=geocoded["lat"],
            lng=geocoded["lng"],
            address=geocoded["full_address"],
        )
        return parcel, geocoded

    async def get_nearby_addresses(
        self, lat: float, lng: float, searched_address: str = ""
    ) -> list[dict]:
        """Get situs addresses of parcels near a point (for map labels).

        Prioritises addresses on the same street as the searched address,
        then fills in cross-streets up to a reasonable limit.
        """
        import re
        buffer = 0.0008
        envelope = f"{lng - buffer},{lat - buffer},{lng + buffer},{lat + buffer}"
        out_fields = "SitusAddress,SitusFullAddress,CENTER_LAT,CENTER_LON"
        from app.services.parcel.lacounty import _query_layer, COUNTY_PARCEL_URL

        features = await _query_layer(COUNTY_PARCEL_URL, envelope, out_fields)
        if not features:
            return []

        street_match = re.search(r"\d+\s+(.+?)(?:,|\s+(?:LOS|LA)\b)", searched_address.upper())
        searched_street = street_match.group(1).strip() if street_match else ""

        same_street: list[dict] = []
        other: list[dict] = []

        for f in features:
            props = f.get("properties", {})
            addr = (props.get("SitusAddress") or "").strip()
            if not addr:
                continue
            geom = f.get("geometry")
            if geom and geom.get("type") == "Polygon" and geom.get("coordinates"):
                coords = geom["coordinates"][0]
                cx = sum(p[0] for p in coords) / len(coords)
                cy = sum(p[1] for p in coords) / len(coords)
            else:
                clat = props.get("CENTER_LAT")
                clng = props.get("CENTER_LON")
                if clat and clng:
                    cy, cx = float(clat), float(clng)
                else:
                    continue
            entry = {"address": addr, "lat": cy, "lng": cx}
            if searched_street and searched_street in addr.upper():
                same_street.append(entry)
            else:
                other.append(entry)

        return same_street + other[:8]

    async def get_by_apn(self, apn: str) -> ParcelSchema | None:
        """Look up a parcel by APN (check cache first)."""
        cached = await self._get_cached_by_apn(apn)
        if cached:
            return self._db_to_schema(cached)
        return None

    async def _get_or_fetch(
        self, lat: float, lng: float, address: str | None = None
    ) -> ParcelSchema | None:
        """Check cache, then fetch from County GIS + ZIMAS if needed."""
        cached = await self._find_cached_near(lat, lng)
        if cached:
            if not address or self._addresses_match(cached.address, address):
                logger.info(f"Cache hit for parcel {cached.apn}")
                return self._db_to_schema(cached)
            logger.info(f"Cache hit APN={cached.apn} but address mismatch, re-fetching")

        logger.info(f"Cache miss, fetching from County GIS + ZIMAS at ({lat}, {lng})")
        parcel_data = await self._fetch_full_parcel(lat, lng, address)
        if not parcel_data:
            logger.warning(f"No parcel data at ({lat}, {lng})")
            return None

        parcel = await self._cache_parcel(parcel_data)
        return self._db_to_schema(parcel)

    @staticmethod
    def _addresses_match(cached_addr: str | None, searched_addr: str) -> bool:
        """Check whether a cached parcel address matches the searched address."""
        if not cached_addr:
            return False
        c_num, c_street = _parse_address(cached_addr)
        s_num, s_street = _parse_address(searched_addr)
        if not c_num or not s_num:
            return False
        return c_num == s_num and c_street and s_street and c_street in s_street

    async def _fetch_full_parcel(
        self, lat: float, lng: float, address: str | None = None
    ) -> dict | None:
        """Assemble parcel data from three sources:
        1. LA County Parcels — boundary geometry, APN, lot area
        2. ZIMAS — zoning classification
        3. LARIAC — building footprints
        """
        zoning = await self.zimas.get_zoning(lat, lng)
        if not zoning:
            logger.warning(f"No ZIMAS zoning data at ({lat}, {lng})")
            return None

        county_parcel = await self.county_parcels.get_parcel(lat, lng, address)
        if not county_parcel:
            if address:
                logger.warning(f"No county parcel found for address '{address}'")
                return None
            logger.warning(f"No county parcel at ({lat}, {lng})")
            return None

        parcel_geom = county_parcel["geometry"]
        buildings = await self.county_buildings.get_buildings_for_parcel(parcel_geom, lat, lng)

        logger.info(
            f"County parcel: APN={county_parcel['apn']}, "
            f"area={county_parcel['lot_area_sqft']} sqft, "
            f"buildings={len(buildings)}"
        )

        apn = county_parcel["apn"] or f"unknown-{_utcnow().timestamp()}"

        return {
            "apn": apn,
            "address": county_parcel.get("situs_address") or address or "",
            "zone_code": zoning.get("zone_code", ""),
            "zone_class": zoning.get("zone_class", ""),
            "height_district": zoning.get("height_district"),
            "specific_plan": zoning.get("specific_plan"),
            "overlay_zones": [zoning["overlay"]] if zoning.get("overlay") else [],
            "lot_area_sqft": county_parcel["lot_area_sqft"],
            "lot_width_ft": county_parcel["lot_width_ft"],
            "lot_depth_ft": county_parcel["lot_depth_ft"],
            "geometry": parcel_geom,
            "building_footprints": buildings,
            "centroid_lat": lat,
            "centroid_lng": lng,
            "community_plan_area": zoning.get("community_plan_area"),
        }

    async def _find_cached_near(self, lat: float, lng: float) -> Parcel | None:
        """Find a cached parcel near the given coordinates that isn't expired."""
        result = await self.db.execute(
            select(Parcel).where(
                Parcel.centroid_lat.between(lat - 0.0005, lat + 0.0005),
                Parcel.centroid_lng.between(lng - 0.0005, lng + 0.0005),
                Parcel.cached_at > _utcnow() - timedelta(days=CACHE_TTL_DAYS),
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_cached_by_apn(self, apn: str) -> Parcel | None:
        result = await self.db.execute(
            select(Parcel).where(
                Parcel.apn == apn,
                Parcel.cached_at > _utcnow() - timedelta(days=CACHE_TTL_DAYS),
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def _cache_parcel(self, data: dict) -> Parcel:
        """Store parcel data in the cache."""
        apn = data.get("apn", f"unknown-{_utcnow().timestamp()}")

        existing = await self.db.execute(
            select(Parcel).where(Parcel.apn == apn)
        )
        parcel = existing.scalar_one_or_none()

        if parcel:
            parcel.address = data.get("address")
            parcel.zone_code = data.get("zone_code", "")
            parcel.zone_class = data.get("zone_class", "")
            parcel.height_district = data.get("height_district")
            parcel.specific_plan = data.get("specific_plan")
            parcel.overlay_zones = data.get("overlay_zones", [])
            parcel.lot_area_sqft = data.get("lot_area_sqft")
            parcel.lot_width_ft = data.get("lot_width_ft")
            parcel.lot_depth_ft = data.get("lot_depth_ft")
            parcel.centroid_lat = data.get("centroid_lat")
            parcel.centroid_lng = data.get("centroid_lng")
            parcel.community_plan_area = data.get("community_plan_area")
            parcel.geometry = data.get("geometry")
            parcel.building_footprints = data.get("building_footprints")
            parcel.cached_at = _utcnow()
        else:
            parcel = Parcel(
                apn=apn,
                address=data.get("address"),
                zone_code=data.get("zone_code", ""),
                zone_class=data.get("zone_class", ""),
                height_district=data.get("height_district"),
                specific_plan=data.get("specific_plan"),
                overlay_zones=data.get("overlay_zones", []),
                lot_area_sqft=data.get("lot_area_sqft"),
                lot_width_ft=data.get("lot_width_ft"),
                lot_depth_ft=data.get("lot_depth_ft"),
                centroid_lat=data.get("centroid_lat"),
                centroid_lng=data.get("centroid_lng"),
                community_plan_area=data.get("community_plan_area"),
                geometry=data.get("geometry"),
                building_footprints=data.get("building_footprints"),
            )
            self.db.add(parcel)

        await self.db.flush()
        return parcel

    def _db_to_schema(self, parcel: Parcel) -> ParcelSchema:
        return ParcelSchema(
            id=parcel.id,
            apn=parcel.apn,
            address=parcel.address,
            zone_code=parcel.zone_code,
            zone_class=parcel.zone_class,
            height_district=parcel.height_district,
            specific_plan=parcel.specific_plan,
            overlay_zones=parcel.overlay_zones or [],
            lot_area_sqft=parcel.lot_area_sqft,
            lot_width_ft=parcel.lot_width_ft,
            lot_depth_ft=parcel.lot_depth_ft,
            centroid_lat=parcel.centroid_lat,
            centroid_lng=parcel.centroid_lng,
            community_plan_area=parcel.community_plan_area,
            geometry_geojson=parcel.geometry,
            building_footprints_geojson=parcel.building_footprints,
        )
