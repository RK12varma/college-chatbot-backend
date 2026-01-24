from fastapi import FastAPI
from app.routers import syllabus, upload

app = FastAPI()

app.include_router(syllabus.router)
app.include_router(upload.router)

@app.get("/")
def root():
    return {"message": "App running successfully"}
