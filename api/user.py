from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIROuter(prefix="/api/user" tags=["User"])

class User():

#회원가입
@router.post("/signup")
def signup(user: User):
    return {"msg" : "success"}


@rouetr.post("/signin")
def signin(user: User):

@router.post("/signout")
def signout

@router.patch('/profile')
def profile():
