from pydantic import BaseModel, Field, EmailStr
from typing import Optional

class UserSchema(BaseModel):
    user_email: EmailStr = Field(..., description="이메일")
    password: str = Field(..., description="비밀번호")
    biz_name: Optional[str] = Field(None, description="사업자명")
    user_name: Optional[str] = Field(None, description="사용자 실명")
