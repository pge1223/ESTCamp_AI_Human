from fastapi import APIRouter, HTTPException
import json
import os
import traceback

router = APIRouter()

# 경로 설정
CURRENT_FILE_PATH = os.path.abspath(__file__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_FILE_PATH)))))
AUTHORS_PATH = os.path.join(BASE_DIR, "data/assets", "authors.json")
QUESTIONS_PATH = os.path.join(BASE_DIR, "data/assets", "questions.json")

# 캐시 데이터를 담아둘 전역 변수
_AUTHORS_CACHE = None
_QUESTIONS_CACHE = None

def load_data_to_cache():
    """디스크에서 JSON 파일을 읽어 전역 변수(메모리)에 저장하는 함수"""
    global _AUTHORS_CACHE, _QUESTIONS_CACHE
    
    # 작가 데이터 로드
    if os.path.exists(AUTHORS_PATH):
        with open(AUTHORS_PATH, "r", encoding="utf-8") as f:
            _AUTHORS_CACHE = json.load(f)
            
    # 질문 데이터 로드
    if os.path.exists(QUESTIONS_PATH):
        with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
            _QUESTIONS_CACHE = json.load(f)


@router.get("/")
async def get_authors():
    try:
        global _AUTHORS_CACHE
        
        if _AUTHORS_CACHE is None:
            load_data_to_cache()
                
        if _AUTHORS_CACHE is None:
            raise HTTPException(status_code=404, detail="작가 정보를 찾을 수 없습니다.")
                
        return _AUTHORS_CACHE
        
    except HTTPException:
        raise
    except Exception as e:
        print("[get_authors Error]")
        traceback.print_exc()
                
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
    

@router.get("/{author_id}")
async def get_author(author_id: int):
    try:
        global _AUTHORS_CACHE
        if _AUTHORS_CACHE is None:
            load_data_to_cache()

        if _AUTHORS_CACHE is None:
            raise HTTPException(status_code=404, detail="작가 정보를 찾을 수 없습니다.")
        
        author = next((item for item in _AUTHORS_CACHE if str(item.get("id")) == str(author_id)), None)

        if not author:
            raise HTTPException(status_code=404, detail="해당 작가를 찾을 수 없습니다.")

        return author

    except HTTPException:
        raise
    except Exception as e:
        print("[get_author Error]")
        traceback.print_exc()
                
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
    

@router.get("/{author_id}/questions")
async def get_questions(author_id: int):
    try:
        global _QUESTIONS_CACHE
        if _QUESTIONS_CACHE is None:
            load_data_to_cache()

        if _QUESTIONS_CACHE is None:
            raise HTTPException(status_code=404, detail="질문 정보를 찾을 수 없습니다.")
        
        questions = _QUESTIONS_CACHE.get(str(author_id))

        if not questions:
            raise HTTPException(status_code=404, detail="해당 작가의 질문을 찾을 수 없습니다.")

        return questions

    except HTTPException:
        raise
    except Exception as e:
        print("[get_questions Error]")
        traceback.print_exc()
                
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")