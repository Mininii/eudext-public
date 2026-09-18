"""strdesign 시험 참조 (WP6a): 원본 Lua 정의를 lupa(Lua 5.4)로 돌리는 도구, 파이썬 참조 구현, S7 5절 기대값 156건.

- `LUA_FILES`: 원본 정의 파일 6개(S7 1절). `reference/` 스냅숏을 먼저 보고, 없으면 사용자 작업 폴더를 **읽기만** 한다.
- `extract(path)`: 파일에서 `StrD = {…}` 와 `function StrDesign…(Str) … end` 원문만 뽑는다(파일 전체는 TEP 전역에 기대므로
  실행하지 않는다 — S7 5절 방법과 같음).
- `LuaDefs(key)`: 뽑은 원문을 `lupa.lua54.LuaRuntime(encoding=None)`(바이트 문자열)에서 실행한 것. `call(func, value)` →
  결과 bytes, 원본이 오류를 내면 None. Lua 는 `eudext.tools.lua_consts.lua_c_locale()` 안에서 부른다(원본 TEP 의 "C" 로캘 —
  Windows 사용자 로캘에서 문자 분류가 달라지지 않게).
- `ref_bytes(style, func, value)`: S7 3절 규칙을 1절 바이트 표(16진)로 옮긴 파이썬 참조(eudext.strdesign 과 독립).
- `INPUTS`, `EXPECTED`: S7 5절 입력 12개 × 함수판 13개 = 156건. `EXPECTED` 는 2026-09-17 이 파일의 `LuaDefs` 로 뽑아
  고정한 값이다(Windows 쪽 `s7_lupa_out.json` 은 이 저장소에 없다). 시험이 원본 Lua 를 다시 돌려 고정값과 같은지도 본다.

    python eudext/tests/ref_strdesign.py          # 기대값 표를 다시 뽑아 출력 (EXPECTED 갱신용)
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # 저장소 최상위
REF = os.path.join(ROOT, "reference")
if ROOT not in sys.path:  # 단독 실행(`python eudext/tests/ref_strdesign.py`)에서도 eudext 를 불러오게
    sys.path.insert(0, ROOT)

# (키, 판, 함수 이름들, 경로 후보들) — S7 약어 표
LUA_FILES = (
    ("L322", "mcf", ("StrDesign", "StrDesignX"),
     (os.path.join(REF, "MapSource", "Library", "LibraryFor322.lua"),)),
    ("Tpl", "seed", ("StrDesign", "StrDesignX"),
     (os.path.join(REF, "MSF-Template", "func.lua"),)),
    ("Seed", "seed", ("StrDesign", "StrDesignX"),
     (os.path.join(REF, "theSeed", "Engine", "func.lua"), "/home/developer/theSeed/Engine/func.lua")),
    ("Stel", "seed", ("StrDesign", "StrDesignX"),
     (os.path.join(REF, "Stella_II", "Engine", "func.lua"), "/home/developer/Stella-II/Engine/func.lua")),
    ("ResV", "respect", ("StrDesign", "StrDesignX"),
     (os.path.join(REF, "MSF_Respect_V", "func.lua"), "/home/developer/MSF_Respect_V/func.lua")),
    ("Mem2", "memory", ("StrDesign", "StrDesignX", "StrDesignX2"),
     (os.path.join(REF, "MapSource", "MSF_Memory_2", "func.lua"), "/home/developer/MapSource/MSF_Memory_2/func.lua")),
)
FILE_STYLE = {k: s for k, s, _f, _p in LUA_FILES}

# 함수판 → design() 인자 (center, lead)
FUNC_ARGS = {
    "StrDesign": (False, True),
    "StrDesignX": (True, True),
    "StrDesignX2": (True, False),
}

# S7 1절 바이트 표 (16진) — (lead, pre, post)
STYLE_HEX = {
    "mcf": ("", "07 E3 80 8E 20", "20 07 E3 80 8F"),
    "seed": ("", "08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20", "20 1C E3 80 82 0F 2B 18 2E 08 CB 9A"),
    "respect": ("", "07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20", "20 1C E3 80 82 0F 2B 18 2E 07 CB 9A"),
    "memory": ("0D 0D", "07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20", "20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7"),
}
STYLE_BYTES = {k: tuple(bytes.fromhex(h) for h in v) for k, v in STYLE_HEX.items()}
# 늘어나는 길이 (StrDesign, StrDesignX, StrDesignX2). S7 1절 표는 memory 를 +32/+33 으로 적었지만 바이트 표·5.4 기대값으로
# 세면 +30/+31 이다(lead 2 + pre 14 + post 14). X2 +29 는 맞다.
GROWTH = {"mcf": (10, 11, None), "seed": (25, 26, None), "respect": (25, 26, None), "memory": (30, 31, 29)}

# S7 5절 입력 12개 (이름, 값)
INPUTS = (
    ("empty", ""),
    ("abc", "abc"),
    ("boss", "보스 등장"),
    ("colored", "\x04[\x1f보스\x04]"),
    ("center", "\x13가운데"),
    ("newline", "a\nb"),
    ("nul", "a\x00b"),
    ("int5", 5),
    ("float1.5", 1.5),
    ("float3.0", 3.0),
    ("nil", None),
    ("true", True),
)


def find_file(paths):
    for p in paths:
        if os.path.isfile(p):
            return p
    return None


_FUNC_RE = re.compile(rb"^function (StrDesign\w*)\(Str\)\r?\n.*?^end\b", re.M | re.S)
_STRD_RE = re.compile(rb"^StrD\s*=\s*\{.*?^\}", re.M | re.S)


def extract(path):
    """파일에서 StrD 표와 StrDesign 계열 함수 원문(bytes)을 뽑는다. 반환: (원문 bytes, 함수 이름 목록, StrD 유무)."""
    with open(path, "rb") as f:
        data = f.read()
    chunks = []
    names = []
    m = _STRD_RE.search(data)
    if m:
        chunks.append(m.group(0))
    for fm in _FUNC_RE.finditer(data):
        chunks.append(fm.group(0))
        names.append(fm.group(1).decode())
    return b"\n".join(chunks) + b"\n", names, m is not None


def lupa_available():
    try:
        import lupa.lua54  # noqa: F401
    except ImportError:
        return False
    return True


def lua_value(v):
    """파이썬 입력을 lupa 에 넘길 값으로 (str → UTF-8 bytes)."""
    if isinstance(v, str):
        return v.encode("utf-8")
    return v


class LuaDefs:
    """원본 파일 하나의 StrDesign 정의를 실행한 Lua 런타임."""

    def __init__(self, key):
        import lupa.lua54 as lua54

        from eudext.tools.lua_consts import lua_c_locale

        self._c_locale = lua_c_locale
        entry = next(e for e in LUA_FILES if e[0] == key)
        self.key, self.style, self.funcs, cands = entry
        self.path = find_file(cands)
        if self.path is None:
            raise FileNotFoundError("원본 Lua 파일이 없습니다: %s" % (cands,))
        self.source, self.found, self.has_strd = extract(self.path)
        self.rt = lua54.LuaRuntime(encoding=None, unpack_returned_tuples=True)
        with lua_c_locale():
            self.rt.execute(self.source)
        g = self.rt.globals()
        self._fn = {name: g[name.encode()] for name in self.found}
        self._cat = self.rt.eval(b'function(x) return "" .. x end')
        self._pcall = self.rt.eval(b"function(f, x) local ok, r = pcall(f, x); if ok then return r end return nil end")

    def call(self, func, value):
        """원본 함수 결과(bytes). 원본이 오류를 내면 None."""
        with self._c_locale():
            r = self._pcall(self._fn[func], lua_value(value))
        return r

    def strd(self):
        """StrD 표 (pre, post) bytes, 없으면 None."""
        t = self.rt.globals()[b"StrD"]
        if t is None:
            return None
        return (t[1], t[2])

    def tostring(self, x):
        """Lua `"" .. x` (숫자 → 문자열) 결과 bytes."""
        with self._c_locale():
            return self._cat(x)


def lua_tostring_ref(x):
    """파이썬 참조: Lua 5.4 tostringbuff (정수 %d, 실수 %.14g + 정수 모양이면 .0)."""
    if isinstance(x, int):
        return str(x)
    s = "%.14g" % x
    if s.lstrip("-").isdigit():
        s += ".0"
    return s


def ref_bytes(style, func, value):
    """S7 3절 규칙의 파이썬 참조(바이트). 원본이 오류를 내는 값(None·bool)은 None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        body = lua_tostring_ref(value).encode()
    elif isinstance(value, str):
        body = value.encode("utf-8")
    else:
        body = bytes(value)
    lead, pre, post = STYLE_BYTES[style]
    center, use_lead = FUNC_ARGS[func]
    return (lead if use_lead else b"") + (b"\x13" if center else b"") + pre + body + post


def generate():
    """원본 Lua 를 돌려 {(키, 함수): (결과 16진 또는 None, … 12개)} 를 만든다."""
    out = {}
    for key, _style, funcs, _p in LUA_FILES:
        d = LuaDefs(key)
        for func in funcs:
            row = []
            for _name, v in INPUTS:
                r = d.call(func, v)
                row.append(None if r is None else r.hex(" ").upper())
            out[(key, func)] = tuple(row)
    return out


# 2026-09-17 generate() 결과 (13 함수판 × 12 입력 = 156건, None = 원본 오류)
EXPECTED = {
    ('L322', 'StrDesign'): (
        '07 E3 80 8E 20 20 07 E3 80 8F',  # empty
        '07 E3 80 8E 20 61 62 63 20 07 E3 80 8F',  # abc
        '07 E3 80 8E 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 07 E3 80 8F',  # boss
        '07 E3 80 8E 20 04 5B 1F EB B3 B4 EC 8A A4 04 5D 20 07 E3 80 8F',  # colored
        '07 E3 80 8E 20 13 EA B0 80 EC 9A B4 EB 8D B0 20 07 E3 80 8F',  # center
        '07 E3 80 8E 20 61 0A 62 20 07 E3 80 8F',  # newline
        '07 E3 80 8E 20 61 00 62 20 07 E3 80 8F',  # nul
        '07 E3 80 8E 20 35 20 07 E3 80 8F',  # int5
        '07 E3 80 8E 20 31 2E 35 20 07 E3 80 8F',  # float1.5
        '07 E3 80 8E 20 33 2E 30 20 07 E3 80 8F',  # float3.0
        None,  # nil
        None,  # true
    ),
    ('L322', 'StrDesignX'): (
        '13 07 E3 80 8E 20 20 07 E3 80 8F',  # empty
        '13 07 E3 80 8E 20 61 62 63 20 07 E3 80 8F',  # abc
        '13 07 E3 80 8E 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 07 E3 80 8F',  # boss
        '13 07 E3 80 8E 20 04 5B 1F EB B3 B4 EC 8A A4 04 5D 20 07 E3 80 8F',  # colored
        '13 07 E3 80 8E 20 13 EA B0 80 EC 9A B4 EB 8D B0 20 07 E3 80 8F',  # center
        '13 07 E3 80 8E 20 61 0A 62 20 07 E3 80 8F',  # newline
        '13 07 E3 80 8E 20 61 00 62 20 07 E3 80 8F',  # nul
        '13 07 E3 80 8E 20 35 20 07 E3 80 8F',  # int5
        '13 07 E3 80 8E 20 31 2E 35 20 07 E3 80 8F',  # float1.5
        '13 07 E3 80 8E 20 33 2E 30 20 07 E3 80 8F',  # float3.0
        None,  # nil
        None,  # true
    ),
    ('Tpl', 'StrDesign'): (
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # empty
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 62 63 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # abc
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # boss
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 04 5B 1F EB B3 B4 EC 8A A4 04 5D 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # colored
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 13 EA B0 80 EC 9A B4 EB 8D B0 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # center
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 0A 62 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # newline
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 00 62 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # nul
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 35 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # int5
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 31 2E 35 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # float1.5
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 33 2E 30 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # float3.0
        None,  # nil
        None,  # true
    ),
    ('Tpl', 'StrDesignX'): (
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # empty
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 62 63 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # abc
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # boss
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 04 5B 1F EB B3 B4 EC 8A A4 04 5D 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # colored
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 13 EA B0 80 EC 9A B4 EB 8D B0 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # center
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 0A 62 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # newline
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 00 62 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # nul
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 35 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # int5
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 31 2E 35 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # float1.5
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 33 2E 30 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # float3.0
        None,  # nil
        None,  # true
    ),
    ('Seed', 'StrDesign'): (
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # empty
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 62 63 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # abc
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # boss
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 04 5B 1F EB B3 B4 EC 8A A4 04 5D 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # colored
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 13 EA B0 80 EC 9A B4 EB 8D B0 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # center
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 0A 62 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # newline
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 00 62 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # nul
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 35 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # int5
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 31 2E 35 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # float1.5
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 33 2E 30 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # float3.0
        None,  # nil
        None,  # true
    ),
    ('Seed', 'StrDesignX'): (
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # empty
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 62 63 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # abc
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # boss
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 04 5B 1F EB B3 B4 EC 8A A4 04 5D 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # colored
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 13 EA B0 80 EC 9A B4 EB 8D B0 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # center
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 0A 62 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # newline
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 00 62 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # nul
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 35 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # int5
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 31 2E 35 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # float1.5
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 33 2E 30 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # float3.0
        None,  # nil
        None,  # true
    ),
    ('Stel', 'StrDesign'): (
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # empty
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 62 63 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # abc
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # boss
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 04 5B 1F EB B3 B4 EC 8A A4 04 5D 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # colored
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 13 EA B0 80 EC 9A B4 EB 8D B0 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # center
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 0A 62 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # newline
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 00 62 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # nul
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 35 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # int5
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 31 2E 35 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # float1.5
        '08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 33 2E 30 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # float3.0
        None,  # nil
        None,  # true
    ),
    ('Stel', 'StrDesignX'): (
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # empty
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 62 63 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # abc
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # boss
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 04 5B 1F EB B3 B4 EC 8A A4 04 5D 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # colored
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 13 EA B0 80 EC 9A B4 EB 8D B0 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # center
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 0A 62 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # newline
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 00 62 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # nul
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 35 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # int5
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 31 2E 35 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # float1.5
        '13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 33 2E 30 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A',  # float3.0
        None,  # nil
        None,  # true
    ),
    ('ResV', 'StrDesign'): (
        '07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # empty
        '07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 62 63 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # abc
        '07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # boss
        '07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 04 5B 1F EB B3 B4 EC 8A A4 04 5D 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # colored
        '07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 13 EA B0 80 EC 9A B4 EB 8D B0 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # center
        '07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 0A 62 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # newline
        '07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 00 62 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # nul
        '07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 35 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # int5
        '07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 31 2E 35 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # float1.5
        '07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 33 2E 30 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # float3.0
        None,  # nil
        None,  # true
    ),
    ('ResV', 'StrDesignX'): (
        '13 07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # empty
        '13 07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 62 63 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # abc
        '13 07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # boss
        '13 07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 04 5B 1F EB B3 B4 EC 8A A4 04 5D 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # colored
        '13 07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 13 EA B0 80 EC 9A B4 EB 8D B0 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # center
        '13 07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 0A 62 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # newline
        '13 07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 00 62 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # nul
        '13 07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 35 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # int5
        '13 07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 31 2E 35 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # float1.5
        '13 07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 33 2E 30 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A',  # float3.0
        None,  # nil
        None,  # true
    ),
    ('Mem2', 'StrDesign'): (
        '0D 0D 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # empty
        '0D 0D 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 61 62 63 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # abc
        '0D 0D 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # boss
        '0D 0D 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 04 5B 1F EB B3 B4 EC 8A A4 04 5D 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # colored
        '0D 0D 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 13 EA B0 80 EC 9A B4 EB 8D B0 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # center
        '0D 0D 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 61 0A 62 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # newline
        '0D 0D 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 61 00 62 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # nul
        '0D 0D 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 35 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # int5
        '0D 0D 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 31 2E 35 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # float1.5
        '0D 0D 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 33 2E 30 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # float3.0
        None,  # nil
        None,  # true
    ),
    ('Mem2', 'StrDesignX'): (
        '0D 0D 13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # empty
        '0D 0D 13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 61 62 63 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # abc
        '0D 0D 13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # boss
        '0D 0D 13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 04 5B 1F EB B3 B4 EC 8A A4 04 5D 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # colored
        '0D 0D 13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 13 EA B0 80 EC 9A B4 EB 8D B0 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # center
        '0D 0D 13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 61 0A 62 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # newline
        '0D 0D 13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 61 00 62 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # nul
        '0D 0D 13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 35 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # int5
        '0D 0D 13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 31 2E 35 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # float1.5
        '0D 0D 13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 33 2E 30 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # float3.0
        None,  # nil
        None,  # true
    ),
    ('Mem2', 'StrDesignX2'): (
        '13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # empty
        '13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 61 62 63 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # abc
        '13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # boss
        '13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 04 5B 1F EB B3 B4 EC 8A A4 04 5D 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # colored
        '13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 13 EA B0 80 EC 9A B4 EB 8D B0 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # center
        '13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 61 0A 62 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # newline
        '13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 61 00 62 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # nul
        '13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 35 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # int5
        '13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 31 2E 35 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # float1.5
        '13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 33 2E 30 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7',  # float3.0
        None,  # nil
        None,  # true
    ),
}


if __name__ == "__main__":
    import pprint

    pprint.pprint(generate(), width=200)
