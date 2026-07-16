import re

_NUM = re.compile(r"(\d+)\s*번")


def referenced_numbers(text: str) -> set[int]:
    return {int(m) for m in _NUM.findall(text or "")}
