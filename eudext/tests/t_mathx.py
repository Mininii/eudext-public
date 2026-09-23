"""`mathx` 시험 (에뮬레이터 차등): lengthdir·Rotator·rotate3d·atan2·atan2_sc·to_dir256·isqrt·ilog2·sdiv/smod·ratio.

- 참조 구현 `tests/ref_mathx.py`(CtrigAsm Lua 원문을 줄 단위로 옮긴 것)와 **무작위 + 경계값** 차등.
  기본 실행은 함수마다 수천 개. `EUDEXT_MATHX_FULL=1` 이면 lengthdir·atan2 각 20만 개(+ Rotator 5만, 그 밖 늘림),
  고정밀 360 표(11.9MB)와 큰 주기(4096·65536) 빌드까지 돈다(수 분).
- S1 9.2(좌표·회전·크기)·S4 6.1(방향) 기대값, 표(Decimal 정확 반올림) = 플랫폼 libm 표, 원본 거친 8갈래 점프가
  결과를 바꾸지 않는다는 것, 상수 접기, 입력 검사, epScript 예제·인게임 맵의 번역·에뮬레이션·euddraft 빌드,
  헤드리스 TEP(tepc)로 CtrigAsm 표 식을 컴파일한 값 대조(C9-1 도구).

python tests/t_mathx.py              (EUDEXT_MATHX_FULL=1 이면 전체)
비용 표: python tools/cost.py tests/t_mathx.py [--append --out <파일> --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

from eudplib import EPD, CompressPayload, EUDLightVariable, EUDVariable, LoadMap, SeqCompute, SetTo  # noqa: E402

import ref_mathx as R  # noqa: E402
from eudext import _compat, cmp  # noqa: E402,F401
from eudext import mathx as mx  # noqa: E402
from eudext import mathx_tables as mt  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing import emu, scmodel  # noqa: E402
from eudext.testing.harness import BASE_MAP, EDGES32, Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

FULL = os.environ.get("EUDEXT_MATHX_FULL", "") not in ("", "0")
M32 = 0xFFFFFFFF
u32, s32 = R.u32, R.s32
EX = os.path.join(_common.PKG, "examples")
STATS = {"random": 0, "edge": 0}


def N(default, full):
    return full if FULL else default


# ---------------------------------------------------------------------------------------------
# 입력 생성기
# ---------------------------------------------------------------------------------------------

R_EDGES = (0, 1, -1, 2, 100, -100, 32767, -32767, -32768, 32768, -32769, 65535, 65536, 0x7FFFFFFF, 0x80000000, 0x80000001, 12345)
A_EDGES = (-1, 0, 1, 29, 30, 45, 89, 90, 91, 179, 180, 181, 269, 270, 271, 359, 360, 361, 719, 720, -89, -90, -91, -359, -360,
           -361, -720, -721, 0x7FFFFFFF, 0x80000000, 0x80000001, 12345678)
D_EDGES = (0, 1, -1, 2, -2, 5, 100, -100, 1000, -1000, 32767, -32767, -32768, 32768, 65535, -65535, 65536, -65536, 0x7FFFFFFF,
           0x80000000)


def g_radius(rng):
    x = rng.random()
    if x < 0.75:
        return rng.randint(-32768, 32767)
    if x < 0.87:
        return rng.randint(-200, 200)
    return rng.getrandbits(32)


def g_angle(rng):
    x = rng.random()
    if x < 0.4:
        return rng.randint(-1000, 1000)
    if x < 0.7:
        return rng.randint(0, 359)
    if x < 0.8:
        return rng.randint(-100000, 100000)
    return rng.getrandbits(32)


def g_delta(rng):
    x = rng.random()
    if x < 0.65:
        return rng.randint(-32768, 32767)
    if x < 0.8:
        return rng.randint(-60, 60)
    if x < 0.9:
        return rng.randint(-100000, 100000)
    if x < 0.93:
        return 0
    return rng.getrandbits(32)


def g_point(rng):
    x = rng.random()
    if x < 0.8:
        return rng.randint(-2000, 2000)
    if x < 0.95:
        return rng.randint(-32768, 32767)
    return rng.getrandbits(32)


def g_small_angle(rng):
    return rng.randint(-720, 720) if rng.random() < 0.85 else rng.getrandbits(32)


def g_any(rng):
    x = rng.random()
    if x < 0.3:
        return rng.randint(-300, 300)
    if x < 0.5:
        return rng.randint(-70000, 70000)
    return rng.getrandbits(32)


def g_cycle_angle(c):
    return lambda rng: rng.randint(-3 * c, 3 * c) if rng.random() < 0.8 else rng.getrandbits(32)


def pair(f):
    return lambda **kw: dict(zip(("c", "s"), f(**kw)))


# ---------------------------------------------------------------------------------------------
# 한 사이클에 여러 호출 (빠른 대량 차등)
# ---------------------------------------------------------------------------------------------


def batch_case(s, name, k, ins, outs, emit):
    """케이스 하나에 k 번 호출. emit(t, 입력 변수 목록) → 출력 값 목록."""

    @s.case(name)
    def _(t):
        for j in range(k):
            args = [t.var("%s%d" % (n, j)) for n in ins]
            res = emit(t, args)
            for n, v in zip(outs, res):
                t.out("%s%d" % (n, j), v)

    return (name, k, ins, outs)


def run_batch(s, spec, ref, gens, count, seed):
    """count 개를 k 개씩 묶어 돌린다. gens: 입력 이름 → 생성기. ref(*입력) → 출력 튜플. 호출마다 판정 1."""
    name, k, ins, outs = spec
    rng = random.Random(seed)
    ok = fail = 0
    done = 0
    while done < count:
        batch = [[gens[n](rng) & M32 for n in ins] for _ in range(k)]
        inputs = {"%s%d" % (n, j): batch[j][i] for j in range(k) for i, n in enumerate(ins)}
        r = s.run(name, inputs)
        for j in range(k):
            want = tuple(u32(v) for v in ref(*batch[j]))
            got = tuple(r.values.get("%s%d" % (n, j)) for n in outs) if not r.error else None
            good = got == want
            if good:
                ok += 1
            else:
                fail += 1
            if good:
                s.expect_true(name, True, "batch")
            else:
                s.expect_true(name, False, "batch %s" % dict(zip(ins, batch[j])), "got %r want %r %s" % (got, want, r.error or ""))
        done += k
    STATS["random"] += count
    return ok, fail


def diff_both(s, name, ref, edges, gens, n, seed=1, max_edges=2000):
    """경계값 조합 전부(max_edges 까지) + 무작위 n 개."""
    a = s.diff(name, ref, edges, n=0, edges=True, max_edges=max_edges)
    b = s.diff(name, ref, gens, n=n, seed=seed, edges=False) if n else (0, 0)
    total = 1
    for v in edges.values():
        total *= len(v)
    STATS["edge"] += min(total, max_edges)
    STATS["random"] += n
    return a[0] + b[0], a[1] + b[1]


# ---------------------------------------------------------------------------------------------
# lengthdir
# ---------------------------------------------------------------------------------------------

LD_CYCLES = (360, 4, 8, 12, 64, 256, 1024)
AK = (-721, -360, -91, -90, -1, 0, 1, 29, 30, 45, 60, 89, 90, 91, 135, 179, 180, 181, 269, 270, 271, 300, 359, 360, 450, 720,
      0x7FFFFFFF, 0x80000000)
AK8 = (0, 1, 2, 3, 4, 5, 6, 7, -1, 9)
RK = (0, 1, -1, 100, -100, 32767, -32767, -32768, 32768, 40000, -40000, 0x7FFFFFFF, 0x80000000)
PK8 = (0, 1, 3, 6, -1)
PR8 = (100, -32768, 40000, 0x80000000)
PB = 6                                   # 줄인 고정밀 표 시험: 반지름 6비트(|r| < 64)만 표
PB_EDGES = (0, 1, -1, 62, 63, 64, 65, -63, -64, -65, 100, -100, 32767, -32768, 40000, 0x7FFFFFFF, 0x80000000)


def ld_bits(r, a, c, bits=PB):
    """줄인 표의 정답: |r| < 2^bits 면 원본 고정밀, 아니면 표 없는 lengthdir."""
    rr = r & M32
    ab = (-rr) & M32 if rr >= 0x80000000 else rr
    return R.lengthdir_precise(r, a, c) if ab < (1 << bits) else R.lengthdir(r, a, c)


def rot_bits(x, y, a, c, bits=PB):
    xc, xs = ld_bits(x, a, c, bits)
    yc, ys = ld_bits(y, a, c, bits)
    return {"x2": (xc - ys) & M32, "y2": (xs + yc) & M32}


def build_ld(s):
    for c in LD_CYCLES:
        @s.case("ld_vv%d" % c)
        def _(t, c=c):
            cc, ss = mx.lengthdir(t.var("r"), t.var("a"), c)
            t.out("c", cc)
            t.out("s", ss)

    for i, a in enumerate(AK):
        @s.case("ld_vk%d" % i)
        def _(t, a=a):
            cc, ss = mx.lengthdir(t.var("r"), a)
            t.out("c", cc)
            t.out("s", ss)

    for i, a in enumerate(AK8):
        @s.case("ld8_vk%d" % i)
        def _(t, a=a):
            cc, ss = mx.lengthdir(t.var("r"), a, 8)
            t.out("c", cc)
            t.out("s", ss)

    for i, r in enumerate(RK):
        @s.case("ld_kv%d" % i)
        def _(t, r=r):
            cc, ss = mx.lengthdir(r, t.var("a"))
            t.out("c", cc)
            t.out("s", ss)

    @s.case("ld_ret")
    def _(t):
        c, sn = t.var("c"), t.var("s")
        mx.lengthdir(t.var("r"), t.var("a"), ret=[c, sn])
        mx.lengthdir(t.var("r2"), 30, ret=[t.var("c2"), t.var("s2")])

    @s.case("ld_kk_ret")
    def _(t):
        mx.lengthdir(-100, 30, ret=[t.var("c"), t.var("s")])

    @s.case("ld_light")
    def _(t):
        lr = EUDLightVariable()
        SeqCompute([(EPD(lr.getValueAddr()), SetTo, t.var("r"))])  # 읽기 전용 칸(Cell 같은 것) → 복사해서 쓴다
        cc, ss = mx.lengthdir(lr, t.var("a"))
        t.out("c", cc)
        t.out("s", ss)

    @s.case("ld_rep")
    def _(t):
        # 같은 각·다른 각을 번갈아: 마지막 각 기억이 맞게 갱신되는지
        a1, a2 = t.var("a1"), t.var("a2")
        for j, (rn, an) in enumerate((("r0", a1), ("r1", a1), ("r2", a2), ("r3", a1), ("r4", a2), ("r5", a2))):
            cc, ss = mx.lengthdir(t.var(rn), an)
            t.out("c%d" % j, cc)
            t.out("s%d" % j, ss)

    for c in (8, 16):
        @s.case("ldp_vv%d" % c)
        def _(t, c=c):
            cc, ss = mx.lengthdir(t.var("r"), t.var("a"), c, precise=True)
            t.out("c", cc)
            t.out("s", ss)

    for i, a in enumerate(PK8):
        @s.case("ldp8_vk%d" % i)
        def _(t, a=a):
            cc, ss = mx.lengthdir(t.var("r"), a, 8, precise=True)
            t.out("c", cc)
            t.out("s", ss)

    for i, r in enumerate(PR8):
        @s.case("ldp8_kv%d" % i)
        def _(t, r=r):
            cc, ss = mx.lengthdir(r, t.var("a"), 8, precise=True)
            t.out("c", cc)
            t.out("s", ss)

    # 줄인 고정밀 표 (precise=비트 수): |r| < 2^PB 는 원본 표 값, 그 밖은 표 없는 값
    for c in (8, 16):
        @s.case("ldb_vv%d" % c)
        def _(t, c=c):
            cc, ss = mx.lengthdir(t.var("r"), t.var("a"), c, precise=PB)
            t.out("c", cc)
            t.out("s", ss)

    for i, a in enumerate(PK8):
        @s.case("ldb8_vk%d" % i)
        def _(t, a=a):
            cc, ss = mx.lengthdir(t.var("r"), a, 8, precise=PB)
            t.out("c", cc)
            t.out("s", ss)

    @s.case("rotb8")
    def _(t):
        x2, y2 = mx.Rotator(t.var("a"), 8, precise=PB)(t.var("x"), t.var("y"))
        t.out("x2", x2)
        t.out("y2", y2)

    return batch_case(s, "ld_batch", 16, ("r", "a"), ("c", "s"), lambda t, a: mx.lengthdir(a[0], a[1]))


def run_ld(s, spec):
    for c in LD_CYCLES:
        ref = pair(lambda r, a, c=c: R.lengthdir(r, a, c))
        ae = A_EDGES if c == 360 else tuple(range(-c - 1, c + 2, max(1, c // 16))) + (0x80000000, 0x7FFFFFFF)
        diff_both(s, "ld_vv%d" % c, ref, {"r": R_EDGES, "a": ae}, {"r": g_radius, "a": g_cycle_angle(c)},
                  N(3000, 20000) if c == 360 else N(300, 3000), seed=c)
    for i, a in enumerate(AK):
        diff_both(s, "ld_vk%d" % i, pair(lambda r, a=a: R.lengthdir(r, a)), {"r": R_EDGES}, {"r": g_radius}, N(40, 400), seed=i)
    for i, a in enumerate(AK8):
        diff_both(s, "ld8_vk%d" % i, pair(lambda r, a=a: R.lengthdir(r, a, 8)), {"r": R_EDGES}, {"r": g_radius}, N(30, 300), seed=i)
    for i, r in enumerate(RK):
        diff_both(s, "ld_kv%d" % i, pair(lambda a, r=r: R.lengthdir(r, a)), {"a": A_EDGES}, {"a": g_angle}, N(40, 400), seed=i)
    s.diff("ld_ret", lambda r, a, r2: {"c": R.lengthdir(r, a)[0], "s": R.lengthdir(r, a)[1],
                                        "c2": R.lengthdir(r2, 30)[0], "s2": R.lengthdir(r2, 30)[1]},
           {"r": g_radius, "a": g_angle, "r2": g_radius}, n=N(100, 1000), edges=False)
    c, sn = R.lengthdir(-100, 30)
    s.check("ld_kk_ret", {}, {"c": c, "s": sn})
    s.diff("ld_light", pair(R.lengthdir), {"r": g_radius, "a": g_angle}, n=N(100, 1000), edges=False)

    def rep_ref(a1, a2, **rs):
        out = {}
        for j, an in enumerate((a1, a1, a2, a1, a2, a2)):
            out["c%d" % j], out["s%d" % j] = R.lengthdir(rs["r%d" % j], an)
        return out

    gens = {"a1": g_angle, "a2": g_angle}
    gens.update({"r%d" % j: g_radius for j in range(6)})
    s.diff("ld_rep", rep_ref, gens, n=N(200, 2000), edges=False)
    rng = random.Random(9)
    for _ in range(N(30, 300)):  # 같은 각 두 번 (기억 적중)
        a = g_angle(rng)
        inp = {"a1": a, "a2": a}
        inp.update({"r%d" % j: g_radius(rng) for j in range(6)})
        s.check("ld_rep", {k: v & M32 for k, v in inp.items()}, rep_ref(**inp), label="rep same %d" % a)
    for c in (8, 16):
        ref = pair(lambda r, a, c=c: R.lengthdir_precise(r, a, c))
        diff_both(s, "ldp_vv%d" % c, ref, {"r": R_EDGES + (0x7FFF, 0x8000, 0xFFFF7FFF), "a": tuple(range(-c - 1, c + 2)) + (0x80000000,)},
                  {"r": g_radius, "a": g_cycle_angle(c)}, N(500, 5000), seed=c)
    for i, a in enumerate(PK8):
        diff_both(s, "ldp8_vk%d" % i, pair(lambda r, a=a: R.lengthdir_precise(r, a, 8)), {"r": R_EDGES}, {"r": g_radius}, N(40, 400))
    for i, r in enumerate(PR8):
        diff_both(s, "ldp8_kv%d" % i, pair(lambda a, r=r: R.lengthdir_precise(r, a, 8)), {"a": tuple(range(-9, 10))},
                  {"a": g_cycle_angle(8)}, N(40, 400))
    for c in (8, 16):
        diff_both(s, "ldb_vv%d" % c, pair(lambda r, a, c=c: ld_bits(r, a, c)),
                  {"r": PB_EDGES, "a": tuple(range(-c - 1, c + 2)) + (0x80000000,)},
                  {"r": g_radius, "a": g_cycle_angle(c)}, N(500, 5000), seed=c)
    for i, a in enumerate(PK8):
        diff_both(s, "ldb8_vk%d" % i, pair(lambda r, a=a: ld_bits(r, a, 8)), {"r": PB_EDGES}, {"r": g_radius}, N(40, 400))
    diff_both(s, "rotb8", lambda x, y, a: rot_bits(x, y, a, 8),
              {"x": PB_EDGES, "y": (0, 63, 64, -64, 100), "a": tuple(range(-9, 10))},
              {"x": g_radius, "y": g_radius, "a": g_cycle_angle(8)}, N(300, 3000))
    t0 = time.time()
    n = N(8000, 200000)
    ok, fail = run_batch(s, spec, lambda r, a: R.lengthdir(r, a), {"r": g_radius, "a": g_angle}, n, seed=360)
    print("  lengthdir 무작위 %d 개: 통과 %d, 실패 %d (%.1fs)" % (n, ok, fail, time.time() - t0))
    return n, time.time() - t0, fail


def suite_ld():
    s = Suite("mathx lengthdir")
    spec = build_ld(s)
    s.build()
    n, dt, fail = run_ld(s, spec)
    return s.report(), (n, dt, fail)


# ---------------------------------------------------------------------------------------------
# atan2 · atan2_sc · to_dir256
# ---------------------------------------------------------------------------------------------

AT_CYCLES = (360, 4, 8, 16, 64, 256, 1024)
YK = (0, 1, -1, 100, -32768, 70000)
DIR_CYCLES = (360, 256, 64, 4, 12, 1024)


def build_at(s):
    for c in AT_CYCLES:
        @s.case("at_vv%d" % c)
        def _(t, c=c):
            t.out("t", mx.atan2(t.var("y"), t.var("x"), c))

    @s.case("atsc_vv")
    def _(t):
        t.out("t", mx.atan2_sc(t.var("y"), t.var("x")))

    for i, k in enumerate(YK):
        @s.case("at_kv%d" % i)
        def _(t, k=k):
            t.out("t", mx.atan2(k, t.var("x")))

        @s.case("at_vk%d" % i)
        def _(t, k=k):
            t.out("t", mx.atan2(t.var("y"), k))

        @s.case("atsc_kv%d" % i)
        def _(t, k=k):
            t.out("t", mx.atan2_sc(k, t.var("x")))

    @s.case("at_ret")
    def _(t):
        mx.atan2(t.var("y"), t.var("x"), ret=[t.var("t")])
        mx.atan2_sc(t.var("y"), t.var("x"), ret=[t.var("u")])
        mx.atan2(3, -4, ret=t.var("k"))

    for c in DIR_CYCLES:
        @s.case("dir_v%d" % c)
        def _(t, c=c):
            t.out("d", mx.to_dir256(t.var("a"), c))

    @s.case("dir_ret")
    def _(t):
        mx.to_dir256(t.var("a"), ret=[t.var("d")])
        mx.to_dir256(-45, ret=[t.var("k")])

    @s.case("bullet_to")
    def _(t):
        # S4 6.1: f_bullet_to 방향 = to_dir256(atan2(출발 − 목표)), 진행 = +128
        sx, sy, tx, ty = t.var("sx"), t.var("sy"), t.var("tx"), t.var("ty")
        a = mx.atan2(sy - ty, sx - tx)
        t.out("a", a)
        f = mx.to_dir256(a)
        t.out("f", f)

    return (batch_case(s, "at_batch", 16, ("y", "x"), ("t",), lambda t, a: (mx.atan2(a[0], a[1]),)),
            batch_case(s, "atsc_batch", 8, ("y", "x"), ("t",), lambda t, a: (mx.atan2_sc(a[0], a[1]),)))


S4_ROWS = (((100, 100), (200, 100), 180, 192), ((100, 100), (100, 200), 270, 0), ((100, 100), (0, 100), 0, 64),
           ((100, 100), (100, 0), 90, 128), ((100, 100), (200, 200), 226, 224), ((100, 100), (0, 0), 46, 96),
           ((100, 100), (101, 102), 244, 237), ((2048, 1548), (2048, 2048), 270, 0), ((0, 0), (32767, 1), 181, 192),
           ((100, 100), (100, 100), 90, 128))
S4_DIR = ((0, 64), (1, 64), (44, 95), (45, 96), (89, 127), (90, 128), (135, 160), (180, 192), (225, 224), (270, 0), (315, 32),
          (359, 63), (360, 64))


def run_at(s, specs):
    for c in AT_CYCLES:
        diff_both(s, "at_vv%d" % c, lambda y, x, c=c: {"t": R.atan2(y, x, c)}, {"y": D_EDGES, "x": D_EDGES},
                  {"y": g_delta, "x": g_delta}, N(3000, 20000) if c == 360 else N(300, 3000), seed=c)
    diff_both(s, "atsc_vv", lambda y, x: {"t": R.atan2_x(y, x)}, {"y": D_EDGES, "x": D_EDGES}, {"y": g_delta, "x": g_delta},
              N(1000, 10000))
    for i, k in enumerate(YK):
        diff_both(s, "at_kv%d" % i, lambda x, k=k: {"t": R.atan2(k, x)}, {"x": D_EDGES}, {"x": g_delta}, N(40, 400), seed=i)
        diff_both(s, "at_vk%d" % i, lambda y, k=k: {"t": R.atan2(y, k)}, {"y": D_EDGES}, {"y": g_delta}, N(40, 400), seed=i)
        diff_both(s, "atsc_kv%d" % i, lambda x, k=k: {"t": R.atan2_x(k, x)}, {"x": D_EDGES}, {"x": g_delta}, N(20, 200), seed=i)
    s.diff("at_ret", lambda y, x: {"t": R.atan2(y, x), "u": R.atan2_x(y, x), "k": R.atan2(3, -4)},
           {"y": g_delta, "x": g_delta}, n=N(100, 1000), edges=False)
    for c in DIR_CYCLES:
        diff_both(s, "dir_v%d" % c, lambda a, c=c: {"d": R.to_dir256(a, c)}, {"a": A_EDGES + tuple(range(-c, c + 1, max(1, c // 32)))},
                  {"a": g_cycle_angle(c)}, N(300, 3000), seed=c)
    s.diff("dir_ret", lambda a: {"d": R.to_dir256(a), "k": R.to_dir256(-45)}, {"a": g_angle}, n=N(50, 500), edges=False)
    for a, d in S4_DIR:
        s.check("dir_v360", {"a": a}, {"d": d}, label="S4 6.1 to_dir256(%d)" % a)
    for (sxy, txy, a, f) in S4_ROWS:
        s.check("bullet_to", {"sx": sxy[0], "sy": sxy[1], "tx": txy[0], "ty": txy[1]}, {"a": a, "f": f},
                label="S4 6.1 %r→%r" % (sxy, txy))
    t0 = time.time()
    n = N(8000, 200000)
    ok, fail = run_batch(s, specs[0], lambda y, x: (R.atan2(y, x),), {"y": g_delta, "x": g_delta}, n, seed=2)
    print("  atan2 무작위 %d 개: 통과 %d, 실패 %d (%.1fs)" % (n, ok, fail, time.time() - t0))
    n2 = N(1000, 20000)
    run_batch(s, specs[1], lambda y, x: (R.atan2_x(y, x),), {"y": g_delta, "x": g_delta}, n2, seed=3)
    return n, time.time() - t0, fail


def suite_at():
    s = Suite("mathx atan2")
    specs = build_at(s)
    s.build()
    res = run_at(s, specs)
    return s.report(), res


# ---------------------------------------------------------------------------------------------
# Rotator · rotate3d
# ---------------------------------------------------------------------------------------------

ROT_K = (90, 45, 30, -30, 180, 135, 1, 0, 270, 359, -721, 0x80000000)
S1_LD = (((32, 0), (32, 0)), ((32, 45), (22, 22)), ((-32, 90), (0, -32)), ((100, -90), (0, -100)), ((100, 450), (0, 100)),
         ((100, 359), (99, -1)), ((100, 360), (100, 0)), ((-100, 30), (-86, -49)), ((32767, 45), (23169, 23169)))
S1_ROT = (((0, -32, 90), (32, 0)), ((32, 0, 45), (22, 22)), ((27, -16, 30), (30, 0)), ((27, -16, -30), (16, -26)),
          ((0, -32, 180), (0, 32)), ((64, 64, 45), (0, 90)), ((-48, 20, 135), (19, -47)), ((100, 0, 1), (99, 1)))
S1_SIZE = (((27, -16), 150, (40, -24)), ((-33, 33), 50, (-16, 16)), ((7, -7), 0, (0, 0)), ((100, -100), 255, (255, -255)),
           ((1, -1), 99, (0, 0)))
R3_K = ((30, 45, 60), (90, None, 90), (None, 135, None), (None, None, -30), (359, 1, 180))


def build_rot(s):
    @s.case("rot_v")
    def _(t):
        rot = mx.Rotator(t.var("a"))
        x2, y2 = rot(t.var("x"), t.var("y"))
        t.out("rx", x2)
        t.out("ry", y2)

    @s.case("rot_set")
    def _(t):
        rot = mx.Rotator()
        rot.set(t.var("a"))
        x2, y2 = rot.rotate(t.var("x"), t.var("y"))
        t.out("rx", x2)
        t.out("ry", y2)
        c, sn = rot.lengthdir(t.var("r"))
        t.out("c", c)
        t.out("s", sn)
        rot.angle += 5  # 속성 통로 (epScript `rot.angle += 5;`)
        x3, y3 = rot(t.var("x"), t.var("y"), ret=[t.var("rx5"), t.var("ry5")])
        t.out("k1", rot(100, 0)[0])

    rot_two = []

    for own in (False, True):
        @s.case("rot_two" + ("_own" if own else ""))
        def _(t, own=own):
            # 변수 각 Rotator 둘을 점마다 번갈아: 공유 본문(매번 다시 준비) / 저마다 본문 — 값은 같아야 한다
            r1, r2 = mx.Rotator(t.var("a1"), own=own), mx.Rotator(t.var("a2"), own=own)
            rot_two.extend((r1, r2))
            for j in range(4):
                rot = r1 if j % 2 == 0 else r2
                x2, y2 = rot(t.var("x%d" % j), t.var("y%d" % j))
                t.out("rx%d" % j, x2)
                t.out("ry%d" % j, y2)
            # 공유 본문이면 lengthdir 과 섞어도 맞아야 한다
            c, sn = mx.lengthdir(t.var("x0"), t.var("a2"))
            t.out("c", c)
            x3, y3 = r1(t.var("x1"), t.var("y1"))
            t.out("rx9", x3)

    for i, a in enumerate(ROT_K):
        @s.case("rot_k%d" % i)
        def _(t, a=a):
            rot = mx.Rotator(a)
            x2, y2 = rot(t.var("x"), t.var("y"))
            t.out("rx", x2)
            t.out("ry", y2)
            c, sn = rot.lengthdir(t.var("x"))
            t.out("c", c)
            t.out("s", sn)

    @s.case("rot_kk")
    def _(t):
        rot = mx.Rotator(-30)
        x2, y2 = rot(27, -16)
        t.out("rx", x2)
        t.out("ry", y2)
        rot(27, -16, ret=[t.var("qx"), t.var("qy")])

    for c in (16,):
        @s.case("rotp_v%d" % c)
        def _(t, c=c):
            rot = mx.Rotator(t.var("a"), c, precise=True)
            x2, y2 = rot(t.var("x"), t.var("y"))
            t.out("rx", x2)
            t.out("ry", y2)

        @s.case("rotp_k%d" % c)
        def _(t, c=c):
            rot = mx.Rotator(3, c, precise=True)
            x2, y2 = rot(t.var("x"), t.var("y"))
            t.out("rx", x2)
            t.out("ry", y2)

    @s.case("r3_vvv")
    def _(t):
        X, Y, Z = mx.rotate3d(t.var("x"), t.var("y"), t.var("a"), t.var("b"), t.var("c"))
        t.out("X", X)
        t.out("Y", Y)
        t.out("Z", Z)

    for i, (a, b, c) in enumerate(R3_K):
        @s.case("r3_k%d" % i)
        def _(t, a=a, b=b, c=c):
            X, Y, Z = mx.rotate3d(t.var("x"), t.var("y"), a, b, c)
            t.out("X", X)
            t.out("Y", Y)
            t.out("Z", Z)

    @s.case("r3_mix")
    def _(t):
        X, Y, Z = mx.rotate3d(t.var("x"), t.var("y"), 30, None, t.var("c"))
        t.out("X", X)
        t.out("Y", Y)
        t.out("Z", Z)
        X2, Y2, Z2 = mx.rotate3d(t.var("x"), t.var("y"), t.var("a"), 45, None, ret=[t.var("X2"), t.var("Y2"), t.var("Z2")])
        X3, Y3, Z3 = mx.rotate3d(t.var("x"), t.var("y"))
        t.out("X3", X3)
        t.out("Y3", Y3)
        t.out("Z3", Z3)
        X4, Y4, Z4 = mx.rotate3d(27, -16, t.var("a"), None, None)
        t.out("X4", X4)
        t.out("Y4", Y4)

    @s.case("r3_own")
    def _(t):
        X, Y, Z = mx.rotate3d(t.var("x"), t.var("y"), t.var("a"), t.var("b"), t.var("c"), own=True)
        t.out("X", X)
        t.out("Y", Y)
        t.out("Z", Z)

    @s.case("r3_p16")
    def _(t):
        X, Y, Z = mx.rotate3d(t.var("x"), t.var("y"), t.var("a"), t.var("b"), t.var("c"), 16, precise=True)
        t.out("X", X)
        t.out("Y", Y)
        t.out("Z", Z)

    @s.case("size_s1")
    def _(t):
        # S1 6.3-1: 크기 = ratio(x, S, 100) (CA_RatioXY)
        t.out("rx", mx.ratio(t.var("x"), t.var("S"), 100))
        t.out("ry", mx.ratio(t.var("y"), t.var("S"), 100))

    def rot_emit(t, a):
        # 한 사이클에 각 하나(첫 입력의 a)로 8점 — 사이클마다 준비 한 번 (spawn 식)
        if not hasattr(rot_emit, "rot"):
            rot_emit.rot = mx.Rotator()
            rot_emit.first = a[0]
            rot_emit.rot.set(a[0])
        return rot_emit.rot(a[1], a[2])

    spec = batch_case(s, "rot_batch", 8, ("a", "x", "y"), ("rx", "ry"), rot_emit)
    spec3 = batch_case(s, "r3_batch", 4, ("x", "y", "a", "b", "c"), ("X", "Y", "Z"),
                       lambda t, a: mx.rotate3d(a[0], a[1], a[2], a[3], a[4]))
    return spec, spec3, rot_two


def run_rot(s, specs):
    spec, spec3, _two = specs
    g = {"x": g_point, "y": g_point, "a": g_small_angle}
    ref = lambda x, y, a: dict(zip(("rx", "ry"), R.rotate(x, y, a)))  # noqa: E731
    diff_both(s, "rot_v", ref, {"x": (0, 27, -16, 32767, -32768, 40000, 0x80000000), "y": (0, -32, 64, 32767, -40000),
                                "a": A_EDGES}, g, N(1500, 15000))

    def set_ref(x, y, a, r):
        rx, ry = R.rotate(x, y, a)
        c, sn = R.lengthdir(r, a)
        rx5, ry5 = R.rotate(x, y, u32(a + 5))
        return {"rx": rx, "ry": ry, "c": c, "s": sn, "rx5": rx5, "ry5": ry5, "k1": R.rotate(100, 0, u32(a + 5))[0]}

    s.diff("rot_set", set_ref, {"x": g_point, "y": g_point, "a": g_small_angle, "r": g_radius}, n=N(300, 3000), edges=False)

    def two_ref(a1, a2, **p):
        out = {}
        for j in range(4):
            out["rx%d" % j], out["ry%d" % j] = R.rotate(p["x%d" % j], p["y%d" % j], a1 if j % 2 == 0 else a2)
        return out

    gens = {"a1": g_small_angle, "a2": g_small_angle}
    gens.update({"%s%d" % (n, j): g_point for j in range(4) for n in "xy"})
    def two_ref2(a1, a2, **p):
        out = two_ref(a1, a2, **p)
        out["c"] = R.lengthdir(p["x0"], a2)[0]
        out["rx9"] = R.rotate(p["x1"], p["y1"], a1)[0]
        return out

    s.diff("rot_two", two_ref2, gens, n=N(200, 2000), edges=False)
    s.diff("rot_two_own", two_ref2, gens, n=N(200, 2000), edges=False)
    for i, a in enumerate(ROT_K):
        def kref(x, y, a=a):
            rx, ry = R.rotate(x, y, a)
            c, sn = R.lengthdir(x, a)
            return {"rx": rx, "ry": ry, "c": c, "s": sn}

        diff_both(s, "rot_k%d" % i, kref, {"x": R_EDGES, "y": (0, -16, 32767, -32768, 40000)}, {"x": g_point, "y": g_point},
                  N(60, 600), seed=i)
    for (x, y, a), (ex, ey) in S1_ROT:
        s.check("rot_v", {"x": x & M32, "y": y & M32, "a": a & M32}, {"rx": ex, "ry": ey}, label="S1 9.2 rotate %r" % ((x, y, a),))
    for (r, a), (ec, es) in S1_LD:
        s.check("rot_set", {"x": 0, "y": 0, "a": a & M32, "r": r & M32}, {"c": ec, "s": es}, label="S1 9.2 lengthdir %r" % ((r, a),))
    s.check("rot_kk", {}, {"rx": 16, "ry": -26, "qx": 16, "qy": -26}, label="S1 9.2 (27,-16,-30) 상수")
    for c in (16,):
        diff_both(s, "rotp_v%d" % c, lambda x, y, a, c=c: dict(zip(("rx", "ry"), R.rotate(x, y, a, c, True))),
                  {"x": (0, 1, -1, 32767, -32768), "y": (0, 5, 0x80000000), "a": tuple(range(-17, 18, 3))},
                  {"x": g_point, "y": g_point, "a": g_cycle_angle(c)}, N(300, 3000))
        diff_both(s, "rotp_k%d" % c, lambda x, y, c=c: dict(zip(("rx", "ry"), R.rotate(x, y, 3, c, True))),
                  {"x": R_EDGES, "y": (0, -7)}, {"x": g_point, "y": g_point}, N(100, 1000))
    r3ref = lambda x, y, a, b, c: dict(zip("XYZ", R.rotate3d(x, y, a, b, c)))  # noqa: E731
    diff_both(s, "r3_vvv", r3ref, {"x": (0, 27, -48, 32767), "y": (0, -16, 20), "a": (0, 30, -1), "b": (0, 45, 270),
                                   "c": (0, 60, 359)}, {"x": g_point, "y": g_point, "a": g_small_angle, "b": g_small_angle,
                                                         "c": g_small_angle}, N(500, 5000))
    for i, (a, b, c) in enumerate(R3_K):
        diff_both(s, "r3_k%d" % i, lambda x, y, a=a, b=b, c=c: dict(zip("XYZ", R.rotate3d(x, y, a, b, c))),
                  {"x": (0, 27, -48, 40000), "y": (0, -16, 20)}, {"x": g_point, "y": g_point}, N(60, 600), seed=i)

    def mix_ref(x, y, a, c):
        X, Y, Z = R.rotate3d(x, y, 30, None, c)
        X2, Y2, Z2 = R.rotate3d(x, y, a, 45, None)
        X4, Y4, _Z4 = R.rotate3d(27, -16, a, None, None)
        return {"X": X, "Y": Y, "Z": Z, "X2": X2, "Y2": Y2, "Z2": Z2, "X3": u32(x), "Y3": u32(y), "Z3": 0, "X4": X4, "Y4": Y4}

    s.diff("r3_mix", mix_ref, {"x": g_point, "y": g_point, "a": g_small_angle, "c": g_small_angle}, n=N(200, 2000), edges=False)
    s.diff("r3_own", r3ref, {"x": g_point, "y": g_point, "a": g_small_angle, "b": g_small_angle, "c": g_small_angle},
           n=N(200, 2000), edges=False)
    s.diff("r3_p16", lambda x, y, a, b, c: dict(zip("XYZ", R.rotate3d(x, y, a, b, c, 16, True))),
           {"x": g_point, "y": g_point, "a": g_cycle_angle(16), "b": g_cycle_angle(16), "c": g_cycle_angle(16)},
           n=N(200, 2000), edges=False)
    for (xy, S, (ex, ey)) in S1_SIZE:
        s.check("size_s1", {"x": xy[0] & M32, "y": xy[1] & M32, "S": S}, {"rx": ex, "ry": ey}, label="S1 9.2 size %r" % ((xy, S),))
    s.diff("size_s1", lambda x, y, S: {"rx": R.ratio(x, S, 100), "ry": R.ratio(y, S, 100)},
           {"x": lambda r: r.randint(-2000, 2000), "y": lambda r: r.randint(-2000, 2000), "S": lambda r: r.randint(0, 255)},
           n=N(300, 3000), edges=False)
    # 사이클마다 각 하나(8점) — 배치 첫 입력의 a 가 그 사이클의 각
    t0 = time.time()
    n = N(1600, 50000)
    name, k, ins, outs = spec
    rng = random.Random(11)
    fail = 0
    for _ in range(n // k):
        a = g_small_angle(rng)
        pts = [(g_point(rng), g_point(rng)) for _ in range(k)]
        inputs = {}
        for j, (x, y) in enumerate(pts):
            inputs.update({"a%d" % j: a & M32, "x%d" % j: x & M32, "y%d" % j: y & M32})
        r = s.run(name, inputs)
        for j, (x, y) in enumerate(pts):
            want = R.rotate(x, y, a)
            got = (r.values.get("rx%d" % j), r.values.get("ry%d" % j))
            if got != want:
                fail += 1
                s.expect_true(name, False, "rot batch %r" % ((x, y, a),), "got %r want %r" % (got, want))
            else:
                s.expect_true(name, True, "rot batch")
    STATS["random"] += n
    print("  Rotator 무작위 %d 점: 실패 %d (%.1fs)" % (n, fail, time.time() - t0))
    n3 = N(400, 20000)
    run_batch(s, spec3, lambda x, y, a, b, c: R.rotate3d(x, y, a, b, c),
              {"x": g_point, "y": g_point, "a": g_small_angle, "b": g_small_angle, "c": g_small_angle}, n3, seed=12)
    return n, time.time() - t0, fail


def suite_rot():
    s = Suite("mathx rotate")
    specs = build_rot(s)
    s.build()
    res = run_rot(s, specs)
    return s.report(), res


# ---------------------------------------------------------------------------------------------
# isqrt · ilog2 · sdiv · smod · ratio
# ---------------------------------------------------------------------------------------------

KD = (0, 1, -1, 2, -2, 3, 7, -7, 16, 100, 360, 65536, 186000, 0x7FFFFFFF, 0x80000000, 1 << 20)
AD = (0, 1, -1, 7, -7, 100000)
RATIO_K = ((150, 100), (0, 100), (255, 100), (-3, 7), (186000, 210600), (1, 0), (0x10001, 3), (99, -100), (0x80000000, 2))
SQ_EDGES = tuple(sorted({v & M32 for k in range(1, 17) for b in (1 << k,) for v in (b * b - 1, b * b, b * b + 1, (b - 1) * (b - 1))}
                        | {0, 1, 2, 3, M32, 0xFFFE0001, 0xFFFE0000}))


def build_int(s):
    @s.case("isqrt")
    def _(t):
        t.out("r", mx.isqrt(t.var("n")))
        mx.isqrt(t.var("n"), ret=[t.var("r2")])

    @s.case("ilog2")
    def _(t):
        t.out("r", mx.ilog2(t.var("n")))
        t.out("z0", mx.ilog2(t.var("n"), 0))
        t.out("zv", mx.ilog2(t.var("n"), t.var("z")))
        mx.ilog2(t.var("n"), ret=[t.var("r2")])

    for p in mx.DIV0:
        @s.case("sdm_" + p)
        def _(t, p=p):
            q, r = mx.sdivmod(t.var("a"), t.var("b"), p)
            t.out("q", q)
            t.out("r", r)
            t.out("q1", mx.sdiv(t.var("a"), t.var("b"), div0=p))
            t.out("r1", mx.smod(t.var("a"), t.var("b"), p))
            mx.sdiv(t.var("a"), t.var("b"), p, ret=[t.var("q2")])
            mx.smod(t.var("a"), t.var("b"), p, ret=[t.var("r2")])

    for i, k in enumerate(KD):
        for p in (mx.DIV0 if k == 0 else ("eudplib",)):
            @s.case("sdk%d_%s" % (i, p))
            def _(t, k=k, p=p):
                q, r = mx.sdivmod(t.var("a"), k, p)
                t.out("q", q)
                t.out("r", r)

    for i, k in enumerate(AD):
        @s.case("sdc%d" % i)
        def _(t, k=k):
            q, r = mx.sdivmod(k, t.var("b"), "ctrig")
            t.out("q", q)
            t.out("r", r)

    for p in mx.DIV0:
        @s.case("ratio_vvv_" + p)
        def _(t, p=p):
            t.out("v", mx.ratio(t.var("x"), t.var("m"), t.var("d"), p))

    for i, (m, d) in enumerate(RATIO_K):
        @s.case("ratio_vkk%d" % i)
        def _(t, m=m, d=d):
            t.out("v", mx.ratio(t.var("x"), m, d))

    @s.case("ratio_mix")
    def _(t):
        t.out("v1", mx.ratio(5, t.var("m"), t.var("d")))
        t.out("v2", mx.ratio(t.var("x"), 150, t.var("d")))
        t.out("v3", mx.ratio(t.var("x"), t.var("m"), 100))
        t.out("v4", mx.ratio(7, 3, t.var("d"), "ctrig"))
        t.out("v5", mx.ratio(-7, 3, 2))
        mx.ratio(t.var("x"), t.var("m"), t.var("d"), ret=[t.var("v6")])

    return batch_case(s, "sdm_batch", 8, ("a", "b"), ("q", "r"), lambda t, a: mx.sdivmod(a[0], a[1]))


def run_int(s, spec):
    s.diff("isqrt", lambda n: {"r": R.isqrt(n), "r2": R.isqrt(n)}, {"n": SQ_EDGES}, n=0, max_edges=1000)
    s.diff("isqrt", lambda n: {"r": R.isqrt(n), "r2": R.isqrt(n)},
           {"n": lambda r: r.getrandbits(r.randint(0, 32))}, n=N(1500, 15000), edges=False)
    STATS["random"] += N(1500, 15000)
    s.diff("ilog2", lambda n, z: {"r": R.ilog2(n), "z0": R.ilog2(n, 0), "zv": R.ilog2(n, z), "r2": R.ilog2(n)},
           {"n": tuple(sorted({0, 1, M32} | {(1 << k) + d & M32 for k in range(32) for d in (-1, 0, 1)})), "z": (0, 5, M32)},
           n=0, max_edges=1000)
    s.diff("ilog2", lambda n, z: {"r": R.ilog2(n), "z0": R.ilog2(n, 0), "zv": R.ilog2(n, z), "r2": R.ilog2(n)},
           {"n": lambda r: r.getrandbits(r.randint(0, 32)), "z": None}, n=N(500, 5000), edges=False)
    small = tuple(range(-9, 10)) + (100, -100, 65536, -65536)
    for p in mx.DIV0:
        def ref(a, b, p=p):
            q, r = R.sdiv(a, b, p)
            return {"q": q, "r": r, "q1": q, "r1": r, "q2": q, "r2": r}

        diff_both(s, "sdm_" + p, ref, {"a": EDGES32 + small, "b": EDGES32 + small}, {"a": g_any, "b": g_any}, N(800, 8000))
    for i, k in enumerate(KD):
        for p in (mx.DIV0 if k == 0 else ("eudplib",)):
            diff_both(s, "sdk%d_%s" % (i, p), lambda a, k=k, p=p: dict(zip("qr", R.sdiv(a, k, p))),
                      {"a": EDGES32 + small + (k & M32, (k + 1) & M32, (k - 1) & M32, (-k) & M32)}, {"a": g_any}, N(60, 600))
    for i, k in enumerate(AD):
        diff_both(s, "sdc%d" % i, lambda b, k=k: dict(zip("qr", R.sdiv(k, b, "ctrig"))), {"b": EDGES32 + small}, {"b": g_any},
                  N(60, 600))
    for p in mx.DIV0:
        diff_both(s, "ratio_vvv_" + p, lambda x, m, d, p=p: {"v": R.ratio(x, m, d, p)},
                  {"x": (0, 1, -1, 27, -33, 0x7FFFFFFF, 0x80000000), "m": (0, 1, -1, 150, 0x10000), "d": (0, 1, -1, 100, 7)},
                  {"x": g_any, "m": g_any, "d": g_any}, N(300, 3000))
    for i, (m, d) in enumerate(RATIO_K):
        diff_both(s, "ratio_vkk%d" % i, lambda x, m=m, d=d: {"v": R.ratio(x, m, d)}, {"x": EDGES32 + small}, {"x": g_any},
                  N(60, 600), seed=i)

    def mix_ref(x, m, d):
        return {"v1": R.ratio(5, m, d), "v2": R.ratio(x, 150, d), "v3": R.ratio(x, m, 100), "v4": R.ratio(7, 3, d, "ctrig"),
                "v5": R.ratio(-7, 3, 2), "v6": R.ratio(x, m, d)}

    s.diff("ratio_mix", mix_ref, {"x": g_any, "m": g_any, "d": g_any}, n=N(200, 2000), edges=False)
    n = N(2000, 30000)
    run_batch(s, spec, lambda a, b: R.sdiv(a, b), {"a": g_any, "b": g_any}, n, seed=21)


def suite_int():
    s = Suite("mathx int")
    spec = build_int(s)
    s.build()
    run_int(s, spec)
    return s.report()


# ---------------------------------------------------------------------------------------------
# 전체 실행 전용: 고정밀 360, 큰 주기
# ---------------------------------------------------------------------------------------------


def suite_big():
    s = Suite("mathx big")

    @s.case("ldp360")
    def _(t):
        c, sn = mx.lengthdir(t.var("r"), t.var("a"), 360, precise=True)
        t.out("c", c)
        t.out("s", sn)

    @s.case("rotp360")
    def _(t):
        x2, y2 = mx.Rotator(45, precise=True)(t.var("x"), t.var("y"))
        t.out("rx", x2)
        t.out("ry", y2)

    for c in (4096, 65536):
        @s.case("at%d" % c)
        def _(t, c=c):
            t.out("t", mx.atan2(t.var("y"), t.var("x"), c))

        @s.case("ld%d" % c)
        def _(t, c=c):
            cc, ss = mx.lengthdir(t.var("r"), t.var("a"), c)
            t.out("c", cc)
            t.out("s", ss)

    t0 = time.time()
    s.build()
    print("  큰 표 빌드 %.1fs" % (time.time() - t0))
    diff_both(s, "ldp360", pair(lambda r, a: R.lengthdir_precise(r, a)), {"r": R_EDGES, "a": A_EDGES},
              {"r": g_radius, "a": g_angle}, 20000)
    s.diff("rotp360", lambda x, y: dict(zip(("rx", "ry"), R.rotate(x, y, 45, 360, True))), {"x": g_point, "y": g_point},
           n=3000, edges=False)
    for c in (4096, 65536):
        diff_both(s, "at%d" % c, lambda y, x, c=c: {"t": R.atan2(y, x, c)}, {"y": D_EDGES, "x": D_EDGES},
                  {"y": g_delta, "x": g_delta}, 5000)
        diff_both(s, "ld%d" % c, pair(lambda r, a, c=c: R.lengthdir(r, a, c)), {"r": R_EDGES, "a": (0, 1, -1, c // 8, c - 1, c)},
                  {"r": g_radius, "a": g_cycle_angle(c)}, 5000)
    return s.report()


# ---------------------------------------------------------------------------------------------
# 파이썬 쪽 판정
# ---------------------------------------------------------------------------------------------


def python_checks(ck):
    # 표: Decimal 정확 반올림 = 이 플랫폼 libm (원본 TEP 식)
    for c in list(range(4, 1025, 4)) + [1440, 2048, 3600, 4096, 16384, 65536]:
        ck.true("sin_table %d" % c, mt.sin_table(c) == tuple(R.sin_table(c)))
        ck.true("atan_thresholds %d" % c, mt.atan_thresholds(c) == tuple(R.tan_table(c)))
    ck.eq("coarse", list(mt.coarse_thresholds()[1:]), R.coarse_table()[1:])
    ck.eq("T[30], T[45], T[90], A[45]", (mt.sin_table(360)[30], mt.sin_table(360)[45], mt.sin_table(360)[90],
                                          mt.atan_thresholds(360)[45]), (32767, 46340, 65536, 65535))
    ck.eq("precise size 360", mt.precise_table_size(360), 11927552)
    tb = mt.precise_table_bytes(16)
    rng = random.Random(4)
    for _ in range(2000):
        l, k = rng.randrange(5), rng.randrange(32768)
        v = int.from_bytes(tb[4 * (l * 32768 + k):4 * (l * 32768 + k) + 4], "little")
        if v != R.precise_value(16, l, k):
            ck.eq("precise 16 (%d, %d)" % (l, k), v, R.precise_value(16, l, k))
            break
    else:
        ck.true("precise 16 표본 2000", True)
    ck.eq("packed 360 [1]", mt.packed_sin_table(360)[1], mt.sin_table(360)[1] + (mt.sin_table(360)[89] << 16))
    ck.eq("int bits 360", mx._int_bits(mt.atan_thresholds(360)), 8)
    ck.eq("int bits 65536", mx._int_bits(mt.atan_thresholds(65536)), 14)
    # 참조 구현 자체: 원본 거친 8갈래 점프는 결과를 바꾸지 않는다 / 두 나눗셈 계열이 같다
    rng = random.Random(5)
    bad = 0
    for c in (4, 8, 12, 16, 64, 256, 360, 1024, 4096):
        for _ in range(N(3000, 30000)):
            y, x = g_delta(rng), g_delta(rng)
            if R.atan2(y, x, c) != R.atan2_first(y, x, c):
                bad += 1
    ck.eq("거친 점프 = 처음 참인 i", bad, 0)
    # 상수 접기 = 참조 (파이썬만, 빠름)
    t0 = time.time()
    nconst = N(20000, 200000)
    bad = []
    for _ in range(nconst):
        r, a = g_radius(rng), g_angle(rng)
        got = tuple(u32(v) for v in mx.lengthdir(r, a))
        if got != R.lengthdir(r, a):
            bad.append(("ld", r, a, got))
        y, x = g_delta(rng), g_delta(rng)
        if mx.atan2(y, x) != R.atan2(y, x):
            bad.append(("at", y, x))
        xx, yy, aa = g_point(rng), g_point(rng), g_small_angle(rng)
        if tuple(u32(v) for v in mx.Rotator(aa)(xx, yy)) != R.rotate(xx, yy, aa):
            bad.append(("rot", xx, yy, aa))
        p, q = g_any(rng), g_any(rng)
        for pol in mx.DIV0:
            if tuple(u32(v) for v in mx.sdivmod(p, q, pol)) != R.sdiv(p, q, pol):
                bad.append(("sdiv", p, q, pol))
        if u32(mx.ratio(p, q, xx, "ctrig")) != R.ratio(p, q, xx, "ctrig"):
            bad.append(("ratio", p, q, xx))
        if mx.to_dir256(a) != R.to_dir256(a) or mx.isqrt(p) != R.isqrt(p) or mx.ilog2(p) != R.ilog2(p):
            bad.append(("misc", a, p))
        if mx.atan2_sc(y, x) != R.atan2_x(y, x):
            bad.append(("sc", y, x))
    for _ in range(N(2000, 20000)):
        args = [g_point(rng), g_point(rng)] + [None if rng.random() < 0.25 else g_small_angle(rng) for _ in range(3)]
        if tuple(u32(v) for v in mx.rotate3d(*args)) != R.rotate3d(*args):
            bad.append(("r3", args))
        c = rng.choice((8, 16, 360))
        r, a = g_radius(rng), g_cycle_angle(c)(rng)
        if tuple(u32(v) for v in mx.lengthdir(r, a, c, precise=True)) != R.lengthdir_precise(r, a, c):
            bad.append(("ldp", r, a, c))
    ck.eq("상수 접기 = 참조 (%d 벌)" % nconst, bad[:5], [])
    print("  상수 접기 %d 벌 %.1fs" % (nconst, time.time() - t0))
    for (r, a), want in S1_LD:
        ck.eq("S1 lengthdir %r" % ((r, a),), mx.lengthdir(r, a), want)
    for (x, y, a), want in S1_ROT:
        ck.eq("S1 rotate %r" % ((x, y, a),), mx.Rotator(a)(x, y), want)
    for (xy, S, want) in S1_SIZE:
        ck.eq("S1 size %r" % ((xy, S),), (mx.ratio(xy[0], S, 100), mx.ratio(xy[1], S, 100)), want)
    for a, d in S4_DIR:
        ck.eq("S4 to_dir256(%d)" % a, mx.to_dir256(a), d)
        ck.eq("S4 표 식(%d)" % a, R.to_dir256_tep(a), d)
    for (sxy, txy, a, f) in S4_ROWS:
        ck.eq("S4 atan2 %r" % ((sxy, txy),), (mx.atan2(sxy[1] - txy[1], sxy[0] - txy[0]),
                                                mx.to_dir256(mx.atan2(sxy[1] - txy[1], sxy[0] - txy[0]))), (a, f))
    ck.eq("atan2(1,1)", mx.atan2(1, 1), 46)
    ck.eq("atan2(0,0)", mx.atan2(0, 0), 90)
    ck.eq("atan2_sc(0,0)", mx.atan2_sc(0, 0), 128)
    ck.eq("sdiv 0 eudplib", (mx.sdiv(5, 0), mx.sdiv(-5, 0), mx.smod(-5, 0)), (-1, 1, -5))
    ck.eq("sdiv 0 ctrig", (mx.sdiv(5, 0, "ctrig"), mx.sdiv(-5, 0, "ctrig"), mx.smod(-5, 0, "ctrig")), (0x7FFFFFFF, -(1 << 31), -5))
    ck.eq("sdiv -2^31 / -1", mx.sdivmod(-(1 << 31), -1), (-(1 << 31), 0))
    ck.eq("ilog2 0", (mx.ilog2(0), mx.ilog2(0, 7)), (0x80000000, 7))
    ck.eq("isqrt max", mx.isqrt(M32), 65535)
    # 이름·목록
    for n in ("lengthdir", "rotate3d", "atan2", "atan2_sc", "to_dir256", "isqrt", "ilog2", "sdivmod", "sdiv", "smod", "ratio"):
        ck.true("alias " + n, getattr(mx, n) is getattr(mx, "f_" + n))
    ck.eq("__all__ 중복", sorted(mx.__all__), sorted(set(mx.__all__)))
    for n in mx.__all__:
        ck.true("__all__ " + n, hasattr(mx, n))
    for n in mt.__all__:
        ck.true("tables __all__ " + n, hasattr(mt, n))
    ck.true("f_sin_table", mt.f_sin_table(8) == mt.sin_table(8) and mt.f_atan_thresholds(8) == mt.atan_thresholds(8))
    ck.true("repr", "상수 각 330" in repr(mx.Rotator(-30)) and "변수 각" in repr(mx.Rotator()))
    # 입력 검사
    v = EUDVariable()
    for bad_c in (0, 2, 6, 3.5, 70000, True, "360"):
        ck.raises("cycle %r" % (bad_c,), EudextError, mx.lengthdir, v, v, bad_c)
    ck.raises("atan2 cycle", EudextError, mx.atan2, v, v, 90 + 1)
    ck.raises("Rotator cycle", EudextError, mx.Rotator, 0, 10)
    ck.raises("precise 16", EudextError, mx.lengthdir, v, v, 360, 16)
    ck.raises("precise 0", EudextError, mx.lengthdir, v, v, 360, 0)
    ck.raises("precise str", EudextError, mx.lengthdir, v, v, 360, "13")
    # 줄인 표: 파이썬 정답(상수 접기)이 원본 표·표 없는 값과 맞물린다 — 360 · 13비트
    for r, a in ((8191, 30), (-8191, 211), (8192, 30), (-8192, 30), (9000, 77), (2151, 359), (0x80000000, 5)):
        ck.eq("precise 13 상수 (%d, %d)" % (r, a), tuple(u32(x) for x in mx.lengthdir(r, a, 360, precise=13)),
              ld_bits(r, a, 360, 13))
    ck.eq("precise 13 크기", mt.precise_table_size(360, 13), 91 * 8192 * 4)
    ck.true("precise 13 표 = 원본 표 앞칸", mt.precise_table_bytes(8, 5) == b"".join(
        mt.precise_table_bytes(8)[l * 32768 * 4:(l * 32768 + 32) * 4] for l in range(3)))
    ck.raises("div0", EudextError, mx.sdiv, v, v, "zero")
    ck.raises("ratio div0", EudextError, mx.ratio, v, 1, 2, "x")
    ck.raises("float", EudextError, mx.lengthdir, 1.5, v)
    ck.raises("range hi", EudextError, mx.atan2, 1 << 32, v)
    ck.raises("range lo", EudextError, mx.isqrt, -(1 << 31) - 1)
    ck.raises("None", EudextError, mx.isqrt, None)
    ck.raises("str", EudextError, mx.ilog2, "a")
    ck.raises("ret 개수", EudextError, mx.lengthdir, v, v, ret=[v])
    ck.raises("ret 값", EudextError, mx.atan2, v, v, ret=[5])
    ck.raises("const Rotator set", EudextError, mx.Rotator(30).set, v)
    ck.raises("Rotator own", EudextError, mx.Rotator, None, 360, False, 1)
    ck.raises("rotate3d own", EudextError, mx.rotate3d, v, v, v, None, None, 360, False, "yes")
    rk = mx.Rotator(30)
    try:
        rk.angle = 45
        ck.true("const Rotator angle =", False, "예외 없음")
    except EudextError:
        ck.true("const Rotator angle =", True)
    ck.eq("Rotator angle 상수", mx.Rotator(-30).angle, 330)
    ck.true("Rotator angle 변수", _compat.is_var(mx.Rotator().angle))
    # 비공개 API
    for fn in ("mathx.py", "mathx_tables.py"):
        with open(os.path.join(_common.PKG, fn), encoding="utf-8") as f:
            src = f.read()
        ck.true(fn + " eudplib 비공개 import 없음", "from eudplib." not in src and "import eudplib." not in src)
        found = re.findall(r"(?<!self)\.\_(?!_)\w+", src)
        ck.eq(fn + " 남의 비공개 속성 접근 없음", found, [])


# ---------------------------------------------------------------------------------------------
# epScript 예제·인게임 맵
# ---------------------------------------------------------------------------------------------

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
            if f.endswith((".scx", ".pyc", ".lua")) and not (rel == "testing" and f.startswith("base")):
                found.append(os.path.join(rel, f))
    return found


def eps_checks(ck):
    src = open(os.path.join(EX, "mathx_example.eps"), encoding="utf-8").read()
    out, nerr = _compat.eps_compile("mathx_example.eps", src)
    ck.eq("example eps 오류", nerr, 0)
    for needle in ("from eudext import mathx as mx", "mx.Rotator()", "mx.Rotator(30)", "mx.f_lengthdir(100, ang)",
                   "spin.set(ang)", "spin(40, -16)", "mx.f_atan2(cy, cx)", "mx.f_to_dir256(back)", "mx.f_sdivmod(ang, 7)",
                   'mx.f_sdiv(ang, 0, "ctrig")', "mx.f_isqrt(", "mx.f_ilog2(frame)", "mx.f_ratio(px, 150, 100)",
                   "mx.f_rotate3d(px, py, ang, 45, None)", "mx.f_atan2_sc(cy, cx)"):
        ck.true("example eps: " + needle, out is not None and needle in out)
    src2 = open(os.path.join(EX, "mathx_ingame.eps"), encoding="utf-8").read()
    out2, nerr2 = _compat.eps_compile("mathx_ingame.eps", src2)
    ck.eq("ingame eps 오류", nerr2, 0)
    ck.true("ingame 배열은 상수 초기값", out2 is not None and "_ARR(" not in out2 and "_TYGV([None], lambda: [-" not in out2)
    # 인게임 맵 표 = 참조 구현
    tables = dict(re.findall(r"^const (\w+) = EUDArray\(list\((.*)\)\);", src2, re.M))
    arr = {k: [int(x, 0) for x in v.split(",")] for k, v in tables.items()}
    LD = list(zip(arr["LD_R"], arr["LD_A"]))
    ck.eq("ingame LD", [list(R.lengthdir(r, a)) for r, a in LD], [list(p) for p in zip(arr["LD_C"], arr["LD_S"])])
    ck.eq("ingame ROT", [list(R.rotate(x, y, a)) for x, y, a in zip(arr["RO_X"], arr["RO_Y"], arr["RO_A"])],
          [list(p) for p in zip(arr["RO_RX"], arr["RO_RY"])])
    r3in = arr["R3_IN"]
    ck.eq("ingame R3", [x for j in range(len(r3in) // 5) for x in R.rotate3d(*r3in[j * 5:j * 5 + 5])], arr["R3_OUT"])
    ck.eq("ingame AT", [R.atan2(y, x) for y, x in zip(arr["AT_Y"], arr["AT_X"])], arr["AT_T"])
    ck.eq("ingame SC", [R.atan2_x(y, x) for y, x in zip(arr["SC_Y"], arr["SC_X"])], arr["SC_T"])
    ck.eq("ingame DR", [R.to_dir256(a) for a in arr["DR_A"]], arr["DR_D"])
    for pol, qk, rk in (("eudplib", "SD_QE", "SD_RE"), ("ctrig", "SD_QC", "SD_RC")):
        ck.eq("ingame SD " + pol, [list(R.sdiv(a, b, pol)) for a, b in zip(arr["SD_A"], arr["SD_B"])],
              [list(p) for p in zip(arr[qk], arr[rk])])
    rtin = arr["RT_IN"]
    ck.eq("ingame RT", [R.ratio(*rtin[j * 3:j * 3 + 3]) for j in range(len(rtin) // 3)], arr["RT_OUT"])
    ck.eq("ingame SQ", [R.isqrt(n) for n in arr["SQ_N"]], arr["SQ_R"])
    ck.eq("ingame LG", [R.ilog2(n) for n in arr["LG_N"]], arr["LG_R"])
    ck.eq("ingame LP", [list(R.lengthdir_precise(r, a, 8)) for r, a in zip(arr["LP_R"], arr["LP_A"])],
          [list(p) for p in zip(arr["LP_C"], arr["LP_S"])])
    counts = [len(LD), len(arr["RO_X"]), len(r3in) // 5, len(arr["AT_Y"]), len(arr["SC_Y"]), len(arr["DR_A"]), len(arr["SD_A"]),
              len(rtin) // 3, len(arr["SQ_N"]), len(arr["LG_N"]), len(arr["LP_R"])]
    ck.eq("ingame COUNTS", arr["COUNTS"], counts)
    for name, n in zip(("i < %d" % c for c in counts), counts):
        ck.true("ingame 반복 수 " + name, ("i < %d;" % n) in src2 or ("j < %d;" % n) in src2 or ("k < %d;" % n) in src2)
    return sum(counts)


def _load_eps(name):
    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_mathx_" + name)
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, name + ".eps"), os.path.join(work, name + ".eps"))
    LoadMap(BASE_MAP)
    CompressPayload(True)
    return build._load_plugin(os.path.join(work, name + ".eps"), {})


def example_emulate(ck):
    """예제를 에뮬레이터에서 여러 사이클 돌려 전역 변수를 참조 구현과 비교한다."""
    mod = _load_eps("mathx_example")
    names = ("frame", "ang", "cx", "cy", "px", "py", "tx", "ty", "sx", "sy", "back", "face", "face2", "q", "m", "qc", "root",
             "e", "scaled", "X", "Y", "Z")
    prog = emu.Program(mod.afterTriggerExec)
    for n in names:
        prog.watch(n, getattr(mod, n))
    m = prog.build()
    scmodel.install(m)
    steps = []
    for cyc in range(1, N(60, 400) + 1):
        m.cycle()
        steps.append(m.last_steps())
        got = {n: m.var(n) for n in names}
        f = cyc - 1  # step 은 frame 을 올리기 전에 계산한다
        ang = u32(f * 7 - 20)
        cx, cy = R.lengthdir(100, ang)
        px, py = R.rotate(40, -16, ang)
        tx, ty = R.rotate(40, -16, 30)
        sx, sy = R.rotate(px, py, 30)
        back = R.atan2(cy, cx)
        q, mm = R.sdiv(ang, 7)
        X, Y, Z = R.rotate3d(px, py, ang, 45, None)
        want = {"frame": cyc, "ang": ang, "cx": cx, "cy": cy, "px": px, "py": py, "tx": tx, "ty": ty, "sx": sx, "sy": sy,
                "back": back, "face": R.to_dir256(back), "face2": R.atan2_x(cy, cx), "q": q, "m": mm,
                "qc": R.sdiv(ang, 0, "ctrig")[0], "root": R.isqrt(u32(s32(cx) * s32(cx) + s32(cy) * s32(cy))),
                "e": R.ilog2(f), "scaled": R.ratio(px, 150, 100), "X": X, "Y": Y, "Z": Z}
        if got != want:
            ck.eq("example 사이클 %d" % cyc, {k: got[k] for k in got if got[k] != want[k]},
                  {k: want[k] for k in got if got[k] != want[k]})
            return
    ck.true("example %d 사이클 = 참조" % len(steps), True)
    print("  예제 한 사이클 실행 %d~%d 트리거" % (min(steps), max(steps)))


def ingame_emulate(ck, expect_total):
    """인게임 맵을 에뮬레이터에서 돌린다: 전체 일치 수 = 전체 수, 실행 오류 없음."""
    mod = _load_eps("mathx_ingame")
    names = ("frame", "total", "good")
    prog = emu.Program(mod.afterTriggerExec)
    for n in names:
        prog.watch(n, getattr(mod, n))
    m = prog.build()
    scmodel.install(m)
    err = None
    try:
        m.cycle(22)
    except emu.EmuError as e:
        err = str(e)
    got = {n: m.var(n) for n in names}
    print("  인게임 맵 에뮬레이션: %r, 페이로드 %d B" % (got, prog.payload_size))
    ck.eq("ingame emu 오류", err, None)
    ck.eq("ingame emu 값", got, {"frame": 22, "total": expect_total, "good": expect_total})
    texts = [x for x in m.log if x[0] == "act" and x[1] == 9]
    ck.eq("ingame 출력 줄 수 (다름 줄 없음)", len(texts), 14)


def euddraft_build(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    for name in ("mathx_example", "mathx_ingame"):
        work = os.path.join(_common.WORK, "t_mathx_build_" + name)
        eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
        r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
        print("  " + r.summary())
        ck.true("euddraft " + name, r.ok, r.log[-2000:])
        ck.true("eps compiled " + name, '[epScript] Compiling "%s.eps"' % name in r.log)
        ck.true("freeze off " + name, not r.freeze)


TEPC = os.environ.get("EUDEXT_TEPC") or "/home/developer/TEP3.0_Headless_Compiler/build/tepc"


def tep_check(ck):
    """C9-1 도구를 헤드리스 TEP(Linux, glibc)로 확인: CtrigAsm 표 식을 컴파일한 값 = mathx_tables."""
    sys.path.insert(0, EX)
    try:
        import mathx_tep_check as tc
    finally:
        sys.path.remove(EX)
    ck.eq("tep_check expected sin", tc.expected()[tc.G_SIN360][30], 32767)
    if not os.path.isfile(TEPC):
        print("  tepc 없음: %s — 건너뜀 (EUDEXT_TEPC 로 지정)" % TEPC)
        return
    work = os.path.join(_common.WORK, "t_mathx_tepc")
    os.makedirs(work, exist_ok=True)
    lua = os.path.join(work, "mathx_tables.lua")
    ck.eq("tep_check lua", tc.main(["lua", lua]), 0)
    base = os.path.join(work, "in.scx")
    shutil.copy2(BASE_MAP, base)
    out = os.path.join(work, "out.scx")
    p = subprocess.run([TEPC, base, lua, out, "--quiet"], capture_output=True, stdin=subprocess.DEVNULL, timeout=300)
    ck.eq("tepc 실행", p.returncode, 0)
    ok, msgs = tc.check(out)
    print("  tepc 표 대조: " + "; ".join(msgs))
    ck.true("C9-1 (헤드리스 TEP) 일치", ok, msgs)


# ---------------------------------------------------------------------------------------------
# 비용 측정 항목 (tools/cost.py)
# ---------------------------------------------------------------------------------------------


def _v(t, n):
    return t.var(n)


def _cost_ld_vv(t):
    mx.lengthdir(_v(t, "r"), _v(t, "a"))


def _cost_ld_vk(t):
    mx.lengthdir(_v(t, "r"), 30)


def _cost_ld_kv(t):
    mx.lengthdir(100, _v(t, "a"))


def _cost_ldp(t):
    mx.lengthdir(_v(t, "r"), _v(t, "a"), 8, precise=True)


def _cost_rot_v(t):
    rot = mx.Rotator()
    rot.set(_v(t, "a"))
    rot(_v(t, "x"), _v(t, "y"))


def _cost_rot_own(t):
    rot = mx.Rotator(own=True)
    rot.set(_v(t, "a"))
    rot(_v(t, "x"), _v(t, "y"))


def _cost_warm(t):
    # 준비 케이스: 공유 엔진(360)에 각 a 를 준비해 둔다 → 잴 케이스는 준비 없이 점만
    mx.lengthdir(_v(t, "r"), _v(t, "a"))


def _cost_rot_k(t):
    mx.Rotator(30)(_v(t, "x"), _v(t, "y"))


def _cost_r3(t):
    mx.rotate3d(_v(t, "x"), _v(t, "y"), 30, 45, 60)


def _cost_at(t):
    mx.atan2(_v(t, "y"), _v(t, "x"))


def _cost_atsc(t):
    mx.atan2_sc(_v(t, "y"), _v(t, "x"))


def _cost_dir(t):
    mx.to_dir256(_v(t, "a"))


def _cost_isqrt(t):
    mx.isqrt(_v(t, "n"))


def _cost_ilog2(t):
    mx.ilog2(_v(t, "n"))


def _cost_sdm(t):
    mx.sdivmod(_v(t, "a"), _v(t, "b"))


def _cost_sdk(t):
    mx.sdivmod(_v(t, "a"), 7)


def _cost_sdk2(t):
    mx.sdivmod(_v(t, "a"), 65536)


def _cost_ratio_k(t):
    mx.ratio(_v(t, "x"), 150, 100)


def _cost_ratio_v(t):
    mx.ratio(_v(t, "x"), _v(t, "m"), _v(t, "d"))


def _cost_eud_lengthdir(t):
    from eudplib import f_lengthdir

    f_lengthdir(_v(t, "r"), _v(t, "a"))


def _cost_eud_atan2(t):
    from eudplib import f_atan2

    f_atan2(_v(t, "y"), _v(t, "x"))


def _cost_eud_sqrt(t):
    from eudplib import f_sqrt

    f_sqrt(_v(t, "n"))


def _cost_eud_divtz(t):
    from eudplib import f_div_towards_zero

    f_div_towards_zero(_v(t, "a"), _v(t, "b"))


_E = mx._shared_engine(360, False)
LD_IN = [{"r": 100, "a": 45}, {"r": 0xFFFFFF9C, "a": 1000}, {"r": 32767, "a": 0x80000000}, {"r": 40000, "a": 30}]
AT_IN = [{"y": 100, "x": 200}, {"y": 1, "x": 0x10000 - 1}, {"y": 0xFFFF8000, "x": 3}, {"y": 1, "x": 0}, {"y": 100000, "x": 3},
         {"y": 3, "x": 100000}]
ROT_IN = [{"a": 30, "x": 100, "y": 50}, {"a": 0xFFFFFD2F, "x": 0xFFFFF830, "y": 2000}]
ROT_IN_K = [{"x": 100, "y": 50}, {"x": 0xFFFFF830, "y": 2000}]
SQ_IN = [{"n": 0}, {"n": 99}, {"n": 10000}, {"n": 1 << 20}, {"n": M32}]
SD_IN = [{"a": 1000, "b": 7}, {"a": 0xFFFFFC18, "b": 0x10000}, {"a": 5, "b": 0}]
ROT_T = {"exec": 120}  # S1 8.6 "회전 +120"

COST_CASES = [
    CostCase("lengthdir(변수, 변수) 360 — 각 준비 포함", _cost_ld_vv, LD_IN, funcs=(_E.ld_func(), _E.load_func()),
             note="공유 본문(주기마다 1벌, Rotator·rotate3d 와 같이 씀). 넷째는 |r| > 32767 느린 길(32비트 곱)"),
    CostCase("lengthdir(변수, 변수) 360 — 같은 각", _cost_ld_vv, [{"r": 100, "a": 30}, {"r": 0xFFFF8001, "a": 30}],
             setup=_cost_warm, setup_inputs={"r": 1, "a": 30}, note="마지막으로 준비한 각과 같으면 표 준비를 건너뜀"),
    CostCase("lengthdir(변수, 30)", _cost_ld_vk, [{"r": 100}, {"r": 40000}], funcs=(mx._const_ld_fn(360, False, 30),),
             note="상수 각마다 본문 1벌"),
    CostCase("lengthdir(100, 변수)", _cost_ld_kv, [{"a": 45}, {"a": 1000}], note="변수 각 공유 본문 (위와 같은 본문)"),
    CostCase("lengthdir(변수, 변수, 8, precise)", _cost_ldp, [{"r": 100, "a": 3}, {"r": 40000, "a": 0xFFFFFFFF}],
             funcs=(mx._shared_engine(8, True).ld_func(), mx._shared_engine(8, True).load_func()),
             note="표 (Q+1)×131072 B = 393KB (360 이면 11.9MB)"),
    CostCase("Rotator(변수).rotate — 각이 바뀐 첫 점", _cost_rot_v, ROT_IN, note="공유 본문. 준비 + 점 (사이클·작업마다 한 번)"),
    CostCase("Rotator(변수).rotate — 같은 각의 점", _cost_rot_v, [{"a": 30, "x": 100, "y": 50}, {"a": 30, "x": 0xFFFFF830, "y": 2000}],
             target=ROT_T, setup=_cost_warm, setup_inputs={"r": 1, "a": 30}, note="점당 실행 (S1 8.6 회전 +120 목표)"),
    CostCase("Rotator(변수, own=True).rotate", _cost_rot_own, ROT_IN, note="인스턴스 전용 본문 — 페이로드가 인스턴스마다 붙는다"),
    CostCase("Rotator(30).rotate", _cost_rot_k, ROT_IN_K, target=ROT_T, funcs=(mx._const_rot_fn(360, False, 30),)),
    CostCase("rotate3d(변수, 변수, 30, 45, 60)", _cost_r3, ROT_IN_K),
    CostCase("atan2(변수, 변수) 360", _cost_at, AT_IN, funcs=(mx._atan2_fn(360, False),),
             note="넷째 dx = 0, 다섯째 |dy| > 65535(하위 16비트만 쓰는 같은 길), 여섯째 |dx| > 65535(32비트 나눗셈)"),
    CostCase("atan2_sc(변수, 변수)", _cost_atsc, AT_IN[:2], funcs=(mx._atan2_fn(256, True),)),
    CostCase("to_dir256(변수) 360", _cost_dir, [{"a": 45}, {"a": 0xFFFFFFFF}, {"a": 100000}], funcs=(mx._dir256_fn(360),)),
    CostCase("isqrt(변수)", _cost_isqrt, SQ_IN, funcs=(mx._isqrt_fn(),)),
    CostCase("ilog2(변수)", _cost_ilog2, SQ_IN, funcs=(mx._ilog2_fn(0x80000000),)),
    CostCase("sdivmod(변수, 변수)", _cost_sdm, SD_IN, funcs=(mx._sdiv_vv_fn("eudplib"), mx._udivmod_fn()),
             note="같은 제수가 이어지면 표 재사용 (DPS div3232)"),
    CostCase("sdivmod(변수, 7)", _cost_sdk, [{"a": 1000}, {"a": 0xFFFFFC18}], funcs=(mx._sdiv_const_fn(7, None),)),
    CostCase("sdivmod(변수, 65536)", _cost_sdk2, [{"a": 1000}, {"a": 0xFFFFFC18}], funcs=(mx._sdiv_const_fn(65536, None),)),
    CostCase("ratio(변수, 150, 100)", _cost_ratio_k, [{"x": 27}, {"x": 0xFFFFFFF0}]),
    CostCase("ratio(변수, 변수, 변수)", _cost_ratio_v, [{"x": 27, "m": 150, "d": 100}, {"x": 0xFFFFFFF0, "m": 186000, "d": 210600}],
             funcs=(mx._smul_fn(),)),
    CostCase("참고: eudplib f_lengthdir (음수에서 틀림)", _cost_eud_lengthdir, LD_IN[:1]),
    CostCase("참고: eudplib f_atan2 (근사식, 값 다름)", _cost_eud_atan2, AT_IN[:1]),
    CostCase("참고: eudplib f_sqrt", _cost_eud_sqrt, SQ_IN),
    CostCase("참고: eudplib f_div_towards_zero(변수, 변수)", _cost_eud_divtz, SD_IN[:1]),
]


def main():
    before = set(repo_artifacts())
    t_start = time.time()
    ck = Checker("t_mathx (python)")
    python_checks(ck)
    ok_ld, ld_stat = suite_ld()
    ok_at, at_stat = suite_at()
    ok_rot, rot_stat = suite_rot()
    ok_int = suite_int()
    oks = [ok_ld, ok_at, ok_rot, ok_int]
    if FULL:
        oks.append(suite_big())
    total = eps_checks(ck)
    example_emulate(ck)
    ingame_emulate(ck, total)
    euddraft_build(ck)
    tep_check(ck)
    ck.eq("repo clean", sorted(set(repo_artifacts()) - before), [])
    oks.append(ck.report())
    print("[t_mathx] %s 실행: 무작위 %d 개 + 경계 조합 %d 개, lengthdir %d / atan2 %d / Rotator %d 점 (%.0fs)" % (
        "전체" if FULL else "기본", STATS["random"], STATS["edge"], ld_stat[0], at_stat[0], rot_stat[0], time.time() - t_start))
    finish(*oks)


if __name__ == "__main__":
    main()
