# main.py
from fastapi import FastAPI
from api.user import router as user_router
from api.store import router as store_router
from api.analysis import router as analysis_router
from api.solution import router as solution_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="BIZIT",
    description="BIZIT",
)

#라우터 등록
app.include_router(user_router)
app.include_router(store_router)
app.include_router(analysis_router)
app.include_router(solution_router)

#프론트엔드 통신
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "hello world"}
