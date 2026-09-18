"""eudext.datpatch 예제 (파이썬 플러그인). datpatch_example.eds 에서 boot.py 다음에 놓인다.

- 모듈을 불러올 때 선언한 값은 "시작 1회 목록" 에 들어가 게임 시작 때 64액션씩 트리거로 한 번 적용된다.
- onPluginStart·beforeTriggerExec 안에서 선언해도 같은 목록에 들어간다(그 빌드에만).
- 조건에 따라 쓰는 값은 `dat.actions(...)` 로 액션 목록을 받아 조건 블록 안에서 낸다.
- 같은 프레임 안에서만 바꿨다 되돌릴 값은 `with dat.temporary(): dat.now…`.
"""

from eudplib import EUDEndIf, EUDIf, EUDVariable

from eudext import datpatch as dat

# ── 시작 1회 목록 (필드 이름 = eudplib scdata 멤버 이름, 값은 원시 값) ──
dat.unit("Terran Marine").set(maxHp=80 * 256, armor=2, mineralCost=75)
dat.unit(208).flags(Flyer=True, Invincible=True)
dat.unit(162).mask("baseProperty", 0x400200, 0x480200).set(buildingDimX=1, buildingDimY=1)
dat.weapon(1).splash(7, 14, 21)
dat.flingy(106).set(topSpeed=8000, acceleration=400)
dat.player_unit_enable("Terran Marine", players=range(5), value=1)

# ── TEP 이식 층: 키 이름·변환(HP×256, SuppCost×2, Playerable 2 = P1~P5 만)을 TEP 그대로 ──
dat.tep.SetUnitsDatX(0, {"HP": 60, "SuppCost": 1, "Playerable": 2})

# ── 매 프레임 목록 (게임이 되돌리는 칸) ──
dat.every_frame().unit(0).set(requirementOffset=0)

phase = EUDVariable()


def onPluginStart():
    dat.weapon(2).set(cooldown=10)  # 빌드 중 선언도 시작 목록에 들어간다


def beforeTriggerExec():
    boss_acts = dat.actions(lambda d: d.weapon(128).set(damage=65535, flingy=158, removeAfter=64))
    if EUDIf()(phase.Exactly(1)):
        dat.emit(boss_acts)  # 조건 없는 트리거로 그 자리에 (64액션당 1)
    EUDEndIf()
    with dat.temporary():  # 블록 끝에서 f_unpatchall 로 되돌림
        dat.now.weapon(phase).set(damage=phase)
