"""`spawn` 시험 2 (에뮬레이터 + testing/locmodel 생성 기록): 점 변환 — S1 9.2 벡터 전부와 무작위 차등.

- lengthdir 9줄(점 (r, 0) 을 θ 로 돌린 결과 = (r·cos, r·sin)), rotate 8줄, size 5줄, 전체 변환 7줄(W = 6144, H = 3072 경계 포함)
  — 참조 모델(`ref_spawn`, CtrigAsm CA_Rotate 원문 이식 `ref_mathx`)이 먼저 표 기대값과 같은지 본다
- 무작위 차등: x, y ∈ [−2000, 2000], θ ∈ [−720, 720], size ∈ [0, 255], 평행이동·중심·전역 회전 — 작업마다 255점씩
  (기본 약 2만 점, `EUDEXT_SPAWN_FULL=1` 이면 20만 점 이상 — S1 9.2 "20만 건")
- 저장 "varray"·경계 밖 점 건너뛰기·음수 좌표(부호 없는 비교)

python tests/t_spawn_xform.py
"""

import sys

sys.dont_write_bytecode = True
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import random  # noqa: E402
import time  # noqa: E402

import ref_spawn as RS  # noqa: E402
from eudplib import EUDEndIf, EUDIf  # noqa: E402
from eudext import spawn  # noqa: E402
from eudext.shape import Shape, ShapeSet  # noqa: E402
from eudext.spawn import Spawner  # noqa: E402
from eudext.testing import locmodel  # noqa: E402
from eudext.testing.harness import Suite  # noqa: E402

M32 = 0xFFFFFFFF
u32 = RS.u32
FULL = os.environ.get("EUDEXT_SPAWN_FULL") == "1"
BIG = (65536, 65536)
LOC, LOC2 = 26, 27

# 9.2 벡터용 한 점 도형 (변수 sid 로 고른다)
VEC_POINTS = sorted({(r, 0) for (r, _a), _w in RS.LENGTHDIR_92}
                    | {(x, y) for (x, y, _a), _w in RS.ROTATE_92}
                    | {(x, y) for (x, y, _s), _w in RS.SIZE_92}
                    | {p for p, _kw, _w in RS.FULL_92})
VEC_SET = ShapeSet([Shape([p], name="v%d" % k) for k, p in enumerate(VEC_POINTS)], name="vec")
SW = Spawner(capacity=8, loc=LOC, loc2=LOC2, map_size=BIG, shapes=VEC_SET, name="sw")
SX = Spawner(capacity=8, loc=LOC, loc2=LOC2, map_size=(RS.W92, RS.H92), shapes=VEC_SET, name="sx")


def rnd_shape(seed, n=255, span=2000):
    rng = random.Random(seed)
    return Shape([(rng.randint(-span, span), rng.randint(-span, span)) for _ in range(n)], name="r%d" % seed)


RSHAPES = [rnd_shape(100 + k) for k in range(8)]
EDGE = Shape([(-2000, -2000), (2000, 2000), (0, 0), (-1, 1), (1, -1), (2000, -2000), (-2000, 2000)] * 36 + [(7, 7)] * 3,
             name="edge")  # 255점
RSET = ShapeSet(RSHAPES + [EDGE], name="rset")
RSETV = ShapeSet(RSHAPES[:3] + [EDGE], storage="varray", name="rsetv")
SB = Spawner(capacity=4, loc=LOC, loc2=LOC2, map_size=BIG, shapes=RSET, name="sb")
SBV = Spawner(capacity=4, loc=LOC, loc2=LOC2, map_size=BIG, shapes=RSETV, name="sbv")
SBX = Spawner(capacity=4, loc=LOC, loc2=LOC2, map_size=(RS.W92, RS.H92), shapes=RSET, name="sbx")


def build_cases(s):
    for name, sp in (("sw", SW), ("sx", SX), ("sb", SB), ("sbv", SBV), ("sbx", SBX)):

        def push(t, sp=sp, glob=False):
            rot = t.var("rot")  # 전역 회전 판에서도 입력 칸 이름을 같게
            sp.push(1, t.var("sid"), owner=0, center=(t.var("cx"), t.var("cy")), size=t.var("size", 100),
                    rotate=spawn.GLOBAL if glob else rot, offset=(t.var("dx"), t.var("dy")),
                    lm=t.var("lm", 255))

        s.case(name + "_push")(push)
        s.case(name + "_push_g")(lambda t, sp=sp, push=push: push(t, sp, True))

        def rot(t, sp=sp):
            sp.rotation = t.var("r")

        s.case(name + "_rot")(rot)

        def tick(t, sp=sp):
            sp.tick()
            t.out("live", sp.live)

        s.case(name + "_tick")(tick)

    # 상수 인자 판 (컴파일 시점 값이 그대로 액션에 들어가는 길)
    @s.case("sw_const")
    def _(t):
        k = t.var("k")
        for idx, ((x, y, a), _w) in enumerate(RS.ROTATE_92):
            if EUDIf()(k.Exactly(idx + 1)):
                SW.push(2, Shape([(x, y)]), owner=0, center=(40000, 40000), rotate=a)
            EUDEndIf()
        for idx, ((x, y, sz), _w) in enumerate(RS.SIZE_92):
            if EUDIf()(k.Exactly(100 + idx)):
                SW.push(2, Shape([(x, y)]), owner=0, center=(40000, 40000), size=sz)
            EUDEndIf()


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


def one_point(s, env, name, sid_point, label, want, **inp):
    """한 점 작업 하나 → 그 프레임 소환 좌표 (없으면 None) 를 want 와 비교."""
    env.fresh()
    d = {"sid": VEC_POINTS.index(sid_point), "cx": 0, "cy": 0, "size": 100, "rot": 0, "dx": 0, "dy": 0}
    glob = inp.pop("glob", False)
    rotation = inp.pop("rotation", None)
    d.update({k: u32(v) for k, v in inp.items()})
    if rotation is not None:
        s.run(name + "_rot", {"r": u32(rotation)})
    s.run(name + ("_push_g" if glob else "_push"), d)
    r = s.run(name + "_tick")
    plots = env.new_plots()
    got = (plots[0].rect[0] & M32, plots[0].rect[1] & M32) if plots else None
    ok = r.error is None and got == want and len(plots) <= 1 and r.values["live"] == 0
    s.expect_true(name + "_tick", ok, label, "%r (기대 %r, 오류 %r)" % (got, want, r.error))


def run_vectors(s, env):
    C = 40000
    for (r, a), (c_, s_) in RS.LENGTHDIR_92:
        one_point(s, env, "sw", (r, 0), "9.2 lengthdir(%d, %d)" % (r, a), (u32(C + c_), u32(C + s_)), cx=C, cy=C, rot=a)
    for (x, y, a), (X, Y) in RS.ROTATE_92:
        one_point(s, env, "sw", (x, y), "9.2 rotate(%d, %d, %d)" % (x, y, a), (u32(C + X), u32(C + Y)), cx=C, cy=C, rot=a)
    for (x, y, sz), (X, Y) in RS.SIZE_92:
        one_point(s, env, "sw", (x, y), "9.2 size(%d, %d)·%d" % (x, y, sz), (u32(C + X), u32(C + Y)), cx=C, cy=C,
                  size=sz)
    for (x, y), kw, (X, Y, ok) in RS.FULL_92:
        kw = dict(kw)
        inp = {"cx": kw.pop("cx"), "cy": kw.pop("cy"), "size": kw.pop("size", 100), "dx": kw.pop("dx", 0),
               "dy": kw.pop("dy", 0)}
        if kw.pop("glob", False):
            inp["glob"] = True
            inp["rotation"] = kw.pop("rotation")
        else:
            inp["rot"] = kw.pop("rot", 0)
        assert not kw, kw
        one_point(s, env, "sx", (x, y), "9.2 전체 %r %r" % ((x, y), inp), (X, Y) if ok else None, **inp)
    # 전역 회전: 넣은 뒤 바꾼 값이 소환 순간에 쓰인다 (점마다 읽음) — 같은 작업을 프레임마다 다른 각으로
    env.fresh()
    s.run("sw_rot", {"r": 0})
    s.run("sw_push_g", {"sid": VEC_POINTS.index((0, -32)), "cx": C, "cy": C, "lm": 1, "dx": 0, "dy": 0})
    got = []
    for a in (90, 180):
        s.run("sw_rot", {"r": a})
        s.run("sw_tick")
        got.extend((p.rect[0] - C, p.rect[1] - C) for p in env.new_plots())
    s.expect_true("sw_tick", got == [(32, 0)], "9.2 전역 회전은 넣은 뒤 값(소환 순간)", repr(got))
    # 상수 인자 판
    for idx, ((x, y, a), (X, Y)) in enumerate(RS.ROTATE_92):
        env.fresh()
        s.run("sw_const", {"k": idx + 1})
        s.run("sw_tick")
        got = [(p.rect[0] - C, p.rect[1] - C) for p in env.new_plots()]
        s.expect_true("sw_const", got == [(X, Y)], "9.2 상수 rotate(%d, %d, %d)" % (x, y, a), repr(got))
    for idx, ((x, y, sz), (X, Y)) in enumerate(RS.SIZE_92):
        env.fresh()
        s.run("sw_const", {"k": 100 + idx})
        s.run("sw_tick")
        got = [(p.rect[0] - C, p.rect[1] - C) for p in env.new_plots()]
        s.expect_true("sw_const", got == [(X, Y)], "9.2 상수 size(%d, %d)·%d" % (x, y, sz), repr(got))


def run_random(s, env, name, shapes, jobs, rng, map_size):
    """무작위 차등: 작업 하나 = 255점 한 프레임. 반환: 비교한 점 수."""
    W, H = map_size
    total = 0
    fails = 0
    for j in range(jobs):
        sid = rng.randrange(len(shapes))
        sh = shapes[sid]
        glob = rng.random() < 0.2
        size = rng.choice((100, rng.randint(0, 255)))
        rot = rng.choice((0, rng.randint(-720, 720), rng.randint(-720, 720)))
        rotation = rng.randint(-720, 720)
        if W >= 65536:
            cx, cy = rng.randint(3000, 60000), rng.randint(3000, 60000)
        else:
            cx, cy = rng.randint(-500, W + 500), rng.randint(-500, H + 500)
        dx, dy = rng.randint(-300, 300), rng.randint(-300, 300)
        env.fresh()
        if glob:
            s.run(name + "_rot", {"r": u32(rotation)})
        d = {"sid": sid, "cx": u32(cx), "cy": u32(cy), "size": size, "rot": u32(rot), "dx": u32(dx), "dy": u32(dy),
             "lm": 255}
        s.run(name + ("_push_g" if glob else "_push"), d)
        r = s.run(name + "_tick")
        got = [(p.rect[0] & M32, p.rect[1] & M32) for p in env.new_plots()]
        want = []
        for x, y in sh.points:
            X, Y, ok = RS.transform(x, y, size=size, rot=rot, glob=glob, rotation=rotation, dx=dx, dy=dy, cx=cx, cy=cy,
                                    W=W, H=H)
            if ok:
                want.append((X, Y))
        total += len(sh.points)
        if got != want or r.error:
            fails += 1
            if fails <= 5:
                bad = next((k for k, (a, b) in enumerate(zip(got, want)) if a != b), None)
                s.expect_true(name + "_tick", False, "무작위 %s job %d" % (name, j),
                              "d=%r glob=%r rotation=%d 첫 차이 %r: %r / %r (길이 %d/%d, 오류 %r)"
                              % (d, glob, rotation, bad, got[bad] if bad is not None else None,
                                 want[bad] if bad is not None else None, len(got), len(want), r.error))
        else:
            s.expect_true(name + "_tick", True, "무작위 %s job %d" % (name, j))
    return total


def python_checks(ck):
    for name, ok, got, want in RS.vectors_92_check():
        ck.true("참조 = S1 9.2 " + name, ok, "%r (기대 %r)" % (got, want))
    # 모듈의 파이썬 계산(preview 가 쓰는 것)도 같은 벡터
    for (r, a), want in RS.LENGTHDIR_92:
        ck.eq("spawn.rotate_py lengthdir(%d, %d)" % (r, a), spawn.rotate_py(r, 0, a), want)
    for (x, y, a), want in RS.ROTATE_92:
        ck.eq("spawn.rotate_py(%d, %d, %d)" % (x, y, a), spawn.rotate_py(x, y, a), want)
    for (x, y, sz), want in RS.SIZE_92:
        ck.eq("spawn.transform_py size(%d, %d)·%d" % (x, y, sz), spawn.transform_py(x, y, sz), want)
    # 파이썬 쪽 20만 건 (참조끼리가 아니라 모듈 계산 ↔ ref_mathx) — 에뮬레이터 차등과 별개
    rng = random.Random(77)
    bad = 0
    n = 200000 if FULL else 20000
    for _ in range(n):
        x, y = rng.randint(-2000, 2000), rng.randint(-2000, 2000)
        a, sz = rng.randint(-720, 720), rng.randint(0, 255)
        sx, sy = RS.size_py(x, y, sz)
        want = RS.rotate_py(sx, sy, a) if u32(a) else (sx, sy)
        if spawn.transform_py(x, y, sz, a) != want:
            bad += 1
    ck.eq("transform_py = 참조 (%d건)" % n, bad, 0)


def main():
    rng = random.Random(33)
    ck = Checker("t_spawn_xform (python)")
    python_checks(ck)

    s = Suite("t_spawn_xform", memory={}, prep=lambda m: locmodel.install(m))
    build_cases(s)
    s.build()
    env = Env(s)
    run_vectors(s, env)
    t0 = time.time()
    jobs = 800 if FULL else 80
    n1 = run_random(s, env, "sb", RSET.shapes, jobs, rng, BIG)
    n2 = run_random(s, env, "sbv", RSETV.shapes, max(8, jobs // 10), rng, BIG)
    n3 = run_random(s, env, "sbx", RSET.shapes, max(8, jobs // 10), rng, (RS.W92, RS.H92))
    print("  무작위 차등: db %d점, varray %d점, 경계(6144×3072) %d점 — %.1f초" % (n1, n2, n3, time.time() - t0))
    ok = s.report()
    finish(ok, ck.report())


if __name__ == "__main__":
    main()
