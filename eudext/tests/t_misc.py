"""`misc` 나머지 소기능 시험 (에뮬레이터로 볼 수 있는 범위): 방장·부대 지정·카운트다운·와이드 판정,
그리고 `unsafe_exit_trap` 이 기본으로 막히는지 (harness expect_build_error).

- host_player: 방장 이름 표를 놓고 슬롯별로 맞는 번호가 나오는지, 못 찾으면 0xFFFFFFFF.
- HostNameIs: 접두 일치 조건.
- hotkey_addr·alpha_id·SetHotkeyUnit/HotkeyUnit: 주소 계산과 조건·액션.
- Countdown: tick(포화)·done·at_least·set·add.
- is_widescreen: 빌드·실행(에뮬레이터는 CenterView 를 흉내 내지 못해 판정 자체는 인게임 F19-3).
- unsafe_exit_trap: enable 없이 부르면 빌드 오류, enable=True 는 빌드된다.

python tests/t_misc.py
"""

import sys

sys.dont_write_bytecode = True
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import warnings  # noqa: E402

from eudplib import Exactly, SetTo  # noqa: E402

from eudext import misc  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing.harness import Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

HOST_NAME_ADDR = 0x6D0F78
PLAYER_NAME_ADDR = 0x6D0FDC

ck = Checker("t_misc (python)")

CD = misc.Countdown(0)
CD2 = misc.Countdown(3)


def python_checks():
    # 주소 계산
    ck.eq("hotkey_addr(0,0,0)", misc.hotkey_addr(0, 0, 0), 0x57FE60)
    ck.eq("hotkey_addr(1,2,3)", misc.hotkey_addr(1, 2, 3), 0x57FE60 + 0x360 + 0x60 + 0xC)
    ck.eq("hotkey_addr(11,17,11)", misc.hotkey_addr(11, 17, 11), 0x57FE60 + 0x360 * 11 + 0x30 * 17 + 4 * 11)
    for bad in ((12, 0, 0), (0, 18, 0), (0, 0, 12), (-1, 0, 0)):
        ck.raises("hotkey_addr 오류 %r" % (bad,), EudextError, misc.hotkey_addr, *bad)
    # alpha_id
    ck.eq("alpha_id(0,0)", misc.alpha_id(0, 0), 1)
    ck.eq("alpha_id(0,5)", misc.alpha_id(0, 5), 6)
    ck.eq("alpha_id(3,0)", misc.alpha_id(3, 0), (3 << 11) | 1)
    ck.raises("alpha_id index 오류", EudextError, misc.alpha_id, 0, 2048)
    # HostNameIs 는 컴파일 시점 조건 목록
    c1 = misc.HostNameIs("Host")
    ck.true("HostNameIs 4바이트 = 조건 1", hasattr(c1, "fields"))
    c2 = misc.HostNameIs("HostName")
    ck.eq("HostNameIs 8바이트 = 조건 2", len(c2), 2)
    ck.raises("HostNameIs 17바이트 오류", EudextError, misc.HostNameIs, "x" * 17)
    # Countdown 검사
    ck.raises("Countdown 음수", EudextError, misc.Countdown, -1)
    ck.raises("tick step 0", EudextError, misc.Countdown(1).tick, 0)


# =============================================================================================
# 에뮬레이터
# =============================================================================================


def build_cases(s):
    @s.case("host")
    def _(t):
        t.out("host", misc.host_player())

    @s.case("hostname")
    def _(t):
        t.flag("m1", misc.HostNameIs("Host"))
        t.flag("m2", misc.HostNameIs("Xyz1"))

    @s.case("hotkey")
    def _(t):
        from eudplib import DoActions

        DoActions(misc.SetHotkeyUnit(0, 0, 0, SetTo, misc.alpha_id(1, 5)))
        t.flag("hit", misc.HotkeyUnit(0, 0, 0, Exactly, misc.alpha_id(1, 5)))
        t.flag("miss", misc.HotkeyUnit(0, 0, 0, Exactly, 999))

    @s.case("cd")
    def _(t):
        start = t.var("start")
        CD.set(start)
        CD.tick(1)
        t.watch("v", CD.v.getValueAddr())
        t.flag("done", CD.done())
        t.flag("ge3", CD.at_least(3))

    @s.case("cd_tick")
    def _(t):
        CD2.tick()
        t.watch("v", CD2.v.getValueAddr())

    @s.case("cd_add")
    def _(t):
        CD2.add(t.var("n"))
        t.watch("v", CD2.v.getValueAddr())

    @s.case("wide")
    def _(t):
        w = misc.is_widescreen("Anywhere")
        t.watch("w", w.getValueAddr())

    @s.case("exit_blocked", expect_build_error=EudextError, expect_message="enable")
    def _(t):
        misc.unsafe_exit_trap(0)

    @s.case("exit_enabled")
    def _(t):
        misc.unsafe_exit_trap(0, enable=True)


def _name16(text):
    b = text.encode("utf-8")[:16]
    return b + bytes(16 - len(b))


def set_names(host, slots):
    """host = 방장 이름(bytes/str), slots = {플레이어: 이름}."""
    def _p(m):
        m.write_bytes(HOST_NAME_ADDR, _name16(host))
        for p in range(8):
            m.write_bytes(PLAYER_NAME_ADDR + 0x24 * p, _name16(slots.get(p, "none%d" % p)))
    return _p


def run_host(s):
    for host_slot in (0, 3, 7):
        s.restart(prep=set_names("HostGuy", {host_slot: "HostGuy"}))
        r = s.run("host")
        s.expect_true("host", r["host"] == host_slot, "방장 = 슬롯 %d" % host_slot, repr(r.values))
    # 못 찾으면 0xFFFFFFFF (관전자 방장)
    s.restart(prep=set_names("Observer", {p: "p%d" % p for p in range(8)}))
    r = s.run("host")
    s.expect_true("host", r["host"] == 0xFFFFFFFF, "방장 미발견 → -1", repr(r.values))
    # 첫 번째 일치만 (같은 이름이 둘이면 낮은 번호)
    s.restart(prep=set_names("Dup", {2: "Dup", 5: "Dup"}))
    r = s.run("host")
    s.expect_true("host", r["host"] == 2, "중복이면 낮은 번호", repr(r.values))


def run_hostname(s):
    s.restart(prep=set_names("HostName", {}))
    r = s.run("hostname")
    s.expect_true("hostname", r["m1"] == 1 and r["m2"] == 0, "HostNameIs 접두 일치", repr(r.values))
    s.restart(prep=set_names("Xyz1zzzz", {}))
    r = s.run("hostname")
    s.expect_true("hostname", r["m1"] == 0 and r["m2"] == 1, "HostNameIs 다른 이름", repr(r.values))


def run_hotkey(s):
    s.restart()
    r = s.run("hotkey")
    s.expect_true("hotkey", r["hit"] == 1 and r["miss"] == 0, "SetHotkeyUnit → HotkeyUnit 조건", repr(r.values))


def run_countdown(s):
    for start, v, done, ge3 in ((5, 4, 0, 1), (3, 2, 0, 0), (1, 0, 1, 0), (0, 0, 1, 0)):
        r = s.run("cd", {"start": start})
        s.expect_true("cd", r["v"] == v and r["done"] == done and r["ge3"] == ge3,
                      "Countdown start=%d → v=%d done=%d ge3=%d" % (start, v, done, ge3), repr(r.values))
    # 매 프레임 감소, 0 에서 멈춤
    s.restart()
    seq = []
    for _ in range(6):
        seq.append(s.run("cd_tick").values["v"])
    s.expect_true("cd_tick", seq == [2, 1, 0, 0, 0, 0], "카운트다운 포화 감소", repr(seq))
    # add (wrap)
    s.restart()
    r = s.run("cd_add", {"n": 10})
    s.expect_true("cd_add", r["v"] == 13, "add 10 → 3+10", repr(r.values))


def run_wide(s):
    s.restart(local_player=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = s.run("wide")
    # 에뮬레이터는 CenterView 로 화면을 옮기지 않아 반폭 = 320 → 와이드 아님(0). 실제 판정은 인게임 F19-3.
    s.expect_true("wide", r.error is None and r["w"] in (0, 1), "is_widescreen 빌드·실행", repr(r.values))


def run_exit(s):
    s.expect_true("exit_enabled", s.cases["exit_enabled"].build_error is None, "unsafe_exit_trap(enable=True) 빌드됨")


def section_emu():
    s = Suite("t_misc", memory={"text": True})
    build_cases(s)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s.build()
    run_host(s)
    run_hostname(s)
    run_hotkey(s)
    run_countdown(s)
    run_wide(s)
    run_exit(s)
    return s.report()


# =============================================================================================
# 비용 (tools/cost.py)
# =============================================================================================

C_CD = misc.Countdown(240)
C_HK = misc.alpha_id(0, 5)

COST_CASES = [
    CostCase("Countdown.tick", lambda t: C_CD.tick()),
    CostCase("host_player (시작 1회)", lambda t: t.out("h", misc.host_player())),
]


def main():
    python_checks()
    ok = section_emu()
    finish(ok, ck.report())


if __name__ == "__main__":
    main()
