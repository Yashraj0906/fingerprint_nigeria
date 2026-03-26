from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from app.db.database import init_db
from app.api import capture, enroll, verify, session, audit, ui

app = FastAPI(
    title="Fingerprint SDK Backend",
    description="Quality assessment, liveness detection, template generation and matching.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


app.include_router(session.router, prefix="/api", tags=["Session"])
app.include_router(capture.router, prefix="/api", tags=["Capture"])
app.include_router(enroll.router,  prefix="/api", tags=["Enroll"])
app.include_router(verify.router,  prefix="/api", tags=["Verify"])
app.include_router(audit.router,   prefix="/api", tags=["Audit"])


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
def testing_ui():
    return HTMLResponse(content=ui._HTML)
