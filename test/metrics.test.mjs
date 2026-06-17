import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseNumber, parseRows, deriveMetrics } from '../lib/metrics.js';

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
