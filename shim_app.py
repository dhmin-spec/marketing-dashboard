# shim_app.py — 심의 의견 반영 (Google Gemini API 자동 버전)
import datetime as dt
import pandas as pd
import streamlit as st
from google import genai

from shim.excel_io import read_copies, build_revised_workbook, SheetNotFoundError
from shim.opinions import referenced_numbers
from shim.ai_revise import revise

st.set_page_config(page_title="심의 의견 반영", page_icon="📝", layout="wide")


def _gate() -> bool:
    """APP_PASSWORD 시크릿이 설정된 경우에만 비밀번호를 요구한다(선택)."""
    try:
        app_password = st.secrets["APP_PASSWORD"]
    except Exception:
        app_password = None  # secrets 파일/키가 없으면 게이트 없이 통과
    if not app_password or st.session_state.get("authed"):
        return True
    pw = st.text_input("비밀번호", type="password")
    if pw and pw == app_password:
        st.session_state["authed"] = True
        return True
    if pw:
        st.error("비밀번호가 틀렸습니다.")
    return False


_TRANSIENT = ("503", "unavailable", "429", "resource_exhausted",
              "high demand", "overloaded", "try again later")


def _is_transient(err: Exception) -> bool:
    return any(t in str(err).lower() for t in _TRANSIENT)


def _candidate_models(client) -> list[str]:
    """flash 우선으로 정렬한 generateContent 가능 모델 목록.
    GEMINI_MODEL 시크릿이 있으면 그것만 사용."""
    import re
    try:
        override = st.secrets["GEMINI_MODEL"]
    except Exception:
        override = None
    if override:
        return [override]
    if st.session_state.get("gemini_models"):
        return st.session_state["gemini_models"]

    names = []
    for m in client.models.list():
        acts = getattr(m, "supported_actions", None) or []
        if "generateContent" in acts:
            names.append(m.name.split("/")[-1])

    def score(n: str) -> float:
        nl, s = n.lower(), 0.0
        if "flash" in nl:
            s += 100            # flash = 저렴·무료 구간
        elif "pro" in nl:
            s += 40
        if "preview" in nl or "exp" in nl:
            s -= 10             # 안정 버전 우선
        mm = re.search(r"(\d+(?:\.\d+)?)", nl)
        if mm:
            s += float(mm.group(1))
        return s

    ordered = sorted(names, key=score, reverse=True) or ["gemini-flash-latest"]
    st.session_state["gemini_models"] = ordered
    return ordered


def _make_call_fn():
    import time
    client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])
    models = _candidate_models(client)

    def call_fn(prompt: str) -> str:
        last = None
        for model in models:
            for attempt in range(3):  # 과부하 시 백오프 재시도
                try:
                    resp = client.models.generate_content(model=model, contents=prompt)
                    st.session_state["gemini_model"] = model
                    return resp.text or ""
                except Exception as e:
                    last = e
                    if _is_transient(e):
                        if attempt < 2:
                            time.sleep(1.5 * (attempt + 1))
                            continue
                        break  # 이 모델은 계속 과부하 → 다음 후보로
                    raise      # 그 외 오류는 즉시 표면화
        raise last

    return call_fn


if not _gate():
    st.stop()

st.title("📝 심의 의견 자동 반영")
st.warning("AI 자동 수정본입니다. 발송 전 반드시 검수하세요. (정확도: 추정)")

up = st.file_uploader("심의안 엑셀(.xlsx) 업로드", type="xlsx")
if not up:
    st.stop()

raw = up.getvalue()
file_id = (up.name, len(raw))
if st.session_state.get("file_id") != file_id:
    st.session_state["file_id"] = file_id
    st.session_state.pop("revs", None)
try:
    copies = read_copies(raw)
except SheetNotFoundError as e:
    st.error(f"엑셀 인식 실패: {e}")
    st.stop()

st.subheader("문안 목록")
st.dataframe(pd.DataFrame([
    {"번호": c.no, "광고위치": c.position, "원문": c.text,
     "글자수": len(c.text), "제한": c.max_len} for c in copies
]), use_container_width=True)

opinions = st.text_area("심의 의견 붙여넣기", height=200,
                        placeholder="2번 문안: '원문' -> 수정 지시 / 6번 문안: ...")

if st.button("AI 수정 실행", type="primary") and opinions.strip():
    with st.spinner("Gemini가 문안을 수정 중..."):
        try:
            revs = revise(copies, opinions, _make_call_fn())
        except Exception as e:
            st.error(f"AI 수정 실패: {e}. 잠시 후 [AI 수정 실행]을 다시 눌러주세요.")
            st.stop()
    st.session_state["revs"] = {r.no: r for r in revs}
    if st.session_state.get("gemini_model"):
        st.caption(f"사용 모델: {st.session_state['gemini_model']}")
    # 매칭 실패 탐지
    copy_nos = {c.no for c in copies}
    missing = referenced_numbers(opinions) - copy_nos
    if missing:
        st.warning(f"의견이 참조했지만 표에 없는 번호: {sorted(missing)}")
    dropped = (referenced_numbers(opinions) & copy_nos) - set(st.session_state.get("revs", {}).keys())
    if dropped:
        st.warning(f"의견은 있으나 AI가 수정하지 않은 번호: {sorted(dropped)}")

if "revs" in st.session_state:
    revs = st.session_state["revs"]
    limit_by_no = {c.no: c.max_len for c in copies}
    text_by_no = {c.no: c.text for c in copies}
    df = pd.DataFrame([
        {"번호": no, "원문": text_by_no.get(no, ""), "수정문": r.revised,
         "제한": limit_by_no.get(no), "사유": r.reason}
        for no, r in sorted(revs.items())
    ])
    st.subheader("검수 (수정문 직접 편집 가능)")
    edited = st.data_editor(df, use_container_width=True,
                            disabled=["번호", "원문", "제한", "사유"])

    edited = edited.copy()
    edited["글자수"] = edited["수정문"].str.len()
    over = edited[(edited["제한"].notna()) & (edited["글자수"] > edited["제한"])]
    if len(over):
        st.error(f"제한 초과 문안 {len(over)}건 — 수정문을 줄여주세요: 번호 {list(over['번호'])}")

    if not len(over):
        revisions = {int(row["번호"]): row["수정문"] for _, row in edited.iterrows()}
        out = build_revised_workbook(raw, revisions)
        name = up.name.rsplit(".", 1)[0]
        today = dt.date.today().strftime("%Y%m%d")
        st.download_button("📥 다운로드", data=out,
                           file_name=f"{name}_심의반영_{today}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
