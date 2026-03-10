from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import assess, parcel, chat, feedback, admin

app = FastAPI(
    title="Cover Regulatory Engine",
    description="Home building regulatory engine for LA City residential parcels",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assess.router, prefix="/api/assess", tags=["Assessment"])
app.include_router(parcel.router, prefix="/api/parcel", tags=["Parcel"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["Feedback"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
