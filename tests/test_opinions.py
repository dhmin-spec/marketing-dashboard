from shim.opinions import referenced_numbers


def test_extracts_numbers_split_by_slash():
    text = "2번 문안: '원문' -> 수정 / 6번 문안: 'x' : 수정"
    assert referenced_numbers(text) == {2, 6}


def test_empty_text_returns_empty_set():
    assert referenced_numbers("") == set()
