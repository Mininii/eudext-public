"""`textfx` 시험: 셀 상수(두 배치), 참조 스캐너 기대값(S6 4.1·5.1), 런타임 스캐너 차등(두 규칙 × 1·2·3·4바이트 UTF-8·
색 코드·0x0D 묶음·줄바꿈·셀 한도·홀수 머리·주소 변수판·상수판), eudplib `_cpchar_addstr` 대조, CP 보존, 로컬 구역 밖 경고,
빌드 오류, epScript 예제 번역·에뮬레이터·euddraft 빌드.

python tests/t_textfx.py
비용 표: python tools/cost.py tests/t_textfx.py [--append --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402
import struct  # noqa: E402
import warnings  # noqa: E402

from eudplib import (  # noqa: E402
    EPD,
    CompressPayload,
    Db,
    EUDVariable,
    Exactly,
    LoadMap,
    Memory,
    RawTrigger,
    SetMemory,
    SetTo,
    f_getcurpl,
    f_setcurpl,
)

from eudext import _compat, local  # noqa: E402
from eudext import textfx as tfx  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing import BASE_MAP, emu  # noqa: E402
from eudext.testing.harness import Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
EX = os.path.join(_common.PKG, "examples")
SENT = 0x11111111
NCELL = 80
SRC_BYTES = 320
PTR_CONST_BASE = 0x640B60 + 4 * 20  # 상수 주소판 시험 자리 (채팅 버퍼 안, 셀 한도 60 이 넘치지 않게)

ck = Checker("t_textfx (python)")


# =============================================================================================
# 1. 파이썬 쪽: 셀 상수, 참조 스캐너
# =============================================================================================


def cells_of(text, rule="ctrig", mx=52, skip=False):
    return tfx.scan_const(text, mx, rule, skip).cells


def python_checks():
    cc, co = tfx.cell_const, tfx.cell_const_ctrig
    # S6 5.1-1 예
    ck.eq("가", cc("가"), 0x80B0EA0D)
    ck.eq("a 07", cc("a", 0x07), 0x0D0D6107)
    ck.eq("ctrig a 07", co("a", 0x07), 0x610D0D07)
    ck.eq("é", cc("é"), 0x0DA9C30D)
    ck.eq("ctrig é", co("é"), 0xA9C30D0D)
    # 조합: 1·2·3바이트 × 색 없음·있음 × 두 배치
    table = [
        ("A", None, 0x0D0D410D, 0x410D0D0D),
        (" ", 4, 0x0D0D2004, 0x200D0D04),
        ("\x13", None, 0x0D0D130D, 0x130D0D0D),
        ("ß", None, 0x0D9FC30D, 0x9FC30D0D),
        ("Ω", "\x1f", 0x0DA9CE1F, 0xA9CE0D1F),
        ("♪", None, 0xAA99E20D, 0xAA99E20D),
        ("보", 7, 0xB4B3EB07, 0xB4B3EB07),
        ("가", b"\x03", 0x80B0EA03, 0x80B0EA03),
    ]
    for ch, col, want_e, want_c in table:
        ck.eq("cell_const %r %r" % (ch, col), cc(ch, col), want_e)
        ck.eq("cell_const_ctrig %r %r" % (ch, col), co(ch, col), want_c)
        ck.eq("bytes 입력 %r" % ch, cc(ch.encode("utf-8"), col), want_e)
    # S6 4.1 의 CtrigAsm 배치 목록
    old = [co("!"), co("H"), co("\x13"), co("보", 7), co("스"), co(" "), co("H", 4), co("P")]
    ck.eq("S6 4.1 CtrigAsm 배치", old,
          [0x210D0D0D, 0x480D0D0D, 0x130D0D0D, 0xB4B3EB07, 0xA48AEC0D, 0x200D0D0D, 0x480D0D04, 0x500D0D0D])
    ck.eq("상수", (tfx.BLANK, tfx.MARK_U200B, tfx.CELL_NEWLINE, tfx.CELL_UNKNOWN),
          (0x0D0D0D0D, 0x8B80E20D, 0x0D0D0A0D, 0x0D0D3F0D))
    ck.eq("표식 셀 = U+200B", cc("\u200b"), tfx.MARK_U200B)
    ck.true("is_marker_cell", tfx.is_marker_cell(0x8B80E200) and tfx.is_marker_cell(0x8B80E207)
            and not tfx.is_marker_cell(0x8880E20D))
    ck.eq("색 코드 집합", sorted(tfx.COLOR_CODES), [1, 2, 3, 4, 5, 6, 7, 8, 14, 15, 16, 17] + list(range(20, 32)))
    for bad in ("ab", "", "😀", 5, None):
        ck.raises("cell_const 오류 %r" % (bad,), EudextError, cc, bad)
    for bad in (256, -1, "ab", True):
        ck.raises("색 오류 %r" % (bad,), EudextError, cc, "a", bad)
    ck.raises("rule 오류", EudextError, tfx.scan_const, b"a", 52, "bad")
    ck.raises("max 오류", EudextError, tfx.scan_const, b"a", -1)

    # S6 4.1 기대값 (rule="ctrig")
    src = bytes.fromhex("0D0D2148130 7EBB3B4EC8AA42004485000".replace(" ", ""))
    r = tfx.scan_const(src)
    ck.eq("S6 4.1 셀", r.cells, [0x0D0D210D, 0x0D0D480D, 0x0D0D130D, 0xB4B3EB07, 0xA48AEC0D, 0x0D0D200D,
                                 0x0D0D4804, 0x0D0D500D])
    ck.eq("S6 4.1 extra", r.extra, {})
    # S6 5.1-2 목록
    B, NL, Q = tfx.BLANK, tfx.CELL_NEWLINE, tfx.CELL_UNKNOWN
    A = cc("a")
    ck.eq("\\r×4", cells_of(b"\r\r\r\r"), [B])
    ck.eq("\\r×3", cells_of(b"\r\r\r"), [])
    ck.eq("\\r×5 + b", cells_of(b"\r\r\r\r\rb"), [B, cc("b")])
    ck.eq("a\\n (끝 줄바꿈 무시)", cells_of(b"a\n"), [A])
    ck.eq("a\\nb", cells_of(b"a\nb"), [A, NL, cc("b")])
    ck.eq("\\x07\\x04a (마지막 색)", cells_of(b"\x07\x04a"), [cc("a", 4)])
    ck.eq("52셀 한도", cells_of(b"a" * 60), [A] * 52)
    ck.eq("한도 3", cells_of(b"abcdef", mx=3), [A, cc("b"), cc("c")])
    ck.eq("한도 0", cells_of(b"abc", mx=0), [])
    ck.eq("é (2바이트 수정)", cells_of("éa"), [cc("é"), A])
    ck.eq("4바이트 → ?", cells_of("😀a"), [Q, A])
    ck.eq("가나", cells_of("가나"), [cc("가"), cc("나")])
    ck.eq("색+\\r×3 = 색 빈칸", cells_of(b"\x07\r\r\rX"), [0x0D0D0D07, cc("X")])
    ck.eq("색+색+\\r×4 → 빈칸에 색", cells_of(b"\x07\x04\r\r\r\rX"), [0x0D0D0D04, cc("X")])
    ck.eq("색 + 외톨이 \\r + 글자", cells_of(b"\x07\r\rX"), [cc("X", 7)])
    ck.eq("색 + 줄바꿈", cells_of(b"\x07\nY"), [0x0D0D0A07, cc("Y")])
    ck.eq("색 + 무시 줄바꿈 → extra", tfx.scan_const(b"a\x07\n"), tfx.ScanResult([A], {1: 7}))
    ck.eq("한도 끝 줄바꿈 무시", cells_of(b"ab\ncd", mx=3), [A, cc("b")])
    ck.eq("색 코드만", cells_of(b"\x07\x04"), [])
    ck.eq("제어 문자 셀", cells_of(b"\t\x0b\x0c\x12\x13\x7f"), [cc(c) for c in "\t\x0b\x0c\x12\x13\x7f"])
    ck.eq("잘린 3바이트", cells_of(b"a\xea\xb0"), [A])
    ck.eq("잘린 2바이트", cells_of(b"a\xc3"), [A])
    ck.eq("잘린 4바이트", cells_of(b"a\xf0\x9f\x98"), [A])
    ck.eq("떠돌이 뒤 바이트 → 3바이트", cells_of(b"\x80ab"), [0x6261800D])
    ck.eq("skip_odd_head", cells_of(b"\r\r\r\rX", skip=True), [cc("X")])
    ck.eq("skip 없음", cells_of(b"\r\r\r\rX"), [B, cc("X")])
    ck.eq("표식 줄 skip 무관", cells_of(b"\r\r!Hab", skip=True), cells_of(b"\r\r!Hab"))
    # rule="eudplib"
    ck.eq("eudplib 제어 문자도 셀", cells_of(b"\x07a\r\n", "eudplib"),
          [cc("\x07"), A, cc("\r"), cc("\n")])
    ck.eq("eudplib é", cells_of("é", "eudplib"), [cc("é")])
    ck.eq("eudplib 가", cells_of("가", "eudplib"), [cc("가")])
    ck.eq("eudplib 4바이트 = 3바이트 + 잘린 2바이트", cells_of("😀", "eudplib"), [0x989FF00D])
    ck.eq("eudplib 0x80 머리 = 2바이트", cells_of(b"\x80ab", "eudplib"), [0x0D61800D, cc("b")])
    # 글자 하나는 cell_const 와 같다
    for ch in "aZ 9~é€가😃\u200b":
        if len(ch.encode()) <= 3:
            ck.eq("한 글자 %r" % ch, cells_of(ch), [cc(ch)])
    # str 입력
    ck.eq("str 입력", tfx.scan_const("ab"), tfx.scan_const(b"ab"))


# =============================================================================================
# 2. 에뮬레이터
# =============================================================================================

SRC = Db(SRC_BYTES)
DST = Db(4 * NCELL)
SRC2 = Db(SRC_BYTES)
DST2 = Db(4 * NCELL)
build_msgs = []


def build_cases(s):
    @s.case("ctrig")
    def _(t):
        with local.allow():
            t.out("n", tfx.f_scan_cells_epd(EPD(SRC) + t.var("off"), EPD(DST), t.var("mx"), src_sub=t.var("sub")))
        t.watch("src", SRC)
        t.watch("dst", DST)
        t.watch("src2", SRC2)
        t.watch("dst2", DST2)

    @s.case("eudplib")
    def _(t):
        with local.allow():
            t.out("n", tfx.f_scan_cells_epd(EPD(SRC) + t.var("off"), EPD(DST), t.var("mx"), src_sub=t.var("sub"),
                                            rule="eudplib"))

    @s.case("ctrig_skip")
    def _(t):
        with local.allow():
            t.out("n", tfx.f_scan_cells_epd(EPD(SRC) + t.var("off"), EPD(DST), t.var("mx"), src_sub=t.var("sub"),
                                            skip_odd_head=True))

    @s.case("ptr_var")
    def _(t):
        with local.only():
            t.out("n", tfx.f_scan_cells(t.var("ptr"), EPD(DST), t.var("mx")))

    for k in range(4):
        @s.case("ptr_const%d" % k)
        def _(t, k=k):
            with local.allow():
                t.out("n", tfx.f_scan_cells(PTR_CONST_BASE + k, EPD(DST), 60, rule="eudplib" if k % 2 else "ctrig"))

    @s.case("ptr_cexpr")
    def _(t):
        with local.allow():
            t.out("n", tfx.f_scan_cells(SRC + 6, EPD(DST), 60))

    @s.case("cpchar")
    def _(t):
        # eudplib _cpchar_addstr (색 칸 0x0D) 과 rule="eudplib" 스캐너를 같은 원문에
        orig = f_getcurpl()
        cv = _compat.cpchar_color_var()
        cv << 0x0D
        f_setcurpl(EPD(DST2))
        _compat.cpchar_addstr_epd(EPD(SRC2))
        t.out("n2", f_getcurpl() - EPD(DST2))
        f_setcurpl(orig)
        cv << 2
        with local.allow():
            t.out("n", tfx.f_scan_cells_epd(EPD(SRC2), EPD(DST), 70, rule="eudplib"))

    @s.case("cp_keep")
    def _(t):
        orig = f_getcurpl()
        f_setcurpl(1234)
        with local.allow():
            t.out("n", tfx.f_scan_cells_epd(EPD(SRC) + 1, EPD(DST), 52, src_sub=3))
        t.flag("cp_raw", Memory(0x6509B0, Exactly, 1234))
        t.out("cp_cache", f_getcurpl())
        f_setcurpl(orig)

    # 로컬 구역 밖 경고 (빌드 때)
    @s.case("warn_outside")
    def _(t):
        t.out("n", tfx.f_scan_cells(0x640B60, EPD(DST), 5))

    @s.case("no_warn_inside")
    def _(t):
        local.begin(0)
        t.out("n", tfx.f_scan_cells(0x640B60, EPD(DST), 5))
        local.end()

    # 빌드 오류
    @s.case("err_rule", expect_build_error=EudextError, expect_message="rule")
    def _(t):
        tfx.f_scan_cells(0x640B60, EPD(DST), 5, rule="ctrigasm")

    @s.case("err_sub", expect_build_error=EudextError, expect_message="src_sub")
    def _(t):
        tfx.f_scan_cells_epd(EPD(SRC), EPD(DST), 5, src_sub=4)

    @s.case("err_max", expect_build_error=EudextError, expect_message="max_cells")
    def _(t):
        tfx.f_scan_cells(0x640B60, EPD(DST), -1)

    @s.case("err_ptr", expect_build_error=EudextError, expect_message="src_ptr")
    def _(t):
        tfx.f_scan_cells("0x640B60", EPD(DST), 5)


class Env:
    def __init__(self, s):
        self.s = s
        self.m = s.machine
        self.src = self.m.addr("ctrig.src")
        self.dst = self.m.addr("ctrig.dst")
        self.src2 = self.m.addr("ctrig.src2")
        self.dst2 = self.m.addr("ctrig.dst2")

    def fill_dst(self, addr=None):
        addr = self.dst if addr is None else addr
        for i in range(NCELL):
            self.m.setdw(addr + 4 * i, SENT)

    def cells(self, n, addr=None):
        addr = self.dst if addr is None else addr
        return [self.m.dw(addr + 4 * i) for i in range(n)]


def expect_dst(ref, n_cells=NCELL):
    out = [SENT] * n_cells
    out[: len(ref.cells)] = ref.cells
    for idx, c in ref.extra.items():
        out[idx] = (SENT & ~0xFF) | c
    return out


def check_scan(env, case, data, mx, sub, rule, skip=False, label=None, place=None):
    s, m = env.s, env.m
    s.reset()
    base = env.src if place is None else place
    m.write_bytes(base, bytes(SRC_BYTES if place is None else 120))
    start = (base + 4 + sub) if place is None else base
    m.write_bytes(start, data)
    env.fill_dst()
    before = m.read_bytes(base, 120)
    inputs = {}
    if case in ("ctrig", "eudplib", "ctrig_skip"):
        inputs = {"off": 1, "mx": mx, "sub": sub}
    elif case == "ptr_var":
        inputs = {"ptr": start, "mx": mx}
    r = s.run(case, inputs)
    ref = tfx.scan_const(data, mx, rule, skip)  # 넣은 바이트 뒤는 0
    got = env.cells(NCELL)
    ok = r.error is None and r["n"] == len(ref.cells) and got == expect_dst(ref) and m.read_bytes(base, 120) == before
    label = label or "%s %r mx=%d sub=%d" % (case, data[:24], mx, sub)
    msg = ""
    if not ok:
        msg = "err=%s n=%s want=%d got=%s want=%s" % (r.error, r.values.get("n"), len(ref.cells),
                                                      [hex(x) for x in got[: len(ref.cells) + 2]],
                                                      [hex(x) for x in expect_dst(ref)[: len(ref.cells) + 2]])
    s.expect_true(case, ok, label, msg)
    return r


FIXED = [
    bytes.fromhex("0D0D2148130 7EBB3B4EC8AA42004485000".replace(" ", "")),
    b"", b"\r\r\r\r", b"\r\r\r", b"a\n", b"a\nb", b"\x07\x04a", b"a" * 60, "é".encode(), "😀a".encode(),
    b"\x07\r\r\rX", b"\x07\x04\r\r\r\rX", b"\x07\nY", b"a\x07\n", b"ab\ncd", b"\t\x0b\x0c\x12\x13\x7f",
    b"a\xea\xb0", b"a\xc3", b"a\xf0\x9f\x98", b"\x80ab", b"\r\r!H\x13\x04\xea\xb0\x80\xeb\x82\x98 \x07ok",
    b"\r\r\r\rX", "가".encode() * 20, b"\x07\r\r\x04\r\r\r\rZ\n\n",
]

TOKENS = [b"a", b"Z", b" ", b"!", b"H", b"\r", b"\r\r", b"\r\r\r\r", b"\n", b"\x07", b"\x04", b"\x1f", b"\x0e",
          b"\x13", b"\x12", b"\t", b"\x0b", b"\x0c", b"\x7f", "é".encode(), "Ω".encode(), "ß".encode(),
          "가".encode(), "♪".encode(), "\u200b".encode(), "😀".encode(), b"\x80", b"\xbf", b"\xc3", b"\xe2\x80",
          b"\r\r!H"]


def rand_data(rng, maxlen=48):
    d = b"".join(rng.choice(TOKENS) for _ in range(rng.randrange(0, maxlen)))
    if rng.random() < 0.3:
        return d  # 끝 = 0 (뒤도 0)
    return d + b"\0" + bytes(rng.randrange(256) for _ in range(rng.randrange(0, 4)))


def run_scan(env, rng):
    for data in FIXED:
        for sub in range(4):
            for mx in (52, 3):
                check_scan(env, "ctrig", data, mx, sub, "ctrig")
                check_scan(env, "eudplib", data, mx, sub, "eudplib")
    for mx in (0, 1, 2, 53, 70):
        check_scan(env, "ctrig", b"ab\ncd\r\r\r\ref", mx, 1, "ctrig")
    for _ in range(500):
        d = rand_data(rng)
        check_scan(env, "ctrig", d, rng.choice([1, 2, 3, 5, 8, 52, 60]), rng.randrange(4), "ctrig")
    for _ in range(250):
        d = rand_data(rng)
        check_scan(env, "eudplib", d, rng.choice([1, 2, 5, 52, 60]), rng.randrange(4), "eudplib")
    for data in (b"\r\r\r\rX", b"\r\r!Hab", b"\r\rX", b"\rX", b"\r\r"):
        for sub in range(4):
            check_scan(env, "ctrig_skip", data, 52, sub, "ctrig", skip=True)
    for _ in range(80):
        d = (b"\r\r" if rng.random() < 0.5 else b"") + rand_data(rng)
        check_scan(env, "ctrig_skip", d, rng.choice([2, 52]), rng.randrange(4), "ctrig", skip=True)
    for _ in range(80):
        check_scan(env, "ptr_var", rand_data(rng), rng.choice([3, 52]), rng.randrange(4), "ctrig")


def run_ptr_const(env, rng):
    s, m = env.s, env.m
    for k in range(4):
        for i in range(12):
            data = FIXED[i] if i < 4 else rand_data(rng, 30)
            s.reset()
            m.write_bytes(PTR_CONST_BASE, bytes(160))
            m.write_bytes(PTR_CONST_BASE + k, data)
            env.fill_dst()
            r = s.run("ptr_const%d" % k)
            ref = tfx.scan_const(data, 60, "eudplib" if k % 2 else "ctrig")
            s.expect_true("ptr_const%d" % k, r.error is None and r["n"] == len(ref.cells) and env.cells(NCELL) == expect_dst(ref),
                          "%r" % data[:20], "%s %s" % (r.error, r.values))
    # 주소식(Db + 6) → 실행 중 나누기
    for i in range(10):
        data = FIXED[i]
        s.reset()
        m.write_bytes(env.src, bytes(SRC_BYTES))
        m.write_bytes(env.src + 6, data)
        env.fill_dst()
        r = s.run("ptr_cexpr")
        ref = tfx.scan_const(data, 60)
        s.expect_true("ptr_cexpr", r.error is None and r["n"] == len(ref.cells) and env.cells(NCELL) == expect_dst(ref),
                      "%r" % data[:20], "%s %s" % (r.error, r.values))


def utf8_data(rng):
    # eudplib 은 뒤 바이트를 그대로 읽으므로 잘리지 않은 원문만 (NUL 은 글자 머리 자리에만)
    toks = [b"a", b" ", b"\r", b"\n", b"\x07", b"\x13", "é".encode(), "Ω".encode(), "가".encode(), "♪".encode(),
            b"\x7f", b"\x04"]
    return b"".join(rng.choice(toks) for _ in range(rng.randrange(0, 40)))


def run_cpchar(env, rng):
    s, m = env.s, env.m
    datas = [b"", b"abc", "é가\r\n\x07x".encode(), bytes.fromhex("0D0D2148130 7EBB3B4EC8AA420044850".replace(" ", ""))]
    datas += [utf8_data(rng) for _ in range(120)]
    for data in datas:
        s.reset()
        m.write_bytes(env.src2, bytes(SRC_BYTES))
        m.write_bytes(env.src2, data)
        env.fill_dst()
        env.fill_dst(env.dst2)
        r = s.run("cpchar")
        n = r.values.get("n")
        ref = tfx.scan_const(data, 70, "eudplib")
        ok = (r.error is None and n == r.values.get("n2") == len(ref.cells)
              and env.cells(n) == env.cells(n, env.dst2) == ref.cells)
        s.expect_true("cpchar", ok, "%r" % data[:20], "%s n=%s n2=%s %s %s" % (
            r.error, n, r.values.get("n2"), [hex(x) for x in env.cells(n or 0)], [hex(x) for x in env.cells(n or 0, env.dst2)]))


def run_misc(env):
    s, m = env.s, env.m
    s.reset()
    m.write_bytes(env.src + 4 + 3, "é가 a\x07b".encode() + b"\0")
    env.fill_dst()
    r = s.run("cp_keep")
    s.expect_true("cp_keep", r.error is None and r["n"] == 5 and r["cp_raw"] == 1 and r["cp_cache"] == 1234,
                  "CP 1234 유지", repr(r))
    s.expect_true("cp_keep", env.cells(5) == tfx.scan_const("é가 a\x07b").cells, "셀", "")
    # 경고
    s.expect_true("warn_outside", any("textfx.scan_cells" in x and "t_textfx.py" in x for x in build_msgs),
                  "구역 밖 경고", "; ".join(build_msgs))
    s.expect_true("no_warn_inside", sum("textfx.scan_cells" in x for x in build_msgs) == 1,
                  "구역 안 경고 없음 (경고는 warn_outside 하나)", "; ".join(build_msgs))
    for name in ("warn_outside", "no_warn_inside"):
        m.write_bytes(0x640B60, b"abc\0")
        env.fill_dst()
        r = s.run(name)
        s.expect_true(name, r.error is None and r["n"] == 3, "실행", repr(r))


def per_byte_steps(env):
    """실행 트리거 수: 빈 원문, ASCII n, 한글 n (보고용)."""
    s, m = env.s, env.m
    out = {}
    for label, data in (("empty", b""), ("ascii10", b"abcdefghij"), ("ascii40", b"a" * 40),
                        ("hangul10", "가" * 10), ("hangul40", "가" * 40), ("marker_line", "\r\r!H\x13\x04가사 한 줄 abc")):
        raw = data.encode() if isinstance(data, str) else data
        s.reset()
        m.write_bytes(env.src, bytes(SRC_BYTES))
        m.write_bytes(env.src + 4, raw)
        r = s.run("ctrig", {"off": 1, "mx": 52, "sub": 0})
        out[label] = r.steps[0]
    print("  스캐너 실행 트리거 수: %r" % out)
    ascii_per = (out["ascii40"] - out["ascii10"]) / 30
    hangul_per = (out["hangul40"] - out["hangul10"]) / 30
    print("  ASCII 글자당 %.1f, 한글(3바이트) 글자당 %.1f" % (ascii_per, hangul_per))
    return out


def section_emu():
    rng = random.Random(17)
    s = Suite("t_textfx")
    build_cases(s)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        s.build()
    build_msgs.extend(str(x.message) for x in w)
    env = Env(s)
    run_scan(env, rng)
    run_ptr_const(env, rng)
    run_cpchar(env, rng)
    run_misc(env)
    steps = per_byte_steps(env)
    ok = s.report()
    return ok, steps


# =============================================================================================
# 3. epScript 예제
# =============================================================================================


def eps_checks(cke):
    src = open(os.path.join(EX, "textfx_example.eps"), encoding="utf-8").read()
    out, nerr = _compat.eps_compile("textfx_example.eps", src)
    cke.eq("eps errors", nerr, 0)
    for needle in ("tfx.f_cell_const(\"가\")", "tfx.f_cell_const_ctrig(\"a\", 7)", "local.f_begin()", "local.f_end()",
                   "tfx.f_scan_cells(0x640B60, EPD(buf), 52)",
                   "tfx.f_scan_cells_epd(EPD(0x640B60) + 54, EPD(buf) + 30, 20, src_sub=2, rule=\"eudplib\")"):
        cke.true("eps: " + needle, out is not None and needle in out, "")


def eps_emulate(cke):
    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_textfx_eps")
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, "textfx_example.eps"), os.path.join(work, "textfx_example.eps"))
    LoadMap(BASE_MAP)
    CompressPayload(True)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        mod = build._load_plugin(os.path.join(work, "textfx_example.eps"), {})
        prog = emu.Program(mod.afterTriggerExec)
        names = ("cells", "oddCells", "firstIsGa", "secondCell", "oldConst")
        for n in names:
            prog.watch(n, getattr(mod, n))
        prog.watch("buf", mod.buf)
        m = prog.build()
    msgs = [str(x.message) for x in w if "구역 밖" in str(x.message)]
    cke.eq("example 구역 밖 경고 없음", msgs, [])
    line0 = "가나 abc".encode() + b"\0"
    line1 = b"\r\r" + "\x07é!".encode() + b"\0"
    m.write_bytes(0x640B60, line0)
    m.write_bytes(0x640B60 + 218, line1)
    m.cycle(2)
    got = {n: m.var(n) for n in names}
    buf = m.addr("buf")
    want0 = tfx.scan_const(line0).cells
    want1 = tfx.scan_const(line1, 20, "eudplib").cells
    cke.eq("example 값", got, {"cells": len(want0), "oddCells": len(want1), "firstIsGa": 1,
                               "secondCell": tfx.cell_const("나"), "oldConst": 0x610D0D07})
    cke.eq("example 줄 0 셀", [m.dw(buf + 4 * i) for i in range(len(want0))], want0)
    cke.eq("example 줄 1 셀", [m.dw(buf + 4 * (30 + i)) for i in range(len(want1))], want1)


def eps_build(cke):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    name = "textfx_example"
    work = os.path.join(_common.WORK, "t_textfx_build_" + name)
    eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
    r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
    print("  " + r.summary())
    cke.true("euddraft " + name, r.ok, r.log[-2000:])
    cke.true("eps compiled " + name, '[epScript] Compiling "%s.eps"' % name in r.log, "")


# =============================================================================================
# 비용 측정 항목 (tools/cost.py)
# =============================================================================================

C_SRC = Db(SRC_BYTES)
C_DST = Db(4 * NCELL)


def _put(data):
    def setup(t):
        raw = (data.encode() if isinstance(data, str) else data) + b"\0" * 8
        raw = raw + bytes(-len(raw) & 3)
        RawTrigger(actions=[SetMemory(C_SRC + i, SetTo, struct.unpack_from("<I", raw, i)[0])
                            for i in range(0, min(len(raw), 256), 4)])

    return setup


def _cost_scan(rule="ctrig"):
    def body(t):
        with local.allow():
            tfx.f_scan_cells_epd(EPD(C_SRC), EPD(C_DST), 52, rule=rule)

    return body


C_PTR = EUDVariable()


def _cost_ptr(t):
    with local.allow():
        tfx.f_scan_cells(C_PTR, EPD(C_DST), 52)


def _cost_ptr_setup(data):
    put = _put(data)

    def setup(t):
        put(t)
        C_PTR << C_SRC

    return setup


COST_CASES = [
    CostCase("scan_cells 빈 원문 (창 채우기만)", _cost_scan(), funcs=[tfx._scanner("ctrig", False)], setup=_put(b""),
             note="본문 = ctrig 규칙 1벌"),
    CostCase("scan_cells ASCII 10글자", _cost_scan(), setup=_put(b"abcdefghij")),
    CostCase("scan_cells 한글 10글자 (30바이트)", _cost_scan(), setup=_put("가나다라마바사아자차")),
    CostCase("scan_cells 표식 줄 \\r\\r!H + 색·한글·ASCII 16글자", _cost_scan(),
             setup=_put("\r\r!H\x13\x04가사 한 줄 \x07abc 끝")),
    CostCase("scan_cells 52칸 한도 (ASCII 60)", _cost_scan(), setup=_put(b"a" * 60)),
    CostCase("scan_cells rule=eudplib ASCII 10글자", _cost_scan("eudplib"), funcs=[tfx._scanner("eudplib", False)],
             setup=_put(b"abcdefghij"), note="본문 = eudplib 규칙 1벌"),
    CostCase("scan_cells 주소 변수판 (ASCII 10)", _cost_ptr, funcs=[tfx._ptr_split_func()],
             setup=_cost_ptr_setup(b"abcdefghij"), note="본문 = 주소 나누기 1벌"),
]


def main():
    python_checks()
    ok1, _steps = section_emu()
    cke = Checker("t_textfx (epScript)")
    eps_checks(cke)
    eps_emulate(cke)
    eps_build(cke)
    finish(ok1, ck.report(), cke.report())


if __name__ == "__main__":
    main()
