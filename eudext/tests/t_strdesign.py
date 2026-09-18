"""eudext.strdesign 시험 (WP6a, DESIGN 4.7, 정본 명세 docs/spec/S7_strdesign.md).

python tests/t_strdesign.py

- S7 5절 기대값 156건(`ref_strdesign.EXPECTED` — 6개 파일 × 13 함수판 × 12 입력): `design`/`design_x`/별칭의 UTF-8 바이트,
  숫자는 `lua_tostring` 을 거친 값과 별칭, 원본 오류(nil·true)는 `EudextError`. 고정 기대값이 원본 Lua 재실행 결과·
  S7 문서 표(5.1~5.4)·1절 바이트 표·늘어나는 길이와 같은지.
- lupa 차등: 원본 Lua 정의(맵 판 4종 + Library 판, 파일 6개)를 lupa(Lua 5.4)로 돌려 무작위 입력 1,000개(str·bytes·숫자)
  × 함수판 13개를 비교. `lua_tostring` 은 무작위 숫자 3,000개를 Lua `"" .. x` 와 비교. `StrD` 표 = `parts()`.
- API: set_style/get_style(판 없음 오류, 판 바꿈 경고), Style(불변·같음·해시), wrap, right, 입력 검사, `\\x00` 경고,
  f_ 별칭, 트리거 0개.
- 에뮬레이터: DisplayText 로 맵 문자열 표에 들어간 바이트가 원본 Lua 결과와 같은지(고정 156건 중 문자열 결과 + 무작위 200개).
- epScript: 예제(examples/strdesign_example.eps)·인게임 확인 맵(examples/strdesign_ingame.eps)의 번역, 에뮬레이터에서 찍힌
  문자열 = 원본 Lua 결과, euddraft 빌드.
- COST_CASES (tools/cost.py) — 트리거 0 확인.
"""

import sys

sys.dont_write_bytecode = True
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import inspect  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402
import struct  # noqa: E402
import warnings  # noqa: E402

import ref_strdesign as R  # noqa: E402
from eudplib import (  # noqa: E402
    CompressPayload,
    DisplayText,
    DoActions,
    EPWarning,
    EUDVariable,
    GetTriggerCounter,
    LoadMap,
)

from eudext import _compat  # noqa: E402
from eudext import strdesign as sd  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing import emu, scmodel  # noqa: E402
from eudext.testing.harness import BASE_MAP, Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

EX = os.path.join(_common.PKG, "examples")
LUPA = R.lupa_available()
N_RANDOM = 1000
N_TOSTRING = 3000
DOC_KEYS = ("인자:", "반환:", "비용:", "CP:", "로컬:", "epScript:", "출처:")
ALIASES = {"StrDesign": sd.StrDesign, "StrDesignX": sd.StrDesignX, "StrDesignX2": sd.StrDesignX2}


def quiet(fn, *args, **kw):
    """`\\x00` 경고를 숨기고 부른다."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EPWarning)
        return fn(*args, **kw)


def as_bytes(s):
    return s if isinstance(s, bytes) else s.encode("utf-8")


def hexs(b):
    return None if b is None else b.hex(" ").upper()


def call_design(style, func, value, **extra):
    center, lead = R.FUNC_ARGS[func]
    return quiet(sd.design, value, style=style, center=center, lead=lead, **extra)


def raises(fn, *args, **kw):
    try:
        quiet(fn, *args, **kw)
    except EudextError:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


# =============================================================================================
# S7 문서 표 (5.1~5.4 에 적힌 행 그대로) — 고정 기대값과 대조
# =============================================================================================

MCF = ("L322",)
SEED = ("Tpl", "Seed", "Stel")
RESV = ("ResV",)
MEM2 = ("Mem2",)
ERR = None

DOC_ROWS = [
    (MCF, "StrDesign", "empty", "07 E3 80 8E 20 20 07 E3 80 8F"),
    (MCF, "StrDesign", "abc", "07 E3 80 8E 20 61 62 63 20 07 E3 80 8F"),
    (MCF, "StrDesign", "boss", "07 E3 80 8E 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 07 E3 80 8F"),
    (MCF, "StrDesign", "colored", "07 E3 80 8E 20 04 5B 1F EB B3 B4 EC 8A A4 04 5D 20 07 E3 80 8F"),
    (MCF, "StrDesign", "nul", "07 E3 80 8E 20 61 00 62 20 07 E3 80 8F"),
    (MCF, "StrDesign", "int5", "07 E3 80 8E 20 35 20 07 E3 80 8F"),
    (MCF, "StrDesign", "float3.0", "07 E3 80 8E 20 33 2E 30 20 07 E3 80 8F"),
    (MCF, "StrDesign", "nil", ERR),
    (MCF, "StrDesign", "true", ERR),
    (MCF, "StrDesignX", "empty", "13 07 E3 80 8E 20 20 07 E3 80 8F"),
    (MCF, "StrDesignX", "center", "13 07 E3 80 8E 20 13 EA B0 80 EC 9A B4 EB 8D B0 20 07 E3 80 8F"),
    (MCF, "StrDesignX", "float1.5", "13 07 E3 80 8E 20 31 2E 35 20 07 E3 80 8F"),
    (SEED, "StrDesign", "empty", "08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A"),
    (SEED, "StrDesign", "abc", "08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 62 63 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A"),
    (SEED, "StrDesign", "newline", "08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 0A 62 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A"),
    (SEED, "StrDesign", "int5", "08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 35 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A"),
    (SEED, "StrDesignX", "boss", "13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 "
                                 "1C E3 80 82 0F 2B 18 2E 08 CB 9A"),
    (SEED, "StrDesignX", "float3.0", "13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 33 2E 30 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A"),
    (RESV, "StrDesign", "abc", "07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 62 63 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A"),
    (RESV, "StrDesignX", "empty", "13 07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A"),
    (MEM2, "StrDesign", "empty", "0D 0D 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7"),
    (MEM2, "StrDesign", "abc", "0D 0D 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 61 62 63 20 07 E3 80 91 08 C2 B7 11 C2 B7 "
                               "07 C2 B7"),
    (MEM2, "StrDesignX", "abc", "0D 0D 13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 61 62 63 20 07 E3 80 91 08 C2 B7 11 C2 B7 "
                                "07 C2 B7"),
    (MEM2, "StrDesignX2", "abc", "13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 61 62 63 20 07 E3 80 91 08 C2 B7 11 C2 B7 "
                                 "07 C2 B7"),
    (MEM2, "StrDesignX2", "float1.5", "13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 31 2E 35 20 07 E3 80 91 08 C2 B7 11 C2 "
                                      "B7 07 C2 B7"),
]
# S7 5.2·5.3 의 StrD 행
DOC_STRD = {
    "seed": ("08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20", "20 1C E3 80 82 0F 2B 18 2E 08 CB 9A"),
    "respect": ("07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20", "20 1C E3 80 82 0F 2B 18 2E 07 CB 9A"),
}


# =============================================================================================
# 1. S7 5절 기대값 156건
# =============================================================================================

def expected_156(ck):
    names = [n for n, _v in R.INPUTS]
    ck.eq("기대값 표 크기", (len(R.EXPECTED), sum(len(v) for v in R.EXPECTED.values())), (13, 156))
    n = 0
    for (key, func), row in R.EXPECTED.items():
        style = R.FILE_STYLE[key]
        for (name, value), want in zip(R.INPUTS, row):
            n += 1
            label = "S7-156 %s.%s(%s)" % (key, func, name)
            problems = []
            if want is None:
                if value is not None and not isinstance(value, bool):
                    problems.append("원본 오류인데 입력이 문자열·숫자")
                if not raises(call_design, style, func, value):
                    problems.append("design 이 오류를 내지 않음")
                if not raises(ALIASES[func], value, style=style):
                    problems.append("별칭이 오류를 내지 않음")
            else:
                want_b = bytes.fromhex(want)
                if isinstance(value, str):
                    got = call_design(style, func, value)
                    if not isinstance(got, str) or as_bytes(got) != want_b:
                        problems.append("design %r" % hexs(as_bytes(got)))
                    got_b = call_design(style, func, value.encode("utf-8"))
                    if got_b != want_b:
                        problems.append("design(bytes) %r" % hexs(got_b))
                    if func == "StrDesignX" and as_bytes(quiet(sd.design_x, value, style=style)) != want_b:
                        problems.append("design_x")
                    if func == "StrDesignX2" and as_bytes(quiet(sd.design_x, value, style=style, lead=False)) != want_b:
                        problems.append("design_x(lead=False)")
                else:
                    if not raises(call_design, style, func, value):
                        problems.append("숫자를 design 이 받음")
                    got = call_design(style, func, sd.lua_tostring(value))
                    if as_bytes(got) != want_b:
                        problems.append("design(lua_tostring) %r" % hexs(as_bytes(got)))
                if as_bytes(quiet(ALIASES[func], value, style=style)) != want_b:
                    problems.append("별칭 %s" % func)
                # set_style 로 정한 판 + style 생략
                sd.set_style(style)
                alias_default = as_bytes(quiet(ALIASES[func], value))
                sd.set_style(None)
                if alias_default != want_b:
                    problems.append("set_style 뒤 별칭")
                # Style 객체·Style.design
                center, lead = R.FUNC_ARGS[func]
                txt = value if isinstance(value, str) else sd.lua_tostring(value)
                if as_bytes(quiet(sd.STYLES[style].design, txt, center=center, lead=lead)) != want_b:
                    problems.append("Style.design")
            ck.true(label, not problems, "; ".join(problems))
    ck.eq("156건 모두 봄", n, 156)
    ck.eq("입력 이름", names, ["empty", "abc", "boss", "colored", "center", "newline", "nul", "int5", "float1.5",
                              "float3.0", "nil", "true"])


def doc_rows(ck):
    names = [n for n, _v in R.INPUTS]
    for keys, func, name, want in DOC_ROWS:
        for key in keys:
            got = R.EXPECTED[(key, func)][names.index(name)]
            ck.eq("S7 문서 표 %s.%s(%s)" % (key, func, name), got, want)
    # seed 세 파일은 출력이 같다 (S7 5.2)
    for func in ("StrDesign", "StrDesignX"):
        ck.true("seed 세 파일 같음 " + func, R.EXPECTED[("Tpl", func)] == R.EXPECTED[("Seed", func)] == R.EXPECTED[("Stel", func)])
    for style, (pre, post) in DOC_STRD.items():
        ck.eq("S7 문서 StrD %s" % style, tuple(hexs(as_bytes(x)) for x in sd.parts(style)), (pre, post))
    # 1절 바이트 표 = STYLES
    for style, (lead, pre, post) in R.STYLE_BYTES.items():
        st = sd.STYLES[style]
        ck.eq("1절 바이트 %s" % style, (as_bytes(st.lead), as_bytes(st.pre), as_bytes(st.post)), (lead, pre, post))
        g = R.GROWTH[style]
        ck.eq("늘어나는 길이 %s" % style, len(as_bytes(sd.design("", style=style))), g[0])
        ck.eq("늘어나는 길이 X %s" % style, len(as_bytes(sd.design_x("", style=style))), g[1])
        if g[2] is not None:
            ck.eq("늘어나는 길이 X2 %s" % style, len(as_bytes(sd.design_x("", style=style, lead=False))), g[2])
    ck.eq("판 이름", sorted(sd.STYLES), ["mcf", "memory", "respect", "seed"])
    # 파이썬 참조(ref_bytes) = 고정 기대값
    bad = 0
    for (key, func), row in R.EXPECTED.items():
        for (_n, v), want in zip(R.INPUTS, row):
            if hexs(R.ref_bytes(R.FILE_STYLE[key], func, v)) != want:
                bad += 1
    ck.eq("파이썬 참조 = 기대값 (156)", bad, 0)


# =============================================================================================
# 2. lupa 차등 (원본 Lua 실행)
# =============================================================================================

PIECES = [
    "a", "Z", "0", "9", " ", "  ", "abc", "보스", "등장", "가", "힣", "ｐｔｓ", "Ｇａｓ", "＋", "『", "』", "。", "˙", "˚", "·",
    "【", "】", "名取さな", "😀", "\u200b", "\n", "\r", "\r\r", "\r\r!H", "\t", "\x00", "!H", "%", "%s", "%d", "..", "\\", '"',
    "'", "[[", "]]", "--", "\x7f", "\u00e9", "\uffff",
] + [chr(i) for i in range(1, 32)]


def rand_text(rng):
    return "".join(rng.choice(PIECES) for _ in range(rng.randrange(0, 13)))


def rand_float(rng):
    k = rng.randrange(10)
    if k == 0:
        return rng.randrange(-10 ** 7, 10 ** 7) / 1000
    if k == 1:
        return float(rng.randrange(-(1 << 60), 1 << 60)) * rng.choice((1, 10, 1000, 1e-3))
    if k == 2:
        return rng.choice((0.0, -0.0, 0.5, -0.5, 1e14, 1e15, 1e16, 1e17, 99999999999999.0, 999999999999999.0,
                           123456789012345.0, 2.0 ** 53, 2.0 ** 63, -2.0 ** 63, 1e-5, 1e-4, 5e-324, 1.7976931348623157e308,
                           0.1, 0.2, 0.3, 1 / 3, 2 / 3, 100000 / 1000, 12500 / 1000))
    if k == 3:
        return float(10 ** rng.randrange(0, 20)) * rng.choice((1, -1))
    if k == 4:
        while True:
            x = struct.unpack("<d", rng.getrandbits(64).to_bytes(8, "little"))[0]
            if math.isfinite(x):
                return x
    if k == 5:
        return rng.uniform(-1e6, 1e6)
    if k == 6:
        return rng.randrange(0, 1 << 20) / (1 << rng.randrange(0, 20))
    if k == 7:
        return rng.random() * 10 ** rng.randrange(-8, 18)
    if k == 8:
        return float(rng.randrange(10 ** 13, 10 ** 17))
    return rng.randrange(-1000, 1000) + rng.choice((0.0, 0.25, 0.5, 0.1))


def rand_int(rng):
    k = rng.randrange(4)
    if k == 0:
        return rng.choice((0, 1, -1, 5, 10 ** 15, 10 ** 16, 2 ** 31, 2 ** 32, 2 ** 53, 2 ** 63 - 1, -(2 ** 63)))
    if k == 1:
        return rng.randrange(-(1 << 63), 1 << 63)
    if k == 2:
        return rng.randrange(-100000, 100000)
    return rng.randrange(0, 1 << rng.randrange(1, 63))


def rand_input(rng):
    r = rng.random()
    if r < 0.70:
        return rand_text(rng)
    if r < 0.85:
        return bytes(rng.getrandbits(8) for _ in range(rng.randrange(0, 30)))
    if r < 0.93:
        return rand_float(rng)
    return rand_int(rng)


def lupa_diff(ck):
    if not LUPA:
        ck.true("lupa 있음 (개발 venv 에 lupa 2.8 이 있어야 한다)", False)
        return None
    defs = {key: R.LuaDefs(key) for key, *_r in R.LUA_FILES}
    # 원본 파일에서 뽑은 함수·StrD
    for key, style, funcs, _p in R.LUA_FILES:
        d = defs[key]
        ck.eq("원본 함수 목록 %s" % key, tuple(d.found), funcs)
        strd = d.strd()
        if style in ("seed", "respect"):
            ck.eq("StrD = parts() %s" % key, strd, tuple(as_bytes(x) for x in sd.parts(style)))
        else:
            ck.eq("StrD 없음 %s" % key, strd, None)
        # StrD[1]/[2] 가 함수의 pre/post 와 같다 (S7 3-5)
        if strd is not None:
            ck.eq("StrD 로 만든 X = StrDesignX %s" % key, b"\x13" + strd[0] + b"X" + strd[1], d.call("StrDesignX", "X"))
    # 고정 기대값 = 원본 Lua 재실행
    ck.true("고정 기대값 = 원본 Lua 재실행 (156)", R.generate() == R.EXPECTED)

    rng = random.Random(0x57D)
    total = 0
    for i in range(N_RANDOM):
        value = rand_input(rng)
        problems = []
        for key, style, funcs, _p in R.LUA_FILES:
            for func in funcs:
                total += 1
                want = defs[key].call(func, value)
                where = "%s.%s" % (key, func)
                if want is None:
                    problems.append("%s 원본 오류" % where)
                if hexs(want) != hexs(R.ref_bytes(style, func, value)):
                    problems.append("%s 파이썬 참조 %r" % (where, hexs(R.ref_bytes(style, func, value))))
                if isinstance(value, (str, bytes)):
                    got = as_bytes(call_design(style, func, value))
                else:
                    if not raises(call_design, style, func, value):
                        problems.append("%s 숫자를 design 이 받음" % where)
                    got = as_bytes(call_design(style, func, sd.lua_tostring(value)))
                if got != want:
                    problems.append("%s design %r (원본 %r)" % (where, hexs(got), hexs(want)))
                alias = as_bytes(quiet(ALIASES[func], value, style=style))
                if alias != want:
                    problems.append("%s 별칭 %r (원본 %r)" % (where, hexs(alias), hexs(want)))
        ck.true("lupa 차등 #%d %r (함수판 13)" % (i, value), not problems, "; ".join(problems[:3]))
    ck.eq("lupa 차등 비교 수 (무작위 %d × 함수판 13)" % N_RANDOM, total, N_RANDOM * 13)

    # lua_tostring: Lua `"" .. x`
    lua = defs["L322"]
    rng = random.Random(0x2B)
    bad = 0
    for i in range(N_TOSTRING):
        x = rand_float(rng) if i % 3 else rand_int(rng)
        want = lua.tostring(x)
        got = sd.lua_tostring(x)
        ref = R.lua_tostring_ref(x)
        if not isinstance(got, str) or got.encode() != want or ref.encode() != want:
            bad += 1
            if bad <= 10:
                print("  [실패] lua_tostring(%r) = %r, 참조 %r, Lua %r" % (x, got, ref, want))
    ck.eq("lua_tostring 무작위 %d개 틀린 수" % N_TOSTRING, bad, 0)
    # S7 6절 설명과 다른 곳 (Lua 가 정답)
    for x, s in ((1e15, "1e+15"), (123456789012345.0, "1.2345678901234e+14"), (-0.0, "-0.0"), (100000 / 1000, "100.0"),
                 (1 / 3, "0.33333333333333"), (2.0 ** 53, "9.007199254741e+15"), (99999999999999.0, "99999999999999.0"),
                 (12.5, "12.5"), (5, "5"), (-(2 ** 63), "-9223372036854775808")):
        ck.eq("lua_tostring(%r)" % x, sd.lua_tostring(x), s)
        ck.eq("Lua tostring(%r)" % x, lua.tostring(x), s.encode())
    return defs


# =============================================================================================
# 3. API
# =============================================================================================

def api_checks(ck):
    sd.set_style(None)
    ck.eq("판 없음", sd.get_style(), None)
    ck.true("판 없이 design 은 오류", raises(sd.design, "x"))
    ck.true("판 없이 design_x 는 오류", raises(sd.design_x, "x"))
    ck.true("판 없이 parts 는 오류", raises(sd.parts))
    ck.true("판 없이 wrap 은 오류", raises(sd.wrap, "x"))
    ck.true("판 없이 StrDesign 은 오류", raises(sd.StrDesign, "x"))
    try:
        sd.design("x")
    except EudextError as e:
        ck.true("판 없음 안내문", "set_style" in str(e), str(e))
    ck.true("모르는 판", raises(sd.set_style, "dps"))
    ck.true("판 형식 오류", raises(sd.design, "x", style=3))
    st = sd.set_style("respect")
    ck.true("set_style 반환", st is sd.STYLES["respect"])
    ck.true("get_style", sd.get_style() is st)
    ck.eq("style 인자가 이긴다", sd.design("x", style="mcf"), "\x07『 x \x07』")
    # 판 바꿈 경고: 판을 지정하지 않은 호출이 나온 뒤에만
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        sd.set_style("seed")  # 아직 판 없는 호출이 없다 → 경고 없음
        ck.eq("판 바꿈 경고 없음 (암묵 호출 전)", [x for x in w if issubclass(x.category, EPWarning)], [])
        sd.design("y")
        sd.set_style("seed")  # 같은 판 → 경고 없음
        ck.eq("같은 판 다시 → 경고 없음", [x for x in w if issubclass(x.category, EPWarning)], [])
        sd.set_style("memory")
        got = [str(x.message) for x in w if issubclass(x.category, EPWarning)]
        ck.true("판 바꿈 경고", len(got) == 1 and "옛 판" in got[0], repr(got))
    sd.set_style(None)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        sd.set_style("mcf")
        sd.set_style("seed")
        ck.eq("None 뒤에는 경고 기록이 지워짐", [x for x in w if issubclass(x.category, EPWarning)], [])
        # \x00 경고
        sd.design("a\x00b")
        sd.design(b"a\x00b")
        got = [str(x.message) for x in w if issubclass(x.category, EPWarning)]
        ck.true("\\x00 경고 2개", len(got) == 2 and all("\\x00" in m for m in got), repr(got))
        sd.design("no nul")
        ck.eq("\\x00 없으면 경고 없음", len([x for x in w if issubclass(x.category, EPWarning)]), 2)

    # 입력 검사
    for bad in (None, True, False, 5, 1.5, EUDVariable, object(), ["a"], ("a",)):
        ck.true("design 입력 오류 %r" % (bad,), raises(sd.design, bad))
    try:
        sd.design(1.5)
    except EudextError as e:
        ck.true("숫자 안내문", "lua_tostring" in str(e), str(e))
    ck.true("design(bytearray) → bytes", sd.design(bytearray(b"q")) == as_bytes(sd.design("q")))
    for kw in ({"center": 2}, {"lead": None}, {"right": "yes"}, {"center": True, "right": True}):
        ck.true("플래그 오류 %r" % kw, raises(sd.design, "x", **kw))
    ck.eq("center=1 은 True", sd.design("x", center=1), sd.design_x("x"))
    ck.eq("lead=0 은 False", sd.design_x("x", style="memory", lead=0), sd.StrDesignX2("x", style="memory"))
    # right
    pre, post = sd.parts("seed")
    ck.eq("right", sd.design("x", right=True), "\x12" + pre + "x" + post)
    ck.eq("right memory", sd.design("x", style="memory", right=True), "\r\r\x12" + sd.parts("memory")[0] + "x" + sd.parts("memory")[1])
    ck.eq("CENTER/RIGHT", (sd.CENTER, sd.RIGHT), ("\x13", "\x12"))
    # lead 는 memory 판에만 영향
    for style in ("mcf", "seed", "respect"):
        ck.eq("lead=False 무영향 %s" % style, sd.design("x", style=style, lead=False), sd.design("x", style=style))
        ck.eq("StrDesignX2 = StrDesignX %s" % style, sd.StrDesignX2("x", style=style), sd.StrDesignX("x", style=style))
    # lua_tostring 오류
    for bad in (None, True, float("inf"), float("-inf"), float("nan"), 2 ** 63, -(2 ** 63) - 1, [1], object()):
        ck.true("lua_tostring 오류 %r" % (bad,), raises(sd.lua_tostring, bad))
    ck.eq("lua_tostring str", sd.lua_tostring("가"), "가")
    ck.eq("lua_tostring bytes", sd.lua_tostring(b"\xff"), b"\xff")
    ck.true("StrDesign(None) 오류", raises(sd.StrDesign, None))
    ck.true("StrDesign(True) 오류", raises(sd.StrDesign, True))
    ck.eq("StrDesign(1.5)", sd.StrDesign(1.5), sd.design("1.5"))

    # wrap
    pre, post = sd.parts()
    ck.eq("wrap 기본", sd.wrap("a", 5), [pre, "a", 5, post])
    ck.eq("wrap center", sd.wrap("a", center=True), ["\x13" + pre, "a", post])
    ck.eq("wrap 빈", sd.wrap(), [pre, post])
    ck.eq("wrap memory", sd.wrap("a", style="memory", center=True), ["\r\r\x13" + sd.parts("memory")[0], "a",
                                                                     sd.parts("memory")[1]])
    ck.eq("wrap memory lead=False", sd.wrap("a", style="memory", center=True, lead=False)[0], "\x13" + sd.parts("memory")[0])
    v = EUDVariable()
    w = sd.wrap("x", v, "y")
    ck.true("wrap 은 원소를 그대로", w[2] is v and len(w) == 5 and w[1] == "x" and w[3] == "y")
    ck.eq("wrap 이어 붙임 = design", "".join(sd.wrap("가", "나", right=True, style="respect")),
          sd.design("가나", right=True, style="respect"))
    ck.true("wrap 플래그 오류", raises(sd.wrap, "x", center=True, right=True))

    # Style
    a = sd.Style("<", ">")
    b = sd.Style(b"<", b">", name="other")
    ck.true("Style 같음 (name 무관)", a == b and hash(a) == hash(b) and not (a != b))
    ck.true("Style 다름", a != sd.Style("<", ">", lead="\r"))
    ck.true("Style 과 str 비교", (a == "<") is False)
    ck.eq("Style 속성", (a.pre, a.post, a.lead, a.name, b.name), ("<", ">", "", None, "other"))
    ck.eq("Style.parts", a.parts(), ("<", ">"))
    ck.eq("사용자 Style", sd.design("x", style=a, center=True), "\x13<x>")
    ck.true("Style 은 불변", raises(setattr, a, "pre", "!"))
    ck.true("Style 은 불변 (지우기)", raises(delattr, a, "pre"))
    ck.true("Style 새 속성 막음", raises(setattr, a, "extra", 1))
    ck.true("Style 입력 오류", raises(sd.Style, 1, ">"))
    ck.true("Style UTF-8 아님", raises(sd.Style, b"\xff", ">"))
    ck.true("Style name 오류", raises(sd.Style, "<", ">", name=3))
    ck.true("STYLES 읽기 전용", not _can_set(sd.STYLES))
    ck.true("repr", repr(sd.STYLES["memory"]).startswith("Style(") and "lead=" in repr(sd.STYLES["memory"]))
    import copy
    import pickle

    ck.true("Style 복사·pickle", copy.deepcopy(a) == a and pickle.loads(pickle.dumps(sd.STYLES["seed"])) == sd.STYLES["seed"])
    ck.true("set_style(Style)", quiet(sd.set_style, a) is a)
    ck.eq("set_style(Style) 뒤 design", sd.design("q"), "<q>")
    ck.eq("MAP_STYLES", {k: sd.MAP_STYLES[k] for k in ("DPS_Enhance", "theSeed", "Stella_II", "MSF_Respect_V", "MSF_Memory_2")},
          {"DPS_Enhance": "mcf", "theSeed": "seed", "Stella_II": "seed", "MSF_Respect_V": "respect", "MSF_Memory_2": "memory"})
    ck.true("MAP_STYLES 값은 판 이름", all(v in sd.STYLES for v in sd.MAP_STYLES.values()))

    # f_ 별칭 (DESIGN 3.1)
    for name in ("design", "design_x", "set_style", "get_style", "parts", "wrap", "lua_tostring"):
        ck.true("f_ 별칭 %s" % name, getattr(sd, name) is getattr(sd, "f_" + name))
    ck.true("__all__", all(hasattr(sd, n) for n in sd.__all__))
    # docstring 3.12 항목, 비공개 eudplib 이름 없음
    for obj in (sd.Style, sd.f_set_style, sd.f_get_style, sd.f_design, sd.f_design_x, sd.f_parts, sd.f_wrap,
                sd.f_lua_tostring, sd.StrDesign, sd.StrDesignX, sd.StrDesignX2):
        doc = inspect.getdoc(obj) or ""
        miss = [k for k in DOC_KEYS if k not in doc]
        ck.eq("docstring %s" % obj.__qualname__, miss, [])
    for word in ("set_style", "lua_tostring", "\\r\\r!H", "mcf", "seed", "respect", "memory", "S7"):
        ck.true("모듈 문서에 %s" % word, word in (sd.__doc__ or ""))
    src = open(sd.__file__, encoding="utf-8").read()
    for bad in ("import eudplib", "from eudplib", "_compat", "eudext.testing"):
        ck.true("strdesign.py 에 %s 없음 (순수 파이썬)" % bad, bad not in src)
    # 줄바꿈: 장식은 첫 줄 앞과 끝 줄 뒤에만 (S7 3-6), \x13 중복 그대로 (3-1)
    quiet(sd.set_style, "seed")
    ck.eq("줄바꿈", sd.design("a\nb").split("\n"), [pre + "a", "b" + post])
    ck.eq("\\x13 중복", sd.design_x("\x13a"), "\x13" + pre + "\x13a" + post)

    # 트리거 0 (호출 전후 트리거 수)
    n0 = GetTriggerCounter()
    for style in sd.STYLES:
        sd.design("x", style=style)
        sd.design_x(b"x", style=style, lead=False)
        sd.parts(style)
        sd.wrap("a", style=style, right=True)
        sd.StrDesign(1.5, style=style)
        sd.lua_tostring(1 / 3)
    ck.eq("트리거 0", GetTriggerCounter() - n0, 0)
    sd.set_style(None)


def _can_set(mapping):
    try:
        mapping["x"] = 1
    except TypeError:
        return False
    return True


# =============================================================================================
# 4. 에뮬레이터 — 맵 문자열 표에 들어간 바이트
# =============================================================================================

def emulator_strings(defs):
    """고정 156건 중 문자열 결과(130) + 무작위 200개를 DisplayText 로 찍고, 기록된 문자열 바이트를 원본 Lua 결과와 비교."""
    s = Suite("t_strdesign 에뮬레이터 (DisplayText)", memory={"text": True})
    items = []  # (이름, 넣은 문자열, 기대 bytes)
    for (key, func), row in R.EXPECTED.items():
        style = R.FILE_STYLE[key]
        for (name, value), want in zip(R.INPUTS, row):
            if want is None:
                continue
            txt = value if isinstance(value, str) else sd.lua_tostring(value)
            items.append(("%s.%s(%s)" % (key, func, name), call_design(style, func, txt), bytes.fromhex(want)))
    rng = random.Random(0x6A)
    keys = [(k, st, f) for k, st, fs, _p in R.LUA_FILES for f in fs]
    for i in range(200):
        value = rand_input(rng)
        key, style, func = rng.choice(keys)
        if isinstance(value, (int, float)):
            value = sd.lua_tostring(value)
        if defs is not None:
            want = defs[key].call(func, value)
        else:
            want = R.ref_bytes(style, func, value)
        items.append(("무작위 #%d %s.%s" % (i, key, func), call_design(style, func, value), want))

    @s.case("all")
    def _(t):
        for j in range(0, len(items), 32):
            DoActions([DisplayText(x[1]) for x in items[j:j + 32]])

    s.build()
    model = scmodel.text_model(s.machine)
    model.clear()
    r = s.run("all", {})
    got = [model.strings.get(rec.strid) for rec in model.records if rec.kind == "text"]
    s.expect_true("all", r.error is None, "실행", str(r.error))
    s.expect_true("all", len(got) == len(items), "기록 수 %d" % len(items), "기록 %d" % len(got))
    for (name, _txt, want), g in zip(items, got):
        # 맵 문자열은 NUL 에서 끝난다 (S7 7-6 — 화면에서도 거기서 끊긴다)
        cut = want.split(b"\x00")[0]
        s.expect_true("all", g == cut, name, "%r != %r" % (hexs(g), hexs(cut)))
    s.expect_true("all", r.steps and r.steps[0] == len(range(0, len(items), 32)), "실행 트리거 = DisplayText 묶음 수",
                  repr(r.steps))
    return s.report()


# =============================================================================================
# 5. epScript 예제·인게임 맵
# =============================================================================================

EPS_NEEDLES = (
    'from eudext import strdesign as sd',
    'sd.f_set_style("memory")',
    'sd.f_design("\\x04[\\x1f보스\\x04] 등장")',
    'sd.f_design_x("\\x1DExtra Boss\\x04 출현")',
    'sd.StrDesignX2(',
    'sd.f_design_x("\\x04theSeed 모양", style="seed", lead=False)',
    'sd.StrDesign(5)',
    'sd.f_parts()',
    'sd.f_wrap("\\x04남은 적", center=True)',
    'f_printAll(title)',
    'DoActions(DisplayText(center))',
    'f_printAll("{}\\x04남은 적 {}{}", pp[0], n, pp[1])',
)
INGAME_NEEDLES = (
    'sd.f_set_style("seed")',
    'sd.f_design("\\x04왼쪽 정렬 (StrDesign)", style="mcf")',
    'sd.f_design_x("\\x04가운데 정렬 (StrDesignX2, \\\\r\\\\r 없음)", style="memory", lead=False)',
    'sd.f_design("\\x04오른쪽 정렬 (\\\\x12, Stella_II 모양)", right=True)',
    'sd.f_parts("respect")',
)


def eps_checks(ck):
    for name, needles in (("strdesign_example.eps", EPS_NEEDLES), ("strdesign_ingame.eps", INGAME_NEEDLES)):
        with open(os.path.join(EX, name), encoding="utf-8") as f:
            src = f.read()
        out, nerr = _compat.eps_compile(name, src)
        ck.eq("eps 오류 수 " + name, nerr, 0)
        ck.true("eps 번역 " + name, out is not None)
        if out:
            for needle in needles:
                ck.true("eps 번역 %s 에 %s" % (name, needle), needle in out, "")
    # 함정 기록: 액션 문장의 문자열 리터럴에 짝 없는 ")" 가 있으면 번역문의 닫는 괄호가 사라진다 (eudplib 0.81.0 epScript).
    # sd.design(...) 으로 감싸거나 const 에 담으면 괜찮다. eudplib 이 고치면 이 판정이 실패한다 — 그때 설계 문서의 함정을 지운다.
    for body, broken in (('DisplayText("a 2) b");', True), ('DisplayText(sd.design("a 2) b"));', False),
                         ('printAll("a 2) b");', False), ('DisplayText("(2) b");', False)):
        out, nerr = _compat.eps_compile("paren.eps", 'import eudext.strdesign as sd;\nfunction f() { %s }\n' % body)
        try:
            compile(out, "paren.py", "exec")
            bad = False
        except SyntaxError:
            bad = True
        ck.eq("epScript 짝 없는 ) 함정: %s" % body, (nerr, bad), (0, broken))
    # 짧은 모양: 전역 const + printAll (지시문)
    src = ('import eudext.strdesign as sd;\nconst st = sd.set_style("mcf");\nconst s = sd.design("x");\n'
           'function f() { printAll(s); printAll(sd.design_x("y")); DisplayText(sd.StrDesign("z")); }\n')
    out, nerr = _compat.eps_compile("short.eps", src)
    ck.true("eps 짧은 모양", nerr == 0 and out is not None and 's = _CGFW(lambda: [sd.f_design("x")], 1)[0]' in out
            and "f_printAll(s)" in out and 'f_printAll(sd.f_design_x("y"))' in out, repr(out))


def lua_line(defs, key, func, text):
    if defs is not None:
        return defs[key].call(func, text)
    return R.ref_bytes(R.FILE_STYLE[key], func, text)


def load_eps(name, work):
    from eudext.tools import build

    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, name), os.path.join(work, name))
    return build._load_plugin(os.path.join(work, name), {})


def run_eps(mod, cycles, watch=()):
    prog = emu.Program(mod.afterTriggerExec)
    for n in watch:
        prog.watch(n, getattr(mod, n))
    m = prog.build()
    model = scmodel.install_text(m)
    err = None
    try:
        for _ in range(cycles):
            m.cycle()
    except emu.EmuError as e:
        err = str(e)
    return m, model, err


def example_emulate(ck, defs):
    """예제 eps 를 에뮬레이터에서 3 사이클 돌려 찍힌 문자열을 원본 Lua 결과와 비교한다."""
    sd.set_style(None)
    LoadMap(BASE_MAP)
    CompressPayload(True)
    mod = load_eps("strdesign_example.eps", os.path.join(_common.WORK, "t_strdesign", "example"))
    ck.true("예제: 판 memory", sd.get_style() is sd.STYLES["memory"])
    m, model, err = run_eps(mod, 3, ("shown",))
    ck.eq("예제 에뮬레이터 오류", err, None)
    ck.eq("예제 shown", m.var("shown"), 1)
    got = [model.strings.get(r.strid) for r in model.records if r.kind == "text"]
    pre, post = (as_bytes(x) for x in sd.parts("memory"))
    want = [
        lua_line(defs, "Mem2", "StrDesign", "\x04[\x1f보스\x04] 등장"),
        lua_line(defs, "Mem2", "StrDesignX", "\x1DExtra Boss\x04 출현"),
        b"\r\r!H" + lua_line(defs, "Mem2", "StrDesignX2", "\x04채팅 효과 줄"),
        b"\x13" + lua_line(defs, "Seed", "StrDesign", "\x04theSeed 모양"),
        lua_line(defs, "Mem2", "StrDesign", 5),
        lua_line(defs, "Mem2", "StrDesignX", "\x04남은 적"),
    ]
    ck.eq("예제 문자열 6줄 = 원본 Lua", [hexs(g) for g in got[:6]], [hexs(w) for w in want])
    ck.eq("예제 기록 수 (printAll 서식 줄 포함)", len(got), 7)
    ck.eq("예제 parts", (pre, post), (bytes.fromhex(R.STYLE_HEX["memory"][1]), bytes.fromhex(R.STYLE_HEX["memory"][2])))
    ck.eq("예제 세 번째 줄은 채팅 표식 4바이트로 시작", got[2][:4] if len(got) > 2 else None, b"\r\r!H")
    ck.true("예제 memory 줄은 표식과 4바이트가 다르다 (S7 3-7)", got[0][:4] != b"\r\r!H" and got[0][:2] == b"\r\r")
    sd.set_style(None)


# 인게임 맵이 쪽마다 찍는 줄 (원본 함수, 판 키, 입력) — None 이면 장식 없는 줄(머리말), ("raw", bytes) 는 직접 만든 기대값
def ingame_expected(defs):
    sp = {k: tuple(as_bytes(x) for x in sd.parts(k)) for k in sd.STYLES}
    pages = [
        [None, None,
         ("L322", "StrDesign", "\x04왼쪽 정렬 (StrDesign)"),
         ("L322", "StrDesignX", "\x04가운데 정렬 (StrDesignX)"),
         ("L322", "StrDesignX", "\x1DExtra Boss\x04 등장 — 가운데")],
        [None,
         ("Seed", "StrDesign", "\x04왼쪽 정렬 (StrDesign)"),
         ("Stel", "StrDesignX", "\x04가운데 정렬 (StrDesignX)"),
         ("Tpl", "StrDesign", "\x04[\x1f보스\x04] 등장 (전역 const + printAll)")],
        [None,
         ("ResV", "StrDesign", "\x04왼쪽 정렬 (StrDesign)"),
         ("ResV", "StrDesignX", "\x04가운데 정렬 (StrDesignX)"),
         ("raw", b"\x13" + sp["respect"][0] + "\x07StrD[1] .. 글 .. StrD[2]".encode() + sp["respect"][1])],
        [None,
         ("Mem2", "StrDesign", "\x04왼쪽 정렬 (StrDesign, 앞에 \\r\\r)"),
         ("Mem2", "StrDesignX", "\x04가운데 정렬 (StrDesignX, \\r\\r 뒤에 \\x13)"),
         ("Mem2", "StrDesignX2", "\x04가운데 정렬 (StrDesignX2, \\r\\r 없음)")],
        [None,
         ("Seed", "StrDesignX", "\x13\x04\\x13 이 두 번 들어간 줄"),
         ("raw", b"\x12" + sp["seed"][0] + "\x04오른쪽 정렬 (\\x12, Stella_II 모양)".encode() + sp["seed"][1]),
         ("Seed", "StrDesign", "\x04첫 줄\n\x04둘째 줄"),
         None],
    ]
    out = []
    for page in pages:
        row = []
        for item in page:
            if item is None:
                row.append(None)
            elif item[0] == "raw":
                row.append(item[1])
            else:
                row.append(lua_line(defs, *item))
        out.append(row)
    return out


def ingame_emulate(ck, defs):
    """인게임 확인 맵을 에뮬레이터에서 두 바퀴(5쪽 × 144 사이클 × 2 + 1) 돌린다. 쪽마다 줄 수·내용·순서를 본다."""
    sd.set_style(None)
    LoadMap(BASE_MAP)
    CompressPayload(True)
    mod = load_eps("strdesign_ingame.eps", os.path.join(_common.WORK, "t_strdesign", "ingame"))
    ck.true("인게임: 판 seed", sd.get_style() is sd.STYLES["seed"])
    m, model, err = run_eps(mod, 144 * 10 + 1, ("page", "wait"))
    ck.eq("인게임 에뮬레이터 오류", err, None)
    recs = [r for r in model.records if r.kind == "text"]
    pages = ingame_expected(defs)
    per = sum(len(p) for p in pages)
    ck.eq("인게임 줄 수 (두 바퀴 + 1쪽)", len(recs), per * 2 + len(pages[0]))
    ck.eq("인게임 쪽 시작 사이클", sorted({r.cycle for r in recs})[:6], [0, 144, 288, 432, 576, 720])
    flat = [x for p in pages for x in p]
    got = [model.strings.get(r.strid) for r in recs[:per]]
    for i, (g, w) in enumerate(zip(got, flat)):
        if w is None:
            ck.true("인게임 머리말 줄 %d" % i, g is not None and g.startswith(b"\x04[D6"), repr(g))
        else:
            ck.eq("인게임 장식 줄 %d = 원본 Lua" % i, hexs(g), hexs(w))
    ck.eq("인게임 두 바퀴째 = 첫 바퀴", [model.strings.get(r.strid) for r in recs[per:2 * per]], got)
    heads = [g.decode("utf-8", "replace") for g in got if g and g.startswith(b"\x04[D6-")]
    ck.eq("인게임 항목 번호", [h[2:6] for h in heads], ["D6-1", "D6-2", "D6-3", "D6-4", "D6-5"])
    ck.true("인게임 줄 길이 ≤ 218 (SC 채팅 줄)", all(len(g) <= 218 for g in got if g), repr([len(g) for g in got if g]))
    ck.eq("인게임 page/wait", (m.var("page"), m.var("wait")), (1, 143))
    sd.set_style(None)


def euddraft_build(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        ck.true("euddraft 있음", False, build.EUDDRAFT)
        return
    for name in ("strdesign_example", "strdesign_ingame"):
        work = os.path.join(_common.WORK, "t_strdesign", "euddraft_" + name)
        shutil.rmtree(work, ignore_errors=True)
        eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
        r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
        print("  " + r.summary())
        ck.true("euddraft " + name, r.ok, r.log[-2000:])
        ck.true("euddraft freeze off " + name, not r.freeze)
        ck.true("euddraft eps " + name, '[epScript] Compiling "%s.eps"' % name in r.log, r.log[-1000:])
        ck.true("euddraft 판 경고 없음 " + name, "옛 판" not in r.log, "")


# =============================================================================================
# 비용 (tools/cost.py)
# =============================================================================================

def _cost_design(t):
    for style in ("mcf", "seed", "respect", "memory"):
        sd.design("\x04[\x1f보스\x04] 등장", style=style)
        sd.design_x("가운데", style=style, lead=False)


def _cost_parts(t):
    sd.wrap("a", t.var("v"), style="seed", center=True)
    sd.parts("memory")
    sd.StrDesignX(1.5, style="mcf")


def _cost_display(t):
    DoActions(DisplayText(sd.design("보스 등장", style="seed")))


COST_MEMORY = {"text": True}
COST_CASES = [
    CostCase("sd.design / design_x (판 4개 × 2)", _cost_design, target={"call": 0, "exec": 0},
             note="컴파일 시점 순수 함수 — 트리거 0"),
    CostCase("sd.wrap / parts / StrDesignX(숫자)", _cost_parts, target={"call": 0, "exec": 0}, note="트리거 0"),
    CostCase("참고: DoActions(DisplayText(sd.design(…)))", _cost_display, target={"call": 1},
             note="DisplayText 액션 1개 트리거(strdesign 몫은 0, 문자열은 맵 STR 에 들어가 페이로드와 무관)"),
]


# =============================================================================================

ARTIFACTS = ("__pycache__", "__epspy__")


def repo_artifacts():
    found = []
    for dirpath, dirnames, filenames in os.walk(_common.PKG):
        rel = os.path.relpath(dirpath, _common.PKG)
        if rel.startswith("docs"):
            continue
        for d in dirnames:
            if d in ARTIFACTS:
                found.append(os.path.join(rel, d))
        for f in filenames:
            if f.endswith((".scx", ".pyc")) and not (rel == "testing" and f.startswith("base")):
                found.append(os.path.join(rel, f))
    return found


def main():
    before = set(repo_artifacts())
    ck = Checker("t_strdesign (python)")
    expected_156(ck)
    doc_rows(ck)
    ckl = Checker("t_strdesign (lupa 차등)")
    defs = lupa_diff(ckl)
    api_checks(ck)
    oks = [emulator_strings(defs)]
    cke = Checker("t_strdesign (epScript·인게임 맵)")
    eps_checks(cke)
    example_emulate(cke, defs)
    ingame_emulate(cke, defs)
    euddraft_build(cke)
    ck.eq("repo clean", sorted(set(repo_artifacts()) - before), [])
    oks += [ck.report(), ckl.report(), cke.report()]
    finish(*oks)


if __name__ == "__main__":
    main()
