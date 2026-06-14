from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from .database import engine, Base
from .config import settings
from .api import api_router
from .services.report_service import generate_daily_report
from .services.notification_service import notification_manager

scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    scheduler.add_job(
        generate_daily_report,
        trigger="cron",
        hour=0,
        minute=0,
        id="daily_report_job",
        replace_existing=True,
    )
    scheduler.start()

    await notification_manager.startup()

    yield

    scheduler.shutdown()
    await notification_manager.shutdown()


app = FastAPI(
    title="城市建筑垃圾运输与处置智能调度系统 API",
    description="""
    城市建筑垃圾运输与处置智能调度系统后端API。
    包括渣土外运计划申报、最优消纳场推荐、电子准运证、车辆称重与轨迹、
    违规告警与执法工单、处罚管理、费用结算、运营报表、实时推送等功能。
    """,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["根目录"])
async def root():
    return {
        "message": "城市建筑垃圾运输与处置智能调度系统 API 运行中",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health", tags=["系统"])
async def health_check():
    return {"status": "healthy"}
