"""NodeVelture G-Eval 실행 스크립트.

사용법:
  python eval/run_eval.py --chat-id <UUID>          # 전체 testset을 하나의 세션으로 평가
  python eval/run_eval.py --chat-id <UUID> --ids 1,3,5  # 특정 테스트만
  python eval/run_eval.py --chat-id <UUID> --category anti_mirror

환경변수:
  ANTHROPIC_API_KEY   필수 — judge 모델 (Claude)
  EVAL_API_BASE       선택 — 기본값 http://localhost:8000/api/v1
  EVAL_JUDGE_MODEL    선택 — 기본값 claude-opus-4-8
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from g_eval import score, avg_score  # noqa: E402

TESTSET_PATH = ROOT / "testset.jsonl"
RESULTS_DIR  = ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)

import os
API_BASE = os.getenv("EVAL_API_BASE", "http://localhost:8000/api/v1")


# ── SSE 스트림 소비 ──────────────────────────────────────────────────────────

def call_chat(chat_id: str, content: str, character_id: str, world_context: str = "") -> dict:
    """
    1) POST /chats/{chat_id}/messages  — 대화 저장
    2) GET  /chats/{chat_id}/stream    — SSE 소비 → reply 이벤트 파싱
    반환: {"narration", "dialogue", "speaker", "ttfb", "error"}
    """
    result = {"narration": "", "dialogue": "", "speaker": "", "ttfb": None, "error": None}

    # 1. 메시지 전송
    try:
        requests.post(
            f"{API_BASE}/chats/{chat_id}/messages",
            json={"content": content, "character_id": character_id},
            timeout=10,
        )
    except requests.RequestException as e:
        result["error"] = f"send_message 실패: {e}"
        return result

    # 2. 스트림 연결 + SSE 파싱
    params = {
        "content": content,
        "character_id": character_id,
        "world_context": world_context,
    }
    t0 = time.time()
    try:
        with requests.get(
            f"{API_BASE}/chats/{chat_id}/stream",
            params=params,
            stream=True,
            timeout=60,
        ) as resp:
            resp.raise_for_status()
            event_type = None
            for raw in resp.iter_lines(decode_unicode=True):
                line = raw.strip() if raw else ""
                if line.startswith("event:"):
                    event_type = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    if result["ttfb"] is None:
                        result["ttfb"] = round(time.time() - t0, 3)
                    if event_type == "reply":
                        try:
                            data = json.loads(line[len("data:"):].strip())
                            result["narration"] = data.get("narration", "")
                            result["dialogue"]  = data.get("dialogue", "")
                            result["speaker"]   = data.get("speaker", "")
                        except json.JSONDecodeError:
                            pass
                    elif event_type == "done":
                        break
    except requests.RequestException as e:
        result["error"] = f"stream 실패: {e}"

    return result


# ── 테스트셋 로드 ─────────────────────────────────────────────────────────────

def load_testset(ids: list[int] | None = None, category: str | None = None) -> list[dict]:
    tests = []
    with open(TESTSET_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            t = json.loads(line)
            if ids and t["id"] not in ids:
                continue
            if category and t.get("category") != category:
                continue
            tests.append(t)
    return tests


# ── 리포트 출력 ───────────────────────────────────────────────────────────────

def print_report(records: list[dict]) -> None:
    valid = [r for r in records if "persona_consistency" in r]
    if not valid:
        print("채점된 결과가 없습니다.")
        return

    metrics = ["persona_consistency", "immersion", "naturalness", "anti_mirroring"]
    ttfbs   = [r["ttfb"] for r in records if r.get("ttfb")]

    print("\n" + "=" * 55)
    print(f"  G-Eval 결과  ({len(valid)}/{len(records)}건 완료)")
    print("=" * 55)
    for m in metrics:
        vals = [r[m] for r in valid if isinstance(r.get(m), (int, float))]
        avg  = sum(vals) / len(vals) if vals else 0
        bar  = "█" * round(avg) + "░" * (5 - round(avg))
        print(f"  {m:<24} {bar}  {avg:.2f} / 5.00")

    if ttfbs:
        avg_ttfb = sum(ttfbs) / len(ttfbs)
        flag = "✅" if avg_ttfb <= 1.5 else "⚠️ "
        print(f"\n  TTFB 평균: {avg_ttfb:.3f}초  {flag} (목표 ≤1.5초)")

    # 카테고리별 평균
    cats: dict[str, list] = {}
    for r in valid:
        c = r.get("category", "-")
        cats.setdefault(c, []).append(avg_score(r))
    if len(cats) > 1:
        print("\n  카테고리별 평균:")
        for c, scores in sorted(cats.items()):
            print(f"    {c:<16} {sum(scores)/len(scores):.2f}")

    print("=" * 55)


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="NodeVelture G-Eval 실행")
    parser.add_argument("--chat-id",   required=True, help="평가에 사용할 세션 UUID")
    parser.add_argument("--ids",       help="쉼표 구분 테스트 ID (예: 1,3,5)")
    parser.add_argument("--category",  help="특정 카테고리만 (예: anti_mirror)")
    parser.add_argument("--no-save",   action="store_true", help="결과 파일 저장 안 함")
    args = parser.parse_args()

    ids = [int(x) for x in args.ids.split(",")] if args.ids else None
    testset = load_testset(ids=ids, category=args.category)

    if not testset:
        print("조건에 맞는 테스트가 없습니다.")
        return

    print(f"총 {len(testset)}건 평가 시작 → chat_id={args.chat_id}")

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = RESULTS_DIR / f"eval_{timestamp}.jsonl"
    records     = []

    for i, test in enumerate(testset, 1):
        label = f"[{i:02d}/{len(testset):02d}] #{test['id']} ({test.get('category', '-')})"
        print(f"{label} ...", end=" ", flush=True)

        # API 호출
        api = call_chat(
            chat_id      = args.chat_id,
            content      = test["input"],
            character_id = test.get("character_id", "baekya"),
            world_context= test.get("world_context", ""),
        )

        if api["error"]:
            print(f"❌  {api['error']}")
            records.append({"test_id": test["id"], "error": api["error"]})
            continue

        # G-Eval 채점
        eval_result = score(
            world_context = test.get("world_context", ""),
            user_input    = test["input"],
            narration     = api["narration"],
            dialogue      = api["dialogue"],
            speaker       = api["speaker"],
        )

        record = {
            "test_id":  test["id"],
            "category": test.get("category"),
            "input":    test["input"],
            "narration":api["narration"],
            "dialogue": api["dialogue"],
            "speaker":  api["speaker"],
            "ttfb":     api["ttfb"],
            **eval_result,
        }
        records.append(record)

        if "error" in eval_result:
            print(f"⚠️   채점 실패: {eval_result['error']}")
        else:
            avg = avg_score(eval_result)
            print(f"✅  avg={avg:.1f}  TTFB={api['ttfb']}s")

        if not args.no_save:
            with open(result_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        time.sleep(0.5)  # API rate-limit 완충

    print_report(records)
    if not args.no_save and records:
        print(f"\n결과 파일: {result_path}")


if __name__ == "__main__":
    main()
