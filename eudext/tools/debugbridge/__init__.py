"""디버그 브리지 외부 도구 (DESIGN 5.5).

- `dbg_reader.py`: 게임 메모리에서 블록을 찾아 읽는 리더 (DPS_Enhance eudplib-port `tools/debugbridge` 사본 + eudext 확장 표시)
- `fake_game.py`: 리더 자체 시험용 가짜 게임 (같은 곳의 사본 + eudext 재생 모드 `--replay`)

둘 다 스크립트로 실행한다(`python eudext/tools/debugbridge/dbg_reader.py --once`). 자동 판정은 `eudext/tools/ingame_auto.py`.
"""
