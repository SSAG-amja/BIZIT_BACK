from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

MONGO_URL = os.getenv("MONGO_URL")

#await 붙여야함- 비동기 실행
client = AsyncIOMotorClient(MONGO_URL)

db = client["BIZIT_DB"]

#collection 생성
#나중에 쓸때는 await users_collection.function(...)
users_collection = db["users"]
