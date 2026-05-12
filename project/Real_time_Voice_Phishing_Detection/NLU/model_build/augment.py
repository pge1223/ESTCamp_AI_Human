"""
KBS + 국세청 + 경찰청 + 금감원 실제 사례 기반 GPT 증강 스크립트 v2
기존보다 훨씬 다양한 수법 패턴 반영
pge : v1 + KBS + 기타 사례로 증강 데이터 반영 => v2
"""
import json
import os
import time
from pathlib import Path
from openai import OpenAI

'''
# Windows
set OPENAI_API_KEY=sk-proj-...
uv run python voicephishing_detection_model/model_build/augment.py
'''

_api_key = os.environ.get("OPENAI_API_KEY", "")
if not _api_key:
    print("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
    print("  Windows : set OPENAI_API_KEY=sk-proj-...")
    print("  Mac/Linux: export OPENAI_API_KEY=sk-proj-...")
    raise SystemExit(1)

client = OpenAI(api_key=_api_key)


# ── 확장된 증강 템플릿 ─────────────────────────────────
AUGMENT_TEMPLATES = {

    # ── 기관사칭 ─────────────────────────────────────────
    "기관사칭_검찰경찰": {
        "label": [1, 0, 0],
        "count": 80,
        "description": "검찰/경찰 수사관 사칭",
        "patterns": [
            "서울중앙지검 첨단범죄수사팀 / 경찰청 사이버범죄수사팀 사칭",
            "비밀수사 / 엠바고 사건 명목으로 비밀 유지 강요",
            "끊으면 범죄인정 / 정식재판출두 위협",
            "통화내용 녹음 중이라며 심리적 압박",
            "금융사기단 연루 혐의 제시"
        ],
        "examples": [
            "서울중앙지검 첨단범죄수사팀 수사관입니다. 귀하 명의 계좌가 금융사기단에 이용된 정황이 포착되어 연락드렸습니다.",
            "경찰청 사이버범죄수사팀입니다. 현재 통화 내용은 전부 녹음되고 있으며, 지금 전화를 끊으시면 수사 방해 혐의가 추가됩니다.",
            "저는 검사입니다. 비밀수사 중인 사건에 귀하 명의가 등장하여 연락드립니다. 절대 주변에 발설하시면 안 됩니다."
        ]
    },

    "기관사칭_금감원": {
        "label": [1, 0, 0],
        "count": 60,
        "description": "금융감독원 사칭",
        "patterns": [
            "개인정보 유출로 2차 피해 방지 명목",
            "안전한 장소(모텔 등) 이동 요구",
            "예금이 위험하다며 안전계좌 이동 유도",
            "팀뷰어 등 원격제어 앱 설치 유도",
            "기존 앱 해킹됐다며 삭제 후 악성앱 설치 유도"
        ],
        "examples": [
            "금융감독원입니다. 귀하의 개인정보가 유출되어 2차 피해가 우려됩니다. 현재 위치가 노출될 수 있으니 안전한 장소로 이동해 주세요.",
            "금융감독원 금융사기예방팀입니다. 고객님 예금이 위험한 상태입니다. 즉시 국가안전계좌로 이동시켜야 합니다.",
            "보안 점검을 위해 팀뷰어 앱을 설치해 주시면 원격으로 확인해 드리겠습니다. 지금 바로 설치 가능하신가요?"
        ]
    },

    "기관사칭_국세청세무서": {
        "label": [1, 0, 0],
        "count": 60,
        "description": "국세청/세무서 직원 사칭",
        "patterns": [
            "세무서 소득세과/법인팀/소득팀 직원 사칭",
            "환급금 지급 명목으로 개인정보 요구",
            "세금 환급 처리 위해 신용카드/신분증 요구",
            "대표자 연락처 확인 명목",
            "국세 환급 계좌 등록 명목"
        ],
        "examples": [
            "안녕하세요, 00세무서 소득세과입니다. 고객님께 세금 환급이 발생하여 연락드렸습니다. 환급 처리를 위해 신용카드 앞면 사진을 보내주시겠어요?",
            "소득팀 직원입니다. 올해 환급받으실 금액이 있는데요, 본인 확인을 위해 신분증 앞면 사진이 필요합니다.",
            "국세청입니다. 환급계좌 등록이 안 되어 있어서요. 본인 명의 통장 사진이랑 비밀번호 앞 두 자리만 알려주시면 바로 처리해 드리겠습니다."
        ]
    },

    "기관사칭_건강보험은행": {
        "label": [1, 0, 0],
        "count": 50,
        "description": "건강보험공단/은행 직원 사칭",
        "patterns": [
            "건강보험공단 환급 명목",
            "은행 법무팀/보안팀 사칭",
            "계좌 이상거래 감지 명목",
            "대출 심사 완료 명목",
            "보안카드 재발급 명목"
        ],
        "examples": [
            "국민건강보험공단입니다. 과납된 보험료 환급이 있으신데 처리가 안 되고 있어서요. 계좌번호랑 주민번호 뒷자리 확인 부탁드립니다.",
            "안녕하세요, OO은행 보안팀입니다. 고객님 계좌에서 이상거래가 감지됐습니다. 본인 확인을 위해 OTP 번호를 말씀해 주세요.",
            "OO은행 법무팀입니다. 고객님 명의로 대출 사기 피해가 발생하여 긴급 확인이 필요합니다."
        ]
    },

    # ── 금전요구 ─────────────────────────────────────────
    "금전요구_계좌이체": {
        "label": [0, 1, 0],
        "count": 80,
        "description": "계좌이체/송금 직접 요구",
        "patterns": [
            "국가안전계좌/안전계좌로 즉시 이체",
            "예금 보호 명목으로 다른 계좌로 이동",
            "공탁금/보증금 납부 요구",
            "범죄 혐의 탈피 위한 이체 유도",
            "피해자 입증 비용 선납 요구"
        ],
        "examples": [
            "지금 바로 국가안전계좌로 송금하지 않으면 계좌가 동결됩니다. 오늘 오후 3시가 마감이에요.",
            "예금 보호를 위해 현재 계좌의 돈을 저희가 안내하는 안전계좌로 옮겨두셔야 합니다.",
            "공탁금 300만원을 납부하시면 구속 수사에서 약식 조사로 전환됩니다. 오늘 중으로 이체하셔야 해요."
        ]
    },

    "금전요구_현금인출": {
        "label": [0, 1, 0],
        "count": 70,
        "description": "현금 인출 후 전달 요구",
        "patterns": [
            "FIU 기준 회피 명목 분산 인출",
            "현금 인출 후 직원 방문 수거",
            "현금 서류봉투 포장 후 퀵 발송",
            "ATM 인출 한도 분산 안내",
            "현금 인출 이유 제공 (푸드트럭 계약금 등)"
        ],
        "examples": [
            "1천만원 이상 한 번에 출금하면 FIU에 자동 신고되니 은행별로 900만원씩 나눠서 출금하셔야 해요.",
            "현금을 서류봉투에 넣으시고 앞면에 성함이랑 날짜 적어두세요. 저희 직원이 방문해서 회수해 드릴 겁니다.",
            "인테리어 업체 계약금이 필요하다고 하시면서 현금으로 찾으시면 됩니다. 은행 직원이 물어보면 그렇게 말씀하세요."
        ]
    },

    "금전요구_대출빙자": {
        "label": [0, 1, 0],
        "count": 60,
        "description": "대출 미끼 / 통장 매입",
        "patterns": [
            "저금리 대환대출 미끼",
            "정부지원 서민대출 명목",
            "신용점수 올려준다며 먼저 상환 요구",
            "취업/부업 미끼로 통장 양도 유도",
            "대출 심사비/공증비 선납 요구"
        ],
        "examples": [
            "정부 지원 서민 대출 상품이 나왔는데요. 기존 대출을 먼저 일부 상환하시면 더 낮은 금리로 갈아탈 수 있어요. 지금 바로 50만원만 이체해 주시겠어요?",
            "신용등급을 올려드릴 수 있는데 먼저 현재 대출 이력을 정리하셔야 해요. 저희 계좌로 200만원 보내주시면 처리해 드릴게요.",
            "재택 부업 채용됐는데요, 회사 자금 관리를 위해 본인 명의 통장이 필요해요. 통장이랑 카드 보내주시면 월 50만원 드릴게요."
        ]
    },

    "금전요구_가족사칭": {
        "label": [0, 1, 0],
        "count": 50,
        "description": "가족 사칭 (AI 딥페이크 포함)",
        "patterns": [
            "자녀/부모 목소리 위장 사고 상황",
            "AI 음성으로 가족 흉내",
            "급전 필요 상황 연출",
            "송금 후 확인 불가 유도",
            "카카오페이/토스 즉시 송금 요구"
        ],
        "examples": [
            "엄마 나야 나 지금 사고 났어. 병원에 있는데 돈이 급해. 100만원만 빨리 보내줘. 자세한 건 나중에 설명할게.",
            "아버지 저 친구 보증 잘못 서서 오늘 당장 돈이 필요해요. 300만원만 이 계좌로 먼저 보내주시면 내일 바로 갚을게요.",
            "엄마 핸드폰 고장나서 친구꺼 빌렸어. 지금 급하니까 일단 카카오페이로 200만원만 보내줘."
        ]
    },

    # ── 개인정보 ─────────────────────────────────────────
    "개인정보_금융정보": {
        "label": [0, 0, 1],
        "count": 70,
        "description": "금융정보 직접 탈취",
        "patterns": [
            "카드번호/유효기간/CVC 요구",
            "OTP/인증번호 요구",
            "인터넷뱅킹 비밀번호 요구",
            "공인인증서 재발급 유도",
            "보안카드 번호 요구"
        ],
        "examples": [
            "본인 확인을 위해 사용하시는 카드 앞면 번호랑 뒷면 세 자리 숫자 말씀해 주시겠어요?",
            "지금 문자로 인증번호 발송했는데요, 수신하신 번호 바로 알려주세요. 시간이 촉박합니다.",
            "공인인증서를 재발급해 드려야 하는데 기존 비밀번호 확인이 필요합니다. 현재 비밀번호 말씀해 주시겠어요?"
        ]
    },

    "개인정보_신분증영상": {
        "label": [0, 0, 1],
        "count": 60,
        "description": "신분증/영상 탈취",
        "patterns": [
            "신분증 앞면 사진 요구",
            "얼굴+신분증 영상 요구",
            "운전면허증/여권 사본 요구",
            "셀카+주민번호 영상 요구",
            "카카오톡/문자로 전송 요도"
        ],
        "examples": [
            "본인 확인 절차상 신분증 앞면 사진을 지금 바로 카카오톡으로 보내주셔야 합니다.",
            "신분증 손에 들고 얼굴 옆에 대고 오늘 날짜랑 성함 말씀하시면서 5초짜리 영상 찍어서 보내주세요.",
            "주민등록증이나 운전면허증 앞면을 사진 찍어서 문자로 보내주시면 바로 확인해 드리겠습니다."
        ]
    },

    "개인정보_통장대포통장": {
        "label": [0, 0, 1],
        "count": 60,
        "description": "통장/체크카드 탈취 (대포통장)",
        "patterns": [
            "취업 미끼 통장 양도",
            "수사 협조 명목 체크카드 전달",
            "대출 조건으로 통장 제출",
            "통장 개설 후 전달 요구",
            "글로벌 체크카드 개설 유도"
        ],
        "examples": [
            "재택 알바인데요, 회사 자금을 잠깐 관리해주실 분 구합니다. 본인 명의 통장이랑 체크카드만 있으면 돼요. 하루 10만원 드려요.",
            "대출 심사 완료됐는데 본인 명의 통장으로 먼저 입금해 드려야 해서요. 통장이랑 체크카드를 택배로 보내주시면 됩니다.",
            "수사 협조 차원에서 체크카드를 저희 직원에게 잠시 맡겨주셔야 합니다. 수사 완료 후 바로 돌려드립니다."
        ]
    },

    "개인정보_악성앱": {
        "label": [0, 0, 1],
        "count": 50,
        "description": "악성앱 설치 유도",
        "patterns": [
            "기존 앱 해킹 명목 삭제 후 재설치",
            "보안 업데이트 명목 링크 전송",
            "원격제어 앱 설치 유도 (팀뷰어 등)",
            "공식 앱스토어 외 APK 설치",
            "금감원/경찰 공식앱 위장"
        ],
        "examples": [
            "고객님 현재 사용 중인 은행 앱이 해킹된 것으로 확인됩니다. 지금 바로 삭제하시고 제가 문자로 보내드리는 링크로 새로 설치하세요.",
            "보안 강화를 위해 팀뷰어 앱을 설치해 주시면 저희가 원격으로 안전하게 처리해 드리겠습니다.",
            "금융감독원 공식 보안 앱 설치가 필요합니다. 문자로 발송해 드린 링크 클릭하셔서 설치해 주세요."
        ]
    },

    # ── 정상 ─────────────────────────────────────────────
    "정상_일상대화": {
        "label": [0, 0, 0],
        "count": 60,
        "description": "일상적인 전화 통화",
        "patterns": [
            "가족 간 안부 / 일정 확인",
            "친구/지인 간 약속",
            "직장 동료 업무 연락",
            "배달/택배 수령",
            "병원/가게 예약"
        ],
        "examples": [
            "엄마 나 오늘 저녁에 좀 늦을 것 같아. 밥 먼저 먹고 있어.",
            "여보세요 내일 오후 2시에 예약했는데 혹시 시간 변경 가능한가요?",
            "안녕하세요 주문한 택배 언제쯤 도착하나요?"
        ]
    },

    "정상_금융기관실제": {
        "label": [0, 0, 0],
        "count": 40,
        "description": "실제 금융기관 정상 연락",
        "patterns": [
            "카드 실적 안내",
            "대출 만기 안내",
            "보험료 납부 안내",
            "계좌 개설 완료 안내",
            "이벤트/혜택 안내"
        ],
        "examples": [
            "안녕하세요 OO카드 고객센터입니다. 이번 달 실적 관련 혜택 안내 드리려고 연락드렸어요.",
            "OO생명보험입니다. 이번 달 보험료 자동이체 예정일 안내드립니다. 15일에 출금 예정입니다.",
            "OO은행입니다. 신청하신 계좌 개설이 완료되었습니다. 영업점 방문 없이 앱에서 바로 이용하실 수 있습니다."
        ]
    }
}

def generate_batch(category: str, template: dict) -> list:
    """카테고리별 증강 데이터 생성"""
    
    patterns_str = "\n".join([f"- {p}" for p in template["patterns"]])
    examples_str = "\n".join([f"- {e}" for e in template["examples"]])
    n = template["count"]
    label = template["label"]
    
    results = []
    
    for i in range(n):
        for retry in range(3):
            try:
                res = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{
                        "role": "user",
                        "content": f"""실제 보이스피싱 또는 정상 전화 통화 발화 1개를 생성해줘.
유형: {template["description"]}

실제 수법 패턴:
{patterns_str}

실제 사례 예시 (그대로 복사 금지):
{examples_str}

조건:
- 실제 통화에서 나올 법한 자연스러운 한국어
- 2~5문장
- 매번 다른 상황/표현 사용
- 구체적인 기관명/금액/상황 포함

아래 JSON 형식만 출력:
{{"text": "발화 내용", "label": {label}, "category_detail": "{category}"}}"""
                    }],
                    temperature=0.9
                )
                
                raw = res.choices[0].message.content.strip()
                raw = raw.replace("```json", "").replace("```", "").strip()
                
                start = raw.find('{')
                end = raw.rfind('}')
                if start != -1 and end != -1:
                    data = json.loads(raw[start:end+1])
                    data["source"] = "augmented_v2"
                    results.append(data)
                    break
                    
            except Exception as e:
                if retry < 2:
                    time.sleep(2)
                else:
                    print(f"  스킵 ({e})")
        
        if (i + 1) % 20 == 0:
            print(f"  [{category}] {i+1}/{n} 완료")
        
        time.sleep(0.3)
    
    return results


def run():
    DATA_ROOT = Path(__file__).parent.parent / "data"
    DIR_V1  = DATA_ROOT / "v1"
    DIR_V2  = DATA_ROOT / "v2"
    DIR_RAW = DATA_ROOT / "raw"
    DIR_V2.mkdir(exist_ok=True)
    AUG_FILE = DIR_V2 / "augmented.json"

    # v1 데이터 로드 (소스)
    all_existing = []
    for fname in ["train_ml.json", "val_ml.json", "test_ml.json"]:
        try:
            all_existing.extend(json.loads((DIR_V1 / fname).read_text(encoding='utf-8')))
        except Exception:
            pass

    # KBS 실제 발화 로드
    try:
        kbs = json.loads((DIR_RAW / "kbs_utterance_dataset.json").read_text(encoding='utf-8'))
        all_existing.extend([{"text": d["text"], "label": d["label"], "source": "KBS_real"} for d in kbs])
    except Exception:
        pass

    print(f"기존 데이터: {len(all_existing)}개")

    # 예상 총 증강 수
    total_aug = sum(t["count"] for t in AUGMENT_TEMPLATES.values())
    print(f"증강 예정: {total_aug}개")
    print(f"완료 후 예상 총합: {len(all_existing) + total_aug}개\n")

    # 증강 실행
    all_augmented = []
    for category, template in AUGMENT_TEMPLATES.items():
        print(f"[{category}] {template['count']}개 시작...")
        batch = generate_batch(category, template)
        all_augmented.extend(batch)
        print(f"[{category}] {len(batch)}개 완료")

        # 중간 저장
        AUG_FILE.write_text(json.dumps(all_augmented, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"\n증강 완료: {len(all_augmented)}개")

    # 전체 합치기
    all_data = all_existing + all_augmented
    print(f"전체: {len(all_data)}개")

    # 라벨 분포
    import numpy as np
    labels = np.array([d['label'] for d in all_data])
    print(f"\n기관사칭: {labels[:, 0].sum()}개")
    print(f"금전요구: {labels[:, 1].sum()}개")
    print(f"개인정보: {labels[:, 2].sum()}개")
    print(f"정상:     {(labels.sum(axis=1) == 0).sum()}개")

    # 재분할 후 v2 저장
    from sklearn.model_selection import train_test_split
    import random
    random.seed(42)
    random.shuffle(all_data)

    train, temp = train_test_split(all_data, test_size=0.2, random_state=42)
    val, test   = train_test_split(temp, test_size=0.5, random_state=42)

    for fname, data in [("train_ml.json", train), ("val_ml.json", val), ("test_ml.json", test)]:
        (DIR_V2 / fname).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"{DIR_V2 / fname} 저장 완료 ({len(data)}개)")

    print("\n✅ 완료! KoELECTRA v2 재학습 준비 됐어요")


if __name__ == "__main__":
    run()
