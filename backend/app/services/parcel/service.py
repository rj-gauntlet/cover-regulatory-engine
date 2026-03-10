"""Parcel service: geocode → ZIMAS lookup → cache."""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Parcel
from app.models.schemas import ParcelSchema
from app.services.parcel.geocoder import geocode_address
from app.services.parcel.zimas import ZIMASClient

logger = logging.getLogger(__name__)


class ParcelService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.zimas = ZIMASClient()

    async def get_by_address(self, address: str) -> ParcelSchema | None:
        """Look up a parcel by street address."""
        geocoded = await geocode_address(address)
        if not geocoded:
            logger.warning(f"Could not geocode address: {address}")
            return None

        return await self._get_or_fetch(
            lat=geocoded["lat"],
            lng=geocoded["lng"],
            address=geocoded["full_address"],
        )

    async def get_by_apn(self, apn: str) -> ParcelSchema | None:
        """Look up a parcel by APN (check cache first)."""
        cached = await self._get_cached_by_apn(apn)
        if cached:
            return self._db_to_schema(cached)
        return None

    async def _get_or_fetch(
        self, lat: float, lng: float, address: str | None = None
    ) -> ParcelSchema | None:
        """Check cache, then fetch from ZIMAS if needed."""
        cached = await self._find_cached_near(lat, lng)
        if cached:
            logger.info(f"Cache hit for parcel {cached.apn}")
            return self._db_to_schema(cached)

        logger.info(f"Cache miss, fetching from ZIMAS at ({lat}, {lng})")
        zimas_data = await self.zimas.get_full_parcel_data(lat, lng)
        if not zimas_data:
            logger.warning(f"No ZIMAS data at ({lat}, {lng})")
            return None

        if address:
            zimas_data["address"] = address

        parcel = await self._cache_parcel(zimas_data)
        return self._db_to_schema(parcel)

    async def _find_cached_near(self, lat: float, lng: float) -> Parcel | None:
        """Find a cached parcel near the given coordinates that isn't expired."""
        result = await self.db.execute(
            select(Parcel).where(
                Parcel.centroid_lat.between(lat - 0.0005, lat + 0.0005),
                Parcel.centroid_lng.between(lng - 0.0005, lng + 0.0005),
                Parcel.cached_at > datetime.utcnow() - timedelta(days=30),
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_cached_by_apn(self, apn: str) -> Parcel | None:
        result = await self.db.execute(
            select(Parcel).where(
                Parcel.apn == apn,
                Parcel.cached_at > datetime.utcnow() - timedelta(days=30),
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def _cache_parcel(self, data: dict) -> Parcel:
        """Store parcel data in the cache."""
        apn = data.get("apn", f"unknown-{datetime.utcnow().timestamp()}")

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
            parcel.cached_at = datetime.utcnow()
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
        )
