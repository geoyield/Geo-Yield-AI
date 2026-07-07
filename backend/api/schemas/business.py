from datetime import date
from typing import Optional

from pydantic import BaseModel


class BusinessOut(BaseModel):
    id_global: str
    nom_local: Optional[str] = None
    nom_activitat: Optional[str] = None
    nom_sector_activitat: Optional[str] = None
    nom_grup_activitat: Optional[str] = None
    codi_barri: Optional[int] = None
    nom_barri: Optional[str] = None
    codi_districte: Optional[int] = None
    nom_districte: Optional[str] = None
    direccio_unica: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    sn_obert24h: Optional[bool] = None
    sn_oci_nocturn: Optional[bool] = None
    data_revisio: Optional[date] = None

    model_config = {"from_attributes": True}


class BusinessListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    results: list[BusinessOut]


class DensityBucket(BaseModel):
    group_key: str
    group_label: Optional[str] = None
    business_count: int


class DensityResponse(BaseModel):
    group_by: str
    activity_filter: Optional[str] = None
    buckets: list[DensityBucket]
