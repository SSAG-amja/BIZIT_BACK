import os
import traceback
from dotenv import load_dotenv
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
from fastapi import APIRouter, Depends
from core.security import get_current_user

# .env 파일 로드 (요청하신 그대로 유지)
load_dotenv()

MONGO_URI = os.getenv("MONGO_URL")
DB_NAME = "BIZIT_DB"

# 파일 경로 절대 경로로 설정 (요청하신 그대로 유지)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKET_CSV = os.path.join(BASE_DIR, "data_set", "서울상권_추정매출.csv")

# 라우터 정의 (API 엔드포인트 등록용)
router = APIRouter(prefix="/analysis", tags=["analysis"])

def classify_percentile(ratio: float):
    if ratio >= 1.30: return ("TOP", "상위 10~15%")
    elif ratio >= 1.15: return ("HIGH", "상위 20~30%")
    elif ratio >= 1.05: return ("UPPER_MID", "상위 30~40%")
    elif ratio >= 0.95: return ("MID", "평균 수준")
    elif ratio >= 0.80: return ("LOW", "하위 30~40%")
    else: return ("BOTTOM", "하위 10~20%")

def ym_to_quarter_code(ym: str) -> str:
    """
    YYYY-MM -> YYYYQ 변환
    """
    year, month = ym.split("-")
    month = int(month)
    if month <= 3: q = "1"
    elif month <= 6: q = "2"
    elif month <= 9: q = "3"
    else: q = "4"
    return f"{year}{q}"

# store.py에서 import해서 쓸 함수 (내용 100% 동일)
def run_analysis(user_email: str):
    print(f"\n========== [DEBUG] 분석 시작: {user_email} ==========")
    
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]

        # 1. storeInfo 조회
        store = db.storeInfo.find_one({"user_id": user_email})
        if not store:
            print(f"!!! [ERROR] storeInfo 없음: {user_email}")
            return

        sector_code = str(store["sector_code_cs"])
        admin_code = str(store["location"]["admin_code"])

        # 2. 내 매출 데이터
        sales_logs = store.get("sales_logs", [])
        if not sales_logs:
             print("!!! [ERROR] 매출 데이터 없음")
             return

        sales_df = pd.DataFrame(sales_logs)
        sales_df = sales_df.sort_values("ym")

        if len(sales_df) < 2:
            print("!!! [STOP] 데이터 2개월 미만")
            return

        # MoM 계산
        this_month_row = sales_df.iloc[-1]
        prev_month_row = sales_df.iloc[-2]
        my_latest_revenue = this_month_row["revenue"]
        my_latest_ym = this_month_row["ym"]

        # 그래프용 데이터 (최근 6개월)
        recent_sales_df = sales_df.tail(6)
        months = recent_sales_df["ym"].tolist()
        my_sales_trend = recent_sales_df["revenue"].tolist()

        # 3. CSV 로딩 및 최신 분기 확인
        if not os.path.exists(MARKET_CSV):
            print(f"!!! [ERROR] CSV 파일 없음: {MARKET_CSV}")
            return
            
        market_df = pd.read_csv(MARKET_CSV, encoding="utf-8")
        
        # 타입 통일
        market_df["행정동_코드"] = market_df["행정동_코드"].astype(str)
        market_df["서비스_업종_코드"] = market_df["서비스_업종_코드"].astype(str)
        market_df["기준_년분기_코드"] = market_df["기준_년분기_코드"].astype(str)

        # ▼▼▼ [핵심 수정] CSV에 존재하는 '가장 최신 분기' 찾기 ▼▼▼
        # 예: CSV가 20253분기까지만 있다면, latest_db_quarter = "20253"
        all_quarters = sorted(market_df["기준_년분기_코드"].unique())
        if not all_quarters:
            print("!!! [ERROR] CSV 파일에 분기 데이터가 없습니다.")
            return
        latest_db_quarter = all_quarters[-1]
        print(f"[DEBUG] CSV 최신 분기: {latest_db_quarter}")

        # ▼▼▼ [핵심 수정] 미래 분기 보정 함수 ▼▼▼
        def get_adjusted_quarter(ym):
            """
            날짜를 분기 코드로 바꾸되, CSV에 없는 미래 분기라면
            CSV의 가장 최신 분기로 대치한다.
            """
            q_code = ym_to_quarter_code(ym)
            if q_code > latest_db_quarter:
                return latest_db_quarter  # 미래면 최신값 리턴
            return q_code

        # 내 매출 월들을 '보정된' 분기 코드로 변환
        # 예: 2025-10(20254) -> CSV에 없으면 20253으로 변환되어 리스트에 들어감
        adjusted_quarters = [get_adjusted_quarter(ym) for ym in months]

        # 4. 비교 데이터 추출 (보정된 쿼터 사용)
        # A. 서울시 전체
        industry_all_df = market_df[
            (market_df["서비스_업종_코드"] == sector_code) &
            (market_df["기준_년분기_코드"].isin(adjusted_quarters)) # <--- 보정된 쿼터로 검색
        ]
        quarter_avg_all_map = industry_all_df.groupby("기준_년분기_코드")["당월_매출_금액"].mean().to_dict()

        # B. 내 행정동
        industry_dong_df = market_df[
            (market_df["서비스_업종_코드"] == sector_code) &
            (market_df["행정동_코드"] == admin_code) &
            (market_df["기준_년분기_코드"].isin(adjusted_quarters)) # <--- 보정된 쿼터로 검색
        ]
        quarter_avg_dong_map = industry_dong_df.groupby("기준_년분기_코드")["당월_매출_금액"].mean().to_dict()

        # C. 그래프용 리스트 생성
        industry_trend_all = []
        industry_trend_dong = []

        for ym in months:
            # 여기서도 get_adjusted_quarter를 사용하여 키를 찾습니다.
            q_key = get_adjusted_quarter(ym)
            
            val_all = int(quarter_avg_all_map.get(q_key, 0))
            val_dong = int(quarter_avg_dong_map.get(q_key, 0))
            
            industry_trend_all.append(val_all)
            industry_trend_dong.append(val_dong)

        # 5. 지표 계산
        latest_benchmark = industry_trend_dong[-1]
        
        # 행정동 데이터가 아예 0이면 서울시 전체 평균으로 대체
        if latest_benchmark == 0:
             latest_benchmark = industry_trend_all[-1] if industry_trend_all[-1] > 0 else 1

        ratio = my_latest_revenue / latest_benchmark
        grade, label = classify_percentile(ratio)

        prev_revenue = prev_month_row["revenue"]
        if prev_revenue == 0:
            mom = 100.0 if my_latest_revenue > 0 else 0.0
        else:
            mom = ((my_latest_revenue - prev_revenue) / prev_revenue) * 100
        direction = "UP" if mom > 1 else "DOWN" if mom < -1 else "FLAT"

        # 6. 저장
        final_result = {
            "user_email": user_email,
            "created_at": datetime.utcnow(),
            "target_ym": my_latest_ym,
            "percentile": {
                "grade": grade,
                "label": label,
                "ratio": round(ratio, 2),
                "benchmark_revenue": int(latest_benchmark)
            },
            "mom_growth": {
                "value": round(mom, 2),
                "direction": direction,
                "diff_amount": int(my_latest_revenue - prev_revenue)
            },
            "monthly_trend": {
                "months": months,
                "my_store": my_sales_trend,
                "industry_avg_all": industry_trend_all,
                "industry_avg_dong": industry_trend_dong,
                "basis": "quarterly_month_average"
            },
            "latest_comparison": {
                "month": my_latest_ym,
                "my_store": int(my_latest_revenue),
                "industry_avg_all": int(industry_trend_all[-1]),
                "industry_avg_dong": int(industry_trend_dong[-1])
            }
        }

        db.analysis.insert_one(final_result)
        print(f"========== [SUCCESS] 분석 완료 (보정 적용됨): {latest_db_quarter} 사용 ==========\n")

    except Exception as e:
        print(f"\n!!! [CRITICAL ERROR] 분석 중 오류 발생 !!!: {e}")
        traceback.print_exc()

# API 엔드포인트 추가 (기존 로직 사용)
@router.post("/run")
def run_analysis_endpoint(user_email: str = Depends(get_current_user)):
    run_analysis(user_email)
    return {
        "status": "success",
        "message": "분석이 완료되었습니다."
    }