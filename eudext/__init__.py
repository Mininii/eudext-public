"""eudext — 새 맵 코드용 eudplib 확장 라이브러리 (설계: DESIGN.md).

기준 판은 euddraft 0.11.0.1 / eudplib 0.81.0 이다(DESIGN 2.1).
이 파일은 가볍게 둔다: 하위 모듈은 쓰는 쪽이 `import eudext.<모듈>` 로 불러온다.
판 검사는 `eudext._compat.check()` 가 한다(부트 플러그인 `boot.py` 가 부른다).

euddraft 에서 쓰는 법 (eds, 다른 eudext 사용 플러그인보다 앞에):

    [..\\..\\MapSource\\Py\\eudext\\boot.py]
    EudextRoot : C:\\...\\MapSource\\Py

파이썬 단독 빌드·시험에서는 `sys.path` 에 `MapSource\\Py` 를 넣고 `import eudext` 한다.
"""

__version__ = "0.0.1"

# 판 번호를 튜플로도 준다 (비교용).
VERSION = tuple(int(x) for x in __version__.split("."))

__all__ = ["VERSION", "__version__"]
