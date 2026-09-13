from app.admin import router as admin_router
from app.main import app


app.include_router(admin_router)
