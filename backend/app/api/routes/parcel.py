"""Parcel lookup API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.models.schemas import ParcelSchema
from app.services.parcel.service import ParcelService

router = APIRouter()


@router.get("/search", response_model=ParcelSchema)
async def search_parcel(
    address: str = Query(..., description="Street address to look up"),
    db: AsyncSession = Depends(get_session),
):
    """Geocode an address and retrieve parcel data."""
    service = ParcelService(db)
    parcel = await service.get_by_address(address)

    if not parcel:
        raise HTTPException(
            status_code=404,
            detail="Could not find parcel for this address. Ensure it is within the City of Los Angeles.",
        )

    return parcel


@router.get("/{apn}", response_model=ParcelSchema)
async def get_parcel(
    apn: str,
    db: AsyncSession = Depends(get_session),
):
    """Get cached parcel data by APN."""
    service = ParcelService(db)
    parcel = await service.get_by_apn(apn)

    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found in cache")

    return parcel
