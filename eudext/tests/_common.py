"""시험 공용: 경로 설정, 산출물 위치, 간단한 판정기. 시험 파일 맨 위에서 `import _common` 한다.

- eudext 패키지의 부모 폴더(저장소 최상위)를 sys.path 앞에 넣어 `import eudext` 가 되게 한다.
- 바이트코드 캐시와 임시 파일(SaveMap 출력)을 저장소 밖(EUDEXT_WORK 또는 <임시 폴더>/eudext_work)으로 보낸다.
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)  # 저장소 최상위 (eudext 의 부모)

WORK = os.environ.get("EUDEXT_WORK") or os.path.join(tempfile.gettempdir(), "eudext_work")
os.makedirs(WORK, exist_ok=True)
if not sys.pycache_prefix:
    sys.pycache_prefix = os.path.join(WORK, "pycache")
tempfile.tempdir = os.path.join(WORK, "tmp")
os.makedirs(tempfile.tempdir, exist_ok=True)

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


class Checker:
    """파이썬 쪽 판정 모음 (에뮬레이터 밖 시험용)."""

    def __init__(self, name):
        self.name = name
        self.ok = 0
        self.fail = 0

    def eq(self, label, got, want):
        if got == want:
            self.ok += 1
            return True
        self.fail += 1
        print("  [실패] %s: %r (기대 %r)" % (label, got, want))
        return False

    def true(self, label, cond, msg=""):
        if cond:
            self.ok += 1
            return True
        self.fail += 1
        print("  [실패] %s %s" % (label, msg))
        return False

    def raises(self, label, exc_type, fn, *args, **kw):
        try:
            fn(*args, **kw)
        except exc_type:
            self.ok += 1
            return True
        except Exception as e:  # noqa: BLE001
            self.fail += 1
            print("  [실패] %s: %s 대신 %r" % (label, exc_type.__name__, e))
            return False
        self.fail += 1
        print("  [실패] %s: 예외가 나지 않음" % label)
        return False

    def report(self):
        print("[%s] 통과 %d, 실패 %d" % (self.name, self.ok, self.fail))
        return self.fail == 0


def finish(*oks):
    """모두 True 면 종료 코드 0. run_all.py 가 마지막 줄 'RESULT ...' 를 읽는다."""
    ok = all(oks)
    print("RESULT %s" % ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
