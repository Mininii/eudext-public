"""S8 인게임 시험: SC:R 의 뺄셈·마스크 액션 의미를 게임 안에서 확인한다.

무엇을 보나
  - 마스크 Subtract (SetMemoryX(.., Subtract, v, m)) 가 어떤 식을 따르는가 (모형 A, A2, Av, C, B, Bw, D)
  - 마스크 Add (SetMemoryX(.., Add, v, m)) 가 어떤 식을 따르는가 (모형 M, Mu, Mn)
  - 마스크 없는 Subtract 가 부호 없는 포화인가, Add 에 넣은 음수가 wrap 인가
  - eudplib 경로 몇 개가 에뮬레이터 결과와 같은가 (v -= v, f_bsubtract_epd, EUDLightVariable >>=)

화면 출력 (1 초에 한 줄씩 돌아가며 찍는다)
  "S1 got 00001200 = A A2 Av"     ← 실제 값과, 그 값이 맞은 모형 이름
  "SUBX A=4/5 A2=5/5 ..."          ← 마스크 Subtract 시험 S1~S5 에서 모형별로 맞은 수 (5/5 인 모형이 답)
  "ADDX M=3/3 ..."                 ← 마스크 Add 시험 X1~X3 에서 모형별로 맞은 수 (3/3 인 모형이 답)
  에뮬레이터(모형 A2·M 가정)로 돌리면 SUBX A2=5/5, ADDX M=3/3, E1=FFFFFFFF, E2=11000022 가 나온다.
  맞은 모형이 없으면 "= ?" 로 나온다 → 값을 그대로 적어 보내 주면 된다.

모형 정의 (d = 원래 값, v = 액션 값, m = 마스크, 모두 32비트 부호 없음)
  마스크 Subtract
    A  : (d & ~m) | max(0, (d&m) - (v&m))              ← DPS G2 1.3 식 (결과를 마스크로 자르지 않음)
    A2 : (d & ~m) | (max(0, (d&m) - (v&m)) & m)        ← EUD 문서(gist)·DPS arith.py 식
    Av : (d & ~m) | (max(0, (d&m) - v) & m)            ← v 를 마스크하지 않음
    C  : (d & ~m) | (((d&m) - (v&m)) & m)              ← 마스크 안에서 wrap
    B  : (d & ~m) | (max(0, d - v) & m)                ← 32비트 전체 포화 뒤 마스크
    Bw : (d & ~m) | ((d - v) & m)                      ← 32비트 전체 wrap 뒤 마스크
    D  : (d&m) < (v&m) 이면 그대로, 아니면 A2           ← 모자라면 아무것도 안 함
  마스크 Add
    M  : (d & ~m) | (((d&m) + (v&m)) & m)              ← DPS G2 1.3·gist 식
    Mu : (d & ~m) | ((d + v) & m)                      ← d 를 마스크하지 않고 더함
    Mn : ((d & ~m) | ((d&m) + (v&m))) & 0xFFFFFFFF     ← 올림이 마스크 밖으로 나감
  마스크 없는 Subtract : U = 부호 없는 포화 max(0, d-v), S = 부호 있는 뺄셈 뒤 음수면 0, W = wrap

euddraft 0.11.0.1(eudplib 0.81.0)과 0.9.2.0(eudplib 0.76.14) 양쪽에서 빌드되게 썼다.

디버그 브리지 (2026-09-18, eudext.dbg — 인게임 확인 문서 A-1·B15-5 자동 판정)
  eudext 부트가 있는 빌드(`eudext/examples/s8_check.eds`: 부트 + dbg_setup + 이 파일, 입력 testing/base.scx)에서만
  `dbg_report()` 가 시험 칸 17+5개 값과 모형별 맞은 수, "다 맞은 모형" 비트를 블록에 남기고 `done` 표식을 세운다.
  eudext 가 없는 빌드(build.bat — CBTest.scx, 0.9.2.0 도)에서는 import 가 실패해 아무것도 하지 않는다(맵 그대로).
  통합 맵(auto_all phase 4)은 이 모듈을 import 해 `run_tests()` → `dbg_report(prefix="s8", suite="s8")` 를 부른다.
  비트 순서: SUBX = A, A2, Av, C, B, Bw, D (A2 = 2), ADDX = M, Mu, Mn (M = 1).
"""
from eudplib import *  # noqa: F401,F403

M32 = 0xFFFFFFFF


def _mod(x):
    return x & M32


# ------------------------------------------------------------------ 모형
def sub_models(d, v, m):
    dm, vm = d & m, v & m
    keep = d & ~m & M32
    return {
        "A": _mod(keep | max(0, dm - vm)),
        "A2": _mod(keep | (max(0, dm - vm) & m)),
        "Av": _mod(keep | (max(0, dm - v) & m)),
        "C": _mod(keep | ((dm - vm) & m)),
        "B": _mod(keep | (max(0, d - v) & m)),
        "Bw": _mod(keep | ((d - v) & m)),
        "D": d if dm < vm else _mod(keep | ((dm - vm) & m)),
    }


def add_models(d, v, m):
    dm, vm = d & m, v & m
    keep = d & ~m & M32
    return {
        "M": _mod(keep | ((dm + vm) & m)),
        "Mu": _mod(keep | ((d + v) & m)),
        "Mn": _mod(keep | (dm + vm)),
    }


def _s32(x):
    return x - (1 << 32) if x >> 31 else x


def plain_sub_models(d, v):
    return {
        "U": max(0, d - v),
        "S": max(0, _s32(d) - _s32(v)) & M32,
        "W": (d - v) & M32,
    }


SUBX_MODELS = ["A", "A2", "Av", "C", "B", "Bw", "D"]
ADDX_MODELS = ["M", "Mu", "Mn"]

# (이름, 원래 값 d, [(수정자, 값, 마스크) ...], 모형 dict, 요약 묶음)
TESTS = []


def subx(name, d, v, m):
    TESTS.append((name, d, [(Subtract, v, m)], sub_models(d, v, m), "SUBX"))


def addx(name, d, v, m):
    TESTS.append((name, d, [(Add, v, m)], add_models(d, v, m), "ADDX"))


subx("S1", 0x00001203, 5, 0xFF)            # 마스크 안 3-5: A/A2/Av=1200, C/B/Bw=12FE, D=1203
subx("S2", 0x00000007, 0x105, 0xFF)        # v 에 마스크 밖 비트: Av/B=0, 나머지 2
subx("S3", 0x00000102, 3, 0x0F0F)          # 떨어진 마스크: A=00FF (마스크 밖 비트가 켜짐), A2 계열=000F
subx("S4", 0x80000001, 2, 0x6)             # CrShift·eudplib >>= 기법: A 계열·D=80000001, C/B/Bw=80000007
subx("S5", 0x00001234, 0x100, 0xFF00)      # 모자라지 않는 경우(대조): 모두 00001134
addx("X1", 0x000012FF, 1, 0xFF)            # 올림이 마스크 밖으로: M/Mu=1200, Mn=1300
addx("X2", 0x000000FF, 1, 0xFF00)          # d 의 마스크 밖 비트가 더해지나: M/Mn=00FF, Mu=01FF
# X3: eudplib 비트 반전(XOR) 기법 — 두 액션
_x3d, _x3v = 0x0000F0F0, 0xFF00FF00
_x3 = {}
for _k in ADDX_MODELS:
    _t = add_models(_x3d, _x3v, 0x55555555)[_k]
    _x3[_k] = add_models(_t, _x3v, 0xAAAAAAAA)[_k]
TESTS.append(("X3", _x3d, [(Add, _x3v, 0x55555555), (Add, _x3v, 0xAAAAAAAA)], _x3, "ADDX"))

# 마스크 없는 액션 (eudx 표식 없는 SetMemory)
PLAIN = [
    ("P1", 3, Subtract, 5),            # U=0, W=FFFFFFFE
    ("P2", 5, Subtract, 0xFFFFFFFF),   # U=0, S=6 (부호 있는 해석이면 5-(-1)=6)
    ("P3", 3, Add, 0xFFFFFFFB),        # 음수 더하기 = wrap: FFFFFFFE
]
# 마스크 0xFFFFFFFF 에 eudx 표식을 켠 Subtract (SetMemoryX)
FULLX = ("F1", 3, 5)                   # 기대 0 (포화)


# ------------------------------------------------------------------ 게임 안 코드
_cells = {}
_counts = {}


def _label_ptr(cell, models):
    """cell 값과 같은 모형 이름들을 담은 문자열 주소를 돌려준다 (없으면 '?')."""
    groups = {}
    for k, val in models.items():
        groups.setdefault(val, []).append(k)
    ptr = EUDVariable()
    ptr << Db(b"?\0")
    for val, names in groups.items():
        RawTrigger(conditions=cell.Exactly(val), actions=ptr.SetNumber(Db((" ".join(names)).encode() + b"\0")))
    return ptr


def run_tests():
    for name, d, acts, models, group in TESTS:
        cell = EUDVariable()
        addr = cell.getValueAddr()
        RawTrigger(actions=[cell.SetNumber(d)] + [SetMemoryX(addr, mod, v, m) for mod, v, m in acts])
        _cells[name] = (cell, _label_ptr(cell, models))
        for k, val in models.items():
            cnt = _counts.setdefault((group, k), EUDVariable())
            RawTrigger(conditions=cell.Exactly(val), actions=cnt.AddNumber(1))
    for name, d, mod, v in PLAIN:
        cell = EUDVariable()
        RawTrigger(actions=[cell.SetNumber(d), SetMemory(cell.getValueAddr(), mod, v)])
        if mod == Subtract:
            models = plain_sub_models(d, v)
        else:
            models = {"W": (d + v) & M32, "SAT": min(d + v, M32)}
        _cells[name] = (cell, _label_ptr(cell, models))
    name, d, v = FULLX
    cell = EUDVariable()
    RawTrigger(actions=[cell.SetNumber(d), SetMemoryX(cell.getValueAddr(), Subtract, v, M32)])
    _cells[name] = (cell, _label_ptr(cell, {"U": 0, "W": (d - v) & M32}))

    # eudplib 경로 (에뮬레이터 결과와 같은지)
    e1 = EUDVariable()
    e1 << 7
    e1 -= e1                                  # 에뮬레이터: FFFFFFFF (eudplib 버그)
    _cells["E1"] = (e1, _label_ptr(e1, {"emu": M32, "zero": 0}))
    e2 = EUDVariable()
    e2 << 0x11000322
    f_bsubtract_epd(EPD(e2.getValueAddr()), 1, 5)   # 바이트 1 = 03 에서 5 빼기
    _cells["E2"] = (e2, _label_ptr(e2, {"A": 0x11000022, "C": 0x1100FE22}))
    e3 = EUDLightVariable(0x80000003)
    e3 >>= 1
    e3v = EUDVariable()
    e3v << 0
    RawTrigger(conditions=e3.Exactly(0x40000001), actions=e3v.SetNumber(0x40000001))
    _cells["E3"] = (e3v, _label_ptr(e3v, {"ok": 0x40000001, "?": 0}))
    e4 = EUDVariable()
    e4 << 3
    e4 -= 5
    _cells["E4"] = (e4, _label_ptr(e4, {"W": 0xFFFFFFFE, "U": 0}))
    e5 = EUDLightVariable(3)
    e5 -= 5
    e5v = EUDVariable()
    e5v << 0xDEAD
    RawTrigger(conditions=e5.Exactly(0), actions=e5v.SetNumber(0))
    RawTrigger(conditions=e5.Exactly(0xFFFFFFFE), actions=e5v.SetNumber(0xFFFFFFFE))
    _cells["E5"] = (e5v, _label_ptr(e5v, {"U": 0, "W": 0xFFFFFFFE}))


def _optional_dbg():
    """eudext.dbg 가 불러와져 있고 켜져 있으면 그 모듈, 아니면 None (eudext 없는 빌드 그대로)."""
    try:
        from eudext import dbg  # noqa: PLC0415 — eudext 부트가 있는 빌드에서만
    except Exception:  # noqa: BLE001 — eudplib 0.76·부트 없음
        return None
    return dbg if dbg.f_enabled() else None


def dbg_report(prefix="m01", suite=None, done=None):
    """run_tests() 뒤에 부른다: 시험 칸 값(<prefix>.<이름>), 모형별 맞은 수(<prefix>.SUBX.<모형>),
    다 맞은 모형 비트(<prefix>.SUBX.match / .ADDX.match), done 이름이 있으면 그 표식. dbg 가 없으면 False."""
    dbg = _optional_dbg()
    if dbg is None:
        return False
    for name, (cell, _lp) in _cells.items():
        dbg.mark("%s.%s" % (prefix, name), cell, suite=suite)
    for group, models in (("SUBX", SUBX_MODELS), ("ADDX", ADDX_MODELS)):
        total = sum(1 for t in TESTS if t[4] == group)
        match = EUDVariable()
        match << 0
        for bit, k in enumerate(models):
            cnt = _counts[(group, k)]
            dbg.mark("%s.%s.%s" % (prefix, group, k), cnt, suite=suite)
            RawTrigger(conditions=cnt.Exactly(total), actions=match.AddNumber(1 << bit))
        dbg.mark("%s.%s.match" % (prefix, group), match, suite=suite)
    if done:
        dbg.mark(done, suite=suite)
    return True


_frame = EUDVariable()
_idx = EUDVariable()


def _print_line(i):
    names = [t[0] for t in TESTS] + [p[0] for p in PLAIN] + [FULLX[0], "E1", "E2", "E3", "E4", "E5"]
    n = len(names)
    if i < n:
        nm = names[i]
        cell, lp = _cells[nm]
        f_printAll("\x07S8\x04 " + nm + " got {} = {}", hptr(cell), ptr2s(lp))
    elif i == n:
        parts = []
        args = []
        total = sum(1 for t in TESTS if t[4] == "SUBX")
        for k in SUBX_MODELS:
            parts.append(k + "={}/" + str(total))
            args.append(_counts[("SUBX", k)])
        f_printAll("\x07S8\x04 SUBX " + " ".join(parts), *args)
    else:
        parts = []
        args = []
        total = sum(1 for t in TESTS if t[4] == "ADDX")
        for k in ADDX_MODELS:
            parts.append(k + "={}/" + str(total))
            args.append(_counts[("ADDX", k)])
        f_printAll("\x07S8\x04 ADDX " + " ".join(parts), *args)


def _line_count():
    return len(TESTS) + len(PLAIN) + 1 + 5 + 2


def beforeTriggerExec():
    if EUDExecuteOnce()():
        run_tests()
        dbg_report(prefix="m01", done="done")
        f_printAll("\x07S8\x04 subtract/mask test ready ({} lines)", _line_count())
    EUDEndExecuteOnce()

    _frame.__iadd__(1)
    if EUDIf()(_frame.AtLeast(24)):          # 약 1 초마다 한 줄
        _frame << 0
        EUDSwitch(_idx)
        for i in range(_line_count()):
            if EUDSwitchCase()(i):
                _print_line(i)
                EUDBreak()
        EUDEndSwitch()
        _idx.__iadd__(1)
        if EUDIf()(_idx.AtLeast(_line_count())):
            _idx << 0
        EUDEndIf()
    EUDEndIf()


if __name__ == "__main__":
    # 모형 기대값 표 (파이썬만으로): python s8_ingame.py
    for name, d, acts, models, group in TESTS:
        print(name, hex(d), acts, {k: "%08X" % v for k, v in models.items()})
    for name, d, mod, v in PLAIN:
        ms = plain_sub_models(d, v) if mod == Subtract else {"W": (d + v) & M32, "SAT": min(d + v, M32)}
        print(name, hex(d), mod, hex(v), {k: "%08X" % x for k, x in ms.items()})
