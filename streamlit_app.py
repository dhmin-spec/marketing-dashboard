"""키워드 효율 추이 대시보드 (Streamlit).

로컬 CSV(키워드 광고 성과)를 받아 EDA + 효율 지표(CTR·CVR·CPA·ROAS) 추이를 시각화한다.
지표 정의·집계 규칙은 HTML 버전(lib/metrics.js)과 동일:
- 집계는 합산 후 비율 재계산(가중평균). 단순 평균 금지.
- 분모 0인 지표는 NaN(표기 '-').
- 매출 = 숫자 컬럼 '매출'. (sales는 포맷 문자열이라 미사용)
"""

from __future__ import annotations

import io
from datetime import timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="키워드 효율 추이",
    page_icon=":material/monitoring:",
    layout="wide",
)

# =============================================================================
# 상수
# =============================================================================

SAMPLE_CSV = Path(__file__).parent / "test" / "fixtures" / "sample.csv"
SUM_FIELDS = [
    "impression", "click", "cost",
    "connection", "input", "complete", "conclusion", "revenue",
]
# (라벨, 지표키, 포맷, 높을수록 좋은가)
METRICS = [
    ("CVR", "cvr", "pct", True),
    ("CTR", "ctr", "pct", True),
    ("CPA", "cpa", "won", False),
    ("ROAS", "roas", "roas", True),
]
RANK_OPTIONS = {"전환수": "conclusion", "비용": "cost", "매출": "revenue", "클릭": "click"}


# =============================================================================
# 데이터 로드 · 파싱
# =============================================================================


def _to_num(series: pd.Series) -> pd.Series:
    """천단위 콤마 제거, '-'/빈칸/NaN → 0, 숫자로 변환."""
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.strip()
        .replace({"-": "0", "": "0", "nan": "0", "None": "0"})
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(0)


@st.cache_data(show_spinner=False)
def parse_rows(content: bytes) -> pd.DataFrame:
    """CSV 바이트 → 타입 변환된 행 DataFrame."""
    raw = pd.read_csv(io.BytesIO(content), dtype=str)
    raw.columns = [c.strip() for c in raw.columns]

    df = pd.DataFrame()
    df["date"] = raw.get("Date", "").astype(str).str.strip()
    df["media"] = raw.get("Media", "").astype(str).str.strip()
    df["device"] = raw.get("Device", "").astype(str).str.strip()
    df["campaign"] = raw.get("campaign", "").astype(str).str.strip()
    df["adgroup"] = raw.get("adgroup", "").astype(str).str.strip()
    df["keyword"] = raw.get("keyword", "").astype(str).str.strip()
    df["product"] = raw.get("Product", "").astype(str).str.strip()

    for col in ["impression", "click", "cost", "connection", "input", "complete", "conclusion"]:
        df[col] = _to_num(raw.get(col, 0))
    df["revenue"] = _to_num(raw.get("매출", 0))

    # keyword 없는 행 제거
    df = df[df["keyword"].astype(bool) & (df["keyword"] != "nan")]
    return df.reset_index(drop=True)


def derive(df: pd.DataFrame) -> pd.DataFrame:
    """합산된 행들에 파생 지표 컬럼 추가 (분모 0 → NaN)."""
    out = df.copy()
    out["ctr"] = out["click"] / out["impression"].where(out["impression"] > 0)
    out["cpc"] = out["cost"] / out["click"].where(out["click"] > 0)
    out["cvr"] = out["conclusion"] / out["click"].where(out["click"] > 0)
    out["cpa"] = out["cost"] / out["conclusion"].where(out["conclusion"] > 0)
    out["roas"] = out["revenue"] / out["cost"].where(out["cost"] > 0)
    return out


def aggregate_keywords(df: pd.DataFrame) -> pd.DataFrame:
    """keyword별 합산 후 파생 지표 계산 (가중)."""
    if df.empty:
        return df
    agg = df.groupby("keyword", as_index=False)[SUM_FIELDS].sum()
    return derive(agg)


def totals(df: pd.DataFrame) -> dict:
    """전체 합산 + 파생 지표 (단일 행 dict)."""
    sums = {f: float(df[f].sum()) if not df.empty else 0.0 for f in SUM_FIELDS}
    row = derive(pd.DataFrame([sums])).iloc[0]
    return row.to_dict()


# =============================================================================
# 포맷터
# =============================================================================


def fmt_pct(v) -> str:
    return "-" if pd.isna(v) else f"{v * 100:.1f}%"


def fmt_roas(v) -> str:
    return "-" if pd.isna(v) else f"{v * 100:.0f}%"


def fmt_won(v) -> str:
    return "-" if pd.isna(v) else f"₩{round(v):,}"


def fmt_int(v) -> str:
    return f"{round(v):,}"


# =============================================================================
# 데이터 소스 (사이드바)
# =============================================================================

st.sidebar.markdown("### 데이터 소스")
upload = st.sidebar.file_uploader("CSV 업로드", type=["csv"])

if upload is not None:
    rows = parse_rows(upload.getvalue())
    src_label = f"업로드: {upload.name}"
elif SAMPLE_CSV.exists():
    rows = parse_rows(SAMPLE_CSV.read_bytes())
    src_label = "샘플 데이터 (test/fixtures/sample.csv)"
else:
    st.error("CSV를 업로드하세요. 샘플 파일도 찾을 수 없습니다.")
    st.stop()

st.sidebar.caption(src_label)

if rows.empty:
    st.warning("데이터가 비어 있습니다.")
    st.stop()

# =============================================================================
# 필터 (사이드바)
# =============================================================================

st.sidebar.markdown("### 필터")
all_dates = sorted(rows["date"].unique())
dmin = pd.to_datetime(all_dates[0]).date()
dmax = pd.to_datetime(all_dates[-1]).date()

date_range = st.sidebar.date_input(
    "기간", value=(dmin, dmax), min_value=dmin, max_value=dmax
)
if isinstance(date_range, tuple) and len(date_range) == 2:
    from_d, to_d = date_range
else:
    from_d, to_d = dmin, dmax

media_opts = sorted(rows["media"].unique())
device_opts = sorted(rows["device"].unique())
sel_media = st.sidebar.multiselect("매체 (Media)", media_opts, default=media_opts)
sel_device = st.sidebar.multiselect("디바이스 (Device)", device_opts, default=device_opts)


def apply_filters(df: pd.DataFrame, f: str, t: str, media: list, device: list) -> pd.DataFrame:
    mask = (
        (df["date"] >= str(f))
        & (df["date"] <= str(t))
        & (df["media"].isin(media) if media else True)
        & (df["device"].isin(device) if device else True)
    )
    return df[mask]


cur = apply_filters(rows, from_d, to_d, sel_media, sel_device)

# 직전 동일 길이 기간 (KPI 증감용)
period_len = (pd.Timestamp(to_d) - pd.Timestamp(from_d)).days + 1
prior_to = pd.Timestamp(from_d) - timedelta(days=1)
prior_from = prior_to - timedelta(days=period_len - 1)
prior = apply_filters(
    rows, prior_from.date(), prior_to.date(), sel_media, sel_device
)

# =============================================================================
# 헤더 + EDA 개요
# =============================================================================

st.markdown("# :material/monitoring: 키워드 효율 추이")

if cur.empty:
    st.warning("해당 조건에 데이터가 없습니다. 필터를 조정하세요.")
    st.stop()

with st.container(border=True):
    st.markdown("**데이터 개요 (EDA)**")
    with st.container(horizontal=True):
        st.metric("행 수", fmt_int(len(cur)))
        st.metric("키워드 수", fmt_int(cur["keyword"].nunique()))
        st.metric("기간", f"{from_d} ~ {to_d}")
        st.metric("일수", fmt_int(cur["date"].nunique()))

# =============================================================================
# KPI 카드 (전기간 대비 증감)
# =============================================================================

cur_t = totals(cur)
prior_t = totals(prior) if not prior.empty else None


def delta_str(key: str) -> str | None:
    if prior_t is None:
        return None
    c, p = cur_t.get(key), prior_t.get(key)
    if c is None or p is None or pd.isna(c) or pd.isna(p) or p == 0:
        return None
    return f"{(c - p) / p * 100:+.1f}%"


kpi_defs = [
    ("ROAS", fmt_roas(cur_t["roas"]), "roas", "normal"),
    ("CVR", fmt_pct(cur_t["cvr"]), "cvr", "normal"),
    ("CTR", fmt_pct(cur_t["ctr"]), "ctr", "normal"),
    ("CPA", fmt_won(cur_t["cpa"]), "cpa", "inverse"),   # 낮을수록 좋음
    ("비용", fmt_won(cur_t["cost"]), "cost", "inverse"),  # 낮을수록 좋음
    ("매출", fmt_won(cur_t["revenue"]), "revenue", "normal"),
]

with st.container(horizontal=True):
    for label, value, key, color in kpi_defs:
        st.metric(label, value, delta=delta_str(key), delta_color=color, border=True)

if prior_t is None:
    st.caption(f"증감은 직전 동일 기간({prior_from.date()} ~ {prior_to.date()}) 대비 — 해당 기간 데이터가 없어 일부 미표시.")

# =============================================================================
# 추이 라인차트 (상위 N개 자동 + 지표 토글 + 키워드 선택)
# =============================================================================

with st.container(border=True):
    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        st.markdown("**키워드별 효율 추이**")
        metric_label = st.segmented_control(
            "지표", options=[m[0] for m in METRICS], default="CVR",
            key="metric_sel", label_visibility="collapsed",
        ) or "CVR"
        rank_label = st.segmented_control(
            "상위 기준", options=list(RANK_OPTIONS.keys()), default="전환수",
            key="rank_sel", label_visibility="collapsed",
        ) or "전환수"

    metric_key = next(m[1] for m in METRICS if m[0] == metric_label)
    metric_fmt = next(m[2] for m in METRICS if m[0] == metric_label)
    rank_key = RANK_OPTIONS[rank_label]

    agg = aggregate_keywords(cur)
    top5 = agg.sort_values(rank_key, ascending=False)["keyword"].head(5).tolist()

    selected = st.multiselect(
        "비교할 키워드", options=agg.sort_values(rank_key, ascending=False)["keyword"].tolist(),
        default=top5,
    )

    if selected:
        sub = cur[cur["keyword"].isin(selected)]
        daily = sub.groupby(["date", "keyword"], as_index=False)[SUM_FIELDS].sum()
        daily = derive(daily)
        daily["date"] = pd.to_datetime(daily["date"])

        is_pct = metric_fmt in ("pct", "roas")
        y_fmt = ".1%" if metric_fmt == "pct" else (".0%" if metric_fmt == "roas" else ",.0f")
        chart = (
            alt.Chart(daily.dropna(subset=[metric_key]))
            .mark_line(point=True)
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y(f"{metric_key}:Q", title=metric_label,
                        scale=alt.Scale(zero=False),
                        axis=alt.Axis(format=y_fmt)),
                color=alt.Color("keyword:N", title=None,
                                legend=alt.Legend(orient="bottom")),
                tooltip=[
                    alt.Tooltip("date:T", title="날짜", format="%Y-%m-%d"),
                    alt.Tooltip("keyword:N", title="키워드"),
                    alt.Tooltip(f"{metric_key}:Q", title=metric_label, format=y_fmt),
                ],
            )
            .properties(height=380)
        )
        st.altair_chart(chart)
    else:
        st.info("키워드를 1개 이상 선택하세요.")

# =============================================================================
# 랭킹 테이블
# =============================================================================

with st.container(border=True):
    st.markdown("**키워드 랭킹**")
    search = st.text_input("키워드 검색", placeholder="키워드 일부 입력...")
    table = aggregate_keywords(cur)
    if search:
        table = table[table["keyword"].str.contains(search, case=False, na=False)]
    table = table.sort_values("conclusion", ascending=False)

    show = table[[
        "keyword", "impression", "click", "ctr", "cost", "cpc",
        "conclusion", "cvr", "cpa", "revenue", "roas",
    ]].rename(columns={
        "keyword": "키워드", "impression": "노출", "click": "클릭", "ctr": "CTR",
        "cost": "비용", "cpc": "CPC", "conclusion": "전환", "cvr": "CVR",
        "cpa": "CPA", "revenue": "매출", "roas": "ROAS",
    })

    st.dataframe(
        show,
        hide_index=True,
        height=420,
        column_config={
            "노출": st.column_config.NumberColumn(format="%d"),
            "클릭": st.column_config.NumberColumn(format="%d"),
            "전환": st.column_config.NumberColumn(format="%d"),
            "CTR": st.column_config.NumberColumn(format="percent", help="클릭/노출"),
            "CVR": st.column_config.NumberColumn(format="percent", help="전환/클릭"),
            "ROAS": st.column_config.NumberColumn(format="percent", help="매출/비용"),
            "비용": st.column_config.NumberColumn(format="₩%,.0f"),
            "CPC": st.column_config.NumberColumn(format="₩%,.0f"),
            "CPA": st.column_config.NumberColumn(format="₩%,.0f"),
            "매출": st.column_config.NumberColumn(format="₩%,.0f"),
        },
    )
    st.caption("집계는 합산 후 비율 재계산(가중평균). 분모 0은 빈 값으로 표기.")
