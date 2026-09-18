"""원래 확인 맵(`i64_ingame`·`i64_ops_ingame`·`i128_ingame`)의 `show()` 소스에서 **10진 출력 기대 글**을 뽑는다.

`res[N].fmt()` / `i64.fmt(res[N], signed=True)` 인자와, 서식 문자열 안 "(숫자 숫자 …)" 묶음을 순서대로 짝짓는다.
맵 쪽(`aa_values`)은 이 순서대로 값을 버퍼에 찍고, 판정 명세 생성기(`tools/make_ingame_specs.py`)는 같은 글을
`text` 항목의 `equals` 로 쓴다 — 두 쪽이 한 함수를 쓰므로 어긋나지 않는다(eudplib 없이 도는 순수 파이썬).
"""

import re

__all__ = ["fmt_expect", "expect_text", "expect_text_of"]

_ARG = re.compile(r"""res\[(\d+)\]\.fmt\((?P<kw1>[^)]*)\)|(?:i64|i128)\.fmt\(res\[(\d+)\](?P<kw2>[^)]*)\)""")
_NUMS = re.compile(r"\(([-\d]+(?: [-\d]+)*)\)")
_CALL = re.compile(r'printAll\("((?:[^"\\]|\\.)*)"([^;]*)\);', re.S)


def _calls(src):
    """`function show(...)` 안의 printAll 호출 → [(서식 문자열, 인자 글)]."""
    i = src.find("function show(")
    if i < 0:
        return []
    j = src.find("\nfunction ", i + 1)
    body = src[i:j if j > 0 else len(src)]
    return [(m.group(1), m.group(2)) for m in _CALL.finditer(body)]


def fmt_expect(src):
    """show() 소스 → [(res 번호, signed, 기대 글)]."""
    out = []
    for fmt, args in _calls(src):
        found = [(int(m.group(1) or m.group(3)), "signed=True" in (m.group("kw1") or m.group("kw2") or ""))
                 for m in _ARG.finditer(args)]
        if not found or len(found) != args.count(".fmt("):
            continue  # res[N].fmt 가 아닌 인자가 섞인 줄(원시 값·점검 수)은 건너뛴다
        toks = []
        for g in _NUMS.findall(fmt):
            toks.extend(g.split())
        if len(toks) != len(found):
            continue
        for (idx, signed), tok in zip(found, toks):
            out.append((idx, signed, tok))
    return out


def expect_text(src):
    """소스 글 → 기대 글 전체(공백으로 이음)."""
    return " ".join(tok for _i, _s, tok in fmt_expect(src))


def expect_text_of(path):
    """eps 파일 경로 → 기대 글 전체."""
    with open(path, encoding="utf-8") as f:
        return expect_text(f.read())
