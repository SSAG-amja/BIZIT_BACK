from datetime import datetime, timedelta
from jose import jwt
from core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
import bcrypt

def hash_password(password: str) -> str:
    # 1. 비밀번호를 바이트로 변환
    password_bytes = password.encode('utf-8')
    # 2. 솔트(Salt) 생성 및 해싱
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    # 3. DB 저장을 위해 문자열로 디코딩하여 반환
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # 비교를 위해 입력값과 DB 값을 바이트로 변환하여 검증
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)