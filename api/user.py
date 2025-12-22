from fastapi import APIRouter, HTTPException
from core.config import user_collection
from schemas.user import UserSchema
from core.auth_utils import hash_password, verify_password, create_access_token
router = APIRouter(prefix="/api/user", tags=["User"])

# 1. 회원가입
@router.post("/signup")
async def signup(user: UserSchema):
    if not user.biz_name or not user.user_name:
         raise HTTPException(status_code=400, detail="사업자명과 이름은 필수입니다.")

    exist_user = await user_collection.find_one({"user_email": user.user_email})
    if exist_user:
        raise HTTPException(status_code=400, detail="Email already exists")

    user_data = user.dict()
    user_data["password"] = hash_password(user.password)

    await user_collection.insert_one(user_data)

    return {"msg": "Signup successful"}


# 2. 로그인
@router.post("/signin")
async def login(user: UserSchema):
    db_user = await user_collection.find_one({"user_email": user.user_email})

    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=400, detail="이메일 또는 비밀번호가 잘못되었습니다.")

    access_token = create_access_token(data={"sub": db_user["user_email"]})

    return {
        "msg": "로그인 성공",
        "access_token": access_token, # 이것이 실제 토큰값
        "token_type": "bearer",
        "user_name": db_user.get("user_name")
    }


@router.post("/signout")
async def signout():
    return {"msg": "Logged out successfully"}
