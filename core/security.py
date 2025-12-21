#인증, JWT 로직 등
# security.py
from fastapi import Depends, HTTPException, status, Header
from core.config import user_collection

async def get_current_user(token: str = Header(..., description="사용자 인증 토큰")):

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token header missing"
        )

    """
    token = username으로 취급.
    """

    user = await user_collection.find_one({"user_email": token})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token or user not found",
        )

    return token
