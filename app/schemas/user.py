from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from ..models import UserRole, EnterpriseType


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    real_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    role: UserRole
    enterprise_id: Optional[int] = None
    enforcement_team_id: Optional[int] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    username: str
    password: str


class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class EnterpriseBase(BaseModel):
    name: str
    type: EnterpriseType
    unified_social_credit_code: Optional[str] = None
    legal_person: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None


class EnterpriseCreate(EnterpriseBase):
    pass


class EnterpriseUpdate(BaseModel):
    name: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None


class EnterpriseResponse(EnterpriseBase):
    id: int
    credit_score: float
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EnforcementTeamBase(BaseModel):
    name: str
    team_code: str
    region: Optional[str] = None
    team_leader: Optional[str] = None
    contact_phone: Optional[str] = None
    workload_weight: float = 1.0


class EnforcementTeamCreate(EnforcementTeamBase):
    pass


class EnforcementTeamUpdate(BaseModel):
    name: Optional[str] = None
    region: Optional[str] = None
    team_leader: Optional[str] = None
    contact_phone: Optional[str] = None
    workload_weight: Optional[float] = None
    is_active: Optional[bool] = None


class EnforcementTeamResponse(EnforcementTeamBase):
    id: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
