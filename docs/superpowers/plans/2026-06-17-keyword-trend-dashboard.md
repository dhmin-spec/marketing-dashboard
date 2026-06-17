# 키워드 효율 추이 대시보드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 구글 시트(웹게시 CSV)의 여행자보험 키워드 광고 데이터를, 키워드별 효율 지표(CTR·CVR·CPA·ROAS) 추이를 비교하는 단일 HTML 대시보드로 만든다.

**Architecture:** 데이터 로직(파싱·집계·파생지표)은 순수 함수 ESM 모듈 `lib/metrics.js`로 분리해 `node --test`로 단위 테스트한다. `dashboard.html`은 CDN으로 ECharts·PapaParse를 로드하고 `lib/metrics.js`를 모듈로 import해 KPI·추이차트·랭킹테이블을 렌더한다. 빌드 단계 없음 — 파일을 그대로 열거나 정적 호스팅에 올린다.

**Tech Stack:** Vanilla JS (ES Modules), ECharts (CDN), PapaParse (CDN), Node.js 내장 테스트 러너(`node --test`).

## Global Constraints

- 배포 산출물은 빌드 불필요: `dashboard.html` + `lib/metrics.js` 두 파일만으로 동작.
- 게시된 CSV URL은 `dashboard.html` 상단 상수 `CSV_URL` 1곳에서만 관리.
- 파생 지표 분모가 0이면 값은 `null`(화면 표기 `-`), 차트는 결측 처리.
- 집계는 **합산 후 비율 재계산**(가중평균). 단순 평균 금지. 예: CTR = Σclick / Σimpression.
- 매출은 숫자 컬럼 `매출` 사용(`sales`는 포맷 문자열이라 미사용).
- 숫자 파싱은 천단위 콤마 제거, `-`/빈칸 → 0.
- 표기: 비용·매출 천단위 콤마(₩), 비율 % 소수 1자리.
- 스타일: 라이트 클린(흰/연회색 배경, 부드러운 그림자), 포인트 컬러 블루 `#3b5bdb`. 효율 좋음=초록 `#16a34a`, 나쁨=빨강 `#dc2626`.
- 언어: UI 라벨 한국어, 코드 식별자 영어.

---

### Task 1: 프로젝트 스캐폴드 + 샘플 픽스처 + parseNumber

**Files:**
- Create: `lib/metrics.js`
- Create: `test/metrics.test.mjs`
- Create: `test/fixtures/sample.csv`
- Create: `.gitignore`

**Interfaces:**
- Consumes: (없음)
- Produces: `parseNumber(raw: string|number): number` — 콤마 제거, `-`/빈칸/null → 0.

- [ ] **Step 1: git 초기화 및 .gitignore 작성**

`.gitignore`:
```
node_modules/
.superpowers/
.playwright-mcp/
```

Run:
```bash
cd "C:/Users/MADUP/Desktop/클로드코드" && git init
```
Expected: `Initialized empty Git repository ...`

- [ ] **Step 2: 샘플 CSV 픽스처 작성**

`test/fixtures/sample.csv` (헤더는 실제 시트와 동일, 4행):
```csv
Date,Media,Device,Media_CPC,Part,campaign,adgroup,keyword,Product,impression,click,cost,sum_rank,connection,input,complete,conclusion,sales,매출
2025-10-31,Google,PC,구글_CPC,일반,캠A,그룹A,여행자보험.,G.해외여행,496,64,220475.4108,0,106,40,38,13,"336,481",336481
2025-11-01,Google,PC,구글_CPC,일반,캠A,그룹A,여행자보험.,G.해외여행,376,44,148972.8414,0,85,32,30,10,"258,832",258832
2025-10-31,Google,Mobile,구글_CPC,일반,캠A,그룹A,KB여행자보험,G.해외여행,21,1,3670.139,0,3,1,0,0,-,0
2025-11-01,Naver,PC,네이버_CPC,일반,캠B,그룹B,유럽여행자보험,G.해외여행,4,2,6095.716,0,2,1,1,0,-,0
```

- [ ] **Step 3: parseNumber 실패 테스트 작성**

`test/metrics.test.mjs`:
```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseNumber } from '../lib/metrics.js';

test('parseNumber: 콤마 제거', () => {
  assert.equal(parseNumber('336,481'), 336481);
});
test('parseNumber: 소수 유지', () => {
  assert.equal(parseNumber('220475.4108'), 220475.4108);
});
test('parseNumber: 대시/빈칸/null → 0', () => {
  assert.equal(parseNumber('-'), 0);
  assert.equal(parseNumber(''), 0);
  assert.equal(parseNumber(null), 0);
});
test('parseNumber: 숫자 그대로', () => {
  assert.equal(parseNumber(42), 42);
});
```

- [ ] **Step 4: 테스트 실패 확인**

Run: `node --test`
Expected: FAIL — `parseNumber` is not a function / import 실패.

- [ ] **Step 5: parseNumber 구현**

`lib/metrics.js`:
```javascript
export function parseNumber(raw) {
  if (raw === null || raw === undefined) return 0;
  if (typeof raw === 'number') return Number.isFinite(raw) ? raw : 0;
  const cleaned = String(raw).replace(/,/g, '').trim();
  if (cleaned === '' || cleaned === '-') return 0;
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : 0;
}
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `node --test`
Expected: PASS (4 tests).

- [ ] **Step 7: 커밋**

```bash
git add .gitignore lib/metrics.js test/metrics.test.mjs test/fixtures/sample.csv
git commit -m "feat: scaffold dashboard project with parseNumber"
```

---

### Task 2: parseRows — CSV 레코드를 타입 변환된 행 객체로

**Files:**
- Modify: `lib/metrics.js`
- Modify: `test/metrics.test.mjs`

**Interfaces:**
- Consumes: `parseNumber`.
- Produces: `parseRows(records: object[]): Row[]` — `records`는 PapaParse `header:true` 결과(키=컬럼명). 반환 `Row` 필드:
  `{ date:string, media:string, device:string, campaign:string, adgroup:string, keyword:string, product:string, impression:number, click:number, cost:number, connection:number, input:number, complete:number, conclusion:number, revenue:number }`
  (`revenue`는 `매출` 컬럼.)

- [ ] **Step 1: 실패 테스트 작성**

`test/metrics.test.mjs`에 추가:
```javascript
import { parseRows } from '../lib/metrics.js';

const RAW = [
  { Date:'2025-10-31', Media:'Google', Device:'PC', campaign:'캠A', adgroup:'그룹A',
    keyword:'여행자보험.', Product:'G.해외여행', impression:'496', click:'64',
    cost:'220475.4108', connection:'106', input:'40', complete:'38', conclusion:'13',
    sales:'336,481', '매출':'336481' },
  { Date:'2025-10-31', Media:'Google', Device:'Mobile', campaign:'캠A', adgroup:'그룹A',
    keyword:'KB여행자보험', Product:'G.해외여행', impression:'21', click:'1',
    cost:'3670.139', connection:'3', input:'1', complete:'0', conclusion:'0',
    sales:'-', '매출':'0' },
];

test('parseRows: 필드 타입 변환', () => {
  const rows = parseRows(RAW);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].keyword, '여행자보험.');
  assert.equal(rows[0].impression, 496);
  assert.equal(rows[0].revenue, 336481);
  assert.equal(rows[0].device, 'PC');
  assert.equal(rows[1].conclusion, 0);
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `node --test`
Expected: FAIL — `parseRows` is not a function.

- [ ] **Step 3: parseRows 구현**

`lib/metrics.js`에 추가:
```javascript
export function parseRows(records) {
  return records
    .filter((r) => r && (r.keyword ?? r.Keyword))
    .map((r) => ({
      date: String(r.Date ?? '').trim(),
      media: String(r.Media ?? '').trim(),
      device: String(r.Device ?? '').trim(),
      campaign: String(r.campaign ?? '').trim(),
      adgroup: String(r.adgroup ?? '').trim(),
      keyword: String(r.keyword ?? '').trim(),
      product: String(r.Product ?? '').trim(),
      impression: parseNumber(r.impression),
      click: parseNumber(r.click),
      cost: parseNumber(r.cost),
      connection: parseNumber(r.connection),
      input: parseNumber(r.input),
      complete: parseNumber(r.complete),
      conclusion: parseNumber(r.conclusion),
      revenue: parseNumber(r['매출']),
    }));
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `node --test`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add lib/metrics.js test/metrics.test.mjs
git commit -m "feat: parse CSV records into typed rows"
```

---

### Task 3: deriveMetrics — 합산값에서 파생 지표 계산

**Files:**
- Modify: `lib/metrics.js`
- Modify: `test/metrics.test.mjs`

**Interfaces:**
- Consumes: (없음)
- Produces: `deriveMetrics(t: {impression,click,cost,conclusion,revenue}): {ctr,cpc,cvr,cpa,roas}` — 각 값은 `number|null`(분모 0 → null).
  - ctr = click/impression, cpc = cost/click, cvr = conclusion/click, cpa = cost/conclusion, roas = revenue/cost.

- [ ] **Step 1: 실패 테스트 작성**

```javascript
import { deriveMetrics } from '../lib/metrics.js';

test('deriveMetrics: 정상 계산', () => {
  const m = deriveMetrics({ impression:100, click:10, cost:5000, conclusion:2, revenue:20000 });
  assert.equal(m.ctr, 0.1);
  assert.equal(m.cpc, 500);
  assert.equal(m.cvr, 0.2);
  assert.equal(m.cpa, 2500);
  assert.equal(m.roas, 4);
});
test('deriveMetrics: 분모 0 → null', () => {
  const m = deriveMetrics({ impression:0, click:0, cost:0, conclusion:0, revenue:0 });
  assert.equal(m.ctr, null);
  assert.equal(m.cpc, null);
  assert.equal(m.cvr, null);
  assert.equal(m.cpa, null);
  assert.equal(m.roas, null);
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `node --test`
Expected: FAIL — `deriveMetrics` is not a function.

- [ ] **Step 3: deriveMetrics 구현**

```javascript
const ratio = (num, den) => (den > 0 ? num / den : null);

export function deriveMetrics(t) {
  return {
    ctr: ratio(t.click, t.impression),
    cpc: ratio(t.cost, t.click),
    cvr: ratio(t.conclusion, t.click),
    cpa: ratio(t.cost, t.conclusion),
    roas: ratio(t.revenue, t.cost),
  };
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `node --test`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add lib/metrics.js test/metrics.test.mjs
git commit -m "feat: derive CTR/CPC/CVR/CPA/ROAS with null on zero denominator"
```

---

### Task 4: filterRows + aggregateKeywords — 필터링과 키워드 합산

**Files:**
- Modify: `lib/metrics.js`
- Modify: `test/metrics.test.mjs`

**Interfaces:**
- Consumes: `deriveMetrics`, `Row` (Task 2).
- Produces:
  - `filterRows(rows: Row[], filters: {from?:string,to?:string,media?:string,device?:string}): Row[]` — `from`/`to`는 'YYYY-MM-DD' 포함 범위. 빈/누락 필터는 무시. `media`/`device`가 `''` 또는 `'ALL'`이면 전체.
  - `aggregateKeywords(rows: Row[]): AggRow[]` — keyword별 합산 + 파생지표.
    `AggRow = { keyword, impression, click, cost, connection, input, complete, conclusion, revenue, ctr, cpc, cvr, cpa, roas }`.

- [ ] **Step 1: 실패 테스트 작성**

```javascript
import { filterRows, aggregateKeywords } from '../lib/metrics.js';

const ROWS = parseRows([
  { Date:'2025-10-31', Media:'Google', Device:'PC', keyword:'여행자보험.', impression:'496', click:'64', cost:'220475.4108', connection:'106', input:'40', complete:'38', conclusion:'13', '매출':'336481' },
  { Date:'2025-11-01', Media:'Google', Device:'PC', keyword:'여행자보험.', impression:'376', click:'44', cost:'148972.8414', connection:'85', input:'32', complete:'30', conclusion:'10', '매출':'258832' },
  { Date:'2025-10-31', Media:'Naver', Device:'Mobile', keyword:'KB여행자보험', impression:'21', click:'1', cost:'3670.139', connection:'3', input:'1', complete:'0', conclusion:'0', '매출':'0' },
]);

test('filterRows: 매체 필터', () => {
  assert.equal(filterRows(ROWS, { media:'Naver' }).length, 1);
  assert.equal(filterRows(ROWS, { media:'ALL' }).length, 3);
});
test('filterRows: 날짜 범위', () => {
  assert.equal(filterRows(ROWS, { from:'2025-11-01', to:'2025-11-01' }).length, 1);
});
test('aggregateKeywords: 합산 후 비율', () => {
  const agg = aggregateKeywords(filterRows(ROWS, { media:'Google' }));
  const kw = agg.find((a) => a.keyword === '여행자보험.');
  assert.equal(kw.impression, 872);   // 496+376
  assert.equal(kw.click, 108);        // 64+44
  assert.equal(kw.conclusion, 23);    // 13+10
  assert.equal(kw.revenue, 595313);   // 336481+258832
  // CTR = 108/872 (가중)
  assert.ok(Math.abs(kw.ctr - 108 / 872) < 1e-9);
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `node --test`
Expected: FAIL — `filterRows` is not a function.

- [ ] **Step 3: 구현**

```javascript
function matchFilter(value, filter) {
  if (!filter || filter === 'ALL' || filter === '') return true;
  return value === filter;
}

export function filterRows(rows, filters = {}) {
  const { from, to, media, device } = filters;
  return rows.filter((r) =>
    (!from || r.date >= from) &&
    (!to || r.date <= to) &&
    matchFilter(r.media, media) &&
    matchFilter(r.device, device));
}

const SUM_FIELDS = ['impression','click','cost','connection','input','complete','conclusion','revenue'];

export function aggregateKeywords(rows) {
  const byKw = new Map();
  for (const r of rows) {
    let acc = byKw.get(r.keyword);
    if (!acc) {
      acc = { keyword: r.keyword };
      for (const f of SUM_FIELDS) acc[f] = 0;
      byKw.set(r.keyword, acc);
    }
    for (const f of SUM_FIELDS) acc[f] += r[f];
  }
  return [...byKw.values()].map((acc) => ({ ...acc, ...deriveMetrics(acc) }));
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `node --test`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
git add lib/metrics.js test/metrics.test.mjs
git commit -m "feat: filter rows and aggregate by keyword with weighted ratios"
```

---

### Task 5: topNKeywords + buildTrendSeries — 상위 선별과 추이 시계열

**Files:**
- Modify: `lib/metrics.js`
- Modify: `test/metrics.test.mjs`

**Interfaces:**
- Consumes: `filterRows`, `deriveMetrics`, `AggRow` (Task 4).
- Produces:
  - `topNKeywords(aggRows: AggRow[], metric: string, n: number): string[]` — `metric`('conclusion'|'cost'|'revenue'|'click') 내림차순 상위 n개 keyword. 기본 정렬 메트릭 = 'conclusion'.
  - `buildTrendSeries(rows: Row[], keywords: string[], metric: string): { dates:string[], series:{keyword:string,data:(number|null)[]}[] }` — `metric`은 파생지표 키('cvr'|'ctr'|'cpa'|'roas'). 각 keyword에 대해 날짜별 합산→파생지표 값(분모0 → null) 배열. `dates`는 입력 rows의 정렬된 고유 날짜.

- [ ] **Step 1: 실패 테스트 작성**

```javascript
import { topNKeywords, buildTrendSeries } from '../lib/metrics.js';

test('topNKeywords: 전환수 상위', () => {
  const agg = aggregateKeywords(ROWS);
  const top = topNKeywords(agg, 'conclusion', 1);
  assert.deepEqual(top, ['여행자보험.']);  // 23 vs 0
});

test('buildTrendSeries: 날짜별 CVR', () => {
  const { dates, series } = buildTrendSeries(ROWS, ['여행자보험.'], 'cvr');
  assert.deepEqual(dates, ['2025-10-31','2025-11-01']);
  const s = series[0];
  assert.equal(s.keyword, '여행자보험.');
  assert.ok(Math.abs(s.data[0] - 13 / 64) < 1e-9);  // 10-31
  assert.ok(Math.abs(s.data[1] - 10 / 44) < 1e-9);  // 11-01
});

test('buildTrendSeries: 데이터 없는 날짜는 null', () => {
  const { series } = buildTrendSeries(ROWS, ['KB여행자보험'], 'cvr');
  // KB여행자보험은 10-31만 존재, click=1 conclusion=0 → cvr 0; 11-01 없음 → null
  assert.equal(series[0].data[0], 0);
  assert.equal(series[0].data[1], null);
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `node --test`
Expected: FAIL — `topNKeywords` is not a function.

- [ ] **Step 3: 구현**

```javascript
export function topNKeywords(aggRows, metric = 'conclusion', n = 5) {
  return [...aggRows]
    .sort((a, b) => (b[metric] ?? -Infinity) - (a[metric] ?? -Infinity))
    .slice(0, n)
    .map((a) => a.keyword);
}

export function buildTrendSeries(rows, keywords, metric) {
  const dates = [...new Set(rows.map((r) => r.date))].sort();
  const series = keywords.map((kw) => {
    const data = dates.map((d) => {
      const dayRows = rows.filter((r) => r.keyword === kw && r.date === d);
      if (dayRows.length === 0) return null;
      const acc = { impression:0, click:0, cost:0, conclusion:0, revenue:0 };
      for (const r of dayRows) {
        acc.impression += r.impression; acc.click += r.click; acc.cost += r.cost;
        acc.conclusion += r.conclusion; acc.revenue += r.revenue;
      }
      return deriveMetrics(acc)[metric];
    });
    return { keyword: kw, data };
  });
  return { dates, series };
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `node --test`
Expected: PASS (전체 테스트 통과).

- [ ] **Step 5: 커밋**

```bash
git add lib/metrics.js test/metrics.test.mjs
git commit -m "feat: top-N keyword selection and date trend series"
```

---

### Task 6: dashboard.html 골격 + 데이터 로드 + KPI 카드

**Files:**
- Create: `dashboard.html`

**Interfaces:**
- Consumes: `lib/metrics.js` 전체(`parseRows`, `filterRows`, `aggregateKeywords`, `topNKeywords`, `buildTrendSeries`), PapaParse(CDN), ECharts(CDN).
- Produces: 전역 `state` 객체 `{ rows, filters, metric, selectedKeywords }`, `loadData()`, `renderKPIs()`.

- [ ] **Step 1: HTML 골격 + CDN + 모듈 import + CSV_URL 상수**

`dashboard.html`:
```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>키워드 효율 추이 대시보드</title>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/papaparse@5/papaparse.min.js"></script>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <header class="topbar">
    <h1>키워드 효율 추이</h1>
    <div class="filters" id="filters"></div>
  </header>
  <section class="kpis" id="kpis"></section>
  <section class="card chart-card">
    <div class="chart-toolbar" id="chartToolbar"></div>
    <div id="trendChart" style="height:380px;"></div>
    <div class="chips" id="chips"></div>
  </section>
  <section class="card table-card">
    <div class="table-toolbar"><input id="search" placeholder="키워드 검색..." /></div>
    <div id="tableWrap"></div>
  </section>
  <div id="status" class="status" hidden></div>

  <script type="module">
    import { parseRows, filterRows, aggregateKeywords, topNKeywords, buildTrendSeries }
      from './lib/metrics.js';

    // === 설정: 시트 → 파일 → 공유 → 웹에 게시 → CSV 링크를 여기에 ===
    const CSV_URL = 'PASTE_PUBLISHED_CSV_URL_HERE';

    const state = {
      rows: [],
      filters: { from: '', to: '', media: 'ALL', device: 'ALL' },
      metric: 'cvr',
      rankBy: 'conclusion',
      selectedKeywords: [],
    };
    window.__state = state; // 디버깅용

    function showStatus(msg, retry = false) {
      const el = document.getElementById('status');
      el.hidden = false;
      el.innerHTML = msg + (retry ? ' <button id="retry">다시 시도</button>' : '');
      if (retry) document.getElementById('retry').onclick = loadData;
    }
    function hideStatus() { document.getElementById('status').hidden = true; }

    async function loadData() {
      hideStatus();
      if (CSV_URL.startsWith('PASTE_')) { showStatus('CSV_URL을 설정하세요 (dashboard.html 상단).'); return; }
      try {
        const res = await fetch(CSV_URL);
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const text = await res.text();
        const parsed = Papa.parse(text, { header: true, skipEmptyLines: true });
        state.rows = parseRows(parsed.data);
        if (state.rows.length === 0) { showStatus('데이터가 비어 있습니다.'); return; }
        initFiltersDefault();
        renderAll();
      } catch (e) {
        showStatus('데이터를 불러오지 못했습니다: ' + e.message, true);
      }
    }

    function initFiltersDefault() {
      const dates = state.rows.map((r) => r.date).filter(Boolean).sort();
      state.filters.from = dates[0] || '';
      state.filters.to = dates[dates.length - 1] || '';
    }

    function currentRows() { return filterRows(state.rows, state.filters); }

    function renderKPIs() {
      const rows = currentRows();
      const acc = { impression:0, click:0, cost:0, conclusion:0, revenue:0 };
      for (const r of rows) { acc.impression+=r.impression; acc.click+=r.click; acc.cost+=r.cost; acc.conclusion+=r.conclusion; acc.revenue+=r.revenue; }
      const pct = (v) => v == null ? '-' : (v*100).toFixed(1) + '%';
      const won = (v) => '₩' + Math.round(v).toLocaleString('ko-KR');
      const roas = acc.cost > 0 ? acc.revenue/acc.cost : null;
      const cvr = acc.click > 0 ? acc.conclusion/acc.click : null;
      const ctr = acc.impression > 0 ? acc.click/acc.impression : null;
      const cpa = acc.conclusion > 0 ? acc.cost/acc.conclusion : null;
      const cards = [
        ['ROAS', roas == null ? '-' : (roas*100).toFixed(0)+'%', 'accent'],
        ['CVR', pct(cvr), ''],
        ['CTR', pct(ctr), ''],
        ['CPA', cpa == null ? '-' : won(cpa), ''],
        ['비용', won(acc.cost), ''],
        ['매출', won(acc.revenue), ''],
      ];
      document.getElementById('kpis').innerHTML = cards.map(([label,val,cls]) =>
        `<div class="kpi ${cls}"><div class="kpi-label">${label}</div><div class="kpi-val">${val}</div></div>`
      ).join('');
    }

    function renderAll() {
      renderKPIs();
      // renderFilters / renderTrend / renderTable 는 이후 태스크에서 채움
      if (window.__renderFilters) window.__renderFilters();
      if (window.__renderTrend) window.__renderTrend();
      if (window.__renderTable) window.__renderTable();
    }

    window.__loadData = loadData;
    window.__renderAll = renderAll;
    window.__currentRows = currentRows;
    loadData();
  </script>
</body>
</html>
```

- [ ] **Step 2: 임시 styles.css 생성(다음 태스크에서 완성)**

`styles.css`:
```css
:root { --bg:#f7f8fa; --card:#fff; --line:#e8ebf0; --text:#1a2233; --muted:#9aa3b2; --accent:#3b5bdb; --good:#16a34a; --bad:#dc2626; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font-family:system-ui,'Segoe UI','Malgun Gothic',sans-serif; }
.kpis { display:flex; gap:12px; padding:16px; flex-wrap:wrap; }
.kpi { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 18px; min-width:120px; box-shadow:0 1px 3px rgba(16,24,40,.06); }
.kpi-label { font-size:12px; color:var(--muted); }
.kpi-val { font-size:22px; font-weight:800; }
.kpi.accent .kpi-val { color:var(--accent); }
.status { padding:16px; color:var(--bad); }
```

- [ ] **Step 3: 로컬 서버로 수동 확인**

Run (모듈 import는 file://에서 CORS 막힘 → 로컬 서버 필요):
```bash
cd "C:/Users/MADUP/Desktop/클로드코드" && python -m http.server 8000
```
브라우저에서 `http://localhost:8000/dashboard.html` 열기.
Expected: CSV_URL 미설정 안내 메시지가 status 영역에 보임. 콘솔 에러 없음.

- [ ] **Step 4: 커밋**

```bash
git add dashboard.html styles.css
git commit -m "feat: dashboard skeleton with data loading and KPI cards"
```

---

### Task 7: 추이 라인차트 (ECharts) + 상위 자동 + 칩 + 지표/기준 토글

**Files:**
- Modify: `dashboard.html`
- Modify: `styles.css`

**Interfaces:**
- Consumes: `aggregateKeywords`, `topNKeywords`, `buildTrendSeries`, `state`, `currentRows()`.
- Produces: `window.__renderTrend()`, `window.__renderChartToolbar()`. `state.selectedKeywords` 갱신.

- [ ] **Step 1: 차트 툴바 + 추이 렌더 함수 추가**

`dashboard.html`의 `<script type="module">` 안, `renderAll` 위에 추가:
```javascript
let chart;
const METRICS = [['cvr','CVR'],['ctr','CTR'],['cpa','CPA'],['roas','ROAS']];
const RANKS = [['conclusion','전환수'],['cost','비용'],['revenue','매출'],['click','클릭']];
const COLORS = ['#3b5bdb','#16a34a','#dc2626','#f59e0b','#7c3aed','#0891b2','#db2777','#65a30d'];

function renderChartToolbar() {
  const m = METRICS.map(([k,l]) => `<button class="seg ${state.metric===k?'on':''}" data-metric="${k}">${l}</button>`).join('');
  const r = RANKS.map(([k,l]) => `<option value="${k}" ${state.rankBy===k?'selected':''}>${l} 상위</option>`).join('');
  document.getElementById('chartToolbar').innerHTML =
    `<div class="segs">${m}</div><select id="rankSel">${r}</select>`;
  document.querySelectorAll('.seg').forEach((b) => b.onclick = () => { state.metric = b.dataset.metric; renderTrend(); renderChartToolbar(); });
  document.getElementById('rankSel').onchange = (e) => { state.rankBy = e.target.value; autoSelectTop(); renderTrend(); };
}

function autoSelectTop() {
  const agg = aggregateKeywords(currentRows());
  state.selectedKeywords = topNKeywords(agg, state.rankBy, 5);
}

function renderTrend() {
  if (!chart) chart = echarts.init(document.getElementById('trendChart'));
  const rows = currentRows();
  if (state.selectedKeywords.length === 0) autoSelectTop();
  const { dates, series } = buildTrendSeries(rows, state.selectedKeywords, state.metric);
  const isPct = state.metric === 'cvr' || state.metric === 'ctr';
  chart.setOption({
    color: COLORS,
    tooltip: { trigger:'axis', valueFormatter:(v)=> v==null?'-':(isPct?(v*100).toFixed(1)+'%':Math.round(v).toLocaleString()) },
    legend: { show:false },
    grid: { left:48, right:16, top:16, bottom:32 },
    xAxis: { type:'category', data:dates },
    yAxis: { type:'value', axisLabel:{ formatter:(v)=> isPct?(v*100).toFixed(0)+'%':v } },
    series: series.map((s) => ({ name:s.keyword, type:'line', data:s.data, connectNulls:true, smooth:true, symbolSize:6 })),
  }, true);
  renderChips(series);
}

function renderChips(series) {
  const all = aggregateKeywords(currentRows()).map((a)=>a.keyword);
  const chips = state.selectedKeywords.map((kw, i) =>
    `<span class="chip" style="--c:${COLORS[i % COLORS.length]}" data-kw="${kw}">${kw} ✕</span>`).join('');
  document.getElementById('chips').innerHTML = chips;
  document.querySelectorAll('.chip').forEach((c) => c.onclick = () => {
    state.selectedKeywords = state.selectedKeywords.filter((k)=>k!==c.dataset.kw);
    renderTrend();
  });
}

window.__renderTrend = renderTrend;
window.__renderChartToolbar = renderChartToolbar;
```

`renderAll()` 안에서 `if (window.__renderTrend)` 줄을 다음으로 교체:
```javascript
      renderChartToolbar();
      autoSelectTop();
      renderTrend();
```

- [ ] **Step 2: 칩/세그 스타일 추가**

`styles.css`에 추가:
```css
.card { background:var(--card); border:1px solid var(--line); border-radius:12px; margin:0 16px 16px; padding:14px; box-shadow:0 1px 3px rgba(16,24,40,.06); }
.chart-toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }
.segs { display:inline-flex; gap:4px; }
.seg { border:1px solid var(--line); background:#fff; border-radius:8px; padding:5px 12px; cursor:pointer; font-size:13px; }
.seg.on { background:var(--accent); color:#fff; border-color:var(--accent); }
#rankSel { border:1px solid var(--line); border-radius:8px; padding:5px 8px; }
.chips { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
.chip { font-size:12px; padding:3px 10px; border-radius:14px; cursor:pointer; color:#fff; background:var(--c,#3b5bdb); }
```

- [ ] **Step 3: 수동 확인 (임시 픽스처로)**

`CSV_URL`을 임시로 로컬 픽스처로 두고 확인 가능: `const CSV_URL = './test/fixtures/sample.csv';`
Run: `python -m http.server 8000` → `http://localhost:8000/dashboard.html`
Expected: 전환수 상위 키워드가 라인으로 표시, CVR/CTR/CPA/ROAS 세그 클릭 시 차트 갱신, 칩 ✕ 클릭 시 라인 제거. 확인 후 `CSV_URL`을 `PASTE_...`로 되돌림.

- [ ] **Step 4: 커밋**

```bash
git add dashboard.html styles.css
git commit -m "feat: trend line chart with auto top-N, metric/rank toggles, chips"
```

---

### Task 8: 랭킹 테이블 + 정렬 + 검색 + 행 클릭 드릴다운

**Files:**
- Modify: `dashboard.html`
- Modify: `styles.css`

**Interfaces:**
- Consumes: `aggregateKeywords`, `currentRows()`, `state`, `renderTrend()`.
- Produces: `window.__renderTable()`. `state.sortKey`, `state.sortDir`, `state.search` 추가.

- [ ] **Step 1: state에 테이블 상태 추가**

`dashboard.html`의 `state` 객체에 추가:
```javascript
      sortKey: 'conclusion',
      sortDir: 'desc',
      search: '',
```

- [ ] **Step 2: 테이블 렌더 함수 추가**

```javascript
const COLS = [
  ['keyword','키워드','text'],['impression','노출','int'],['click','클릭','int'],
  ['ctr','CTR','pct'],['cost','비용','won'],['cpc','CPC','won'],
  ['conclusion','전환','int'],['cvr','CVR','pct'],['cpa','CPA','won'],
  ['revenue','매출','won'],['roas','ROAS','roas'],
];
const fmt = {
  text:(v)=>v, int:(v)=>Math.round(v).toLocaleString('ko-KR'),
  pct:(v)=>v==null?'-':(v*100).toFixed(1)+'%',
  won:(v)=>v==null?'-':'₩'+Math.round(v).toLocaleString('ko-KR'),
  roas:(v)=>v==null?'-':(v*100).toFixed(0)+'%',
};

function renderTable() {
  let agg = aggregateKeywords(currentRows());
  if (state.search) agg = agg.filter((a)=>a.keyword.includes(state.search));
  agg.sort((a,b)=>{
    const av=a[state.sortKey], bv=b[state.sortKey];
    const an=av==null?-Infinity:av, bn=bv==null?-Infinity:bv;
    if (typeof av==='string') return state.sortDir==='asc'?String(av).localeCompare(bv):String(bv).localeCompare(av);
    return state.sortDir==='asc'?an-bn:bn-an;
  });
  agg = agg.slice(0, 200);
  const head = COLS.map(([k,l])=>`<th data-key="${k}" class="${state.sortKey===k?'sorted '+state.sortDir:''}">${l}</th>`).join('');
  const body = agg.map((a)=>{
    const sel = state.selectedKeywords.includes(a.keyword) ? 'sel' : '';
    const tds = COLS.map(([k,,t])=>`<td class="${t==='text'?'l':'r'}">${fmt[t](a[k])}</td>`).join('');
    return `<tr class="${sel}" data-kw="${a.keyword}">${tds}</tr>`;
  }).join('');
  document.getElementById('tableWrap').innerHTML = `<table class="grid"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  document.querySelectorAll('.grid th').forEach((th)=>th.onclick=()=>{
    const k=th.dataset.key;
    if (state.sortKey===k) state.sortDir = state.sortDir==='asc'?'desc':'asc';
    else { state.sortKey=k; state.sortDir = k==='keyword'?'asc':'desc'; }
    renderTable();
  });
  document.querySelectorAll('.grid tbody tr').forEach((tr)=>tr.onclick=()=>{
    const kw=tr.dataset.kw;
    if (state.selectedKeywords.includes(kw)) state.selectedKeywords = state.selectedKeywords.filter((k)=>k!==kw);
    else state.selectedKeywords = [...state.selectedKeywords, kw];
    renderTrend(); renderTable();
  });
}
window.__renderTable = renderTable;
```

`renderAll()`에서 `if (window.__renderTable)` 줄을 `renderTable();`로 교체. 그리고 검색 입력 바인딩을 `loadData` 성공 후 1회 보장하기 위해 `renderAll` 마지막에 추가:
```javascript
      const search = document.getElementById('search');
      if (search && !search.__bound) { search.__bound = true; search.oninput = (e)=>{ state.search = e.target.value.trim(); renderTable(); }; }
```

- [ ] **Step 3: 테이블 스타일 추가**

`styles.css`에 추가:
```css
.table-toolbar { margin-bottom:10px; }
#search { width:240px; border:1px solid var(--line); border-radius:8px; padding:7px 10px; }
.grid { width:100%; border-collapse:collapse; font-size:13px; }
.grid th, .grid td { padding:8px 10px; border-bottom:1px solid var(--line); white-space:nowrap; }
.grid th { text-align:right; cursor:pointer; color:var(--muted); font-weight:600; user-select:none; }
.grid th:first-child, .grid td.l { text-align:left; }
.grid td.r { text-align:right; }
.grid th.sorted { color:var(--accent); }
.grid tbody tr { cursor:pointer; }
.grid tbody tr:hover { background:#f3f5f9; }
.grid tbody tr.sel { background:#eef2ff; }
```

- [ ] **Step 4: 수동 확인**

`CSV_URL='./test/fixtures/sample.csv'`로 두고 `python -m http.server 8000` 실행.
Expected: 테이블이 전환수 내림차순으로 표시, 헤더 클릭 시 정렬 토글, 검색어 입력 시 필터, 행 클릭 시 해당 키워드가 차트 라인으로 추가/제거되고 행이 하이라이트. 확인 후 CSV_URL 복원.

- [ ] **Step 5: 커밋**

```bash
git add dashboard.html styles.css
git commit -m "feat: ranking table with sort, search, and row drill-down"
```

---

### Task 9: 필터 바(기간·매체·디바이스) + 빈/에러 상태 + 최종 스타일 폴리시

**Files:**
- Modify: `dashboard.html`
- Modify: `styles.css`

**Interfaces:**
- Consumes: `state`, `renderAll()`, `state.rows`.
- Produces: `window.__renderFilters()`.

- [ ] **Step 1: 필터 렌더 함수 추가**

```javascript
function uniqueVals(field) { return [...new Set(state.rows.map((r)=>r[field]).filter(Boolean))].sort(); }

function renderFilters() {
  const media = uniqueVals('media').map((v)=>`<option value="${v}" ${state.filters.media===v?'selected':''}>${v}</option>`).join('');
  const device = uniqueVals('device').map((v)=>`<option value="${v}" ${state.filters.device===v?'selected':''}>${v}</option>`).join('');
  document.getElementById('filters').innerHTML = `
    <label>기간 <input type="date" id="fFrom" value="${state.filters.from}"></label>
    <span>~</span>
    <label><input type="date" id="fTo" value="${state.filters.to}"></label>
    <label>매체 <select id="fMedia"><option value="ALL">전체</option>${media}</select></label>
    <label>디바이스 <select id="fDevice"><option value="ALL">전체</option>${device}</select></label>`;
  document.getElementById('fFrom').onchange=(e)=>{ state.filters.from=e.target.value; onFilterChange(); };
  document.getElementById('fTo').onchange=(e)=>{ state.filters.to=e.target.value; onFilterChange(); };
  document.getElementById('fMedia').onchange=(e)=>{ state.filters.media=e.target.value; onFilterChange(); };
  document.getElementById('fDevice').onchange=(e)=>{ state.filters.device=e.target.value; onFilterChange(); };
}

function onFilterChange() {
  if (currentRows().length === 0) { showStatus('해당 조건에 데이터가 없습니다.'); }
  else { hideStatus(); }
  autoSelectTop();
  renderKPIs(); renderTrend(); renderTable();
}
window.__renderFilters = renderFilters;
```

`renderAll()` 시작 부분에 `renderFilters();` 추가(중복 호출 방지를 위해 한 번만 정의된 함수 호출).

- [ ] **Step 2: 필터 바 + 반응형 스타일**

`styles.css`에 추가:
```css
.topbar { display:flex; align-items:center; justify-content:space-between; gap:16px; padding:14px 16px; background:#fff; border-bottom:1px solid var(--line); flex-wrap:wrap; }
.topbar h1 { font-size:18px; margin:0; }
.filters { display:flex; align-items:center; gap:12px; flex-wrap:wrap; font-size:13px; color:var(--muted); }
.filters input, .filters select { border:1px solid var(--line); border-radius:8px; padding:6px 8px; font-size:13px; color:var(--text); }
@media (max-width:720px){ .kpis .kpi{ flex:1 1 40%; } .grid{ font-size:12px; } }
```

- [ ] **Step 3: 전체 흐름 수동 확인**

`CSV_URL='./test/fixtures/sample.csv'`로 `python -m http.server 8000` 실행.
Expected:
- 상단 필터(기간/매체/디바이스) 표시, 기본값=데이터 전체 기간.
- 매체를 'Naver'로 바꾸면 KPI·차트·테이블이 일관되게 갱신.
- 데이터 0건 조건이면 "해당 조건에 데이터가 없습니다" 안내.
- 라이트 클린 스타일, 블루 포인트로 렌더.
확인 후 `CSV_URL`을 `PASTE_PUBLISHED_CSV_URL_HERE`로 복원.

- [ ] **Step 4: 단위 테스트 전체 통과 재확인**

Run: `node --test`
Expected: 전체 PASS.

- [ ] **Step 5: 커밋**

```bash
git add dashboard.html styles.css
git commit -m "feat: filter bar (date/media/device), empty/error states, responsive polish"
```

---

### Task 10: 사용 안내 문서 + 게시 CSV 연결 확인

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: (없음)

- [ ] **Step 1: README 작성**

`README.md`:
```markdown
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
```

- [ ] **Step 2: 커밋**

```bash
git add README.md
git commit -m "docs: setup and usage guide"
```

---

## Self-Review

**Spec coverage:**
- §2 데이터 소스(게시 CSV) → Task 6 `loadData`/`CSV_URL`, Task 10 README. ✓
- §2.1 컬럼 파싱 → Task 2 `parseRows`. ✓
- §2.2 파생 지표 정의 → Task 3 `deriveMetrics`. ✓
- §3.1-1 필터+KPI → Task 6 `renderKPIs`, Task 9 `renderFilters`. ✓
- §3.1-2 추이차트 상위N 자동/토글/칩 → Task 5 `topNKeywords`/`buildTrendSeries`, Task 7. ✓
- §3.1-3 랭킹테이블 정렬/검색/드릴다운 → Task 8. ✓
- §3.2 라이트 클린 스타일 → Task 6/7/8/9 `styles.css`. ✓
- §4 기술 구조(단일 HTML+ECharts+PapaParse, 역할 분리) → Task 6-9. ✓
- §5 엣지/에러(로드 실패·분모0·빈결과·표기) → Task 3, Task 6 `showStatus`, Task 9 빈상태. ✓
- §7 검증 기준 → 각 Task 수동 확인 단계. ✓

**Placeholder scan:** `CSV_URL`의 `PASTE_...`는 의도된 사용자 설정값(코드 placeholder 아님, README에 절차 명시). 그 외 TBD/TODO 없음. ✓

**Type consistency:** `AggRow`/`Row` 필드명(`revenue`=매출, `conclusion` 등)이 Task 2→4→5→7→8에서 일관. `topNKeywords(agg, metric, n)`, `buildTrendSeries(rows, keywords, metric)` 시그니처가 Task 5 정의와 Task 7 호출에서 일치. `renderTrend`/`renderTable`/`renderKPIs`/`renderFilters` 명칭 일관. ✓
