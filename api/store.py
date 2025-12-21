from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, BackgroundTasks
from core.sercurity import get_current_user
from core.config import store_collection
from schemas.sotreInfo import StoreInfoSchema
from datetime import datetime
import csv
import io
from analysis.compare import run_analysis

router = APIRouter(prefix="/api/store", tags=["Store"])

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
    """
    사용자가 입력한(또는 CSV로 채워진) 최종 데이터를 에 저장합니다.
    이미 등록된 매장이 있다면 업데이트(덮어쓰기) 합니다.
    """
    
    # 1. Pydantic 모델을 dict로 변환
    store_dict = store_data.dict()
    
    # 2. 시스템 관리 필드 추가
    store_dict["user_id"] = current_user  # 토큰에서 추출한 사용자 ID
    store_dict["updated_at"] = datetime.now()

    # 3. DB 저장 (Upsert: 없으면 생성, 있으면 수정)
    # user_id를 기준으로 매장을 찾습니다.
    result = await store_collection.update_one(
        {"user_id": current_user},    # 검색 조건
        {"$set": store_dict},         # 변경할 내용 ($set을 써야 전체 필드 업데이트)
        upsert=True                   # 없으면 insert_one 수행
    )

    run_analysis(current_user)

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
    """
    로그인한 사용자의 저장된 매장 정보를 불러옵니다.
    """
    store = await store_collection.find_one(
        {"user_id": current_user},
        {"_id": 0} # _id 필드는 제외하고 반환 (JSON 직렬화 문제 방지)
    )

    if not store:
        raise HTTPException(status_code=404, detail="등록된 매장 정보가 없습니다.")

    return store