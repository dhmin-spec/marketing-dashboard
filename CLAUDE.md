# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

키워드 광고 성과 CSV를 받아 키워드별 효율 지표(CTR·CVR·CPA·ROAS) 추이를 시각화하는 대시보드. **같은 로직을 두 프론트엔드로 구현**한다:

- **HTML 버전** (`dashboard.html` + `lib/metrics.js`) — Vanilla JS ESM, 빌드 없음. CDN으로 ECharts·PapaParse 로드, 게시된 구글 시트 CSV URL을 fetch.
- **Streamlit 버전** (`streamlit_app.py`) — CSV 업로드 또는 샘플 파일 사용, altair 차트.

두 버전은 **지표 정의·집계 규칙이 반드시 동일**해야 한다 (`lib/metrics.js` ↔ `streamlit_app.py`의 `parse_rows`/`derive`/`aggregate_keywords`). 한쪽을 고치면 다른 쪽도 맞춰야 한다.

## 핵심 데이터 규칙 (양쪽 공통, 절대 어기지 말 것)

- **집계는 합산 후 비율 재계산 (가중평균).** 단순 평균 금지. 예: CTR = Σclick / Σimpression.
- **분모 0인 파생 지표는 결측** — JS는 `null`, Python은 `NaN`, 화면 표기는 `-`.
- **매출은 숫자 컬럼 `매출`을 사용.** `sales` 컬럼은 포맷 문자열이라 쓰지 않는다.
- **숫자 파싱**: 천단위 콤마 제거, `-`/빈칸/null → 0.
- **keyword 없는 행은 제거.**
- 합산 대상 필드(`SUM_FIELDS`): `impression, click, cost, connection, input, complete, conclusion, revenue`.
- 파생 지표: `ctr=click/impression`, `cpc=cost/click`, `cvr=conclusion/click`, `cpa=cost/conclusion`, `roas=매출/cost`.

## 명령어

```bash
# 데이터 로직 단위 테스트 (HTML 버전) — 지표/집계 수정 시 반드시 실행
node --test
node --test test/metrics.test.mjs   # 단일 파일

# HTML 대시보드 실행 (ESM import 때문에 file:// 직접 열기 불가, 로컬 서버 필요)
python -m http.server 8000          # → http://localhost:8000/dashboard.html

# Streamlit 대시보드 실행 (키워드 버전)
streamlit run streamlit_app.py

# 퍼포먼스 마케팅 대시보드 (채널 × 앱스플라이어)
.venv/Scripts/streamlit run mkt_dashboard.py --server.port 8502

# 파이프라인 단독 실행(합본 생성) — 전처리 로직 수정 시 확인
python mkt_pipeline.py data/raw
```

- Python 의존성: `requirements.txt` (streamlit, pandas). altair는 streamlit과 함께 설치됨. `.venv/` 사용.
- HTML 버전은 별도 빌드/설치 없음. 배포 시 `dashboard.html` + `styles.css` + `lib/metrics.js` 세 파일만 정적 호스팅에 올리면 동작.

## 퍼포먼스 마케팅 데이터 파이프라인 (일별 채널 × 앱스플라이어)

매일 채널(매체) 로우와 앱스플라이어(MMP) 로우를 업로드 → 조인 → 전처리 → 인사이트.
전처리 엔진 `mkt_pipeline.py`, 대시보드 `mkt_dashboard.py`. **둘 다 폴더를 재귀 탐색**한다.

### 폴더·파일 규칙 (자세히는 `data/README.md`)

- 로우 데이터는 `data/raw/channel/`, `data/raw/appsflyer/`에 소스별로 둔다. 합본은 `data/processed/`.
- 파일명 규칙: `YYYY-MM-DD_channel.csv` / `YYYY-MM-DD_appsflyer.csv` (날짜_소스). 인코딩 UTF-8(cp949 자동인식).
- **매일 하는 일**: 전날 파일 2개를 각 폴더에 규칙대로 넣기 → 대시보드 새로고침이면 폴더 전체 자동 재처리. 별도 데몬 불필요.

### 조인·전처리 규칙 (절대 어기지 말 것)

- **조인키**: `일 · 채널 · 캠페인 · 그룹 · 소재` 5개로 OUTER JOIN (한쪽만 있는 행도 보존해 누락 탐지).
- **채널명 매핑 필수**: AF의 `미디어소스`는 채널 파일의 `채널`과 표기가 다르다. `mkt_pipeline.py`의 `AF_TO_CHANNEL`로 매핑(`googleadwords_int→구글`, `Facebook Ads→메타`, `naver_search→네이버`). **신규 매체는 여기 추가** — 누락 시 대시보드 상단 경고.
- **집계는 합산 후 비율 재계산(가중평균).** 단순 평균 금지 (키워드 버전과 동일 원칙).
- **분모 0 파생 지표는 결측(NaN → 화면 `-`).** 숫자 파싱: 콤마 제거, `-`/빈칸/null → 0.
- 겹치는 성과지표는 `_매체`/`_af` 접미사로 구분(클릭·회원가입·구매·구매매출). 노출·비용은 채널에만 존재.
- 파생: `CTR=클릭/노출`, `CPC=비용/클릭`, `CPA=비용/구매`, `ROAS=구매매출/비용`. 갭%=`(매체-AF)/매체`.

### 스키마 계약

- channel: `일, 채널, 채널분류, 캠페인, 캠페인목적, 그룹, 소재, 노출, 클릭, 비용, 회원가입, 구매, 구매매출`
- appsflyer: `일, 미디어소스, 캠페인, 그룹, 소재, 클릭, 회원가입, 구매, 구매매출` (노출·비용 없음, 전환 중심)
- 컬럼이 바뀌면 `mkt_pipeline.py`의 `SUM/GAP_METRICS`와 이 문서를 함께 갱신.

### 네이밍 컨벤션

- **소재/캠페인/그룹 코드 문법 정의는 `docs/conventions/naming-convention.md`가 원본.** 소재 유형 분류(prefix `VID/IMG/CRS/TXT`)·AB테스트·시즌/카테고리 파싱이 여기 규칙에 의존한다.
- 이 문서를 고치면 `mkt_pipeline.py`/`mkt_dashboard.py`의 파싱 로직도 맞춘다.

### 인사이트·자동화 경계

- `mkt_dashboard.py`의 `generate_insights()`는 **규칙 기반(수치 정확, LLM 추정 금지)**. 임계값(ROAS 목표·갭 경고선 등)은 `docs/conventions/naming-convention.md` 또는 별도 KPI 문서 기준을 따른다.
- **예산 재배분·소재 교체·카피 결정은 사람 검수 필수** — 인사이트는 근거 제시까지, 실행 결정은 무인 자동화 금지.

## 데이터 소스 설정

- **HTML**: `dashboard.html` 상단 상수 `CSV_URL` 한 곳에서만 관리. 구글 시트 → 파일 → 공유 → 웹에 게시 → CSV 링크를 붙여넣는다.
- **Streamlit**: 사이드바에서 CSV 업로드, 없으면 `test/fixtures/sample.csv`를 샘플로 로드.

## MCP·브라우저 자동화

`.mcp.json`에 두 서버가 설정돼 있다:

- **google-sheets** — 시트 읽기/쓰기. OAuth 자격증명은 `.claude/google/` (gitignore됨), 설정은 `.claude/.env` 참조.
- **playwright** — `--cdp-endpoint=http://127.0.0.1:9222`로 **이미 떠 있는 로컬 크롬**에 붙는다.

브라우저로 실제 사이트 데이터를 수집할 때 (예: 네이버쇼핑 — curl_cffi 직접 요청은 캡차에 막힌다), 실브라우저 CDP 세션(원격 디버깅 포트 9222)을 통해 우회한다. `browser-harness`(`uv tool`로 설치)도 같은 9222 포트에 CDP로 붙어 `js()`/`goto_url()`/`scroll()` 등 헬퍼로 DOM을 추출하는 데 쓴다. 네이버쇼핑 검색결과는 **가상 스크롤**이라 `window.scrollTo`로 촘촘히 내리며 `data-shp-contents-*` 속성을 수집해야 누락 없이 잡힌다.

## 참고

- 승인된 계획·설계 문서는 `docs/superpowers/`에 있다 (plans/, specs/). 대시보드 요구사항의 원본 근거.
- UI 라벨은 한국어, 코드 식별자·컬럼명은 영어.
- 테마 컬러: 포인트 블루 `#3b5bdb`, 효율 좋음=초록 `#16a34a`, 나쁨=빨강 `#dc2626`.
