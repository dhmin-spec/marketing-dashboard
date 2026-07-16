# shim_app.py
import datetime as dt
import pandas as pd
import streamlit as st
import anthropic

from shim.excel_io import read_copies, build_revised_workbook, SheetNotFoundError
from shim.opinions import referenced_numbers
from shim.ai_revise import revise

st.set_page_config(page_title="심의 의견 반영", page_icon="📝", layout="wide")


def _gate() -> bool:
    if st.session_state.get("authed"):
        return True
    pw = st.text_input("비밀번호", type="password")
    if pw and pw == st.secrets.get("APP_PASSWORD"):
        st.session_state["authed"] = True
        return True
    if pw:
        st.error("비밀번호가 틀렸습니다.")
    return False


def _make_call_fn():
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

    def call_fn(prompt: str) -> str:
        resp = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")

    return call_fn


if not _gate():
    st.stop()

st.title("📝 심의 의견 자동 반영")
st.warning("AI 자동 수정본입니다. 발송 전 반드시 검수하세요. (정확도: 추정)")

up = st.file_uploader("심의안 엑셀(.xlsx) 업로드", type="xlsx")
if not up:
    st.stop()

raw = up.getvalue()
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
    with st.spinner("Claude가 문안을 수정 중..."):
        revs = revise(copies, opinions, _make_call_fn())
    st.session_state["revs"] = {r.no: r for r in revs}
    # 매칭 실패 탐지
    missing = referenced_numbers(opinions) - {c.no for c in copies}
    if missing:
        st.warning(f"의견이 참조했지만 표에 없는 번호: {sorted(missing)}")

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

    if st.button("엑셀 다운로드 생성", disabled=len(over) > 0):
        revisions = {int(row["번호"]): row["수정문"] for _, row in edited.iterrows()}
        out = build_revised_workbook(raw, revisions)
        name = up.name.rsplit(".", 1)[0]
        today = dt.date.today().strftime("%Y%m%d")
        st.download_button("📥 다운로드", data=out,
                           file_name=f"{name}_심의반영_{today}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
