from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from ..models import VehicleStatus


class VehicleBase(BaseModel):
    plate_number: str
    vehicle_type: Optional[str] = None
    load_capacity: float
    container_volume: float
    enterprise_id: int
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    gps_device_id: Optional[str] = None
    has_sealing_device: bool = True


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    vehicle_type: Optional[str] = None
    load_capacity: Optional[float] = None
    container_volume: Optional[float] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    gps_device_id: Optional[str] = None
    has_sealing_device: Optional[bool] = None
    status: Optional[VehicleStatus] = None
    is_active: Optional[bool] = None


class VehicleResponse(VehicleBase):
    id: int
    status: VehicleStatus
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WeighingEntryCreate(BaseModel):
    permit_id: Optional[int] = None
    vehicle_id: int
    construction_site_id: int
    disposal_site_id: int
    tare_weight: float
    gross_weight: Optional[float] = None
    entry_images: Optional[List[str]] = None


class WeighingExitUpdate(BaseModel):
    gross_weight: float
    exit_images: Optional[List[str]] = None


class DisposalUnloadUpdate(BaseModel):
    disposal_entry_time: Optional[datetime] = None
    disposal_unload_time: Optional[datetime] = None


class WeighingRecordResponse(BaseModel):
    id: int
    record_code: Optional[str] = None
    permit_id: Optional[int] = None
    vehicle_id: int
    construction_site_id: int
    disposal_site_id: int
    gross_weight: Optional[float] = None
    tare_weight: Optional[float] = None
    net_weight: Optional[float] = None
    volume: Optional[float] = None
    entry_weight_time: Optional[datetime] = None
    exit_weight_time: Optional[datetime] = None
    disposal_entry_time: Optional[datetime] = None
    disposal_unload_time: Optional[datetime] = None
    is_overloaded: bool
    overload_percentage: float
    is_sealed: bool
    status: str
    model_config = ConfigDict(from_attributes=True)


class TrackPointCreate(BaseModel):
    vehicle_id: int
    permit_id: Optional[int] = None
    latitude: float
    longitude: float
    speed: Optional[float] = None
    heading: Optional[float] = None
    gps_signal: Optional[float] = None


class TrackPointResponse(BaseModel):
    id: int
    vehicle_id: int
    permit_id: Optional[int] = None
    latitude: float
    longitude: float
    speed: Optional[float] = None
    heading: Optional[float] = None
    timestamp: datetime
    is_off_route: bool
    off_route_distance: float
    model_config = ConfigDict(from_attributes=True)
