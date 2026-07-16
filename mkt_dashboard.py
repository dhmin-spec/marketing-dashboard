"""마케팅 성과 대시보드 — 채널(매체) vs 앱스플라이어(MMP) 갭 분석 + EDA.

실행:  streamlit run mkt_dashboard.py
폴더에 `YYYY-MM-DD_channel.csv` / `YYYY-MM-DD_appsflyer.csv` 를 넣어두면
열 때마다 폴더 전체를 다시 읽어 자동 반영된다.
"""
from __future__ import annotations
import os
import altair as alt
import pandas as pd
import streamlit as st

from mkt_pipeline import load_folder, GAP_METRICS, compute_alerts, ALERT_THRESHOLD

st.set_page_config(page_title="마케팅 성과 대시보드", page_icon="📊", layout="wide")

POINT = "#3b5bdb"
GOOD, BAD = "#16a34a", "#dc2626"


@st.cache_data(show_spinner="데이터 로딩 중…")
def _load(folder: str, sig: tuple):
    """폴더 로드. sig(파일명·수정시각 튜플)가 바뀌면 캐시 무효화 → 파일 추가 시 자동 갱신."""
    return load_folder(folder)


def _folder_signature(folder: str) -> tuple:
    import glob
    files = sorted(glob.glob(os.path.join(folder, "**", "*_channel.csv"), recursive=True)
                   + glob.glob(os.path.join(folder, "**", "*_appsflyer.csv"), recursive=True))
    return tuple((os.path.basename(f), os.path.getmtime(f)) for f in files)


def _won(v):
    return f"₩{v:,.0f}" if pd.notna(v) else "-"


def _fmt(label, v):
    return _won(v) if label in ("비용", "전환매출") else f"{v:,.0f}"


def render_alerts(df: pd.DataFrame, date_d):
    """랜딩 최상단 알림 배너 렌더."""
    with st.container(border=True):
        alerts = compute_alerts(df, date_d=date_d, threshold=ALERT_THRESHOLD)
        st.markdown("### 🚨 오늘의 알림")
        if alerts["status"] == "empty":
            st.warning("선택 조건에 데이터가 없습니다.", icon="⚠️")
            return
        if alerts["status"] == "no_prev":
            d = pd.Timestamp(alerts["D"]).strftime("%Y-%m-%d") if alerts["D"] is not None else "-"
            st.info(f"전일 비교하려면 데이터가 2일 이상 필요합니다 (현재 {d} 하루).", icon="ℹ️")
            return

        D = pd.Timestamp(alerts["D"]).strftime("%Y-%m-%d")
        P = pd.Timestamp(alerts["D_prev"]).strftime("%Y-%m-%d")
        st.caption(f"기준일: **{D}** vs 직전일 **{P}** · 급변 기준 ±{ALERT_THRESHOLD}%")

        surges = [it for it in alerts["items"] if it["급변"]]
        if not surges:
            st.success("이상 없음 — 전일 대비 ±50% 초과 항목이 없습니다.", icon="✅")
        for it in alerts["items"]:
            label = it["지표"]
            if it["신규여부"]:
                st.markdown(f"🔴 **{label} 신규 발생** (0 → {_fmt(label, it['d'])})")
                continue
            rate = it["변화율"]
            cur, prev = _fmt(label, it["d"]), _fmt(label, it["prev"])
            if it["급변"]:
                arrow = "▲" if rate > 0 else "▼"
                cause = " · ".join(
                    f"{ch} {'+' if dv>=0 else ''}{_fmt(label, dv)}" for ch, dv in it["원인_top"]
                )
                st.markdown(f"🔴 **{label} {rate:+.0f}%** {arrow} ({prev} → {cur})")
                if cause:
                    st.caption(f"　원인 Top: {cause}")
            else:
                st.markdown(f"<span style='color:#9ca3af'>⚪ {label} {rate:+.0f}% (임계값 내, 정상)</span>",
                            unsafe_allow_html=True)


def generate_insights(df: pd.DataFrame) -> list[str]:
    """필터된 데이터에서 규칙 기반 인사이트 문장 생성 (수치 정확)."""
    out: list[str] = []
    met_rev = "구매매출_매체" if "구매매출_매체" in df else "구매매출"
    met_clk = "클릭_매체" if "클릭_매체" in df else "클릭"
    met_buy = "구매_매체" if "구매_매체" in df else "구매"

    # 1) 채널별 ROAS 최고/최저
    if "비용" in df and met_rev in df:
        ch = df.groupby("채널").agg(비용=("비용", "sum"), 매출=(met_rev, "sum")).reset_index()
        ch = ch[ch["비용"] > 0]
        if len(ch) >= 1:
            ch["ROAS"] = ch["매출"] / ch["비용"] * 100
            best, worst = ch.loc[ch["ROAS"].idxmax()], ch.loc[ch["ROAS"].idxmin()]
            out.append(f"📈 **ROAS 최고 채널은 `{best['채널']}` ({best['ROAS']:,.0f}%)**, "
                       f"최저는 `{worst['채널']}` ({worst['ROAS']:,.0f}%). "
                       + ("두 채널 간 예산 재배분을 검토하세요." if len(ch) >= 2 else ""))

    # 2) 비용 집중도
    if "비용" in df:
        chc = df.groupby("채널")["비용"].sum().sort_values(ascending=False)
        tot = chc.sum()
        if tot > 0:
            top = chc.index[0]
            out.append(f"💰 **전체 비용의 {chc.iloc[0]/tot*100:.0f}%가 `{top}`에 집중**"
                       f" (₩{chc.iloc[0]:,.0f} / ₩{tot:,.0f}).")

    # 3) 매체 vs AF 갭 최대 지표 (트래킹 점검 우선순위)
    gaps = []
    for m in GAP_METRICS:
        cm, ca = f"{m}_매체", f"{m}_af"
        if cm in df and ca in df and df[cm].sum() > 0:
            g = (df[cm].sum() - df[ca].sum()) / df[cm].sum() * 100
            gaps.append((m, g))
    if gaps:
        m, g = max(gaps, key=lambda x: abs(x[1]))
        out.append(f"🔀 **매체-AF 갭이 가장 큰 지표는 `{m}` ({g:+.1f}%)** — "
                   f"AF가 매체보다 {'적게' if g > 0 else '많게'} 집계. 어트리뷰션/트래킹 점검 1순위.")

    # 4) CPA 효율 캠페인 (비용 대비 구매)
    if "비용" in df and met_buy in df:
        cp = df.groupby("캠페인").agg(비용=("비용", "sum"), 구매=(met_buy, "sum")).reset_index()
        cp = cp[(cp["비용"] > 0) & (cp["구매"] > 0)]
        if len(cp) >= 2:
            cp["CPA"] = cp["비용"] / cp["구매"]
            lo, hi = cp.loc[cp["CPA"].idxmin()], cp.loc[cp["CPA"].idxmax()]
            out.append(f"🎯 **CPA 최저(효율↑) 캠페인 `{lo['캠페인']}` (₩{lo['CPA']:,.0f})** vs "
                       f"최고(효율↓) `{hi['캠페인']}` (₩{hi['CPA']:,.0f}), {hi['CPA']/lo['CPA']:.1f}배 차이.")

    # 5) 소재 유형(prefix)별 ROAS
    if "비용" in df and met_rev in df and "소재" in df:
        tmp = df.copy()
        tmp["유형"] = tmp["소재"].astype(str).str.split("_").str[0]
        cr = tmp.groupby("유형").agg(비용=("비용", "sum"), 매출=(met_rev, "sum")).reset_index()
        cr = cr[cr["비용"] > 0]
        if len(cr) >= 2:
            cr["ROAS"] = cr["매출"] / cr["비용"] * 100
            b = cr.loc[cr["ROAS"].idxmax()]
            out.append(f"🎨 **소재 유형 중 `{b['유형']}`의 ROAS가 가장 높음 ({b['ROAS']:,.0f}%)** — "
                       f"고효율 소재 포맷 비중 확대를 고려하세요.")

    return out


# ─────────────────────────── 사이드바 ───────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    _default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw")
    folder = st.text_input("데이터 폴더", value=_default)
    if st.button("🔄 새로고침", width="stretch"):
        st.cache_data.clear()
        st.rerun()

try:
    data = _load(folder, _folder_signature(folder))
except Exception as e:
    st.error(f"데이터를 불러오지 못했습니다: {e}")
    st.stop()

df = data["merged"].copy()

with st.sidebar:
    st.divider()
    st.subheader("🔎 필터")
    dmin, dmax = df["일"].min(), df["일"].max()
    if pd.notna(dmin):
        dr = st.date_input("기간", value=(dmin, dmax), min_value=dmin, max_value=dmax)
        if isinstance(dr, tuple) and len(dr) == 2:
            df = df[(df["일"] >= pd.Timestamp(dr[0])) & (df["일"] <= pd.Timestamp(dr[1]))]
    channels = sorted(df["채널"].dropna().unique())
    sel_ch = st.multiselect("채널", channels, default=channels)
    df = df[df["채널"].isin(sel_ch)]
    camps = sorted(df["캠페인"].dropna().unique())
    sel_cp = st.multiselect("캠페인", camps, default=camps)
    df = df[df["캠페인"].isin(sel_cp)]

    st.divider()
    _dates = sorted(pd.to_datetime(df["일"]).dropna().dt.strftime("%Y-%m-%d").unique(), reverse=True)
    alert_date = st.selectbox("🚨 알림 비교 기준일", _dates, index=0) if _dates else None

st.title("📊 마케팅 성과 대시보드")
st.caption("채널(매체) 집행데이터 × 앱스플라이어(MMP) 어트리뷰션 — 갭 분석 & EDA")

for w in data["warnings"]:
    (st.warning if "누락" in w else st.info)(w, icon="⚠️" if "누락" in w else "ℹ️")

if df.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# ─────────────────────────── 알림 배너 (최상단) ───────────────────────────
render_alerts(df, alert_date)


# ─────────────────────────── KPI ───────────────────────────
tot_cost = df["비용"].sum() if "비용" in df else 0
tot_imp = df["노출"].sum() if "노출" in df else 0
clk_m = df["클릭_매체"].sum() if "클릭_매체" in df else df.get("클릭", pd.Series()).sum()
buy_m = df["구매_매체"].sum() if "구매_매체" in df else df.get("구매", pd.Series()).sum()
rev_m = df["구매매출_매체"].sum() if "구매매출_매체" in df else df.get("구매매출", pd.Series()).sum()
ctr = clk_m / tot_imp if tot_imp else 0
cpa = tot_cost / buy_m if buy_m else 0
roas = rev_m / tot_cost if tot_cost else 0

with st.container(horizontal=True):
    st.metric("총 비용", _won(tot_cost), border=True)
    st.metric("총 노출", f"{tot_imp:,.0f}", border=True)
    st.metric("총 클릭 (매체)", f"{clk_m:,.0f}", border=True)
    st.metric("평균 CTR", f"{ctr*100:.2f}%", border=True)
    st.metric("총 구매 (매체)", f"{buy_m:,.0f}", border=True)
    st.metric("CPA", _won(cpa), border=True)
    st.metric("ROAS", f"{roas*100:,.0f}%", border=True)

# ─────────────────────────── 자동 인사이트 ───────────────────────────
with st.container(border=True):
    st.markdown("### 💡 자동 인사이트")
    insights = generate_insights(df)
    if insights:
        for line in insights:
            st.markdown(f"- {line}")
        st.caption("※ 필터 조건 기준으로 자동 계산된 수치입니다 (정확도: 정확 / 규칙 기반).")
    else:
        st.info("인사이트를 계산할 지표가 부족합니다.")

tab_gap, tab_perf, tab_eda = st.tabs(["🔀 매체 vs AF 갭", "📈 성과·효율", "🔍 데이터 상태(EDA)"])

# ─────────────────────────── 탭1: 갭 분석 ───────────────────────────
with tab_gap:
    st.markdown("**매체 리포트 vs 앱스플라이어 어트리뷰션 비교** — 갭이 크면 트래킹/어트리뷰션 점검 필요")
    present = [m for m in GAP_METRICS if f"{m}_매체" in df.columns and f"{m}_af" in df.columns]
    if not present:
        st.info("비교 가능한 공통 지표가 없습니다.")
    else:
        rows = []
        for m in present:
            rows.append({"지표": m, "출처": "매체", "값": df[f"{m}_매체"].sum()})
            rows.append({"지표": m, "출처": "AF", "값": df[f"{m}_af"].sum()})
        comp = pd.DataFrame(rows)
        c1, c2 = st.columns([3, 2])
        with c1:
            with st.container(border=True):
                st.markdown("**지표별 매체 vs AF 합계**")
                chart = alt.Chart(comp).mark_bar().encode(
                    x=alt.X("지표:N", title=None),
                    xOffset="출처:N",
                    y=alt.Y("값:Q", title=None),
                    color=alt.Color("출처:N", scale=alt.Scale(domain=["매체", "AF"], range=[POINT, "#f59e0b"])),
                    tooltip=["지표", "출처", alt.Tooltip("값:Q", format=",")],
                ).properties(height=320)
                st.altair_chart(chart, width="stretch")
        with c2:
            with st.container(border=True):
                st.markdown("**갭% (매체 대비 AF 차이)**")
                summ = pd.DataFrame({
                    "지표": present,
                    "매체": [df[f"{m}_매체"].sum() for m in present],
                    "AF": [df[f"{m}_af"].sum() for m in present],
                })
                summ["갭%"] = (summ["매체"] - summ["AF"]) / summ["매체"].where(summ["매체"] != 0) * 100
                st.dataframe(
                    summ, hide_index=True, width="stretch",
                    column_config={
                        "매체": st.column_config.NumberColumn(format="%d"),
                        "AF": st.column_config.NumberColumn(format="%d"),
                        "갭%": st.column_config.NumberColumn(format="%.1f%%"),
                    },
                )
        # 채널별 갭 히트맵
        gap_cols = [f"{m}_갭%" for m in present if f"{m}_갭%" in df.columns]
        if gap_cols:
            with st.container(border=True):
                st.markdown("**채널별 평균 갭%**")
                ch_gap = df.groupby("채널")[gap_cols].mean().reset_index()
                melt = ch_gap.melt("채널", var_name="지표", value_name="갭%")
                melt["지표"] = melt["지표"].str.replace("_갭%", "")
                heat = alt.Chart(melt).mark_rect().encode(
                    x=alt.X("지표:N", title=None),
                    y=alt.Y("채널:N", title=None),
                    color=alt.Color("갭%:Q", scale=alt.Scale(scheme="redyellowgreen", reverse=True, domainMid=0)),
                    tooltip=["채널", "지표", alt.Tooltip("갭%:Q", format=".1f")],
                ).properties(height=140)
                st.altair_chart(heat, width="stretch")

# ─────────────────────────── 탭2: 성과·효율 ───────────────────────────
with tab_perf:
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("**채널별 비용 / ROAS**")
            ch = df.groupby("채널").agg(비용=("비용", "sum"),
                                     매출=(("구매매출_매체" if "구매매출_매체" in df else "구매매출"), "sum")).reset_index()
            ch["ROAS%"] = ch["매출"] / ch["비용"].where(ch["비용"] != 0) * 100
            base = alt.Chart(ch)
            bar = base.mark_bar(color=POINT).encode(x=alt.X("채널:N", title=None), y=alt.Y("비용:Q", title="비용"))
            line = base.mark_line(color=BAD, point=True).encode(x="채널:N", y=alt.Y("ROAS%:Q", title="ROAS%"))
            st.altair_chart(alt.layer(bar, line).resolve_scale(y="independent").properties(height=300), width="stretch")
    with c2:
        with st.container(border=True):
            st.markdown("**일자별 비용·클릭 추이**")
            daily = df.groupby("일").agg(비용=("비용", "sum"),
                                      클릭=(("클릭_매체" if "클릭_매체" in df else "클릭"), "sum")).reset_index()
            b = alt.Chart(daily).mark_bar(color=POINT, opacity=0.5).encode(x=alt.X("일:T", title=None), y=alt.Y("비용:Q", title="비용"))
            l = alt.Chart(daily).mark_line(color=BAD, point=True).encode(x="일:T", y=alt.Y("클릭:Q", title="클릭"))
            st.altair_chart(alt.layer(b, l).resolve_scale(y="independent").properties(height=300), width="stretch")
    with st.container(border=True):
        st.markdown("**소재별 효율 Top 15 (ROAS 기준)**")
        met = "구매매출_매체" if "구매매출_매체" in df else "구매매출"
        cr = df.groupby(["채널", "소재"]).agg(비용=("비용", "sum"), 매출=(met, "sum")).reset_index()
        cr["ROAS%"] = cr["매출"] / cr["비용"].where(cr["비용"] != 0) * 100
        cr = cr.sort_values("ROAS%", ascending=False).head(15)
        st.dataframe(cr, hide_index=True, width="stretch",
                     column_config={"비용": st.column_config.NumberColumn(format="%d"),
                                    "매출": st.column_config.NumberColumn(format="%d"),
                                    "ROAS%": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=float(cr["ROAS%"].max() or 1))})

# ─────────────────────────── 탭3: EDA ───────────────────────────
with tab_eda:
    with st.container(horizontal=True):
        st.metric("병합 행수", f"{len(df):,}", border=True)
        st.metric("채널 파일", f"{len(data['files']['channel'])}개", border=True)
        st.metric("AF 파일", f"{len(data['files']['appsflyer'])}개", border=True)
        st.metric("기간", f"{df['일'].min():%Y-%m-%d} ~ {df['일'].max():%Y-%m-%d}", border=True)
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("**결측치 (병합 후)**")
            miss = df.isna().sum()
            miss = miss[miss > 0]
            st.dataframe(miss.rename("결측수").to_frame(), width="stretch") if not miss.empty else st.success("결측치 없음")
    with c2:
        with st.container(border=True):
            st.markdown("**로드된 파일**")
            for k, ps in data["files"].items():
                st.write(f"**{k}**")
                for p in ps:
                    st.caption(f"• {os.path.basename(p)}")
    with st.container(border=True):
        st.markdown("**기술통계**")
        st.dataframe(df.describe().T, width="stretch")

# ─────────────────────────── 원본 테이블 + 다운로드 ───────────────────────────
with st.expander("📄 병합 데이터 전체 보기 / 다운로드"):
    st.dataframe(df, hide_index=True, width="stretch")
    st.download_button("CSV 다운로드", df.to_csv(index=False).encode("utf-8-sig"),
                       "marketing_merged.csv", "text/csv")
