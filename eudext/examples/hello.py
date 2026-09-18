"""eudext 예제 (파이썬 플러그인): 부트 플러그인 뒤에서 `import eudext.<하위 모듈>` 을 한다.

hello.eds 에서 boot.py 다음에 놓인다. boot.py 는 `eudext` 와 `eudext._compat` 만 불러오므로
여기서 불러오는 `eudext.errors` 는 부트 **뒤에** 처음 불러오는 하위 모듈이다(sys.path 가 되돌려진 뒤).
"""

import os
import sys

from eudplib import DisplayText, DoActions, EUDEndIf, EUDIf, EUDVariable

import eudext
import eudext.errors as er  # 부트 뒤 첫 import

ROOT_ON_PATH = any(os.path.isfile(os.path.join(p, "eudext", "__init__.py")) for p in sys.path if isinstance(p, str))
print(
    "[hello.py] eudext %s, %s 불러옴, EudextRoot 가 sys.path 에 %s, __file__ %s"
    % (eudext.__version__, er.__name__, "있음" if ROOT_ON_PATH else "없음", "있음" if "__file__" in globals() else "없음")
)

frames = EUDVariable()


def onPluginStart():
    import eudext._parts  # noqa: F401  빌드 중(onPluginStart) 지연 import 도 된다

    print("[hello.py] onPluginStart: eudext._parts 불러옴")


def beforeTriggerExec():
    er.require(frames is not None, "예제 변수가 없습니다")
    frames.__iadd__(1)
    if EUDIf()(frames.Exactly(24)):
        DoActions(DisplayText("\x04eudext hello (py)"))
    EUDEndIf()
