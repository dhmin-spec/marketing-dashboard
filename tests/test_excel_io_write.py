import io
import openpyxl
from shim.excel_io import build_revised_workbook, read_copies


def _load(data, keep_formulas=True):
    return openpyxl.load_workbook(io.BytesIO(data), data_only=not keep_formulas)


def test_overwrites_only_targeted_copy(sample_workbook_bytes):
    out = build_revised_workbook(sample_workbook_bytes, {2: "AI맞춤보장보험"})
    wb = _load(out)
    t = wb["검색광고 T&D"]
    assert t["D5"].value == "판매 수수료가 없어 저렴한 삼성화재 다이렉트"  # 미수정 유지
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
    assert d["B1"].value == "삼성화재"
    assert d["C1"].value == "=B1"
