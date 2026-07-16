# shim_app.py — 심의 의견 반영 (복붙 브리지 버전, API 키 불필요)
import datetime as dt
import pandas as pd
import streamlit as st

from shim.excel_io import read_copies, build_revised_workbook, SheetNotFoundError
from shim.opinions import referenced_numbers
from shim.ai_revise import build_prompt, parse_revisions

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


def _extract_revisions(raw: str):
    """AI 답변에서 수정문 JSON을 최대한 관대하게 추출한다."""
    try:
        return parse_revisions(raw)
    except Exception:
        s, e = raw.find("["), raw.rfind("]")
        if s != -1 and e != -1 and e > s:
            return parse_revisions(raw[s:e + 1])
        raise


if not _gate():
    st.stop()

st.title("📝 심의 의견 자동 반영 (복붙 브리지)")
st.warning(
    "AI 자동 수정본입니다. 발송 전 반드시 검수하세요. (정확도: 추정) — "
    "AI 수정은 무료 채팅(claude.ai / ChatGPT)에서 처리하고, 엑셀 작업은 이 사이트가 자동으로 합니다."
)

# --- 1. 업로드 ---
up = st.file_uploader("① 심의안 엑셀(.xlsx) 업로드", type="xlsx")
if not up:
    st.stop()

raw = up.getvalue()
file_id = (up.name, len(raw))
if st.session_state.get("file_id") != file_id:
    st.session_state["file_id"] = file_id
    st.session_state.pop("answer", None)

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

# --- 2. 의견 입력 → 프롬프트 생성 ---
opinions = st.text_area(
    "② 심의 의견 붙여넣기", height=180,
    placeholder="2번 문안: '원문' -> 수정 지시 / 6번 문안: ...",
)

if opinions.strip():
    prompt = build_prompt(copies, opinions)
    st.subheader("③ 아래 프롬프트를 복사 → claude.ai 또는 ChatGPT에 붙여넣기")
    st.caption("코드 박스 오른쪽 위 복사 버튼을 누르세요. 채팅이 JSON으로 답하면 그 답 전체를 복사합니다.")
    st.code(prompt, language="text")

    # --- 3. AI 답변 붙여넣기 ---
    st.subheader("④ AI 답변(JSON)을 여기에 붙여넣기")
    answer = st.text_area(
        "AI 답변", height=180, key="answer",
        placeholder='[{"no": 2, "revised": "수정된 문안", "reason": "사유"}]',
    )

    if answer.strip():
        try:
            revs = _extract_revisions(answer)
        except Exception:
            st.error("JSON을 읽지 못했습니다. 채팅 답변에서 대괄호 [ ] 로 시작하는 JSON 부분까지 포함해 다시 붙여넣어 주세요.")
            st.stop()

        rev_by_no = {r.no: r for r in revs}
        copy_nos = {c.no for c in copies}

        missing = referenced_numbers(opinions) - copy_nos
        if missing:
            st.warning(f"의견이 참조했지만 표에 없는 번호: {sorted(missing)}")
        dropped = (referenced_numbers(opinions) & copy_nos) - set(rev_by_no)
        if dropped:
            st.warning(f"의견은 있으나 수정되지 않은 번호: {sorted(dropped)}")

        limit_by_no = {c.no: c.max_len for c in copies}
        text_by_no = {c.no: c.text for c in copies}
        df = pd.DataFrame([
            {"번호": no, "원문": text_by_no.get(no, ""), "수정문": r.revised,
             "제한": limit_by_no.get(no), "사유": r.reason}
            for no, r in sorted(rev_by_no.items())
        ])

        st.subheader("⑤ 검수 (수정문 직접 편집 가능)")
        edited = st.data_editor(
            df, use_container_width=True,
            disabled=["번호", "원문", "제한", "사유"],
        ).copy()
        edited["글자수"] = edited["수정문"].str.len()
        over = edited[(edited["제한"].notna()) & (edited["글자수"] > edited["제한"])]
        if len(over):
            st.error(f"제한 초과 문안 {len(over)}건 — 수정문을 줄여주세요: 번호 {list(over['번호'])}")
        else:
            revisions = {int(row["번호"]): row["수정문"] for _, row in edited.iterrows()}
            out = build_revised_workbook(raw, revisions)
            name = up.name.rsplit(".", 1)[0]
            today = dt.date.today().strftime("%Y%m%d")
            st.download_button(
                "⑥ 📥 엑셀 다운로드", data=out,
                file_name=f"{name}_심의반영_{today}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
