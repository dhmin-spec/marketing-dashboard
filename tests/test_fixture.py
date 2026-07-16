# tests/test_fixture.py
import io
import openpyxl
from tests.conftest import _build


def test_fixture_has_expected_structure():
    wb = openpyxl.load_workbook(io.BytesIO(_build()))
    assert wb.sheetnames == ["드롭다운 수식", "검색광고 T&D", "업로드용"]
    t = wb["검색광고 T&D"]
    assert t["C4"].value == "NO"
    assert t["D5"].value == "판매 수수료가 없어 저렴한 삼성화재 다이렉트"
    assert t["H6"].value == 15
