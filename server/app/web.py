from app.dashboard import router as dashboard_router
from app.main import app


app.include_router(dashboard_router)
