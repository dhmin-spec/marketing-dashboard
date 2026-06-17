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
