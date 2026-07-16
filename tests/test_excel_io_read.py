import pytest
from shim.excel_io import read_copies, SheetNotFoundError, Copy


def test_read_copies_extracts_rows(sample_workbook_bytes):
    copies = read_copies(sample_workbook_bytes)
    assert len(copies) == 3
    assert copies[0] == Copy(no=1, text="판매 수수료가 없어 저렴한 삼성화재 다이렉트",
                             position="설명문구", max_len=45, row=5)
    assert copies[1].max_len == 15
    assert copies[2].no == 3


def test_read_copies_missing_sheet_raises():
    import io, openpyxl
    wb = openpyxl.Workbook()
    buf = io.BytesIO(); wb.save(buf)
    with pytest.raises(SheetNotFoundError):
        read_copies(buf.getvalue())
