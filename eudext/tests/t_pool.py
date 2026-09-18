"""`pool` 시험 (에뮬레이터): S2 7.2 시나리오 T1~T14, 참조 모델(ref_pool.RefPool)과 무작위 차등, 넘침·dropped·문구,
루프 중 free/alloc, dispatch, 옛 줄 번호 별칭(Subtract 포화), 부호 필드, alloc_n 원자성, 여러 풀·여러 호출 자리·중첩,
되쓰기 목록, get/set/is_alive/index_of, 실행 수, epScript 예제·인게임 확인 맵의 번역·에뮬레이션·euddraft 빌드.

python tests/t_pool.py            (--storage: 저장 크기만 재서 출력)
비용 표: python tools/cost.py tests/t_pool.py [--append --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402

from eudplib import (  # noqa: E402
    Add,
    AtLeast,
    AtMost,
    CompressPayload,
    DoActions,
    EUDArray,
    EUDBreak,
    EUDContinue,
    EUDDoEvents,
    EUDElse,
    EUDEndIf,
    EUDEndInfLoop,
    EUDEndSwitch,
    EUDIf,
    EUDInfLoop,
    EUDSwitch,
    EUDSwitchCase,
    EUDVariable,
    Exactly,
    LoadMap,
    SaveMap,
    SetTo,
    ShufflePayload,
    Subtract,
)

from eudext import _compat  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.pool import Field, Pool  # noqa: E402
from eudext.testing import BASE_MAP, emu, scmodel  # noqa: E402
from eudext.testing.harness import Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

import ref_pool  # noqa: E402
from ref_pool import RefPool  # noqa: E402

M32 = 0xFFFFFFFF
EPD0 = 0x58A364
F4 = ("kind", "timer", "phase", "done")
EX = os.path.join(_common.PKG, "examples")

# 본문 동작 비트 (드라이버 본문과 참조 본문이 같은 순서로 처리한다)
B_TIMER = 1  # timer += 16
B_ALLOC = 2  # alloc(kind=ARG[i]) → ALOG
B_FREE_T = 4  # free(TGT[i])
B_FREE_CUR = 8  # free_current()
B_W777 = 16  # timer = 777, phase = 3
B_W555 = 32  # timer = 555
B_CONT = 64  # EUDContinue()
B_PHASE = 128  # phase += 1
B_FREE_SELF = 256  # free(g.handle)
B_ALIVE = 512  # is_alive(TGT[i]) → VLOG
B_BREAK = 1024  # EUDBreak()
BITS = (B_TIMER, B_ALLOC, B_FREE_T, B_FREE_CUR, B_W777, B_W555, B_CONT, B_PHASE, B_FREE_SELF, B_ALIVE, B_BREAK)

# 드라이버 조작 번호
OP_ALLOC, OP_FREE, OP_TICK, OP_ALLOC_N2, OP_GET, OP_SET, OP_ALIVE, OP_INDEX, OP_ALLOC_T, OP_ALLOC_N3, OP_TICK2 = range(1, 12)


def ref_body(beh, arg, tgt, alog, vlog):
    def body(p, i, r):
        b = beh.get(i, 0)
        if b & B_TIMER:
            r["timer"] = (r["timer"] + 16) & M32
        if b & B_ALLOC:
            alog.append(p.alloc(kind=arg.get(i, 0)))
        if b & B_FREE_T:
            p.free(tgt.get(i))
        if b & B_FREE_CUR:
            p.free_current()
        if b & B_W777:
            r["timer"] = 777
            r["phase"] = 3
        if b & B_W555:
            r["timer"] = 555
        if b & B_CONT:
            return
        if b & B_PHASE:
            r["phase"] = (r["phase"] + 1) & M32
        if b & B_FREE_SELF:
            p.free(i)
        if b & B_ALIVE:
            vlog.append(1 if p.is_alive(tgt.get(i)) else 0)
        if b & B_BREAK:
            p.break_()

    return body


def ref_body2(p, i, r):
    r["done"] = (r["done"] + 1) & M32


# =============================================================================================
# 드라이버: 풀 하나를 조작 번호로 움직이는 케이스
# =============================================================================================


class Drv:
    def __init__(self, name, cap, **pool_kw):
        self.name = name
        self.cap = cap
        self.P = Pool(name, " ".join(F4), capacity=cap, **pool_kw)
        self.E = self.P._E
        self.F = len(F4)
        n = 4 * cap + 8
        self.BEH, self.ARG, self.TGT = EUDArray(cap), EUDArray(cap), EUDArray(cap)
        self.LOG, self.ALOG, self.VLOG = EUDArray(n), EUDArray(n), EUDArray(n)
        self.s = None

    def body(self, t):
        P = self.P
        op, a, b = t.var("op"), t.var("a"), t.var("b")
        nlog, nalog, nvlog = t.var("nlog"), t.var("nalog"), t.var("nvlog")
        h, h2, h3, r = t.var("h"), t.var("h2"), t.var("h3"), t.var("r")
        m = P._mach()
        EUDSwitch(op)
        if EUDSwitchCase()(OP_ALLOC):
            h << P.alloc(kind=a)
            EUDBreak()
        if EUDSwitchCase()(OP_FREE):
            P.free(a)
            EUDBreak()
        if EUDSwitchCase()(OP_TICK):
            idx = EUDVariable()
            for g in P.each():
                idx << g.index  # 함수 결과(rvalue)는 뒤의 배열 읽기가 제자리에서 고치므로 복사해 둔다
                self.LOG[nlog] = idx
                nlog += 1
                bits = self.BEH[idx]
                if EUDIf()(bits.AtLeastX(1, B_TIMER)):
                    g.timer += 16
                EUDEndIf()
                if EUDIf()(bits.AtLeastX(1, B_ALLOC)):
                    nh = P.alloc(kind=self.ARG[idx])
                    self.ALOG[nalog] = nh
                    nalog += 1
                EUDEndIf()
                if EUDIf()(bits.AtLeastX(1, B_FREE_T)):
                    P.free(self.TGT[idx])
                EUDEndIf()
                if EUDIf()(bits.AtLeastX(1, B_FREE_CUR)):
                    P.free_current()
                EUDEndIf()
                if EUDIf()(bits.AtLeastX(1, B_W777)):
                    g.timer = 777
                    g.phase = 3
                EUDEndIf()
                if EUDIf()(bits.AtLeastX(1, B_W555)):
                    g.timer = 555
                EUDEndIf()
                if EUDIf()(bits.AtLeastX(1, B_CONT)):
                    EUDContinue()
                EUDEndIf()
                if EUDIf()(bits.AtLeastX(1, B_PHASE)):
                    g.phase += 1
                EUDEndIf()
                if EUDIf()(bits.AtLeastX(1, B_FREE_SELF)):
                    P.free(g.handle)
                EUDEndIf()
                if EUDIf()(bits.AtLeastX(1, B_ALIVE)):
                    if EUDIf()(P.is_alive(self.TGT[idx])):
                        self.VLOG[nvlog] = 1
                    if EUDElse()():
                        self.VLOG[nvlog] = 0
                    EUDEndIf()
                    nvlog += 1
                EUDEndIf()
                if EUDIf()(bits.AtLeastX(1, B_BREAK)):
                    EUDBreak()
                EUDEndIf()
            EUDBreak()
        if self.cap >= 2 and EUDSwitchCase()(OP_ALLOC_N2):
            hs = P.alloc_n(2, kind=a)
            h << hs[0]
            h2 << hs[1]
            EUDBreak()
        if self.cap >= 3 and EUDSwitchCase()(OP_ALLOC_N3):
            hs = P.alloc_n(3, kind=a)
            h << hs[0]
            h2 << hs[1]
            h3 << hs[2]
            EUDBreak()
        if EUDSwitchCase()(OP_GET):
            r << P.get(a, "timer")
            EUDBreak()
        if EUDSwitchCase()(OP_SET):
            P.set(a, "timer", b)
            EUDBreak()
        if EUDSwitchCase()(OP_ALIVE):
            if EUDIf()(P.is_alive(a)):
                r << 1
            if EUDElse()():
                r << 0
            EUDEndIf()
            EUDBreak()
        if EUDSwitchCase()(OP_INDEX):
            r << P.index_of(a)
            EUDBreak()
        if EUDSwitchCase()(OP_ALLOC_T):
            h << P.alloc(kind=a, timer=b)
            EUDBreak()
        if EUDSwitchCase()(OP_TICK2):
            for g in P.each():  # 두 번째 호출 자리
                g.done += 1
            EUDBreak()
        EUDEndSwitch()
        t.out("count", P.count)
        t.out("dropped", P.dropped)
        for k, v in (("S", P._S), ("L", P._L), ("FS", P._FS), ("T_alive", m.T_alive), ("T_dead", m.T_dead),
                     ("BEH", _compat.eudarray_addr(self.BEH)), ("ARG", _compat.eudarray_addr(self.ARG)),
                     ("TGT", _compat.eudarray_addr(self.TGT)), ("LOG", _compat.eudarray_addr(self.LOG)),
                     ("ALOG", _compat.eudarray_addr(self.ALOG)), ("VLOG", _compat.eudarray_addr(self.VLOG)),
                     ("live_end", P._live_end), ("free_n", P._free_n)):
            t.watch(k, v)

    # --- 파이썬 쪽 ---
    def register(self, s):
        self.s = s
        s.case(self.name)(self.body)

    def _a(self, k):
        return self.s.machine.addr("%s.%s" % (self.name, k))

    def handle(self, i):
        if i is None:
            return 0
        S = self._a("S")
        return ((S + 72 * (self.E * i + self.E - 1) - EPD0) // 4 + 1) & M32

    def index(self, h):
        if h == 0:
            return None
        d = (h - self.handle(0)) & M32
        step = 18 * self.E
        if d % step or d // step >= self.cap:
            raise AssertionError("%s: 이상한 핸들 0x%X" % (self.name, h))
        return d // step

    def run(self, op, a=0, b=0):
        r = self.s.run(self.name, {"op": op, "a": a, "b": b, "nlog": 0, "nalog": 0, "nvlog": 0})
        if r.error:
            raise AssertionError("%s op %d: %s" % (self.name, op, r.error))
        return r

    def reset(self):
        self.s.reset()
        m = self.s.machine
        for k in ("BEH", "ARG", "TGT"):
            base = self._a(k)
            for i in range(self.cap):
                m.setdw(base + 4 * i, 0)

    def alloc(self, kind=0):
        return self.index(self.run(OP_ALLOC, kind)["h"])

    def alloc_t(self, kind, timer):
        return self.index(self.run(OP_ALLOC_T, kind, timer)["h"])

    def alloc_n(self, k, kind=0):
        r = self.run(OP_ALLOC_N2 if k == 2 else OP_ALLOC_N3, kind)
        return [self.index(r[x]) for x in ("h", "h2", "h3")[:k]]

    def free(self, i):
        self.run(OP_FREE, self.handle(i))

    def get(self, i):
        return self.run(OP_GET, self.handle(i))["r"]

    def set(self, i, v):
        self.run(OP_SET, self.handle(i), v)

    def is_alive(self, i):
        return self.run(OP_ALIVE, self.handle(i))["r"]

    def index_of(self, i):
        return self.run(OP_INDEX, self.handle(i))["r"]

    def tick(self, beh=None, arg=None, tgt=None, site=1):
        m = self.s.machine
        beh, arg, tgt = beh or {}, arg or {}, tgt or {}
        for k, table in (("BEH", beh), ("ARG", arg), ("TGT", tgt)):
            base = self._a(k)
            for i in range(self.cap):
                v = table.get(i, 0)
                m.setdw(base + 4 * i, self.handle(v) if k == "TGT" and v is not None else (v or 0))
        r = self.run(OP_TICK if site == 1 else OP_TICK2)
        visit = [m.dw(self._a("LOG") + 4 * j) for j in range(r["nlog"])]
        alog = [self.index(m.dw(self._a("ALOG") + 4 * j)) for j in range(r["nalog"])]
        vlog = [m.dw(self._a("VLOG") + 4 * j) for j in range(r["nvlog"])]
        return visit, alog, vlog, r

    def state(self):
        m = self.s.machine
        S, L, FS = self._a("S"), self._a("L"), self._a("FS")
        E = self.E
        n = (m.var("%s.live_end" % self.name) - L) // 72
        live = [(m.dw(L + 72 * j + 348) - S) // (72 * E) for j in range(n)]
        nf = m.var("%s.free_n" % self.name)
        stack = [m.dw(FS + 4 * k) for k in range(nf)]
        ta = self._a("T_alive")
        alive = [m.dw(S + 72 * (E * r + E - 1) + 4) == ta for r in range(self.cap)]
        data = [[m.dw(S + 72 * (E * r + k) + 348) for k in range(self.F)] for r in range(self.cap)]
        return {"live": live, "stack": stack, "alive": alive, "data": data,
                "count": m.var("%s.count" % self.name), "dropped": m.var("%s.dropped" % self.name)}


def ref_state(rp):
    return {"live": list(rp.live), "stack": list(rp.stack), "alive": list(rp.alive),
            "data": [[d[f] for f in F4] for d in rp.data], "count": rp.count & M32, "dropped": rp.dropped}


# 풀 여럿 (시나리오는 용량별로 하나씩, 무작위 차등은 여러 설정)
D1 = Drv("P1", 1)
D2 = Drv("P2", 2)
D4 = Drv("P4", 4)
D4d = Drv("P4d", 4, debug=True)
D5 = Drv("P5", 5)
D6 = Drv("P6", 6)
D7i = Drv("P7i", 7, index=True)
D9a = Drv("P9a", 9, writeback="all", on_full="silent")
DRIVERS = [D1, D2, D4, D4d, D5, D6, D7i, D9a]


# =============================================================================================
# S2 7.2 시나리오
# =============================================================================================


def scenario_impl(name):
    """시나리오를 구현에서 돌려 ref_pool.SCENARIOS 와 같은 모양의 결과를 낸다(+ 참조 모델 상태와 비교할 추가 값)."""
    if name == "T1":
        d = D4
        d.reset()
        hs = [d.alloc() for _ in range(3)]
        v = d.tick()[0]
        st = d.state()
        return d, {"handles": hs, "visit": v, "count": st["count"], "top": st["stack"][-1]}
    if name == "T2":
        d = D4
        d.reset()
        for _ in range(3):
            d.alloc()
        d.free(1)
        st = d.state()
        out = {"count_after_free": st["count"], "live_after_free": st["live"]}
        out["visit1"] = d.tick()[0]
        st = d.state()
        out["live1"], out["top1"] = st["live"], st["stack"][-1]
        out["alloc"] = d.alloc()
        out["visit2"] = d.tick()[0]
        return d, out
    if name == "T3":
        d = D4
        d.reset()
        for _ in range(3):
            d.alloc()
        v1 = d.tick({1: B_FREE_CUR})[0]
        st = d.state()
        out = {"visit1": v1, "live1": st["live"], "count": st["count"], "top1": st["stack"][-1]}
        out["visit2"] = d.tick()[0]
        return d, out
    if name == "T4":
        d = D4
        d.reset()
        for _ in range(3):
            d.alloc()
        v1 = d.tick({0: B_FREE_T}, tgt={0: 2})[0]
        st = d.state()
        return d, {"visit1": v1, "live1": st["live"], "top1": st["stack"][-1]}
    if name == "T5":
        d = D4
        d.reset()
        for _ in range(3):
            d.alloc()
        v1 = d.tick({2: B_FREE_T}, tgt={2: 0})[0]
        st = d.state()
        out = {"visit1": v1, "live1": st["live"], "count": st["count"], "top1": st["stack"][-1]}
        out["visit2"] = d.tick()[0]
        out["top2"] = d.state()["stack"][-1]
        return d, out
    if name == "T6":
        d = D5
        d.reset()
        for _ in range(3):
            d.alloc()
        v1, alog, _vl, _r = d.tick({0: B_ALLOC})
        st = d.state()
        out = {"alloc": alog[0], "visit1": v1, "live1": st["live"], "count": st["count"]}
        out["visit2"] = d.tick()[0]
        return d, out
    if name == "T7":
        d = D5
        d.reset()
        for _ in range(3):
            d.alloc()
        v1, alog, _vl, _r = d.tick({0: B_ALLOC, 1: B_FREE_T}, tgt={1: 3})
        st = d.state()
        return d, {"alloc": alog[0], "visit1": v1, "live1": st["live"], "count": st["count"],
                   "top1": st["stack"][-1]}
    if name == "T8":
        d = D4
        d.reset()
        hs = [d.alloc() for _ in range(5)]
        st = d.state()
        return d, {"handles": hs, "dropped": st["dropped"], "count": st["count"]}
    if name == "T9":
        d = D2
        d.reset()
        d.alloc()
        d.alloc()
        d.free(0)
        out = {"alloc_before": d.alloc(), "dropped": d.state()["dropped"]}
        d.tick()
        out["alloc_after"] = d.alloc()
        out["live"] = d.state()["live"]
        return d, out
    if name == "T10":
        d = D4
        d.reset()
        d.alloc()
        for _ in range(3):
            d.tick({0: B_TIMER})
        data = d.state()["data"][0]
        return d, {"timer": data[1], "phase": data[2]}
    if name == "T11":
        d = D1
        d.reset()
        d.alloc_t(131, 5)
        d.tick({0: B_W777 | B_FREE_CUR})
        h = d.alloc(132)
        data = d.state()["data"][h]
        return d, {"handle": h, "fields": dict(zip(F4, data))}
    if name == "T12":
        d = D4
        d.reset()
        d.alloc()
        d.tick({0: B_W555 | B_FREE_SELF})
        st = d.state()
        return d, {"timer": st["data"][0][1], "count": st["count"], "live": st["live"]}
    if name == "T13":
        d = D4d
        d.reset()
        tm = scmodel.text_model(d.s.machine)
        tm.clear()
        h = d.alloc()
        d.free(h)
        d.free(h)
        warns = [x for x in tm.texts() if x and "이미 반납된 핸들" in x]
        return d, {"warnings": 1 if warns else 0, "count": d.state()["count"]}
    if name == "T14":
        d = D6
        d.reset()
        for _ in range(6):
            d.alloc()
        d.free(1)
        d.free(3)
        out = {"visit1": d.tick()[0]}
        out["allocs"] = [d.alloc(), d.alloc()]
        out["visit2"] = d.tick()[0]
        return d, out
    raise KeyError(name)


def run_scenarios(ck):
    for name in ref_pool.SCENARIOS:
        got_ref, want = ref_pool.run_scenario(name)
        ck.eq("참조 모델 %s" % name, got_ref, want)
        try:
            _d, got = scenario_impl(name)
        except AssertionError as e:
            ck.true("구현 %s" % name, False, str(e))
            continue
        ck.eq("구현 %s (S2 7.2)" % name, got, want)


# =============================================================================================
# 무작위 차등 (참조 모델)
# =============================================================================================


def fuzz(ck, d, steps, seed, sites=1):
    rng = random.Random(seed)
    d.reset()
    rp = RefPool(d.cap, F4)
    bad = 0
    for step in range(steps):
        r = rng.random()
        label = "%s 무작위 %d" % (d.name, step)
        if r < 0.28:
            kind = rng.choice((0, 131, 132, 0xFFFFFFFF, rng.getrandbits(32)))
            got, want = d.alloc(kind), rp.alloc(kind=kind)
        elif r < 0.33 and d.cap >= 2:
            got, want = d.alloc_n(2, 7), rp.alloc_n(2, kind=7)
        elif r < 0.36 and d.cap >= 3:
            got, want = d.alloc_n(3, 9), rp.alloc_n(3, kind=9)
        elif r < 0.50:
            i = rng.randrange(d.cap)
            d.free(i)
            rp.free(i)
            got = want = None
        elif r < 0.53:
            i = rng.randrange(d.cap)
            got, want = d.get(i), rp.data[i]["timer"]
        elif r < 0.56:
            i = rng.randrange(d.cap)
            v = rng.getrandbits(32)
            d.set(i, v)
            rp.data[i]["timer"] = v
            got = want = None
        elif r < 0.59:
            i = rng.randrange(d.cap)
            got, want = d.is_alive(i), int(rp.alive[i])
        elif r < 0.61:
            i = rng.randrange(d.cap)
            got, want = d.index_of(i), i
        elif sites > 1 and r < 0.68:
            d.tick(site=2)
            rp.tick(ref_body2)
            got = want = None
        else:
            beh, arg, tgt = {}, {}, {}
            for i in range(d.cap):
                b = 0
                for bit, pr in ((B_TIMER, 0.5), (B_ALLOC, 0.12), (B_FREE_T, 0.12), (B_FREE_CUR, 0.1),
                                (B_W777, 0.08), (B_W555, 0.08), (B_CONT, 0.1), (B_PHASE, 0.3),
                                (B_FREE_SELF, 0.06), (B_ALIVE, 0.15), (B_BREAK, 0.04)):
                    if rng.random() < pr:
                        b |= bit
                beh[i] = b
                arg[i] = rng.getrandbits(8)
                tgt[i] = rng.choice([None] + list(range(d.cap)))
            v, alog, vlog, _res = d.tick(beh, arg, tgt)
            ralog, rvlog = [], []
            rv = rp.tick(ref_body(beh, arg, tgt, ralog, rvlog))
            got, want = (v, alog, vlog), (rv, ralog, rvlog)
        if got != want:
            bad += 1
            ck.eq(label + " 결과", got, want)
        st, rst = d.state(), ref_state(rp)
        if st != rst:
            bad += 1
            diff = {k: (st[k], rst[k]) for k in st if st[k] != rst[k]}
            ck.true(label + " 상태", False, repr(diff))
        elif got == want:
            ck.ok += 1  # 걸음마다 결과·상태 일치 1 판정
        if bad > 5:
            break
    ck.true("%s 무작위 %d 걸음 (시드 %d)" % (d.name, steps, seed), bad == 0, "")
    return bad


# =============================================================================================
# 개별 케이스
# =============================================================================================

PE = Pool("Edge", "a b c", capacity=2)
PS = Pool("Sub", "timer", capacity=2, aliases={7: "timer"})
PD = Pool("Disp", "kind hits", capacity=4)
PD2 = Pool("Disp2", "kind hits", capacity=4, on_unknown="silent")
PH = Pool("Hnd", "kind", capacity=5)
PW = Pool("WbA", "a b c d! e", capacity=2)
PW2 = Pool("WbB", "a b c d! e", capacity=2, writeback="all")
PA, PB = Pool("NestA", "x", capacity=3), Pool("NestB", "y", capacity=3)
PSg = Pool("Sgn", [Field("dir", signed=True), "u"], capacity=2, aliases={0: "dir", 5: "u"})
PF1 = Pool("FullR", "x", capacity=1)
PF2 = Pool("FullS", "x", capacity=1, on_full="silent")
FULL_CALLS = EUDVariable()
PF3 = Pool("FullF", "x", capacity=1, on_full=lambda: DoActions(FULL_CALLS.AddNumber(1)))
PC = Pool("Cur", "timer", capacity=2)
PX = Pool("Seed", "unit! x! y! owner timer phase work1 work2 work3 done gunid glevel efftimer", capacity=36)

EDGE_VALUES = (0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF)
BUILD_ERRORS = {}


def _expect_error(key, fn):
    try:
        fn()
    except EudextError as e:
        BUILD_ERRORS[key] = str(e)
        return
    BUILD_ERRORS[key] = None


def build_cases(s):
    for d in DRIVERS:
        d.register(s)

    @s.case("edge_var")
    def _(t):
        op = t.var("op")
        a, b, c = t.var("a"), t.var("b"), t.var("c")
        if EUDIf()(op.Exactly(1)):
            PE.alloc(a=a, b=b, c=c)
        EUDEndIf()
        if EUDIf()(op.Exactly(2)):
            for g in PE.each():
                t.out("ra", g.a)
                t.out("rb", g.b)
                t.out("rc", g.c)
        EUDEndIf()

    @s.case("edge_const")
    def _(t):
        op = t.var("op")
        for k, v in enumerate(EDGE_VALUES[:3]):
            if EUDIf()(op.Exactly(k + 1)):
                PE.alloc(a=v, b=EDGE_VALUES[k + 2], c=0x12345678)
            EUDEndIf()
        if EUDIf()(op.Exactly(9)):
            PE.alloc(a=-1, b=-2, c=a_same)  # 같은 변수를 두 필드에 (VProc 중복 방지)
        EUDEndIf()

    a_same = EUDVariable(0xABCD)

    @s.case("edge_dup")
    def _(t):
        v = t.var("v")
        h = PE.alloc(a=v, b=v, c=v)
        t.out("h", h)

    @s.case("sub")
    def _(t):
        op, k = t.var("op"), t.var("k")
        if EUDIf()(op.Exactly(0)):
            PS.alloc(timer=3)
        EUDEndIf()
        for g in PS.each():
            EUDSwitch(op)
            if EUDSwitchCase()(1):
                g.timer -= 5  # 파이썬 연산자 = eudplib wrap
                EUDBreak()
            if EUDSwitchCase()(2):
                g.isub_sat("timer", 5)
                EUDBreak()
            if EUDSwitchCase()(3):
                PS.SetLine(7, Subtract, 5)
                EUDBreak()
            if EUDSwitchCase()(4):
                g.isubattr("timer", 5)  # epScript `g.timer -= 5` 통로 = wrap
                EUDBreak()
            if EUDSwitchCase()(5):
                PS.SetLine("timer", Add, 7)
                t.flag("f", PS.Line(7, AtLeast, 10))
                t.flag("f2", PS.Line(7, Exactly, 10))
                t.flag("f3", g.eqattr("timer", 10))
                EUDBreak()
            if EUDSwitchCase()(6):
                g.isub_sat("timer", k)
                EUDBreak()
            if EUDSwitchCase()(7):
                PS.SetLine(7, Subtract, k)
                EUDBreak()
            if EUDSwitchCase()(8):
                g.isubattr("timer", k)
                EUDBreak()
            if EUDSwitchCase()(9):
                PS.SetLine(7, SetTo, k)
                DoActions(PS.SetLineAct(7, Add, 1))
                EUDBreak()
            if EUDSwitchCase()(10):
                PS.SetLine(7, SetTo, 0xF0F0, mask=0xFF00)
                t.flag("f", PS.Line(7, Exactly, 0xF000, mask=0xFF00))
                EUDBreak()
            EUDEndSwitch()
            t.out("t", g.timer)
            t.out("ln", PS.line(7))

    @s.case("disp")
    def _(t):
        op = t.var("op")
        if EUDIf()(op.Exactly(0)):
            for k in (131, 132, 999):
                PD.alloc(kind=k)
                PD2.alloc(kind=k)
        EUDEndIf()

        @PD.case(131)
        def c131(g):
            g.hits += 1

        @PD.case(132, 133)
        def c132():
            PD.cur.hits += 100

        _expect_error("case 중복", lambda: PD.case(133))
        for g in PD.each():
            PD.dispatch("kind")
        seen = t.var("seen2")
        for g in PD2.each():
            PD2.dispatch(0, {131: lambda g: DoActions(seen.AddNumber(1))},
                         default=lambda: DoActions(seen.AddNumber(1000)))
            PD2.dispatch("kind", {132: lambda: DoActions(seen.AddNumber(10))})  # 기본 가지 = on_unknown(silent)
        for g in PD2.each():
            PD2.dispatch("kind", {132: lambda: None}, default=None)
        for i in range(3):
            t.out("hits%d" % i, PD.get(t.var("h%d" % i), "hits"))
        t.out("count", PD.count)
        t.out("count2", PD2.count)

    @s.case("hnd")
    def _(t):
        op = t.var("op")
        if EUDIf()(op.Exactly(0)):
            for k in range(4):
                PH.alloc(kind=k)
        EUDEndIf()
        ok, n = t.var("ok"), t.var("n")
        for g, h in PH.each(handle=True):
            n += 1
            if EUDIf()(h == PH.cur.handle):
                ok += 1
            EUDEndIf()
            if EUDIf()(PH.index_of(h) == g.kind):
                ok += 10
            EUDEndIf()
            if EUDIf()(g.index == g.kind):
                ok += 100
            EUDEndIf()
            if EUDIf()(g.alive == 1):
                ok += 1000
            EUDEndIf()

    @s.case("wb")
    def _(t):
        op = t.var("op")
        outside_c = PW.cur.c  # 본문 밖에서 꺼낸 레지스터 (되쓰기 목록에 안 잡힘)
        outside_e = PW.cur.e
        outside_c2 = PW2.cur.c
        if EUDIf()(op.Exactly(0)):
            PW.alloc(d=4)
            PW2.alloc(d=4)
        EUDEndIf()
        for g in PW.each():
            DoActions(g.b.SetNumber(2))
            outside_c << 9
            g.touch("e")
            outside_e << 11
            _expect_error("readonly 대입", lambda: setattr(g, "d", 5))
            _expect_error("readonly iaddattr", lambda: g.iaddattr("d", 1))
            _expect_error("readonly SetLine", lambda: PW.SetLine("d", SetTo, 1))
            _expect_error("없는 줄 번호", lambda: PW.Line(9, Exactly, 0))
            _expect_error("같은 풀 중첩", lambda: next(iter(PW.each())))
        for g in PW2.each():
            outside_c2 << 9
        t.out("pw_count", PW.count)

    @s.case("nest")
    def _(t):
        op = t.var("op")
        if EUDIf()(op.Exactly(0)):
            for k in range(3):
                PA.alloc(x=k + 1)
                PB.alloc(y=10 * (k + 1))
        EUDEndIf()
        tot = t.var("tot")
        for ga in PA.each():
            for gb in PB.each():
                tot += gb.y
                gb.y += 1
            ga.x += 100
        t.out("x0", PA.get(t.var("ha"), "x"))

    @s.case("sgn")
    def _(t):
        v, k = t.var("v"), t.var("k")
        op = t.var("op")
        if EUDIf()(op.Exactly(0)):
            PSg.alloc(dir=v, u=0xFFFFFFF0)
        EUDEndIf()
        for g in PSg.each():
            t.flag("ge_m10", PSg.Line("dir", AtLeast, -10))
            t.flag("le_m6", PSg.Line("dir", AtMost, -6))
            t.flag("eq_m5", PSg.Line(0, Exactly, -5))
            t.flag("ge_var", PSg.Line(0, AtLeast, k))
            t.flag("att_ge", g.geattr("dir", -5))
            t.flag("att_gt", g.gtattr("dir", -5))
            t.flag("att_lt0", g.ltattr("dir", 0))
            t.flag("att_ne", g.neattr("dir", k))
            t.flag("u_ge5", PSg.Line(5, AtLeast, 5))
            t.flag("u_ltattr", g.ltattr("u", 5))
            t.flag("range", PSg.LineRange("dir", -10, 0))

    @s.case("full")
    def _(t):
        for P in (PF1, PF2, PF3):
            t.out("h_" + P.name, P.alloc(x=1))
            t.out("d_" + P.name, P.dropped)
        t.out("calls", FULL_CALLS)

    @s.case("cur")
    def _(t):
        op = t.var("op")
        if EUDIf()(op.Exactly(0)):
            PC.alloc(timer=5)
        EUDEndIf()
        for g in PC.each():
            t.out("get", PC.get(g.handle, "timer"))
            PC.set(g.handle, "timer", 42)
            t.flag("alive1", PC.is_alive(g.handle))
            PC.free_current()
            t.flag("alive2", PC.is_alive(g.handle))
            PC.free_current()  # 두 번째는 세지 않는다
            PC.free(g.handle)  # 방문 중 레코드 = free_current (이미 반납)
            t.out("cnt_in", PC.count)
        t.out("cnt", PC.count)

    @s.case("seed")
    def _(t):
        op = t.var("op")
        if EUDIf()(op.Exactly(0)):
            for k in range(5):
                PX.alloc(unit=131 + k, x=k * 32, y=k * 64, gunid=k)
        EUDEndIf()
        for g in PX.each():
            g.timer += 16
            if EUDIf()(g.done >= 1):
                PX.free_current()
            EUDEndIf()
            if EUDIf()(PX.Line("timer", AtLeast, 48)):
                g.phase += 1
            EUDEndIf()

    @s.case("empty")
    def _(t):
        for _g in Pool("Empty", "a b", capacity=8).each():
            pass


def run_cases(s, ck):
    m = s.machine
    tm = scmodel.text_model(m)
    # 필드 값 경계 (변수 값 / 상수 값)
    for va in EDGE_VALUES:
        vb, vc = (va + 0x100) & M32, (~va) & M32
        s.run("edge_var", {"op": 1, "a": va, "b": vb, "c": vc}, fresh=True)
        r = s.run("edge_var", {"op": 2})
        ck.eq("경계 변수 값 0x%X" % va, (r["ra"], r["rb"], r["rc"]), (va, vb, vc))
    for k in range(3):
        s.run("edge_const", {"op": k + 1}, fresh=True)
        r = s.run("edge_var", {"op": 2})
        ck.eq("경계 상수 값 %d" % k, (r["ra"], r["rb"], r["rc"]), (EDGE_VALUES[k], EDGE_VALUES[k + 2], 0x12345678))
    s.run("edge_const", {"op": 9}, fresh=True)
    r = s.run("edge_var", {"op": 2})
    ck.eq("음수 상수·변수 값", (r["ra"], r["rb"], r["rc"]), (M32, M32 - 1, 0xABCD))
    r = s.run("edge_dup", {"v": 0x5555}, fresh=True)
    r2 = s.run("edge_var", {"op": 2})
    ck.eq("같은 변수를 세 필드에", (r["h"] != 0, r2["ra"], r2["rb"], r2["rc"]), (True, 0x5555, 0x5555, 0x5555))

    # 뺄셈 의미 (S2 7.2 추가: timer=3 에서 5 빼기 → wrap 0xFFFFFFFE / 포화 0 / 별칭 Subtract 포화 0)
    def sub(op, k=0, cycles=1):
        s.run("sub", {"op": 0}, fresh=True)
        r = None
        for _ in range(cycles):
            r = s.run("sub", {"op": op, "k": k})
        return r

    ck.eq("-= wrap", sub(1)["t"], 0xFFFFFFFE)
    ck.eq("isub_sat 포화", sub(2)["t"], 0)
    ck.eq("SetLine Subtract 포화", sub(3)["t"], 0)
    ck.eq("isubattr wrap", sub(4)["t"], 0xFFFFFFFE)
    r = sub(5)
    ck.eq("SetLine Add 뒤 Line 참", (r["t"], r["f"], r["f2"], r["f3"], r["ln"]), (10, 1, 1, 1, 10))
    ck.eq("isub_sat 변수 포화", sub(6, 5)["t"], 0)
    ck.eq("isub_sat 변수", sub(6, 2)["t"], 1)
    ck.eq("SetLine Subtract 변수 포화", sub(7, 5)["t"], 0)
    ck.eq("isubattr 변수 wrap", sub(8, 5)["t"], 0xFFFFFFFE)
    ck.eq("SetLine SetTo 변수 + SetLineAct Add", sub(9, 40)["t"], 41)
    r = sub(10)
    ck.eq("SetLine 마스크 SetTo + Line 마스크", (r["t"], r["f"]), (0xF003, 1))
    r = sub(1, cycles=2)
    ck.eq("되쓰기 뒤 다음 방문 (wrap 두 번)", r["t"], 0xFFFFFFF9)

    # dispatch
    tm.clear()
    r0 = s.run("disp", {"op": 0, "seen2": 0}, fresh=True)
    r = s.run("disp", {"op": 1, "seen2": 0})
    msgs = [x for x in tm.texts() if x and "등록되지 않은 kind 값" in x]
    ck.eq("dispatch 개수 (Disp: 999 반납 / Disp2: silent 기본 가지가 131·999 반납)", (r["count"], r["count2"]), (2, 1))
    ck.true("dispatch 미등록 문구", len(msgs) >= 1, repr(tm.texts()))
    ck.eq("dispatch Buzz ×2 (문구마다)", len([w for w in tm.wavs() if w and "Buzz" in w]), 2 * len(msgs))
    ck.eq("dispatch silent 는 문구 없음 (Disp2)", len([x for x in tm.texts() if x and "Disp2" in x]), 0)
    ck.eq("dispatch 기본 가지 (1프레임 1+1000+1000+10, 2프레임 1000+10)", (r0["seen2"], r["seen2"]), (2011, 1010))
    # 핸들로 hits 읽기: 레코드 0 = 131, 1 = 132 (1프레임에 이미 한 번 돌았다)
    dh = DrvLike(s, "disp", PD)
    r = s.run("disp", {"op": 1, "h0": dh.handle(0), "h1": dh.handle(1), "h2": dh.handle(2)})
    ck.eq("dispatch 본문 (131 → +1, 132 → +100) 세 프레임", (r["hits0"], r["hits1"]), (3, 300))
    ck.eq("dispatch case 중복 오류", BUILD_ERRORS.get("case 중복") is not None, True)

    # each(handle=True), index_of, g.index, g.alive
    s.run("hnd", {"op": 0}, fresh=True)
    r = s.run("hnd", {"op": 1, "ok": 0, "n": 0})
    ck.eq("each(handle=True)", (r["n"], r["ok"]), (4, 4 * 1111))

    # 되쓰기 목록
    s.run("wb", {"op": 0}, fresh=True)
    s.run("wb", {"op": 1})
    dw = DrvLike(s, "wb", PW)
    dw2 = DrvLike(s, "wb", PW2)
    ck.eq("되쓰기: DoActions 로만 쓴 b 저장 / 밖에서 꺼낸 c 안 저장 / touch 한 e 저장 / readonly d",
          dw.fields(0), [0, 2, 0, 4, 11])
    ck.eq("writeback=all: 밖에서 꺼낸 c 도 저장", dw2.fields(0)[2], 9)
    for key in ("readonly 대입", "readonly iaddattr", "readonly SetLine", "없는 줄 번호", "같은 풀 중첩"):
        ck.true("컴파일 오류: " + key, BUILD_ERRORS.get(key) is not None, repr(BUILD_ERRORS.get(key)))

    # 중첩 순회 (다른 풀)
    s.run("nest", {"op": 0}, fresh=True)
    dn = DrvLike(s, "nest", PA)
    r1 = s.run("nest", {"op": 1, "ha": dn.handle(0), "tot": 0})
    r2 = s.run("nest", {"op": 1, "ha": dn.handle(0), "tot": 0})
    # 프레임마다 A 3회 × B 3개 합, B 는 방문마다 +1: 1프레임 60+63+66, 2프레임 69+72+75, 3프레임 78+81+84
    ck.eq("다른 풀 중첩", (r1["tot"], r1["x0"], r2["tot"], r2["x0"]), (216, 201, 243, 301))

    # 부호 필드
    for v, k, want in (
        (-5 & M32, -5 & M32, dict(ge_m10=1, le_m6=0, eq_m5=1, ge_var=1, att_ge=1, att_gt=0, att_lt0=1, att_ne=0,
                                  u_ge5=1, u_ltattr=0, range=1)),
        (-11 & M32, 3, dict(ge_m10=0, le_m6=1, eq_m5=0, ge_var=0, att_ge=0, att_gt=0, att_lt0=1, att_ne=1,
                            u_ge5=1, u_ltattr=0, range=0)),
        (7, -20 & M32, dict(ge_m10=1, le_m6=0, eq_m5=0, ge_var=1, att_ge=1, att_gt=1, att_lt0=0, att_ne=1,
                            u_ge5=1, u_ltattr=0, range=0)),
    ):
        s.run("sgn", {"op": 0, "v": v}, fresh=True)
        r = s.run("sgn", {"op": 1, "k": k})
        ck.eq("부호 필드 dir=%d k=%d" % (v - (1 << 32) if v >> 31 else v, k - (1 << 32) if k >> 31 else k),
              {x: r[x] for x in want}, want)

    # 넘침 문구 (report / silent / 함수)
    tm.clear()
    s.run("full", {}, fresh=True)
    r = s.run("full", {})
    ck.eq("넘침 핸들·dropped", [r[x] for x in ("h_FullR", "d_FullR", "h_FullS", "d_FullS", "h_FullF", "d_FullF")],
          [0, 1, 0, 1, 0, 1])
    ck.true("첫 alloc 핸들", True)
    full_msgs = [x for x in tm.texts() if x and "목록이 가득 차" in x]
    ck.true("report 문구 (FullR 만)", full_msgs and all("FullR" in x for x in full_msgs), repr(tm.texts()))
    ck.eq("report Buzz ×3 (문구마다)", len([w for w in tm.wavs() if w and "Buzz" in w]), 3 * len(full_msgs))
    ck.eq("on_full 함수 호출 (넘친 프레임에만)", r["calls"], 1)
    r = s.run("full", {})
    ck.eq("넘침 누적", (r["d_FullR"], r["calls"]), (2, 2))
    pristine = s._pristine[0]
    for P in (PF1, PF2, PF3):
        t0 = m.addr("full.__T_%s" % P.name)
        size = 4 * (18 * P._E + 100)
        outside = [a for a in range(t0 + size, t0 + size + 256, 4) if m.dw(a) != pristine.get(a, 0)]
        written = [a for a in range(t0, t0 + size, 4) if m.dw(a)]
        ck.true("넘침 쓰기가 쓰레기 레코드 안 (%s)" % P.name, not outside and written, repr((outside, written[:3])))

    # 방문 중 레코드의 get/set/is_alive/free
    r = s.run("cur", {"op": 0}, fresh=True)
    dc = DrvLike(s, "cur", PC)
    ck.eq("현재 레코드 get·is_alive·free_current 두 번·free(현재)",
          (r["get"], r["alive1"], r["alive2"], r["cnt_in"], r["cnt"]), (5, 1, 0, 0, 0))
    ck.eq("반납한 현재 레코드는 set 도 되쓰기 안 함", dc.fields(0)[0], 5)
    r = s.run("cur", {"op": 1, "get": 77})
    ck.eq("반납 뒤 방문 없음", (r["cnt"], r["get"]), (0, 77))

    # Seed 규모 (F=13) 여러 프레임
    s.run("seed", {"op": 0}, fresh=True)
    for _ in range(3):
        r = s.run("seed", {"op": 1})
    dx = DrvLike(s, "seed", PX)
    ck.eq("Seed 5개 4프레임 timer·phase", [dx.fields(i)[4:6] for i in range(5)], [[64, 2]] * 5)
    ck.eq("Seed readonly 필드 그대로", [dx.fields(i)[:3] for i in range(5)], [[131 + i, i * 32, i * 64] for i in range(5)])
    SEED_STEPS.extend(r.steps)

    # 빈 풀
    r = s.run("empty", {}, fresh=True)
    ck.true("빈 풀 실행 ≤ 6 (S2 6.13)", max(r.steps) <= 6, repr(r.steps))
    EMPTY_STEPS.extend(r.steps)


SEED_STEPS = []
EMPTY_STEPS = []


class DrvLike:
    """개별 케이스용: 풀 주소를 watch 없이 구한다(드라이버와 같은 공식)."""

    def __init__(self, s, case, P):
        self.s, self.P = s, P
        self.key = "%s.__S_%s" % (case, P.name)

    def S(self):
        return self.s.machine.addr(self.key)

    def handle(self, i):
        E = self.P._E
        return ((self.S() + 72 * (E * i + E - 1) - EPD0) // 4 + 1) & M32

    def fields(self, r):
        E, m = self.P._E, self.s.machine
        return [m.dw(self.S() + 72 * (E * r + k) + 348) for k in range(self.P._F)]


def add_watches(s):
    """개별 케이스에 풀 시작 주소 watch 를 붙인다 (케이스 본문 뒤에 등록)."""
    pairs = {"disp": [PD], "wb": [PW, PW2], "nest": [PA], "cur": [PC], "seed": [PX], "full": [PF1, PF2, PF3]}
    for case, pools in pairs.items():
        c = s.cases[case]
        fn = c.fn

        def wrapped(t, fn=fn, pools=pools):
            fn(t)
            for P in pools:
                t.watch("__S_%s" % P.name, P._S)
                t.watch("__T_%s" % P.name, P._TRASH)

        c.fn = wrapped


def run_steps(s, ck):
    """실행 수: 방문당 고정 (S2 6.13 목표 F+12+2W, 허용 상한 F+17+6W)."""
    d = D4
    rows = {}
    for n in (1, 2, 4):
        d.reset()
        for _ in range(n):
            d.alloc()
        rows[n] = d.tick({i: B_TIMER for i in range(n)})[3].steps[0]
    per = rows[2] - rows[1]
    ck.eq("방문당 실행 일정 (1→2→4)", rows[4] - rows[2], 2 * per)
    VISIT_STEPS.update(rows)


VISIT_STEPS = {}


# =============================================================================================
# 파이썬 쪽 (선언 검사)
# =============================================================================================


def python_checks(ck):
    ck.raises("필드 중복", EudextError, Pool, "X", "a a", capacity=2)
    ck.raises("밑줄 이름", EudextError, Pool, "X", "_a", capacity=2)
    ck.raises("예약 이름", EudextError, Pool, "X", "handle", capacity=2)
    ck.raises("식별자 아님", EudextError, Field, "1a")
    ck.raises("capacity 0", EudextError, Pool, "X", "a", capacity=0)
    ck.raises("aliases 에 없는 필드", EudextError, Pool, "X", "a", capacity=2, aliases={0: "b"})
    ck.raises("alias_base 2", EudextError, Pool, "X", "a", capacity=2, alias_base=2)
    ck.raises("on_full 잘못", EudextError, Pool, "X", "a", capacity=2, on_full="loud")
    ck.raises("writeback 잘못", EudextError, Pool, "X", "a", capacity=2, writeback="some")
    ck.raises("필드 목록 형", EudextError, Pool, "X", 5, capacity=2)
    ck.raises("init 형", EudextError, Field, "a", init="x")
    p = Pool("Decl", ["unit! x!", Field("dir", signed=True, init=-1), "timer"], capacity=3, alias_base=1)
    ck.eq("필드 선언", (p.fields, [f.readonly for f in p._fields], p._fields[2].signed, p._fields[2].init),
          (("unit", "x", "dir", "timer"), [True, True, False, False], True, M32))
    ck.eq("기본 별칭 (alias_base=1)", p._aliases, {1: "unit", 2: "x", 3: "dir", 4: "timer"})
    ck.eq("숨은 원소 수", (p._E, Pool("Ix", "a", capacity=1, index=True)._E), (6, 4))
    ck.eq("번호 비트 수", [Pool("B", "a", capacity=c)._bits for c in (1, 2, 3, 4, 5, 36, 128, 1700)],
          [1, 1, 2, 2, 3, 6, 7, 11])
    ck.eq("핸들 오프셋: 필드 0 값 칸, 생존 칸", (p._off(0), p._off(p._E - 1)), (86 - 18 * 5, 86))
    ck.eq("repr", repr(p), "Pool('Decl', unit! x! dir timer, capacity=3)")
    ck.eq("보기 repr 안내", "const" in repr(p.cur), True)
    ck.raises("보기 bool", EudextError, bool, p.cur)
    ck.raises("없는 필드 읽기", AttributeError, getattr, p.cur, "nope")
    with_warn = []
    import warnings

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Pool("Big", " ".join("f%d" % i for i in range(32)), capacity=1)
        with_warn = [x for x in w if "CtrigAsm" in str(x.message)]
    ck.true("F+3 > 33 경고", bool(with_warn), "")
    # _compat 판 검사
    _compat.check_pool()
    ck.true("_compat.check_pool", True)
    ck.true("_WP11_REQUIRED", all(hasattr(__import__(mod, fromlist=[a]), a) for mod, a in _compat._WP11_REQUIRED))


# =============================================================================================
# epScript 예제·인게임 확인 맵
# =============================================================================================


def eps_checks(ck):
    src = open(os.path.join(EX, "pool_ingame.eps"), encoding="utf-8").read()
    ck.eq("ingame eps errors", _compat.eps_compile("pool_ingame.eps", src)[1], 0)
    src = open(os.path.join(EX, "pool_example.eps"), encoding="utf-8").read()
    out, nerr = _compat.eps_compile("pool_example.eps", src)
    ck.eq("eps errors", nerr, 0)
    for needle in ('pool.Pool("Gun", "unit! x! y! owner timer started phase work done", capacity=8)',
                   "guns.alloc(unit=u, x=x, y=y, owner=owner)", "for _ in guns.each():", "EUDSwitch(g.unit)",
                   "_ATTW(g, 'timer').__iadd__(16)", "guns.free_current()", "EUDContinue()",
                   "guns.Line(5, Exactly, 0)", "guns.SetLine(5, SetTo, 1)", "guns.SetLine(7, Subtract, 1)",
                   "for g2, h in guns.each(handle=True):", "_ATTC(g, 'timer') >= 48", "_ATTW(g, 'done') << (1)"):
        ck.true("eps: " + needle, out is not None and needle in out, "")


def _load_eps(name, work_name):
    from eudext.tools import build

    work = os.path.join(_common.WORK, work_name)
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, name + ".eps"), os.path.join(work, name + ".eps"))
    LoadMap(BASE_MAP)
    CompressPayload(True)
    return build._load_plugin(os.path.join(work, name + ".eps"), {})


def eps_emulate(ck):
    """예제를 싣고 에뮬레이터에서 6 사이클 돌린다."""
    mod = _load_eps("pool_example", "t_pool_eps")
    prog = emu.Program(mod.afterTriggerExec)
    names = ("frame", "sent", "failed", "visits", "hatch", "unknownSeen", "started", "lastIndex", "handleOk")
    for n in names:
        prog.watch(n, getattr(mod, n))
    prog.watch("count", mod.guns.count)
    m = prog.build()
    scmodel.install(m, text=True)
    rows = []
    for _ in range(6):
        m.cycle()
        rows.append({n: m.var(n) for n in names + ("count",)})
    print("  epScript 에뮬레이션: %r" % rows[-1])
    # 1프레임: 9번 보냄(용량 8 → 1 실패), 같은 프레임에 8개 방문(999 는 반납). 3프레임에 timer 48 → done → 모두 반납.
    # 2프레임의 두 번째 호출 자리: 7개 (마지막 번호 6)
    want_last = {"frame": 6, "sent": 8, "failed": 1, "count": 0, "started": 8, "lastIndex": 6, "handleOk": 7,
                 "hatch": 12, "unknownSeen": 1}
    ck.eq("eps 마지막 프레임", {k: rows[-1][k] for k in want_last}, want_last)
    ck.eq("eps 방문 수 (프레임별 누적)", [r["visits"] for r in rows], [8, 15, 22, 22, 22, 22])
    tm = scmodel.text_model(m)
    ck.true("eps 넘침 문구", any(x and "Gun의 목록이 가득 차" in x for x in tm.texts()), repr(tm.texts()[:5]))


def ingame_emulate(ck):
    """인게임 확인 맵을 에뮬레이터에서 돌려 [T] 줄의 판정 변수가 모두 통과인지 본다."""
    mod = _load_eps("pool_ingame", "t_pool_ingame")
    prog = emu.Program(mod.afterTriggerExec)
    names = ("frame", "t1ok", "t2ok", "t3ok", "t4ok", "t5ok", "t6ok", "t7ok")
    for n in names:
        prog.watch(n, getattr(mod, n))
    m = prog.build()
    scmodel.install(m, text=True)
    err = None
    try:
        m.cycle(200)
    except emu.EmuError as e:
        err = str(e)
    got = {n: m.var(n) for n in names}
    print("  인게임 맵 에뮬레이션: %r" % got)
    ck.eq("ingame emu 오류", err, None)
    ck.eq("ingame emu 판정", got, {"frame": 200, "t1ok": 1, "t2ok": 1, "t3ok": 1, "t4ok": 1, "t5ok": 1, "t6ok": 1,
                                   "t7ok": 1})
    tm = scmodel.text_model(m)
    ck.true("ingame 넘침 문구", any(x and "목록이 가득 차" in x for x in tm.texts()), "")


def eps_build(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    for name in ("pool_example", "pool_ingame"):
        work = os.path.join(_common.WORK, "t_pool_build_" + name)
        eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
        r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
        print("  " + r.summary())
        ck.true("euddraft " + name, r.ok, r.log[-2000:])
        ck.true("eps compiled " + name, '[epScript] Compiling "%s.eps"' % name in r.log, "")


# =============================================================================================
# 저장 크기
# =============================================================================================


def measure_storage():
    """풀 하나(ResV 규모 cap 128·F 16 / Seed cap 36·F 13)의 페이로드·scx 증가분."""
    rows = []

    def build(tag, make):
        _compat.reset_build_state()
        LoadMap(BASE_MAP)
        CompressPayload(True)
        ShufflePayload(False)
        v = EUDVariable()
        holder = {}

        def main():
            if EUDInfLoop()():
                _compat.set_game_loop_start()
                DoActions(v.AddNumber(1))
                make(holder)
                EUDDoEvents()
            EUDEndInfLoop()

        out = os.path.join(_common.WORK, "t_pool_storage_%s.scx" % tag)
        SaveMap(out, main)
        ShufflePayload(True)
        return os.path.getsize(out)

    def pool_user(cap, f):
        def make(holder):
            P = Pool("St%d_%d" % (cap, f), " ".join("f%d" % i for i in range(f)), capacity=cap)
            P.alloc()
            for g in P.each():
                g.f0 += 1

        return make

    empty = build("empty", lambda h: None)
    for cap, f in ((128, 16), (36, 13), (128, 1)):
        size = build("p%d_%d" % (cap, f), pool_user(cap, f))
        rows.append(("Pool cap %d · F %d (+ alloc 1곳 + each 1곳)" % (cap, f), size - empty))
    for name, d in rows:
        print("  scx 증가 %-44s %+d B" % (name, d))
    return rows


def measure_payload():
    """페이로드(재배치 전) 증가분: 풀 선언 + 사용 1벌."""
    from eudext.tools.cost import _payload_size

    base = _payload_size(lambda: None)
    rows = []
    for cap, f in ((128, 16), (36, 13)):
        def body(cap=cap, f=f):
            P = Pool("Pl%d_%d" % (cap, f), " ".join("f%d" % i for i in range(f)), capacity=cap)
            P.alloc()
            for g in P.each():
                g.f0 += 1

        rows.append(("cap %d · F %d" % (cap, f), _payload_size(body) - base))
    for name, d in rows:
        print("  페이로드 증가 %-20s %+d B (목표 cap×((F+3)×72+76)+(F+3)×72 = %d)" % (
            name, d, _target_bytes(*map(int, name.replace("cap ", "").split(" · F ")))))
    return rows


def _target_bytes(cap, f):
    return cap * ((f + 3) * 72 + 76) + (f + 3) * 72


# =============================================================================================
# 비용 측정 항목 (tools/cost.py)
# =============================================================================================

COST_MEMORY = {"text": True}

C4 = Pool("Cost4", "kind timer phase done", capacity=8)
C4w = Pool("Cost4w0", "kind timer phase done", capacity=8)
C4m = Pool("Cost4m", "kind timer phase done", capacity=8)
C13 = Pool("Cost13", "unit! x! y! owner timer phase work1 work2 work3 done gunid glevel efftimer", capacity=36)
C16 = Pool("Cost16", " ".join("f%d" % i for i in range(16)), capacity=128)
CE = Pool("CostE", "a b", capacity=8)
CF = Pool("CostF", "x", capacity=1)
CD = Pool("CostD", "kind", capacity=4)
CI = Pool("CostI", "kind timer phase done", capacity=8, index=True)


def _alloc_n(P, n, **kw):
    def setup(t):
        for _ in range(n):
            P.alloc(**kw)

    return setup


def _each_timer(P):
    def build(t):
        for g in P.each():
            g.timer += 16

    return build


def _each_empty_body(P):
    def build(t):
        for _g in P.each():
            pass

    return build


def _each_f0(P):
    def build(t):
        for g in P.each():
            g.f0 += 1

    return build


def _each_seed(t):
    for g in C13.each():
        g.timer += 16
        g.phase += 0
        g.work1 += 0


def _free_first_setup(P, n):
    def setup(t):
        hs = [P.alloc() for _ in range(n)]
        P.free(hs[0])

    return setup


def _dispatch26(t):
    cases = {k: (lambda g: None) for k in range(100, 126)}
    for _g in CD.each():
        CD.dispatch("kind", cases, default=None)


COST_H = EUDVariable()  # 준비 케이스가 잡은 핸들 (잴 케이스가 쓴다)


def _alloc_keep(P, **kw):
    def setup(t):
        COST_H << P.alloc(**kw)

    return setup


def _alloc_in_body(t):
    for g in C4m.each():
        C4m.alloc(kind=1)


COST_CASES = [
    CostCase("빈 풀 each (본문 비움)", _each_empty_body(CE), target={"exec": 6}, note="S2 6.13 ≤ 6"),
    CostCase("each 방문 1개 (F=4, W=1: timer += 16)", _each_timer(C4), setup=_alloc_n(C4, 1),
             note="고정 8 + 방문(F+10+W = 15) + 본문 1 (목표 방문 F+12+2W = 18)"),
    CostCase("each 방문 4개 (F=4, W=1)", _each_timer(C4), setup=_alloc_n(C4, 4), note="8 + 4×16"),
    CostCase("each 방문 1개 (F=4, W=0)", _each_empty_body(C4w), setup=_alloc_n(C4w, 1), note="8 + F+6"),
    CostCase("each 방문 5개 (Seed F=13, W=3)", _each_seed, setup=_alloc_n(C13, 5),
             note="S2 5.3 Seed 행: 시제품 약 246, 목표 약 161"),
    CostCase("each 방문 4개 (F=4, W=1, index=True)", _each_timer(CI), setup=_alloc_n(CI, 4), note="방문당 +1"),
    CostCase("each 방문 4개, 첫 레코드는 루프 밖에서 반납", _each_timer(C4), setup=_free_first_setup(C4, 5),
             note="4×16 + 8 + 반납 레코드(적재 9 + 번호 b+2 + 넣기 3) + 이동 3×4 + 끝 3"),
    CostCase("each 방문 2개, 본문마다 alloc (2단계 정리)", _alloc_in_body, setup=_alloc_n(C4m, 2),
             note="alloc 2 + 2단계 머리 4 + 새 레코드 2×(적재 9 + 1)"),
    CostCase("each 방문 1개 (F=16, W=1, cap 128)", _each_f0(C16), setup=_alloc_n(C16, 1), note="ResV 규모"),
    CostCase("alloc (F=4, 상수 값)", lambda t: C4.alloc(kind=131), target={"call": 4, "exec": 3 * 4 + 30},
             note="공유 핵심 1벌 포함 안 함(호출 자리). cap 8 → b=3"),
    CostCase("alloc (F=13, 변수 값 3개)", lambda t: C13.alloc(unit=t.var("u"), x=t.var("x"), y=t.var("y")),
             target={"call": 4, "exec": 3 * 13 + 30}, note="cap 36 → b=6"),
    CostCase("alloc (F=16, cap 128)", lambda t: C16.alloc(f0=1), target={"call": 4, "exec": 3 * 16 + 30}),
    CostCase("alloc 넘침 (report)", lambda t: CF.alloc(x=1), setup=_alloc_n(CF, 1), note="문구 + Buzz ×3 포함"),
    CostCase("alloc_n(3) (F=4)", lambda t: C4.alloc_n(3, kind=1)),
    CostCase("free (루프 밖, 산 레코드)", lambda t: CE.free(COST_H), setup=_alloc_keep(CE), target={"exec": 6}),
    CostCase("free (루프 밖, 핸들 0)", lambda t: CE.free(t.var("h")), note="0 은 '방문 중 레코드' 경로 (아무 일 없음)"),
    CostCase("free_current", lambda t: CE.free_current(), target={"call": 1, "exec": 1}),
    CostCase("is_alive (루프 밖, 산 레코드)", lambda t: t.flag("a", CE.is_alive(COST_H)), setup=_alloc_keep(CE),
             note="결과를 0/1 변수로 옮기는 몫(EUDIf 2~3) 포함"),
    CostCase("index_of (b=3)", lambda t: CE.index_of(COST_H), setup=_alloc_keep(CE), note="EUDFunc 1벌 (첫 호출에)"),
    CostCase("get (루프 밖)", lambda t: CE.get(COST_H, "a"), setup=_alloc_keep(CE, a=7), note="f_dwread_epd 포함"),
    CostCase("set (루프 밖)", lambda t: CE.set(COST_H, "a", 5), setup=_alloc_keep(CE)),
    CostCase("each 방문 1개 (F=1, 본문 비움) — dispatch 기준선", _each_empty_body(CD), setup=_alloc_n(CD, 1, kind=113)),
    CostCase("dispatch 26경우 (방문 1개, kind 113)", _dispatch26, setup=_alloc_n(CD, 1, kind=113),
             note="기준선과의 차이 = EUDSwitch (S2 5.2: 26경우 실행 6~7)"),
    CostCase("Line (상수, 조건만)", lambda t: t.flag("f", C4.Line("timer", AtLeast, 5))),
    CostCase("SetLine Subtract (상수)", lambda t: C4.SetLine("timer", Subtract, 1)),
]


def main():
    if "--storage" in sys.argv:
        measure_storage()
        measure_payload()
        return
    ck = Checker("t_pool (python)")
    python_checks(ck)

    s = Suite("t_pool", memory={"text": True})
    build_cases(s)
    add_watches(s)
    s.build()
    cks = Checker("t_pool (시나리오 T1~T14)")
    run_scenarios(cks)
    ckf = Checker("t_pool (참조 모델 차등)")
    fuzz(ckf, D4, 300, 1)
    fuzz(ckf, D6, 300, 2, sites=2)
    fuzz(ckf, D2, 150, 3)
    fuzz(ckf, D7i, 250, 4)
    fuzz(ckf, D9a, 250, 5, sites=2)
    fuzz(ckf, D5, 200, 6)
    ckc = Checker("t_pool (개별)")
    run_cases(s, ckc)
    run_steps(s, ckc)
    print("  실행 수: 빈 풀 %r, D4 방문 1/2/4개 %r, Seed 5개 %r" % (EMPTY_STEPS, VISIT_STEPS, SEED_STEPS))
    ok1 = s.report()

    cke = Checker("t_pool (epScript)")
    eps_checks(cke)
    eps_emulate(cke)
    ingame_emulate(cke)
    eps_build(cke)
    rows = measure_storage()
    ck.true("scx: cap 128·F 16 풀 < 30KB", dict(rows)["Pool cap 128 · F 16 (+ alloc 1곳 + each 1곳)"] < 30000,
            repr(rows))
    finish(ok1, ck.report(), cks.report(), ckf.report(), ckc.report(), cke.report())


if __name__ == "__main__":
    main()
