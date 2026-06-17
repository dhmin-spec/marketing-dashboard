export function parseNumber(raw) {
  if (raw === null || raw === undefined) return 0;
  if (typeof raw === 'number') return Number.isFinite(raw) ? raw : 0;
  const cleaned = String(raw).replace(/,/g, '').trim();
  if (cleaned === '' || cleaned === '-') return 0;
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : 0;
}

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
