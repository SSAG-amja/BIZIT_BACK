from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, BackgroundTasks
from core.security import get_current_user
# ▼▼▼ [수정 1] solution_collection, db 추가 import ▼▼▼
from core.config import store_collection, surrounding_collection, code_mapping_collection, solution_collection, db
from core.config import KAKAO_API_KEY, DATA_GO_KR_API_KEY
from schemas.storeInfo import StoreInfoSchema
from schemas.aroundLocInfo import SurroundingSchema, Coordinate
from datetime import datetime
import csv
import io
from api.analysis import run_analysis
from api.solution import run_sol
import requests
import httpx
import asyncio

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
    
    match_first = result['documents'][0]
    lat = float(match_first['y'])
    lng = float(match_first['x'])

    if match_first.get('address'):
        addr_info = match_first['address']
        raw_code = addr_info.get('h_code', '') 
        admin_code = raw_code[:-2] if len(raw_code) >= 2 else raw_code
        dong_name = addr_info.get('region_3depth_name', '')
    else:
        admin_code = ""
        dong_name = ""

    return lat, lng, admin_code, dong_name


# =================================================================
# 공공데이터 상권 정보 가져오기 (비동기 병렬 처리)
# =================================================================
async def fetch_store_data_go_kr(lat: float, lng: float, radius: int) -> list[Coordinate]:
    url = "http://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius"
    
    from urllib.parse import unquote
    service_key = unquote(DATA_GO_KR_API_KEY) 

    params = {
        "serviceKey": service_key,
        "pageNo": 1,
        "numOfRows": 500,
        "radius": radius,
        "cx": lng,   # 경도
        "cy": lat,   # 위도
        "indsSclsCd": "S21105",
        "type": "json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=15.0)
            
            if response.status_code != 200:
                print(f"API Error ({radius}m): {response.status_code} - {response.text}")
                return []

            content_type = response.headers.get("Content-Type", "")
            if "xml" in content_type or response.text.strip().startswith("<"):
                print(f"API Error ({radius}m) - XML Response received (Check ServiceKey)")
                return []

            data = response.json()
            body = data.get("body")
            if not body:
                return []

            items = body.get("items")
            if not items:
                return []

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
    task_500 = fetch_store_data_go_kr(lat, lng, 500)
    task_1000 = fetch_store_data_go_kr(lat, lng, 1000)
    task_1500 = fetch_store_data_go_kr(lat, lng, 1500)
    task_2000 = fetch_store_data_go_kr(lat, lng, 2000)

    results = await asyncio.gather(task_500, task_1000, task_1500, task_2000)

    return SurroundingSchema(
        rad_500=results[0],
        rad_1000=results[1],
        rad_1500=results[2],
        rad_2000=results[3]
    )    


# =================================================================
# 1. CSV 파싱 API
# =================================================================
@router.post("/parse-csv")
async def parse_store_csv(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="CSV 파일만 업로드 가능합니다.")

    try:
        content = await file.read()
        try:
            decoded = content.decode('utf-8')
        except UnicodeDecodeError:
            decoded = content.decode('euc-kr')

        csv_reader = csv.DictReader(io.StringIO(decoded))
        extracted_sales = []
        
        for row in csv_reader:
            row = {k.strip(): v.strip() for k, v in row.items() if k}
            if '년월' in row and '매출' in row:
                try:
                    revenue = int(row.get('매출', '0').replace(',', ''))
                    profit = int(row.get('순수익', '0').replace(',', ''))
                    extracted_sales.append({
                        "ym": row['년월'],
                        "revenue": revenue,
                        "profit": profit,
                        "details": None
                    })
                except ValueError:
                    continue

        return {
            "message": "CSV parsed successfully",
            "suggested_data": {"sales_logs": extracted_sales}
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV Parsing Error: {str(e)}")


# =================================================================
# 2. 매장 정보 저장/수정 API (Submit)
# =================================================================
@router.post("/submit")
async def submit_store_info(
    store_data: StoreInfoSchema,
    background_tasks: BackgroundTasks,
    current_user: str = Depends(get_current_user)
):
    # 0. 업종 매핑
    if store_data.sector_name:
        mapping_doc = await code_mapping_collection.find_one(
            {"ksic_list.name": store_data.sector_name}
        )
        if mapping_doc:
            store_data.sector_code_cs = mapping_doc.get("code_cs", "")
            store_data.sector_code_low = mapping_doc.get("so_code", "")
            ksic_list = mapping_doc.get("ksic_list", [])
            for ksic in ksic_list:
                if ksic.get("name") == store_data.sector_name:
                    store_data.sector_code = ksic.get("code", "")
                    break
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"지원하지 않는 업종명입니다: {store_data.sector_name}"
            )
    
    # 1. 좌표 변환
    address = store_data.location.address
    lat, lng, admin_code, dong_name = await get_coordinates(address)

    if lat is None:
        raise HTTPException(status_code=400, detail="유효하지 않은 주소입니다.")

    store_data.location.lat = lat
    store_data.location.lng = lng
    store_data.location.admin_code = admin_code
    store_data.location.admin_dong_name = dong_name

    # 2. 주변 상권 정보
    surrounding_data = await get_surrounding_commercial_areas(lat, lng)

    # 3. DB 저장 (Store Info)
    store_dict = store_data.dict()
    store_dict["user_id"] = current_user  
    store_dict["updated_at"] = datetime.now()

    result = await store_collection.update_one(
        {"user_id": current_user},    
        {"$set": store_dict},         
        upsert=True                   
    )

    # 4. DB 저장 (Surrounding Info)
    surrounding_dict = surrounding_data.dict()
    surrounding_dict["user_id"] = current_user
    surrounding_dict["updated_at"] = datetime.now()

    await surrounding_collection.update_one(
        {"user_id": current_user},
        {"$set": surrounding_dict},
        upsert=True
    )

    # 5. 분석 실행
    run_analysis(current_user) # 동기 실행
    background_tasks.add_task(run_sol, current_user) # 비동기 백그라운드 실행

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
        {"_id": 0}
    )

    if not store:
        raise HTTPException(status_code=404, detail="등록된 매장 정보가 없습니다.")

    return store


# =================================================================
# 4. [NEW] 대시보드 데이터 통합 조회 API (Dashboard)
# =================================================================
# ▼▼▼ [수정 2] 대시보드 API 추가 ▼▼▼
@router.get("/dashboard")
async def get_dashboard_data(
    current_user: str = Depends(get_current_user)
):
    """
    로그인 직후 또는 정보 입력 후 프론트엔드가 호출하는 API
    """
    
    # 1. 매장 정보 존재 여부 확인
    store = await store_collection.find_one({"user_id": current_user})
    
    if not store:
        return {
            "hasData": False,
            "message": "매장 정보가 없습니다. 정보를 먼저 등록해주세요.",
            "data": None
        }

    # 2. 분석 정보 (AnalysisInfo) 조회
    # analysis.py는 db['analysisInfo']에 저장하도록 수정했으므로 여기서 가져옵니다.
    analysis = await db.analysisInfo.find_one({"user_email": current_user})
    
    # 3. 주변 상권 정보 (SurroundingInfo) 조회
    surrounding = await surrounding_collection.find_one({"user_id": current_user})

    # 4. 솔루션 정보 (SolutionInfo) 조회 - 최신순 정렬
    solutions_cursor = solution_collection.find({"user_id": current_user}).sort("created_at", -1)
    solutions_list = await solutions_cursor.to_list(length=20) 

    # 분석 데이터가 없으면 '분석 중' 상태로 간주 가능
    if not analysis:
        return {
            "hasData": True,
            "isAnalyzing": True,
            "message": "분석 데이터가 아직 생성되지 않았습니다.",
            "data": None
        }

    # === 데이터 가공 ===
    
    # [12] 주변 상권 좌표 추출
    surrounding_coords = []
    if surrounding:
        for rad_key in ["rad_500", "rad_1000", "rad_1500", "rad_2000"]:
            items = surrounding.get(rad_key, [])
            for item in items:
                if "lat" in item and "lng" in item:
                    surrounding_coords.append({
                        "lat": item["lat"],
                        "lng": item["lng"]
                    })

    # [13, 14] 솔루션 추출
    solution_titles = [sol.get("title", "") for sol in solutions_list]
    solution_full = [
        {"title": sol.get("title", ""), "solution": sol.get("solution", "")} 
        for sol in solutions_list
    ]

    dashboard_data = {
        # [1] 등급 라벨
        "percentile_label": analysis.get("percentile", {}).get("label", ""),
        # [2] 내 최신 매출
        "my_latest_revenue": analysis.get("latest_comparison", {}).get("my_store", 0),
        # [3, 4] 전월 대비 증감율
        "mom_growth_rate": analysis.get("mom_growth", {}).get("value", 0.0),
        # [추가] 증감 방향
        "mom_direction": analysis.get("mom_growth", {}).get("direction", "FLAT"),
        # [5] 전월 대비 차액
        "mom_diff_amount": analysis.get("mom_growth", {}).get("diff_amount", 0),
        # [6] 월별 추세 (x축)
        "trend_months": analysis.get("monthly_trend", {}).get("months", []),
        # [7] 월별 추세 (내 매출)
        "trend_my_store": analysis.get("monthly_trend", {}).get("my_store", []),
        # [8] 월별 추세 (동 평균)
        "trend_industry_dong": analysis.get("monthly_trend", {}).get("industry_avg_dong", []),
        # [9] 최신 비교 (내 매출)
        "latest_my_store": analysis.get("latest_comparison", {}).get("my_store", 0),
        # [10] 최신 비교 (동 평균)
        "latest_industry_dong": analysis.get("latest_comparison", {}).get("industry_avg_dong", 0),
        # [11] 최신 비교 (시 전체 평균)
        "latest_industry_all": analysis.get("latest_comparison", {}).get("industry_avg_all", 0),
        # [12] 주변 상권 좌표
        "surrounding_coordinates": surrounding_coords,
        # [13] 솔루션 제목
        "solution_titles": solution_titles,
        # [14] 솔루션 전체
        "solutions": solution_full
    }

    return {
        "hasData": True,
        "data": dashboard_data
    }