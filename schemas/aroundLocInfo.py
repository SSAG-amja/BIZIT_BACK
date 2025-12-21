from pydantic import BaseModel, Field
from typing import List

# 1. 좌표 객체 (내부 재사용용 부품)
class Coordinate(BaseModel):
    lat: float = Field(..., description="위도")
    lng: float = Field(..., description="경도")

# 2. 주변 상권 스키마 (입력용)
class SurroundingSchema(BaseModel):
    rad_500: List[Coordinate] = Field(default=[], description="반경 500m 상권 좌표 리스트")
    rad_1000: List[Coordinate] = Field(default=[], description="반경 1000m 상권 좌표 리스트")
    rad_1500: List[Coordinate] = Field(default=[], description="반경 1500m 상권 좌표 리스트")
    rad_2000: List[Coordinate] = Field(default=[], description="반경 2000m 상권 좌표 리스트")