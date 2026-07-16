"""마케팅 데이터 전처리 파이프라인 (채널 매체데이터 + 앱스플라이어 MMP데이터).

폴더 안의 모든 `*_channel.csv` / `*_appsflyer.csv` 를 자동으로 모아
[일·채널·캠페인·그룹·소재] 기준으로 OUTER JOIN 하고 파생·갭 지표를 계산한다.

- 매일 전날 파일만 폴더에 추가하면, load_folder() 가 폴더 전체를 다시 읽어 반영.
- 대시보드(mkt_dashboard.py)와 배치 스크립트 양쪽에서 재사용.
"""
from __future__ import annotations
import glob
import os
import pandas as pd

# 앱스플라이어 미디어소스 → 채널 표기 매핑 (신규 매체 생기면 여기만 추가)
AF_TO_CHANNEL = {
    "googleadwords_int": "구글",
    "Facebook Ads": "메타",
    "naver_search": "네이버",
}

JOIN_KEYS = ["일", "채널", "캠페인", "그룹", "소재"]
# 양쪽에 공통으로 존재해 갭 비교 대상이 되는 성과 지표
GAP_METRICS = ["클릭", "회원가입", "구매", "구매매출"]


def _read_csv(path: str) -> pd.DataFrame:
    """인코딩 자동 판별(utf-8-sig → cp949) 후 읽기."""
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return pd.read_csv(path, encoding="utf-8", errors="replace")


def _concat(paths: list[str]) -> pd.DataFrame:
    frames = [_read_csv(p) for p in paths]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_folder(folder: str) -> dict:
    """폴더 내 채널/AF CSV 를 모두 로드·조인해 결과 dict 반환.

    반환: {"merged": df, "channel": df, "af": df, "warnings": [...], "files": {...}}
    """
    # 하위 폴더까지 재귀 탐색 (data/raw/channel/*.csv 등)
    ch_paths = sorted(glob.glob(os.path.join(folder, "**", "*_channel.csv"), recursive=True))
    af_paths = sorted(glob.glob(os.path.join(folder, "**", "*_appsflyer.csv"), recursive=True))
    warnings: list[str] = []

    ch = _concat(ch_paths)
    af = _concat(af_paths)
    if ch.empty and af.empty:
        raise FileNotFoundError(
            f"'{folder}' 에서 *_channel.csv / *_appsflyer.csv 를 찾지 못했습니다."
        )

    # 숫자 컬럼 정제 (천단위 콤마 제거, 빈값 0)
    numeric = ["노출", "클릭", "비용", "회원가입", "구매", "구매매출"]
    for df in (ch, af):
        for col in numeric:
            if col in df.columns:
                df[col] = (
                    df[col].astype(str).str.replace(",", "", regex=False)
                    .replace({"-": "0", "": "0", "nan": "0"})
                )
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # AF: 미디어소스 → 채널 매핑
    if not af.empty:
        af = af.rename(columns={"미디어소스": "채널"})
        unmapped = sorted(set(af["채널"]) - set(AF_TO_CHANNEL))
        if unmapped:
            warnings.append(
                "AF 미디어소스 매핑 누락 → 조인 안 됨: " + ", ".join(unmapped)
                + " (AF_TO_CHANNEL 에 추가하세요)"
            )
        af["채널"] = af["채널"].map(AF_TO_CHANNEL).fillna(af["채널"])

    # 키 문자열 정규화(공백 제거)
    for df in (ch, af):
        for k in JOIN_KEYS:
            if k in df.columns:
                df[k] = df[k].astype(str).str.strip()

    # 집계(동일 키 중복 행 합산) 후 OUTER JOIN
    ch_metrics = [c for c in ["노출", "클릭", "비용", "회원가입", "구매", "구매매출"] if c in ch.columns]
    af_metrics = [c for c in GAP_METRICS if c in af.columns]
    # 채널 부가 컬럼(채널분류·캠페인목적)은 첫값 유지
    extra = [c for c in ["채널분류", "캠페인목적"] if c in ch.columns]

    ch_g = ch.groupby(JOIN_KEYS, as_index=False).agg(
        {**{m: "sum" for m in ch_metrics}, **{e: "first" for e in extra}}
    ) if not ch.empty else pd.DataFrame(columns=JOIN_KEYS)
    af_g = af.groupby(JOIN_KEYS, as_index=False).agg(
        {m: "sum" for m in af_metrics}
    ) if not af.empty else pd.DataFrame(columns=JOIN_KEYS)

    merged = ch_g.merge(af_g, on=JOIN_KEYS, how="outer", suffixes=("_매체", "_af"))

    # 조인 매칭 통계
    if not ch_g.empty and not af_g.empty:
        matched = ch_g.merge(af_g[JOIN_KEYS], on=JOIN_KEYS, how="inner").shape[0]
        warnings.append(
            f"조인 매칭: {matched}건 (채널 {len(ch_g)}행 / AF {len(af_g)}행)"
        )

    merged = _derive(merged)
    merged["일"] = pd.to_datetime(merged["일"], errors="coerce")
    return {
        "merged": merged.sort_values(["일", "채널", "캠페인", "그룹", "소재"]).reset_index(drop=True),
        "channel": ch, "af": af,
        "warnings": warnings,
        "files": {"channel": ch_paths, "appsflyer": af_paths},
    }


def _safe_div(a, b):
    return (a / b).where(b != 0)


def _derive(df: pd.DataFrame) -> pd.DataFrame:
    """파생지표(매체 기준) + 매체 vs AF 갭(%) 계산."""
    g = lambda c: df[c] if c in df.columns else 0
    # 매체 기준 효율지표
    if "노출" in df.columns:
        df["CTR"] = _safe_div(g("클릭_매체") if "클릭_매체" in df.columns else g("클릭"), g("노출"))
    click_m = df["클릭_매체"] if "클릭_매체" in df.columns else df.get("클릭")
    if "비용" in df.columns:
        df["CPC"] = _safe_div(g("비용"), click_m)
        buy_m = df["구매_매체"] if "구매_매체" in df.columns else df.get("구매")
        df["CPA"] = _safe_div(g("비용"), buy_m)
        rev_m = df["구매매출_매체"] if "구매매출_매체" in df.columns else df.get("구매매출")
        df["ROAS"] = _safe_div(rev_m, g("비용"))
    # 매체 vs AF 갭% = (매체 - AF) / 매체
    for m in GAP_METRICS:
        cm, ca = f"{m}_매체", f"{m}_af"
        if cm in df.columns and ca in df.columns:
            df[f"{m}_갭%"] = _safe_div(df[cm] - df[ca], df[cm]) * 100
    return df


# 알림 감시 지표: (표시라벨, 우선 컬럼, 폴백 컬럼)
ALERT_METRICS = [("비용", "비용", None), ("클릭", "클릭_매체", "클릭"), ("전환", "구매_매체", "구매")]
ALERT_THRESHOLD = 50  # |변화율| ≥ 50% → 급변


def _resolve(df: pd.DataFrame, col: str, fallback):
    if col in df.columns:
        return col
    if fallback and fallback in df.columns:
        return fallback
    return None


def _channel_deltas(df: pd.DataFrame, col: str, d, prev, top: int = 3):
    """채널별 D vs D_prev 차이(Δ) 큰 순 Top."""
    if "채널" not in df.columns:
        return []
    dd = df[df["일"] == d].groupby("채널")[col].sum()
    pp = df[df["일"] == prev].groupby("채널")[col].sum()
    delta = dd.subtract(pp, fill_value=0)
    delta = delta[delta != 0].reindex(delta.abs().sort_values(ascending=False).index)
    return [(ch, float(v)) for ch, v in delta.head(top).items()]


def compute_alerts(df: pd.DataFrame, date_d=None, threshold: int = ALERT_THRESHOLD,
                   metrics=ALERT_METRICS) -> dict:
    """전일 대비 급변 알림 계산 (계정 총합, 순수 함수).

    반환: {"D", "D_prev", "status": "ok|no_prev|empty", "items": [...]}
      item: {"지표","변화율"|None,"d","prev","신규여부","급변","원인_top":[(채널,Δ)]}
    """
    if df is None or df.empty or "일" not in df.columns:
        return {"D": None, "D_prev": None, "status": "empty", "items": []}
    dates = sorted(pd.to_datetime(df["일"]).dropna().unique())
    if not dates:
        return {"D": None, "D_prev": None, "status": "empty", "items": []}
    D = pd.Timestamp(date_d) if date_d is not None else dates[-1]
    prevs = [x for x in dates if x < D]
    if not prevs:
        return {"D": D, "D_prev": None, "status": "no_prev", "items": []}
    D_prev = prevs[-1]

    items = []
    for label, col, fb in metrics:
        c = _resolve(df, col, fb)
        if c is None:
            continue
        d_val = float(df.loc[df["일"] == D, c].sum())
        p_val = float(df.loc[df["일"] == D_prev, c].sum())
        if p_val == 0:
            item = {"지표": label, "변화율": None, "d": d_val, "prev": p_val,
                    "신규여부": d_val > 0, "급변": d_val > 0, "원인_top": []}
        else:
            rate = (d_val - p_val) / p_val * 100
            surge = abs(rate) >= threshold
            item = {"지표": label, "변화율": rate, "d": d_val, "prev": p_val,
                    "신규여부": False, "급변": surge,
                    "원인_top": _channel_deltas(df, c, D, D_prev) if surge else []}
        items.append(item)
    return {"D": D, "D_prev": D_prev, "status": "ok", "items": items}


if __name__ == "__main__":
    import sys
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    out = load_folder(folder)
    m = out["merged"]
    print("파일:", out["files"])
    for w in out["warnings"]:
        print("  -", w)
    print("병합 shape:", m.shape)
    print(m.head(10).to_string())
    # 배치용 합본 저장 (data/processed 우선, 없으면 folder)
    proc = os.path.join(folder, "..", "processed")
    outdir = proc if os.path.isdir(proc) else folder
    combined = os.path.join(outdir, "_combined.parquet")
    try:
        m.to_parquet(combined)
        print("저장:", combined)
    except Exception as e:
        m.to_csv(os.path.join(folder, "_combined.csv"), index=False, encoding="utf-8-sig")
        print("parquet 실패, csv 저장:", e)
