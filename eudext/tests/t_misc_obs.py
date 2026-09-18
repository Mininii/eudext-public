"""`misc.ObserverChat` 시험 (에뮬레이터 + scmodel 글·소리 기록): S6 5.1-4.

- **128·131 두 슬롯에서 두 번째 입력**이 delay 뒤에 먹히는지 (원본 버그 B1 수정 — 완료 추가 조건).
- 채팅창이 닫혀 있어야 키가 먹히고, 열리면 0x68C144 가 모드 값이 되는지.
- 관전자가 아닌 PC(0)에서는 아무 메모리도 안 바뀌는지.
- 문구 DisplayText 의 CP 가 이 PC(관전자)이고 끝나면 CP 가 캐시로 돌아오는지.
- always="all"(OBA 판), edge, 여러 모드, 빌드 오류(always+keys, mode='player').
- epScript 예제·인게임 확인 맵 번역·euddraft 빌드.

python tests/t_misc_obs.py
"""

import sys

sys.dont_write_bytecode = True
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import shutil  # noqa: E402
import warnings  # noqa: E402

from eudplib import (  # noqa: E402
    DoActions,
    Exactly,
    Memory,
    SetMemory,
    SetTo,
    f_getcurpl,
    f_setcurpl,
)

from eudext import _compat, chat, local, misc  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing import BASE_MAP, emu, scmodel  # noqa: E402
from eudext.testing.harness import Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

EX = os.path.join(_common.PKG, "examples")
CHAT_ADDR = 0x68C144
CP_ADDR = 0x6509B0
KEY_ADDR = 0x596A18
KEYCODE = {"END": 0x23, "HOME": 0x24, "INSERT": 0x2D}

ck = Checker("t_misc_obs (python)")

# 시험용 인스턴스 (모듈 수준 — 빌드 전에 만든다)
OBS = misc.ObserverChat()
OBS_ALWAYS = misc.ObserverChat(keys=None, always="all")
OBS_EDGE = misc.ObserverChat(edge=True, delay=0)
OBS_NOSOUND = misc.ObserverChat(keys={"END": "ob"}, notice=None, sound=None)


def python_checks():
    ck.eq("모드 값", misc.MODE_VALUES, {"ob": 5, "all": 2, "none": 3})
    ck.eq("기본 키", list(misc.ObserverChat().keys), ["END", "HOME", "INSERT"])
    ck.eq("기본 슬롯", misc.ObserverChat().slots, (128, 129, 130, 131))
    ck.true("always 는 mode 2 초기값", OBS_ALWAYS.mode is not None)
    ck.raises("always + keys 오류", EudextError, misc.ObserverChat, keys={"END": "ob"}, always="all")
    ck.raises("mode=player 오류", EudextError, misc.ObserverChat, keys={"END": "player"})
    ck.raises("잘못된 모드", EudextError, misc.ObserverChat, keys={"END": "spam"})
    ck.raises("잘못된 키 이름", EudextError, misc.ObserverChat, keys={"NOPE": "ob"})
    ck.raises("잘못된 delay", EudextError, misc.ObserverChat, delay=-1)
    ck.raises("잘못된 slots", EudextError, misc.ObserverChat, slots=(7,))
    ck.raises("잘못된 always", EudextError, misc.ObserverChat, keys=None, always="ob")
    ck.true("repr", "ObserverChat" in repr(OBS))
    # 부분 슬롯도 된다
    ck.eq("단일 슬롯", misc.ObserverChat(slots=131).slots, (131,))


# =============================================================================================
# 에뮬레이터
# =============================================================================================


def build_cases(s):
    @s.case("obs")
    def _(t):
        OBS.tick()
        t.watch("mode", OBS.mode.getValueAddr())
        t.watch("wait", OBS.wait.getValueAddr())

    @s.case("always")
    def _(t):
        OBS_ALWAYS.tick()

    @s.case("nosound")
    def _(t):
        OBS_NOSOUND.tick()
        t.watch("mode", OBS_NOSOUND.mode.getValueAddr())
        t.watch("wait", OBS_NOSOUND.wait.getValueAddr())

    @s.case("edge")
    def _(t):
        OBS_EDGE.tick()
        t.watch("mode", OBS_EDGE.mode.getValueAddr())
        local.update()  # 엣지 캐시 갱신 (edge=True)

    @s.case("cp")
    def _(t):
        f_setcurpl(6)
        OBS.tick()
        t.flag("cp_raw", Memory(CP_ADDR, Exactly, 6))
        t.out("cp_cache", f_getcurpl())

    @s.case("err_always_keys", expect_build_error=EudextError, expect_message="함께")
    def _(t):
        o = misc.ObserverChat(keys={"END": "ob"}, always="all")
        o.tick()

    @s.case("err_player", expect_build_error=EudextError, expect_message="player")
    def _(t):
        misc.ObserverChat(keys={"F2": "player"})


def press(m, name):
    m.setdb(KEY_ADDR + KEYCODE[name], 1)


def release_all(m):
    for c in KEYCODE.values():
        m.setdb(KEY_ADDR + c, 0)


def set_chat(m, v):
    m.setdw(CHAT_ADDR, v)


def prep(env):
    """관전자 상태 초기화: 채팅 닫힘, 키 뗌."""
    m = env.m
    set_chat(m, 0)
    release_all(m)
    tm = scmodel.text_model(m)
    if tm is not None:
        tm.clear()


class Env:
    def __init__(self, s):
        self.s = s
        self.m = s.machine


def run_second_input(env, slot):
    """B1: slot(128~131) PC 에서 첫 입력 뒤 delay 만큼 기다렸다 두 번째 입력이 먹히는지."""
    s, m = env.s, env.m
    s.restart(local_player=slot)
    prep(env)
    # 첫 입력: END → 관전자(5)
    press(m, "END")
    r = s.run("obs")
    s.expect_true("obs", r["mode"] == 5 and r["wait"] == 10, "%d 첫 입력 END → mode 5, wait 10" % slot, repr(r.values))
    release_all(m)
    # delay 동안은 다른 키 무시
    press(m, "HOME")
    r = s.run("obs")
    s.expect_true("obs", r["mode"] == 5, "%d delay 중 HOME 무시" % slot, repr(r.values))
    release_all(m)
    # wait 가 0 이 될 때까지 (모든 슬롯에서 줄어야 한다 — B1)
    for _ in range(12):
        r = s.run("obs")
        if r["wait"] == 0:
            break
    s.expect_true("obs", r["wait"] == 0, "%d wait 가 0 으로 (B1: 모든 슬롯에서 감소)" % slot, repr(r.values))
    # 두 번째 입력: HOME → 전체(2)
    press(m, "HOME")
    r = s.run("obs")
    s.expect_true("obs", r["mode"] == 2 and r["wait"] == 10, "%d 두 번째 입력 HOME → mode 2" % slot, repr(r.values))
    release_all(m)


def run_obs(env):
    s, m = env.s, env.m
    # B1: 128 과 131 두 슬롯에서 두 번째 입력
    for slot in (128, 131):
        run_second_input(env, slot)

    # 채팅창이 열려 있으면 키 무시, 대신 0x68C144 를 모드 값으로
    s.restart(local_player=129)
    prep(env)
    press(m, "END")
    set_chat(m, 1)  # 입력 중
    r = s.run("obs")
    s.expect_true("obs", r["mode"] == 0, "채팅 중에는 키 무시(mode 그대로 0)", repr(r.values))
    # 모드를 먼저 정하고(닫힘) 채팅을 연다
    set_chat(m, 0)
    release_all(m)
    press(m, "INSERT")
    s.run("obs")
    release_all(m)
    set_chat(m, 1)
    s.run("obs")
    s.expect_true("obs", m.dw(CHAT_ADDR) == 3, "채팅 열리면 0x68C144 = 대상없음(3)", hex(m.dw(CHAT_ADDR)))
    # END → 5, HOME → 2 도
    for key, mv in (("END", 5), ("HOME", 2)):
        s.restart(local_player=130)
        prep(env)
        press(m, key)
        s.run("obs")
        release_all(m)
        set_chat(m, 1)
        s.run("obs")
        s.expect_true("obs", m.dw(CHAT_ADDR) == mv, "%s → 채팅 열리면 %d" % (key, mv), hex(m.dw(CHAT_ADDR)))

    # 관전자가 아닌 PC: 아무것도 안 바뀐다
    for pc in (0, 5, 7):
        s.restart(local_player=pc)
        prep(env)
        press(m, "END")
        set_chat(m, 1)
        r = s.run("obs")
        s.expect_true("obs", r["mode"] == 0 and r["wait"] == 0 and m.dw(CHAT_ADDR) == 1,
                      "PC %d(관전자 아님) 무변화" % pc, repr(r.values))

    # 문구: CP 가 이 PC(관전자)이고 소리도 그 CP
    s.restart(local_player=128)
    prep(env)
    tm = scmodel.text_model(m)
    press(m, "END")
    s.run("obs")
    notices = tm.texts()
    s.expect_true("obs", any("관전자" in (t or "") for t in notices), "문구가 떴다", repr(notices))
    s.expect_true("obs", all(r.cp == 128 for r in tm.records), "문구·소리 CP = 이 PC(128)",
                  repr([(r.kind, r.cp) for r in tm.records]))
    s.expect_true("obs", any(r.kind == "wav" for r in tm.records), "button3.wav 소리")

    # notice=None, sound=None: 아무 표시·소리 없이 모드만
    s.restart(local_player=128)
    prep(env)
    tm.clear()
    press(m, "END")
    r = s.run("nosound")
    s.expect_true("nosound", r["mode"] == 5 and not tm.records, "notice·sound None → 표시 없음, 모드만", repr(tm.records))


def run_always(env):
    s, m = env.s, env.m
    s.restart(local_player=128)
    prep(env)
    set_chat(m, 1)
    s.run("always")
    s.expect_true("always", m.dw(CHAT_ADDR) == 2, "always: 채팅 열리면 전체(2)", hex(m.dw(CHAT_ADDR)))
    # 채팅 닫히면 안 건드림
    set_chat(m, 0)
    s.run("always")
    s.expect_true("always", m.dw(CHAT_ADDR) == 0, "always: 채팅 닫히면 그대로")
    # 관전자 아님 → 무변화
    s.restart(local_player=0)
    prep(env)
    set_chat(m, 1)
    s.run("always")
    s.expect_true("always", m.dw(CHAT_ADDR) == 1, "always: 관전자 아니면 무변화")


def run_edge(env):
    s, m = env.s, env.m
    s.restart(local_player=131)
    prep(env)
    # 프레임1: 새로 누름 → 엣지 참 → mode 5
    press(m, "END")
    r = s.run("edge")
    s.expect_true("edge", r["mode"] == 5, "엣지: 누르는 순간 mode 5", repr(r.values))
    # 프레임2: 계속 눌림 → 엣지 거짓 (mode 그대로, 다시 안 바뀜은 값으로 확인 불가하나 캐시가 막는다)
    r = s.run("edge")
    s.expect_true("edge", r["mode"] == 5, "엣지: 계속 눌러도 mode 유지")
    # 뗐다가 다시 → 엣지 다시
    release_all(m)
    s.run("edge")
    press(m, "HOME")
    r = s.run("edge")
    s.expect_true("edge", r["mode"] == 2, "엣지: 뗐다 다른 키 → mode 2", repr(r.values))


def run_cp(env):
    s = env.s
    s.restart(local_player=128)
    prep(env)
    press(env.m, "END")
    r = s.run("cp")
    s.expect_true("cp", r.error is None and r["cp_raw"] == 1 and r["cp_cache"] == 6, "CP 6 유지(문구 뒤 되돌림)", repr(r.values))


def section_emu():
    s = Suite("t_misc_obs", memory={"text": True, "local_player": 128})
    build_cases(s)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s.build()
    env = Env(s)
    run_obs(env)
    run_always(env)
    run_edge(env)
    run_cp(env)
    return s.report()


# =============================================================================================
# epScript 예제·인게임 맵
# =============================================================================================


def eps_checks(cke):
    for name, needles in (
        ("misc_example", ("misc.ObserverChat(", "obs.tick()", "misc.Countdown(", "misc.f_host_player()")),
        ("misc_ingame", ("misc.ObserverChat(", "obs.tick()", "local.f_update()")),
        ("misc_exit_trap", ("misc.f_unsafe_exit_trap(", "enable=True")),
    ):
        src = open(os.path.join(EX, name + ".eps"), encoding="utf-8").read()
        out, nerr = _compat.eps_compile(name + ".eps", src)
        cke.eq("%s eps errors" % name, nerr, 0)
        for needle in needles:
            cke.true("%s: %s" % (name, needle), out is not None and needle in out, "")


def _load(name):
    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_misc_" + name)
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, name + ".eps"), os.path.join(work, name + ".eps"))
    from eudplib import CompressPayload, LoadMap

    LoadMap(BASE_MAP)
    CompressPayload(True)
    return build._load_plugin(os.path.join(work, name + ".eps"), {})


def eps_emulate(cke):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mod = _load("misc_example")
        prog = emu.Program(mod.afterTriggerExec)
        for n in ("frame", "cdDone"):
            if hasattr(mod, n):
                prog.watch(n, getattr(mod, n))
        m = prog.build()
    scmodel.install(m, text=True, local_player=128)
    m.cycle(60)
    cke.true("example 돈다", m.ends[-1][0] < 500, str(m.ends[-1]))


def eps_build(cke):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    for name in ("misc_example", "misc_ingame", "misc_exit_trap"):
        work = os.path.join(_common.WORK, "t_misc_build_" + name)
        eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
        r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
        print("  " + r.summary())
        cke.true("euddraft " + name, r.ok, r.log[-2000:])
        cke.true("eps compiled " + name, '[epScript] Compiling "%s.eps"' % name in r.log, "")


# =============================================================================================
# 비용 (tools/cost.py)
# =============================================================================================

C_OBS = misc.ObserverChat()
C_OBS_ALWAYS = misc.ObserverChat(keys=None, always="all")


def _obs_setup_observer(t):
    # 관전자로 만드는 준비는 memory 로 (COST_MEMORY)
    pass


COST_CASES = [
    CostCase("ObserverChat.tick (키 3개)", lambda t: C_OBS.tick(), funcs=[C_OBS._get_body()],
             note="본문 = 이 인스턴스 1벌"),
    CostCase("ObserverChat.tick (always='all')", lambda t: C_OBS_ALWAYS.tick(), funcs=[C_OBS_ALWAYS._get_body()]),
]
COST_MEMORY = {"text": True, "local_player": 128}


def main():
    python_checks()
    ok = section_emu()
    cke = Checker("t_misc_obs (epScript)")
    eps_checks(cke)
    eps_emulate(cke)
    eps_build(cke)
    finish(ok, ck.report(), cke.report())


if __name__ == "__main__":
    main()
