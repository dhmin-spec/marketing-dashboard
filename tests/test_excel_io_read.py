import pytest
from shim.excel_io import read_copies, SheetNotFoundError, Copy, _resolve_int


def test_resolve_int_uses_cached_when_formula():
    assert _resolve_int("=C5+1", 2) == 2      # 수식이면 캐시값 사용


def test_resolve_int_plain_number():
    assert _resolve_int(3, None) == 3          # 일반 숫자는 그대로


def test_resolve_int_non_numeric_returns_none():
    assert _resolve_int("참고", None) is None   # 비숫자→None
    assert _resolve_int("=C5+1", None) is None  # 캐시 없으면 None


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


def test_read_copies_skips_non_numeric_no_row():
    import io, openpyxl
    from shim.excel_io import SHEET_TND, DATA_START, COL_NO, COL_COPY, COL_POS, COL_MAX

    wb = openpyxl.Workbook()
    wb.active.title = "드롭다운 수식"
    t = wb.create_sheet(SHEET_TND)
    t["B4"], t["C4"], t["D4"] = "보종", "NO", "문구 및 이미지"
    t["E4"], t["F4"], t["H4"] = "글자수", "광고위치", "비고"

    r = DATA_START
    t.cell(r, 2, "전 보종")
    t.cell(r, COL_NO, 1)
    t.cell(r, COL_COPY, "정상 문구")
    t.cell(r, COL_POS, "설명문구")
    t.cell(r, COL_MAX, 45)

    r2 = DATA_START + 1
    t.cell(r2, 2, "전 보종")
    t.cell(r2, COL_NO, "참고")
    t.cell(r2, COL_COPY, "비고 텍스트")
    t.cell(r2, COL_POS, "설명문구")
    t.cell(r2, COL_MAX, 45)

    buf = io.BytesIO()
    wb.save(buf)

    copies = read_copies(buf.getvalue())
    assert len(copies) == 1
    assert copies[0].no == 1
