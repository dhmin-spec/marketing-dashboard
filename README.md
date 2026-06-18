# 키워드 효율 추이 대시보드

## 설정 (1회)
1. 구글 시트 → 파일 → 공유 → 웹에 게시 → 해당 탭 선택, 형식 **CSV** → 게시 → 링크 복사.
2. `dashboard.html` 상단 `CSV_URL` 상수에 그 링크를 붙여넣기.

## 실행
ES 모듈 import 때문에 `file://`로 직접 열면 안 되고 로컬 서버가 필요합니다:
```
python -m http.server 8000
```
브라우저에서 http://localhost:8000/dashboard.html

또는 정적 호스팅(Vercel/Netlify/GitHub Pages/구글 사이트 등)에 `dashboard.html`, `styles.css`, `lib/metrics.js`를 함께 올리면 됩니다.

## 데이터 갱신
시트를 수정하면 게시 CSV가 몇 분 내 반영됩니다. 대시보드는 새로고침 시 최신값을 불러옵니다.

## 테스트
```
node --test
```

## 지표 정의
- CTR = click/impression, CPC = cost/click, CVR = conclusion/click, CPA = cost/conclusion, ROAS = 매출/cost
- 집계는 합산 후 비율 재계산(가중평균). 분모 0은 `-`로 표기.
