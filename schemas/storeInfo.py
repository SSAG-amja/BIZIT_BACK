from pydantic import BaseModel, Field
from typing import List, Optional


# 1. 하위 세부 스키마 정의 (부품들)

# 2. 위치 정보
class LocationSchema(BaseModel):
    address: str = Field(..., description="도로명 주소 또는 지번 주소", example="서울 종로구 사직로 161")
    detail_address: Optional[str] = Field(None, description="상세 주소 (층, 호수 등)")

    # [입력 불필요] 아래는 프론트에서 안 보내도 됨 (서버가 채움) -> Optional 처리
    lat: Optional[float] = Field(None, description="위도 (서버 자동 생성)")
    lng: Optional[float] = Field(None, description="경도 (서버 자동 생성)")
    
    # 행정동 정보도 주소 API 등을 통해 프론트에서 받거나, 서버에서 채울 수 있음
    admin_code: Optional[str] = Field(None, description="행정동 코드")
    admin_dong_name: Optional[str] = Field(None, description="행정동 이름")
    
# 3. 매출 상세 내역 (Weekly, Time, Gender, Age)
class WeeklySales(BaseModel):
    mon: Optional[int] = 0
    tue: Optional[int] = 0
    wed: Optional[int] = 0
    thu: Optional[int] = 0
    fri: Optional[int] = 0
    sat: Optional[int] = 0
    sun: Optional[int] = 0

class TimeSlotSales(BaseModel):
    t00_06: Optional[int] = 0
    t06_11: Optional[int] = 0
    t11_14: Optional[int] = 0
    t14_17: Optional[int] = 0
    t17_21: Optional[int] = 0
    t21_24: Optional[int] = 0

class GenderSales(BaseModel):
    male: Optional[int] = 0
    female: Optional[int] = 0

class AgeGroupSales(BaseModel):
    a10: Optional[int] = 0
    a20: Optional[int] = 0
    a30: Optional[int] = 0
    a40: Optional[int] = 0
    a50: Optional[int] = 0
    a60_over: Optional[int] = 0

class SalesLogDetails(BaseModel):
    weekly: Optional[WeeklySales] = None
    time_slot: Optional[TimeSlotSales] = None
    gender: Optional[GenderSales] = None
    age_groups: Optional[AgeGroupSales] = None

class SalesLog(BaseModel):
    ym: str = Field(..., description="년월 (YYYY-MM)")
    revenue: int = Field(..., description="매출")
    profit: int = Field(..., description="순이익")
    details: Optional[SalesLogDetails] = None

# 4. 고정 지출
class FixedCost(BaseModel):
    electricity: Optional[int] = 0
    water: Optional[int] = 0
    gas: Optional[int] = 0
    labor: Optional[int] = 0
    rent: Optional[int] = 0
    etc: Optional[int] = 0

# 5. 배달
class DeliveryInfo(BaseModel):
    is_active: bool = Field(False, description="배달 운영 여부")
    sales_ratio: Optional[float] = Field(0.0, description="배달 매출 비중 (%)")

# 6. 메뉴
class MenuItem(BaseModel):
    name: str = Field(..., description="메뉴명", examples=["제육볶음"])
    price: int = Field(..., description="가격", examples=[12000])
    cost_rate: float = Field(..., description="원가율 (%)", examples=[35.5])

class MenuInfo(BaseModel):
    main: List[MenuItem] = Field(default=[], description="주력 메뉴 리스트")
    general: List[MenuItem] = Field(default=[], description="일반 메뉴 리스트")

    model_config = {
        "json_schema_extra": {
            "example": {
                "general": [
                    {
                        "name": "된장찌개",
                        "price": 5000,
                        "cost_rate": 25.0
                    },
                    {
                        "name": "공기밥",
                        "price": 1000,
                        "cost_rate": 10.0
                    }
                ],
                "main": [
                    {
                        "name": "숙성 삼겹살",
                        "price": 16000,
                        "cost_rate": 32.0
                    }
                ]
            }
        }
    }
# 7. 매장 규모
class StoreScale(BaseModel):
    area_size: Optional[float] = Field(None, description="평수")
    seats: Optional[int] = Field(None, description="좌석 수")
    turnover: Optional[float] = Field(None, description="회전율")

# 8. 영업 시간
class OperationHours(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None

class OperationInfo(BaseModel):
    months_business: Optional[int] = Field(None, description="영업 개월 수")
    closed_days: List[str] = []
    hours: Optional[OperationHours] = None

# 9. 목표
class Goals(BaseModel):
    growth_target: List[str] = []
    problem_area: List[str] = []


# 전체 매장 정보 스키마
class StoreInfoSchema(BaseModel):
    # 1. 업종 정보
    sector_code: str = Field(..., description="KSIC 코드")
    sector_name: str = Field(..., description="업종 명칭")
    sector_code_cs: str = Field(..., description="서비스 업종 코드")
    
    # 2. 위치
    location: LocationSchema

    # 3. 매출 (로그 리스트)
    sales_logs: List[SalesLog]

    # 4 ~ 9. 선택 정보 (Optional)
    fixed_cost: Optional[FixedCost] = None
    delivery: Optional[DeliveryInfo] = None
    menus: Optional[MenuInfo] = None
    scale: Optional[StoreScale] = None
    operation: Optional[OperationInfo] = None
    goals: Optional[Goals] = None