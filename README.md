# Code Bot

RAG 기반 코드베이스 Q&A 봇

## 개요

코드베이스에 대한 질문에 답변하는 RAG(Retrieval Augmented Generation) 시스템입니다.
비개발자(PM, 기획자, 디자이너)도 이해할 수 있는 친근한 답변을 제공합니다.

### 주요 기능

- **코드베이스 Q&A**: 코드 동작 방식, 정책, 구현 세부사항에 대한 질문 답변
- **Analytics 이벤트 분석**: 이벤트 데이터 조회 + 코드에서 해당 이벤트 발송 시점 설명

## 기술 스택

| 구성요소 | 기술 |
|---------|------|
| API 서버 | FastAPI / Uvicorn |
| 벡터 DB | ChromaDB |
| 임베딩 | Jina Code v2 (MPS/CUDA 가속 지원) |
| 리랭킹 | FlashRank |
| LLM | OpenAI 호환 API |
| 프레임워크 | LangChain |

## 동작 흐름

### 코드베이스 Q&A

```
[질문] → [한국어→영어 번역] → [벡터 검색 top K] → [리랭킹 top N] → [답변 생성]
```

### Analytics 이벤트 분석

```
[질문] → [이벤트명 추출] → [Analytics 데이터 조회] + [코드베이스 검색] → [통합 답변 생성]
```

---

## 1. 환경 설정

### Python 환경

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 환경 변수

```bash
cp .env.example .env
# .env 파일 편집
```

---

## 2. 코드베이스 인덱싱

```bash
python scripts/build_index.py --reset
```

다른 저장소 인덱싱:
```bash
# .env 수정
CODEBASE_PATH=/path/to/new-repo
COLLECTION_NAME=new-repo-codebase

# 재인덱싱
python scripts/build_index.py --reset
```

### 인덱싱 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--codebase-path` | 인덱싱할 코드베이스 경로 | .env의 CODEBASE_PATH |
| `--reset` | 기존 인덱스 삭제 후 재생성 | false |
| `--chunk-size` | 청크 최대 크기 (문자) | 1000 |
| `--chunk-overlap` | 청크 오버랩 (문자) | 200 |
| `--batch-size` | 벡터 DB 추가 배치 크기 | 100 |
| `--log-level` | 로그 레벨 | INFO |

---

## 3. 서버 실행 및 종료

### 실행

```bash
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 >> ~/rag-server.log 2>&1 &
```

### 상태 확인

```bash
curl -s http://localhost:8000/api/health
```

### 종료

```bash
pkill -f "uvicorn app.main:app"
```

### 로그 확인

```bash
tail -f ~/rag-server.log
```

---

## API

### GET /api/health

헬스체크 엔드포인트

```bash
curl -s http://localhost:8000/api/health
# {"status":"ok","service":"code-bot-api"}
```

### POST /api/codebase

코드베이스에 대한 질문 답변

```bash
curl -X POST http://localhost:8000/api/codebase \
  -H "Content-Type: application/json" \
  -d '{"question": "비밀번호 변경 팝업 노출 주기는?"}'
```

**Request Body**
| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `question` | string | Y | 코드베이스 관련 질문 |
| `top_k` | int | N | 벡터 검색 문서 수 (1-500) |
| `rerank_top_n` | int | N | 리랭킹 후 유지할 문서 수 (1-100) |

**Response**
```json
{
  "answer": "비밀번호 변경 팝업은...",
  "sources": ["app/src/main/java/PasswordPolicy.kt"]
}
```

### POST /api/analytics

이벤트 데이터 분석 + 코드 설명

```bash
curl -X POST http://localhost:8000/api/analytics \
  -H "Content-Type: application/json" \
  -d '{"question": "screen_view_home 이벤트 분석해줘", "days": 7}'
```

**Request Body**
| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `question` | string | Y | 분석할 이벤트 관련 질문 |
| `days` | int | N | 분석 기간 (1-90일, 기본: 7) |

**Response**
```json
{
  "answer": "📊 *이벤트 데이터 분석*\n...",
  "sources": ["app/src/main/kotlin/EventTracker.kt"],
  "event_name": "screen_view_home"
}
```

---

## 프로젝트 구조

```
code-bot/
├── app/
│   ├── main.py              # FastAPI 앱 엔트리포인트
│   ├── config.py            # 환경 설정 (Pydantic Settings)
│   ├── api/
│   │   └── routes.py        # API 엔드포인트 (/codebase, /analytics, /health)
│   ├── core/
│   │   ├── index.py         # CodebaseIndexer - 코드베이스 인덱싱
│   │   └── search.py        # CodebaseSearch - 벡터 검색 + 리랭킹
│   ├── services/
│   │   ├── codebase/
│   │   │   └── answer.py    # CodebaseAnswerGenerator - 코드 Q&A 답변 생성
│   │   └── analytics/
│   │       ├── answer.py    # AnalyticsAnswerGenerator - 이벤트 분석 답변 생성
│   │       └── data_source.py  # AnalyticsDataSource - 외부 Analytics API 연동
│   └── prompts/
│       ├── base.py          # 공통 프롬프트 (Slack 포맷, 보안 규칙, 가이드라인)
│       ├── codebase.py      # 코드베이스 Q&A 프롬프트
│       └── analytics.py     # Analytics 분석 프롬프트
├── scripts/
│   └── build_index.py       # 인덱싱 CLI 스크립트
├── data/chroma/             # 벡터 DB 저장소 (gitignored)
├── requirements.txt
├── TUNNEL.md                # Cloudflare Tunnel 가이드
├── .env                     # 환경 설정 (gitignored)
└── .env.example             # 환경 설정 템플릿
```

---

## 환경 변수

모든 설정은 `.env` 파일에서 관리합니다. `.env.example`을 참고하세요.

### LLM 설정

| 변수 | 설명 | 예시 |
|------|------|------|
| `LLM_API_KEY` | API 키 | `sk-...` |
| `LLM_BASE_URL` | API 엔드포인트 | `https://api.openai.com/v1` |
| `LLM_MODEL` | 모델명 | `gpt-4o-mini` |

### 임베딩 설정

| 변수 | 설명 | 예시 |
|------|------|------|
| `EMBEDDING_MODEL` | 임베딩 모델 | `jinaai/jina-embeddings-v2-base-code` |
| `EMBEDDING_DEVICE` | 디바이스 | `cpu`, `cuda`, `mps` |

### 리랭킹 설정

| 변수 | 설명 | 예시 |
|------|------|------|
| `RERANK_MODEL` | 리랭커 모델 | `ms-marco-MiniLM-L-12-v2` |
| `RERANK_TOP_N` | 리랭킹 후 반환할 문서 수 | `30` |
| `RERANK_MAX_LENGTH` | 리랭킹 입력 최대 길이 | `128` |
| `RETRIEVE_TOP_K` | 벡터 검색 시 가져올 문서 수 | `100` |

### 코드베이스 설정

| 변수 | 설명 | 예시 |
|------|------|------|
| `CODEBASE_PATH` | 인덱싱할 코드베이스 경로 | `/path/to/android-app` |
| `COLLECTION_NAME` | ChromaDB 컬렉션 이름 | `my-app-codebase` |
| `CHROMA_DB_PATH` | ChromaDB 저장 경로 | `./data/chroma` |

### Analytics 설정

| 변수 | 설명 | 예시 |
|------|------|------|
| `ANALYTICS_GATEWAY_URL` | Analytics 데이터 게이트웨이 URL | `https://analytics-gateway.example.com` |

### API 설정

| 변수 | 설명 | 예시 |
|------|------|------|
| `API_HOST` | 서버 호스트 | `0.0.0.0` |
| `API_PORT` | 서버 포트 | `8000` |
| `API_RELOAD` | 자동 리로드 (개발용) | `true` |
| `LOG_LEVEL` | 로그 레벨 | `INFO` |

---

## Cloudflare Tunnel

외부에서 로컬 서버에 접근해야 할 때 Cloudflare Tunnel을 사용할 수 있습니다.
자세한 내용은 [TUNNEL.md](./TUNNEL.md)를 참고하세요.

---

## 라이선스

MIT
