"""`numfmt` 차등 시험 (에뮬레이터): Dec·Hex·Per·Man·Gauge·numfmt.dp·직접 쓰기·셀·서식 지정자·epScript.

- 옵션 조합(32비트 179 · 64비트 20 · 16진 9 · 소수점 14 · 만 단위 13 · 막대 6)마다 경계값 + 무작위 값으로
  **바이트 단위** 비교. 기준은 `tests/ref_numfmt.py`(파이썬 참조 — 확장이 없는 조합은 파이썬 `format` 과 같음을 스스로 확인)와
  `format` 자체(확장을 쓰지 않는 조합). 에뮬레이터 바이트 읽기(`Machine.read_bytes`).
- `numfmt.dp.*` 9개: docs/spec/S3_display.md 8.1 기대값 표 + 무작위 2만 개(S3 8.2-1) — REF 모델(`ref_numfmt.dp_*`)과 차등.
- fmt() 훅: `f_dbstr_print`·`f_sprintf`·`StringBuffer.print/printf`·`printAll` (문자열 결과는 한 빌드에, DESIGN 5.1),
  한 인쇄에 fmt() 두 개, 입력 종류(EUDLightVariable·Int64Array 원소·32비트를 64비트로·주소식·문자열·음수 상수),
  `f_cpchar_print`/TextFX/`StringBuffer.fadeIn` 안내 오류, `enable_format_spec` 켠 뒤 `{:05d}`·`{:+,d}`·`{:08x}`·`{:w}`…
  (끈 뒤 원래대로), `f_fmt_dec_to`(단어째·바이트 복사·앞뒤 보존), `f_fmt_dec_cells`/`f_scan_dec_cells` 왕복과 손으로 만든 셀,
  CP 보존.
- epScript 예제(examples/numfmt_example.eps) 번역·에뮬레이터 실행·euddraft 빌드, DESIGN 0.3 모양 번역·실행,
  인게임 확인 맵(numfmt_ingame) 에뮬레이터(23 / 23)·빌드, 빌드 오류여야 하는 epScript,
  파이썬 쪽 판정(옵션 오류·상수 서식·계획 흉내 = 참조 — 조합 수천 개·문서·비공개 API).

python tests/t_numfmt.py        (환경 변수 NUMFMT_DP_RANDOM = dp 무작위 개수, 기본 20000)
비용 표: python tools/cost.py tests/t_numfmt.py [--append --out <파일> --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import importlib  # noqa: E402
import itertools  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402
import types  # noqa: E402

from eudplib import (  # noqa: E402
    EPD,
    CompressPayload,
    Db,
    EPSLoader,
    EUDLightVariable,
    EUDVariable,
    GetGlobalStringBuffer,
    GetMapStringAddr,
    LoadMap,
    SeqCompute,
    SetTo,
    StringBuffer,
    TextFX_FadeIn,
    f_dbstr_print,
    f_getcurpl,
    f_printAll,
    f_sprintf,
)

import ref_numfmt as R  # noqa: E402
from eudext import _compat, numfmt  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.i64 import Int64, Int64Array  # noqa: E402
from eudext.numfmt import Dec, Gauge, Hex, Man, Per, dp  # noqa: E402
from eudext.testing import emu  # noqa: E402
from eudext.testing.harness import BASE_MAP, Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1
D = 0x0D
EPD0 = 0x58A364
EX = os.path.join(_common.PKG, "examples")

EDGE32 = sorted({
    0, 1, 2, 9, 10, 11, 99, 100, 101, 999, 1000, 1001, 9999, 10**4, 99999, 10**5, 10**6 - 1, 10**6, 10**7 - 1, 10**7,
    10**8 - 1, 10**8, 10**9 - 1, 10**9, 1234567890, 2**31 - 2, 2**31 - 1, 2**31, 2**31 + 1, 2**32 - 10, 2**32 - 2, M32,
})  # fmt: skip
EDGE64 = sorted({
    0, 1, 9, 10, 99, M32, 2**32, 2**32 + 1, 10**10, 12800000000, 10**12 - 1, 10**12, 10**16 - 1, 10**16, 10**18 - 1,
    10**18, 10**19 - 1, 10**19, 2**63 - 2, 2**63 - 1, 2**63, 2**63 + 1, 2**64 - 10**18, M64 - 1, M64,
})  # fmt: skip


def s32(v):
    v &= M32
    return v - (1 << 32) if v >> 31 else v


def rvals32(rng, n):
    out = []
    for _ in range(n):
        if rng.random() < 0.6:
            out.append(rng.randrange(10 ** rng.randrange(1, 11)) & M32)
        else:
            out.append(rng.getrandbits(32))
    return out


def rvals64(rng, n):
    out = []
    for _ in range(n):
        if rng.random() < 0.6:
            out.append(rng.randrange(10 ** rng.randrange(1, 21)) & M64)
        else:
            out.append(rng.getrandbits(64))
    return out


def cstr(m, addr, n=300):
    return m.read_bytes(addr, n).split(b"\0")[0]


def ref_kw(kw):
    """Dec 옵션 → ref_numfmt.dec 인자."""
    kw = dict(kw)
    if "_mode" in kw:
        kw["mode"] = kw.pop("_mode")
    kw.pop("bits", None)
    if kw.get("group") is True:
        kw["group"] = (3, ",")
    return kw


# ---------------------------------------------------------------------------------------------
# 옵션 조합
# ---------------------------------------------------------------------------------------------

LIN3 = "０１２３４５６７８９"
CJK = "零一二三四五六七八九"
CIRC = ["⓪", "①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨"]  # 0 만 등차가 아님 → 자리마다 트리거 9
MIX4 = ["🄌", "➀", "➁", "➂", "➃", "➄", "➅", "➆", "➇", "➈"]  # 4바이트 + 3바이트 (접두 없는 4B 슬롯)


def combos32():
    base = list(itertools.product((0, 1, 5, 11, 14), ("\r", "0", " ", "*"), (None, "-", "+-", " -"), (None, (3, ",")),
                                  (None, ">", "=")))  # fmt: skip
    rng = random.Random(11)
    rng.shuffle(base)
    out = [dict(width=w, fill=f, sign=sg, group=g, align=a) for w, f, sg, g, a in base[:130]]
    out += [
        dict(), dict(width=5, fill="0"), dict(sign="-"), dict(group=(3, ",")), dict(width=10, fill="0", sign="+-", group=(3, ",")),
        dict(sign="-", sign_space=True), dict(sign="+-", sign_space=True, width=13, fill="0"),
        dict(sign=" -", sign_space=True, width=9, fill="*"),
        dict(max_digits=1), dict(max_digits=3, width=5), dict(max_digits=9, sign="-", fill="0", width=11),
        dict(max_digits=2, width=2), dict(max_digits=5, group=(3, ","), sign="+-"),
        dict(cut_low=1), dict(cut_low=3, width=12, fill="0", sign="+-", group=(3, ",")), dict(cut_low=10),
        dict(max_digits=4, cut_low=2, sign="-", width=7), dict(cut_low=2, width=8, fill=" "),
        dict(group=(4, "'")), dict(group=(2, "."), width=16, fill="0"), dict(group=(1, "_"), sign="-"),
        dict(fullwidth=True), dict(fullwidth=True, width=12, fill="\r"),
        dict(fullwidth=True, width=14, fill="0", sign="+-", group=(3, ",")), dict(fullwidth=True, fill=" ", width=13, sign=" -"),
        dict(fullwidth=True, cut_low=3, max_digits=6, sign="-"),
        dict(colors=0x1F), dict(colors=(1, 2, 3, 4, 5)), dict(colors=(8, 0, 14), width=12, fill="0", sign="-", group=(3, ",")),
        dict(colors=tuple(range(1, 11)), fullwidth=True, sign="+-"), dict(colors=(7,), width=6, fill=" ", cut_low=1),
        dict(glyphs=CJK), dict(glyphs=CJK, colors=0x11, width=11, fill=" "), dict(glyphs="0369258147"),
        dict(glyphs="abcdefghij", width=4, fill="0"), dict(glyphs=CIRC, sign="-"), dict(glyphs=LIN3),
        dict(glyphs=MIX4, width=3), dict(glyphs=CJK, max_digits=3, cut_low=1, sign="+-"),
        dict(width=40, fill="0", sign="-", group=(3, ",")), dict(width=30, fill="*", sign="+-", align="="),
        dict(width=25, fill=" ", sign=" -", sign_space=True), dict(width=33, fill="\r", group=(3, ","), sign="-"),
        dict(_mode="eudplib"), dict(_mode="ctrig"), dict(_mode="ctrig", colors=4, sign="-", group=(3, ",")),
        dict(_mode="eudplib", glyphs=CJK, width=12), dict(_mode="eudplib", width=13, fill="0", sign="+-"),
        dict(_mode="ctrig", glyphs="abcdefghij", sign="-", width=12, fill=" "),
    ]  # fmt: skip
    return out


COMBOS64 = [
    dict(), dict(sign="-"), dict(sign="+-", sign_space=True), dict(group=(3, ",")),
    dict(width=30, fill="0", sign="-", group=(3, ",")), dict(width=22), dict(width=25, fill="*", sign=" -"),
    dict(max_digits=5), dict(max_digits=19, sign="-"), dict(cut_low=3), dict(cut_low=20, sign="+-"),
    dict(fullwidth=True), dict(fullwidth=True, group=(3, ","), sign="-", width=30, fill="0"), dict(colors=(1, 2, 3)),
    dict(glyphs=LIN3), dict(_mode="ctrig", group=(3, ",")), dict(width=20, fill="0"), dict(sign="-", width=21, fill="\r"),
    dict(group=(4, " "), sign="-", width=28, fill="0"),
]  # fmt: skip

COMBOS_HEX = [
    dict(), dict(width=0), dict(width=0, lower=True), dict(width=4), dict(width=4, fill="\r"), dict(width=12, fill=" "),
    dict(width=10, fill="0", lower=True), dict(width=3, fill="0", align=">"), dict(width=16, fill="*", align="="),
]  # fmt: skip

COMBOS_PER = [
    dict(), dict(max=100000), dict(scale=100, frac=2), dict(scale=100, frac=1, trim=False), dict(scale=10**6, frac=6, int_min=2),
    dict(frac=0), dict(scale=10, frac=1, width=12, fill="0"), dict(max=5000000, width=8), dict(trim=False, int_min=3),
    dict(scale=10**9, frac=9, int_min=1), dict(scale=10**4, frac=2, width=10, fill="*"),
]  # fmt: skip
COMBOS_PER64 = [dict(), dict(scale=10**9, frac=4, max=10**15), dict(scale=10**12, frac=12, trim=False, width=30)]

COMBOS_MAN = [
    dict(), dict(colors="dps", after=4), dict(colors="dps", after=4, fixed=True), dict(fixed=True), dict(top=1),
    dict(top=1, colors=[1, 2, 3], after=0x1F), dict(colors=[(1, 2), (3, 4), (5, 6)], units="KMB"),
    dict(units="ABCD", fixed=True, colors="dps"), dict(colors=[0x11, 0, 5], after=0x1E, units="만억조"),
]  # fmt: skip
COMBOS_MAN64 = [dict(), dict(colors="dps", after=4, fixed=True), dict(top=1, colors="dps"), dict(units="kmbtq", after=2)]

COMBOS_GAUGE = [
    dict(), dict(cells=1), dict(cells=5, glyph="■", on=0x11, off=0x05), dict(cells=33, glyph="é"), dict(cells=60),
    dict(cells=7, glyph="|", on=0x03, off=0x03),
]  # fmt: skip


def per_ref(v, kw):
    return R.per(v, kw.get("scale", 1000), kw.get("frac", 3), kw.get("max"), kw.get("trim", True), kw.get("int_min", 1),
                 kw.get("width", 0), kw.get("fill", "\r"))  # fmt: skip


def man_ref(v, kw, bits):
    return R.man(v, bits, kw.get("top", 2), kw.get("colors"), kw.get("after"), kw.get("units", R.UNITS), kw.get("fixed", False))


# ---------------------------------------------------------------------------------------------
# 1. 서식 바이트 (옵션 조합 × 값)
# ---------------------------------------------------------------------------------------------


def add_case(s, name, make, bits=32):
    @s.case(name)
    def _(t):
        x, h = t.var("x"), t.var("h")
        v = x if bits == 32 else Int64.wrap(x, h)
        t.out("p", make(v).fmt()._value)


def judge_bytes(s, name, v, want, label):
    r = s.run(name, {"x": v & M32, "h": (v >> 32) & M32})
    if r.error:
        return s.expect_true(name, False, label, r.error)
    got = cstr(s.machine, r["p"])
    return s.expect_true(name, got == want, label, "%r != %r" % (got, want))


def suite_formats():
    s = Suite("t_numfmt 서식 바이트")
    c32 = combos32()
    for i, kw in enumerate(c32):
        add_case(s, "d32_%03d" % i, lambda v, kw=kw: Dec(v, **kw))
    for i, kw in enumerate(COMBOS64):
        add_case(s, "d64_%02d" % i, lambda v, kw=kw: Dec(v, **kw), bits=64)
    add_case(s, "d32as64", lambda v: Dec(v, bits=64, sign="-", group=(3, ",")))
    for i, kw in enumerate(COMBOS_HEX):
        add_case(s, "hex_%d" % i, lambda v, kw=kw: Hex(v, **kw))
    for i, kw in enumerate(COMBOS_PER):
        add_case(s, "per_%02d" % i, lambda v, kw=kw: Per(v, **kw))
    for i, kw in enumerate(COMBOS_PER64):
        add_case(s, "per64_%d" % i, lambda v, kw=kw: Per(v, **kw), bits=64)
    for i, kw in enumerate(COMBOS_MAN):
        add_case(s, "man_%d" % i, lambda v, kw=kw: Man(v, **kw))
    for i, kw in enumerate(COMBOS_MAN64):
        add_case(s, "man64_%d" % i, lambda v, kw=kw: Man(v, **kw), bits=64)
    for i, kw in enumerate(COMBOS_GAUGE):
        add_case(s, "gauge_%d" % i, lambda v, kw=kw: Gauge(v, **kw))
    s.build()
    rng = random.Random(5)
    for i, kw in enumerate(c32):
        name = "d32_%03d" % i
        for v in EDGE32 + rvals32(rng, 26):
            want = R.dec(v, 32, **ref_kw(kw))
            judge_bytes(s, name, v, want, "%r v=0x%X" % (kw, v))
            plain = not any(k in kw for k in ("sign_space", "max_digits", "cut_low", "fullwidth", "colors", "glyphs", "_mode"))
            g = kw.get("group")
            if plain and (g is None or (g[0] == 3 and g[1] in ",_")):
                x = s32(v) if kw.get("sign") else v
                spec = R.py_spec(kw.get("width", 0), kw.get("fill", "\r"), kw.get("sign"), g, kw.get("align"))
                s.expect_true(name, format(x, spec).encode() == want, "python format %r v=%d" % (spec, x))
    for i, kw in enumerate(COMBOS64):
        for v in EDGE64 + rvals64(rng, 30):
            judge_bytes(s, "d64_%02d" % i, v, R.dec(v, 64, **ref_kw(kw)), "%r v=0x%X" % (kw, v))
    for v in EDGE32 + rvals32(rng, 20):
        judge_bytes(s, "d32as64", v, R.dec(v, 64, sign="-", group=(3, ",")), "bits=64 v=0x%X" % v)
    for i, kw in enumerate(COMBOS_HEX):
        for v in EDGE32 + [0xABCDEF, 0x10, 0xF, 0xA0B0C0D] + rvals32(rng, 20):
            want = R.hexf(v, kw.get("width", 8), kw.get("lower", False), kw.get("fill", "0"), kw.get("align"))
            judge_bytes(s, "hex_%d" % i, v, want, "%r v=0x%X" % (kw, v))
            typ = "x" if kw.get("lower") else "X"
            spec = R.py_spec(kw.get("width", 8), kw.get("fill", "0"), None, None, kw.get("align"), typ)
            if kw.get("fill", "0") != "\r":
                s.expect_true("hex_%d" % i, format(v, spec).encode() == want, "python format %r" % spec)
    for i, kw in enumerate(COMBOS_PER):
        for v in EDGE32 + [500, 12500, 12050, 150000, 1234567, 5000000] + rvals32(rng, 20):
            judge_bytes(s, "per_%02d" % i, v, per_ref(v, kw), "%r v=%d" % (kw, v))
    for i, kw in enumerate(COMBOS_PER64):
        for v in EDGE64 + rvals64(rng, 20):
            judge_bytes(s, "per64_%d" % i, v, per_ref(v, kw), "%r v=%d" % (kw, v))
    for i, kw in enumerate(COMBOS_MAN):
        for v in EDGE32 + [7, 10000, 12345678, 100050000, 100000000, 100001234, 99990000] + rvals32(rng, 25):
            judge_bytes(s, "man_%d" % i, v, man_ref(v, kw, 32), "%r v=%d" % (kw, v))
    for i, kw in enumerate(COMBOS_MAN64):
        for v in EDGE64 + [10**16, 10**16 + 10**12, 123456789012, 10**12, 10**8] + rvals64(rng, 25):
            judge_bytes(s, "man64_%d" % i, v, man_ref(v, kw, 64), "%r v=%d" % (kw, v))
    for i, kw in enumerate(COMBOS_GAUGE):
        cells = kw.get("cells", 20)
        for v in list(range(0, cells + 2)) + [cells + 100, 2**31, M32] + rvals32(rng, 5):
            want = R.gauge(v, cells, kw.get("glyph", "l"), kw.get("on", 7), kw.get("off", 4))
            judge_bytes(s, "gauge_%d" % i, v, want, "%r n=%d" % (kw, v))
    return s.report()


# ---------------------------------------------------------------------------------------------
# 2. numfmt.dp — S3 8.1 표 + 무작위 2만 개
# ---------------------------------------------------------------------------------------------

DP_NAMES = ("dec16", "decfw48", "hex12", "dig2", "gauge40", "per8", "per8p", "per8t", "man18", "man18c", "dec20", "man18w")
NAMES = [b"GALAXY_BURST", b"", b"ABCDEFGHIJKLMNOP", "마린키우기".encode(), b"a\0b", b"Seed\0\0\0\0x", b"P7name", b"P8name"]


def suite_dp(n_random):
    s = Suite("t_numfmt numfmt.dp", init_mem={0x6D0FDC + 36 * p: nm.ljust(36, b"\0")[:36] for p, nm in enumerate(NAMES)})

    @s.case("dp")
    def _(t):
        x, h = t.var("x"), t.var("h")
        w = Int64.wrap(x, h)
        objs = {
            "dec16": dp.dec16(x), "decfw48": dp.decfw48(x), "hex12": dp.hex12(x), "dig2": dp.dig2(x),
            "gauge40": dp.gauge40(x), "per8": dp.per8(x), "per8p": dp.per8(x, permil=True),
            "per8t": dp.per8(x, permil=True, tbl=True), "man18": dp.man18(x), "man18c": dp.man18(x, color=True),
            "dec20": dp.dec20(w), "man18w": dp.man18(w, color=True),
        }  # fmt: skip
        for k in DP_NAMES:
            t.out(k, objs[k].fmt()._value)

    @s.case("name")
    def _(t):
        t.out("p", dp.name20(t.var("x")).fmt()._value)

    for p in range(7):

        @s.case("namec%d" % p)
        def _(t, p=p):
            t.out("p", dp.name20(p).fmt()._value)

    s.build()
    m = s.machine
    refs = {
        "dec16": R.dp_dec16, "decfw48": R.dp_decfw48, "hex12": R.dp_hex12, "dig2": R.dp_dig2, "gauge40": R.gauge,
        "per8": R.dp_per8, "per8p": lambda v: R.dp_per8(v, permil=True), "per8t": lambda v: R.dp_per8(v, True, True),
        "man18": lambda v: R.man18(v, False), "man18c": lambda v: R.man18(v, True),
    }  # fmt: skip

    def run(x, h=0, table=None):
        r = s.run("dp", {"x": x, "h": h})
        if r.error:
            return s.expect_true("dp", False, "x=0x%X" % x, r.error)
        v64 = x | (h << 32)
        for k in DP_NAMES:
            got = cstr(m, r[k])
            if k == "dec20":
                want = R.dp_dec20(v64)
            elif k == "man18w":
                want = R.man18(v64, True)
            else:
                want = refs[k](x)
            if table is not None and k in table:
                s.expect_true("dp", got == table[k], "S3 8.1 %s 0x%X" % (k, v64), "%s != %s" % (got.hex(" "), table[k].hex(" ")))
            s.expect_true("dp", got == want, "%s 0x%X" % (k, v64), "%s != %s" % (got.hex(" "), want.hex(" ")))

    for name, rows in R.S3_EXPECT.items():  # S3 8.1 표
        if name == "name20":
            continue
        key = {"man18_on": "man18c", "man18_off": "man18", "per8_permil": "per8p"}.get(name, name)
        for v, e in rows:
            want = R.expect_bytes(e)
            if key == "dec20" or (key == "man18c" and v > M32):
                run(v & M32, v >> 32, {"dec20" if key == "dec20" else "man18w": want})
            else:
                run(v, 0, {key: want})
    rng = random.Random(8)
    for v in EDGE32:
        run(v, rng.getrandbits(32))
    for v in EDGE64:
        run(v & M32, v >> 32)
    for _ in range(n_random):
        run(rvals32(rng, 1)[0], rng.getrandbits(32) if rng.random() < 0.5 else 0)
    # 이름 (S3 8.1 + 0 바이트·16B·한글, 7 이상은 쓰지 않음)
    s.expect_true("name", R.dp_name20(b"GALAXY_BURST", 0) == R.expect_bytes(R.S3_EXPECT["name20"][0][1]), "S3 8.1 name20")
    for p in list(range(10)) + [M32]:
        r = s.run("name", {"x": p}, fresh=True)
        got = cstr(m, r["p"], 24) if not r.error else None
        want = R.dp_name20(NAMES[p], p) if p <= 6 else b""
        s.expect_true("name", got == want, "name20 p=%d" % p, "%r != %r %s" % (got, want, r.error))
    for p in range(7):
        r = s.run("namec%d" % p, {}, fresh=True)
        got = cstr(m, r["p"], 24)
        s.expect_true("namec%d" % p, got == R.dp_name20(NAMES[p], p), "name20 상수 p=%d" % p, repr(got))
    return s.report()


# ---------------------------------------------------------------------------------------------
# 3. fmt() 훅·입력 종류·서식 지정자·직접 쓰기·셀 (문자열 결과 → 한 빌드)
# ---------------------------------------------------------------------------------------------

DST_A = 0x00600001  # 단어째 쓰기 (시작 위치 1 과 정렬이 맞음)
DST_B = 0x00600102  # 정렬이 안 맞음 → 바이트 복사
DST_C = 0x00600200  # 변수 주소
DST_D = 0x00600300  # 상수 값
DST_E = 0x00600400  # 가변 길이
SENT = bytes(range(0xA0, 0xE0))  # 앞뒤 보존 확인용 무늬


def scan_ref(cells, signed, layout="eudplib"):
    """f_scan_dec_cells 규칙 (앞에서부터: 숫자 이어 붙임, ',' 건너뜀, '-' 는 부호 켜고 0, 그 밖은 0·부호 끔)."""
    v, neg = 0, False
    for i in range(0, len(cells), 4):
        c = cells[i : i + 4]
        ch = c[1] if layout == "eudplib" else c[3]
        rest = (c[2], c[3]) if layout == "eudplib" else (c[1], c[2])
        if rest == (D, D) and 0x30 <= ch <= 0x39:
            v = (v * 10 + ch - 0x30) & M32
        elif rest == (D, D) and ch == 0x2C:
            pass
        elif signed and rest == (D, D) and ch == 0x2D:
            v, neg = 0, True
        else:
            v, neg = 0, False
    return (-v) & M32 if neg else v


def cells_of(text, layout="eudplib", color=0x02):
    out = b""
    for ch in text:
        b = ch.encode()
        if len(b) == 1:
            out += bytes([color]) + (b + b"\r\r" if layout == "eudplib" else b"\r\r" + b)
        else:
            out += bytes([color]) + b.ljust(3, b"\r")
    return out


SCAN_TEXTS = ["x12,345", "-12", "1-2", "12-", "12 ", "", "4294967296", "99999999999", ",,,5", "１２", "--7", "7,-,8",
              "000123", "-0", "-4294967295", "2147483648", "1\r2"]  # fmt: skip


def suite_hooks():
    rng = random.Random(21)
    s = Suite("t_numfmt fmt 훅·지정자·직접 쓰기·셀", init_mem={DST_A - 1: SENT, DST_B - 2: SENT})
    bufs = {k: Db(512) for k in ("sp", "db", "two", "kinds", "spec", "spec2", "specoff")}
    holder = {}

    def get_sb():  # StringBuffer 는 LoadMap 뒤(빌드 안)에서 만든다
        if "sb" not in holder:
            holder["sb"] = StringBuffer(512)
        return holder["sb"]

    cellbuf = Db(128)
    cellvar = Db(128)
    scanbuf = Db(128)

    @s.case("sprintf")
    def _(t):
        x = t.var("x")
        t.watch("buf", bufs["sp"])
        f_sprintf(bufs["sp"], "A{}B{}C{}D", Dec(x, width=5, fill="0"), Hex(x), Man(x, colors="dps", after=4))

    @s.case("dbstr")
    def _(t):
        x = t.var("x")
        t.watch("buf", bufs["db"])
        f_dbstr_print(bufs["db"], "[", Dec(x, sign="-"), "|", Per(x), "|", Gauge(x, cells=4), "|", dp.dec16(x), "]")

    @s.case("two")
    def _(t):
        x, y = t.var("x"), t.var("y")
        a = Dec(x).fmt()  # epScript 처럼 인자를 먼저 계산
        b = Dec(y, sign="+-").fmt()
        t.watch("buf", bufs["two"])
        f_dbstr_print(bufs["two"], a, " ", b)

    @s.case("sb")
    def _(t):
        x = t.var("x")
        sb = get_sb()
        t.watch("sb", GetMapStringAddr(sb.StringIndex))
        sb.printf("HP {} / {}", Dec(x, width=5, fill="0"), Dec(x, group=True))

    @s.case("sbprint")
    def _(t):
        x = t.var("x")
        sb = get_sb()
        t.watch("sb", GetMapStringAddr(sb.StringIndex))
        sb.print("[", Hex(x, width=0), "|", dp.man18(x), "]")

    @s.case("printall")
    def _(t):
        x = t.var("x")
        t.watch("sb", GetMapStringAddr(GetGlobalStringBuffer().StringIndex))
        f_printAll("MP {} {}", Dec(x, width=5, fill="0"), Dec(x, fullwidth=True))

    lv = EUDLightVariable()
    arr = Int64Array(4)

    @s.case("kinds")
    def _(t):
        x, h = t.var("x"), t.var("h")
        SeqCompute([(EPD(lv.getValueAddr()), SetTo, x)])
        arr[1] = Int64.wrap(x, h)
        t.watch("buf", bufs["kinds"])
        f_dbstr_print(bufs["kinds"], Dec(lv, sign="-"), "|", Dec(arr[1], group=True), "|", Dec(x, bits=64, sign="-"), "|",
                      Hex(bufs["kinds"]), "|", Dec("12800000000", group=True), "|", Dec(-5, sign="-"), "|", Dec(-5))  # fmt: skip

    numfmt.enable_format_spec()
    numfmt.enable_format_spec()  # 두 번 불러도 된다

    @s.case("spec")
    def _(t):
        x, h = t.var("x"), t.var("h")
        w = Int64.wrap(x, h)
        t.watch("buf", bufs["spec"])
        f_sprintf(bufs["spec"], "[{:05d}|{:+,d}|{: d}|{:08x}|{:4X}|{:w}|{:,}|{:*>7d}|{:x}|{}|{:,}|{:=+8d}|{:9}]",
                  x, x, x, x, x, x, x, x, x, w, w, x, x)  # fmt: skip

    @s.case("spec2")
    def _(t):
        t.watch("buf", bufs["spec2"])
        f_sprintf(bufs["spec2"], "{:05d}|{:+d}|{:,}|{}", 42, -5, 1234567, 7)

    @s.case("specoff")
    def _(t):
        x = t.var("x")
        numfmt.disable_format_spec()
        try:
            t.watch("buf", bufs["specoff"])
            f_sprintf(bufs["specoff"], "{:05d}|{}", x, x)  # 끄면 eudplib 그대로 (지정자 무시)
        finally:
            numfmt.enable_format_spec()

    @s.case("spec_left", expect_build_error=EudextError, expect_message="왼쪽")
    def _(t):
        f_sprintf(Db(16), "{:<5d}", t.var("x"))

    @s.case("spec_prec", expect_build_error=EudextError, expect_message="정밀도")
    def _(t):
        f_sprintf(Db(16), "{:.3d}", t.var("x"))

    @s.case("textfx", expect_build_error=EudextError, expect_message="fmt\\(\\)")
    def _(t):
        TextFX_FadeIn(Dec(t.var("x")), tag="numfmt_textfx")

    @s.case("fadein", expect_build_error=EudextError, expect_message="fmt\\(\\)")
    def _(t):
        StringBuffer(64).fadeIn(Dec(t.var("x")), tag="numfmt_fadein")

    @s.case("cpchar", expect_build_error=EudextError, expect_message="f_cpchar_print")
    def _(t):
        importlib.import_module("eudplib.string.texteffect").f_cpchar_print(Man(t.var("x")))

    @s.case("fmtok_textfx")
    def _(t):  # .fmt() 결과는 된다
        TextFX_FadeIn(Dec(t.var("x"), width=3).fmt(), tag="numfmt_textfx_ok")

    @s.case("to")
    def _(t):
        x, dv = t.var("x"), t.var("dv")
        t.out("cp0", f_getcurpl())
        t.out("na", numfmt.f_fmt_dec_to(DST_A, x, width=11, sign="-"))
        t.out("nb", numfmt.fmt_dec_to(DST_B, x, width=11, sign="-"))
        t.out("nc", numfmt.fmt_dec_to(dv, x, sign="+-", group=(3, ",")))
        t.out("nd", numfmt.fmt_dec_to(DST_D, 12345678, width=12, group=True))
        t.out("ne", numfmt.fmt_dec_to(DST_E, x))
        t.out("cp1", f_getcurpl())

    @s.case("cells")
    def _(t):
        x, ev = t.var("x"), t.var("ev")
        t.out("cp0", f_getcurpl())
        t.watch("cb", cellbuf)
        t.watch("cv", cellvar)
        t.out("n1", numfmt.f_fmt_dec_cells(EPD(cellbuf), x, color=0x1F, sign="-", group=(3, ",")))
        t.out("n2", numfmt.fmt_dec_cells(ev, x, layout="ctrig", width=12))
        t.out("n3", numfmt.fmt_dec_cells(EPD(cellbuf) + 20, 4321, color=3))
        t.out("n4", numfmt.fmt_dec_cells(ev + 20, 987, layout="ctrig"))
        t.out("r1", numfmt.f_scan_dec_cells(EPD(cellbuf), 14, signed=True))
        t.out("r2", numfmt.scan_dec_cells(ev, t.var("k"), layout="ctrig"))
        t.out("cp1", f_getcurpl())

    @s.case("scan")
    def _(t):
        t.watch("sc", scanbuf)
        n, e = t.var("n"), t.var("e")
        t.out("cp0", f_getcurpl())
        t.out("u", numfmt.f_scan_dec_cells(EPD(scanbuf), n))
        t.out("s", numfmt.f_scan_dec_cells(EPD(scanbuf), n, signed=True))
        t.out("uc", numfmt.f_scan_dec_cells(e, n, layout="ctrig"))
        t.out("sc2", numfmt.f_scan_dec_cells(e, n, signed=True, layout="ctrig"))
        t.out("cp1", f_getcurpl())

    try:
        s.build()
    finally:
        numfmt.disable_format_spec()
    m = s.machine
    for v in EDGE32 + rvals32(rng, 40):
        r = s.run("sprintf", {"x": v})
        want = b"A" + R.dec(v, width=5, fill="0") + b"B" + R.hexf(v) + b"C" + R.man(v, colors="dps", after=4) + b"D"
        got = cstr(m, m.addr("sprintf.buf"))
        s.expect_true("sprintf", not r.error and got == want, "v=%d" % v, "%r %r %s" % (got, want, r.error))
        r = s.run("dbstr", {"x": v})
        want = b"[" + R.dec(v, sign="-") + b"|" + R.per(v) + b"|" + R.gauge(v, 4) + b"|" + R.dp_dec16(v) + b"]"
        got = cstr(m, m.addr("dbstr.buf"))
        s.expect_true("dbstr", not r.error and got == want, "v=%d" % v, "%r %r %s" % (got, want, r.error))
        y = rng.getrandbits(32)
        r = s.run("two", {"x": v, "y": y})
        want = R.dec(v) + b" " + R.dec(y, sign="+-")
        s.expect_true("two", not r.error and cstr(m, m.addr("two.buf")) == want, "v=%d" % v, repr(r.error))
        # StringBuffer 는 항목마다 dword 경계까지 0x0D 를 채운다 → 0x0D 를 빼고 비교
        r = s.run("sb", {"x": v})
        want = b"HP " + R.dec(v, width=5, fill="0") + b" / " + R.dec(v, group=(3, ","))
        got = cstr(m, m.addr("sb.sb"), 600).replace(b"\r", b"")
        s.expect_true("sb", not r.error and got == want.replace(b"\r", b""), "v=%d" % v, "%r %r %s" % (got, want, r.error))
        r = s.run("sbprint", {"x": v})
        want = b"[" + R.hexf(v, 0) + b"|" + R.man18(v, False) + b"]"
        got = cstr(m, m.addr("sbprint.sb"), 600).replace(b"\r", b"")
        s.expect_true("sbprint", not r.error and got == want.replace(b"\r", b""), "v=%d" % v, "%r %r" % (got, want))
        r = s.run("printall", {"x": v})
        want = b"MP " + R.dec(v, width=5, fill="0") + b" " + R.dec(v, fullwidth=True)
        got = cstr(m, m.addr("printall.sb"), 600).replace(b"\r", b"")
        s.expect_true("printall", not r.error and got == want.replace(b"\r", b""), "v=%d" % v, "%r %r" % (got, want))
        h = rng.getrandbits(32)
        r = s.run("kinds", {"x": v, "h": h})
        want = b"|".join([R.dec(v, sign="-"), R.dec(v | (h << 32), 64, group=(3, ",")), R.dec(v, 64, sign="-"),
                          b"%08X" % m.addr("kinds.buf"), b"12,800,000,000", b"-5", b"4294967291"])  # fmt: skip
        got = cstr(m, m.addr("kinds.buf"))
        s.expect_true("kinds", not r.error and got == want, "v=%d" % v, "%r %r %s" % (got, want, r.error))
        r = s.run("spec", {"x": v, "h": h})
        w = v | (h << 32)
        sv = s32(v)
        want = ("[%s|%s|%s|%s|%s|" % (format(v, "05d"), format(sv, "+,d"), format(sv, " d"), format(v, "08x"),
                                      format(v, "4X"))).encode()  # fmt: skip
        want += R.dec(v, fullwidth=True, fill=" ") + ("|%s|%s|%08X|%d|%s|%s|%s]" % (
            format(v, ","), format(v, "*>7d"), v, w, format(w, ","), format(sv, "=+8d"), format(v, "9"))).encode()  # fmt: skip
        got = cstr(m, m.addr("spec.buf"), 400)
        s.expect_true("spec", not r.error and got == want, "v=%d" % v, "%r != %r %s" % (got, want, r.error))
        r = s.run("specoff", {"x": v})
        s.expect_true("specoff", cstr(m, m.addr("specoff.buf")) == ("%d|%d" % (v, v)).encode(), "v=%d" % v)
        # 직접 쓰기
        dv = DST_C + rng.randrange(4)
        m.write_bytes(DST_C - 8, SENT)
        m.write_bytes(DST_E - 8, SENT)
        r = s.run("to", {"x": v, "dv": dv})
        wa, wc, we = R.dec(v, width=11, sign="-"), R.dec(v, sign="+-", group=(3, ",")), R.dec(v)
        ok = (not r.error and m.read_bytes(DST_A, 11) == wa and r["na"] == 11 and m.read_bytes(DST_A - 1, 1) == SENT[:1]
              and m.read_bytes(DST_A + 11, 4) == SENT[12:16] and m.read_bytes(DST_B, 11) == wa and r["nb"] == 11
              and m.read_bytes(DST_B - 2, 2) == SENT[:2] and m.read_bytes(DST_B + 11, 4) == SENT[13:17]
              and m.read_bytes(dv, len(wc)) == wc and r["nc"] == len(wc) and m.read_bytes(DST_D, 12) == b"\r\r12,345,678"
              and r["nd"] == 12 and m.read_bytes(DST_E, len(we)) == we and r["ne"] == len(we)
              and m.read_bytes(DST_E - 8, 8) == SENT[:8] and r["cp0"] == r["cp1"])  # fmt: skip
        vals = {k: r.values.get(k) for k in ("na", "nb", "nc", "nd", "ne", "cp0", "cp1")}
        s.expect_true("to", ok, "v=%d" % v, "%r %s %s" % (vals, m.read_bytes(DST_A - 1, 16), r.error))
        # 셀
        cv_addr = m.addr("cells.cv")
        e = (cv_addr - EPD0) // 4
        r = s.run("cells", {"x": v, "ev": e & M32, "k": 12})
        want1 = R.dec(v, mode="eudplib", colors=0x1F, sign="-", group=(3, ",")).rjust(56, b"\r")
        want2 = R.dec(v, mode="ctrig", width=12)
        cb = m.read_bytes(m.addr("cells.cb"), 128)
        cvb = m.read_bytes(cv_addr, 128)
        ok = (not r.error and r["n1"] == 14 and cb[:56] == want1 and r["n2"] == 12 and cvb[:48] == want2
              and r["n3"] == 10 and cb[80:120] == R.dec(4321, mode="eudplib", colors=3).rjust(40, b"\r")
              and r["n4"] == 10 and cvb[80:120] == R.dec(987, mode="ctrig").rjust(40, b"\r")
              and r["r1"] == v and r["r2"] == scan_ref(cvb[:48], False, "ctrig") and r["cp0"] == r["cp1"])  # fmt: skip
        s.expect_true("cells", ok, "v=%d" % v, "%r %r %r %s" % (cb[:56], want1, r.values, r.error))
    # 손으로 만든 셀 읽기
    sc_addr = m.addr("scan.sc")
    e = (sc_addr - EPD0) // 4
    texts = SCAN_TEXTS + ["".join(rng.choice("0123456789,- x") for _ in range(rng.randrange(0, 14))) for _ in range(60)]
    for text in texts:
        for layout in ("eudplib", "ctrig"):
            cells = cells_of(text, layout)
            m.write_bytes(sc_addr, cells + bytes(128 - len(cells)))
            r = s.run("scan", {"n": len(text), "e": e & M32})
            if layout == "eudplib":
                ok = r["u"] == scan_ref(cells, False) and r["s"] == scan_ref(cells, True)
            else:
                ok = r["uc"] == scan_ref(cells, False, "ctrig") and r["sc2"] == scan_ref(cells, True, "ctrig")
            ok = ok and not r.error and r["cp0"] == r["cp1"]
            s.expect_true("scan", ok, "%r %s" % (text, layout), "%r %s" % (r.values, r.error))
    s.run("spec2", {})
    got = cstr(m, m.addr("spec2.buf"))
    s.expect_true("spec2", got == b"00042|-5|1,234,567|7", "상수 지정자", repr(got))
    r = s.run("fmtok_textfx", {"x": 5})
    s.expect_true("fmtok_textfx", r.error is None, ".fmt() 는 TextFX 에 넘길 수 있다", repr(r.error))
    s.expect_true("specoff", not numfmt.format_spec_enabled(), "빌드 뒤 지정자 끔")
    return s.report()


# ---------------------------------------------------------------------------------------------
# 4. epScript 예제·인게임 맵·euddraft 빌드
# ---------------------------------------------------------------------------------------------


def load_eps(name):
    """예제 eps 를 작업 폴더에 복사해 EPSLoader 로 불러온다(__epspy__ 가 작업 폴더에 생긴다)."""
    d = os.path.join(_common.WORK, "t_numfmt", "eps")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name + ".eps")
    shutil.copy2(os.path.join(EX, name + ".eps"), p)
    mname = name + "_eps"
    mod = types.ModuleType(mname)
    loader = EPSLoader(mname, p)
    mod.__loader__ = loader
    sys.modules[mname] = mod
    loader.exec_module(mod)
    return mod


def suite_eps(eps):
    s = Suite("t_numfmt epScript 예제")
    bufs = {k: Db(256) for k in ("dec_to", "hex_to", "man_to", "per_to", "two_to", "const_to", "write")}
    cells = Db(128)

    @s.case("dec_to")
    def _(t):
        t.watch("buf", bufs["dec_to"])
        eps.f_dec_to(bufs["dec_to"], t.var("x"))

    @s.case("hex_to")
    def _(t):
        t.watch("buf", bufs["hex_to"])
        eps.f_hex_to(bufs["hex_to"], t.var("x"))

    @s.case("man_to")
    def _(t):
        t.watch("buf", bufs["man_to"])
        eps.f_man_to(bufs["man_to"], t.var("x"), t.var("h"))

    @s.case("per_to")
    def _(t):
        t.watch("buf", bufs["per_to"])
        eps.f_per_to(bufs["per_to"], t.var("x"))

    @s.case("two_to")
    def _(t):
        t.watch("buf", bufs["two_to"])
        eps.f_two_to(bufs["two_to"], t.var("x"), t.var("y"))

    @s.case("const_to")
    def _(t):
        t.watch("buf", bufs["const_to"])
        eps.mp << t.var("x")
        eps.f_const_to(bufs["const_to"])

    @s.case("cells")
    def _(t):
        t.out("r", eps.f_cells_roundtrip(cells, t.var("x")))

    @s.case("write")
    def _(t):
        t.watch("buf", bufs["write"])
        t.out("n", eps.f_write_to(bufs["write"], t.var("x")))

    @s.case("main")
    def _(t):
        t.watch("gsb", GetMapStringAddr(GetGlobalStringBuffer().StringIndex))
        eps.mp << t.var("x")
        eps.afterTriggerExec()
        t.out("mp", eps.mp)

    s.build()
    m = s.machine
    rng = random.Random(4)
    for v in EDGE32 + rvals32(rng, 30):
        h, y = rng.getrandbits(32), rng.getrandbits(32)
        checks = (
            ("dec_to", b"[" + R.dec(v, width=5, fill="0") + b"|" + R.dec(v, sign="-") + b"|" + R.dec(v, group=(3, ",")) + b"|"
             + R.dec(v, fullwidth=True) + b"]"),
            ("hex_to", R.hexf(v) + b"/" + R.hexf(v, 0, True)),
            ("man_to", R.man(v | (h << 32), 64) + b"|" + R.man18(v | (h << 32), True)),
            ("per_to", R.per(v, max_=100000) + b"|" + R.dp_per8(v) + b"|" + R.gauge(v, 5)),
            ("two_to", R.dec(v) + b" " + R.dec(y, sign="+-")),
            ("const_to", R.dec(v, width=5, fill="0")),
        )  # fmt: skip
        for name, want in checks:
            inputs = {"x": v, "h": h} if name == "man_to" else {"x": v, "y": y} if name == "two_to" else {"x": v}
            r = s.run(name, inputs)
            got = cstr(m, m.addr(name + ".buf"), 400)
            s.expect_true(name, r.error is None and got == want, "v=%d" % v, "%r != %r %s" % (got, want, r.error))
        r = s.run("cells", {"x": v})
        s.expect_true("cells", r.error is None and r["r"] == v, "v=%d" % v, repr(r.values))
        r = s.run("write", {"x": v})
        want = R.dec(v, sign="-")
        got = m.read_bytes(m.addr("write.buf"), len(want))
        s.expect_true("write", r.error is None and r["n"] == len(want) and got == want, "v=%d" % v, repr((r.values, got)))
    for v in (0, 35, 99999, 4294967288):
        r = s.run("main", {"x": v})
        mp = (v + 7) & M32
        got = cstr(m, m.addr("main.gsb"), 600).replace(b"\r", b"")
        want = "골드 12,800,000,000 = ".encode() + R.man(12800000000, 64, colors="dps", after=4).replace(b"\r", b"")
        if mp < 7:  # 넘쳐서 0~6 이면 출력이 없다 → 버퍼는 앞 줄 그대로
            want = got
        s.expect_true("main", r.error is None and r["mp"] == mp and got == want, "main v=%d" % v, "%r %r %s" % (got, want, r.error))
    return s.report()


def eps_checks(ck):
    for name in ("numfmt_example", "numfmt_ingame"):
        with open(os.path.join(EX, name + ".eps"), encoding="utf-8") as f:
            src = f.read()
        out, nerr = _compat.eps_compile(name + ".eps", src)
        ck.eq("eps 오류 수 " + name, nerr, 0)
        ck.true("eps 번역 " + name, out is not None)
        if name != "numfmt_example" or not out:
            continue
        for needle in (
            "from eudext import numfmt as nf",
            'f_printAll("MP {}", nf.Dec(mp, width=5, fill="0"))',
            'nf.Dec(gold, group=FlattenList([3, ","]))',
            'nf.Man(gold, colors="dps", after=0x04)',
            "nf.dp.man18(x, color=True)",
            "nf.f_fmt_dec_cells(EPD(cells), v, color=0x1F",
            "nf.f_scan_dec_cells(EPD(cells), n, signed=True)",
            "nf.f_fmt_dec_to(dst, v, sign=",
            "nf.Dec(a).fmt()",
        ):
            ck.true("eps 번역에 %s" % needle, needle in out or needle.replace('"', "'") in out, needle)
    # DESIGN 0.3 의 epScript 예 그대로 (번역 + 에뮬레이터 실행)
    src = (
        "import eudext.i64 as i64;\nimport eudext.numfmt as nf;\n"
        "const hp = i64.Int64(0x100000000);\nvar mp;\n"
        "function afterTriggerExec() {\n    hp.v += 5;\n    if (hp >= 0x100000005) {\n"
        '        printAll("HP {}", hp.fmt());\n        printAll("MP {}", nf.Dec(mp, width=5, fill="0"));\n    }\n}\n'
    )
    out, nerr = _compat.eps_compile("design03.eps", src)
    ck.true("DESIGN 0.3 예 번역", out is not None and nerr == 0)
    ck.true("DESIGN 0.3 예 번역 모양", out is not None and "nf.Dec(mp, width=5, fill=" in out, str(out))
    if out:
        ns = {"__name__": "design03_eps"}
        exec(compile(out, "design03.eps.py", "exec"), ns)  # noqa: S102 — 시험용 번역문
        LoadMap(BASE_MAP)
        CompressPayload(True)
        prog = emu.Program(ns["afterTriggerExec"])
        prog.watch("gsb", GetMapStringAddr(GetGlobalStringBuffer().StringIndex))
        prog.watch("mp", ns["mp"])
        m = prog.build()
        m.cycle()
        m.set_var("mp", 42)
        m.cycle(2)
        got = cstr(m, m.addr("gsb"), 300).replace(b"\r", b"")
        ck.eq("DESIGN 0.3 예 실행", got, b"MP 00042")


def ingame_emulate(ck):
    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_numfmt_ingame")
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, "numfmt_ingame.eps"), os.path.join(work, "numfmt_ingame.eps"))
    LoadMap(BASE_MAP)
    CompressPayload(True)
    mod = build._load_plugin(os.path.join(work, "numfmt_ingame.eps"), {})
    prog = emu.Program(mod.afterTriggerExec)
    names = ("frame", "okCount", "total", "lastBad", "cellsOk")
    for n in names:
        prog.watch(n, getattr(mod, n))
    m = prog.build()
    err = None
    steps = []
    try:
        for _ in range(130):
            m.cycle()
            steps.append(m.last_steps())
    except emu.EmuError as e:
        err = str(e)
    got = {n: m.var(n) for n in names}
    print("  인게임 맵 에뮬레이션: %r, 사이클 최대 실행 %d" % (got, max(steps) if steps else -1))
    ck.eq("ingame emu 오류", err, None)
    ck.eq("ingame emu 값", got, {"frame": 130, "okCount": 23, "total": 23, "lastBad": 0, "cellsOk": 1})


def euddraft_builds(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    for name in ("numfmt_example", "numfmt_ingame"):
        work = os.path.join(_common.WORK, "t_numfmt_build_" + name)
        eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
        r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
        print("  " + r.summary())
        ck.true("euddraft " + name, r.ok, r.log[-2000:])
        ck.true("euddraft freeze off " + name, not r.freeze)
        ck.true("eps compiled " + name, '[epScript] Compiling "%s.eps"' % name in r.log, r.log[-1000:])


def bad_builds(ck):
    """빌드 오류여야 하는 epScript (모든 에뮬레이터 시험 뒤에 — 실패한 빌드가 뒤 빌드에 영향을 주지 않게)."""
    src = (
        "import eudext.numfmt as nf;\nimport eudext.i64 as i64;\n"
        "var mp;\n"
        "function bvar() { var d = nf.Dec(mp); d += 1; }\n"
        "function btextfx() { TextFX_FadeIn(nf.Dec(mp)); }\n"
        "function bfadein() { const sb = StringBuffer(64); sb.fadeIn(nf.Gauge(mp)); }\n"
        'function bleft() { nf.enable_format_spec(); printAll("{:<5d}", mp); }\n'
        "function bhex64() { const x = nf.Hex(i64.Int64(5)); }\n"
        'function bopt() { printAll("{}", nf.Dec(mp, fill="ab")); }\n'
    )
    out, nerr = _compat.eps_compile("bad_numfmt.eps", src)
    ck.true("bad eps 번역", out is not None and nerr == 0, str(nerr))
    if not out:
        return
    ns = {"__name__": "bad_numfmt_eps"}
    exec(compile(out, "bad_numfmt.eps.py", "exec"), ns)  # noqa: S102
    want = {"f_bvar": "", "f_btextfx": "fmt()", "f_bfadein": "fmt()", "f_bleft": "왼쪽", "f_bhex64": "2차", "f_bopt": "한 개"}
    try:
        for fn, needle in want.items():
            LoadMap(BASE_MAP)
            CompressPayload(True)
            try:
                emu.Program(lambda fn=fn: ns[fn]()).build()
                ck.true("%s 빌드 오류" % fn, False, "빌드가 됐다")
            except Exception as e:  # noqa: BLE001
                ck.true("%s 빌드 오류" % fn, needle in str(e), repr(e))
    finally:
        numfmt.disable_format_spec()


# ---------------------------------------------------------------------------------------------
# 5. 파이썬 쪽 판정
# ---------------------------------------------------------------------------------------------


def python_checks(ck):
    with _compat.isolated_scope():  # 트리거를 내는 호출이 있으므로 버려지는 트리거 범위 안에서
        _python_checks(ck)


def _python_checks(ck):
    v = EUDVariable()
    rng = random.Random(9)
    # 상수 서식 (트리거 0) = 참조
    for x in EDGE32 + rvals32(rng, 40):
        for kw in ({}, dict(width=7, fill="0", sign="-"), dict(group=True, sign="+-"), dict(fullwidth=True, colors=5)):
            ck.eq("상수 Dec %r %d" % (kw, x), Dec(x, bits=32, **kw).fmt(), R.dec(x, 32, **ref_kw(kw)))
        ck.eq("상수 Hex %d" % x, Hex(x).fmt(), R.hexf(x))
        ck.eq("상수 Man %d" % x, Man(x, colors="dps", after=4).fmt(), R.man(x, colors="dps", after=4))
        ck.eq("상수 Per %d" % x, Per(x, frac=2).fmt(), R.per(x, frac=2))
        ck.eq("상수 Gauge %d" % x, Gauge(x, cells=8).fmt(), R.gauge(x, 8))
        ck.eq("상수 dp.dec16 %d" % x, dp.dec16(x).fmt(), R.dp_dec16(x))
    for x in EDGE64 + rvals64(rng, 20):
        ck.eq("상수 64 %d" % x, Dec(x, bits=64, group=True).fmt(), R.dec(x, 64, group=(3, ",")))
        ck.eq("상수 64 부호 %d" % x, Dec(x, bits=64, sign="-").fmt(), R.dec(x, 64, sign="-"))
        ck.true("Int64(상수) 는 실행 값 %d" % x, Dec(Int64(x)).const_bytes() is None)
        ck.eq("상수 dec20 %d" % x, dp.dec20(x).fmt(), R.dp_dec20(x))
        ck.eq("상수 man18 %d" % x, dp.man18(x, color=True).fmt(), R.man18(x, True))
    ck.eq("상수 음수 자동 64", Dec(-(1 << 40), sign="-").fmt(), b"-1099511627776")
    ck.eq("상수 문자열", Dec("18446744073709551615").fmt(), b"18446744073709551615")
    ck.eq("상수 음수 32 부호 없음", Dec(-5).fmt(), b"4294967291")
    ck.eq("상수 const_bytes", Dec(42, width=4).const_bytes(), b"\r\r42")
    # 계획 흉내 = 참조 (조합 수천 개 — 트리거 생성이 쓰는 계획 자체를 넓게 확인)
    n = bad = 0
    for width, fill, sign, sp, group, align, md, cut in itertools.product(
        (0, 1, 3, 5, 8, 11, 14), ("\r", "0", " "), (None, "-", "+-", " -"), (False, True), (None, (3, ",")),
        (None, ">", "="), (None, 3), (0, 2)):  # fmt: skip
        if sp and sign is None:
            continue
        kw = dict(width=width, fill=fill, sign=sign, sign_space=sp, group=group, align=align, max_digits=md, cut_low=cut)
        plan = Dec(0, bits=32, **kw)._plan()
        for x in (0, 7, 12045, 999999, 2**31, M32, 4294967291, rng.getrandbits(32)):
            n += 1
            bad += plan.simulate(x) != R.dec(x, 32, **kw)
    ck.eq("계획 흉내 = 참조 (%d)" % n, bad, 0)
    n = bad = 0
    for kw in COMBOS64:
        plan = Dec(0, bits=64, **kw)._plan()
        for x in EDGE64:
            n += 1
            bad += plan.simulate(x) != R.dec(x, 64, **ref_kw(kw))
    ck.eq("64비트 계획 흉내 (%d)" % n, bad, 0)
    # S3 8.1 (상수 경로)
    table = {
        "dec16": dp.dec16, "decfw48": dp.decfw48, "hex12": dp.hex12, "dec20": dp.dec20,
        "man18_on": lambda x: dp.man18(x, color=True), "man18_off": dp.man18, "per8": dp.per8,
        "per8_permil": lambda x: dp.per8(x, permil=True), "dig2": dp.dig2, "gauge40": dp.gauge40,
    }  # fmt: skip
    for name, rows in R.S3_EXPECT.items():
        if name in table:
            for x, e in rows:
                ck.eq("S3 8.1 %s %r" % (name, x), table[name](x).fmt(), R.expect_bytes(e))
    # 길이 정보
    for label, got, want in (
        ("max_len Dec", Dec(v).max_len, 10), ("max_len Dec 부호", Dec(v, sign="-", group=True).max_len, 14),
        ("fixed_len Dec", Dec(v).fixed_len, None), ("fixed_len dec16", dp.dec16(v).fixed_len, 16),
        ("fixed_len decfw48", dp.decfw48(v).fixed_len, 48), ("fixed_len dec20", dp.dec20(v).fixed_len, 20),
        ("fixed_len man18", dp.man18(v).fixed_len, 18), ("max_len Man", Man(v).max_len, 18),
        ("fixed_len Man", Man(v).fixed_len, None), ("fixed_len per8", dp.per8(v).fixed_len, 8),
        ("fixed_len gauge40", dp.gauge40(v).fixed_len, 40), ("fixed_len name20", dp.name20(v).fixed_len, 20),
        ("max_len 64", Dec(Int64.wrap(v, v), sign="-", group=True).max_len, 26),
        ("const_bytes 변수", Dec(v).const_bytes(), None),
        ("max_len 전각", Dec(v, fullwidth=True).max_len, 40), ("fixed_len hex12", dp.hex12(v).fixed_len, 12),
    ):  # fmt: skip
        ck.eq(label, got, want)
    # 실수 막기
    d = Dec(v)
    ck.raises("format", EudextError, format, d, "")
    ck.raises("f-string", EudextError, lambda: f"{d}")
    ck.raises("bool", EudextError, bool, d)
    ck.raises("_value", EudextError, getattr, d, "_value")
    ck.raises("iter", TypeError, list, d)
    ck.true("repr 안내", "const" in repr(d) and "fmt" in repr(d))
    ck.true("dont_flatten", getattr(d, "dont_flatten", False))
    ck.true("dp repr", "DisplayPrint" in repr(dp))
    # 옵션 오류
    bad_opts = [
        dict(width=-1), dict(width=200), dict(width="5"), dict(fill="ab"), dict(fill=""), dict(fill=5), dict(sign="x"),
        dict(sign_space=True), dict(sign_space=1, sign="-"), dict(max_digits=0), dict(max_digits=11), dict(cut_low=11),
        dict(cut_low=-1), dict(group=(3,)), dict(group=(0, ",")), dict(group=(3, ",,")), dict(group=5), dict(colors=[]),
        dict(colors=256), dict(colors=(1, "a")), dict(glyphs="012"), dict(glyphs=["0"] * 9 + ["12345"]), dict(align="<"),
        dict(align="^"), dict(bits=16), dict(fullwidth=1), dict(glyphs=MIX4, colors=1), dict(_mode="cell"),
        dict(glyphs=["\r"] * 10),
    ]  # fmt: skip
    for kw in bad_opts:
        ck.raises("옵션 %r" % (kw,), EudextError, Dec, v, **kw)
    for label, fn in (
        ("Dec bool", lambda: Dec(True)), ("Dec None", lambda: Dec(None)), ("Dec float", lambda: Dec(1.5)),
        ("Dec 범위", lambda: Dec(1 << 64)), ("Dec 32 범위", lambda: Dec(1 << 40, bits=32)),
        ("Dec 문자열", lambda: Dec("12a")), ("Dec 조건", lambda: Dec(v.Exactly(1))),
        ("Dec Int64 bits32", lambda: Dec(Int64.wrap(v, v), bits=32)), ("Hex Int64", lambda: Hex(Int64(5))),
        ("Hex sign", lambda: numfmt._make_spec("hex", 32, sign="-")), ("Hex lower", lambda: Hex(v, lower=1)),
        ("Per scale", lambda: Per(v, scale=300)), ("Per scale1", lambda: Per(v, scale=1)),
        ("Per frac", lambda: Per(v, scale=100, frac=3)), ("Per int_min", lambda: Per(v, int_min=0)),
        ("Per scale 큼", lambda: Per(v, scale=10**10)), ("Per max", lambda: Per(v, max=1 << 32)),
        ("Man top", lambda: Man(v, top=3)), ("Man colors", lambda: Man(v, colors="red")),
        ("Man units", lambda: Man(v, units="만")), ("Man units64", lambda: Man(Int64.wrap(v, v), units="만억조")),
        ("Man pair", lambda: Man(v, colors=[(1, 2, 3)])), ("Man fixed", lambda: Man(v, fixed=1)),
        ("Gauge cells", lambda: Gauge(v, cells=0)), ("Gauge cells 큼", lambda: Gauge(v, cells=61)),
        ("Gauge glyph", lambda: Gauge(v, glyph="ab")), ("Gauge glyph4", lambda: Gauge(v, glyph="🄌")),
        ("Gauge on", lambda: Gauge(v, on=256)), ("name20 상수", lambda: dp.name20(7)),
        ("man18 color", lambda: dp.man18(v, color=1)), ("per8 permil", lambda: dp.per8(v, permil=1)),
        ("cells layout", lambda: numfmt.f_fmt_dec_cells(0, v, layout="x")),
        ("cells color", lambda: numfmt.f_fmt_dec_cells(0, v, color=0)),
        ("scan layout", lambda: numfmt.f_scan_dec_cells(0, 4, layout="x")),
        ("scan signed", lambda: numfmt.f_scan_dec_cells(0, 4, signed=1)),
        ("glyph64", lambda: Dec(Int64.wrap(v, v), glyphs=CJK).fmt()),
        ("prefix 가변", lambda: numfmt._make_spec("dec", 32, prefix=b"\r")),
    ):  # fmt: skip
        ck.raises(label, EudextError, fn)
    # 서식 지정자 해석
    P = numfmt._parse_spec
    for spec in ("", "x", "X", "s", "n", "t", "c", "5s"):
        ck.eq("spec %r 는 eudplib 몫" % spec, P(spec), None)
    ck.eq("spec 05d", P("05d"), ("dec", {"width": 5, "fill": "0", "align": "="}))
    ck.eq("spec +,d", P("+,d"), ("dec", {"width": 0, "fill": " ", "sign": "+-", "group": (3, ",")}))
    ck.eq("spec 08x", P("08x"), ("hex", {"width": 8, "fill": "0", "align": "=", "lower": True}))
    ck.eq("spec w", P("w"), ("dec", {"width": 0, "fill": " ", "fullwidth": True}))
    ck.eq("spec *>7", P("*>7"), ("dec", {"width": 7, "fill": "*", "align": ">"}))
    for bad in ("<5d", "^5d", ".2d", "#x", "z5d", "+x", "_x"):
        ck.raises("spec %r" % bad, EudextError, P, bad)
    ck.true("hook 끔 상태", not numfmt.format_spec_enabled())
    numfmt.enable_format_spec()
    ck.true("hook 켬", numfmt.format_spec_enabled())
    ck.true("hook 변수 d", isinstance(numfmt._format_hook(v, "05d"), Dec))
    ck.true("hook 변수 x", isinstance(numfmt._format_hook(v, "08x"), Hex))
    ck.eq("hook 변수 빈", numfmt._format_hook(v, ""), None)
    ck.eq("hook Db", numfmt._format_hook(Db(4), "5"), None)
    ck.eq("hook 문자열", numfmt._format_hook("abc", "5"), None)
    ck.eq("hook bool", numfmt._format_hook(True, "5"), None)
    ck.true("hook Int64 빈", isinstance(numfmt._format_hook(Int64(5), ""), Dec))
    numfmt.disable_format_spec()
    numfmt.disable_format_spec()
    ck.true("hook 끔", not numfmt.format_spec_enabled())
    fmtprint = importlib.import_module("eudplib.string.fmtprint")
    ck.true("hook 되돌림", not hasattr(fmtprint._EUDFormatter.__dict__["eudformat_field"], "_eudext_orig"))
    # 별칭·__all__
    for a, b in (("fmt_dec_to", "f_fmt_dec_to"), ("fmt_dec_cells", "f_fmt_dec_cells"), ("scan_dec_cells", "f_scan_dec_cells"),
                 ("enable_format_spec", "f_enable_format_spec"), ("disable_format_spec", "f_disable_format_spec"),
                 ("format_spec_enabled", "f_format_spec_enabled")):  # fmt: skip
        ck.true("별칭 %s" % a, getattr(numfmt, a) is getattr(numfmt, b))
    ck.eq("__all__ 중복", sorted(numfmt.__all__), sorted(set(numfmt.__all__)))
    for name in numfmt.__all__:
        ck.true("__all__ %s" % name, hasattr(numfmt, name))
    for name in ("dec16", "decfw48", "hex12", "dec20", "name20", "man18", "per8", "dig2", "gauge40"):
        ck.true("dp.%s" % name, callable(getattr(dp, name)) and bool(getattr(dp, name).__doc__))
    # 3.12 문서화
    for obj in (Dec, Hex, Man, Per, Gauge, numfmt.f_fmt_dec_to, numfmt.f_fmt_dec_cells, numfmt.f_scan_dec_cells,
                numfmt.f_enable_format_spec):  # fmt: skip
        doc = obj.__doc__ or ""
        ck.true("docstring %s" % obj.__name__, all(k in doc for k in ("인자", "반환", "비용", "CP", "로컬", "epScript", "출처")))
    # 비공개 API 는 _compat 에서만 (3.9)
    with open(numfmt.__file__, encoding="utf-8") as f:
        text = f.read()
    ck.true("_compat 밖 비공개 API 없음", "from eudplib." not in text and "import eudplib." not in text)
    ck.true("P1 마린 칸 안 씀", "0x58A364" not in text)
    ck.true("_WP5_REQUIRED", _compat._WP5_REQUIRED == (("eudplib.string.fmtprint", "_EUDFormatter"),))


# ---------------------------------------------------------------------------------------------
# 비용 측정 항목 (tools/cost.py)
# ---------------------------------------------------------------------------------------------

T32 = {"body": 60, "exec": 80}  # 3.8: 32비트 10진 고정 폭 본문 ≤ 60, 실행 ≤ 80
T64 = {"body": 620, "exec": 450}  # 3.8: 64비트 10진 본문 ≤ 620, 실행 ≤ 450
X32 = [{"x": 0}, {"x": 5}, {"x": 12345}, {"x": 1234567890}, {"x": M32}, {"x": 0x80000000}]
X64 = [{"x": 5, "h": 0}, {"x": 0xFAF08000, "h": 2}, {"x": M32, "h": M32}, {"x": 0, "h": 0x80000000}]


def _fmt(make, bits=32):
    def build(t):
        x, h = t.var("x"), t.var("h")
        v = x if bits == 32 else Int64.wrap(x, h)
        make(v).fmt()

    return build


def _prep(fn):
    """비용 측정 전에 EUDFunc 본문을 만들어 둔다(호출 자리 수에 본문이 섞이지 않게). 실패하면 빈 목록."""
    try:
        with _compat.isolated_scope():
            out = fn()
        for f in out:
            f.size()
        return out
    except Exception:  # noqa: BLE001 — 비용 표는 시험 실패와 따로
        return []


def _tail_of(make, bits=32):
    obj = make(EUDVariable() if bits == 32 else Int64.wrap(EUDVariable(), EUDVariable()))
    f, _plan, body = numfmt._tail(obj._spec)
    return f, body


def _cc(name, make, bits=32, target=None, note=""):
    """본문 칸 = 배치별 공용 본문(같은 본문이 여러 줄에 나온다), 꼬리(옵션마다 1벌) 크기는 비고에."""
    pair = _prep(lambda: list(_tail_of(make, bits)))
    funcs = pair[1:]
    tail = "꼬리 %d" % pair[0].size() if pair else "꼬리 ?"
    note = tail + (", " + note if note else "")
    return CostCase(name, _fmt(make, bits), X32 if bits == 32 else X64, funcs=funcs, target=target, note=note)


def _man_funcs(bits, **kw):
    def get():
        ms = Man(EUDVariable() if bits == 32 else Int64.wrap(EUDVariable(), EUDVariable()), **kw)._ms
        return [numfmt._man_front32() if bits == 32 else numfmt._man_front64(), numfmt._man_tail(ms)]

    return _prep(get)


def _gauge_funcs():
    return _prep(lambda: [Gauge(EUDVariable())._tail()])


def _cells_funcs(**kw):
    return _prep(lambda: list(_tail_of(lambda v: Dec(v, _mode="eudplib", **kw))))


def _scan_funcs():
    def get():
        numfmt.f_scan_dec_cells(EUDVariable(), 12)
        return [numfmt._scanners[(False, "eudplib")]]

    return _prep(get)


_prep(lambda: list(_tail_of(lambda v: Dec(v, width=11, sign="-"))) + list(_tail_of(lambda v: Dec(v))))
_prep(lambda: [numfmt._name_tail()])

COST_CASES = [
    _cc("Dec(v) (기본, 가변 길이)", lambda v: Dec(v), target=T32),
    _cc('Dec(v, width=5, fill="0")', lambda v: Dec(v, width=5, fill="0"), target=T32),
    _cc('Dec(v, width=11, fill=" ") (고정 폭)', lambda v: Dec(v, width=11, fill=" "), target=T32),
    _cc('Dec(v, sign="-")', lambda v: Dec(v, sign="-"), target=T32, note="음수면 절댓값·부호 보정"),
    _cc('Dec(v, sign="+-", width=10, fill="0", group=True)', lambda v: Dec(v, sign="+-", width=10, fill="0", group=True),
        target=T32),  # fmt: skip
    _cc("Dec(v, group=True)", lambda v: Dec(v, group=True), target=T32, note="묶음 배치 본문"),
    _cc("Dec(v, fullwidth=True)", lambda v: Dec(v, fullwidth=True), target=T32, note="셀 배치 본문"),
    _cc("Dec(v, colors=(1, 2, 3))", lambda v: Dec(v, colors=(1, 2, 3)), target=T32, note="반각 2B 슬롯 본문"),
    _cc("Dec(v, glyphs=한자) (등차 아님)", lambda v: Dec(v, glyphs=CJK), note="자리마다 트리거 ≤ 9"),
    _cc("Dec(v, max_digits=3, cut_low=1)", lambda v: Dec(v, max_digits=3, cut_low=1), target=T32),
    _cc("Hex(v)", lambda v: Hex(v), target=T32),
    _cc("Hex(v, width=0, lower=True)", lambda v: Hex(v, width=0, lower=True), target=T32),
    _cc("Per(v)", lambda v: Per(v), target=T32),
    _cc("dp.dec16(v)", lambda v: dp.dec16(v), target=T32),
    _cc("dp.decfw48(v)", lambda v: dp.decfw48(v), target=T32),
    _cc("dp.hex12(v)", lambda v: dp.hex12(v), target=T32),
    _cc("dp.per8(v)", lambda v: dp.per8(v), target=T32),
    _cc("dp.dig2(v)", lambda v: dp.dig2(v), target=T32),
    CostCase("dp.gauge40(n)", _fmt(lambda v: dp.gauge40(v)), [{"x": 0}, {"x": 7}, {"x": 30}], funcs=_gauge_funcs(),
             note="본문 = 꼬리(칸마다 1)"),  # fmt: skip
    CostCase("Man(v) (32비트)", _fmt(lambda v: Man(v)), X32 + [{"x": 100050000}], funcs=_man_funcs(32),
             note="본문 = 앞 계산 + 꼬리"),  # fmt: skip
    CostCase("dp.man18(v, color=True)", _fmt(lambda v: dp.man18(v, color=True)), X32 + [{"x": 100050000}],
             funcs=_man_funcs(32, colors="dps", after=4, fixed=True), note="본문 = 앞 계산 + 꼬리"),  # fmt: skip
    CostCase("dp.name20(p) (변수)", lambda t: dp.name20(t.var("x")).fmt(), [{"x": 0}, {"x": 6}, {"x": 9}],
             funcs=_prep(lambda: [numfmt._name_tail()]), note="p ≥ 7 이면 호출하지 않음"),  # fmt: skip
    _cc("Dec(Int64) (i64 본문 공유)", lambda v: Dec(v), bits=64, target=T64, note="본문 = i64._lidec_body"),
    _cc('Dec(Int64, sign="-")', lambda v: Dec(v, sign="-"), bits=64, target=T64),
    _cc("dp.dec20(x64)", lambda v: dp.dec20(v), bits=64, target=T64),
    _cc("Dec(Int64, group=True) (자체 64비트 본문)", lambda v: Dec(v, group=True), bits=64, target=T64),
    _cc("Dec(Int64, fullwidth=True)", lambda v: Dec(v, fullwidth=True), bits=64, target=T64),
    CostCase("Man(Int64)", _fmt(lambda v: Man(v), 64), X64, funcs=_man_funcs(64), target={"body": 620, "exec": 450},
             note="본문 = 앞 계산 + 꼬리"),  # fmt: skip
    CostCase('f_sprintf(buf, "{}", Dec(v)) (복사 포함)', lambda t: f_sprintf(Db(32), "{}", Dec(t.var("x"))), X32,
             note="호출 자리에 eudplib 복사 코드가 붙는다"),  # fmt: skip
    CostCase("f_fmt_dec_to(상수 주소, v, width=11, sign) (단어째)",
             lambda t: numfmt.f_fmt_dec_to(0x600001, t.var("x"), width=11, sign="-"), X32, note="앞 부분 단어 마스크 쓰기"),  # fmt: skip
    CostCase("f_fmt_dec_to(변수 주소, v) (바이트 복사)", lambda t: numfmt.f_fmt_dec_to(t.var("d"), t.var("x")),
             [dict(x, d=0x600000) for x in X32]),  # fmt: skip
    CostCase("f_fmt_dec_cells(상수 EPD, v)", lambda t: numfmt.f_fmt_dec_cells(EPD(Db(64)), t.var("x")), X32,
             funcs=_cells_funcs()),  # fmt: skip
    CostCase("f_fmt_dec_cells(변수 EPD, v)", lambda t: numfmt.f_fmt_dec_cells(t.var("e"), t.var("x")),
             [dict(x, e=0x2000) for x in X32], funcs=_cells_funcs()),  # fmt: skip
    CostCase("f_scan_dec_cells(상수 EPD, 12) (빈 칸 12)", lambda t: numfmt.f_scan_dec_cells(EPD(Db(64)), 12), [{}],
             funcs=_scan_funcs(), note="숫자 칸은 칸마다 +약 13"),  # fmt: skip
]


def repo_artifacts():
    found = []
    for dirpath, dirnames, filenames in os.walk(_common.PKG):
        rel = os.path.relpath(dirpath, _common.PKG)
        if rel.startswith("docs"):
            continue
        for d in dirnames:
            if d in ("__pycache__", "__epspy__"):
                found.append(os.path.join(rel, d))
        for f in filenames:
            if f.endswith((".scx", ".pyc")) and not (rel == "testing" and f.startswith("base")):
                found.append(os.path.join(rel, f))
    return found


def main():
    before = set(repo_artifacts())
    ck = Checker("t_numfmt (python)")
    n_random = int(os.environ.get("NUMFMT_DP_RANDOM", "20000"))
    only = os.environ.get("NUMFMT_ONLY", "")
    oks = []
    if not only or "formats" in only:
        oks.append(suite_formats())
    if not only or "dp" in only:
        oks.append(suite_dp(n_random))
    if not only or "hooks" in only:
        oks.append(suite_hooks())
    if not only or "eps" in only:
        oks.append(suite_eps(load_eps("numfmt_example")))
    if not only or "python" in only:
        python_checks(ck)
    if not only or "misc" in only:
        eps_checks(ck)
        ingame_emulate(ck)
        euddraft_builds(ck)
        bad_builds(ck)
    mine = [p for p in set(repo_artifacts()) - before if "numfmt" in p or "__epspy__" in p or p.endswith(".scx")]
    ck.eq("repo clean", sorted(mine), [])
    oks.append(ck.report())
    finish(*oks)


if __name__ == "__main__":
    main()
