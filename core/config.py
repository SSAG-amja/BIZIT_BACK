from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()
MONGO_URL = os.getenv("MONGO_URL")
KAKAO_API_KEY = os.getenv("KAKAO_API")
DATA_GO_KR_API_KEY = os.getenv("DATA_GO_KR_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

#await 붙여야함- 비동기 실행
client = AsyncIOMotorClient(MONGO_URL)

db = client["BIZIT_DB"]

#collection 생성
#나중에 쓸때는 await users_collection.function(...)
user_collection = db["users"]
store_collection = db['storeInfo']
solution_collection = db['solutionInfo']
surrounding_collection = db['surroundingInfo']