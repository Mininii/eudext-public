"""차등 시험 틀: 여러 케이스를 한 빌드에 모아 에뮬레이터로 돌린다 (DESIGN 5.1).

- 한 번 빌드(LoadMap + SaveMap 가로채기)로 모든 케이스를 싣는다. 사이클마다 `mode` 변수로 케이스 하나만 돈다.
- 케이스 본문은 따로 떨어진 서브루틴(`_parts.SubLabel`)에 만든다. 본문을 만들다 예외가 나면 그 케이스만
  "빌드 실패" 로 기록하고 나머지는 계속한다. 실행 중 에뮬레이터 오류가 나면 기록하고 메모리를 초기 상태로 되돌린다.
- 파이썬 참조 구현과 무작위 + 경계값 차등 시험(`Suite.diff`), 케이스별 실행 트리거 수 기록(`Suite.steps`).

예:
    from eudext.testing.harness import Suite, EDGES32
    suite = Suite("parts")

    @suite.case("and")
    def _(t):
        a = t.var("a")
        t.out("r", a & 0xF0)

    suite.build()
    suite.diff("and", lambda a: {"r": a & 0xF0}, {"a": EDGES32}, n=100)
    suite.check("and", {"a": 0xFF}, {"r": 0xF0})
    ok = suite.report()

주의 (WP0 실측 (d)): 한 프로세스에서 Suite 를 여러 개 빌드해도 되지만, 문자열을 굽는 EUDFunc 본문
(DisplayText 등)은 첫 빌드의 문자열 번호를 그대로 쓴다. 문자열 결과를 보는 시험은 한 빌드에 모은다.

## 빌드 때 오류가 나야 하는 케이스 (WP2 추가)

컴파일 시점 입력 검사(`EudextError` 등)를 시험할 때 케이스에 기대하는 예외를 적는다.

    @suite.case("bad_index", expect_build_error=EudextError, expect_message="범위")
    def _(t):
        arr = cell.CellArray(3)
        arr[5] << 1                       # 여기서 EudextError 가 나야 한다

- 본문을 만들다 그 예외(클래스 또는 클래스 튜플, `isinstance` 로 본다)가 나면 **통과 1**, 예외가 안 나거나 다른 예외가
  나거나 `expect_message`(정규식, `re.search`)가 메시지와 맞지 않으면 **실패 1** 로 센다(판정 이름 "빌드 오류 기대").
- 판정은 `build()` 때 기록된다. 이런 케이스는 실행하지 않는다(`run`/`check`/`diff` 는 실패로 기록).
  잡은 예외는 `suite.cases[이름].caught` 에 남는다.
- 본문은 따로 떨어진 트리거 범위(`_compat.isolated_scope`)에서 만들어지므로, 예외 전에 만든 트리거·블록은 바깥 흐름에
  이어지지 않는다. 다만 조건을 만든 뒤 그 조건을 참조하는 트리거를 남기고 예외가 나면 빌드 때 `Orphan condition` 이
  날 수 있다(케이스 밖 오류 — 빌드 전체가 실패한다). SaveMap 단계에서 나는 오류는 이 표시로 시험할 수 없다.
- `expect_build_error` 가 없는 케이스는 예전과 같다(예외 = "빌드 실패" 로 기록, 실패 1).

## 이 PC 번호·게임 메모리만 바꿔 다시 시작하기 (WP2 추가)

빌드한 프로그램은 그대로 두고, 메모리를 **빌드 직후(게임 시작 전)** 로 되돌린 뒤 새 초기 메모리를 쓰고
"게임 시작 1회" 코드(eudplib 초기화 사이클 — `EUDOnStart`, `f_getuserplayerid` 초기화, 비보존 트리거 …)부터 다시 돈다.
이 PC 번호(0x512684)처럼 초기화 때 읽히는 값을 바꿔 보려고 번호마다 새로 빌드할 필요가 없다.

    s = Suite("players", memory={"local_player": 0, "players": ["human", "human"]})
    …케이스 등록…
    s.build()
    for local in (0, 1, 128, 131):
        s.restart(local_player=local)          # memory 의 local_player 만 바꾼다 (나머지 키는 그대로)
        s.check("userp", {}, {"p": local})
    s.restart(memory={"local_player": 2, "players": ["human"] * 3})   # memory 를 통째로 바꾼다
    s.restart(init_mem={0x58D634: 1}, prep=lambda m: set_allies(m))   # 원시 메모리·준비 함수

- `restart(memory=None, *, init_mem=None, prep=None, **바꿀 키)`: `memory` 를 주면 통째로 바꾸고, 키워드(`local_player`,
  `players`, `cp`, `races`, `forces`, `units`)는 그 위에 덮어쓴다. 바뀐 값은 `suite.memory` 에 남아 뒤의 `reset()`·
  `run(fresh=True)` 도 새 시작 상태로 되돌아간다. `init_mem`(`{주소: 값 또는 bytes}`)·`prep`(fn(machine))을 주면
  바꾸고, 안 주면 앞의 것(`Suite(init_mem=…, prep=…)` 포함)을 그대로 쓴다. 지우려면 `init_mem={}`, `prep=False`.
- 순서: 빌드 직후 스냅숏 복원 → `scmodel.install(machine, **memory)` → `init_mem` → `prep(machine)` → 초기화 사이클 2번
  (빈 사이클 기준값·케이스 호출 오버헤드를 다시 잰다) → 그 상태를 `reset()` 기준으로 기억.
- 파이썬 쪽 상태는 되돌리지 않는다: 시험이 끼운 처리기(`machine.act_handlers` 등)는 그대로 남고, 유닛 모델은
  `memory["units"]` 가 있으면 새로 만든다(기록·실패 주입 설정도 새것). `machine.log`·`ends` 는 계속 쌓인다.
- 반환: machine (같은 객체).
"""

import os
import random
import re
import traceback

from eudplib import CompressPayload, EUDElse, EUDEndIf, EUDIf, EUDVariable, LoadMap

from eudext import _parts
from eudext.testing import emu, scmodel

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_MAP = os.path.join(HERE, "base.scx")
M32 = 0xFFFFFFFF

# 32비트 경계값
EDGES32 = (0, 1, 2, 0x7FFFFFFE, 0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFFFFFE, 0xFFFFFFFF)

__all__ = ["BASE_MAP", "EDGES32", "Case", "CaseCtx", "RunResult", "Suite", "rand32"]


def rand32(rng):
    """경계 근처에 치우친 32비트 난수."""
    r = rng.random()
    if r < 0.15:
        return rng.randrange(0, 256)
    if r < 0.3:
        return (M32 - rng.randrange(0, 256)) & M32
    if r < 0.4:
        return (0x80000000 + rng.randrange(-256, 256)) & M32
    return rng.getrandbits(32)


class CaseCtx:
    """케이스 본문을 만들 때 받는 도구.

    - `var(name, init=0)`: 입력·출력 칸(EUDVariable). 사이클 전에 값을 넣고 뒤에 읽는다.
    - `out(name, value)`: 새 칸에 value 를 대입(`<<`).
    - `flag(name, cond)`: 조건 결과를 0/1 로 기록.
    - `watch(name, addr)`: 임의 주소 읽기 등록.
    """

    def __init__(self, suite, case):
        self._suite = suite
        self._case = case

    def _key(self, name):
        return "%s.%s" % (self._case.name, name)

    def var(self, name, init=0):
        key = self._key(name)
        v = self._case.vars.get(name)
        if v is None:
            v = EUDVariable(init)
            self._case.vars[name] = v
            self._suite._prog.watch(key, v.getValueAddr())
        return v

    def out(self, name, value):
        v = self.var(name)
        v << value
        return v

    def flag(self, name, cond):
        v = self.var(name)
        if EUDIf()(cond):
            v << 1
        if EUDElse()():
            v << 0
        EUDEndIf()
        return v

    def watch(self, name, addr):
        self._case.watches.append(name)
        self._suite._prog.watch(self._key(name), addr)


class Case:
    def __init__(self, name, fn, cid, expect_error=None, expect_message=None):
        self.name = name
        self.fn = fn
        self.id = cid
        self.vars = {}
        self.watches = []
        self.sub = _parts.SubLabel(name)
        self.build_error = None
        self.results = []  # (label, ok, message)
        self.steps = []
        # 빌드 때 이 예외가 나야 하는 케이스 (None = 보통 케이스)
        self.expect_error = expect_error
        self.expect_message = expect_message
        self.caught = None  # 잡은 예외 (expect_error 케이스)


class RunResult:
    def __init__(self, values, steps, log, error=None):
        self.values = values  # 마지막 사이클 뒤 {이름: 값}
        self.steps = steps  # 사이클별 실행 트리거 수 (빈 사이클 기준값을 뺀 값)
        self.log = log  # 흉내 못 낸/기록된 액션
        self.error = error

    def __getitem__(self, k):
        return self.values[k]

    def __repr__(self):
        return "RunResult(%r, steps=%r, error=%r)" % (self.values, self.steps, self.error)


class Suite:
    """시험 묶음 하나 = 빌드 하나.

    인자: name(표시용), base_map(기본: testing/base.scx), memory(scmodel.install 인자 dict — game_memory 인자와 units),
          verbose, init_mem({주소: 값 또는 bytes} — memory 뒤에 쓰는 원시 초기 메모리, 선택),
          prep(fn(machine) — 초기화 사이클 직전에 부르는 준비 함수, 선택)
    """

    def __init__(self, name, base_map=None, memory=None, verbose=True, init_mem=None, prep=None):
        self.name = name
        self.base_map = base_map or BASE_MAP
        self.memory = memory or {}
        self.verbose = verbose
        self.init_mem = dict(init_mem or {})
        self.prep = prep
        self.cases = {}
        self._order = []
        self.machine = None
        self.baseline = 0
        self._snap = None
        self._pristine = None
        self._mode = None
        self._prog = None
        self.overhead = 0
        self.build_time_errors = []
        self.restarts = 0

    # --- 등록 ---
    def case(self, name=None, expect_build_error=None, expect_message=None):
        """케이스 등록 데코레이터. expect_build_error(예외 클래스 또는 튜플)를 주면 "본문을 만들 때 그 예외가 나야 하는"
        케이스가 된다(모듈 docstring). expect_message 는 메시지에 대한 정규식(선택)."""
        if expect_build_error is not None:
            kinds = expect_build_error if isinstance(expect_build_error, tuple) else (expect_build_error,)
            if not kinds or not all(isinstance(k, type) and issubclass(k, BaseException) for k in kinds):
                raise TypeError("expect_build_error 는 예외 클래스(또는 그 튜플)여야 합니다: %r" % (expect_build_error,))
            expect_build_error = kinds
        elif expect_message is not None:
            raise TypeError("expect_message 는 expect_build_error 와 함께 씁니다")

        def deco(fn):
            cname = name or fn.__name__
            if cname in self.cases:
                raise ValueError("케이스 이름 중복: %s" % cname)
            c = Case(cname, fn, len(self._order) + 1, expect_build_error, expect_message)
            self.cases[cname] = c
            self._order.append(c)
            return fn

        return deco

    # --- 빌드 ---
    def _judge_expected(self, c, e):
        """빌드 오류 기대 케이스의 판정을 기록한다. e = 잡은 예외(없으면 None)."""
        label = "빌드 오류 기대"
        want = "/".join(k.__name__ for k in c.expect_error)
        if e is None:
            return self._record(c, label, False, "오류가 나지 않았습니다 (기대 %s)" % want)
        c.caught = e
        got = "%s: %s" % (type(e).__name__, e)
        if not isinstance(e, c.expect_error):
            self.build_time_errors.append((c.name, traceback.format_exc()))
            return self._record(c, label, False, "다른 오류 %s (기대 %s)" % (got, want))
        if c.expect_message is not None and not re.search(c.expect_message, str(e)):
            return self._record(c, label, False, "메시지 %r 가 %r 와 맞지 않습니다" % (str(e), c.expect_message))
        return self._record(c, label, True)

    def _body(self):
        # 케이스 본문은 처음 한 번만 만든다(따로 떨어진 영역). 실패한 케이스·빌드 오류 기대 케이스는 부르지 않는다.
        for c in self._order:
            if c.build_error is not None or c.sub is None or c.sub.defined:
                continue
            try:
                with c.sub.define():
                    c.fn(CaseCtx(self, c))
            except Exception as e:  # noqa: BLE001 — 케이스 격리
                c.sub = None
                if c.expect_error is not None:
                    self._judge_expected(c, e)
                    continue
                c.build_error = "%s: %s" % (type(e).__name__, e)
                self.build_time_errors.append((c.name, traceback.format_exc()))
            else:
                if c.expect_error is not None:
                    self._judge_expected(c, None)
        for c in self._order:
            if c.build_error is None and c.expect_error is None:
                _parts.call_sub(c.sub, conds=self._mode.Exactly(c.id))

    def build(self):
        if "__empty__" not in self.cases:
            self.case("__empty__")(lambda t: None)  # 케이스 호출 오버헤드 측정용
        LoadMap(self.base_map)
        CompressPayload(True)
        self._mode = EUDVariable()
        self._prog = emu.Program(self._body)
        self._prog.watch("__mode__", self._mode.getValueAddr())
        m = self._prog.build()
        self.machine = m
        self._pristine = m.snapshot()  # 게임 시작 전(초기화 사이클 전) 상태 — restart() 가 여기로 되돌린다
        self._start()
        if self.verbose:
            nfail = sum(1 for c in self._order if c.build_error)
            print(
                "[%s] 빌드: 케이스 %d (빌드 실패 %d), 페이로드 %d B, 빈 사이클 %d + 케이스 호출 %d 트리거"
                % (self.name, len(self._order) - 1, nfail, self._prog.payload_size, self.baseline - self.overhead, self.overhead)
            )
            for cname, tb in self.build_time_errors:
                print("  [빌드 실패] %s\n%s" % (cname, tb))
        return m

    def _start(self):
        """빌드 직후 상태에서 초기 메모리를 쓰고 초기화 사이클을 돈 뒤, 기준값을 재고 그 상태를 기억한다."""
        m = self.machine
        m.restore(self._pristine)
        scmodel.install(m, **self.memory)
        if self.init_mem:
            m.init_mem(self.init_mem)
        if self.prep:
            self.prep(m)
        # 첫 사이클(eudplib 초기화)을 빈 모드로 돌리고 상태를 기억한다
        m.set_var("__mode__", 0)
        m.cycle()
        m.cycle()
        baseline = m.last_steps()
        # 빈 케이스로 호출 오버헤드(분기 + 호출 + 복귀)를 재서 실행 수에서 뺀다
        m.set_var("__mode__", self.cases["__empty__"].id)
        m.cycle()
        self.overhead = m.last_steps() - baseline
        m.set_var("__mode__", 0)
        self.baseline = baseline + self.overhead
        self._snap = m.snapshot()

    # --- 실행 ---
    def _case(self, name):
        c = self.cases[name]
        if self.machine is None:
            raise RuntimeError("build() 를 먼저 부르세요")
        return c

    def reset(self):
        """메모리를 빌드 직후(초기화 사이클 뒤) 상태로 되돌린다. restart() 뒤에는 그 새 시작 상태로."""
        self.machine.restore(self._snap)

    def restart(self, memory=None, *, init_mem=None, prep=None, **changes):
        """빌드한 프로그램을 그대로 두고 게임 메모리만 바꿔 "게임 시작" 부터 다시 초기화한다 (모듈 docstring).

        인자: memory(scmodel.install 인자 dict — 주면 통째로 바꿈), init_mem({주소: 값} — 주면 바꿈, `{}` = 지움),
              prep(fn(machine) — 주면 바꿈, False = 지움), changes(memory 에 덮어쓸 키: local_player 등)
        반환: machine
        """
        if self.machine is None or self._pristine is None:
            raise RuntimeError("build() 를 먼저 부르세요")
        new = dict(self.memory if memory is None else memory)
        new.update(changes)
        if init_mem is not None:
            self.init_mem = dict(init_mem)
        if prep is not None:
            self.prep = prep or None
        self.memory = new
        self._start()
        self.restarts += 1
        return self.machine

    def run(self, name, inputs=None, cycles=1, fresh=False):
        """케이스 하나를 cycles 사이클 돌린다.

        inputs: {이름: 값} 을 첫 사이클 전에 넣는다. fresh=True 면 먼저 메모리를 초기 상태로 되돌린다.
        반환: RunResult (values = 케이스의 모든 var/watch 값)
        """
        c = self._case(name)
        m = self.machine
        if c.build_error:
            return RunResult({}, [], [], error="빌드 실패: " + c.build_error)
        if c.expect_error is not None:
            return RunResult({}, [], [], error="빌드 오류 기대 케이스는 실행하지 않습니다")
        if fresh:
            self.reset()
        m.set_var("__mode__", c.id)
        for k, v in (inputs or {}).items():
            if k not in c.vars:
                raise KeyError("%s: 입력 칸 %r 이 없습니다 (t.var 로 만드세요)" % (name, k))
            m.set_var("%s.%s" % (name, k), v & M32)
        steps = []
        loglen = len(m.log)
        err = None
        try:
            for _ in range(cycles):
                m.cycle()
                steps.append(m.last_steps() - self.baseline)
        except Exception as e:  # noqa: BLE001
            err = "%s: %s" % (type(e).__name__, e)
        values = {k: m.var("%s.%s" % (name, k)) for k in list(c.vars) + c.watches}
        log = m.log[loglen:]
        m.set_var("__mode__", 0)
        if err is not None:
            self.reset()
        c.steps.extend(steps)
        return RunResult(values, steps, log, err)

    def trace(self, name, inputs_per_cycle):
        """사이클마다 다른 입력을 넣고 사이클별 값 목록을 돌려준다(여러 사이클 동작 시험)."""
        out = []
        for inp in inputs_per_cycle:
            out.append(self.run(name, inp, 1))
        return out

    # --- 판정 ---
    def _record(self, c, label, ok, msg=""):
        c.results.append((label, ok, msg))
        if not ok and self.verbose:
            print("  [실패] %s / %s: %s" % (c.name, label, msg))
        return ok

    def check(self, name, inputs, expect, label=None, cycles=1, fresh=False):
        """입력 → 기대값 비교. expect: {이름: 값}."""
        c = self._case(name)
        label = label or repr(inputs)
        r = self.run(name, inputs, cycles, fresh=fresh)
        if r.error:
            return self._record(c, label, False, r.error)
        bad = {k: (r.values.get(k), v & M32) for k, v in expect.items() if r.values.get(k) != (v & M32)}
        if bad:
            msg = ", ".join("%s=0x%X (기대 0x%X)" % (k, got if got is not None else -1, want) for k, (got, want) in bad.items())
            return self._record(c, label, False, msg)
        return self._record(c, label, True)

    def expect_true(self, name, cond, label, msg=""):
        """파이썬 쪽 판정 결과를 기록한다(여러 사이클 시험 등)."""
        return self._record(self.cases[name], label, bool(cond), msg)

    def diff(self, name, ref, inputs, n=100, seed=1, edges=True, max_edges=400):
        """파이썬 참조 구현과 차등 시험.

        ref(**입력) -> {출력 이름: 기대값}
        inputs: {입력 이름: 경계값 목록 또는 fn(rng)->값 또는 None(rand32)}
        edges=True 면 경계값 조합(최대 max_edges 개)을 먼저, 이어 무작위 n 개.
        반환: (통과 수, 실패 수)
        """
        c = self._case(name)
        if c.build_error:
            self._record(c, "diff", False, "빌드 실패: " + c.build_error)
            return 0, 1
        if c.expect_error is not None:
            self._record(c, "diff", False, "빌드 오류 기대 케이스는 실행하지 않습니다")
            return 0, 1
        rng = random.Random(seed)
        names = list(inputs)
        combos = []
        if edges:
            pools = [list(inputs[k]) if isinstance(inputs[k], (list, tuple)) else list(EDGES32) for k in names]
            total = 1
            for p in pools:
                total *= len(p)
            if total <= max_edges:
                idx = [0] * len(names)
                for _ in range(total):
                    combos.append({k: pools[j][idx[j]] for j, k in enumerate(names)})
                    for j in range(len(idx)):
                        idx[j] += 1
                        if idx[j] < len(pools[j]):
                            break
                        idx[j] = 0
            else:
                for _ in range(max_edges):
                    combos.append({k: rng.choice(pools[j]) for j, k in enumerate(names)})
        for _ in range(n):
            d = {}
            for k in names:
                g = inputs[k]
                if callable(g):
                    d[k] = g(rng) & M32
                else:
                    d[k] = rand32(rng)
            combos.append(d)
        ok = fail = 0
        for d in combos:
            if self.check(name, d, ref(**d), label="diff " + ", ".join("%s=0x%X" % kv for kv in d.items())):
                ok += 1
            else:
                fail += 1
        return ok, fail

    # --- 보고 ---
    def summary(self):
        rows = []
        for c in self._order:
            if c.name == "__empty__":
                continue
            passed = sum(1 for _l, ok, _m in c.results if ok)
            failed = sum(1 for _l, ok, _m in c.results if not ok)
            st = c.steps
            rows.append(
                {
                    "case": c.name,
                    "passed": passed,
                    "failed": failed + (1 if c.build_error else 0),
                    "build_error": c.build_error,
                    "expect_build_error": c.expect_error is not None,
                    "steps_min": min(st) if st else None,
                    "steps_max": max(st) if st else None,
                }
            )
        return rows

    def report(self):
        """표를 출력하고 모두 통과했으면 True."""
        rows = self.summary()
        total_ok = sum(r["passed"] for r in rows)
        total_fail = sum(r["failed"] for r in rows)
        print("[%s] 결과: 통과 %d, 실패 %d" % (self.name, total_ok, total_fail))
        for r in rows:
            st = "-" if r["steps_min"] is None else ("%d" % r["steps_min"] if r["steps_min"] == r["steps_max"] else "%d~%d" % (r["steps_min"], r["steps_max"]))
            mark = "OK " if r["failed"] == 0 else "FAIL"
            extra = (" (빌드 실패: %s)" % r["build_error"]) if r["build_error"] else ""
            if r.get("expect_build_error"):
                extra += " (빌드 오류 기대)"
            print("  %s %-28s 통과 %4d 실패 %3d 실행 %s%s" % (mark, r["case"], r["passed"], r["failed"], st, extra))
        if self.machine is not None and self.machine.unknown:
            top = ", ".join("%s%d×%d" % (k[0], k[1], v) for k, v in self.machine.unknown.most_common(8))
            print("  흉내 못 낸 조건·액션: %s" % top)
        return total_fail == 0
