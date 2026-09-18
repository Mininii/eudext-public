"""eds 에서 디버그 브리지를 켜는 작은 플러그인 (DESIGN 4.21 — 인게임 확인 맵의 계측판).

eds 에서 부트 바로 뒤, 맵 플러그인 **앞**에 둔다:

    [../boot.py]
    EudextRoot : ../..

    [dbg_setup.py]
    :: MapName 을 비우면 eds 의 [main] output 파일 이름(확장자 뺌)이 자동 판정의 맵 이름이다
    WatchSlots : 128
    Probes : 256

    [sprite_ingame.eps]

설정(모두 선택, 대소문자 무시): `MapName`(자동 판정 명세의 "map"), `WatchSlots`·`Probes`(블록 용량), `Addr`("top"·"payload"·
16진 주소). 맵 코드(eps)는 모듈 전역·함수 안에서 `dbg.watch`·`dbg.mark` … 만 부른다 — 이 플러그인이 없는 빌드(시험의
에뮬레이터, 원래 eds)에서는 dbg 가 꺼져 있어 트리거를 만들지 않는다. 부트 `Dbg : 0` 이면 이 플러그인이 있어도 꺼진다.

플러그인 모듈 본문이 실행될 때(euddraft 가 맵을 읽고 플러그인을 차례로 불러올 때) `dbg.setup` 을 부르므로, 뒤에 오는
플러그인의 모듈 전역 `dbg.watch` 도 이 설정에 들어간다(DESIGN 4.21 "빌드 밖 설정·등록은 계속 남는다").
"""

from eudext import dbg

_raw = globals().get("settings") or {}
_opts = {str(k).strip().lower(): str(v).strip() for k, v in _raw.items() if not str(k).strip().startswith("::")}


def _int(key, default):
    v = _opts.get(key)
    return int(v, 0) if v else default


def _addr():
    v = _opts.get("addr", "top")
    return v if v.lower() in ("top", "payload") else int(v, 0)


bridge = dbg.setup(map_name=_opts.get("mapname") or None, addr=_addr(),
                   watch_slots=_int("watchslots", dbg.DEFAULT_WATCH_SLOTS), probes=_int("probes", dbg.DEFAULT_PROBES))
