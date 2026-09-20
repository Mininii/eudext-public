"""`spawn` 시험 3 (에뮬레이터 + testing/locmodel): 2026-09-20 에 더한 세 가지 — `size_div`·`rot3d`·`bounds`.

- **`size_div`**: 크기의 분모를 고른다. 기본 100(퍼센트)은 그대로이고, `Spawner(size_div=256)` 은 원본
  `CA_RatioXY(v, 256, v, 256)`(Mem2 `func.lua:1358`, `G_CA_Ratio(n)`)과 같은 값이어야 한다 — 참조는 `ref_mathx.ratio`.
- **`rot3d`**: `push(rot3d=True)`/`rot3d=묶음` 이 `mathx.rotate3d` 를 점마다 부른다(2D 회전 **뒤**, 평행이동 **앞**).
  묶음이 둘이면(원본 `CA_Eff_*` / `CA_Eff_*2`) 작업마다 다른 묶음을 쓴다. 참조는 `ref_mathx.rotate3d`(CBP 9883 원문).
- **`bounds`**: `"skip"`(기본, 지금까지의 동작 — 밖은 버린다)과 `"clamp"`(0~W−1·0~H−1 로 잘라 **반드시** 소환 —
  옛판 G_CA `CA_Func` 의 기본). 맵 크기는 `map_size` 를 안 주면 **chk 의 DIM 섹션**에서 온다(128×128 → 4096).
- 기본값 회귀: `size_div` 를 안 준 Spawner 는 100, `bounds` 는 "skip", `rot3d` 를 안 쓰면 3D 코드가 없다.

python tests/t_spawn_p6c.py
"""

import sys

sys.dont_write_bytecode = True
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import random  # noqa: E402

import ref_mathx as RM  # noqa: E402
import ref_spawn as RS  # noqa: E402
from eudplib import EUDVariable  # noqa: E402
from eudext import _compat, spawn  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.shape import Shape, ShapeSet  # noqa: E402
from eudext.spawn import Spawner  # noqa: E402
from eudext.testing import BASE_MAP, locmodel  # noqa: E402
from eudext.testing.harness import Suite  # noqa: E402

M32 = 0xFFFFFFFF
u32, s32 = RS.u32, RM.s32
LOC, LOC2 = 26, 27
CHK_W = CHK_H = 4096  # 기본 맵(128×128 타일)의 chk DIM × 32


def rnd_shape(seed, n=120, span=1500):
    rng = random.Random(seed)
    return Shape([(rng.randint(-span, span), rng.randint(-span, span)) for _ in range(n)], name="p%d" % seed)


SHAPES = [rnd_shape(700 + k) for k in range(3)]
# 경계 밖으로 넉넉히 나가는 점(클램프·건너뛰기 둘 다 보려고)
EDGE = Shape([(-9000, -9000), (9000, 9000), (0, 0), (-3000, 3000), (3000, -3000), (-1, -1), (2047, 2047)],
             name="edge")
SET = ShapeSet(SHAPES + [EDGE], name="p6c")

# size_div 256 (원본 CA_RatioXY)
SD = Spawner(capacity=8, loc=LOC, loc2=LOC2, shapes=SET, map_size=(CHK_W, CHK_H), size_div=256, name="sd")
# 3D 회전 두 묶음 (원본 CA_Eff_* 와 CA_Eff_*2) — tick() 보다 **앞에서** 만든다
S3 = Spawner(capacity=8, loc=LOC, loc2=LOC2, shapes=SET, map_size=(CHK_W, CHK_H), name="s3")
R3A = S3.rot3d
R3B = S3.rot3d_set("eff2")
# 경계 클램프 — map_size 를 주지 않아 chk DIM 에서 온다
SC = Spawner(capacity=8, loc=LOC, loc2=LOC2, shapes=SET, bounds="clamp", name="sc")
# 고정밀 lengthdir 표 (원본 `Include_CtrigPlib(360, …, 1)` 인 맵 — Mem2)
SP = Spawner(capacity=8, loc=LOC, loc2=LOC2, shapes=SET, map_size=(CHK_W, CHK_H), precise=True, name="sp")


def xform(x, y, size=None, size_div=100, rot=0, r3=None, dx=0, dy=0, cx=0, cy=0, cycle=360,
          W=CHK_W, H=CHK_H, clamp=False, precise=False):
    """참조 변환 (S1 6.3 + 이번에 더한 3D·클램프·고정밀 표). 반환 (X, Y, 소환하나)."""
    if size is None:
        size = size_div
    if size != size_div:
        x = RS.tdiv(s32(u32(x * size)), size_div)
        y = RS.tdiv(s32(u32(y * size)), size_div)
    if u32(rot):
        X2, Y2 = RM.rotate(x, y, rot, cycle, precise)
        x, y = s32(X2), s32(Y2)
    if r3 is not None:
        X3, Y3, _Z = RM.rotate3d(x, y, r3[0], r3[1], r3[2], cycle, precise)
        x, y = s32(X3), s32(Y3)
    X = u32(x + dx + cx)
    Y = u32(y + dy + cy)
    if clamp:
        X = 0 if X >= 0x80000000 else min(X, W - 1)
        Y = 0 if Y >= 0x80000000 else min(Y, H - 1)
    return X, Y, (X <= W - 1 and Y <= H - 1)


# =============================================================================================
# 케이스
# =============================================================================================


def build_cases(s):
    @s.case("sd_push")
    def _(t):
        SD.push(1, t.var("sid"), owner=0, center=(t.var("cx"), t.var("cy")), size=t.var("size", 256), lm=255)

    @s.case("sd_push_const")
    def _(t):
        # 상수 크기 352 = 137.5% (Mem2 `G_CA_Ratio(352)`) — 퍼센트로는 옮길 수 없는 값
        SD.push(1, 0, owner=0, center=(2048, 2048), size=352, lm=255)

    @s.case("sd_push_same")
    def _(t):
        # size == size_div 는 "크기 그대로" — 크기 계산을 건너뛴다
        SD.push(1, 0, owner=0, center=(2048, 2048), size=256, lm=255)

    @s.case("sd_tick")
    def _(t):
        SD.tick()
        t.out("live", SD.live)

    @s.case("s3_ang")
    def _(t):
        R3A.set(t.var("xy"), t.var("yz"), t.var("zx"))
        R3B.set(t.var("xy2"), t.var("yz2"), t.var("zx2"))

    @s.case("s3_push")
    def _(t):
        S3.push(1, t.var("sid"), owner=0, center=(t.var("cx"), t.var("cy")), rotate=t.var("rot"), rot3d=True, lm=255)

    @s.case("s3_push2")
    def _(t):
        S3.push(1, t.var("sid"), owner=0, center=(t.var("cx"), t.var("cy")), rotate=t.var("rot"), rot3d=R3B, lm=255)

    @s.case("s3_push0")
    def _(t):
        S3.push(1, t.var("sid"), owner=0, center=(t.var("cx"), t.var("cy")), rotate=t.var("rot"), lm=255)

    @s.case("s3_tick")
    def _(t):
        S3.tick()
        t.out("live", S3.live)

    @s.case("sc_push")
    def _(t):
        SC.push(1, t.var("sid"), owner=0, center=(t.var("cx"), t.var("cy")), lm=255)

    @s.case("sc_push_skip")
    def _(t):
        SC.push(1, t.var("sid"), owner=0, center=(t.var("cx"), t.var("cy")), lm=255, bounds="skip")

    @s.case("sc_tick")
    def _(t):
        SC.tick()
        t.out("live", SC.live)

    @s.case("sp_ang")
    def _(t):
        SP.rot3d.set(t.var("xy"), t.var("yz"), t.var("zx"))

    @s.case("sp_push")
    def _(t):
        SP.push(1, t.var("sid"), owner=0, center=(t.var("cx"), t.var("cy")), rotate=t.var("rot"),
                rot3d=True, lm=255)

    @s.case("sp_tick")
    def _(t):
        SP.tick()
        t.out("live", SP.live)


class Env:
    def __init__(self, s):
        self.s = s
        self.m = s.machine
        self.lm = locmodel.loc_model(self.m)
        self.seen = 0

    def fresh(self):
        self.s.reset()
        self.lm.clear()
        self.seen = 0

    def new_plots(self):
        out = self.lm.plots[self.seen:]
        self.seen = len(self.lm.plots)
        return out


def one_job(s, env, push, tick, inp, want, label):
    env.fresh()
    s.run(push, inp)
    r = s.run(tick)
    got = [(p.rect[0] & M32, p.rect[1] & M32) for p in env.new_plots()]
    ok = r.error is None and got == want
    detail = ""
    if not ok:
        bad = next((k for k, (a, b) in enumerate(zip(got, want)) if a != b), None)
        detail = "첫 차이 %r: %r / %r (길이 %d/%d, 오류 %r)" % (
            bad, got[bad] if bad is not None else None, want[bad] if bad is not None else None,
            len(got), len(want), r.error)
    s.expect_true(tick, ok, label, detail)


def run_size_div(s, env, rng):
    """size_div=256 = 원본 CA_RatioXY(v, 256, v, 256)."""
    for j in range(24):
        sid = rng.randrange(len(SET.shapes))
        sh = SET.shapes[sid]
        size = rng.choice((256, 0, 1, 128, 352, 512, 65535, rng.randint(0, 65535)))
        cx, cy = rng.randint(0, CHK_W), rng.randint(0, CHK_H)
        want = [(X, Y) for X, Y, ok in
                (xform(x, y, size=size, size_div=256, cx=cx, cy=cy) for x, y in sh.points) if ok]
        one_job(s, env, "sd_push", "sd_tick", {"sid": sid, "cx": u32(cx), "cy": u32(cy), "size": size}, want,
                "size_div=256 job %d (size=%d sid=%d)" % (j, size, sid))
    # 상수 인자 두 판
    for case, size in (("sd_push_const", 352), ("sd_push_same", 256)):
        sh = SET.shapes[0]
        want = [(X, Y) for X, Y, ok in
                (xform(x, y, size=size, size_div=256, cx=2048, cy=2048) for x, y in sh.points) if ok]
        one_job(s, env, case, "sd_tick", {}, want, "size_div=256 상수 size=%d" % size)


def run_rot3d(s, env, rng):
    """rot3d 배선 = 원본 CA_Rotate3D (2D 회전 뒤, 평행이동 앞). 묶음 둘을 섞어 쓴다."""
    for j in range(20):
        sid = rng.randrange(len(SET.shapes))
        sh = SET.shapes[sid]
        a = {k: rng.choice((0, 30, 90, 180, 270, -45, 720, rng.randint(-720, 720)))
             for k in ("xy", "yz", "zx", "xy2", "yz2", "zx2")}
        rot = rng.choice((0, 0, 37, -91))
        cx, cy = rng.randint(0, CHK_W), rng.randint(0, CHK_H)
        env.fresh()
        s.run("s3_ang", {k: u32(v) for k, v in a.items()})
        inp = {"sid": sid, "cx": u32(cx), "cy": u32(cy), "rot": u32(rot)}
        for case, r3 in (("s3_push", (a["xy"], a["yz"], a["zx"])),
                         ("s3_push2", (a["xy2"], a["yz2"], a["zx2"])),
                         ("s3_push0", None)):
            s.run(case, inp)
            r = s.run("s3_tick")
            got = [(p.rect[0] & M32, p.rect[1] & M32) for p in env.new_plots()]
            want = [(X, Y) for X, Y, ok in
                    (xform(x, y, rot=rot, r3=r3, cx=cx, cy=cy) for x, y in sh.points) if ok]
            ok = r.error is None and got == want
            bad = None if ok else next((k for k, (p, q) in enumerate(zip(got, want)) if p != q), None)
            s.expect_true("s3_tick", ok, "rot3d %s job %d (rot=%d %r)" % (case, j, rot, r3),
                          "" if ok else "첫 차이 %r: %r / %r (길이 %d/%d, 오류 %r)"
                          % (bad, got[bad] if bad is not None else None, want[bad] if bad is not None else None,
                             len(got), len(want), r.error))


def run_precise(s, env, rng):
    """precise=True = 고정밀 lengthdir 표(원본 `Include_CtrigPlib(…, LengthdirX=1)`) — 2D·3D 회전 둘 다."""
    for j in range(12):
        sid = rng.randrange(len(SET.shapes))
        sh = SET.shapes[sid]
        a = {k: rng.choice((0, 30, 90, 180, -45, rng.randint(-720, 720))) for k in ("xy", "yz", "zx")}
        rot = rng.choice((0, 37, -91, 123))
        cx, cy = rng.randint(0, CHK_W), rng.randint(0, CHK_H)
        env.fresh()
        s.run("sp_ang", {k: u32(v) for k, v in a.items()})
        s.run("sp_push", {"sid": sid, "cx": u32(cx), "cy": u32(cy), "rot": u32(rot)})
        r = s.run("sp_tick")
        got = [(p.rect[0] & M32, p.rect[1] & M32) for p in env.new_plots()]
        r3 = (a["xy"], a["yz"], a["zx"])
        want = [(X, Y) for X, Y, ok in
                (xform(x, y, rot=rot, r3=r3, cx=cx, cy=cy, precise=True) for x, y in sh.points) if ok]
        ok = r.error is None and got == want
        bad = None if ok else next((k for k, (p, q) in enumerate(zip(got, want)) if p != q), None)
        s.expect_true("sp_tick", ok, "precise 회전+3D job %d (rot=%d %r)" % (j, rot, r3),
                      "" if ok else "첫 차이 %r: %r / %r (길이 %d/%d, 오류 %r)"
                      % (bad, got[bad] if bad is not None else None, want[bad] if bad is not None else None,
                         len(got), len(want), r.error))


def run_bounds(s, env, rng):
    """bounds="clamp" = 원본 CA_Func 기본(0~4095 클램프), "skip" = 지금까지의 동작."""
    edge_sid = SET.shapes.index(EDGE)
    for j in range(16):
        sid = edge_sid if j % 2 == 0 else rng.randrange(len(SET.shapes))
        sh = SET.shapes[sid]
        cx, cy = rng.randint(-2000, CHK_W + 2000), rng.randint(-2000, CHK_H + 2000)
        inp = {"sid": sid, "cx": u32(cx), "cy": u32(cy)}
        for case, clamp in (("sc_push", True), ("sc_push_skip", False)):
            want = [(X, Y) for X, Y, ok in
                    (xform(x, y, cx=cx, cy=cy, clamp=clamp) for x, y in sh.points) if ok]
            one_job(s, env, case, "sc_tick", inp, want,
                    "bounds=%s job %d (sid=%d, 중심 %d,%d)" % ("clamp" if clamp else "skip", j, sid, cx, cy))
        # 클램프 판은 점을 하나도 버리지 않는다
        want_n = len(sh.points)
        env.fresh()
        s.run("sc_push", inp)
        s.run("sc_tick")
        n = len(env.new_plots())
        s.expect_true("sc_tick", n == want_n, "clamp 는 점을 버리지 않는다 job %d" % j, "%d / %d" % (n, want_n))


# =============================================================================================
# 에뮬레이터 밖
# =============================================================================================


def python_checks(ck):
    from eudplib import LoadMap

    LoadMap(BASE_MAP)
    E = EudextError
    # --- 기본값 회귀 (옵션을 안 주면 지금까지와 같다) ---
    d = Spawner(capacity=2, loc=1, loc2=2, name="d0")
    ck.eq("기본 size_div", d.size_div, 100)
    ck.eq("기본 bounds", d.bounds, "skip")
    ck.eq("기본 rtype_none", d.rtype_none, 0)
    ck.eq("기본 rot3d 묶음 없음", len(d._rot3d_sets), 0)
    ck.eq("map_size 는 chk DIM 에서", d.map_size, (CHK_W, CHK_H))
    ck.raises("size_div 0", E, Spawner, loc=1, loc2=2, size_div=0)
    ck.raises("size_div 변수", E, Spawner, loc=1, loc2=2, size_div=EUDVariable())
    ck.raises("bounds 오타", E, Spawner, loc=1, loc2=2, bounds="wrap")
    ck.raises("rot3d_own 정수", E, Spawner, loc=1, loc2=2, rot3d_own=1)
    ck.eq("기본 precise", d.precise, False)
    ck.raises("precise 정수", E, Spawner, loc=1, loc2=2, precise=1)
    # 파이썬 계산도 precise 를 받는다 (preview 가 쓴다)
    ck.eq("rotate_py 기본 = 참조", spawn.rotate_py(700, -300, 37), RS.rotate_py(700, -300, 37))
    pr = spawn.rotate_py(700, -300, 37, 360, True)
    ck.eq("rotate_py precise = 참조", pr, tuple(s32(v) for v in RM.rotate(700, -300, 37, 360, True)))
    ck.eq("transform_py size_div", spawn.transform_py(700, -300, 352, 0, 360, 256),
          (RS.tdiv(s32(u32(700 * 352)), 256), RS.tdiv(s32(u32(-300 * 352)), 256)))
    # --- ② rtype 0 ---
    z = Spawner(capacity=2, loc=1, loc2=2, name="z0")
    ck.eq("rtype id=0 등록", z.rtype("Zero", id=0).id, 0)
    ck.eq("0 을 쓰면 없음 표지가 옮겨 간다", (z.rtype_none, z.default_rtype), (spawn.RTYPE_NONE, spawn.RTYPE_NONE))
    ck.eq("rtype_id(0) = 등록한 0", z.rtype_id(0), 0)
    ck.eq("자동 번호는 1부터", z.rtype("One").id, 1)
    z.default_rtype = "Zero"
    ck.eq("default_rtype 0", z.default_rtype, 0)
    z.default_rtype = None
    ck.eq("default_rtype None", z.default_rtype, spawn.RTYPE_NONE)
    ck.raises("id=0 중복", E, z.rtype, "Zero2", id=0)
    z2 = Spawner(capacity=2, loc=1, loc2=2, name="z2")
    z2._pushed = True
    ck.raises("push 뒤 id=0", E, z2.rtype, "Late", id=0)
    ck.raises("id 음수", E, z2.rtype, "Neg", id=-1)
    # --- ① rot3d 인자 ---
    r = Spawner(capacity=2, loc=1, loc2=2, name="r0")
    ck.eq("rot3d 는 같은 묶음", (r.rot3d is r.rot3d, r.rot3d.index), (True, 1))
    ck.eq("rot3d_set 이름", (r.rot3d_set("b").index, r.rot3d_set("c").index, r.rot3d_set("b").index), (2, 3, 2))
    ck.raises("rot3d 묶음 4개", E, r.rot3d_set, "d")
    ck.eq("rot3d 인자 → 번호", (r._rot3d_index(False, "x"), r._rot3d_index(True, "x"), r._rot3d_index("c", "x"),
                            r._rot3d_index(r.rot3d_set("b"), "x")), (0, 1, 3, 2))
    ck.raises("rot3d 번호 밖", E, r._rot3d_index, 7, "x")
    ck.raises("rot3d 없는 번호", E, Spawner(capacity=2, loc=1, loc2=2, name="r1")._rot3d_index, 2, "x")
    ck.raises("다른 Spawner 의 rot3d", E, Spawner(capacity=2, loc=1, loc2=2, name="r2")._rot3d_index, r.rot3d, "x")
    r._point_sub = object()
    ck.raises("tick 뒤 rot3d 묶음", E, r.rot3d_set, "late")
    r._point_sub = None
    # --- ③ size_div 값이 원본 CA_RatioXY 와 같은가 (컴파일 시점 preview) ---
    sp = Spawner(capacity=2, loc=1, loc2=2, shapes=SET, map_size=(CHK_W, CHK_H), size_div=256, name="pv")
    bad = 0
    for size in (0, 1, 128, 256, 352, 512, 65535):
        pv = sp.preview(SHAPES[0], center=(2048, 2048), size=size)
        want = []
        for x, y in SHAPES[0].points:
            X, Y, ok = xform(x, y, size=size, size_div=256, cx=2048, cy=2048)
            if ok:
                want.append((X, Y))
        if pv != want:
            bad += 1
        # 원본 CA_RatioXY 두 축과 직접 대조 (RM.ratio 는 부호 없는 32비트로 준다)
        for x, y in SHAPES[0].points:
            if (RM.ratio(x, size, 256, "ctrig"), RM.ratio(y, size, 256, "ctrig")) != (
                    u32(RS.tdiv(s32(u32(x * size)), 256)), u32(RS.tdiv(s32(u32(y * size)), 256))):
                bad += 1
    ck.eq("preview(size_div=256) = CA_RatioXY", bad, 0)
    ck.eq("size 생략 = size_div", sp.preview(SHAPES[0], center=(2048, 2048)),
          sp.preview(SHAPES[0], center=(2048, 2048), size=256))
    # --- ④ bounds preview ---
    spc = Spawner(capacity=2, loc=1, loc2=2, shapes=SET, name="pvc")
    ck.eq("preview clamp 는 다 남는다", len(spc.preview(EDGE, center=(0, 0), bounds="clamp")), len(EDGE.points))
    ck.true("preview skip 은 버린다", len(spc.preview(EDGE, center=(0, 0))) < len(EDGE.points))
    ck.raises("preview bounds 오타", E, spc.preview, EDGE, bounds="wrap")


def zero_cost(ck):
    """안 쓰면 트리거가 하나도 늘지 않는다 (기본 동작 불변의 비용 쪽 근거)."""
    from eudplib import CompressPayload, GetTriggerCounter, LoadMap

    LoadMap(BASE_MAP)
    CompressPayload(True)

    def count(**kw):
        ss = ShapeSet([Shape([(1, 2), (3, 4)])], name="zc%d" % count.n)
        sp = Spawner(capacity=4, loc=LOC, loc2=LOC2, shapes=ss, name="zc%d" % count.n, **kw)
        count.n += 1
        with _compat.isolated_scope():
            c0 = GetTriggerCounter()
            sp.push(1, 0, owner=0, center=(100, 100), size=sp.size_div * 3 // 2, rotate=30)
            sp.tick()
            sp._define_xsubs()
            return GetTriggerCounter() - c0

    count.n = 0
    count()  # 예열 (mathx 상수 본문·lru 캐시는 첫 판에서만 페이로드가 는다)
    base = count()
    same_div = count(size_div=100)
    same_bd = count(bounds="skip")
    clamp = count(bounds="clamp")
    div256 = count(size_div=256)
    ck.eq("size_div=100 은 기본과 같다", same_div, base)
    ck.eq("bounds=\"skip\" 은 기본과 같다", same_bd, base)
    ck.true("bounds=clamp 는 트리거가 는다", clamp > base, "%d / %d" % (clamp, base))
    print("  트리거 수: 기본 %d / size_div=100 %d / skip %d / clamp %d / size_div=256 %d"
          % (base, same_div, same_bd, clamp, div256))


def main():
    rng = random.Random(41)
    ck = Checker("t_spawn_p6c (python)")
    python_checks(ck)
    zero_cost(ck)

    s = Suite("t_spawn_p6c", memory={}, prep=lambda m: locmodel.install(m))
    build_cases(s)
    s.build()
    env = Env(s)
    run_size_div(s, env, rng)
    run_rot3d(s, env, rng)
    run_precise(s, env, rng)
    run_bounds(s, env, rng)
    ok = s.report()
    finish(ok, ck.report())


if __name__ == "__main__":
    main()
