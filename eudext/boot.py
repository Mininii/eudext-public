"""eudext 부트 플러그인 — euddraft eds 에서 경로로 지정한다 (DESIGN 2.3).

    [../../eudext/boot.py]
    EudextRoot : ../..
    VenvSite : /home/<사용자>/eudext/.tools/euddraft_site
    Preload : shape, i64
    PycachePrefix : /tmp/eudext_work/pycache

(Windows 예: `EudextRoot : C:\\Users\\whatd\\Documents\\eudext`, `VenvSite : C:\\Users\\whatd\\.venvs\\euddraft011_site`)

키(대소문자 무시):
- EudextRoot (필수): `eudext` 패키지가 들어 있는 폴더(= 이 저장소의 최상위). eds 폴더 기준 상대 경로도 된다.
  경로 구분자는 `\\`, `/` 둘 다 된다(Linux 에서는 `\\` 를 `/` 로 바꿔 읽는다).
  `sys.path` **앞**에 넣는다.
- VenvSite (선택): lupa 같은 외부 패키지 폴더. `sys.path` **끝**에 붙인다(번들 eudplib 이 먼저 잡혀야 한다). 폴더가 없으면 경고만 하고 넘어간다.
- Preload (선택): 부트 중에 미리 불러올 eudext 하위 모듈 이름(쉼표 구분). 외부 패키지(lupa)를 쓰는 모듈은
  반드시 여기 넣는다 — euddraft 는 플러그인 하나를 읽을 때마다 `sys.path` 를 되돌리므로 부트 뒤에는 VenvSite 가 빠진다.
- PycachePrefix (선택): `sys.pycache_prefix` 로 정한다(바이트코드 캐시를 저장소 밖으로).
- DbgDir (선택): `eudext.dbg` 심볼 JSON 을 쓸 폴더(환경 변수 `EUDEXT_DBG_DIR` 로 넘긴다). eds 폴더 기준 상대 경로도 된다.
- Dbg (선택): `0` 이면 `eudext.dbg` 를 코드와 상관없이 끈다(배포 빌드 — 환경 변수 `EUDEXT_DBG=0`). `1` 은 코드대로.

eds 줄에는 끝 주석을 달 수 없다(euddraft 는 `; …` 를 값의 일부로 읽는다). 이 파일은 방어로 값 끝의
`<공백>; …` 를 떼어 낸다. 주석 줄은 `::` 로 시작한다.

부트 뒤에는 어느 플러그인(.py, .eps)에서든 `import eudext.<모듈>` 이 된다(패키지 `__path__` 로 찾음).
EudextRoot 바로 밑의 비패키지 모듈은 부트 뒤에 불러올 수 없다.
"""

import importlib
import os
import re
import sys

_TRAIL_COMMENT = re.compile(r"\s+;.*$")


def _read_settings():
    raw = globals().get("settings")  # euddraft 가 넣어 준다
    out = {}
    if not raw:
        return out
    for k, v in raw.items():
        key = str(k).strip().lower()
        if key.startswith((";", "#", "::")):
            continue  # 주석처럼 쓴 줄 (euddraft 는 키로 읽는다)
        out[key] = _TRAIL_COMMENT.sub("", str(v)).strip()
    return out


def _split_names(text):
    return [x.strip() for x in re.split(r"[,;\s]+", text or "") if x.strip()]


def _fail(msg):
    raise RuntimeError("[eudext boot] " + msg)


def _native(p):
    return p.replace("\\", "/") if os.sep == "/" else p


def _boot(opts):
    root = opts.get("eudextroot")
    if not root:
        _fail("EudextRoot 설정이 없습니다. eds 의 [<경로>/eudext/boot.py] 아래에 'EudextRoot : <eudext 패키지의 부모 폴더>' 를 적으세요.")
    root = os.path.abspath(_native(root))
    if not os.path.isfile(os.path.join(root, "eudext", "__init__.py")):
        _fail("EudextRoot 에 eudext 패키지가 없습니다: %s" % root)

    prefix = opts.get("pycacheprefix")
    if prefix:
        prefix = os.path.abspath(_native(prefix))
        os.makedirs(prefix, exist_ok=True)
        sys.pycache_prefix = prefix

    dbg_dir = opts.get("dbgdir")
    if dbg_dir:
        os.environ["EUDEXT_DBG_DIR"] = os.path.abspath(_native(dbg_dir))
    if opts.get("dbg"):
        os.environ["EUDEXT_DBG"] = "0" if opts["dbg"].strip().lower() in ("0", "off", "false", "no") else "1"

    if root not in sys.path:
        sys.path.insert(0, root)
    venv = opts.get("venvsite")
    if venv:
        venv = os.path.abspath(_native(venv))
        if not os.path.isdir(venv):
            # 같은 eds 를 Windows·Linux 에서 함께 쓸 수 있게 경고만 한다(shape 는 lupa 폴더를 스스로도 찾는다, WP7)
            print("[eudext] 경고: VenvSite 폴더가 없어 건너뜁니다: %s" % venv)
            venv = None
        elif venv not in sys.path:
            sys.path.append(venv)

    old = sys.modules.get("eudext")
    if old is not None:
        old_dir = os.path.dirname(getattr(old, "__file__", "") or "")
        if os.path.normcase(old_dir) != os.path.normcase(os.path.join(root, "eudext")):
            _fail("다른 위치의 eudext 가 이미 올라와 있습니다: %s" % old_dir)

    import eudext
    import eudext._compat

    epver = eudext._compat.check()
    loaded = []
    for name in _split_names(opts.get("preload")):
        modname = name if name.startswith("eudext.") else "eudext." + name
        importlib.import_module(modname)
        loaded.append(modname[len("eudext."):])
    print(
        "[eudext] %s (eudplib %s) root=%s preload=%s venv=%s"
        % (eudext.__version__, epver, root, ",".join(loaded) or "-", "yes" if venv else "-")
    )
    return eudext


if __name__ != "__main__" and "settings" in globals():
    _boot(_read_settings())
