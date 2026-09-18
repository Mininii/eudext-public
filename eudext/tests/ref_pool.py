"""`eudext.pool` 파이썬 참조 모델 (S2 6.12 의사코드 + 7.2 기대값, WP11).

S2 가 말한 스크래치패드 `refmodel.py` 는 없어져서 명세 6.4·6.5·6.12 규칙으로 새로 만들었다. 핸들 = 레코드 번호, None = 없음.

규칙 (구현과 같게):
- 빈 칸 스택: 처음 pop 순서 0, 1, 2 …. 반납된 칸은 **살아 있는 목록에서 빠지는 순간** 스택에 쌓인다(LIFO).
- `alloc`: 스택이 비면 None + dropped += 1. 아니면 번호를 꺼내 모든 필드를 쓰고 목록 끝에 붙인다(count += 1).
- `free(i)`: 방문 중인 레코드면 `free_current()` 와 같다. 아니면 살아 있을 때만 생존 표시를 지우고 count −= 1
  (이미 반납이면 무시하고 `warnings` += 1 — 구현의 debug 문구).
- `free_current()`: 방문 중 생존 표시가 켜져 있을 때만 끄고 count −= 1.
- `tick(body)`: 시작 때 목록 길이 n0 고정. 앞에서부터: 반납 표시면 스택에 넣고 건너뜀. 아니면 필드를 레지스터에 싣고
  body(pool, i, reg) → 방문 중 반납이면 되쓰기 없이 스택에, 아니면 되쓰기(reg 의 쓰기 가능 필드)하고 남김.
  body 가 `pool.break_()` 를 부르면 이번 방문을 마치고 남은 레코드는 본문 없이 정리만.
  뒤에 n0 이후(루프 중 alloc)를 본문 없이 정리(반납 표시면 스택에). 방문 순서를 돌려준다.
"""

__all__ = ["RefPool", "SCENARIOS", "run_scenario"]

M32 = 0xFFFFFFFF


class RefPool:
    def __init__(self, cap, fields, readonly=(), inits=None):
        self.cap = cap
        self.fields = list(fields)
        self.readonly = set(readonly)
        self.inits = dict(inits or {})
        self.stack = list(reversed(range(cap)))  # 끝이 맨 위
        self.live = []
        self.alive = [False] * cap
        self.data = [{f: 0 for f in self.fields} for _ in range(cap)]
        self.count = 0
        self.dropped = 0
        self.warnings = 0
        self.cur = None
        self.cur_alive = False
        self._break = False

    # --- 조작 ---
    def alloc(self, **vals):
        if not self.stack:
            self.dropped += 1
            return None
        i = self.stack.pop()
        self.alive[i] = True
        d = {f: self.inits.get(f, 0) for f in self.fields}
        for k, v in vals.items():
            d[k] = v & M32
        self.data[i] = d
        self.live.append(i)
        self.count += 1
        return i

    def alloc_n(self, k, **vals):
        if len(self.stack) < k:
            self.dropped += 1
            return [None] * k
        return [self.alloc(**vals) for _ in range(k)]

    def free(self, i):
        if i is None:
            return
        if self.cur is not None and i == self.cur:
            self.free_current()
            return
        if not self.alive[i]:
            self.warnings += 1
            return
        self.alive[i] = False
        self.count -= 1

    def free_current(self):
        if self.cur is not None and self.cur_alive:
            self.cur_alive = False
            self.count -= 1

    def break_(self):
        self._break = True

    def is_alive(self, i):
        if self.cur is not None and i == self.cur:
            return self.cur_alive
        return i is not None and self.alive[i]

    def top(self):
        return self.stack[-1] if self.stack else None

    def tick(self, body=None):
        n0 = len(self.live)
        kept = []
        visited = []
        self._break = False
        for r in range(n0):
            i = self.live[r]
            if not self.alive[i]:
                self.stack.append(i)
                continue
            if self._break or body is None:
                kept.append(i)
                continue
            visited.append(i)
            self.cur, self.cur_alive = i, True
            reg = dict(self.data[i])
            body(self, i, reg)
            alive = self.cur_alive
            self.cur = None
            if not alive:
                self.alive[i] = False
                self.stack.append(i)
                continue
            for f in self.fields:
                if f not in self.readonly:
                    self.data[i][f] = reg[f] & M32
            kept.append(i)
        for i in self.live[n0:]:
            if self.alive[i]:
                kept.append(i)
            else:
                self.stack.append(i)
        self.live = kept
        self._break = False
        return visited


# ---------------------------------------------------------------------------------------------
# S2 7.2 시나리오 T1~T14 (필드 kind timer phase done)
# ---------------------------------------------------------------------------------------------

F4 = ("kind", "timer", "phase", "done")


def _t1():
    p = RefPool(4, F4)
    hs = [p.alloc() for _ in range(3)]
    v = p.tick(lambda p, i, r: None)
    return {"handles": hs, "visit": v, "count": p.count, "top": p.top()}


def _t2():
    p = RefPool(4, F4)
    for _ in range(3):
        p.alloc()
    p.free(1)
    out = {"count_after_free": p.count, "live_after_free": list(p.live)}
    out["visit1"] = p.tick(lambda p, i, r: None)
    out["live1"] = list(p.live)
    out["top1"] = p.top()
    out["alloc"] = p.alloc()
    out["visit2"] = p.tick(lambda p, i, r: None)
    return out


def _t3():
    p = RefPool(4, F4)
    for _ in range(3):
        p.alloc()

    def body(p, i, r):
        if i == 1:
            p.free_current()

    out = {"visit1": p.tick(body), "live1": list(p.live), "count": p.count, "top1": p.top()}
    out["visit2"] = p.tick(lambda p, i, r: None)
    return out


def _t4():
    p = RefPool(4, F4)
    for _ in range(3):
        p.alloc()

    def body(p, i, r):
        if i == 0:
            p.free(2)

    return {"visit1": p.tick(body), "live1": list(p.live), "top1": p.top()}


def _t5():
    p = RefPool(4, F4)
    for _ in range(3):
        p.alloc()

    def body(p, i, r):
        if i == 2:
            p.free(0)

    out = {"visit1": p.tick(body), "live1": list(p.live), "count": p.count, "top1": p.top()}
    out["visit2"] = p.tick(lambda p, i, r: None)
    out["top2"] = p.top()
    return out


def _t6():
    p = RefPool(5, F4)
    for _ in range(3):
        p.alloc()
    got = []

    def body(p, i, r):
        if i == 0:
            got.append(p.alloc())

    out = {"visit1": p.tick(body)}
    out["alloc"] = got[0]
    out["live1"] = list(p.live)
    out["count"] = p.count
    out["visit2"] = p.tick(lambda p, i, r: None)
    return out


def _t7():
    p = RefPool(5, F4)
    for _ in range(3):
        p.alloc()
    got = []

    def body(p, i, r):
        if i == 0:
            got.append(p.alloc())
        if i == 1:
            p.free(got[0])

    out = {"visit1": p.tick(body), "alloc": got[0], "live1": list(p.live), "count": p.count, "top1": p.top()}
    return out


def _t8():
    p = RefPool(4, F4)
    hs = [p.alloc() for _ in range(5)]
    return {"handles": hs, "dropped": p.dropped, "count": p.count}


def _t9():
    p = RefPool(2, F4)
    p.alloc()
    p.alloc()
    p.free(0)
    out = {"alloc_before": p.alloc(), "dropped": p.dropped}
    p.tick(lambda p, i, r: None)
    out["alloc_after"] = p.alloc()
    out["live"] = list(p.live)
    return out


def _t10():
    p = RefPool(4, F4)
    p.alloc()

    def body(p, i, r):
        r["timer"] += 16

    for _ in range(3):
        p.tick(body)
    return {"timer": p.data[0]["timer"], "phase": p.data[0]["phase"]}


def _t11():
    p = RefPool(1, F4)
    p.alloc(kind=131, timer=5)

    def body(p, i, r):
        r["timer"] = 777
        r["phase"] = 3
        p.free_current()

    p.tick(body)
    h = p.alloc(kind=132)
    return {"handle": h, "fields": dict(p.data[h])}


def _t12():
    p = RefPool(4, F4)
    p.alloc()

    def body(p, i, r):
        r["timer"] = 555
        p.free_current()

    p.tick(body)
    return {"timer": p.data[0]["timer"], "count": p.count, "live": list(p.live)}


def _t13():
    p = RefPool(4, F4)
    h = p.alloc()
    p.free(h)
    p.free(h)
    return {"warnings": p.warnings, "count": p.count}


def _t14():
    p = RefPool(6, F4)
    for _ in range(6):
        p.alloc()
    p.free(1)
    p.free(3)
    out = {"visit1": p.tick(lambda p, i, r: None)}
    out["allocs"] = [p.alloc(), p.alloc()]
    out["visit2"] = p.tick(lambda p, i, r: None)
    return out


SCENARIOS = {
    "T1": (_t1, {"handles": [0, 1, 2], "visit": [0, 1, 2], "count": 3, "top": 3}),
    "T2": (_t2, {"count_after_free": 2, "live_after_free": [0, 1, 2], "visit1": [0, 2], "live1": [0, 2], "top1": 1,
                 "alloc": 1, "visit2": [0, 2, 1]}),
    "T3": (_t3, {"visit1": [0, 1, 2], "live1": [0, 2], "count": 2, "top1": 1, "visit2": [0, 2]}),
    "T4": (_t4, {"visit1": [0, 1], "live1": [0, 1], "top1": 2}),
    "T5": (_t5, {"visit1": [0, 1, 2], "live1": [0, 1, 2], "count": 2, "top1": 3, "visit2": [1, 2], "top2": 0}),
    "T6": (_t6, {"alloc": 3, "visit1": [0, 1, 2], "live1": [0, 1, 2, 3], "count": 4, "visit2": [0, 1, 2, 3]}),
    "T7": (_t7, {"alloc": 3, "visit1": [0, 1, 2], "live1": [0, 1, 2], "count": 3, "top1": 3}),
    "T8": (_t8, {"handles": [0, 1, 2, 3, None], "dropped": 1, "count": 4}),
    "T9": (_t9, {"alloc_before": None, "dropped": 1, "alloc_after": 0, "live": [1, 0]}),
    "T10": (_t10, {"timer": 48, "phase": 0}),
    "T11": (_t11, {"handle": 0, "fields": {"kind": 132, "timer": 0, "phase": 0, "done": 0}}),
    "T12": (_t12, {"timer": 0, "count": 0, "live": []}),
    "T13": (_t13, {"warnings": 1, "count": 0}),
    "T14": (_t14, {"visit1": [0, 2, 4, 5], "allocs": [3, 1], "visit2": [0, 2, 4, 5, 3, 1]}),
}


def run_scenario(name):
    fn, want = SCENARIOS[name]
    return fn(), want


if __name__ == "__main__":
    bad = 0
    for name in SCENARIOS:
        got, want = run_scenario(name)
        ok = got == want
        bad += not ok
        print(name, "OK" if ok else "FAIL %r != %r" % (got, want))
    print("참조 모델 시나리오: 실패 %d" % bad)
