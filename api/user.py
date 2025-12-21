from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.config import user_collection

router = APIRouter(prefix="/api/user", tags=["User"])

# 요청 데이터 형식
class User(BaseModel):
    user_email: str
    password: str
    biz_name: str
    user_name: str

@router.post("/signup")
async def signup(user: User):
    # username 중복 확인
    exist_user = await user_collection.find_one({"user_email": user.user_email})
    if exist_user:
        raise HTTPException(status_code=400, detail="email already exists")

    # 평문 저장 (테스트용)
    await user_collection.insert_one(
        {"user_email": user.user_email, "password": user.password,
         "biz_name": user.biz_name, "user_name": user.user_name}
    )

    return {"msg": "Signup successful"}


@router.post("/signin")
async def login(user: User):
    db_user = await user_collection.find_one({"user_email": user.user_email})

    # 사용자 존재 & 비밀번호 검증
    if not db_user or db_user["password"] != user.password:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    # 테스트용 로그인 → token 대신 username 반환
    return {"msg": "Login successful", "token": user.user_email}


@router.post("/signout")
async def signout():
    # 테스트용은 그냥 응답만
    return {"msg": "Logged out successfully"}
