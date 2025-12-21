from fastapi import APIRouter, HTTPException
from core.config import user_collection
from schemas.user import UserSchema

router = APIRouter(prefix="/api/user", tags=["User"])

# 1. 회원가입
@router.post("/signup")
async def signup(user: UserSchema):
    if not user.biz_name or not user.user_name:
         raise HTTPException(status_code=400, detail="사업자명과 이름은 필수입니다.")

    exist_user = await user_collection.find_one({"user_email": user.user_email})
    if exist_user:
        raise HTTPException(status_code=400, detail="Email already exists")

    await user_collection.insert_one(user.dict())

    return {"msg": "Signup successful"}


# 2. 로그인
@router.post("/signin")
async def login(user: UserSchema):
    db_user = await user_collection.find_one({"user_email": user.user_email})

    if not db_user or db_user["password"] != user.password:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    return {
        "msg": "Login successful",
        "token": user.user_email,
        "user_name": db_user.get("user_name")
    }


@router.post("/signout")
async def signout():
    return {"msg": "Logged out successfully"}
