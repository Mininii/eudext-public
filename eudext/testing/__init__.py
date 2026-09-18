"""eudext 개발용 시험 도구 (DESIGN 5.1). 개발 venv 전용 — 맵 빌드에서 불러오지 않는다.

- `emu`: 트리거 에뮬레이터 (DPS_eud 에서 옮김)
- `scmodel`: SC 조건·액션·게임 메모리 모델 확장
- `harness`: 여러 케이스를 한 빌드로 도는 차등 시험 틀
- `base.scx`: 작은 기준 맵 (C:\\euddraft0.9.2.0\\CBTest.scx 사본)
"""

import os

BASE_MAP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "base.scx")

__all__ = ["BASE_MAP"]
