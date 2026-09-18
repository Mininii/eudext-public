"""eudext 예제 (파이썬 플러그인): 로컬 입력은 **표시 전용** 구역에서만 쓴다 (DESIGN 3.7, 4.12).

- `local.only(p)` 안에서만 로컬 조건·값을 쓴다(밖에서 쓰면 빌드 경고).
- 공유 루프(`EUDPlayerLoop`)가 모든 PC 에서 같게 CP 를 p 로 바꾼 뒤, `local.only(CurrentPlayer)` 로
  "이 PC 가 p 일 때만" 표시한다 → CP 를 로컬로 바꾸지 않아 디싱크가 없다.
- `local.update()` 는 모든 소비자 뒤에 한 번(afterTriggerExec 끝). sync 훅 플러그인을 쓰는 맵이면 필요 없다.

단독 빌드: python eudext/tools/build.py standalone eudext/examples/local_example.py --out <작업 폴더>/local.scx
"""

from eudplib import CurrentPlayer, EUDEndPlayerLoop, EUDPlayerLoop, EUDEndIf, EUDIf, f_println

from eudext import local

show = local.key_toggle("TAB", guard=local.not_typing())  # TAB 을 누를 때마다 0/1 (로컬)
mouse = local.track_mouse()  # update() 가 채우는 마우스 맵 좌표 (로컬)


def afterTriggerExec():
    EUDPlayerLoop()()  # 공유: 모든 PC 가 같은 순서로 CP 를 바꾼다
    with local.only(CurrentPlayer):  # 이 PC 가 CP 일 때만
        if EUDIf()(local.key_pressed("F5")):
            f_println("F5 — 마우스 {}, {}", mouse.x, mouse.y)
        EUDEndIf()
        if EUDIf()([show.Exactly(1), local.mouse_pressed("R"), local.not_typing()]):
            f_println("오른쪽 클릭 (TAB 표시 켜짐)")
        EUDEndIf()
    EUDEndPlayerLoop()
    local.update()  # 모든 소비자 뒤 1회
