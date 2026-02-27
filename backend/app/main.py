import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import auth, sessions, monitoring, admin, users
from app.config import settings
from app.core.database import init_db
from app.core.exceptions import AppException

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up KiroCLI Platform backend...")
    init_db()
    logger.info("Database initialized")

    from app.core.database import SessionLocal
    from app.services.session_service import SessionService

    db = SessionLocal()
    try:
        service = SessionService(db)
        await service.restore_sessions_on_startup()
        logger.info("Session state restored")

        # 初始化 Nginx IP 白名单配置
        from app.services.ip_whitelist_service import IPWhitelistService
        try:
            IPWhitelistService().init_nginx_conf(db)
        except Exception as e:
            logger.warning(f"IP whitelist Nginx config init skipped: {e}")

        # 初始化 Token 黑名单内存缓存
        from app.services.token_service import token_service
        try:
            token_service.init_blacklist_cache(db)
        except Exception as e:
            logger.warning(f"Token blacklist cache init skipped: {e}")

        # 检测 SECRET_KEY 是否轮换
        from app.services.secrets_manager import secrets_loader
        try:
            secrets_loader.check_key_rotation(db, settings.SECRET_KEY)
        except Exception as e:
            logger.warning(f"Secret key rotation check skipped: {e}")
    finally:
        db.close()

    async def cleanup_task():
        while True:
            await asyncio.sleep(settings.SESSION_CLEANUP_INTERVAL_MINUTES * 60)
            db = SessionLocal()
            try:
                service = SessionService(db)
                await service.cleanup_idle_sessions()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
            finally:
                db.close()

    async def token_cleanup_task():
        """每 24 小时清理过期 Token 记录"""
        while True:
            await asyncio.sleep(24 * 3600)
            db = SessionLocal()
            try:
                from app.services.token_service import token_service
                token_service.cleanup_expired(db)
            except Exception as e:
                logger.error(f"Token cleanup error: {e}")
            finally:
                db.close()

    task = asyncio.create_task(cleanup_task())
    token_task = asyncio.create_task(token_cleanup_task())
    yield
    task.cancel()
    token_task.cancel()
    logger.info("Shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {"code": exc.code, "message": exc.message},
        },
    )


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
app.include_router(monitoring.router, prefix="/api/v1/monitoring", tags=["monitoring"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])


@app.get("/api/v1/health")
async def health_check():
    from app.core.database import SessionLocal
    db_status = "connected"
    try:
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
    except Exception:
        db_status = "disconnected"

    from datetime import datetime
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "database": db_status,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }
