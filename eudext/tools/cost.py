"""비용 보고 (DESIGN 5.2): 본문 트리거 수, 호출 자리 트리거 수, 에뮬레이터 실행 트리거 수, 페이로드 증가분.

시험 파일이 `COST_CASES`(CostCase 목록)를 두면 이 도구가 재서 표로 낸다.

    python tools/cost.py tests/t_parts.py                 # 표 출력
    python tools/cost.py tests/t_parts.py --append --title "_parts (WP0)"   # docs/COSTS.md 에 덧붙이기
    python tools/cost.py tests/t_parts.py --bytes         # 페이로드 증가분까지 (케이스마다 따로 빌드)

측정 방법
- 본문: CostCase.funcs 의 EUDFunc 마다 `f.size()` (한 벌 본문 트리거 수).
- 호출 자리: 본문을 먼저 만든 뒤 `GetTriggerCounter()` 차이 (케이스 build 함수가 낸 RawTrigger 수).
- 실행: harness 로 한 사이클 돌린 실행 트리거 수 (빈 사이클·케이스 호출 오버헤드를 뺀 값). 입력이 여러 벌이면 최소~최대.
- 페이로드: 케이스를 40벌 넣은 빌드와 빈 빌드의 페이로드(적층 뒤, 재배치 전, 셔플 끔) 차이 ÷ 40 (참고값).

시험 파일에 둘 수 있는 것 (WP11 추가, 없어도 예전과 같다):
- `COST_MEMORY` (모듈 전역 dict): harness `Suite(memory=…)` 로 넘기는 SC 모델 설치 인자
  (예: `{"units": {}}` — 유닛 모델, `{"text": True}` — 글 기록). `--memory-attr` 로 이름을 바꾼다.
- `CostCase(…, setup=fn(ctx), setup_inputs={…}, setup_cycles=1)`: 잴 코드 앞에 상태를 만드는 준비 코드.
  준비는 따로 떨어진 케이스로 빌드되고, 측정 때 메모리를 초기 상태로 되돌린 뒤 준비 케이스를 먼저 돌리고(세지 않음)
  이어서 잴 케이스를 돈다. 준비 코드와 잴 코드는 파이썬 객체(예: 같은 pool)를 함께 쓸 수 있다.
  준비 코드는 호출 자리·페이로드 측정에 들어가지 않는다.
"""

import argparse
import datetime
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)
COSTS_MD = os.path.join(PKG, "docs", "COSTS.md")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

__all__ = ["COSTS_MD", "CostCase", "CostRow", "append_costs", "func_size", "measure", "render"]


class CostCase:
    """비용 측정 항목.

    인자: name, build(fn(ctx) — 잴 코드만 낸다. 입력 칸은 ctx.var(이름)), inputs(dict 또는 dict 목록),
          funcs(본문을 잴 EUDFunc 목록), target(dict: body/call/exec 상한, 3.8 목표), note(비고),
          cycles(잴 사이클 수 — 실행 값은 그중 최대), setup(선택: fn(ctx) 준비 코드, 모듈 docstring),
          setup_inputs(준비 케이스 입력 dict), setup_cycles(준비 사이클 수)
    """

    def __init__(self, name, build, inputs=None, funcs=(), target=None, note="", cycles=1, setup=None,
                 setup_inputs=None, setup_cycles=1):
        self.name = name
        self.build = build
        if inputs is None:
            inputs = [{}]
        elif isinstance(inputs, dict):
            inputs = [inputs]
        self.inputs = list(inputs)
        self.funcs = tuple(funcs)
        self.target = dict(target or {})
        self.note = note
        self.cycles = cycles
        self.setup = setup
        self.setup_inputs = dict(setup_inputs or {})
        self.setup_cycles = setup_cycles


class CostRow:
    def __init__(self, name, note=""):
        self.name = name
        self.body = None
        self.call = None
        self.exec_min = None
        self.exec_max = None
        self.payload = None
        self.target = {}
        self.note = note
        self.error = None

    def over(self):
        """3.8 목표를 넘은 항목 이름 목록."""
        out = []
        vals = {"body": self.body, "call": self.call, "exec": self.exec_max}
        for k, lim in self.target.items():
            v = vals.get(k)
            if v is not None and lim is not None and v > lim:
                out.append("%s %d > %d" % (k, v, lim))
        return out


def func_size(f):
    """EUDFunc 한 벌 본문의 트리거 수 (`EUDFuncN.size()`)."""
    from eudext import _compat

    if not _compat.is_eudfunc(f):
        raise TypeError("EUDFunc 가 아닙니다: %r" % (f,))
    return f.size()


class _PlainCtx:
    """페이로드 측정용: harness 없이 입력 칸만 만든다."""

    def __init__(self):
        self.vars = {}

    def var(self, name, init=0):
        from eudplib import EUDVariable

        if name not in self.vars:
            self.vars[name] = EUDVariable(init)
        return self.vars[name]

    def out(self, name, value):
        v = self.var(name)
        v << value
        return v

    def flag(self, name, cond):
        # harness.CaseCtx.flag 와 같게 조건을 소비한다 (버리면 빌드 때 "Orphan condition")
        from eudplib import EUDElse, EUDEndIf, EUDIf

        v = self.var(name)
        if EUDIf()(cond):
            v << 1
        if EUDElse()():
            v << 0
        EUDEndIf()
        return v

    def watch(self, name, addr):
        pass


def _payload_size(body, seed=None):
    import random

    from eudplib import CompressPayload, LoadMap, ShufflePayload

    from eudext.testing import emu
    from eudext.testing.harness import BASE_MAP

    LoadMap(BASE_MAP)
    CompressPayload(True)
    ShufflePayload(seed is not None)
    if seed is not None:
        random.seed(seed)
    try:
        prog = emu.Program(body)
        prog.build()
    finally:
        ShufflePayload(True)
    return prog.payload_size


BYTE_REPEAT = 40


def _setup_name(cc):
    return cc.name + " [준비]"


def measure(cases, title="cost", with_bytes=False, verbose=False, memory=None):
    """CostCase 목록을 재서 CostRow 목록을 돌려준다.

    memory: harness `Suite(memory=…)` 인자(SC 모델 설치 — 시험 파일의 `COST_MEMORY`). 없으면 기본 게임 메모리만.
    """
    from eudplib import GetTriggerCounter

    from eudext.testing.harness import Suite

    rows = {}
    suite = Suite("cost:" + title, verbose=verbose, memory=dict(memory or {}))
    for cc in cases:
        if cc.setup is not None:
            suite.case(_setup_name(cc))(lambda t, cc=cc: cc.setup(t))
    for cc in cases:
        row = CostRow(cc.name, cc.note)
        row.target = cc.target
        rows[cc.name] = row

        def body(t, cc=cc, row=row):
            if cc.funcs:
                row.body = sum(func_size(f) for f in cc.funcs)
            n0 = GetTriggerCounter()
            cc.build(t)
            row.call = GetTriggerCounter() - n0

        suite.case(cc.name)(body)
    suite.build()
    for cc in cases:
        row = rows[cc.name]
        if suite.cases[cc.name].build_error:
            row.error = suite.cases[cc.name].build_error
            continue
        steps = []
        for inp in cc.inputs:
            fresh = True
            if cc.setup is not None:
                sname = _setup_name(cc)
                if suite.cases[sname].build_error:
                    row.error = "setup: " + suite.cases[sname].build_error
                    break
                r = suite.run(sname, cc.setup_inputs, cycles=cc.setup_cycles, fresh=True)
                if r.error:
                    row.error = "setup: " + r.error
                    break
                fresh = False
            r = suite.run(cc.name, inp, cycles=cc.cycles, fresh=fresh)
            if r.error:
                row.error = r.error
                break
            steps.append(max(r.steps))
        if steps:
            row.exec_min, row.exec_max = min(steps), max(steps)
    if with_bytes:
        # 적층 배치는 전체 배치에 따라 달라져 한 번 넣고 잰 차이는 ±1KB 흔들린다 → BYTE_REPEAT 벌을 넣고 나눈다
        empty = _payload_size(lambda: None)
        for cc in cases:
            row = rows[cc.name]
            if row.error:
                continue
            for f in cc.funcs:
                f.size()

            def many(cc=cc):
                for _ in range(BYTE_REPEAT):
                    cc.build(_PlainCtx())

            try:
                row.payload = round((_payload_size(many) - empty) / BYTE_REPEAT)
            except Exception as e:  # noqa: BLE001
                row.error = "payload: %s" % e
    return [rows[cc.name] for cc in cases]


def _fmt(v):
    return "-" if v is None else str(v)


def render(rows, title, date=None):
    """마크다운 표 문자열."""
    date = date or datetime.date.today().isoformat()
    lines = [
        "## %s (%s)" % (title, date),
        "",
        "| 항목 | 본문 | 호출 자리 | 실행 | 페이로드 B | 목표 | 비고 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        ex = "-" if r.exec_min is None else (str(r.exec_min) if r.exec_min == r.exec_max else "%d~%d" % (r.exec_min, r.exec_max))
        tgt = ", ".join("%s≤%s" % kv for kv in r.target.items()) or "-"
        over = r.over()
        if over:
            tgt += " **초과: %s**" % "; ".join(over)
        note = r.note
        if r.error:
            note = (note + " " if note else "") + "**오류: %s**" % r.error
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (r.name, _fmt(r.body), _fmt(r.call), ex, _fmt(r.payload), tgt, note or ""))
    lines.append("")
    return "\n".join(lines)


_HEADER = """# eudext 비용 측정 기록

`tools/cost.py` 가 덧붙인다(DESIGN 3.8, 5.2). 단위는 트리거 수(본문·호출 자리·실행)와 바이트(페이로드).

- 본문: EUDFunc 한 벌의 트리거 수(`f.size()`). 인라인 부품이면 `-`.
- 호출 자리: 그 코드가 호출한 자리에 낸 RawTrigger 수(`GetTriggerCounter()` 차이, 본문 제외).
- 실행: 에뮬레이터 한 사이클에서 그 코드가 실행한 트리거 수(변수 트리거 포함). 입력에 따라 다르면 최소~최대.
- 페이로드: 그 코드를 40벌 넣은 빌드와 빈 빌드의 페이로드 차이 ÷ 40 (적층 뒤, 셔플 끔, 변수 트리거 72B 포함).
  적층 배치가 전체에 따라 달라져 한 벌만 넣고 재면 ±1KB 흔들리므로 나눠서 적는다. **참고값**이다.

"""


def append_costs(rows, title, path=COSTS_MD, date=None):
    """COSTS.md 에 표를 덧붙인다(없으면 머리말과 함께 만든다)."""
    text = render(rows, title, date)
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write(_HEADER)
        f.write(text + "\n")
    return path


def _load_spec(path, attr, memory_attr=None):
    path = os.path.abspath(path)
    d = os.path.dirname(path)
    if d not in sys.path:
        sys.path.insert(0, d)
    name = "_cost_spec_" + os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if memory_attr is None:
        return getattr(mod, attr)
    return getattr(mod, attr), getattr(mod, memory_attr, None)


def main(argv=None):
    ap = argparse.ArgumentParser(description="eudext 비용 보고")
    ap.add_argument("spec", help="COST_CASES 를 가진 파이썬 파일")
    ap.add_argument("--attr", default="COST_CASES")
    ap.add_argument("--memory-attr", default="COST_MEMORY", help="SC 모델 설치 인자 dict 이름 (없으면 기본)")
    ap.add_argument("--title", default=None)
    ap.add_argument("--append", action="store_true", help="docs/COSTS.md 에 덧붙이기")
    ap.add_argument("--bytes", action="store_true", help="페이로드 증가분도 잰다")
    ap.add_argument("--out", default=COSTS_MD)
    args = ap.parse_args(argv)

    sys.dont_write_bytecode = True
    work = os.environ.get("EUDEXT_WORK") or os.path.join(tempfile.gettempdir(), "eudext_work")
    os.makedirs(os.path.join(work, "tmp"), exist_ok=True)
    tempfile.tempdir = os.path.join(work, "tmp")
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    cases, memory = _load_spec(args.spec, args.attr, args.memory_attr)
    title = args.title or os.path.splitext(os.path.basename(args.spec))[0]
    rows = measure(cases, title, with_bytes=args.bytes, memory=memory)
    text = render(rows, title)
    print(text)
    if args.append:
        print("덧붙임:", append_costs(rows, title, args.out))
    return 0 if not any(r.error for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
