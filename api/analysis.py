from fastapi import APIRouter, Depends
from core.sercurity import get_current_user
from analysis.compare import run_analysis

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.post("/run")
def run(user_email: str = Depends(get_current_user)):
    result = run_analysis(user_email)
    return {
        "status": "success",
        "data": result
    }
