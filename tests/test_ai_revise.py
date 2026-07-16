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
