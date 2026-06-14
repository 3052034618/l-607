from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db
from ..models import User, UserRole, Enterprise, EnforcementTeam
from ..schemas.user import (
    UserCreate, UserLogin, UserUpdate, UserResponse, Token,
    EnterpriseCreate, EnterpriseUpdate, EnterpriseResponse,
    EnforcementTeamCreate, EnforcementTeamUpdate, EnforcementTeamResponse,
)
from ..utils.security import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_roles,
)
from ..config import settings

router = APIRouter(prefix="/auth", tags=["认证与权限"])


@router.post("/register", response_model=UserResponse)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == user_in.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    if user_in.enterprise_id:
        ent = db.query(Enterprise).filter(Enterprise.id == user_in.enterprise_id).first()
        if not ent:
            raise HTTPException(status_code=400, detail="企业不存在")
    user = User(
        username=user_in.username,
        password_hash=hash_password(user_in.password),
        real_name=user_in.real_name,
        phone=user_in.phone,
        email=user_in.email,
        role=user_in.role,
        enterprise_id=user_in.enterprise_id,
        enforcement_team_id=user_in.enforcement_team_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=access_token, user=user)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserResponse)
def update_me(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    update_data = user_in.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password_hash"] = hash_password(update_data.pop("password"))
    for field, value in update_data.items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/users", response_model=List[UserResponse])
def list_users(
    role: Optional[UserRole] = None,
    enterprise_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if enterprise_id:
        query = query.filter(User.enterprise_id == enterprise_id)
    return query.offset(skip).limit(limit).all()


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    update_data = user_in.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password_hash"] = hash_password(update_data.pop("password"))
    for field, value in update_data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/enterprises", response_model=EnterpriseResponse)
def create_enterprise(
    ent_in: EnterpriseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    ent = Enterprise(**ent_in.model_dump())
    db.add(ent)
    db.commit()
    db.refresh(ent)
    return ent


@router.get("/enterprises", response_model=List[EnterpriseResponse])
def list_enterprises(
    type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Enterprise)
    if type:
        query = query.filter(Enterprise.type == type)
    return query.offset(skip).limit(limit).all()


@router.get("/enterprises/{ent_id}", response_model=EnterpriseResponse)
def get_enterprise(
    ent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ent = db.query(Enterprise).filter(Enterprise.id == ent_id).first()
    if not ent:
        raise HTTPException(status_code=404, detail="企业不存在")
    return ent


@router.put("/enterprises/{ent_id}", response_model=EnterpriseResponse)
def update_enterprise(
    ent_id: int,
    ent_in: EnterpriseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    ent = db.query(Enterprise).filter(Enterprise.id == ent_id).first()
    if not ent:
        raise HTTPException(status_code=404, detail="企业不存在")
    update_data = ent_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(ent, field, value)
    db.commit()
    db.refresh(ent)
    return ent


@router.post("/enforcement-teams", response_model=EnforcementTeamResponse)
def create_enforcement_team(
    team_in: EnforcementTeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    team = EnforcementTeam(**team_in.model_dump())
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.get("/enforcement-teams", response_model=List[EnforcementTeamResponse])
def list_enforcement_teams(
    region: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(EnforcementTeam)
    if region:
        query = query.filter(EnforcementTeam.region == region)
    return query.offset(skip).limit(limit).all()


@router.put("/enforcement-teams/{team_id}", response_model=EnforcementTeamResponse)
def update_enforcement_team(
    team_id: int,
    team_in: EnforcementTeamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    team = db.query(EnforcementTeam).filter(EnforcementTeam.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="执法队不存在")
    update_data = team_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(team, field, value)
    db.commit()
    db.refresh(team)
    return team
