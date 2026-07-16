# 마케팅 데이터 폴더 규칙

일별 로우 데이터를 소스별로 관리합니다. 파이프라인(`mkt_pipeline.py`)과
대시보드(`mkt_dashboard.py`)가 이 폴더를 **재귀 탐색**해 자동으로 합칩니다.

## 구조

```
data/
├── raw/                         # 로우 데이터 (원본, 손대지 않음)
│   ├── channel/                 # 채널(매체) 집행 데이터
│   │   └── YYYY-MM-DD_channel.csv
│   └── appsflyer/               # 앱스플라이어(MMP) 어트리뷰션 데이터
│       └── YYYY-MM-DD_appsflyer.csv
└── processed/                   # 파이프라인이 생성하는 합본
    └── _combined.parquet
```

## 매일 하는 일 (딱 하나)

전날 데이터를 각 폴더에 파일명 규칙대로 넣기만 하면 됩니다:

- 채널: `data/raw/channel/2025-01-02_channel.csv`
- 앱스플라이어: `data/raw/appsflyer/2025-01-02_appsflyer.csv`

→ 대시보드를 열거나 "🔄 새로고침"만 누르면 폴더 전체를 다시 읽어 자동 반영됩니다.

## 파일 규칙

- **파일명**: `YYYY-MM-DD_channel.csv` / `YYYY-MM-DD_appsflyer.csv` (날짜_소스)
- **인코딩**: UTF-8 (BOM 허용). cp949도 자동 인식.
- **필수 컬럼**
  - channel: `일, 채널, 채널분류, 캠페인, 캠페인목적, 그룹, 소재, 노출, 클릭, 비용, 회원가입, 구매, 구매매출`
  - appsflyer: `일, 미디어소스, 캠페인, 그룹, 소재, 클릭, 회원가입, 구매, 구매매출`
- **조인키**: `일 · 채널 · 캠페인 · 그룹 · 소재`
  - 채널명 매핑: `googleadwords_int→구글`, `Facebook Ads→메타`, `naver_search→네이버`
    (신규 매체는 `mkt_pipeline.py`의 `AF_TO_CHANNEL`에 추가)

## 배치 자동화 (선택)

야간에 합본 parquet를 미리 생성하려면:

```bash
python mkt_pipeline.py data/raw
```
Windows 작업 스케줄러에 등록하면 매일 자동 실행됩니다.
