from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# 1. 백분위 등급 정보 (Percentile)
class PercentileInfo(BaseModel):
    grade: str = Field(..., description="등급 (TOP, HIGH, MID, LOW, BOTTOM)")
    label: str = Field(..., description="등급 한글 라벨 (예: 상위 10~15%)")
    ratio: float = Field(..., description="내 매출 / 기준 매출 비율")
    benchmark_revenue: int = Field(..., description="비교 대상(동종업계) 평균 매출")

# 2. 전월 대비 성장률 (MoM Growth)
class MomGrowthInfo(BaseModel):
    value: float = Field(..., description="증감율 (%)")
    direction: str = Field(..., description="방향 (UP, DOWN, FLAT)")
    diff_amount: int = Field(..., description="전월 대비 차액")

# 3. 월별 추세 (Monthly Trend)
class MonthlyTrendInfo(BaseModel):
    months: List[str] = Field(..., description="년월 리스트 (x축)")
    my_store: List[int] = Field(..., description="내 매장 매출 리스트")
    industry_avg_all: List[int] = Field(..., description="서울시 전체 평균 매출 리스트")
    industry_avg_dong: List[int] = Field(..., description="행정동 평균 매출 리스트")
    basis: str = Field(..., description="데이터 기준 (예: quarterly_month_average)")

# 4. 최신 데이터 비교 (Latest Comparison)
class LatestComparisonInfo(BaseModel):
    month: str = Field(..., description="비교 기준 월 (YYYY-MM)")
    my_store: int = Field(..., description="내 매장 매출")
    industry_avg_all: int = Field(..., description="서울시 전체 평균")
    industry_avg_dong: int = Field(..., description="행정동 평균")

# 5. 전체 분석 정보 스키마 (Main Schema)
class AnalysisResultSchema(BaseModel):
    user_email: str = Field(..., description="사용자 이메일")
    created_at: datetime = Field(..., description="분석 생성/수정 일시")
    target_ym: str = Field(..., description="분석 대상 년월")
    
    percentile: PercentileInfo
    mom_growth: MomGrowthInfo
    monthly_trend: MonthlyTrendInfo
    latest_comparison: LatestComparisonInfo

    class Config:
        json_schema_extra = {
            "example": {
                "user_email": "user@example.com",
                "created_at": "2025-12-21T21:01:10.559Z",
                "target_ym": "2025-07",
                "percentile": {
                    "grade": "LOW",
                    "label": "하위 30~40%",
                    "ratio": 0.93,
                    "benchmark_revenue": 10751618
                },
                "mom_growth": {
                    "value": -16.67,
                    "direction": "DOWN",
                    "diff_amount": -2000000
                },
                "monthly_trend": {
                    "months": ["2025-05", "2025-06", "2025-07"],
                    "my_store": [10000000, 12000000, 10000000],
                    "industry_avg_all": [321469110, 321469110, 300330547],
                    "industry_avg_dong": [7311100, 7311100, 10751618],
                    "basis": "quarterly_month_average"
                },
                "latest_comparison": {
                    "month": "2025-07",
                    "my_store": 10000000,
                    "industry_avg_all": 300330547,
                    "industry_avg_dong": 10751618
                }
            }
        }