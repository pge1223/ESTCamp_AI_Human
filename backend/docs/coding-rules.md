# 코딩 규칙

## 기본 원칙

| 규칙 | 내용 |
|------|------|
| 비동기 | 모든 API 함수는 `async def` |
| 타입 힌트 | 모든 함수 파라미터·반환값에 타입 필수 |
| 입출력 검증 | Pydantic 스키마로 통일 |
| 에러 처리 | `HTTPException` 으로 통일 |
| 로깅 | `logging` 모듈 사용 (print 금지) |
| 주석 | 한국어 작성 |

---

## API 엔드포인트 작성 패턴

```python
import logging
import uuid
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.world import World
from app.schemas.world import WorldCreate, WorldResponse

router = APIRouter()
logger = logging.getLogger(__name__)  # 모듈별 로거


@router.post("/", response_model=WorldResponse, status_code=201)
async def create_world(
    user_id: uuid.UUID,
    body: WorldCreate,                    # 입력값 → 스키마로 자동 검증
    db: AsyncSession = Depends(get_db),   # DB 세션 의존성 주입
):
    world = World(user_id=user_id, **body.model_dump())
    db.add(world)
    await db.flush()
    await db.refresh(world)
    logger.info("세계관 생성: %s (user=%s)", world.id, user_id)  # 로깅
    return world  # 스키마가 자동으로 직렬화
```

---

## 스키마 명명 규칙

| 클래스명 | 용도 |
|---------|------|
| `XXXCreate` | POST 요청 body (생성) |
| `XXXUpdate` | PUT/PATCH 요청 body (수정) — 모든 필드 Optional |
| `XXXResponse` | API 응답 — `model_config = {"from_attributes": True}` 필수 |

```python
# 수정 스키마는 모든 필드를 Optional로
class WorldUpdate(BaseModel):
    title: str | None = None
    description: str | None = None

# 응답 스키마는 from_attributes 필수 (ORM 객체 → Pydantic 변환)
class WorldResponse(BaseModel):
    id: uuid.UUID
    title: str
    ...
    model_config = {"from_attributes": True}
```

---

## 에러 처리

```python
# 리소스 없음
if not world:
    raise HTTPException(status_code=404, detail="세계관을 찾을 수 없습니다.")

# 중복
if existing:
    raise HTTPException(status_code=409, detail="이미 존재합니다.")

# 상태 불일치
if session.status != SessionStatus.ACTIVE:
    raise HTTPException(status_code=400, detail="활성화된 세션이 아닙니다.")
```

| 상태 코드 | 사용 상황 |
|---------|---------|
| `400` | 잘못된 요청, 상태 불일치 |
| `404` | 리소스 없음 |
| `409` | 중복 충돌 |
| `422` | Pydantic 자동 처리 (입력값 형식 오류) |

---

## DB 조작 패턴

```python
# 조회
result = await db.execute(select(World).where(World.id == world_id))
world = result.scalar_one_or_none()   # 없으면 None 반환

# 생성
obj = MyModel(**data)
db.add(obj)
await db.flush()     # DB에 SQL 전송 (커밋 전)
await db.refresh(obj) # DB에서 최신값 다시 읽기 (id, created_at 등)

# 수정
for field, value in body.model_dump(exclude_none=True).items():
    setattr(obj, field, value)
await db.flush()
await db.refresh(obj)

# 삭제
await db.delete(obj)
# (get_db에서 자동 commit)
```

> `get_db()` 가 요청 성공 시 자동으로 `commit`, 실패 시 자동으로 `rollback` 처리함

---

## 로깅

```python
import logging
logger = logging.getLogger(__name__)

# 정상 동작
logger.info("세계관 생성: %s (user=%s)", world.id, user_id)

# 경고 (동작은 하지만 주의 필요)
logger.warning("캐시 조회 실패: %s", e)

# 에러 (예외 발생)
logger.error("LLM 호출 실패: %s", e)
```

- `%s` 포맷 사용 (f-string 아님) — 로그 레벨 필터링 시 성능상 유리
- `print()` 사용 금지

---

## 모델 작성 규칙

```python
import uuid
from datetime import datetime
from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class MyModel(Base):
    __tablename__ = "my_models"  # 소문자 + 복수형

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
```

- PK는 항상 UUID
- `created_at` 은 `func.now()` (DB 서버 시간 기준)
- `updated_at` 이 필요한 경우 `onupdate=func.now()` 추가

---

## 브랜치 전략

```
main (배포)
  └── dev (개발 통합) ← PR 필수 · 전원 1승인 · merge-commit(squash 비활성)
        ├── feature/jyj    ← 작성자별 브랜치
        ├── feature/pge
        ├── feature/ygh
        └── feature/ygy
```

- `feature/* → dev`: PR 올리고 **CI(Vercel·test) green + 1승인** 후 머지. 충돌은 양쪽 기능 보존.
- `dev → main`: 배포 시점에 통합.

커밋 메시지 형식:
```
feat: 새로운 기능 추가
fix: 버그 수정
refactor: 코드 리팩토링 (기능 변경 없음)
docs: 문서 작성/수정
chore: 설정, 패키지 등 기타 변경
```

예시:
```
feat: World CRUD API 추가
fix: 세션 완료 시 ended_at 미기록 버그 수정
docs: API 명세 작성
```
