"""스위치 표 주소 확인 맵 (docs/INGAME_CHECKLIST.md A-2, testing/scmodel.py 의 SWITCH_TABLE = 0x58DC40).

빌드: python eudext/tools/build.py euddraft eudext/examples/switch_ingame.eds --work <작업 폴더>
혼자 연다. 첫 사이클에 스위치 1·3·32·33·40 을 켜고, 약 2초마다 한 번 아래 줄을 띄운다.

    [A-2] 0x58DC40 = <값> (기대 2147483653 = 0x80000005)  0x58DC44 = <값> (기대 129 = 0x00000081)
    [A-2] 조건 확인: Switch 1 켜짐 / Switch 2 꺼짐 (둘 다 떠야 정상)

값이 기대와 다르면(예: 둘 다 0) 스위치 표가 0x58DC40 이 아니다 — 두 값을 그대로 알려 준다.
스위치 번호 i(0부터)는 dword `0x58DC40 + 4·(i >> 5)` 의 비트 `i & 31` 이라는 가정
(eudplib locf.py 의 MRGN 표 0x58DC60 바로 앞 32바이트)을 본다.
"""

from eudplib import (
    Cleared,
    DoActions,
    EUDEndExecuteOnce,
    EUDEndIf,
    EUDExecuteOnce,
    EUDIf,
    EUDVariable,
    Set,
    SetSwitch,
    Switch,
    f_dwread,
    f_simpleprint,
    hptr,
)

SWITCHES = (0, 2, 31, 32, 39)  # Switch 1, 3, 32, 33, 40
EXPECT_W0 = (1 << 0) | (1 << 2) | (1 << 31)
EXPECT_W1 = (1 << 0) | (1 << 7)

_tick = EUDVariable()


def onPluginStart():
    pass


def beforeTriggerExec():
    if EUDExecuteOnce()():
        DoActions([SetSwitch(i, Set) for i in SWITCHES])
    EUDEndExecuteOnce()
    _tick.__iadd__(1)
    if EUDIf()(_tick.AtLeast(48)):
        _tick << 0
        w0 = f_dwread(0x58DC40)
        w1 = f_dwread(0x58DC44)
        f_simpleprint(
            "\x07[A-2]\x04 0x58DC40 =", w0, hptr(w0), "(기대 %d = 0x%08X)" % (EXPECT_W0, EXPECT_W0),
            " 0x58DC44 =", w1, hptr(w1), "(기대 %d = 0x%08X)" % (EXPECT_W1, EXPECT_W1),
        )
        if EUDIf()(Switch(0, Set)):
            f_simpleprint("\x07[A-2]\x04 조건 확인: Switch 1 켜짐")
        EUDEndIf()
        if EUDIf()(Switch(1, Cleared)):
            f_simpleprint("\x07[A-2]\x04 조건 확인: Switch 2 꺼짐")
        EUDEndIf()
    EUDEndIf()
