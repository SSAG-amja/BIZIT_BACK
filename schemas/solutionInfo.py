from pydantic import BaseModel, Field

class SolutionSchema(BaseModel):
    # 1. 솔루션 내용
    title: str = Field(..., description="솔루션 제목", min_length=1)
    solution: str = Field(..., description="솔루션 상세 내용")