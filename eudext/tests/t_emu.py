"""에뮬레이터 자체 기본 시험 (DPS_eud tests/t_emu_basic.py 방식 + 확장 기능).

python tests/t_emu.py
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: F401  (경로·산출물 설정)
from _common import Checker, finish

from eudplib import (
    AtLeast,
    CompressPayload,
    CurrentPlayer,
    Deaths,
    DisplayText,
    DoActions,
    EUDEndIf,
    EUDEndInfLoop,
    EUDIf,
    EUDInfLoop,
    EUDOnStart,
    EUDVariable,
    Force1,
    LoadMap,
    RawTrigger,
    SetDeaths,
    SetSwitch,
    SetTo,
    Switch,
    Toggle,
    f_dwread_epd,
    f_setcurpl,
    EPD,
)
from eudplib import Set as SwSet
from eudplib import EUDFunc, SaveMap, ShufflePayload

import os
import tempfile

from eudext import _compat
from eudext.testing import BASE_MAP, emu, scmodel

ck = Checker("t_emu")
LoadMap(BASE_MAP)
CompressPayload(True)

# --- 1. 기본 (DPS t_emu_basic 과 같은 값) + 확장 ---
v = EUDVariable()
w = EUDVariable()
x = EUDVariable(5)
once_cnt = EUDVariable()
sat = EUDVariable(10)
masked = EUDVariable(0x12345678)
mask_hit = EUDVariable()
sw_on = EUDVariable()
local_id = EUDVariable()


def body():
    v.__iadd__(3)
    if EUDIf()(v.AtLeast(10)):
        w << w + 100
    EUDEndIf()
    x << x - 7  # wrap 뺄셈
    DoActions(DisplayText("hi"))  # 흉내 못 냄 → 기록만
    RawTrigger(actions=once_cnt.AddNumber(1), preserved=False)  # 비보존: 한 번만
    RawTrigger(actions=sat.SubtractNumber(4))  # SC Subtract = 0 포화
    RawTrigger(actions=masked.AddNumberX(1, 0xFF))  # 마스크 Add: 하위 바이트만 +1
    RawTrigger(conditions=masked.AtLeastX(0x7A, 0xFF), actions=mask_hit.AddNumber(1))  # 마스크 조건
    f_setcurpl(3)
    DoActions(SetDeaths(CurrentPlayer, SetTo, 77, 0))  # player 13 = CP → P4 마린 데스 칸
    f_setcurpl(0)
    DoActions(SetSwitch(5, Toggle))  # scmodel 스위치
    if EUDIf()(Switch(5, SwSet)):
        sw_on.__iadd__(1)
    EUDEndIf()
    local_id << f_dwread_epd(EPD(scmodel.LOCAL_PLAYER_ADDR))  # 게임 메모리 초기값


prog = emu.Program(body)
for name, var in (("v", v), ("w", w), ("x", x), ("once", once_cnt), ("sat", sat), ("masked", masked),
                  ("mask_hit", mask_hit), ("sw_on", sw_on), ("local", local_id)):
    prog.watch(name, var)
m = prog.build()
scmodel.install(m, local_player=2, players=("human", "human", "computer"))

want_x = 5
rows = []
for i in range(1, 6):
    m.cycle()
    want_x = (want_x - 7) & 0xFFFFFFFF
    ck.eq("v@%d" % i, m.var("v"), 3 * i)
    ck.eq("w@%d" % i, m.var("w"), max(0, i - 3) * 100)
    ck.eq("x@%d" % i, m.var("x"), want_x)
    ck.eq("sat@%d" % i, m.var("sat"), max(0, 10 - 4 * i))
    ck.eq("masked@%d" % i, m.var("masked"), 0x12345600 | (0x78 + i))
    ck.eq("mask_hit@%d" % i, m.var("mask_hit"), max(0, 0x78 + i - 0x7A + 1))
    ck.eq("sw_on@%d" % i, m.var("sw_on"), (i + 1) // 2)
    ck.eq("end@%d" % i, m.ends[-1][1], emu.END)
    rows.append((i, m.var("v"), m.var("w"), hex(m.var("x")), m.ends[-1][0]))
ck.eq("once", m.var("once"), 1)
ck.eq("P4 deaths via CP", m.dw(emu.EPD0 + 4 * 3), 77)
ck.eq("CP after", m.dw(emu.CP_ADDR), 0)
ck.eq("local player", m.var("local"), 2)
ck.eq("player type P3", m.db(scmodel.PLAYER_TABLE + 36 * 2 + 8), scmodel.PLAYER_TYPE["computer"])
ck.true("DisplayText logged", any(e[0] == "act" and e[1] == 9 for e in m.log))
ck.true("unknown counter", m.unknown[("act", 9)] >= 5, repr(m.unknown))
ck.true("switch model", scmodel.read_switch(m, 5) is True)
for r in rows:
    print("  cycle %d: v=%d w=%d x=%s steps=%d" % r)

# 바이트 읽기·쓰기, 스냅숏
m.setdb(0x58A365, 0xAB)
ck.eq("db", m.db(0x58A365), 0xAB)
ck.eq("dw after setdb", m.dw(0x58A364) & 0xFF00, 0xAB00)
ck.raises("unaligned setdw", emu.EmuError, m.setdw, 0x58A365, 1)
snap = m.snapshot()
m.cycle()
ck.eq("v@6", m.var("v"), 18)
m.restore(snap)
ck.eq("v restored", m.var("v"), 15)

# --- 2. 같은 프로세스에서 두 번째 빌드: EUDOnStart 누적이 없어야 한다 (_compat.reset_build_state) ---
starts = EUDVariable()
bad = EUDVariable()


def body2():
    pass


def setup2():
    EUDOnStart(lambda: DoActions(starts.AddNumber(1)))


for k in range(2):
    LoadMap(BASE_MAP)
    p2 = emu.Program(body2, setup=setup2)
    p2.watch("starts", starts)
    m2 = p2.build()
    m2.cycle(2)
    ck.eq("EUDOnStart once (build %d)" % (k + 1), m2.var("starts"), 1)

# 빌드마다 페이로드 크기가 같아야 한다 (0.81.0 은 create-payload 콜백이 첫 빌드에서만 불려 변수 버퍼가 쌓인다 →
# _compat.reset_build_state 가 버퍼를 새로 만든다)
sizes = []
for k in range(3):
    LoadMap(BASE_MAP)
    ShufflePayload(False)
    p3 = emu.Program(body2)
    p3.build()
    sizes.append(p3.payload_size)
ShufflePayload(True)
ck.eq("payload size stable", len(set(sizes)), 1)
print("  빈 빌드 페이로드: %s" % sizes)


# 알려진 한계: 첫 빌드에서 만든 EUDFunc 본문에 구운 문자열은 LoadMap 뒤 다음 빌드의 STR 에 없다
@EUDFunc
def f_show():
    DoActions(DisplayText("eudext-multibuild-probe"))


strs = []
for k, extra in enumerate(("", "other-first")):
    LoadMap(BASE_MAP)

    def mainf(extra=extra):
        if extra:
            DoActions(DisplayText(extra))
        f_show()

    _compat.reset_build_state()
    SaveMap(os.path.join(tempfile.gettempdir(), "t_emu_str_%d.scx" % k), mainf)
    strs.append(b"eudext-multibuild-probe" in _compat.chk_string_section())
ck.eq("string baked in 1st build only (known limit)", strs, [True, False])

# --- 3. 오류 검출 ---


def body_jump_out():
    RawTrigger(nextptr=0x12345678)


def body_special_player():
    RawTrigger(conditions=Deaths(Force1, AtLeast, 1, 0))


def body_endless():
    if EUDInfLoop()():
        bad.__iadd__(1)
    EUDEndInfLoop()


for label, fn, kw in (("jump out", body_jump_out, {}), ("special player", body_special_player, {}),
                      ("step limit", body_endless, {"limit": 5000})):
    LoadMap(BASE_MAP)
    m3 = emu.Program(fn).build()
    ck.raises(label, emu.EmuError, m3.cycle, 1, **kw)

# --- 4. harness 추가 기능 (WP2): 빌드 오류 기대 케이스, restart(이 PC 번호·게임 메모리만 바꿔 다시 시작) ---
# 이 Suite 는 일부러 실패하는 판정을 담으므로 report() 를 부르지 않고(run_all 합계에 섞이지 않게) ck 로 확인한다.
from eudplib import EUDEndIf as _EndIf, EUDIf as _If, f_getuserplayerid  # noqa: E402

from eudext.errors import EudextError, fail  # noqa: E402
from eudext.testing.harness import Suite  # noqa: E402

ORE_P1 = 0x57F0F0
hs = Suite("t_emu harness", memory={"local_player": 0, "players": ("human", "human")}, verbose=False)


@hs.case("ok_before")
def _(t):
    t.out("r", t.var("a") + 1)


@hs.case("exp_ok", expect_build_error=EudextError)
def _(t):
    a = t.var("a")
    RawTrigger(actions=a.SetNumber(7))  # 예외 전에 만든 트리거·열린 블록은 바깥 흐름에 붙지 않아야 한다
    if _If()(a.Exactly(1)):
        fail("일부러 낸 오류 %d", 3)
    _EndIf()


@hs.case("exp_msg", expect_build_error=(TypeError, EudextError), expect_message="일부러.*3")
def _(t):
    fail("일부러 낸 오류 %d", 3)


@hs.case("exp_wrong_msg", expect_build_error=EudextError, expect_message="다른 글")
def _(t):
    fail("일부러")


@hs.case("exp_none", expect_build_error=EudextError)
def _(t):
    t.out("r", 1)


@hs.case("exp_other", expect_build_error=EudextError)
def _(t):
    raise ValueError("다른 종류")


@hs.case("plain_error")
def _(t):
    raise EudextError("보통 케이스의 빌드 실패")


@hs.case("userp")
def _(t):
    t.out("p", f_getuserplayerid())  # eudplib 이 게임 시작 때 한 번 0x512684 를 읽어 둔 값
    t.watch("raw", scmodel.LOCAL_PLAYER_ADDR)
    t.watch("ore", ORE_P1)
    t.watch("ore2", ORE_P1 + 4)
    once = t.var("once")
    RawTrigger(actions=once.AddNumber(1), preserved=False)  # 게임당 한 번


@hs.case("ok_after")
def _(t):
    t.out("r", t.var("a") * 3)


ck.raises("case: expect_message 만", TypeError, hs.case, "x", expect_message="y")
ck.raises("case: 예외 클래스가 아님", TypeError, hs.case, "x", expect_build_error="EudextError")
hs.build()
rows = {r["case"]: r for r in hs.summary()}
for cname, want in (("exp_ok", (1, 0)), ("exp_msg", (1, 0)), ("exp_wrong_msg", (0, 1)), ("exp_none", (0, 1)),
                    ("exp_other", (0, 1)), ("plain_error", (0, 1))):
    ck.eq("expect %s 통과·실패" % cname, (rows[cname]["passed"], rows[cname]["failed"]), want)
ck.true("expect 표시", rows["exp_ok"]["expect_build_error"] and not rows["ok_before"]["expect_build_error"])
ck.true("expect caught", isinstance(hs.cases["exp_ok"].caught, EudextError), repr(hs.cases["exp_ok"].caught))
ck.true("expect caught (other)", isinstance(hs.cases["exp_other"].caught, ValueError))
ck.eq("expect 케이스는 build_error 없음", hs.cases["exp_ok"].build_error, None)
ck.true("보통 케이스 빌드 실패", "EudextError" in (hs.cases["plain_error"].build_error or ""))
ck.true("expect run 거부", "실행하지 않" in (hs.run("exp_ok").error or ""))
ck.eq("expect diff 거부", hs.diff("exp_none", lambda a: {}, {"a": [1]}, n=0), (0, 1))
for a in (0, 5, 0xFFFFFFFF):
    ck.eq("ok_before %d" % a, hs.run("ok_before", {"a": a}).values["r"], (a + 1) & 0xFFFFFFFF)
    ck.eq("ok_after %d" % a, hs.run("ok_after", {"a": a}).values["r"], (a * 3) & 0xFFFFFFFF)
base0 = hs.baseline
r = hs.run("userp", fresh=True)
ck.eq("userp 처음", (r["p"], r["raw"], r["once"], r["ore"]), (0, 0, 1, 0))
r = hs.run("userp")
ck.eq("userp 두 번째 사이클 (한 번만)", r["once"], 1)

hs.restart(local_player=3)
ck.eq("restart memory 덮어쓰기", hs.memory, {"local_player": 3, "players": ("human", "human")})
r = hs.run("userp")
ck.eq("restart 뒤 userp", (r["p"], r["raw"], r["once"]), (3, 3, 1))
hs.run("userp")
hs.reset()
r = hs.run("userp")
ck.eq("restart 뒤 reset → 새 시작 상태", (r["p"], r["once"]), (3, 1))
ck.eq("restart 뒤 다른 케이스", hs.run("ok_after", {"a": 7}).values["r"], 21)
ck.eq("restart 기준값 같음", hs.baseline, base0)
ck.eq("restart 기준값 P2 형", hs.machine.db(scmodel.PLAYER_TABLE + 36 * 1 + 8), scmodel.PLAYER_TYPE["human"])

hs.restart(memory={"local_player": 129}, init_mem={ORE_P1: 0x1234}, prep=lambda mm: mm.setdw(ORE_P1 + 4, 77))
r = hs.run("userp")
ck.eq("restart memory 통째 + init_mem + prep", (r["p"], r["raw"], r["ore"], r["ore2"], r["once"]), (129, 129, 0x1234, 77, 1))
ck.eq("restart memory 통째 (P2 형 기본값)", hs.machine.db(scmodel.PLAYER_TABLE + 36 * 1 + 8), scmodel.PLAYER_TYPE["inactive"])
hs.restart()
r = hs.run("userp")
ck.eq("restart 인자 없음 = 그대로", (r["p"], r["ore"], r["ore2"]), (129, 0x1234, 77))
hs.restart(local_player=0, init_mem={}, prep=False)
r = hs.run("userp")
ck.eq("restart init_mem·prep 지우기", (r["p"], r["ore"], r["ore2"], r["once"]), (0, 0, 0, 1))
ck.eq("restart 횟수", hs.restarts, 4)

hs.restart(units={})
model = scmodel.unit_model(hs.machine)
ck.true("restart units 모델", model is not None and len(model.created) == 1 and not model.created[0].ok,
        repr(model and model.created))
hs.restart(local_player=2)
ck.true("restart units 모델 새것", scmodel.unit_model(hs.machine) is not model and len(scmodel.unit_model(hs.machine).created) == 1)
ck.eq("restart units 뒤 userp", hs.run("userp").values["p"], 2)

ok = ck.report()
finish(ok)
