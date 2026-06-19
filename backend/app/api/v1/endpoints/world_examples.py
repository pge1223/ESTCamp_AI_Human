from fastapi import APIRouter, HTTPException, Query
import json
import os
import random
import traceback

router = APIRouter()

CURRENT_FILE_PATH = os.path.abspath(__file__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_FILE_PATH)))))
WORLD_EXAMPLES_DIR = os.path.join(BASE_DIR, "data/assets/world_examples")

_WORLD_EXAMPLES_CACHE = {}


def load_world_examples(author_id: int):
    """작가별 세계관 예시 JSON 파일을 읽어 캐시에 저장"""
    cache_key = str(author_id)

    if cache_key in _WORLD_EXAMPLES_CACHE:
        return _WORLD_EXAMPLES_CACHE[cache_key]

    file_path = os.path.join(WORLD_EXAMPLES_DIR, f"author{author_id}.json")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="해당 작가의 세계관 예시 파일을 찾을 수 없습니다.")

    with open(file_path, "r", encoding="utf-8") as f:
        examples = json.load(f)

    if not examples:
        raise HTTPException(status_code=404, detail="해당 작가의 세계관 예시가 없습니다.")

    _WORLD_EXAMPLES_CACHE[cache_key] = examples

    return examples


@router.get("/random/{author_id}")
async def get_random_world_examples(
    author_id: int,
    count: int = Query(default=1, ge=1, le=10)
):
    try:
        examples = load_world_examples(author_id)

        sample_count = min(count, len(examples))

        return random.sample(examples, sample_count)

    except HTTPException:
        raise
    except Exception:
        print("[get_random_world_examples Error]")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="세계관 예시를 불러오는 중 서버 오류가 발생했습니다."
        )