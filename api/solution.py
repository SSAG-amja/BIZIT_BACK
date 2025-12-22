import os
import pandas as pd
import asyncio
import requests
import json
from datetime import datetime
from fastapi import APIRouter, Depends
from core.config import store_collection, surrounding_collection, solution_collection, GEMINI_API_KEY
from core.security import get_current_user 
from schemas.solutionInfo import SolutionSchema

router = APIRouter(prefix="/api/solution", tags=["Solution"])

# =================================================================
# [Point 1] 솔루션 조회 API
# =================================================================
@router.get("/list")
async def get_my_solutions(current_user: str = Depends(get_current_user)): 
    projection = {"title": 1, "solution": 1, "_id": 0}
    # 최신순 정렬
    cursor = solution_collection.find({"user_id": current_user}, projection).sort("created_at", -1)
    return await cursor.to_list(length=20)

# =================================================================
# [Helper] 검색 조건 추출
# =================================================================
def extract_search_criteria(store_doc: dict):
    try:
        location = store_doc.get("location", {})
        admin_code = location.get("admin_code", "")
        sector_code = store_doc.get("sector_code_cs", "")
        
        sales_logs = store_doc.get("sales_logs", [])
        quarters_set = set()
        
        for log in sales_logs:
            ym = log.get("ym")
            if ym and len(str(ym)) == 6:
                try:
                    s_ym = str(ym)
                    year = s_ym[:4]
                    month = int(s_ym[4:])
                    quarter = (month - 1) // 3 + 1
                    quarters_set.add(f"{year}{quarter}")
                except ValueError:
                    continue 
        return admin_code, sector_code, list(quarters_set)
    except Exception:
        return None, None, []

# =================================================================
# [Helper] CSV 1: 유동인구/소득 -> JSON List 변환
# =================================================================
def get_population_data(file_path: str, admin_code: str, quarters_list: list):
    if not os.path.exists(file_path): return []
    try:
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding='cp949')
        
        cond_admin = df['행정동_코드'].astype(str) == str(admin_code)
        cond_quarter = df['기준_년분기_코드'].astype(str).isin(quarters_list)
        
        filtered_df = df[cond_admin & cond_quarter]
        if filtered_df.empty: return []
            
        return filtered_df.to_dict(orient='records')
    except Exception as e:
        print(f"CSV 1 Error: {e}")
        return []

# =================================================================
# [Helper] CSV 2: 매출 -> JSON List 변환
# =================================================================
def get_sales_data(file_path: str, admin_code: str, sector_code: str, quarters_list: list):
    if not os.path.exists(file_path): return []
    try:
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding='cp949')
        
        cond_admin = df['행정동_코드'].astype(str) == str(admin_code)
        cond_quarter = df['기준_년분기_코드'].astype(str).isin(quarters_list)
        cond_sector = df['서비스_업종_코드'].astype(str) == str(sector_code)
        
        filtered_df = df[cond_admin & cond_quarter & cond_sector]
        if filtered_df.empty: return []
            
        return filtered_df.to_dict(orient='records')
    except Exception as e:
        print(f"CSV 2 Error: {e}")
        return []

# =================================================================
# [Step 3] LLM 요청 함수 (Pandas + requests 사용)
# =================================================================
async def request_llm_generation(final_context: dict):
    print("Step 2: Gemini 분석 요청 시작 (requests 라이브러리)")

    # 1. API 키 확인
    if not GEMINI_API_KEY:
        print("!! 오류: GEMINI_API_KEY가 설정되지 않았습니다.")
        return {
            "title": ["API 키 설정 필요"],
            "solution": ["환경 변수 또는 설정 파일에서 GEMINI_API_KEY를 확인해주세요."]
        }
    
    MODEL_NAME = "gemini-2.5-flash"

    # 2. 데이터 최적화
    market_data = final_context.get("market_data", {})
    
    pop_list = market_data.get("population", [])
    pop_str = pd.DataFrame(pop_list).to_csv(index=False) if pop_list else "데이터 없음"

    sales_list = market_data.get("sales_estimate", [])
    sales_str = pd.DataFrame(sales_list).to_csv(index=False) if sales_list else "데이터 없음"

    # 3. 프롬프트 구성
    system_instruction_text = """
    당신은 소상공인 상권 분석 전문가입니다.
    제공된 데이터를 바탕으로 매출 상승을 위한 구체적인 전략을 3~5가지 제안하세요.

    [작성 규칙]
    1. 입력 데이터의 영문 키워드(예: 'operation', 'scale', 'menus', 'delivery' 등)를 결과에 그대로 출력하지 마십시오.
    2. 반드시 문맥에 맞는 자연스러운 한국어(예: '운영 방식', '매장 규모', '메뉴 구성', '배달 시스템')로 의역하여 작성하세요.
    3. 구체적인 수치(매출액, 유동인구 수 등)는 근거로 적극 활용하세요.

    [포맷 규칙]
    응답은 반드시 '제목'과 '솔루션'이 짝지어진 JSON 배열(List of Objects) 포맷이어야 합니다.
    Markdown 코드 블록(```json) 없이 순수 JSON 텍스트만 반환하세요.
    
    [
        {
            "title": "전략 제목 1",
            "solution": "구체적인 실행 방안 및 근거 1"
        },
        {
            "title": "전략 제목 2",
            "solution": "구체적인 실행 방안 및 근거 2"
        }
    ]
    """

    user_prompt_text = f"""
    아래 데이터를 분석해줘.

    [1. 매장 정보]
    {json.dumps(final_context['store_info'], ensure_ascii=False, indent=2, default=str)}

    [2. 주변 상권 밀집도 (반경별 상가 수)]
    {json.dumps(final_context['surrounding_location'], ensure_ascii=False, indent=2, default=str)}

    [3. 상권 유동인구 데이터 (CSV)]
    {pop_str}

    [4. 상권 추정 매출 데이터 (CSV)]
    {sales_str}
    """

    # 4. Gemini REST API 호출
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"

    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "systemInstruction": {
            "parts": [{"text": system_instruction_text}]
        },
        "contents": [{
            "parts": [{"text": user_prompt_text}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    def _send_request():
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"!! Requests 요청 오류: {e}")
            if hasattr(e.response, 'text'):
                print(f"   서버 응답: {e.response.text}")
            return None

    # 비동기 실행
    response_json = await asyncio.to_thread(_send_request)

    # 5. 결과 파싱
    if response_json and "candidates" in response_json:
        try:
            content_text = response_json["candidates"][0]["content"]["parts"][0]["text"]
            cleaned_text = content_text.replace("```json", "").replace("```", "").strip()
            result_list = json.loads(cleaned_text)
            
            titles = []
            solutions = []
            
            if isinstance(result_list, list):
                for item in result_list:
                    titles.append(item.get("title", "제목 없음"))
                    solutions.append(item.get("solution", "내용 없음"))
            elif isinstance(result_list, dict):
                titles.append(result_list.get("title", "제목 없음"))
                solutions.append(result_list.get("solution", "내용 없음"))
            
            print(f"--> Gemini 응답 성공 ({len(titles)}개 전략 도출)")
            
            return {
                "title": titles,
                "solution": solutions
            }
            
        except (KeyError, json.JSONDecodeError) as e:
            print(f"!! 응답 파싱 실패: {e}\n원본: {response_json}")
            return {
                "title": ["분석 결과 형식 오류"],
                "solution": ["AI 응답을 처리하는 중 오류가 발생했습니다."]
            }
    else:
        print("!! 유효한 응답을 받지 못했습니다.")
        return {
            "title": ["분석 실패"],
            "solution": ["AI 서비스 연결 상태를 확인해주세요."]
        }
    
# =================================================================
# [Step 4] DB 저장 함수 (덮어쓰기 로직 적용)
# =================================================================
async def save_solutions_to_db(user_id: str, generated_data: dict):
    # 생성된 데이터가 없으면 아무것도 하지 않음 (기존 데이터 보존)
    if not generated_data: return

    titles = generated_data.get("title", [])
    solutions = generated_data.get("solution", [])
    
    # 데이터가 비어있으면 저장 안 함
    if not titles: return

    try:
        # ▼▼▼ [수정됨] 기존 데이터 모두 삭제 (덮어쓰기) ▼▼▼
        # user_id에 해당하는 기존 솔루션을 전부 삭제합니다.
        await solution_collection.delete_many({"user_id": user_id})
        
        # 2. 새로운 데이터 저장
        for t, s in zip(titles, solutions):
            solution_data = SolutionSchema(title=t, solution=s)
            doc = solution_data.model_dump() 
            doc["user_id"] = user_id
            doc["created_at"] = datetime.now()
            
            await solution_collection.insert_one(doc)
            
        print(f"솔루션 저장 완료 (기존 데이터 삭제 후 갱신)")
        
    except Exception as e:
        print(f"!! 데이터 저장 중 오류 발생: {e}")

# =================================================================
# [Main] 메인 실행 함수
# =================================================================
async def run_sol(user_id: str):
    print(f"=== [Process Start] User: {user_id} ===")
    
    # 1. Store Info 가져오기
    store_doc = await store_collection.find_one({"user_id": user_id})
    if not store_doc:
        print("매장 정보 없음")
        return 0
    if "_id" in store_doc: del store_doc["_id"]

    # 2. Surrounding Info 가져와서 개수 세기
    surrounding_data = await surrounding_collection.find_one({"user_id": user_id})
    if not surrounding_data:
        surrounding_data = {}
    
    surrounding_summary = {
        "rad_500": len(surrounding_data.get("rad_500", [])),
        "rad_1000": len(surrounding_data.get("rad_1000", [])),
        "rad_1500": len(surrounding_data.get("rad_1500", [])),
        "rad_2000": len(surrounding_data.get("rad_2000", []))
    }

    # 3. CSV 데이터 가져오기
    admin_code, sector_code, quarters_list = extract_search_criteria(store_doc)
    csv1_data = []
    csv2_data = []
    
    if admin_code:
        CSV1_PATH = os.path.join("data_set", "서울상권_소득소비_유동인구.csv")
        CSV2_PATH = os.path.join("data_set", "서울상권_추정매출.csv")
        csv1_data = get_population_data(CSV1_PATH, admin_code, quarters_list)
        csv2_data = get_sales_data(CSV2_PATH, admin_code, sector_code, quarters_list)

    # 4. 통합 JSON 생성
    final_context = {
        "store_info": store_doc,
        "surrounding_location": surrounding_summary,
        "market_data": {
            "population": csv1_data,       
            "sales_estimate": csv2_data    
        }
    }

    # 5. 실행
    generated_result = await request_llm_generation(final_context)
    await save_solutions_to_db(user_id, generated_result)
    
    print("=== [Process End] 분석 완료 ===")
    return 1