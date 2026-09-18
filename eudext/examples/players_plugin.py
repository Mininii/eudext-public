"""eudext players 예제 (파이썬 플러그인) — players_example.eds 에서 부트 뒤에 놓인다.

    for p in pl.humans():           컴파일 시점 펼침
    with pl.each(pl.Humans) as p:   런타임 반복 (본문 한 벌, CP = p, 끝나면 CP 복구)
    pl.run_as(대상, 액션…)          RotatePlayer 대체
"""

from eudplib import (
    Add,
    CurrentPlayer,
    DisplayText,
    DoActions,
    EUDEndIf,
    EUDIf,
    EUDVariable,
    Gas,
    SetResources,
)

import eudext.players as pl

gold = pl.PerPlayer(EUDVariable)
frames = EUDVariable()


def onPluginStart():
    # 맵을 불러온 뒤라 컴파일 시점 표를 읽을 수 있다
    print("[players_plugin.py] humans=%r force1=%r" % (pl.humans(), pl.force_members(1)))


def beforeTriggerExec():
    frames.__iadd__(1)
    for p in pl.humans():
        gold[p] += 1
    if EUDIf()(frames.Exactly(48)):
        pl.run_as(pl.Everyone, DisplayText("\x04players (py) 48 프레임"))
        pl.run_as([pl.Force(1), pl.Observers], DisplayText("\x04Force1 + 관전자"))
    EUDEndIf()
    with pl.each(pl.Humans) as p:
        if EUDIf()(p == 0):
            DoActions(SetResources(CurrentPlayer, Add, 1, Gas))
        EUDEndIf()
        gold.iadditem(p, 1)
    if EUDIf()(pl.contains_user(pl.Observers)):
        pass  # 관전자 PC 에서만 (로컬) — 표시 외의 일은 하지 않는다
    EUDEndIf()
