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
    if not isinstance(data, list):
        raise ValueError("AI 응답이 JSON 배열이 아닙니다")
    revs = []
    for d in data:
        no = d.get("no")
        revised = d.get("revised")
        if no is None or revised is None:
            continue
        revs.append(Revision(no=int(no), revised=str(revised),
                             reason=str(d.get("reason", ""))))
    return revs


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
