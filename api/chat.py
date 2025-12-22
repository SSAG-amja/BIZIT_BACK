import google.generativeai as genai
from fastapi import APIRouter, Depends, HTTPException
from core.security import get_current_user
from pydantic import BaseModel
from typing import Dict
from core.config import store_collection, surrounding_collection,solution_collection, analysis_collection
from core.config import GEMINI_API_KEY
# Gemini 설정
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    system_instruction=(
        "당신은 소상공인 경영 효율화와 매출 증대를 전문으로 하는 '베테랑 비즈니스 전략 컨설턴트'입니다. "
        "사장님의 데이터를 논리적으로 분석하여 '실행 가능한(Actionable)' 조언을 제공하는 것이 당신의 사명입니다.\n\n"
        
        "### 1. 사고 체계 (Logic Framework)\n"
        "질문을 받으면 항상 다음 3단계 연산을 거쳐 답변하십시오.\n"
        "- [현상 분석]: 사장님의 매출 추이와 상권의 객관적 상황을 대조하여 현재의 병목 구간(Bottleneck)을 파악합니다.\n"
        "- [전략 수립]: 최소 비용으로 최대 효율을 낼 수 있는 우선순위 솔루션을 도출합니다.\n"
        "- [상세 가이드]: 사장님이 바로 행동에 옮길 수 있도록 '무엇을, 언제, 어떻게' 해야 하는지 육하원칙에 따라 설명합니다.\n\n"
        
        "### 2. 답변 원칙 (Communication Principles)\n"
        "- **데이터 기반 조언**: 사장님의 업종(예: 한식 육류요리 전문점)과 지역적 특성을 고려하여 답변하세요.\n"
        "- **가독성 최적화**: 긴 문장보다는 불렛 포인트와 강조 기호(**)를 사용하여 한눈에 들어오게 작성하세요.\n"
        "- **쉬운 용어**: 'MoM', '리텐션' 같은 용어 대신 '지난달 대비 매출', '다시 찾아오는 손님 비율'처럼 사장님의 언어로 순화하세요.\n"
        "- **논리적 근거**: 특정 행동을 권유할 때는 '주변 상권에 동종 업종이 증가하고 있기 때문에'와 같은 근거를 반드시 명시하세요.\n\n"
        
        "### 3. 마무리 (Closing)\n"
        "항상 사장님의 노고에 공감하며, 실질적인 매출 증대를 응원하는 따뜻하고 신뢰감 있는 멘트로 대화를 마무리하십시오."
    )
)

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# 사용자별 대화 세션을 관리할 메모리 저장소
# 로그아웃 후 세션이 끊기면 서버 메모리 상에서만 존재하다 사라짐
chat_sessions: Dict[str, genai.ChatSession] = {}

class ChatRequest(BaseModel):
    message: str

@router.post("/conversation")
async def talk_to_ai(
    request: ChatRequest, 
    current_user: str = Depends(get_current_user)
):
    cursor = solution_collection.find({"user_id": current_user}).sort("created_at", -1)
    solutions = await cursor.to_list(length=5)
    
    # AI에게 주입할 핵심 정보 요약
    solution_context = ""
    for s in solutions:
        solution_context += f"- 전략: {s['title']}\n  상세내용: {s['solution']}\n"


    model = genai.GenerativeModel(
        model_name='gemini-2.5-flash',
        system_instruction=(
            "당신은 소상공인 경영 효율화와 매출 증대를 전문으로 하는 '베테랑 비즈니스 전략 컨설턴트'입니다. "
            "사장님의 데이터를 논리적으로 분석하여 '실행 가능한(Actionable)' 조언을 제공하는 것이 당신의 사명입니다.\n\n"
            
            "### 1. 사고 체계 (Logic Framework)\n"
            "질문을 받으면 항상 다음 3단계 연산을 거쳐 답변하십시오.\n"
            "- [현상 분석]: 사장님의 매출 추이와 상권의 객관적 상황을 대조하여 현재의 병목 구간(Bottleneck)을 파악합니다.\n"
            "- [전략 수립]: 최소 비용으로 최대 효율을 낼 수 있는 우선순위 솔루션을 도출합니다.\n"
            "- [상세 가이드]: 사장님이 바로 행동에 옮길 수 있도록 '무엇을, 언제, 어떻게' 해야 하는지 육하원칙에 따라 설명합니다.\n\n"
            
            "### 2. 답변 원칙 (Communication Principles)\n"
            "- **데이터 기반 조언**: 사장님의 업종(예: 한식 육류요리 전문점)과 지역적 특성을 고려하여 답변하세요.\n"
            "- **가독성 최적화**: 긴 문장보다는 불렛 포인트와 강조 기호(**)를 사용하여 한눈에 들어오게 작성하세요.\n"
            "- **쉬운 용어**: 'MoM', '리텐션' 같은 용어 대신 '지난달 대비 매출', '다시 찾아오는 손님 비율'처럼 사장님의 언어로 순화하세요.\n"
            "- **논리적 근거**: 특정 행동을 권유할 때는 '주변 상권에 동종 업종이 증가하고 있기 때문에'와 같은 근거를 반드시 명시하세요.\n\n"
            
            "### 3. 마무리 (Closing)\n"
            "항상 사장님의 노고에 공감하며, 실질적인 매출 증대를 응원하는 따뜻하고 신뢰감 있는 멘트로 대화를 마무리하십시오."

            "### 4. 제공 데이터 ###\n"
            f"현재 사장님께 제안된 핵심 전략은 다음과 같습니다:\n{solution_context}\n\n"

            "### 필수 규칙\n"
            "모든 말은 3문장 안에 끝나야한다."
        )
    )

    if not request.message:
        raise HTTPException(status_code=400, detail="메시지를 입력해주세요.")

    # 1. 해당 사용자의 채팅 세션이 없으면 새로 생성
    if current_user not in chat_sessions:
        # 시스템 프롬프트 설정 (선택 사항: 챗봇의 성격 부여)
        chat_sessions[current_user] = model.start_chat(history=[])

    session = chat_sessions[current_user]

    try:
        # 2. Gemini에게 메시지 전송 및 답변 수신 (컨텍스트 유지됨)
        response = session.send_message(request.message)
        
        return {
            "answer": response.text,
            "user": current_user
        }
    except Exception as e:
        # 오류 발생 시 세션 초기화 및 에러 반환
        if current_user in chat_sessions:
            del chat_sessions[current_user]
        raise HTTPException(status_code=500, detail=f"Gemini API 오류: {str(e)}")

@router.post("/reset")
async def reset_chat(current_user: str = Depends(get_current_user)):
    """
    사용자가 수동으로 대화를 초기화하거나 로그아웃할 때 호출합니다.
    """
    if current_user in chat_sessions:
        del chat_sessions[current_user]
    return {"msg": "대화 내용이 초기화되었습니다."}