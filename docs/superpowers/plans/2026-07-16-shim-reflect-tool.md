# 심의 의견 자동 반영 도구 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 심의안 엑셀을 업로드하고 심의 의견을 붙여넣으면 Claude가 최대 글자수(H열) 안에서 문안을 수정한 새 엑셀을 다운로드받는 사내 Streamlit 웹앱을 만든다.

**Architecture:** 순수 로직(엑셀 IO·의견 파싱·AI 수정)을 `shim/` 패키지로 분리하고 `shim_app.py`가 Streamlit UI로 조립한다. AI 호출은 `call_fn(prompt)->str` 주입으로 추상화해 로직을 API 없이 테스트한다. 원본 워크북을 복제하고 수정 행의 D열(+`업로드용` C열)만 덮어써 서식·수식을 보존한다.

**Tech Stack:** Python, Streamlit, openpyxl, anthropic (SDK), pytest.

## Global Constraints

- 대상 시트: `검색광고 T&D` — 헤더 4행, 데이터 5행부터. 열: NO=C(3), 문구=D(4), 글자수=E(5, `=LEN` 수식·유지), 광고위치=F(6), 최대글자수=H(8).
- `업로드용` 시트: C열(3)=문안 고정값, D열(4)=`=A&B&C` 수식. T&D 데이터 순서와 1:1 매핑.
- 글자수 규칙: `len()` (공백 포함, 한글 1자=1).
- **최대 글자수(H)는 하드 제약** — 초과 시 자동 축약 1회, 그래도 초과면 사람에게(임의 자르기 금지).
- 원본 워크북 복제 후 D열(+업로드용 C열)만 수정, 나머지 시트·서식·수식 무변경.
- 의견 없는 번호는 원본 유지. 카피 최종 결정은 사람 검수.
- UI 라벨 한국어, 코드 식별자·컬럼 영어.
- 민감 자료: 실제 광고주 파일을 깃에 커밋 금지 — 테스트는 합성 픽스처 사용.

---

### Task 1: 테스트 픽스처 빌더

합성 심의안 워크북을 만드는 헬퍼. 이후 모든 엑셀 테스트가 이걸 쓴다.

**Files:**
- Create: `shim/__init__.py` (빈 파일)
- Create: `tests/conftest.py`
- Test: (이 태스크가 픽스처 자체이므로 별도 실패 테스트 없음 — 스모크로 검증)

**Interfaces:**
- Produces: `sample_workbook_bytes() -> bytes` — 3시트(`드롭다운 수식`, `검색광고 T&D`, `업로드용`) 워크북의 xlsx 바이트. T&D 데이터 3행(NO 1~3), 업로드용 3행.

- [ ] **Step 1: 빈 패키지 파일 생성**

`shim/__init__.py` 를 빈 파일로 생성.

- [ ] **Step 2: conftest 픽스처 작성**

```python
# tests/conftest.py
import io
import openpyxl
import pytest

SHEET_TND = "검색광고 T&D"
SHEET_UPLOAD = "업로드용"


def _build() -> bytes:
    wb = openpyxl.Workbook()
    # sheet 1: 드롭다운 수식 (반드시 무변경으로 남아야 함)
    d = wb.active
    d.title = "드롭다운 수식"
    d["B1"] = "가나보험"
    d["C1"] = "=B1"  # 수식 보존 확인용

    # sheet 2: 검색광고 T&D
    t = wb.create_sheet(SHEET_TND)
    t["B4"], t["C4"], t["D4"] = "보종", "NO", "문구 및 이미지"
    t["E4"], t["F4"], t["H4"] = "글자수", "광고위치", "비고"
    rows = [
        (1, "판매 수수료가 없어 저렴한 가나다이렉트", "설명문구", 45),
        (2, "AI맞춤보장", "추가제목", 15),
        (3, "보험료확인", "서브링크", 6),
    ]
    for i, (no, text, pos, mx) in enumerate(rows):
        r = 5 + i
        t.cell(r, 2, "전 보종")
        t.cell(r, 3, no)
        t.cell(r, 4, text)
        t.cell(r, 5, f"=LEN(D{r})")
        t.cell(r, 6, pos)
        t.cell(r, 8, mx)

    # sheet 3: 업로드용 (C=문안 고정값, D=수식)
    u = wb.create_sheet(SHEET_UPLOAD)
    for i, (_no, text, _pos, _mx) in enumerate(rows):
        r = 1 + i
        u.cell(r, 1, "전 보종")
        u.cell(r, 2, ">")
        u.cell(r, 3, text)
        u.cell(r, 4, f"=A{r}&B{r}&C{r}")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_workbook_bytes() -> bytes:
    return _build()
```

- [ ] **Step 3: 픽스처 로드 스모크 테스트**

```python
# tests/test_fixture.py
import io
import openpyxl
from tests.conftest import _build


def test_fixture_has_expected_structure():
    wb = openpyxl.load_workbook(io.BytesIO(_build()))
    assert wb.sheetnames == ["드롭다운 수식", "검색광고 T&D", "업로드용"]
    t = wb["검색광고 T&D"]
    assert t["C4"].value == "NO"
    assert t["D5"].value == "판매 수수료가 없어 저렴한 가나다이렉트"
    assert t["H6"].value == 15
```

- [ ] **Step 4: 실행해서 통과 확인**

Run: `python -m pytest tests/test_fixture.py -v`
Expected: PASS (2 sheets 헬퍼 + 구조 확인)

- [ ] **Step 5: 커밋**

```bash
git add shim/__init__.py tests/conftest.py tests/test_fixture.py
git commit -m "test: 심의안 합성 워크북 픽스처"
```

---

### Task 2: 엑셀 읽기 — read_copies

T&D 시트에서 문안 목록을 뽑는다.

**Files:**
- Create: `shim/excel_io.py`
- Test: `tests/test_excel_io_read.py`

**Interfaces:**
- Consumes: `sample_workbook_bytes` 픽스처.
- Produces:
  - 상수 `SHEET_TND="검색광고 T&D"`, `SHEET_UPLOAD="업로드용"`, `HEADER_ROW=4`, `DATA_START=5`, `COL_NO=3`, `COL_COPY=4`, `COL_POS=6`, `COL_MAX=8`
  - `@dataclass Copy: no:int; text:str; position:str; max_len:int|None; row:int`
  - `class SheetNotFoundError(Exception)`
  - `read_copies(data: bytes) -> list[Copy]`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_excel_io_read.py
import pytest
from shim.excel_io import read_copies, SheetNotFoundError, Copy


def test_read_copies_extracts_rows(sample_workbook_bytes):
    copies = read_copies(sample_workbook_bytes)
    assert len(copies) == 3
    assert copies[0] == Copy(no=1, text="판매 수수료가 없어 저렴한 가나다이렉트",
                             position="설명문구", max_len=45, row=5)
    assert copies[1].max_len == 15
    assert copies[2].no == 3


def test_read_copies_missing_sheet_raises():
    import io, openpyxl
    wb = openpyxl.Workbook()
    buf = io.BytesIO(); wb.save(buf)
    with pytest.raises(SheetNotFoundError):
        read_copies(buf.getvalue())
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest tests/test_excel_io_read.py -v`
Expected: FAIL (`ModuleNotFoundError: shim.excel_io`)

- [ ] **Step 3: 최소 구현**

```python
# shim/excel_io.py
import io
from dataclasses import dataclass
import openpyxl

SHEET_TND = "검색광고 T&D"
SHEET_UPLOAD = "업로드용"
HEADER_ROW = 4
DATA_START = 5
COL_NO = 3
COL_COPY = 4
COL_POS = 6
COL_MAX = 8


class SheetNotFoundError(Exception):
    pass


@dataclass
class Copy:
    no: int
    text: str
    position: str
    max_len: int | None
    row: int


def read_copies(data: bytes) -> list[Copy]:
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=False)
    if SHEET_TND not in wb.sheetnames:
        raise SheetNotFoundError(f"시트 '{SHEET_TND}' 없음. 있는 시트: {wb.sheetnames}")
    ws = wb[SHEET_TND]
    copies: list[Copy] = []
    for r in range(DATA_START, ws.max_row + 1):
        no = ws.cell(r, COL_NO).value
        text = ws.cell(r, COL_COPY).value
        if no is None or text is None:
            continue
        mx = ws.cell(r, COL_MAX).value
        copies.append(Copy(
            no=int(no),
            text=str(text),
            position=str(ws.cell(r, COL_POS).value or ""),
            max_len=int(mx) if isinstance(mx, (int, float)) else None,
            row=r,
        ))
    return copies
```

- [ ] **Step 4: 실행해서 통과 확인**

Run: `python -m pytest tests/test_excel_io_read.py -v`
Expected: PASS (2개)

- [ ] **Step 5: 커밋**

```bash
git add shim/excel_io.py tests/test_excel_io_read.py
git commit -m "feat: read_copies로 T&D 문안 추출"
```

---

### Task 3: 엑셀 쓰기 — build_revised_workbook

수정 행의 D열과 업로드용 C열만 덮어쓴 새 워크북을 만든다.

**Files:**
- Modify: `shim/excel_io.py` (함수 추가)
- Test: `tests/test_excel_io_write.py`

**Interfaces:**
- Consumes: `read_copies`, `Copy`, 시트/열 상수.
- Produces: `build_revised_workbook(data: bytes, revisions: dict[int, str]) -> bytes`
  - `revisions`: `{NO: 수정문}`. 포함된 NO만 수정, 나머지 원본 유지.
  - T&D D열 값 교체(E 수식 유지). 업로드용 같은 NO 행의 C열 교체(D 수식 유지).
  - 업로드용 매핑: T&D 데이터 순서(index)로 1:1. `업로드용` 행 = index+1.

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_excel_io_write.py
import io
import openpyxl
from shim.excel_io import build_revised_workbook, read_copies


def _load(data, keep_formulas=True):
    return openpyxl.load_workbook(io.BytesIO(data), data_only=not keep_formulas)


def test_overwrites_only_targeted_copy(sample_workbook_bytes):
    out = build_revised_workbook(sample_workbook_bytes, {2: "AI맞춤보장보험"})
    wb = _load(out)
    t = wb["검색광고 T&D"]
    assert t["D5"].value == "판매 수수료가 없어 저렴한 가나다이렉트"  # 미수정 유지
    assert t["D6"].value == "AI맞춤보장보험"                              # 수정 반영


def test_e_column_formula_preserved(sample_workbook_bytes):
    out = build_revised_workbook(sample_workbook_bytes, {2: "AI맞춤보장보험"})
    t = _load(out)["검색광고 T&D"]
    assert t["E6"].value == "=LEN(D6)"  # 글자수 수식 그대로


def test_upload_sheet_c_synced_d_formula_kept(sample_workbook_bytes):
    out = build_revised_workbook(sample_workbook_bytes, {2: "AI맞춤보장보험"})
    u = _load(out)["업로드용"]
    assert u["C2"].value == "AI맞춤보장보험"   # NO 2 -> 업로드용 2행
    assert u["D2"].value == "=A2&B2&C2"        # 연결 수식 유지


def test_other_sheet_untouched(sample_workbook_bytes):
    out = build_revised_workbook(sample_workbook_bytes, {2: "AI맞춤보장보험"})
    d = _load(out)["드롭다운 수식"]
    assert d["B1"].value == "가나보험"
    assert d["C1"].value == "=B1"
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest tests/test_excel_io_write.py -v`
Expected: FAIL (`ImportError: cannot import name 'build_revised_workbook'`)

- [ ] **Step 3: 최소 구현 (excel_io.py 끝에 추가)**

```python
def build_revised_workbook(data: bytes, revisions: dict[int, str]) -> bytes:
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=False)
    ws = wb[SHEET_TND]

    order: list[int] = []  # T&D 데이터 순서대로의 NO 목록
    for r in range(DATA_START, ws.max_row + 1):
        no = ws.cell(r, COL_NO).value
        text = ws.cell(r, COL_COPY).value
        if no is None or text is None:
            continue
        no = int(no)
        order.append(no)
        if no in revisions:
            ws.cell(r, COL_COPY).value = revisions[no]

    if SHEET_UPLOAD in wb.sheetnames:
        us = wb[SHEET_UPLOAD]
        for idx, no in enumerate(order):
            if no in revisions:
                us.cell(idx + 1, 3).value = revisions[no]  # C열

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

- [ ] **Step 4: 실행해서 통과 확인**

Run: `python -m pytest tests/test_excel_io_write.py -v`
Expected: PASS (4개)

- [ ] **Step 5: 커밋**

```bash
git add shim/excel_io.py tests/test_excel_io_write.py
git commit -m "feat: build_revised_workbook로 D열·업로드용 C열 갱신"
```

---

### Task 4: 의견 참조 번호 추출 — referenced_numbers

의견에서 언급된 문안 번호를 뽑아 "매칭 실패" 탐지에 쓴다.

**Files:**
- Create: `shim/opinions.py`
- Test: `tests/test_opinions.py`

**Interfaces:**
- Produces: `referenced_numbers(text: str) -> set[int]` — `N번` 패턴의 N을 모두 반환.

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_opinions.py
from shim.opinions import referenced_numbers


def test_extracts_numbers_split_by_slash():
    text = "2번 문안: '원문' -> 수정 / 6번 문안: 'x' : 수정"
    assert referenced_numbers(text) == {2, 6}


def test_empty_text_returns_empty_set():
    assert referenced_numbers("") == set()
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest tests/test_opinions.py -v`
Expected: FAIL (`ModuleNotFoundError: shim.opinions`)

- [ ] **Step 3: 최소 구현**

```python
# shim/opinions.py
import re

_NUM = re.compile(r"(\d+)\s*번")


def referenced_numbers(text: str) -> set[int]:
    return {int(m) for m in _NUM.findall(text or "")}
```

- [ ] **Step 4: 실행해서 통과 확인**

Run: `python -m pytest tests/test_opinions.py -v`
Expected: PASS (2개)

- [ ] **Step 5: 커밋**

```bash
git add shim/opinions.py tests/test_opinions.py
git commit -m "feat: 의견에서 참조 번호 추출"
```

---

### Task 5: AI 수정 — 파싱 + 글자수 제한 강제

Claude 호출은 `call_fn` 주입으로 추상화. 제한 초과 시 축약 1회 재요청.

**Files:**
- Create: `shim/ai_revise.py`
- Test: `tests/test_ai_revise.py`

**Interfaces:**
- Consumes: `Copy` (from `shim.excel_io`).
- Produces:
  - `@dataclass Revision: no:int; revised:str; reason:str`
  - `build_prompt(copies: list[Copy], opinions: str) -> str`
  - `parse_revisions(raw: str) -> list[Revision]` — 모델이 낸 JSON 텍스트 파싱(코드펜스 허용).
  - `revise(copies, opinions, call_fn) -> list[Revision]` — `call_fn(prompt:str)->str`. 초과 항목만 1회 축약 재요청 후 병합. (초과 판정은 여기서 하되 자르지 않음.)

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_ai_revise.py
import json
from shim.excel_io import Copy
from shim.ai_revise import build_prompt, parse_revisions, revise, Revision

C = [
    Copy(no=1, text="원문1", position="설명문구", max_len=45, row=5),
    Copy(no=2, text="AI맞춤보장", position="추가제목", max_len=15, row=6),
]


def test_build_prompt_includes_max_len_and_opinions():
    p = build_prompt(C, "2번 문안: 수정")
    assert "15" in p and "2번" in p and "AI맞춤보장" in p


def test_parse_revisions_handles_code_fence():
    raw = "```json\n[{\"no\":2,\"revised\":\"AI맞춤보장보험\",\"reason\":\"명확화\"}]\n```"
    revs = parse_revisions(raw)
    assert revs == [Revision(no=2, revised="AI맞춤보장보험", reason="명확화")]


def test_revise_returns_only_opinioned_numbers():
    def call_fn(_prompt):
        return json.dumps([{"no": 2, "revised": "AI맞춤보장보험", "reason": "명확화"}])
    revs = revise(C, "2번 문안: 수정", call_fn)
    assert [r.no for r in revs] == [2]


def test_revise_retries_once_when_over_limit():
    calls = []
    def call_fn(prompt):
        calls.append(prompt)
        if len(calls) == 1:
            # 15자 초과 응답
            return json.dumps([{"no": 2, "revised": "열다섯자를훌쩍넘겨버리는긴문장입니다", "reason": "x"}])
        # 재요청 시 15자 이내
        return json.dumps([{"no": 2, "revised": "AI맞춤보장보험", "reason": "축약"}])
    revs = revise(C, "2번 문안: 수정", call_fn)
    assert len(calls) == 2                       # 축약 재요청 1회 발생
    assert revs[0].revised == "AI맞춤보장보험"
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest tests/test_ai_revise.py -v`
Expected: FAIL (`ModuleNotFoundError: shim.ai_revise`)

- [ ] **Step 3: 최소 구현**

```python
# shim/ai_revise.py
import json
import re
from dataclasses import dataclass
from shim.excel_io import Copy


@dataclass
class Revision:
    no: int
    revised: str
    reason: str


def build_prompt(copies: list[Copy], opinions: str) -> str:
    lines = []
    for c in copies:
        lim = c.max_len if c.max_len is not None else "제한없음"
        lines.append(f"- {c.no}번 [{c.position}] 최대 {lim}자 | 원문: {c.text}")
    catalog = "\n".join(lines)
    return f"""너는 광고 심의 문안 교정기다. 아래 문안 목록과 심의 의견을 보고,
의견이 언급한 번호의 문안만 수정하라.

절대 규칙:
- 각 문안의 '최대 N자'를 넘기지 마라 (공백 포함, 한 글자=1). 이건 하드 제약이다.
- 의견이 없는 번호는 결과에 포함하지 마라.
- 광고 심의 맥락과 원문 톤을 유지하라.

[문안 목록]
{catalog}

[심의 의견]
{opinions}

결과는 JSON 배열만 출력하라. 각 원소:
{{"no": 정수, "revised": "수정문", "reason": "수정 사유 한 줄"}}"""


def parse_revisions(raw: str) -> list[Revision]:
    text = raw.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    data = json.loads(text)
    return [Revision(no=int(d["no"]), revised=str(d["revised"]),
                     reason=str(d.get("reason", ""))) for d in data]


def _over_limit(revs, limits):
    return [r for r in revs if limits.get(r.no) is not None and len(r.revised) > limits[r.no]]


def revise(copies, opinions, call_fn):
    limits = {c.no: c.max_len for c in copies}
    revs = parse_revisions(call_fn(build_prompt(copies, opinions)))

    over = _over_limit(revs, limits)
    if over:
        subset = [c for c in copies if c.no in {r.no for r in over}]
        shorten = (build_prompt(subset, opinions)
                   + "\n\n앞선 수정문이 최대 글자수를 초과했다. 반드시 제한 이내로 더 줄여라.")
        retried = {r.no: r for r in parse_revisions(call_fn(shorten))}
        revs = [retried.get(r.no, r) for r in revs]
    return revs
```

- [ ] **Step 4: 실행해서 통과 확인**

Run: `python -m pytest tests/test_ai_revise.py -v`
Expected: PASS (4개)

- [ ] **Step 5: 전체 테스트 실행**

Run: `python -m pytest -v`
Expected: 전부 PASS

- [ ] **Step 6: 커밋**

```bash
git add shim/ai_revise.py tests/test_ai_revise.py
git commit -m "feat: AI 문안 수정 + 최대 글자수 축약 재요청"
```

---

### Task 6: Streamlit 앱 조립

로직을 UI로 묶고 anthropic으로 `call_fn`을 연결한다.

**Files:**
- Create: `shim_app.py`
- Modify: `requirements.txt` (anthropic 추가)
- Modify: `.gitignore` (`.streamlit/secrets.toml` 확인/추가)

**Interfaces:**
- Consumes: `read_copies`, `build_revised_workbook` (excel_io), `revise`, `Revision` (ai_revise), `referenced_numbers` (opinions).
- Produces: 실행 가능한 Streamlit 앱. AI `call_fn`은 `anthropic.Anthropic(...).messages.create(model="claude-opus-4-8", ...)` 응답 텍스트를 반환.

- [ ] **Step 1: requirements에 anthropic 추가**

`requirements.txt` 마지막 줄에 추가:

```
anthropic==0.69.0
```

- [ ] **Step 2: secrets.toml gitignore 확인**

`.gitignore` 에 아래 줄이 없으면 추가:

```
.streamlit/secrets.toml
```

- [ ] **Step 3: 앱 작성**

```python
# shim_app.py
import io
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
        return resp.content[0].text

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
    revised_nos = {r.no for r in revs}
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

    if st.button("엑셀 다운로드 생성"):
        revisions = {int(row["번호"]): row["수정문"] for _, row in edited.iterrows()}
        out = build_revised_workbook(raw, revisions)
        name = up.name.rsplit(".", 1)[0]
        today = dt.date.today().strftime("%Y%m%d")
        st.download_button("📥 다운로드", data=out,
                           file_name=f"{name}_심의반영_{today}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
```

- [ ] **Step 4: 임포트/구문 스모크 체크**

Run: `python -c "import ast; ast.parse(open('shim_app.py', encoding='utf-8').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 5: 앱 기동 확인 (수동)**

Run: `.venv/Scripts/streamlit run shim_app.py --server.port 8503` (또는 `streamlit run shim_app.py`)
Expected: 브라우저에서 비밀번호 화면 → 통과 후 업로드 UI 표시. (`.streamlit/secrets.toml`에 `APP_PASSWORD`, `ANTHROPIC_API_KEY` 설정 필요)

- [ ] **Step 6: 커밋**

```bash
git add shim_app.py requirements.txt .gitignore
git commit -m "feat: 심의 의견 반영 Streamlit 앱"
```

---

### Task 7: 실제 파일 종단 확인 + 문서

첨부된 실제 심의안으로 전체 흐름을 확인하고 CLAUDE.md에 앱을 등록한다. (실제 파일은 커밋하지 않는다.)

**Files:**
- Modify: `CLAUDE.md` (실행 명령 섹션에 shim_app 추가)

- [ ] **Step 1: 실제 파일로 읽기 검증 (수동 스크립트, 커밋 안 함)**

Run:
```bash
python -c "from shim.excel_io import read_copies; import pathlib; p=pathlib.Path(r'<로컬 심의안 파일 경로>.xlsx'); print(len(read_copies(p.read_bytes())), '건')"
```
Expected: `12 건`

- [ ] **Step 2: 실제 파일로 쓰기 검증 (수동)**

Run:
```bash
python -c "from shim.excel_io import read_copies, build_revised_workbook; import pathlib,io,openpyxl; p=pathlib.Path(r'<로컬 심의안 파일 경로>.xlsx'); raw=p.read_bytes(); out=build_revised_workbook(raw, {3:'테스트수정문안'}); wb=openpyxl.load_workbook(io.BytesIO(out)); print('T&D D7:', wb['검색광고 T&D']['D7'].value); print('업로드용 C3:', wb['업로드용']['C3'].value)"
```
Expected: `T&D D7: 테스트수정문안` / `업로드용 C3: 테스트수정문안`

- [ ] **Step 3: CLAUDE.md 명령어 섹션에 추가**

`## 명령어` 코드블록에 추가:

```bash
# 심의 의견 자동 반영 도구
.venv/Scripts/streamlit run shim_app.py --server.port 8503
```

- [ ] **Step 4: 커밋**

```bash
git add CLAUDE.md
git commit -m "docs: 심의 반영 도구 실행 명령 추가"
```

---

## Self-Review

- **Spec 커버리지:** 업로드/의견/AI수정/검수/다운로드(Task 6), 최대 글자수 강제(Task 5), 엑셀 재생성 규칙(Task 3), 의견 파싱·매칭실패(Task 4/6), 비밀번호·시크릿·비영속(Task 6), 엣지케이스 시트없음(Task 2/6), 테스트(Task 1~5). 모두 태스크 존재.
- **Placeholder:** 없음 — 모든 코드 단계에 실제 코드 포함.
- **타입 일관성:** `Copy`(excel_io) → `revise`/`build_prompt` 입력, `Revision`(ai_revise) 일관. `build_revised_workbook(bytes, dict[int,str])` 시그니처 Task 3 정의 = Task 6 호출 일치. `call_fn(str)->str` Task 5 정의 = Task 6 `_make_call_fn` 일치.
- **비고:** 실제 광고주 파일은 Task 7에서 로컬 검증만, 커밋 제외 (Global Constraints 준수).
