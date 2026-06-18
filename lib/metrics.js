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
