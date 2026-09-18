"""auto_all phase 6~11 — 값 모듈 확인 맵을 **모듈로 import** 해 한 프레임씩 돌린다 (C3-1~3, D4-1, F20-1, D5-1·9·10, B1-1, C2-1, C9-2).

원래 확인 맵(02 i64, 15 i64_ops, 24 i128, 16 numfmt, 05 cmp, 06 cell, 07 mathx)은 첫 프레임에 `run_tests()`(또는
`selftest()`)를 돌리고 그 뒤 화면에 결과 줄을 되풀이한다. 통합 맵은 `afterTriggerExec` 를 부르지 않고 시험 함수만
불러서 결과를 블록에 남긴다 — 그래서 원래 맵의 화면 줄 반복(show)이 저절로 빠진다(분류 문서 5.3).

10진 출력(`fmt()`)은 화면 글로만 확인되므로(발견 6), 원래 맵의 `show()` 소스에서 **기대 문자열**을 뽑아
같은 값들을 버퍼에 찍고 글 스냅숏으로 판정한다(`fmt_expect(모듈)` → 명세 생성기도 같은 함수를 쓴다).
"""

import os

import aa_fmt
import cell_example
import cmp_example
import i64_ingame
import i64_ops_ingame
import i128_ingame
import mathx_ingame
import numfmt_ingame
from eudplib import Db, EUDEndIf, EUDIf, EUDVariable, Exactly, MemoryEPD, f_dbstr_print, f_dwread

import aa_common as aa
from eudext import dbg
from eudext import mathx as mx

# --- C3-2 기대값 (examples/i64_ingame.eps 주석의 res 3~15) --------------------------------------
I64_C3_2 = {3: (0xFFFFFFFF, 0), 4: (0, 0), 5: (2, 0), 6: (0, 0), 7: (0, 0), 8: (0x48202200, 2),
            9: (0xFFFFFFFF, 0), 10: (0, 0), 11: (2, 0), 12: (0, 0), 13: (0xFFFFFFFF, 0), 14: (0, 0), 15: (2, 0)}
NAME_EUDPLIB = 0x57EEEB  # eudplib·display 가 읽는 이 PC 이름 (미러 밖)
NAME_DUMP = 0x57EEE8     # 4의 배수 — 글 스냅숏은 이 자리에서 3바이트 건너뛰고 읽는다


def _source(mod):
    path = getattr(mod, "__file__", None)
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return ""


def expect_text(mod):
    """그 맵의 fmt 기대 글 전체(공백으로 이은 것) — 명세의 text equals 값 (aa_fmt 와 같은 함수)."""
    return aa_fmt.expect_text(_source(mod))


def _fmt_check(name, mod, suite):
    """모듈의 res 값을 기대 순서대로 버퍼에 찍고 글 스냅숏으로 남긴다(등록은 첫 호출 자리에서)."""
    plan = aa_fmt.fmt_expect(_source(mod))
    text = " ".join(tok for _i, _s, tok in plan)
    buf = Db(len(text) + 64)
    parts = []
    for k, (idx, signed, _tok) in enumerate(plan):
        if k:
            parts.append(" ")
        v = mod.res[idx]
        parts.append(v.fmt(signed=signed) if signed else v)
    f_dbstr_print(buf, *parts)
    dbg.snapshot_text(name, buf, len(text) // 4 + 2, every=0, suite=suite)
    dbg.capture(name)
    return text


# --- phase 6 i64 (C3-1·2·3) ---------------------------------------------------------------------


def f_i64_step(f, run, fmt):
    m = i64_ingame
    if EUDIf()(f == run):
        m.f_run_tests()
        dbg.mark("i64.C3-1.raw1", m.raw1, suite="i64")
        dbg.mark("i64.C3-1.raw2", m.raw2, suite="i64")
        dbg.mark("i64.C3-1.raw3", m.raw3, suite="i64")
        dbg.check("i64.C3-1.sub", [m.raw1.Exactly(0), m.raw2.Exactly(0), m.raw3.Exactly(0x7FFFFFFF)], suite="i64")
        for idx, (lo, hi) in I64_C3_2.items():
            dbg.check("i64.C3-2.res", [MemoryEPD(m.res.epd_lo + idx, Exactly, lo),
                                       MemoryEPD(m.res.epd_hi + idx, Exactly, hi)], suite="i64")
        dbg.result("i64.C3-3.all", m.okCount, m.total, suite="i64")
        aa.f_say("\x07[C3-7]\x04 i64 점검 {} / {} (23 / 23), SC Subtract {} {} {} (0 0 2147483647)",
                 m.okCount, m.total, m.raw1, m.raw2, m.raw3)
    EUDEndIf()
    if EUDIf()(f == fmt):
        _fmt_check("i64.C3-3.fmt", m, "i64")
    EUDEndIf()


# --- phase 7 i64_ops (D4-1) ---------------------------------------------------------------------


def f_i64_ops_step(f, run, fmt):
    m = i64_ops_ingame
    if EUDIf()(f == run):
        m.f_run_tests()
        dbg.result("i64_ops.D4-1.all", m.okCount, m.total, suite="i64_ops")
        aa.f_say("\x07[D4-9]\x04 i64 2차 점검 {} / {} (56 / 56)", m.okCount, m.total)
    EUDEndIf()
    if EUDIf()(f == fmt):
        _fmt_check("i64_ops.D4-1.fmt", m, "i64_ops")
    EUDEndIf()


# --- phase 8 i128 (F20-1) -----------------------------------------------------------------------


def f_i128_step(f, run, fmt):
    m = i128_ingame
    if EUDIf()(f == run):
        m.f_run_tests()
        dbg.result("i128.F20-1.all", m.okCount, m.total, suite="i128")
        aa.f_say("\x07[F20-9]\x04 i128 점검 {} / {} (46 / 46)", m.okCount, m.total)
    EUDEndIf()
    if EUDIf()(f == fmt):
        _fmt_check("i128.F20-1.fmt", m, "i128")
    EUDEndIf()


# --- phase 9 numfmt (D5-1·9·10) -----------------------------------------------------------------


def f_numfmt_step(f, run, name):
    m = numfmt_ingame
    if EUDIf()(f == run):
        m.f_run_tests()
        dbg.result("numfmt.D5-1.all", m.okCount, m.total, suite="numfmt")
        dbg.mark("numfmt.D5-1.lastbad", m.lastBad, suite="numfmt")
        dbg.mark("numfmt.D5-1.cells", m.cellsOk, suite="numfmt")
        dbg.check("numfmt.D5-1.ok", [m.lastBad.Exactly(0), m.cellsOk.Exactly(1)], suite="numfmt")
        aa.f_say("\x07[D5-1]\x04 numfmt 자체 점검 {} / {} (23 / 23), 틀린 번호 {} (0), 셀 왕복 {} (1)",
                 m.okCount, m.total, m.lastBad, m.cellsOk)
    EUDEndIf()
    if EUDIf()(f == name):
        dbg.snapshot_text("numfmt.D5-9.name20", m.nameBuf, 8, every=0, suite="numfmt")
        dbg.snapshot_text("numfmt.D5-9.eudplib", NAME_DUMP, 8, every=0, suite="numfmt")
        dbg.capture("numfmt.D5-9.name20")
        dbg.capture("numfmt.D5-9.eudplib")
        first = f_dwread(m.nameBuf) & 0xFF
        dbg.mark("numfmt.D5-9.color", first, suite="numfmt")
        same = aa.f_name_eq(m.nameBuf, NAME_EUDPLIB, 16)
        dbg.mark("numfmt.D5-9.same", same, suite="numfmt")
        dbg.check("numfmt.D5-9.same", same == 1, suite="numfmt")
        aa.f_say("\x07[D5-9]\x04 이름 표(0x6D0FDC) = eudplib 이름(0x57EEEB) {} (1), 첫 색 바이트 {} (8)", same, first)
    EUDEndIf()


# --- phase 10 cmp·cell (B1-1, C2-1) -------------------------------------------------------------


def f_cmp_cell_step(f, t_cmp, t_cell):
    if EUDIf()(f == t_cmp):
        n = cmp_example.f_selftest()
        dbg.result("cmp_cell.B1-1", n, 15, suite="cmp_cell")
        aa.f_say("\x07[B1-1]\x04 cmp 점검 {} / 15", n)
    EUDEndIf()
    if EUDIf()(f == t_cell):
        n2 = cell_example.f_selftest()
        dbg.result("cmp_cell.C2-1", n2, 18, suite="cmp_cell")
        aa.f_say("\x07[C2-1]\x04 cell 점검 {} / 18", n2)
    EUDEndIf()


# --- phase 11 mathx (C9-2) ----------------------------------------------------------------------

MATHX_GROUPS = (("lengthdir", 19), ("rotate", 12), ("atan2", 37), ("div", 18), ("int", 24))  # 합 110 (에뮬레이터 실측)


def _group(m, name, fn):
    g0 = EUDVariable()
    t0 = EUDVariable()
    g0 << m.good
    t0 << m.total
    fn()
    dbg.result("mathx.C9-2." + name, m.good - g0, m.total - t0, suite="mathx")


def f_mathx_step(f, base):
    """base 프레임부터 2 프레임 간격으로 그룹 여섯(마지막은 표본·판정)."""
    m = mathx_ingame
    for k, (name, _n) in enumerate(MATHX_GROUPS):
        if EUDIf()(f == base + 2 * k):
            _group(m, name, getattr(m, "f_g_" + name))
        EUDEndIf()
    if EUDIf()(f == base + 10):
        m.f_g_samples()
        c, s = mx.f_lengthdir(m.hundred, m.f45)
        a = mx.f_atan2(m.one, m.one)
        q = mx.f_isqrt(m.n99)
        nc, ns = mx.f_lengthdir(m.m100, m.f30)
        for nm, v in (("c", c), ("s", s), ("a", a), ("q", q), ("nc", nc), ("ns", ns)):
            dbg.mark("mathx.C9-2.sample_" + nm, v, suite="mathx")
        dbg.result("mathx.C9-2.all", m.good, m.total, suite="mathx")
        aa.f_say("\x07[C9-2]\x04 mathx 전체 일치 {} / {} (110 / 110)", m.good, m.total)
    EUDEndIf()
