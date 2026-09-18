"""`display` 시험 (에뮬레이터): DisplayText 캡처 비교, S3 참조 모델(tests/ref_dp.py) 무작위 차등, 8.1 기대값, 8.2 항목.

- 원소(part) 약 60종 × 경계값·무작위 값: 이 PC 화면에 뜬 글(실행 순간 버퍼 메모리 — testing/dispmodel.py)이
  ① 보이는 글 = 원소 출력을 이은 것(ref_dp.ex_out, 서식은 ref_numfmt) ② 버퍼 바이트 = 틀 모델(상수 그대로, 4 배수 자리, 자리 맞춤)
  ③ 틀의 상수·맞춤 바이트는 실행 뒤에도 그대로.
- 대상 18종 × 이 PC 번호 12가지(0~7, 관전자 128~131 — `suite.restart(local_player=…)` 로 빌드 한 번):
  보이는 횟수(정확히 한 번/0번), 소리, CP 복구(원시 CP·캐시), 상수만 있는 경로(run_as), players.display 연결.
- every·update_if·pin·pinned·sound, 채팅 줄 모델(0x640B58 고정).
- 13번째 줄: CCMU 가 이 PC 번호와 무관하게 같은 순서로 도는지, 로컬 쓰기는 대상 PC 에서만, 틀 + NUL, 217B 경계(218B 빌드 오류, 줄 버퍼 밖 바이트 보존),
  hold, 변수 대상 8 이상·관전자 CCMU 없음, players.Humans(each 경로), 로컬 구역 경고.
- TBL: 바이트 정확 쓰기(4 배수가 아닌 주소), tail·eos 조합 4가지, capacity 오류, 변수 번호, 잔재, every.
- Template(DisplaySTRX): 모든 PC 에서 갱신, every·update_if 되풀이.
- DPL 참조 모델 차등(무작위 구조): show 보이는 글 = DPL 틀, 13번째 줄 보이는 글 = DPL Er, TBL(dp 프리셋·eos=False) 바이트 = DPL Tbl.
- epScript 예제(examples/display_example.eps) 번역·실행, 인게임 확인 맵(display_ingame) 에뮬레이션, euddraft 빌드 2개.
- 파이썬 쪽: 입력 오류, 문서(3.12), 별칭, 비공개 API, players.display 가 display 로 넘어가는지.

python tests/t_display.py         (환경 변수 DISPLAY_ONLY = 스위트 이름 일부, DISPLAY_N = 무작위 배수 — 기본 1)
비용 표: python tools/cost.py tests/t_display.py [--append --out <파일> --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import inspect  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import types  # noqa: E402
import warnings  # noqa: E402

from eudplib import (  # noqa: E402
    EPD,
    AllPlayers,
    CompressPayload,
    CurrentPlayer,
    Db,
    DisplayTextAll,
    DoActions,
    EPSLoader,
    EPWarning,
    EUDArray,
    EUDVariable,
    Force1,
    LoadMap,
    Memory,
    P1,
    P2,
    P3,
    P4,
    P9,
    SetDeaths,
    SetMissionObjectives,
    SetTo,
    StringBuffer,
    ptr2s,
)

import ref_dp as RD  # noqa: E402
import ref_numfmt as R  # noqa: E402
from eudext import _compat, display as dp, local, numfmt, players  # noqa: E402
from eudext import strdesign as sd  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.i64 import Int64  # noqa: E402
from eudext.numfmt import Dec, Gauge, Hex, Man, Per  # noqa: E402
from eudext.testing import chatmodel, dispmodel, emu, scmodel  # noqa: E402
from eudext.testing.harness import BASE_MAP, Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402
from eudext.display import Byte, Bytes, LocalName, Part, Pick, PName  # noqa: E402

M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1
D = 0x0D
CP_ADDR = 0x6509B0
DEATH0 = 0x58A364
EX = os.path.join(_common.PKG, "examples")
BASE_MULTI = os.path.join(_common.PKG, "testing", "base_multi.scx")
MULT = int(os.environ.get("DISPLAY_N", "1"))

HUMANS = [0, 1, 2, 3, 5]
FORCES = [[0, 1, 2], [3, 4], [5, 6, 7], []]
TYPES = ["human", "human", "human", "human", "computer", "human", "computer", "computer"]
OBS = [128, 129, 130, 131]
LOCALS = list(range(8)) + OBS
NAMES = {
    0: b"Alpha", 1: b"BravoBravo", 2: "한글이름".encode(), 3: b"Delta__16bytes__", 4: b"Echo",
    5: b"F", 6: b"[CLAN]Golf", 7: b"Hotel7",
}  # fmt: skip
TBL_IDS = 60

EDGE32 = sorted({0, 1, 9, 10, 99, 100, 999, 9999, 10**4, 12345, 99999, 10**6, 1234567, 10**8, 123456789, 999999999,
                 10**9, 2**31 - 1, 2**31, 2**31 + 1, 4294967286, M32})  # fmt: skip


def rvals(rng, n, bits=32):
    out = []
    for _ in range(n):
        r = rng.random()
        if r < 0.5:
            out.append(rng.randrange(10 ** rng.randrange(1, 11 if bits == 32 else 21)) & ((1 << bits) - 1))
        else:
            out.append(rng.getrandbits(bits))
    return out


def run_env(s, name, env, **kw):
    """케이스에 있는 입력 칸만 넣어 실행한다."""
    inputs = {k: v for k, v in env_inputs(env).items() if k in s.cases[name].vars}
    return s.run(name, inputs, **kw)


def cstr(data):
    i = data.find(b"\0")
    return data if i < 0 else data[:i]


def memory(local=0):
    return {"local_player": local, "players": list(TYPES), "cp": 0, "text": True, "units": {}}


def prep_tbl(entries=None):
    def prep(m):
        dispmodel.install(m, tbl=entries, names=NAMES)

    return prep


def set_tables():
    players.set_table(humans=HUMANS, forces=FORCES)


# ---------------------------------------------------------------------------------------------
# 원소 명세 → part
# ---------------------------------------------------------------------------------------------

XP = RD.XP


def V(t, name):
    if name.startswith("q"):
        return Int64.wrap(t.var(name + "lo"), t.var(name + "hi"))
    return t.var(name)


def env_inputs(env):
    out = {}
    for k, v in env.items():
        if k.startswith("q"):
            out[k + "lo"] = v & M32
            out[k + "hi"] = (v >> 32) & M32
        else:
            out[k] = v & M32
    return out


class CustomPart(Part):
    """사용자 확장 예: 값이 짝수면 "EVEN", 아니면 "odd!" (fmt 는 Db 두 개 중 하나를 고른다)."""

    max_len = 4

    def __init__(self, v):
        self.v = v

    def fmt(self):
        from eudplib import EUDElse, EUDEndIf, EUDIf

        p = EUDVariable()
        if EUDIf()(self.v.ExactlyX(0, 1)):
            p << Db(b"EVEN\0")
        if EUDElse()():
            p << Db(b"odd!\0")
        EUDEndIf()
        return ptr2s(p)


def make_part(xp, t):
    k = xp.kind
    o = dict(xp.opt)
    val = V(t, xp.value) if isinstance(xp.value, str) and k not in ("s", "custom", "partof") else xp.value
    if k == "s":
        return xp.value
    if k in ("var", "i64"):
        return val
    if k == "int":
        return xp.value
    if k == "dec":
        return Dec(val, **o)
    if k == "hex":
        return Hex(val, **o)
    if k == "man":
        o.pop("bits", None)
        return Man(val, **o)
    if k == "per":
        return Per(val, **o)
    if k == "gauge":
        return Gauge(val, **o)
    if k == "dp":
        name = o.pop("name")
        return getattr(numfmt.dp, name)(val, **o)
    if k == "pname":
        return PName(val, **o)
    if k == "local":
        return LocalName(**o)
    if k == "byte":
        return Byte(val)
    if k == "bytes":
        return Bytes(*[V(t, x) if isinstance(x, str) else x for x in xp.value])
    if k == "pick":
        return Pick(val, o["table"], default=o.get("default", ""))
    if k == "custom":
        return CustomPart(V(t, xp.value))
    if k == "partof":
        return Part.of(Db(xp.value + b"\0\0\0\0"), len(xp.value))
    if k == "wrap":
        return sd.wrap(make_part(xp.value, t), "님", style="seed", center=True)
    raise ValueError(k)


def ex_out(xp, env, local=0):
    if xp.kind == "int":
        x = xp.value
        return (str(RD.s32(x)) if -(1 << 31) <= x < (1 << 32) else str(RD.s64(x))).encode()
    if xp.kind == "custom":
        return b"EVEN" if env[xp.value] % 2 == 0 else b"odd!"
    if xp.kind == "partof":
        return xp.value
    if xp.kind == "wrap":
        pre, post = sd.parts(style="seed")
        return b"\x13" + pre.encode() + RD.ex_out(xp.value, env, NAMES, local) + "님".encode() + post.encode()
    return RD.ex_out(xp, env, NAMES, local)


def fixed_xps(xps):
    """모델에 넘길 원소 목록: wrap 은 펼친 모양으로 (상수 + 원소 + 상수)."""
    out = []
    for xp in xps:
        if xp.kind == "wrap":
            pre, post = sd.parts(style="seed")
            out += [XP("s", "\x13" + pre), xp.value, XP("s", "님" + post)]
        elif xp.kind == "int" or is_const_xp(xp):
            out.append(XP("s", ex_out(xp, {})))
        else:
            out.append(xp)
    return out


def is_const_xp(xp):
    if xp.kind in ("pick", "byte", "pname") and isinstance(xp.value, int):
        return xp.kind != "pname"
    if xp.kind == "bytes":
        return all(isinstance(x, int) for x in xp.value)
    return False


def model_out(xp, env, local):
    if xp.kind in ("custom", "partof"):
        return ex_out(xp, env, local)
    return RD.ex_out(xp, env, NAMES, local)


def model_buffer(xps, slots, env, local, before):
    """(새 틀, 채운 뒤 바이트, 오류) — ref_dp.ex_template 에 custom·partof 를 더한 것."""
    flat = fixed_xps(xps)
    errs = []
    fresh = bytearray()
    placed = []
    it = iter(slots)
    for xp in flat:
        if xp.kind == "s":
            fresh += xp.value if isinstance(xp.value, bytes) else xp.value.encode("utf-8")
            continue
        off, size, kind, align = next(it)
        want = len(fresh) + (-len(fresh) % 4)
        if off != want:
            errs.append("자리 %d != %d" % (off, want))
        fresh += bytes([D]) * (want - len(fresh) + size)
        placed.append((off, size, kind, align, xp))
    out = bytearray(before)
    for off, size, kind, align, xp in placed:
        if kind == "namecache":
            out[off : off + size] = RD.ex_namecache(xp, env, NAMES, local)
            continue
        b = model_out(xp, env, local)
        if b is None:  # name20 p ≥ 7
            continue
        out[off : off + size] = RD.ex_fill_slot(b, size, align)
    return bytes(fresh), bytes(out), errs, placed


# ---------------------------------------------------------------------------------------------
# 1. 원소
# ---------------------------------------------------------------------------------------------

PICK3 = ["zero", "one", "둘"]
PICKD = {3: "three", 100: "\x1fhundred", 7: "칠"}
PART_SPECS = [
    ("var", [XP("var", "x")], "x32"),
    ("i64", [XP("i64", "q")], "x64"),
    ("dec", [XP("dec", "x")], "x32"),
    ("dec_w5z", [XP("dec", "x", width=5, fill="0")], "x32"),
    ("dec_group", [XP("dec", "x", sign="+-", group=(3, ","))], "x32"),
    ("dec_space", [XP("dec", "x", fill=" ", width=4)], "x32"),
    ("dec_fw", [XP("dec", "x", fullwidth=True)], "x32"),
    ("dec_colors", [XP("dec", "x", colors=(1, 2, 3))], "x32"),
    ("dec_md3", [XP("dec", "x", max_digits=3)], "x32"),
    ("dec_cut", [XP("dec", "x", cut_low=2, width=6)], "x32"),
    ("dec64_group", [XP("dec", "q", bits=64, group=(3, ","), sign="-")], "x64"),
    ("hex", [XP("hex", "x")], "x32"),
    ("hex_w0", [XP("hex", "x", width=0)], "x32"),
    ("hex_w0r", [XP("hex", "x", width=0, fill="\r", lower=True)], "x32"),
    ("per", [XP("per", "x")], "x32"),
    ("per_max", [XP("per", "x", max=100000)], "x32"),
    ("per_s100f1", [XP("per", "x", scale=100, frac=1)], "x32"),
    ("per_notrim", [XP("per", "x", trim=False)], "x32"),
    ("man", [XP("man", "x")], "x32"),
    ("man_dps", [XP("man", "x", colors="dps", after=4)], "x32"),
    ("man_top1", [XP("man", "x", top=1, colors="dps")], "x32"),
    ("man_fixed", [XP("man", "x", fixed=True, after=4)], "x32"),
    ("man64", [XP("man", "q", bits=64, colors="dps", after=4)], "x64"),
    ("gauge", [XP("gauge", "x")], "g"),
    ("gauge7", [XP("gauge", "x", cells=7, glyph="■", on=3, off=4)], "g"),
    ("dp_dec16", [XP("dp", "x", name="dec16")], "x32"),
    ("dp_decfw48", [XP("dp", "x", name="decfw48")], "x32"),
    ("dp_hex12", [XP("dp", "x", name="hex12")], "x32"),
    ("dp_dec20", [XP("dp", "q", name="dec20")], "x64"),
    ("dp_name20", [XP("dp", "x", name="name20")], "p"),
    ("dp_man18", [XP("dp", "x", name="man18", color=True)], "x32"),
    ("dp_man18off", [XP("dp", "x", name="man18")], "x32"),
    ("dp_per8", [XP("dp", "x", name="per8")], "x32"),
    ("dp_per8pm", [XP("dp", "x", name="per8", permil=True, tbl=True)], "x32"),
    ("dp_dig2", [XP("dp", "x", name="dig2")], "x32"),
    ("dp_gauge40", [XP("dp", "x", name="gauge40")], "g"),
    ("pname0", [XP("pname", 0)], None),
    ("pname3_nocolor", [XP("pname", 3, color=None)], None),
    ("pname_var", [XP("pname", "x")], "p"),
    ("pname_var_c", [XP("pname", "x", color=0x1F)], "p"),
    ("pname_var_cache", [XP("pname", "x", cache=True)], "p"),
    ("pname_var_cache_c", [XP("pname", "x", cache=True, color=0x06)], "p"),
    ("pname2_cache_plain", [XP("pname", 2, cache=True, color=None)], None),
    ("pname6_cache", [XP("pname", 6, cache=True)], None),
    ("localname", [XP("local")], None),
    ("localname_cache", [XP("local", cache=True, color=None)], None),
    ("byte_var", [XP("byte", "x")], "b"),
    ("byte_const", [XP("byte", 0x41)], None),
    ("bytes3", [XP("bytes", ["x", 0x42, "y"])], "b"),
    ("bytes5", [XP("bytes", ["x", "x", "y", "x", "y"])], "b"),
    ("pick", [XP("pick", "x", table=PICK3, default="?")], "k"),
    ("pick_dict", [XP("pick", "x", table=PICKD, default="")], "k"),
    ("pick_const", [XP("pick", 1, table=PICK3)], None),
    ("custom", [XP("custom", "x")], "x32"),
    ("partof", [XP("partof", b"\x07dbtext")], None),
    ("int_neg", [XP("int", M32), XP("s", " "), XP("int", -5), XP("s", " "), XP("int", 12800000000)], None),
    ("wrap", [XP("wrap", XP("pname", "x"))], "p"),
    ("mix", [XP("s", "\x07HP "), XP("var", "x"), XP("s", " / "), XP("man", "y", colors="dps", after=4), XP("s", " "),
             XP("pname", 1), XP("byte", "z"), XP("s", "\x04|끝")], "mix"),  # fmt: skip
    ("mix2", [XP("pick", "z", table=PICK3, default="?"), XP("dec", "x", group=(3, ",")), XP("s", "é"),
              XP("dp", "x", name="dig2"), XP("local"), XP("i64", "q")], "mix"),  # fmt: skip
]


def value_sets(kind, rng):
    n = 12 * MULT
    if kind is None:
        return [{}]
    if kind == "x32":
        return [{"x": v} for v in EDGE32 + rvals(rng, n)]
    if kind == "x64":
        e64 = [0, 1, M32, 1 << 32, 12800000000, 10**18, (1 << 63) - 1, 1 << 63, M64 - 4, M64]
        return [{"q": v} for v in e64 + rvals(rng, n, 64)]
    if kind == "g":
        return [{"x": v} for v in (0, 1, 3, 6, 7, 8, 19, 20, 21, M32) + tuple(rng.randrange(30) for _ in range(4))]
    if kind == "p":
        return [{"x": v} for v in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 128, 131, M32)]
    if kind == "b":
        return [{"x": v, "y": w} for v, w in ((0x41, 0x42), (0, 0x61), (0x1F, 0), (0x141, 0xFF), (0x7E, 0x100))]
    if kind == "k":
        return [{"x": v} for v in (0, 1, 2, 3, 4, 7, 99, 100, 101, M32)]
    if kind == "mix":
        return [{"x": rng.choice(EDGE32), "y": rng.choice(EDGE32), "z": rng.randrange(0, 4), "q": rng.getrandbits(64)}
                for _ in range(8 * MULT)] + [{"x": 0, "y": 0, "z": 0x1F, "q": 0}]  # fmt: skip
    raise ValueError(kind)


def suite_parts():
    set_tables()
    s = Suite("t_display 원소", memory=memory(0), prep=prep_tbl())
    shown = {}
    for name, xps, _vk in PART_SPECS:

        @s.case(name)
        def _(t, name=name, xps=xps):
            parts = [make_part(xp, t) for xp in xps]
            shown[name] = dp.show(P1, "[", *parts, "]")

    s.build()
    m = s.machine
    dm = dispmodel.disp_model(m)
    rng = random.Random(61)
    for name, xps, vk in PART_SPECS:
        sh = shown.get(name)
        if sh is None:
            continue
        full = [XP("s", "[")] + list(xps) + [XP("s", "]")]
        for local_ in (0,):
            for env in value_sets(vk, rng):
                if sh.addr is None:  # 상수만 → 버퍼 없이 DisplayText(상수)
                    dm.clear()
                    r = run_env(s, name, env)
                    want = b"".join(ex_out(xp, env) for xp in full)
                    s.expect_true(name, r.error is None and dm.shown() == [want] and sh.string_id is not None
                                  and dm.string(sh.string_id) == want, "상수 %r" % env, "%r != %r" % (dm.shown(), want))
                    continue
                addr = dm.string_addr(sh.string_id)
                before = m.read_bytes(addr, sh.size + 4)
                dm.clear()
                r = run_env(s, name, env)
                label = "%s %r" % (name, env)
                texts = dm.shown()
                s.expect_true(name, r.error is None and len(texts) == 1, label + " 한 번", "%r %r" % (r.error, texts))
                if len(texts) != 1:
                    continue
                fresh, filled, errs, placed = model_buffer(full, sh.slots, env, 0, before[: sh.size])
                outs = [ex_out(xp, env) for xp in full]
                want_vis = RD.visible(filled) if any(o is None for o in outs) else RD.visible(b"".join(outs))
                s.expect_true(name, RD.visible(texts[0]) == want_vis, label + " 보이는 글",
                              "%r != %r" % (RD.visible(texts[0]), want_vis))  # fmt: skip
                after = m.read_bytes(addr, sh.size + 4)
                s.expect_true(name, not errs and fresh == sh.content, label + " 틀 규칙", "%r %r %r" % (errs, fresh, sh.content))
                s.expect_true(name, after[: sh.size] == filled, label + " 버퍼 바이트", "%r != %r" % (after[: sh.size], filled))
                s.expect_true(name, after[sh.size] == 0 and texts[0] == cstr(after), label + " NUL·표시 = 버퍼",
                              "%r" % after[sh.size :])  # fmt: skip
                slot_bytes = set()
                for off, size, _k, _a, _x in placed:
                    slot_bytes.update(range(off, off + size))
                keep = all(after[i] == fresh[i] for i in range(sh.size) if i not in slot_bytes)
                s.expect_true(name, keep, label + " 상수·맞춤 그대로", "%r" % after)
    # 25바이트 이름(NUL 없음)·NUL 뒤 잔재 — 자리를 넘지 않고 잔재를 쓰지 않는다 (캐시는 시작 때 읽으므로 restart)
    long_name = b"Y" * 25

    def prep_long(mm):
        prep_tbl()(mm)
        dmm = dispmodel.disp_model(mm)
        dmm.set_name_raw(4, long_name)
        dmm.set_name_raw(5, b"Short\0JUNKJUNK\0")

    s.restart(prep=prep_long)
    m = s.machine
    dm = dispmodel.disp_model(m)
    for nm in ("pname_var", "pname_var_cache"):
        for p, want in ((4, long_name), (5, b"Short")):
            s.reset()
            dm.clear()
            r = s.run(nm, {"x": p})
            texts = dm.shown()
            got = RD.visible(texts[0]) if texts else None
            s.expect_true(nm, r.error is None and got == "[" + want.decode() + "]", "긴 이름·잔재 p=%d" % p, "%r" % got)
    s.restart(prep=prep_tbl())
    ok = s.report()
    players.set_table()
    return ok


# ---------------------------------------------------------------------------------------------
# 1b. S3 8.1 기대값 (show 자리·TBL·13번째 줄)
# ---------------------------------------------------------------------------------------------

S3_PRESETS = {
    "dec16": (lambda v: numfmt.dp.dec16(v), 32), "decfw48": (lambda v: numfmt.dp.decfw48(v), 32),
    "hex12": (lambda v: numfmt.dp.hex12(v), 32), "dec20": (lambda v: numfmt.dp.dec20(v), 64),
    "man18_on": (lambda v: numfmt.dp.man18(v, color=True), 64), "man18_off": (lambda v: numfmt.dp.man18(v), 64),
    "per8": (lambda v: numfmt.dp.per8(v), 32), "per8_permil": (lambda v: numfmt.dp.per8(v, permil=True), 32),
    "dig2": (lambda v: numfmt.dp.dig2(v), 32), "gauge40": (lambda v: numfmt.dp.gauge40(v), 32),
}  # fmt: skip


def suite_s3():
    entries = {1: (b"?" * 32, 32), 2: (b"?" * 32, 32)}
    names = dict(NAMES)
    names[0] = b"GALAXY_BURST"

    def prep(m):
        dispmodel.install(m, tbl=entries, names=names)

    s = Suite("t_display S3 8.1", memory=memory(0), prep=prep)
    shown = {}
    for key, (mk, bits) in S3_PRESETS.items():

        @s.case("s3_" + key)
        def _(t, key=key, mk=mk, bits=bits):
            v = V(t, "q") if bits == 64 else t.var("x")
            shown[key] = dp.show(P1, mk(v))

    @s.case("name20")
    def _(t):
        shown["name20"] = dp.show(P1, numfmt.dp.name20(0))

    @s.case("tbl_layout")
    def _(t):
        dp.set_tbl(1, "\x04Lv ", numfmt.dp.dec16(t.var("x")), eos=False)

    @s.case("tbl_layout_eos")
    def _(t):
        dp.set_tbl(2, "\x04Lv ", t.var("x"))

    @s.case("er_layout")
    def _(t):
        shown["er"] = dp.show_line13(P1, "\x07HP ", t.var("x"), " / ", Byte(t.var("c")), "MAX")

    s.build()
    m = s.machine
    dm = dispmodel.disp_model(m)
    for key, rows in R.S3_EXPECT.items():
        if key not in S3_PRESETS:
            continue
        sh = shown[key]
        off, size, kind, align = sh.slots[0]
        for x, e in rows:
            want = R.expect_bytes(e)
            dm.clear()
            r = s.run("s3_" + key, {"qlo": x & M32, "qhi": x >> 32} if S3_PRESETS[key][1] == 64 else {"x": x})
            got = m.read_bytes(dm.string_addr(sh.string_id) + off, size)
            s.expect_true("s3_" + key, r.error is None and kind == "direct" and got == want.rjust(size, b"\r"),
                          "%s %r" % (key, x), "%r != %r (%s)" % (got, want, kind))  # fmt: skip
    sh = shown["name20"]
    r = s.run("name20")
    got = m.read_bytes(dm.string_addr(sh.string_id), 20)
    s.expect_true("name20", got == RD.hexb("0D 0D 0D 08 47 41 4C 41 58 59 5F 42 55 52 53 54 0D 0D 0D 0D"), "GALAXY_BURST", repr(got))
    els, env, orig, hx = RD.TBL_LAYOUT
    r = s.run("tbl_layout", {"x": env["v"]})
    s.expect_true("tbl_layout", dm.tbl_raw(1, extra=0) == RD.hexb(hx), "S3 4.3 예", repr(dm.tbl_raw(1, extra=0)))
    s.expect_true("tbl_layout", RD.dpl_tbl(els, env, orig) == RD.hexb(hx), "모델", "")
    r = s.run("tbl_layout_eos", {"x": env["v"]})
    s.expect_true("tbl_layout_eos", dm.tbl_raw(2, extra=0) == ("\x04Lv 42\u2009".encode() + b"\0").ljust(32, b"?"), "eudext 기본",
                  repr(dm.tbl_raw(2, extra=0)))  # fmt: skip
    els, env, hx, dev, vis = RD.ER_LAYOUT
    r = s.run("er_layout", {"x": env["v"], "c": env["c"]})
    raw = dm.line13_raw(222)
    buf, _d = RD.dpl_er(els, env)
    s.expect_true("er_layout", RD.visible(raw) == RD.visible(buf) == "HP 123 / MAX", "보이는 글 = DPL", repr(raw[:40]))
    s.expect_true("er_layout", raw[: shown["er"].size + 1] == b"\x07HP \r\r\r\r\r\r\r\r\r123 / \r\x1f\r\r\rMAX\0", "eudext 틀",
                  repr(raw[:40]))  # fmt: skip
    return s.report()


# ---------------------------------------------------------------------------------------------
# 2. 대상 × 이 PC 번호
# ---------------------------------------------------------------------------------------------


def target_specs():
    """이름 → (대상 만들기(t), 기대 집합(v, w, cp))."""
    allp = set(range(8))
    return {
        "p1": (lambda t: P1, lambda v, w, cp: {0}),
        "n3": (lambda t: 3, lambda v, w, cp: {3}),
        "p9": (lambda t: P9, lambda v, w, cp: {128}),
        "o130": (lambda t: 130, lambda v, w, cp: {130}),
        "var": (lambda t: t.var("v"), lambda v, w, cp: {v}),
        "cur": (lambda t: CurrentPlayer, lambda v, w, cp: {cp}),
        "force1": (lambda t: Force1, lambda v, w, cp: set(FORCES[0])),
        "force2": (lambda t: players.Force(2), lambda v, w, cp: set(FORCES[1])),
        "all": (lambda t: AllPlayers, lambda v, w, cp: allp),
        "humans": (lambda t: players.Humans, lambda v, w, cp: set(HUMANS)),
        "observers": (lambda t: players.Observers, lambda v, w, cp: set(OBS)),
        "everyone": (lambda t: players.Everyone, lambda v, w, cp: set(HUMANS) | set(OBS)),
        "list": (lambda t: [P2, P4], lambda v, w, cp: {1, 3}),
        "list_var": (lambda t: [P2, t.var("v"), t.var("w")], lambda v, w, cp: {1, v, w}),
        "targets": (lambda t: players.Targets(P1, players.Observers, t.var("w")), lambda v, w, cp: {0, w} | set(OBS)),
        "local": (lambda t: dp.LOCAL, lambda v, w, cp: set(LOCALS)),
        "local_list": (lambda t: [P3, dp.LOCAL], lambda v, w, cp: set(LOCALS)),
        "empty": (lambda t: [], lambda v, w, cp: set()),
    }


CONST_TARGETS = ("p1", "var", "cur", "humans", "observers", "local", "list_var", "everyone")


def suite_targets():
    set_tables()
    s = Suite("t_display 대상 × 이 PC", memory=memory(0), prep=prep_tbl())
    specs = target_specs()
    for key, (mk, _ref) in specs.items():

        @s.case("dyn_" + key)
        def _(t, mk=mk, key=key):
            cpv = t.var("cp")
            from eudplib import f_setcurpl

            f_setcurpl(cpv)
            dp.show(mk(t), "\x04dyn " + key + " ", t.var("x"), sound="dyn.wav")
            t.watch("rawcp", CP_ADDR)
            t.watch("cache", _compat.cpcache_var().getValueAddr())

    for key in CONST_TARGETS:
        mk = specs[key][0]

        @s.case("const_" + key)
        def _(t, mk=mk, key=key):
            cpv = t.var("cp")
            from eudplib import f_setcurpl

            f_setcurpl(cpv)
            dp.show(mk(t), "\x04const " + key, sound="c.wav")
            t.watch("rawcp", CP_ADDR)
            t.watch("cache", _compat.cpcache_var().getValueAddr())

    @s.case("players_display")
    def _(t):
        players.display([P2, t.var("v")], "\x04pl ", t.var("x"), every=1)

    s.build()
    rng = random.Random(7)
    for local_ in LOCALS:
        s.restart(local_player=local_)
        dm = dispmodel.disp_model(s.machine)
        combos = [(local_, 3, local_), (5, local_, 2), (128, 131, 129), (9, 0, local_), (M32, 130, 0)]
        combos += [(rng.choice(LOCALS + [8, 11]), rng.choice(LOCALS), rng.choice(LOCALS)) for _ in range(2 * MULT)]
        for key, (_mk, ref) in specs.items():
            for v, w, cpv in combos:
                for prefix in ("dyn_", "const_"):
                    name = prefix + key
                    if name not in s.cases:
                        continue
                    x = rng.getrandbits(32)
                    dm.clear()
                    r = run_env(s, name, {"v": v, "w": w, "cp": cpv, "x": x})
                    want = local_ in ref(v, w, cpv)
                    label = "local=%d v=%d w=%d cp=%d" % (local_, v, w, cpv)
                    shown = dm.shown()
                    ok = r.error is None and len(shown) == (1 if want else 0)
                    if ok and want and prefix == "dyn_":
                        ok = RD.visible(shown[0]) == "dyn %s %d" % (key, RD.s32(x))
                    if ok and want and prefix == "const_":
                        ok = RD.visible(shown[0]) == "const " + key
                    s.expect_true(name, ok, label + " 보임", "%r %r 기대 %r" % (r.error, shown, want))
                    wavs = dm.wavs(shown=True)
                    s.expect_true(name, len(wavs) == (1 if want else 0), label + " 소리", "%r" % wavs)
                    if prefix == "dyn_":
                        texts = dm.texts()
                        s.expect_true(name, len(texts) == (1 if want else 0), label + " 로컬 분기 1회", "%r" % texts)
                    cp_ok = r.values.get("rawcp") == cpv and r.values.get("cache") == cpv
                    s.expect_true(name, cp_ok, label + " CP 복구", "%r" % r.values)
        for v in (1, 5, 128, local_):
            dm.clear()
            r = s.run("players_display", {"v": v, "x": 77})
            want = local_ in {1, v}
            s.expect_true("players_display", r.error is None and len(dm.shown()) == int(want)
                          and (not want or RD.visible(dm.shown()[0]) == "pl 77"), "local=%d v=%d" % (local_, v),
                          "%r" % dm.shown())  # fmt: skip
    ok = s.report()
    players.set_table()
    return ok


# ---------------------------------------------------------------------------------------------
# 3. every / update_if / pin / pinned / sound
# ---------------------------------------------------------------------------------------------


def suite_options():
    s = Suite(
        "t_display 옵션", memory=memory(0),
        prep=lambda m: (prep_tbl()(m), chatmodel.install(m, strings=dispmodel.live_strings(m))),
    )  # fmt: skip

    @s.case("every3")
    def _(t):
        dp.show(P1, "e", t.var("x"), every=3)

    @s.case("every3_var")
    def _(t):
        dp.show(t.var("v"), "ev", t.var("x"), every=3)

    @s.case("every_local")
    def _(t):
        dp.show(dp.LOCAL, "el", t.var("x"), every=2)

    @s.case("upd_var")
    def _(t):
        dp.show(P1, "u", t.var("x"), update_if=t.var("f"))

    @s.case("upd_cond")
    def _(t):
        x = t.var("x")
        dp.show(P1, "c", x, update_if=x.AtLeast(10))

    @s.case("upd_list")
    def _(t):
        x, f = t.var("x"), t.var("f")
        dp.show(P1, "l", x, update_if=[x.AtLeast(10), f.Exactly(1)], every=2)

    @s.case("pin")
    def _(t):
        dp.show(P1, "pin", t.var("x"), pin=True)

    @s.case("nopin")
    def _(t):
        dp.show(P1, "nopin", t.var("x"))

    @s.case("pin_const")
    def _(t):
        dp.show([P1, P2], "pinc", pin=True)

    @s.case("pin_const_local")
    def _(t):
        dp.show(dp.LOCAL, "pinl", pin=True, sound=["a.wav", "b.wav"])

    @s.case("pinned")
    def _(t):
        x = t.var("x")
        with dp.pinned():
            dp.show(P1, "L1 ", x)
            dp.show(dp.LOCAL, "L2 ", x)
            with dp.pinned():
                dp.show(P1, "L3")
            dp.show(P1, "L4 ", x)

    @s.case("begin_end")
    def _(t):
        dp.begin_pinned()
        dp.show(P1, "B1")
        dp.show(P1, "B2 ", t.var("x"))
        dp.end_pinned()

    @s.case("sound_list")
    def _(t):
        dp.show(t.var("v"), "s", t.var("x"), sound=["one.wav", ("two.wav", "three.wav")])

    @s.case("bad_every", expect_build_error=EudextError, expect_message="every")
    def _(t):
        dp.show(P1, "x", t.var("x"), every=t.var("x"))

    @s.case("bad_upd", expect_build_error=EudextError, expect_message="update_if")
    def _(t):
        dp.show(P1, "x", t.var("x"), update_if=5)

    @s.case("bad_end", expect_build_error=EudextError, expect_message="begin_pinned")
    def _(t):
        dp.end_pinned()

    s.build()
    m = s.machine
    dm = dispmodel.disp_model(m)
    cm = chatmodel.chat_model(m)

    def run_seq(name, seq, extra=None):
        """seq = [x 값…] 을 사이클마다 → [(보인 글 목록)]"""
        out = []
        s.reset()
        for i, x in enumerate(seq):
            dm.clear()
            inp = {"x": x}
            if extra:
                inp.update(extra(i))
            r = s.run(name, inp)
            out.append((r.error, [RD.visible(z) for z in dm.shown()]))
        return out

    # every=3: 0,3,6 번째에 갱신, 표시는 매번
    seq = list(range(100, 110))
    got = run_seq("every3", seq)
    want = [(None, ["e%d" % seq[i - i % 3]]) for i in range(len(seq))]
    s.expect_true("every3", got == want, "주기 3", "%r" % got)
    got = run_seq("every_local", seq)
    want = [(None, ["el%d" % seq[i - i % 2]]) for i in range(len(seq))]
    s.expect_true("every_local", got == want, "LOCAL 주기 2", "%r" % got)
    # 대상이 아니던 PC 는 시계만 돌다가 대상이 되면 바로 갱신
    vs = [1, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0, 0]
    got = run_seq("every3_var", list(range(200, 212)), lambda i: {"v": vs[i]})
    want = []
    last = None
    ctr = 0
    for i, v in enumerate(vs):
        ctr = max(ctr - 1, 0)
        if v == 0:
            if ctr == 0:
                last = 200 + i
                ctr = 3
            want.append((None, ["ev%d" % last]))
        else:
            want.append((None, []))
    s.expect_true("every3_var", got == want, "대상 바뀜", "%r != %r" % (got, want))
    fs = [0, 1, 0, 1, 1, 0]
    got = run_seq("upd_var", [10, 11, 12, 13, 14, 15], lambda i: {"f": fs[i]})
    s.expect_true("upd_var", [g[1] for g in got] == [["u"], ["u11"], ["u11"], ["u13"], ["u14"], ["u14"]], "update_if 변수",
                  "%r" % got)
    got = run_seq("upd_cond", [3, 12, 5, 20, 9])
    s.expect_true("upd_cond", [g[1] for g in got] == [["c"], ["c12"], ["c12"], ["c20"], ["c20"]], "update_if 조건", "%r" % got)
    fs = [1, 1, 1, 0, 1, 1, 1, 1]
    got = run_seq("upd_list", [11, 12, 13, 14, 15, 16, 5, 18], lambda i: {"f": fs[i]})
    # every=2 와 조건(x ≥ 10 ∧ f == 1)이 모두 참일 때만. 시계는 조건과 상관없이 0 이 되면 기다린다
    want, cur, ctr = [], "", 0
    for i, x in enumerate([11, 12, 13, 14, 15, 16, 5, 18]):
        ctr = max(ctr - 1, 0)
        if ctr == 0 and x >= 10 and fs[i] == 1:
            cur = str(x)
            ctr = 2
        want.append(["l" + cur])
    s.expect_true("upd_list", [g[1] for g in got] == want, "every + update_if 목록", "%r != %r" % (got, want))
    # pin: 0x640B58 이 그대로, 같은 줄에 덮어쓴다
    for name, pinned_ in (("pin", True), ("nopin", False)):
        s.reset()
        cm.next_slot = 4
        slots = []
        for x in (1, 2, 3):
            r = s.run(name, {"x": x})
            slots.append(cm.next_slot)
        want_slots = [4, 4, 4] if pinned_ else [5, 6, 7]
        s.expect_true(name, slots == want_slots, "줄 번호", "%r" % slots)
        s.expect_true(name, cm.visible(4) == ("pin3" if pinned_ else "nopin1"), "줄 4 내용", repr(cm.visible(4)))
    for name, want_text in (("pin_const", "pinc"), ("pin_const_local", "pinl")):
        s.reset()
        cm.next_slot = 9
        for _ in range(3):
            dm.clear()
            r = s.run(name)
        s.expect_true(name, r.error is None and cm.next_slot == 9 and cm.visible(9) == want_text, "상수 pin",
                      "%r %r %r" % (r.error, cm.next_slot, cm.visible(9)))  # fmt: skip
    s.expect_true("pin_const_local", dm.wavs(shown=True) == [b"a.wav", b"b.wav"], "LOCAL 소리 2", "%r" % dm.wavs())
    for name, lines in (("pinned", ["L1 7", "L2 7", "L3", "L4 7"]), ("begin_end", ["B1", "B2 7"])):
        s.reset()
        cm.next_slot = 10
        for _ in range(2):
            r = s.run(name, {"x": 7})
        got = [cm.visible((10 + i) % 11) for i in range(len(lines))]
        # 안쪽 pinned 블록(L3)은 L3 를 찍고 줄을 되돌리므로 L4 가 같은 줄에 덮인다
        if name == "pinned":
            lines = ["L1 7", "L2 7", "L4 7"]
            got = got[:3]
        s.expect_true(name, r.error is None and cm.next_slot == 10 and got == lines, "고정 구역", "%r %r" % (cm.next_slot, got))
    # 소리 목록 (대상 PC 에서만)
    for v in (0, 1):
        s.reset()
        dm.clear()
        s.run("sound_list", {"v": v, "x": 1})
        want = [b"one.wav", b"two.wav", b"three.wav"] if v == 0 else []
        s.expect_true("sound_list", dm.wavs(shown=True) == want, "v=%d" % v, "%r" % dm.wavs())
    return s.report()


# ---------------------------------------------------------------------------------------------
# 4. 13번째 줄
# ---------------------------------------------------------------------------------------------

L13_SENT = bytes(range(0x41, 0x41 + 26)) * 9  # 줄 버퍼 앞에 채워 두는 보초 (234바이트)


def suite_line13():
    set_tables()
    s = Suite("t_display 13번째 줄", memory=memory(0), prep=prep_tbl())
    info = {}
    targets = {
        "c0": (lambda t: 0, lambda v, cp: [0]),
        "c3": (lambda t: P4, lambda v, cp: [3]),
        "var": (lambda t: t.var("v"), lambda v, cp: [v] if v <= 7 else []),
        "list": (lambda t: [P1, P3, t.var("v")], lambda v, cp: [0, 2] + ([v] if v <= 7 else [])),
        "force1": (lambda t: Force1, lambda v, cp: list(FORCES[0])),
        "all": (lambda t: AllPlayers, lambda v, cp: list(range(8))),
        "cur": (lambda t: CurrentPlayer, lambda v, cp: [cp]),
        "humans": (lambda t: players.Humans, lambda v, cp: [p for p in HUMANS]),
    }
    for key, (mk, _ref) in targets.items():

        @s.case("t_" + key)
        def _(t, mk=mk, key=key):
            from eudplib import f_setcurpl

            f_setcurpl(t.var("cp"))
            info["t_" + key] = dp.show_line13(mk(t), "\x08ERR \x04", t.var("x"), " ", key)
            t.watch("rawcp", CP_ADDR)

    @s.case("hold")
    def _(t):
        dp.show_line13([P2, t.var("v")], "hold", hold=(15, 5000))

    @s.case("hold_fn")
    def _(t):
        dp.show_line13(P3, "holdfn", hold=lambda p: [SetDeaths(p, SetTo, 77, 16)])

    @s.case("parts")
    def _(t):
        xps = L13_PARTS
        info["parts"] = dp.show_line13(P1, *[make_part(xp, t) for xp in xps])

    @s.case("max217")
    def _(t):
        info["max217"] = dp.show_line13(P1, "A" * 193, t.var("x"), "B" * 9)

    @s.case("over218", expect_build_error=EudextError, expect_message="217")
    def _(t):
        dp.show_line13(P1, "A" * 193, t.var("x"), "B" * 10)

    @s.case("over_const", expect_build_error=EudextError, expect_message="217")
    def _(t):
        dp.show_line13(P1, "가" * 73)

    @s.case("obs", expect_build_error=EudextError, expect_message="관전자")
    def _(t):
        dp.show_line13(players.Observers, "x")

    @s.case("obs130", expect_build_error=EudextError, expect_message="관전자")
    def _(t):
        dp.show_line13([P1, 130], "x")

    @s.case("local_target", expect_build_error=EudextError, expect_message="LOCAL")
    def _(t):
        dp.show_line13(dp.LOCAL, "x")

    @s.case("everyone", expect_build_error=EudextError, expect_message="관전자")
    def _(t):
        dp.show_line13(players.Everyone, "x")

    warned = {}

    @s.case("in_local")
    def _(t):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with local.only(P1):
                dp.show_line13(P1, "local")
        warned["in_local"] = [str(x.message) for x in w]

    s.build()
    rng = random.Random(13)
    s.expect_true("in_local", any("로컬 구역" in x for x in warned.get("in_local", [])), "경고", "%r" % warned)
    for local_ in (0, 2, 3, 5, 7, 128, 131):
        s.restart(local_player=local_)
        m = s.machine
        dm = dispmodel.disp_model(m)
        for key, (_mk, ref) in targets.items():
            for v, cpv in ((local_, 0), (3, local_ if local_ < 8 else 1), (8, 2), (128, 5), (rng.randrange(8), 6)):
                s.reset()
                m.write_bytes(0x641598 - 4, L13_SENT)
                dm.clear()
                x = rng.getrandbits(32)
                r = run_env(s, "t_" + key, {"v": v, "cp": cpv, "x": x})
                ccmu_want = ref(v, cpv)
                got = [p for p, _sh in dm.ccmu()]
                label = "local=%d v=%d cp=%d" % (local_, v, cpv)
                s.expect_true("t_" + key, r.error is None and sorted(got) == sorted(ccmu_want), label + " CCMU 대상",
                              "%r != %r %r" % (got, ccmu_want, r.error))  # fmt: skip
                if key not in ("list", "humans", "force1", "all"):
                    s.expect_true("t_" + key, got == ccmu_want, label + " CCMU 순서", "%r" % got)
                target_here = local_ in ccmu_want
                sh = info["t_" + key]
                raw = dm.line13_raw(222)
                if target_here:
                    want = sh.content  # 틀
                    want_vis = "ERR %d %s" % (RD.s32(x), key)
                    ok = RD.visible(raw) == want_vis and dm.line13_shown == ccmu_want.count(local_)
                    fresh, filled, errs, _placed = model_buffer(
                        [XP("s", "\x08ERR \x04"), XP("var", "x"), XP("s", " " + key)], sh.slots, {"x": x}, local_, sh.content)
                    ok = ok and raw[: sh.size] == filled and raw[sh.size] == 0 and not errs
                    s.expect_true("t_" + key, ok, label + " 13번째 줄 쓰기", "%r %r" % (raw[:60], dm.line13_shown))
                else:
                    s.expect_true("t_" + key, raw == L13_SENT[4:226] and dm.line13_shown == 0, label + " 로컬 쓰기 없음",
                                  "%r" % raw[:40])  # fmt: skip
                s.expect_true("t_" + key, m.read_bytes(0x641598 - 4, 4) == L13_SENT[:4], label + " 앞 보초", "")
                s.expect_true("t_" + key, r.values.get("rawcp") == cpv, label + " CP", "%r" % r.values)
                s.expect_true("t_" + key, m.dw(0x628438) != 0, label + " 0x628438 복원", hex(m.dw(0x628438)))
        # hold
        for v in (1, 4, 9):
            s.reset()
            r = s.run("hold", {"v": v})
            d = {p: m.dw(DEATH0 + 4 * (15 * 12 + p)) for p in range(8)}
            want = {p: (5000 if p in ({1} | ({v} if v <= 7 else set())) else 0) for p in range(8)}
            s.expect_true("hold", r.error is None and d == want, "v=%d" % v, "%r" % d)
        s.reset()
        r = s.run("hold_fn")
        s.expect_true("hold_fn", m.dw(DEATH0 + 4 * (16 * 12 + 2)) == 77, "fn(p)", "")
        # 여러 원소
        sh = info["parts"]
        for env in [{"x": rng.getrandbits(32), "y": rng.getrandbits(32), "z": rng.randrange(1, 4), "q": rng.getrandbits(64)}
                    for _ in range(6 * MULT)] + [{"x": 0, "y": 0, "z": 0, "q": 0}]:  # fmt: skip
            s.reset()
            m.write_bytes(0x641598 - 4, L13_SENT)
            dm.clear()
            r = run_env(s, "parts", env)
            raw = dm.line13_raw(222)
            if local_ == 0:
                fresh, filled, errs, _p = model_buffer(L13_PARTS, sh.slots, env, local_, sh.content)
                vis = RD.visible(b"".join(ex_out(xp, env, local_) or b"" for xp in L13_PARTS))
                s.expect_true("parts", r.error is None and not errs and raw[: sh.size] == filled and raw[sh.size] == 0
                              and RD.visible(raw) == vis, "local=0 %r" % env, "%r\n%r" % (raw[: sh.size + 1], filled))
            else:
                s.expect_true("parts", raw == L13_SENT[4:226], "local=%d 쓰기 없음" % local_, "")
        # 217 바이트 경계: 줄 버퍼(218) 밖 2바이트 보존
        s.reset()
        m.write_bytes(0x641598 - 4, L13_SENT)
        dm.clear()
        r = s.run("max217", {"x": M32})
        raw = dm.line13_raw(222)
        sh = info["max217"]
        if local_ == 0:
            s.expect_true("max217", sh.size == 217 and raw[217] == 0 and raw[218:222] == L13_SENT[4 + 218 : 4 + 222]
                          and RD.visible(raw) == "A" * 193 + "-1" + "B" * 9, "217B", "%r %r" % (sh.size, raw[190:]))  # fmt: skip
    ok = s.report()
    players.set_table()
    return ok


L13_PARTS = [
    XP("s", "\x07『 "), XP("man", "x", colors="dps", after=4), XP("s", "\x04개 "), XP("pname", 1), XP("byte", "z"),
    XP("s", "."), XP("var", "y"), XP("i64", "q"), XP("pick", "z", table=PICK3, default="?"), XP("s", " \x07』"),
]  # fmt: skip


# ---------------------------------------------------------------------------------------------
# 5. TBL
# ---------------------------------------------------------------------------------------------

TBL_ORIG = b"original tooltip text " * 3


def suite_tbl():
    entries = {i: (TBL_ORIG[:40], 120) for i in range(1, TBL_IDS + 1)}
    s = Suite("t_display TBL", memory=memory(0), prep=prep_tbl(entries))
    xps = [XP("s", "z\x02\x08HP "), XP("var", "x"), XP("s", " / "), XP("dec", "y", group=(3, ",")), XP("s", " "),
           XP("pname", 1), XP("s", " "), XP("local"), XP("byte", "z"), XP("pick", "z", table=PICK3, default="?"),
           XP("man", "y", colors="dps", after=4), XP("i64", "q")]  # fmt: skip
    combos = [(True, "\u2009"), (False, "\u2009"), (True, None), (False, None)]
    for i, (eos, tail) in enumerate(combos):

        @s.case("tbl_%d" % i)
        def _(t, i=i, eos=eos, tail=tail):
            dp.set_tbl(i + 1, *[make_part(xp, t) for xp in xps], tail=tail, eos=eos)

    @s.case("tbl_var_id")
    def _(t):
        dp.set_tbl(t.var("id"), "var id ", t.var("x"), tail="!")

    @s.case("tbl_const")
    def _(t):
        dp.set_tbl(7, "\x08\x08상수만 \x1c설정")

    @s.case("tbl_empty")
    def _(t):
        dp.set_tbl(8, tail=None)

    @s.case("tbl_every")
    def _(t):
        dp.set_tbl(9, "ev ", t.var("x"), every=2, update_if=t.var("f"))

    @s.case("tbl_cap")
    def _(t):
        t.out("n", dp.set_tbl(10, "cap ", t.var("x"), capacity=19))

    @s.case("tbl_cap_over", expect_build_error=EudextError, expect_message="자리 크기")
    def _(t):
        dp.set_tbl(10, "cap ", t.var("x"), capacity=18)

    @s.case("tbl_bad_id", expect_build_error=EudextError, expect_message="1~65535")
    def _(t):
        dp.set_tbl(0, "x")

    s.build()
    m = s.machine
    rng = random.Random(5)
    for local_ in (0, 1, 130):
        s.restart(local_player=local_)
        m = s.machine
        dm = dispmodel.disp_model(m)
        for i, (eos, tail) in enumerate(combos):
            for env in [{"x": rng.getrandbits(32), "y": rng.getrandbits(32), "z": rng.randrange(0, 5), "q": rng.getrandbits(64)}
                        for _ in range(5 * MULT)] + [{"x": 0, "y": 0, "z": 0, "q": 0}]:  # fmt: skip
                s.reset()
                r = s.run("tbl_%d" % i, env_inputs(env))
                body = b"".join(RD.ex_out(xp, env, NAMES, local_) for xp in xps)
                want = body + (tail.encode() if tail else b"") + (b"\0" if eos else b"")
                orig = (TBL_ORIG[:40] + b"\0").ljust(120, b"?") + b"????"
                want_raw = want + orig[len(want):]
                got = dm.tbl_raw(i + 1)
                s.expect_true("tbl_%d" % i, r.error is None and got == want_raw, "local=%d %r" % (local_, env),
                              "%r\n%r" % (got, want_raw))  # fmt: skip
        for tid in (11, 12, 59):
            s.reset()
            r = s.run("tbl_var_id", {"id": tid, "x": 42})
            s.expect_true("tbl_var_id", dm.tbl(tid) == b"var id 42!", "id=%d" % tid, repr(dm.tbl(tid)))
            s.expect_true("tbl_var_id", dm.tbl(tid - 1) == TBL_ORIG[:40], "옆 칸 그대로 %d" % tid, repr(dm.tbl(tid - 1)))
        s.reset()
        s.run("tbl_const")
        s.expect_true("tbl_const", dm.tbl(7) == "\x08\x08상수만 \x1c설정\u2009".encode(), "상수만", repr(dm.tbl(7)))
        s.run("tbl_empty")
        s.expect_true("tbl_empty", dm.tbl(8) == b"" and dm.tbl_raw(8)[1:40] == TBL_ORIG[1:40], "빈 원소 + NUL", repr(dm.tbl_raw(8)[:8]))
        s.reset()
        seq = []
        for k, (x, f) in enumerate(((1, 1), (2, 1), (3, 0), (4, 1), (5, 0), (6, 1))):
            s.run("tbl_every", {"x": x, "f": f})
            seq.append(dm.tbl(9))
        want, cur, ctr = [], None, 0
        for x, f in ((1, 1), (2, 1), (3, 0), (4, 1), (5, 0), (6, 1)):
            ctr = max(ctr - 1, 0)
            if ctr == 0 and f:
                cur = "ev %d\u2009" % x
                ctr = 2
            want.append(cur.encode() if cur else TBL_ORIG[:40])
        s.expect_true("tbl_every", seq == want, "every + update_if", "%r != %r" % (seq, want))
        s.reset()
        r = s.run("tbl_cap", {"x": M32})
        s.expect_true("tbl_cap", r["n"] == 19 and dm.tbl(10) == "cap -1\u2009".encode(), "capacity", "%r %r" % (r.values, dm.tbl(10)))
    return s.report()


# ---------------------------------------------------------------------------------------------
# 6. Template
# ---------------------------------------------------------------------------------------------


def suite_template():
    s = Suite("t_display Template", memory=memory(0), prep=prep_tbl())
    holder = {}

    def get(key, *parts, **kw):
        if key not in holder:
            holder[key] = dp.Template(*parts, **kw)
        return holder[key]

    @s.case("tmpl")
    def _(t):
        tp = get("a", "\x13", PName(0), " 남은 적 ", t.var("x"), "/", Int64(5), "\n", Man(t.var("y")))
        tp.update()
        DoActions(DisplayTextAll(tp.string), SetMissionObjectives(tp.string))

    @s.case("tmpl_every")
    def _(t):
        x = t.var("x")
        tp = get("b", "T", x, every=3, update_if=x.AtLeast(1))
        tp.update()
        DoActions(DisplayTextAll(tp.string_id))

    @s.case("tmpl_fn")
    def _(t):
        x = t.var("x")
        tp = get("c", "F", x, update_if=lambda: x.Exactly(7))
        tp.update()
        tp.update()  # 두 번 불러도 조건 객체가 겹치지 않는다
        DoActions(DisplayTextAll(tp.string))

    @s.case("tmpl_const")
    def _(t):
        tp = get("d", "상수 틀")
        tp.update()
        DoActions(DisplayTextAll(tp.string))

    s.build()
    rng = random.Random(3)
    for local_ in (1, 129):
        s.restart(local_player=local_)
        dm = dispmodel.disp_model(s.machine)
        for x, y in [(0, 0), (M32, 12345678)] + [(rng.getrandbits(32), rng.getrandbits(32)) for _ in range(4 * MULT)]:
            dm.clear()
            r = s.run("tmpl", {"x": x, "y": y})
            want = "%s 남은 적 %d/5\n%s" % (NAMES[0].decode(), RD.s32(x), RD.visible(R.man(y)))
            got = dm.shown()
            s.expect_true("tmpl", r.error is None and len(got) == 1 and RD.visible(got[0]) == want, "local=%d x=%d" % (local_, x),
                          "%r %r" % (got, want))  # fmt: skip
            s.expect_true("tmpl", s.machine.unknown.get(("act", 12), 0) >= 1, "SetMissionObjectives 액션", "")
        s.reset()
        seq = []
        xs = [0, 5, 6, 7, 0, 9, 10, 11, 12]
        for x in xs:
            dm.clear()
            s.run("tmpl_every", {"x": x})
            seq.append(RD.visible(dm.shown()[0]))
        want, cur, ctr = [], "T", 0
        for x in xs:
            ctr = max(ctr - 1, 0)
            if ctr == 0 and x >= 1:
                cur = "T%d" % x
                ctr = 3
            want.append(cur)
        s.expect_true("tmpl_every", seq == want, "local=%d" % local_, "%r != %r" % (seq, want))
        s.reset()
        seq = []
        for x in (1, 7, 8, 7):
            dm.clear()
            r = s.run("tmpl_fn", {"x": x})
            seq.append(RD.visible(dm.shown()[0]) if dm.shown() else r.error)
        s.expect_true("tmpl_fn", seq == ["F", "F7", "F7", "F7"], "update_if 함수", "%r" % seq)
        dm.clear()
        s.run("tmpl_const")
        s.expect_true("tmpl_const", [RD.visible(z) for z in dm.shown()] == ["상수 틀"], "상수 틀", "%r" % dm.shown())
    t = holder["a"]
    s.expect_true("tmpl", isinstance(t.string, int) and t.string == t.string_id and t.size == len(t.content), "속성", repr(t))
    return s.report()


# ---------------------------------------------------------------------------------------------
# 7. DPL 참조 모델 차등 (무작위 구조)
# ---------------------------------------------------------------------------------------------

STR_POOL = ["\x07HP ", " / ", "\x04골드 ", "\x1f", "abc", " ", "\x13\x08【 ", "킬: ", "\x12", ".", "\x02\x07원", "1)", "",
            "\x07『 \x1F은\x1C하", "Lv. ", "\x04개 소모하여 \x07강화"]


def gen_struct(rng, ctx, n_max=5):
    els, xps = [], []
    k = rng.randint(1, n_max)
    for i in range(k):
        name = "v%d" % i
        kinds = ["s", "v", "fwc", "hex", "w", "name", "byte", "setnum"]
        if ctx != "er":
            kinds += ["eper", "dig2", "gauge"]
        if ctx == "show":
            kinds += ["vlist"]
        kind = "s" if rng.random() < 0.35 else rng.choice(kinds)
        if kind == "s":
            sv = rng.choice(STR_POOL)
            els.append(RD.El("s", sv))
            xps.append(XP("s", sv))
        elif kind == "v":
            els.append(RD.El("v", name))
            xps.append(XP("dp", name, name="dec16") if ctx == "tbl" else XP("var", name))
        elif kind == "fwc":
            els.append(RD.El("v", name, fwc=True))
            xps.append(XP("dp", name, name="decfw48") if ctx == "tbl" else XP("dec", name, fullwidth=True))
        elif kind == "hex":
            els.append(RD.El("v", name, hex=True))
            if ctx == "tbl":
                xps.append(XP("dp", name, name="hex12"))
            elif ctx == "er":
                xps.append(XP("var", name))
            else:
                xps.append(XP("hex", name))
        elif kind == "w":
            els.append(RD.El("w", "q%d" % i))
            if ctx == "tbl" or rng.random() < 0.5:
                xps.append(XP("dp", "q%d" % i, name="dec20", nonneg=False))
            else:
                xps.append(XP("i64", "q%d" % i, nonneg=True))
        elif kind == "name":
            p = rng.randrange(7)
            els.append(RD.El("name", p))
            xps.append(XP("dp", p, name="name20") if ctx == "tbl" else XP("pname", p))
        elif kind == "byte":
            els.append(RD.El("byte", "b%d" % i))
            xps.append(XP("byte", "b%d" % i))
        elif kind == "vlist":
            names = ["b%d" % i, "c%d" % i]
            els.append(RD.El("vlist", names))
            xps.append(XP("bytes", names))
        elif kind == "setnum":
            color = rng.random() < 0.5
            els.append(RD.El("setnum", name, color=color))
            if ctx == "tbl":
                xps.append(XP("dp", name, name="man18", color=color))
            else:
                xps.append(XP("man", name, colors="dps", after=4) if color else XP("man", name))
        elif kind == "eper":
            pm = rng.random() < 0.3
            els.append(RD.El("eper", name, permil=pm))
            if ctx == "tbl":
                xps.append(XP("dp", name, name="per8", permil=pm, tbl=True))
            else:
                xps.append(XP("per", name, max=5000000 if pm else 100000))
        elif kind == "dig2":
            els.append(RD.El("dig2", name))
            xps.append(XP("dp", name, name="dig2"))
        elif kind == "gauge":
            els.append(RD.El("gauge", name, reset=True))
            xps.append(XP("dp", name, name="gauge40") if ctx == "tbl" else XP("gauge", name))
    return els, xps


def gen_env(rng, n=5):
    env = {}
    for i in range(n):
        env["v%d" % i] = rng.choice([rng.getrandbits(32), rng.randrange(1000), rng.choice(EDGE32)])
        env["q%d" % i] = rng.getrandbits(64) if rng.random() < 0.6 else rng.randrange(10**12)
        env["b%d" % i] = rng.randrange(1, 0x80)
        env["c%d" % i] = rng.randrange(0x20, 0x7F)
    return env


def fix_env(xps, env):
    env = dict(env)
    for xp in xps:
        if xp.kind == "i64" and xp.opt.get("nonneg"):
            env[xp.value] &= (1 << 63) - 1
    return env


def strip_opt(xps):
    out = []
    for xp in xps:
        o = {k: v for k, v in xp.opt.items() if k != "nonneg"}
        out.append(XP(xp.kind, xp.value, **o))
    return out


def suite_dpl():
    rng = random.Random(2024)
    n_struct = 24 * MULT
    structs = {ctx: [gen_struct(rng, ctx) for _ in range(n_struct)] for ctx in ("show", "er", "tbl")}
    entries = {i + 1: (b"", 400) for i in range(n_struct)}
    s = Suite("t_display DPL 차등", memory=memory(0), prep=prep_tbl(entries))
    shown = {}
    for ctx in ("show", "er", "tbl"):
        for i, (els, xps) in enumerate(structs[ctx]):
            parts_x = strip_opt(xps)

            @s.case("%s_%d" % (ctx, i))
            def _(t, ctx=ctx, i=i, parts_x=parts_x):
                parts = [make_part(xp, t) for xp in parts_x]
                if ctx == "show":
                    shown[(ctx, i)] = dp.show(P1, *parts)
                elif ctx == "er":
                    shown[(ctx, i)] = dp.show_line13(P1, *parts)
                else:
                    dp.set_tbl(i + 1, *parts, eos=False)

    s.build()
    m = s.machine
    dm = dispmodel.disp_model(m)
    n_env = 8 * MULT
    for ctx in ("show", "er", "tbl"):
        for i, (els, xps) in enumerate(structs[ctx]):
            name = "%s_%d" % (ctx, i)
            for _k in range(n_env):
                env = fix_env(xps, gen_env(rng))
                s.reset()
                dm.clear()
                r = run_env(s, name, env)
                if r.error:
                    s.expect_true(name, False, "실행", r.error)
                    continue
                if ctx == "show":
                    want = RD.visible(RD.dpl_display(els, env, NAMES))
                    got = RD.visible(dm.shown()[0]) if dm.shown() else None
                    s.expect_true(name, got == want, "보이는 글 %r" % els, "%r != %r" % (got, want))
                elif ctx == "er":
                    buf, _dev = RD.dpl_er(els, env, NAMES)
                    want = RD.visible(buf)
                    got = RD.visible(dm.line13_raw(222))
                    s.expect_true(name, got == want, "13번째 줄 보이는 글 %r" % els, "%r != %r" % (got, want))
                else:
                    orig = b"\0".ljust(400, b"?") + b"????"
                    want = RD.dpl_tbl(els, env, orig, NAMES)
                    got = dm.tbl_raw(i + 1)
                    s.expect_true(name, got == want, "TBL 바이트 %r" % els, "%r\n%r" % (got, want))
    return s.report()


# ---------------------------------------------------------------------------------------------
# 8. epScript
# ---------------------------------------------------------------------------------------------


def load_eps(name):
    d = os.path.join(_common.WORK, "t_display", "eps")
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


def eps_example(ck):
    for name in ("display_example", "display_ingame"):
        with open(os.path.join(EX, name + ".eps"), encoding="utf-8") as f:
            src = f.read()
        out, nerr = _compat.eps_compile(name + ".eps", src)
        ck.eq("eps 오류 수 " + name, nerr, 0)
        ck.true("eps 번역 " + name, out is not None)
        if name == "display_example" and out:
            for needle in ("dp.f_show(dp.LOCAL", "dp.f_show_line13(", "dp.f_set_tbl(", "dp.Template(", "dp.f_begin_pinned()",
                           "dp.f_end_pinned()", "dp.LocalName(", "nf.Man(", "sd.f_wrap(", "FlattenList(", "every=2"):  # fmt: skip
                ck.true("eps 번역에 " + needle, needle in out, needle)
    set_tables()
    LoadMap(BASE_MAP)
    CompressPayload(True)
    eps = load_eps("display_example")
    s = Suite("t_display epScript 예제", memory=memory(0), prep=prep_tbl({92: (b"", 80)}))

    @s.case("tick")
    def _(t):
        eps.gold << t.var("x")
        eps.hp << t.var("y")
        eps.gcp << t.var("v")
        eps.afterTriggerExec()

    s.build()
    pre, post = sd.parts(style="seed")
    for local_ in (0, 1, 4, 128):
        s.restart(local_player=local_)
        dm = dispmodel.disp_model(s.machine)
        for x, y, v in ((12345678, 7, 0), (0, M32, 1), (10**9, 42, 4), (5, 5, 128)):
            s.reset()
            dm.clear()
            r = s.run("tick", {"x": x, "y": y, "v": v})
            vis = [RD.visible(z) for z in dm.shown()]
            want = ["HP %d / 골드 %s" % (RD.s32(y), RD.visible(R.man(x, colors="dps", after=4)))]
            if local_ in HUMANS:
                want.append(RD.visible(pre.encode() + NAMES[local_] + " 님 차례".encode() + post.encode()))
            want.append("목표 %d" % RD.s32(x))
            s.expect_true("tick", r.error is None and vis == want, "local=%d x=%d" % (local_, x), "%r != %r %r" % (vis, want, r.error))
            line13 = RD.visible(dm.line13_raw(222))
            want13 = "골드 부족: %d" % RD.s32(y) if (local_ == v and local_ < 8) else ""
            s.expect_true("tick", line13 == want13, "local=%d v=%d 13번째 줄" % (local_, v), "%r != %r" % (line13, want13))
            s.expect_true("tick", [p for p, _sh in dm.ccmu()] == ([v] if v < 8 else []), "CCMU v=%d" % v, "%r" % dm.ccmu())
            tbl = dm.tbl(92)
            s.expect_true("tick", tbl == ("\x08자동사냥 \x1c%d\x04단계\u2009" % RD.s32(y)).encode(), "TBL", repr(tbl))
    players.set_table()
    return s.report()


def ingame_emulate(ck):
    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_display_ingame")
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, "display_ingame.eps"), os.path.join(work, "display_ingame.eps"))
    LoadMap(BASE_MULTI)
    CompressPayload(True)
    mod = build._load_plugin(os.path.join(work, "display_ingame.eps"), {})
    prog = emu.Program(mod.afterTriggerExec)
    names = ("frame", "okCount", "total", "lastBad")
    for n in names:
        prog.watch(n, getattr(mod, n))
    m = prog.build()
    mem = memory(0)
    mem["players"] = ["human"] * 4
    scmodel.install(m, **mem)
    dm = dispmodel.install(m, tbl={1: (b"Terran Marine", 64)}, names={0: b"Tester"})
    err = None
    try:
        for _ in range(2):
            m.cycle()
        seen = []
        for _ in range(1500):
            dm.clear()
            m.cycle()
            seen += [RD.visible(z) for z in dm.shown()]
    except emu.EmuError as e:
        err = str(e)
    got = {n: m.var(n) for n in names}
    print("  인게임 맵 에뮬레이션: %r" % got)
    ck.eq("ingame emu 오류", err, None)
    ck.eq("ingame emu 자체 점검", (got["okCount"], got["total"], got["lastBad"]), (INGAME_TOTAL, INGAME_TOTAL, 0))
    for tag in ["[E6-%d]" % i for i in range(1, 11)]:
        ck.true("ingame 줄 " + tag, any(tag in z for z in seen), tag)
    ck.true("ingame 자체 점검 줄", any(("점검 %d / %d" % (INGAME_TOTAL, INGAME_TOTAL)) in z for z in seen), "")


INGAME_TOTAL = 7


def euddraft_builds(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    for name in ("display_example", "display_ingame"):
        work = os.path.join(_common.WORK, "t_display_build_" + name)
        eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
        r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
        print("  " + r.summary())
        ck.true("euddraft " + name, r.ok, r.log[-2000:])
        ck.true("euddraft eps " + name, '[epScript] Compiling "%s.eps"' % name in r.log, r.log[-600:])


def bad_builds(ck):
    src = (
        "import eudext.display as dp;\n"
        "var hp;\n"
        "function barr() { dp.show(P1, [hp, 1]); }\n"
        "function bpinned() { dp.pinned(); }\n"
        "function blocal13() { dp.show_line13(dp.LOCAL, hp); }\n"
        "function bvar() { var t = dp.PName(0); }\n"
    )
    out, nerr = _compat.eps_compile("bad_display.eps", src)
    ck.true("bad eps 번역", out is not None and nerr == 0, str(nerr))
    if not out:
        return
    ns = {"__name__": "bad_display_eps"}
    exec(compile(out, "bad_display.eps.py", "exec"), ns)  # noqa: S102 — 시험용 번역문
    want = {"f_barr": "list(a, b)", "f_bpinned": "begin_pinned", "f_blocal13": "LOCAL", "f_bvar": ""}
    for fn, needle in want.items():
        LoadMap(BASE_MAP)
        CompressPayload(True)
        try:
            emu.Program(lambda fn=fn: ns[fn]()).build()
            ck.true("%s 빌드 오류" % fn, False, "빌드가 됐다")
        except Exception as e:  # noqa: BLE001
            ck.true("%s 빌드 오류" % fn, needle in str(e), repr(e))


# ---------------------------------------------------------------------------------------------
# 9. 파이썬 쪽
# ---------------------------------------------------------------------------------------------

PUBLIC = ["f_show", "f_show_line13", "f_set_tbl", "f_begin_pinned", "f_end_pinned", "pinned", "f_max_len", "Template",
          "PName", "LocalName", "Byte", "Bytes", "Pick", "Part"]  # fmt: skip


def python_checks(ck):
    LoadMap(BASE_MAP)
    with _compat.isolated_scope():
        _python_checks(ck)


def _python_checks(ck):
    v = EUDVariable()
    E = EudextError
    bad_parts = [None, True, 1.5, v.Exactly(0), EUDArray(3), ptr2s(0x1000), dp.LOCAL, 2**64, -(2**63) - 1,
                 StringBuffer(8)]  # fmt: skip
    for p in bad_parts:
        ck.raises("원소 오류 %r" % (p,), E, dp.show, P1, "x", p)
    ck.raises("Part.of 오류", E, Part.of, "abc", -1)
    ck.raises("Part.of 목록", E, Part.of, ["a"], 3)
    ck.raises("PName 8", E, PName, 8)
    ck.raises("PName 관전자", E, PName, 128)
    ck.raises("PName 문자열", E, PName, "Player 1")
    ck.raises("PName 색", E, PName, 0, color=0)
    ck.raises("PName 색 2", E, PName, 0, color="red")
    ck.raises("PName cache", E, PName, 0, cache="yes")
    ck.raises("Byte 범위", E, Byte, 300)
    ck.raises("Byte 조건", E, Byte, v.Exactly(1))
    ck.raises("Bytes 0개", E, Bytes)
    ck.raises("Bytes 65개", E, Bytes, *([1] * 65))
    ck.raises("Pick 표", E, Pick, v, "abc")
    ck.raises("Pick 빈 표", E, Pick, v, [])
    ck.raises("Pick 번호", E, Pick, v, {5000: "a"})
    ck.raises("Pick NUL", E, Pick, v, ["a\0b"])
    ck.raises("Pick 값", E, Pick, v, [1])
    ck.raises("Pick 번호 종류", E, Pick, 1.5, ["a"])
    ck.eq("Pick missing", Pick(9, ["a"], missing="없음").const_bytes(), "없음".encode())
    ck.raises("every 0", E, dp.show, P1, "x", v, every=0)
    ck.raises("every 문자열", E, dp.show, P1, "x", v, every="3")
    ck.raises("sound", E, dp.show, P1, "x", sound=5)
    ck.raises("상수만 update_if", E, dp.show, P1, "x", update_if="a")
    ck.raises("상수만 every", E, dp.show, P1, "x", every=-1)
    ck.raises("pin", E, dp.show, P1, "x", pin=2)
    ck.raises("대상 문자열", E, dp.show, "Player 1", "x", v)
    ck.raises("13 대상 문자열", E, dp.show_line13, "P1", "x")
    ck.raises("13 hold", E, dp.show_line13, P1, "x", hold=5)
    ck.raises("13 hold 값", E, dp.show_line13, P1, "x", hold=(15, "a"))
    ck.raises("tbl id", E, dp.set_tbl, 70000, "x")
    ck.raises("tbl id 문자열", E, dp.set_tbl, "92", "x")
    ck.raises("tbl tail", E, dp.set_tbl, 5, "x", tail=5)
    ck.raises("tbl eos", E, dp.set_tbl, 5, "x", eos="no")
    ck.raises("tbl capacity", E, dp.set_tbl, 5, "x", capacity=0)
    ck.raises("f_pinned", E, dp.f_pinned)
    ck.raises("LOCAL bool", E, bool, dp.LOCAL)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        dp.show(P1, "a\0b", v)
        dp.show(P1, "x" * 230, v)
    msgs = [str(x.message) for x in w]
    ck.true("NUL 경고", any("NUL" in x for x in msgs), repr(msgs))
    ck.true("줄 길이 경고", any("218" in x for x in msgs), repr(msgs))
    # max_len
    ck.eq("max_len 이음", dp.max_len("ab", v, PName(0), Byte(v), "가"), 2 + 11 + 26 + 1 + 3)
    ck.eq("max_len 틀", dp.max_len("ab", v, layout=True), 4 + 12)
    ck.eq("max_len 상수·Int64", dp.f_max_len(5, -1, Int64(12800000000), 12800000000), 1 + 2 + 20 + 11)
    # 반환 정보
    sh = dp.show(P1, "abc", v, " ", Man(v), PName(v, cache=True), Pick(v, ["x"]), Byte(3))
    ck.eq("slots", [(k, a) for _o, _s, k, a in sh.slots], [("direct", "right"), ("direct", "right"), ("namecache", "left"),
                                                             ("pick", "left")])  # fmt: skip
    ck.true("content", sh.content.startswith(b"abc\r") and sh.content.endswith(b"\x03") and sh.size == len(sh.content), repr(sh))
    ck.true("Shown repr", "dp.Shown" in repr(sh))
    sh = dp.show(P1, "const ", 5, -7, Byte(0x41), Pick(2, ["a", "b", "c"]), Dec(3), Bytes(1, 2))
    ck.eq("상수만 → 문자열 번호", (sh.addr, sh.size, isinstance(sh.string_id, int)), (None, 0, True))
    ck.eq("빈 show", dp.show(P1).string_id, None)
    # 서식 객체 상수 = 틀에 굽는다
    sh = dp.show(P1, Dec(12, width=4), v)
    ck.eq("상수 서식 굽기", sh.content[:4], b"\r\r12")
    # 문서 (3.12)
    for name in PUBLIC:
        obj = getattr(dp, name)
        doc = inspect.getdoc(obj) or ""
        if name in ("f_pinned",):
            continue
        for key in ("인자", "반환", "비용", "CP", "로컬", "epScript", "출처"):
            if name in ("Part",) and key == "반환":
                continue
            ck.true("문서 %s %s" % (name, key), key in doc, name)
    for alias, f in (("show", "f_show"), ("show_line13", "f_show_line13"), ("set_tbl", "f_set_tbl"),
                     ("begin_pinned", "f_begin_pinned"), ("end_pinned", "f_end_pinned"), ("max_len", "f_max_len")):  # fmt: skip
        ck.true("별칭 " + alias, getattr(dp, alias) is getattr(dp, f), alias)
    for n in dp.__all__:
        ck.true("__all__ " + n, hasattr(dp, n), n)
    # 비공개 API: display.py 는 eudplib 최상위 이름만
    with open(dp.__file__, encoding="utf-8") as f:
        src = f.read()
    ck.eq("eudplib 하위 모듈 import 없음", re.findall(r"from eudplib\.\S+ import|import eudplib\.", src), [])
    ck.true("_compat WP6b 이름", all(hasattr(_compat, n) for n in ("force_add_string", "forget_mapstring_addrs",
                                                                   "string_map_token", "_WP6b_REQUIRED")), "")  # fmt: skip
    for mod_name, attr in _compat._WP6b_REQUIRED:
        import importlib

        ck.true("WP6b 필요 이름 %s.%s" % (mod_name, attr), hasattr(importlib.import_module(mod_name), attr), attr)
    # players.display → display.f_show (players 쪽 lazy import 경로)
    sh = players.display(P1, "pl ", v)
    ck.true("players.display → dp.show", isinstance(sh, dp.Shown) and sh.addr is not None, repr(sh))
    sh = players.display(P1, "const", pin=True)
    ck.true("players.display 옵션", isinstance(sh, dp.Shown), repr(sh))
    ck.true("players.display 문서", "display.show" in (players.f_display.__doc__ or ""), "")
    # 빌드 되돌리기: 앞 LoadMap 의 문자열 번호만 지운다
    tok = _compat.string_map_token()
    ck.true("문자열 표 표식", tok is not None, "")


def repo_artifacts():
    found = []
    for dirpath, dirnames, filenames in os.walk(_common.PKG):
        rel = os.path.relpath(dirpath, _common.PKG)
        if rel.startswith("docs"):
            continue
        for d in dirnames:
            if d == "__epspy__":
                found.append(os.path.join(rel, d))
        for f in filenames:
            if f.endswith(".scx") and not (rel == "testing" and f.startswith("base")):
                found.append(os.path.join(rel, f))
            if f.startswith("display") and f.endswith(".pyc"):
                found.append(os.path.join(rel, f))
    return found


# ---------------------------------------------------------------------------------------------
# 비용
# ---------------------------------------------------------------------------------------------

COST_MEMORY = {"text": True, "units": {}}
X32 = [{"x": 0}, {"x": 7}, {"x": 123456}, {"x": M32}]


def _prep(fn):
    """비용 측정 전에 EUDFunc 본문을 만들어 둔다. 실패하면 빈 목록."""
    try:
        with _compat.isolated_scope():
            out = fn()
        for f in out:
            f.size()
        return out
    except Exception:  # noqa: BLE001 — 비용 표는 시험 실패와 따로
        return []


def _dec_funcs(**kw):
    def get():
        f, _plan, body = numfmt._tail(Dec(EUDVariable(), **kw)._spec)
        return [body, f]

    return _prep(get)


SIGNED12 = _dec_funcs(sign="-", width=12, bits=32)


def _tg(nparts, extra=0):
    """DESIGN 4.7 비용 목표: 대상 판정 ≤ 3 + 분기 ≤ 2 + 원소마다 ≤ 3 + 표시 1 (+ every·pin 1)."""
    return {"call": 3 + 2 + 3 * nparts + 1 + extra}


def _cc(name, fn, inputs=None, target=None, note="", funcs=()):
    """setup = 같은 코드(공용 본문·eudplib 복사 틀을 먼저 만든다) → 호출 자리 칸에는 그 자리 몫만 남는다."""
    inputs = X32 if inputs is None else inputs
    return CostCase(name, fn, inputs, funcs=funcs, target=target, note=note, setup=fn, setup_inputs=dict(inputs[0]))


COST_CASES = [
    _cc('show(P1, "HP ", v) (맨 변수)', lambda t: dp.show(P1, "\x07HP ", t.var("x")), target=_tg(1),
        funcs=SIGNED12, note="본문 = numfmt 공용 본문 + 꼬리(부호 폭 12)"),  # fmt: skip
    _cc('show(P1, "상수") (run_as)', lambda t: dp.show(P1, "\x07상수 글"), [{}], target=_tg(0)),
    _cc("show(LOCAL, 상수)", lambda t: dp.show(dp.LOCAL, "\x07상수 글"), [{}], target=_tg(0)),
    _cc("show(players.Humans, 상수)", lambda t: dp.show(players.Humans, "\x07상수 글"), [{}], target=_tg(0)),
    _cc("show(LOCAL, v, Man, v)", lambda t: dp.show(dp.LOCAL, "HP ", t.var("x"), " / ", Man(t.var("x")), " ", t.var("x")),
        target=_tg(3), note="원소 3개"),  # fmt: skip
    _cc("show(Everyone, v)", lambda t: dp.show(players.Everyone, "a ", t.var("x")), target=_tg(1)),
    _cc("show(변수 대상, v)", lambda t: dp.show(t.var("p"), "a ", t.var("x")), [dict(x, p=0) for x in X32],
        target=_tg(1)),  # fmt: skip
    _cc("show([P1, 변수], v)", lambda t: dp.show([P1, t.var("p")], "a ", t.var("x")), [dict(x, p=0) for x in X32],
        target=_tg(1), note="섞인 대상 = 1비트 깃발 판정"),  # fmt: skip
    _cc("show(P1, v, every=5)", lambda t: dp.show(P1, "a ", t.var("x"), every=5), target=_tg(1, 1)),
    _cc("show(P1, v, update_if=f)", lambda t: dp.show(P1, "a ", t.var("x"), update_if=t.var("f")),
        [dict(x, f=1) for x in X32], target=_tg(1, 1)),  # fmt: skip
    _cc("show(P1, v, pin=True)", lambda t: dp.show(P1, "a ", t.var("x"), pin=True), target=_tg(1, 1)),
    _cc("show(P1, v, sound=wav)", lambda t: dp.show(P1, "a ", t.var("x"), sound="a.wav"), target=_tg(1)),
    _cc("show(P1, Dec(v)) (넓혀 직접)", lambda t: dp.show(P1, Dec(t.var("x"))), funcs=_dec_funcs(width=10)),
    _cc('show(P1, Dec(v, width=5, fill="0")) (복사)', lambda t: dp.show(P1, Dec(t.var("x"), width=5, fill="0")),
        note="가변 길이·0 채움 → 버퍼 + 바이트 복사(바이트당 약 35)"),  # fmt: skip
    _cc("show(P1, Per(v, max=100000))", lambda t: dp.show(P1, Per(t.var("x"), max=100000))),
    _cc("show(P1, dp.man18(v, True))", lambda t: dp.show(P1, numfmt.dp.man18(t.var("x"), color=True))),
    _cc("show(P1, Int64)", lambda t: dp.show(P1, Int64.wrap(t.var("x"), t.var("x")))),
    _cc("show(P1, PName(0)) (실시간)", lambda t: dp.show(P1, PName(0)), [{}], note="비용 표 메모리는 이름 칸이 비어 있다 — 이름 바이트당 약 35 더 (t_display: 16바이트 555)"),
    _cc("show(P1, PName(p)) (실시간)", lambda t: dp.show(P1, PName(t.var("p"))), [{"p": 1}, {"p": 9}],
        funcs=_prep(lambda: [dp._name_info()]), note="빈 이름 칸 / p ≥ 8 — 이름 바이트당 약 35 더"),  # fmt: skip
    _cc("show(P1, PName(0, cache=True))", lambda t: dp.show(P1, PName(0, cache=True)), [{}],
        note="시작 때 한 번 채움(약 3,000 실행)은 세지 않음"),  # fmt: skip
    _cc("show(P1, PName(p, cache=True))", lambda t: dp.show(P1, PName(t.var("p"), cache=True)), [{"p": 1}, {"p": 9}]),
    _cc("show(P1, LocalName())", lambda t: dp.show(P1, LocalName()), [{}]),
    _cc("show(P1, Byte(v))", lambda t: dp.show(P1, Byte(t.var("x")))),
    _cc("show(P1, Bytes(v, 0x41, v))", lambda t: dp.show(P1, Bytes(t.var("x"), 0x41, t.var("x")))),
    _cc("show(P1, Pick(v, 3개))", lambda t: dp.show(P1, Pick(t.var("x"), ["zero", "one", "two"]))),
    _cc("show_line13(P1, v)", lambda t: dp.show_line13(P1, "\x08ERR ", t.var("x")), target=_tg(1, 1),
        note="CCMU 1 + 분기 1 + 틀 1 + 서식 1"),  # fmt: skip
    _cc("show_line13(변수, v)", lambda t: dp.show_line13(t.var("p"), "\x08ERR ", t.var("x")), [dict(x, p=0) for x in X32]),
    _cc("show_line13(players.Humans, v)", lambda t: dp.show_line13(players.Humans, "E ", t.var("x")),
        note="players.each"),  # fmt: skip
    _cc("set_tbl(5, 20바이트, v)", lambda t: dp.set_tbl(5, "\x08자동사냥 ", t.var("x"), "\x04단계"),
        note="바이트당 약 35 (상수 포함)"),  # fmt: skip
    _cc("set_tbl(5, 상수 40바이트)", lambda t: dp.set_tbl(5, "z\x02" + "a" * 38), [{}]),
    _cc("Template.update() (v)", lambda t: dp.Template("T ", t.var("x")).update()),
    _cc("begin_pinned + end_pinned", lambda t: (dp.begin_pinned(), dp.end_pinned()), [{}]),
]


def main():
    before = set(repo_artifacts())
    ck = Checker("t_display (python)")
    only = os.environ.get("DISPLAY_ONLY", "")
    oks = []
    steps = [
        ("parts", suite_parts), ("s3", suite_s3), ("targets", suite_targets), ("options", suite_options), ("line13", suite_line13),
        ("tbl", suite_tbl), ("template", suite_template), ("dpl", suite_dpl),
    ]  # fmt: skip
    for key, fn in steps:
        if not only or key in only:
            oks.append(fn())
    if not only or "eps" in only:
        oks.append(eps_example(ck))
    if not only or "python" in only:
        python_checks(ck)
    if not only or "misc" in only:
        ingame_emulate(ck)
        euddraft_builds(ck)
        bad_builds(ck)
    mine = sorted(set(repo_artifacts()) - before)
    ck.eq("repo clean", mine, [])
    oks.append(ck.report())
    finish(*oks)


if __name__ == "__main__":
    main()
