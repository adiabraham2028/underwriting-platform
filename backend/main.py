import uuid
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from config import settings
from database import async_session_maker, engine, Base
from models.user import User
from models.template import Template
from models.deal import Deal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_migrations():
    """Run alembic migrations on startup."""
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd="/app",
    )
    if result.returncode != 0:
        logger.error(f"Migration failed:\n{result.stderr}")
        raise RuntimeError(f"Alembic migration failed: {result.stderr}")
    logger.info("Migrations applied successfully")


async def seed_admin():
    """Create admin user if not exists."""
    from routers.auth import hash_password

    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == settings.ADMIN_EMAIL))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(
                id=uuid.uuid4(),
                email=settings.ADMIN_EMAIL,
                full_name="Administrator",
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
            session.add(admin)
            await session.commit()
            logger.info(f"Admin user created: {settings.ADMIN_EMAIL}")
        else:
            logger.info("Admin user already exists")
        return admin


async def seed_default_template(admin_id: uuid.UUID):
    """Create default Excel template if none exists."""
    from services.excel_exporter import create_default_template
    from services.model_populator import DEFAULT_CELL_MAPPING

    async with async_session_maker() as session:
        result = await session.execute(select(Template).limit(1))
        existing = result.scalar_one_or_none()
        if not existing:
            template_bytes = create_default_template()
            template = Template(
                id=uuid.uuid4(),
                name="Default Underwriting Model",
                version=1,
                is_default=True,
                file_data=template_bytes,
                cell_mapping=DEFAULT_CELL_MAPPING,
                created_at=datetime.now(timezone.utc),
                created_by=admin_id,
                is_active=True,
            )
            session.add(template)
            await session.commit()
            logger.info("Default template created")
        else:
            logger.info("Template already exists")


async def assign_default_template_to_existing_deals():
    """One-time migration: assign the default template to any deals that have none."""
    from sqlalchemy import update as sa_update
    async with async_session_maker() as session:
        result = await session.execute(select(Template).where(Template.is_default == True).limit(1))
        default_tmpl = result.scalar_one_or_none()
        if not default_tmpl:
            return
        await session.execute(
            sa_update(Deal)
            .where(Deal.active_template_id == None)
            .values(active_template_id=default_tmpl.id)
        )
        await session.commit()
        logger.info(f"Auto-assigned default template to deals missing one")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await run_migrations()
    admin = await seed_admin()
    await seed_default_template(admin.id)
    await assign_default_template_to_existing_deals()
    if settings.SEED_DEMO_DATA:
        from seed_demo_data import seed_demo_data
        await seed_demo_data()
    logger.info("Application startup complete")
    yield
    # Shutdown
    await engine.dispose()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Underwriting Platform API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Register routers
from routers.auth import router as auth_router
from routers.deals import router as deals_router
from routers.documents import router as documents_router
from routers.templates import router as templates_router
from routers.models import router as models_router
from routers.ai import router as ai_router

app.include_router(auth_router)
app.include_router(deals_router)
app.include_router(documents_router)
app.include_router(templates_router)
app.include_router(models_router)
app.include_router(ai_router)

from routers.classification import router as classification_router
from routers.client_templates import router as client_templates_router
from routers.knowledge_base import router as knowledge_base_router
from routers.expense_comps import router as expense_comps_router

app.include_router(classification_router)
app.include_router(client_templates_router)
app.include_router(knowledge_base_router)
app.include_router(expense_comps_router)
