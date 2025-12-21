from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from core.security import get_current_user
from core.config import store_collection
from core.config import KAKAO_API_KEY, DATA_GO_KR_API_KEY # 공공데이터 API 키 추가 필요
from schemas.storeInfo import StoreInfoSchema
from schemas.aroundLocInfo import SurroundingSchema, Coordinate # 제공해주신 스키마 임포트
from datetime import datetime
import csv
import io
import requests # Kakao용 (기존 유지)
import httpx    # 공공데이터용 (신규 추가, 비동기 요청용)
import asyncio  # 병렬 처리를 위해 추가

router = APIRouter(prefix="/api/store", tags=["Store"])

async def get_coordinates(address: str):
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"} 
    url = 'https://dapi.kakao.com/v2/local/search/address.json'
    params = {'query': address}

    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        print(f"Kakao API Error: {response.status_code}")
        print(response.text)
        raise HTTPException(status_code=500, detail="Kakao API 호출 실패")

    result = response.json()

    if not result.get('documents'):
        raise HTTPException(status_code=404, detail="해당 주소를 찾을 수 없습니다.")

    # 첫 번째 검색 결과 가져오기
    match_first = result['documents'][0]
    
    # 좌표 추출
    lat = float(match_first['y'])
    lng = float(match_first['x'])

    # 추가 정보 추출 (행정코드, 동 이름)
    # address 객체가 있는 경우(지번 주소 정보)
    if match_first.get('address'):
        addr_info = match_first['address']
        # h_code: 행정동 코드 / b_code: 법정동 코드 (필요에 따라 변경 가능)
        admin_code = addr_info.get('h_code', '') 
        dong_name = addr_info.get('region_3depth_name', '') # 예: 효자동
    else:
        # 도로명 주소만 있고 지번 매핑이 안 된 희귀 케이스 대비
        admin_code = ""
        dong_name = ""

    # 이제 4개의 값을 순서대로 반환합니다.
    return lat, lng, admin_code, dong_name


# =================================================================
# 공공데이터 상권 정보 가져오기 (비동기 병렬 처리)
# =================================================================
async def fetch_store_data_go_kr(lat: float, lng: float, radius: int) -> list[Coordinate]:
    url = "http://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius"
    
    from urllib.parse import unquote
    service_key = unquote(DATA_GO_KR_API_KEY) 

    params = {
        "serviceKey": service_key, # 디코딩된 키 입력
        "pageNo": 1,
        "numOfRows": 500,
        "radius": radius,
        "cx": lng,   # 경도 (Longitude)
        "cy": lat,   # 위도 (Latitude)
        "indsSclsCd": "S21105",
        "type": "json" # json 응답 요청
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=15.0)
            
            if response.status_code != 200:
                print(f"API Error ({radius}m): {response.status_code} - {response.text}")
                return []

            content_type = response.headers.get("Content-Type", "")
            if "xml" in content_type or response.text.strip().startswith("<"):
                print(f"API Error ({radius}m) - XML Response received (Check ServiceKey): {response.text[:200]}")
                return []

            data = response.json()
            
            body = data.get("body")
            if not body:
                print(f"API Error ({radius}m) - No 'body' in response: {data}")
                return []

            items = body.get("items")
            
            # items가 None이거나 비어있는 경우 처리
            if not items:
                return []

            # 결과가 리스트가 아니라 단일 딕셔너리인 경우 리스트로 감싸기
            if isinstance(items, dict):
                items = [items]
            
            coords = []
            for item in items:
                try:
                    c_lat = float(item.get("lat"))
                    c_lon = float(item.get("lon"))
                    coords.append(Coordinate(lat=c_lat, lng=c_lon))
                except (ValueError, TypeError):
                    continue
            
            return coords

        except Exception as e:
            print(f"Public Data API Exception ({radius}m): {str(e)}")
            return []

async def get_surrounding_commercial_areas(lat: float, lng: float) -> SurroundingSchema:
    """
    500m, 1000m, 1500m, 2000m 반경의 데이터 병렬 처리
    """
    # 4개의 비동기 작업을 생성
    task_500 = fetch_store_data_go_kr(lat, lng, 500)
    task_1000 = fetch_store_data_go_kr(lat, lng, 1000)
    task_1500 = fetch_store_data_go_kr(lat, lng, 1500)
    task_2000 = fetch_store_data_go_kr(lat, lng, 2000)

    # 병렬 실행 및 결과 대기 (asyncio.gather 사용)
    results = await asyncio.gather(task_500, task_1000, task_1500, task_2000)

    return SurroundingSchema(
        rad_500=results[0],
        rad_1000=results[1],
        rad_1500=results[2],
        rad_2000=results[3]
    )     


# =================================================================
# 1. CSV 파싱 API (매출 데이터 자동 채우기용)
# =================================================================
@router.post("/parse-csv")
async def parse_store_csv(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)
):
    """
    업로드된 CSV 파일을 분석하여 '매출 로그(sales_logs)' 리스트를 반환합니다.
    프론트엔드는 이 데이터를 받아 사용자가 수정할 수 있게 화면에 뿌려줍니다.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="CSV 파일만 업로드 가능합니다.")

    try:
        content = await file.read()
        # 인코딩 처리 (utf-8 or euc-kr)
        try:
            decoded = content.decode('utf-8')
        except UnicodeDecodeError:
            decoded = content.decode('euc-kr')

        csv_reader = csv.DictReader(io.StringIO(decoded))
        
        extracted_sales = []
        
        # [CSV 매핑 로직]
        # 사용자의 CSV 헤더가 '년월', '매출', '순수익' 이라고 가정
        # 실제로는 다양한 헤더명을 처리하는 로직이 필요할 수 있습니다.
        for row in csv_reader:
            # 공백 제거 및 키 확인
            row = {k.strip(): v.strip() for k, v in row.items() if k}
            
            if '년월' in row and '매출' in row:
                try:
                    # 금액에서 쉼표(,) 제거 후 정수 변환
                    revenue = int(row.get('매출', '0').replace(',', ''))
                    profit = int(row.get('순수익', '0').replace(',', '')) # 없으면 0
                    
                    extracted_sales.append({
                        "ym": row['년월'],      # 예: "2024-01"
                        "revenue": revenue,
                        "profit": profit,
                        "details": None       # 상세 내용은 CSV에 없으면 None
                    })
                except ValueError:
                    continue # 숫자 변환 실패 시 해당 행 건너뜀

        return {
            "message": "CSV parsed successfully",
            "suggested_data": {
                "sales_logs": extracted_sales
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV Parsing Error: {str(e)}")


# =================================================================
# 2. 매장 정보 저장/수정 API (Submit)
# =================================================================
@router.post("/submit")
async def submit_store_info(
    store_data: StoreInfoSchema,
    current_user: str = Depends(get_current_user)
):
    # 1. 주소를 좌표로 변환
    address = store_data.location.address
    lat, lng, admin_code, dong_name = await get_coordinates(address)

    if lat is None:
        raise HTTPException(status_code=400, detail="유효하지 않은 주소입니다. 주소를 다시 확인해주세요.")

    # 2. 변환된 정보를 스키마 데이터에 주입
    store_data.location.lat = lat
    store_data.location.lng = lng

    if not store_data.location.admin_code:
        store_data.location.admin_code = admin_code
    if not store_data.location.admin_dong_name:
        store_data.location.admin_dong_name = dong_name

    surrounding_data = await get_surrounding_commercial_areas(lat, lng)

    store_dict = store_data.dict()
    store_dict["surrounding_info"] = surrounding_data.dict()
    store_dict["user_id"] = current_user  
    store_dict["updated_at"] = datetime.now()

    result = await store_collection.update_one(
        {"user_id": current_user},    
        {"$set": store_dict},         
        upsert=True                   
    )

    if result.upserted_id:
        msg = "매장 정보가 신규 등록되었습니다."
    else:
        msg = "매장 정보가 업데이트되었습니다."

    return {"message": msg, "user_id": current_user}


# =================================================================
# 3. 내 매장 정보 조회 API (Get)
# =================================================================
@router.get("/me")
async def get_my_store_info(
    current_user: str = Depends(get_current_user)
):
    store = await store_collection.find_one(
        {"user_id": current_user},
        {"_id": 0} # _id 필드는 제외하고 반환 (JSON 직렬화 문제 방지)
    )

    if not store:
        raise HTTPException(status_code=404, detail="등록된 매장 정보가 없습니다.")

    return store