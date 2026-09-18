"""Lua 파일을 lupa 로 실행해 전역 상수·함수 결과를 파이썬 값으로 가져온다 (DESIGN 5.4, 4.18 (a)).

단일 출처 원칙: CtrigAsm/TEP 라이브러리(`SCR_DB_Core.lua`, `CB Paint v2.5.lua` …)에 있는 약속 값을
파이썬에 다시 적지 않고 **빌드 때** 원본 Lua 를 실행해 읽는다.

    from eudext.tools import lua_consts as lc
    lua = lc.Lua()                                   # 새 Lua 5.4 실행기 (lupa, 문자열은 바이트 그대로)
    lua.run_file("SCR_DB_Core.lua")
    lua.get("SCRDB_I")                                # {'Version': 8, ...}  (표 → dict/list 로 바꿔 준다)
    lua.call("SCRDB_FieldHash", [{"id": "a", "mode": "arr", "index": 0}])
    core = lc.scrdb_core()                            # SCR_DB 약속 값 묶음 (ScrdbCore, 파일마다 캐시)

**재사용할 적재 부품** (다음 배치의 `shape.CX` 가 `CB Paint v2.5.lua` 를 읽을 때 같이 쓴다):
`Lua`(실행기·변환), `load(path, stubs=…)`, `read_globals(path, names)`, `find_lua_file(name, …)`,
`CtrigTrace`(CtrigAsm 트리거 함수 스텁 — 컴파일 시점 호출을 트리로 기록), `file_info(path)`,
`lua_c_locale()`(Lua 를 부르는 동안 C 런타임 `LC_CTYPE` 을 "C" 로 — lupa 로 Lua 를 부르는 곳은 **모두** 이것으로 감싼다).

**로캘 (Windows)**: Windows 표준 파이썬(개발 venv `python.exe`)은 시작할 때 `LC_CTYPE` 을 사용자 로캘
(예: `Korean_Korea.949`)로 잡고, lupa 의 Lua 는 같은 ucrt 를 쓴다. 그러면 Lua 문자 분류(`%c`·`%a` 등 패턴,
`string.upper`, `%q`)가 로캘을 따라 달라진다 — 949 에서는 바이트 0x80 이 제어문자로 분류되어 `SCRDB_Json` 이
`"글"`(EA B8 80)을 `\\u0080` 으로 바꾼다. 원본 TEP 는 정적 CRT(/MT)로 빌드되어 플러그인 CRT 로캘이 "C" 로
시작하고 `setlocale` 을 부르지 않으므로 0x80 을 그대로 둔다. `lua_c_locale()` 이 그 결과에 맞춘다.
euddraft 0.11 번들 파이썬(3.14.7)은 플러그인 단계에서 `LC_ALL=C` 라 원래 해당이 없다(2026-09-17 확인) — 가드는
개발 venv 안의 빌드(`tools/build.py standalone`)·시험·명령줄을 위한 것이고, euddraft 안에서는 아무것도 바꾸지 않는다.

**euddraft 안에서** (DESIGN 2.3): lupa 는 부트 플러그인이 `VenvSite` 를 `sys.path` 에 붙인 **부트 중에만**
import 할 수 있다. 이 모듈은 import 되는 순간 lupa 를 불러오므로 eds 부트 섹션에
`VenvSite : <euddraft 용 lupa 폴더>` 와 `Preload : scrdb`(scrdb 가 이 모듈을 불러온다) 또는 `Preload : tools.lua_consts`
를 넣는다. 부트 뒤에 처음 불러오면 lupa 가 없다고 `LuaConstsError` 를 낸다(`lupa_error()` 에 원인).
`tools/edsgen.EdsDoc.add_scrdb()` 가 Preload·VenvSite 를 확인한다.

**SCR_DB 코어 파일 찾기** (`find_scrdb_core`) — 앞에서부터 처음 있는 것:
1. 인자로 준 경로(파일 또는 폴더). `scrdb.setup(core=…)`, eds 훅 설정 `Core : …`
2. 환경 변수 `EUDEXT_SCRDB_CORE`(파일 또는 폴더) — 주면 이것만 본다(없으면 오류)
3. 저장소 옆 `MapSource/Library` (`<eudext 저장소>/../MapSource/Library`, 이 Ubuntu 머신은 `/home/developer/MapSource/Library`)
4. `~/MapSource/Library`
5. (Windows) `%USERPROFILE%\\Desktop\\Stormcoast Fortress\\ScmDraft 2\\MapSource\\Library`
6. 저장소 사본 `reference/MapSource/Library` — 옛 사본일 수 있다(이때는 경고). 2026-09-17 확인: MapSource `b57b6fe`(레이아웃 7) 와 같다.
어느 파일을 썼는지는 `ScrdbCore.path`·`sha256` 과 빌드 로그 한 줄(`[eudext.scrdb] Lua 코어 …`)로 알 수 있다.

명령줄:
    python eudext/tools/lua_consts.py scrdb [--core 경로] [--json]      # SCR_DB 약속 값·헤더 계획·알림음
    python eudext/tools/lua_consts.py get <lua 파일> <전역 이름> ...     # 전역 값을 JSON 으로

비공개 eudplib API 는 쓰지 않는다. 표준 모듈만 쓴다(번들 파이썬 3.14 에 있는 것).
"""

import contextlib
import hashlib
import json
import locale
import os
import sys
import tempfile
import threading

if __name__ == "__main__":  # 명령줄로 직접 실행할 때 저장소 최상위를 경로에 넣는다
    sys.dont_write_bytecode = True
    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _root not in sys.path:
        sys.path.insert(0, _root)

from eudext.errors import EudextError, warn  # noqa: E402

try:  # euddraft 안에서는 부트 중(VenvSite 가 경로에 있을 때)에만 성공한다 — 모듈 docstring
    import lupa.lua54 as _lua
except Exception as _e:  # noqa: BLE001
    _lua = None
    _LUPA_ERROR = "%s: %s" % (type(_e).__name__, _e)
else:
    _LUPA_ERROR = None

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)

SCRDB_CORE_ENV = "EUDEXT_SCRDB_CORE"
SCRDB_CORE_NAME = "SCR_DB_Core.lua"
REFERENCE_LIBRARY = os.path.join(ROOT, "reference", "MapSource", "Library")

__all__ = [
    "CtrigTrace",
    "Lua",
    "LuaConstsError",
    "LuaStubError",
    "Node",
    "REFERENCE_LIBRARY",
    "Ref",
    "SCRDB_CORE_ENV",
    "SCRDB_CORE_NAME",
    "ScrdbCore",
    "Term",
    "file_info",
    "find_lua_file",
    "find_scrdb_core",
    "load",
    "lua_c_locale",
    "lupa_available",
    "lupa_error",
    "read_globals",
    "require_lupa",
    "scrdb_core",
    "scrdb_core_candidates",
    "trace_digest",
]


class LuaConstsError(EudextError):
    """Lua 파일을 읽거나 실행하지 못했다(lupa 없음, 파일 없음, Lua 오류)."""


class LuaStubError(LuaConstsError):
    """Lua 코드가 `PushErrorMsg`(TEP 컴파일 오류)로 멈췄다. 메시지는 Lua 가 준 그대로."""


# ---------------------------------------------------------------------------------------------
# lupa
# ---------------------------------------------------------------------------------------------


def lupa_available():
    """lupa(Lua 5.4)를 쓸 수 있는가.

    인자: 없음
    반환: bool
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    return _lua is not None


def lupa_error():
    """lupa 를 불러오지 못한 이유(문자열) 또는 None."""
    return _LUPA_ERROR


def require_lupa():
    """lupa 가 없으면 안내와 함께 `LuaConstsError` 를 낸다."""
    if _lua is None:
        raise LuaConstsError(
            "lupa 를 불러오지 못했습니다 (%s). euddraft 빌드라면 eds 부트 섹션에 'VenvSite : <euddraft 용 lupa 폴더>' 와 "
            "'Preload : scrdb' 를 넣으세요(lupa 는 부트 중에만 불러올 수 있다, DESIGN 2.3). 개발 venv 라면 'pip install lupa'."
            % _LUPA_ERROR
        )


def _lua_type(obj):
    return _lua.lua_type(obj) if _lua is not None else None


# ---------------------------------------------------------------------------------------------
# C 로캘 가드 (모듈 docstring "로캘")
# ---------------------------------------------------------------------------------------------

_locale_lock = threading.Lock()
_locale_depth = 0  # 지금 열려 있는 lua_c_locale 구간 수(재진입·스레드 합계)
_locale_saved = None  # 구간에 들어갈 때 바꿔 둔 원래 LC_CTYPE (바꾸지 않았으면 None)


def _ctype_matches_c(name):
    """이 LC_CTYPE 에서 Lua 문자 분류가 "C" 와 같은가: C/POSIX, 또는 UTF-8 로캘(바이트 0x80~0xFF 를 분류하지 않음 —
    Windows ucrt `.UTF-8`·glibc 모두)."""
    n = (name or "").lower()
    return n in ("c", "posix") or "utf-8" in n or "utf8" in n


@contextlib.contextmanager
def lua_c_locale():
    """이 `with` 구간 동안 C 런타임 `LC_CTYPE` 을 "C" 로 둔다(나갈 때 되돌림). lupa 로 Lua 코드를 부르는 곳은 모두 감싼다.

    Lua 의 문자 분류(`%c`·`%a`… 패턴, `string.upper/lower`, `string.format("%q")`, `tonumber(s, base)`)는 C `ctype`
    함수라 프로세스 로캘을 따른다. 원본 TEP(정적 CRT, "C")와 같은 결과를 내려고 구간 동안만 "C" 로 바꾼다.
    - 지금 로캘이 이미 "C"/"POSIX"/UTF-8 이면 아무것도 바꾸지 않는다(Linux·UTF-8 Windows 는 동작 그대로).
    - 재진입(Lua → 파이썬 콜백 → 다시 Lua)·여러 스레드: 열린 구간 수를 세어 마지막 구간이 닫힐 때 한 번만 되돌린다.
      구간이 열려 있는 동안은 프로세스 전체가 "C" 다(ucrt·glibc 의 `setlocale` 은 프로세스 전역).
    - 예외(Lua 오류, 콜백이 낸 파이썬 예외)로 빠져나가도 되돌린다. 원래 이름으로 되돌리지 못하면 사용자 기본 로캘("")로.
    - LC_NUMERIC 등 다른 범주는 건드리지 않는다(표준 파이썬은 시작할 때 LC_CTYPE 만 바꾼다 — 개발 venv 에서 eudplib
      import·epScript 컴파일 뒤에도 나머지는 "C", euddraft 0.11 번들은 플러그인 단계에서 전부 "C" 임을 확인했다, 2026-09-17 Windows).
    인자: 없음
    반환: 컨텍스트 관리자
    비용: 없음(컴파일 시점). 로캘을 바꿀 때 구간마다 `setlocale` 두 번
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성 (2026-09-17 Windows 실측 — 949 에서 `string.char(128):find("%c")` 가 참, "C" 에서 거짓.
          TEP3.0 `TrigEditPlus.vcxproj` Release RuntimeLibrary=MultiThreaded, TEP 소스에 `setlocale` 호출 없음)
    """
    global _locale_depth, _locale_saved
    with _locale_lock:
        if _locale_depth == 0:
            cur = locale.setlocale(locale.LC_CTYPE)
            if not _ctype_matches_c(cur):
                locale.setlocale(locale.LC_CTYPE, "C")
                _locale_saved = cur
        _locale_depth += 1
    try:
        yield
    finally:
        with _locale_lock:
            _locale_depth -= 1
            if _locale_depth == 0 and _locale_saved is not None:
                saved, _locale_saved = _locale_saved, None
                try:
                    locale.setlocale(locale.LC_CTYPE, saved)
                except locale.Error:
                    locale.setlocale(locale.LC_CTYPE, "")


def _enc(s):
    if isinstance(s, str):
        return s.encode("utf-8")
    return s


def file_info(path):
    """(절대 경로, sha256 16진, 크기, 수정 시각 ns) — 캐시 열쇠와 빌드 로그에 쓴다."""
    path = os.path.abspath(path)
    with open(path, "rb") as f:
        data = f.read()
    st = os.stat(path)
    return path, hashlib.sha256(data).hexdigest(), len(data), st.st_mtime_ns


class Lua:
    """lupa Lua 5.4 실행기 하나(전역 공간 하나). 문자열은 **바이트 그대로** 주고받는다(`encoding=None`).

    인자: stubs({이름: 파이썬 함수 또는 값} — 실행 전에 전역으로 넣는다),
          os_time(정수 — `os.time()` 이 늘 이 값을 돌려주게), os_date(문자열 — `os.date(…)` 가 늘 이 값)
    - `run_file(path)`, `run(code)`: Lua 코드 실행. Lua 오류는 `LuaConstsError`(메시지 해독), 스텁이 낸 파이썬 예외는 그대로.
      Lua 를 부르는 메서드(`run`·`run_file`·`call`·`has`·`set_os`)는 `lua_c_locale()` 안에서 부른다. `rt` 로 직접 부를 때는 직접 감싼다.
    - `get(name, raw=False)`: 전역 값을 파이썬 값으로(`to_py`). `has(name)`: rawget 결과가 nil 이 아닌가.
    - `set(name, value)`: 파이썬 값을 Lua 값으로(`to_lua`) 넣는다.
    - `call(name, *args, raw=False)`: 전역 함수를 부르고 결과를 `to_py` 로. 여러 값이면 튜플.
    - `to_lua(obj)`: str → 바이트 문자열, dict → 표(키도 변환, 값이 None 인 칸은 뺀다), list/tuple → 1부터 배열 표.
      그 밖(int·float·bool·None·파이썬 객체)은 그대로.
    - `to_py(obj, raw=False)`: 표 → 키가 1..n 이면 list, 비었으면 [], 아니면 dict. 바이트 문자열 → str(UTF-8,
      `surrogateescape`) — `raw=True` 면 bytes 그대로.
    - `rt`: lupa LuaRuntime, `g`: 전역 표.
    비용: 없음(컴파일 시점). 실행기 하나 만드는 데 약 1ms.
    출처: 새로 작성 (R4b B3 lupa 실험, docs/proto)
    """

    def __init__(self, stubs=None, os_time=None, os_date=None):
        require_lupa()
        self.rt = _lua.LuaRuntime(unpack_returned_tuples=True, encoding=None)
        self.g = self.rt.globals()
        self.files = []
        if stubs:
            self.install(stubs)
        if os_time is not None or os_date is not None:
            self.set_os(os_time, os_date)

    # --- 변환 ---
    def to_lua(self, obj):
        if isinstance(obj, str):
            return obj.encode("utf-8")
        if isinstance(obj, dict):
            t = self.rt.table()
            for k, v in obj.items():
                if v is None:
                    continue
                t[self.to_lua(k)] = self.to_lua(v)
            return t
        if isinstance(obj, (list, tuple)):
            t = self.rt.table()
            for i, v in enumerate(obj, 1):
                t[i] = self.to_lua(v)
            return t
        return obj

    def to_py(self, obj, raw=False):
        if isinstance(obj, bytes):
            return obj if raw else obj.decode("utf-8", "surrogateescape")
        if _lua_type(obj) == "table":
            keys = list(obj.keys())
            n = len(keys)
            if n == 0:
                return []
            if all(isinstance(k, int) and not isinstance(k, bool) for k in keys) and set(keys) == set(range(1, n + 1)):
                return [self.to_py(obj[i], raw) for i in range(1, n + 1)]
            return {self.to_py(k, raw): self.to_py(v, raw) for k, v in obj.items()}
        return obj

    # --- 실행 ---
    def _wrap(self, fn, *args, **kw):
        try:
            with lua_c_locale():  # Lua 코드는 늘 "C" 문자 분류로 (모듈 docstring "로캘")
                return fn(*args, **kw)
        except _lua.LuaError as e:
            msg = e.args[0] if e.args else ""
            if isinstance(msg, str):  # encoding=None 이면 lupa 가 바이트를 latin-1 로 풀어 준다
                try:
                    msg = msg.encode("latin-1")
                except UnicodeEncodeError:
                    pass
            if isinstance(msg, bytes):
                msg = msg.decode("utf-8", "replace")
            raise LuaConstsError("Lua 오류: %s" % msg) from e

    def install(self, stubs):
        for name, value in stubs.items():
            self.g[_enc(name)] = self.to_lua(value) if isinstance(value, (str, dict, list, tuple)) else value
        return self

    def set_os(self, time=None, date=None):
        """`os.time()`/`os.date()` 을 고정값으로 바꾼다(재현 가능한 빌드 ID·생성 시각)."""
        setter = self.rt.eval(
            b"function(t, d) if t ~= nil then os.time = function() return t end end "
            b"if d ~= nil then os.date = function() return d end end end"
        )
        self._wrap(setter, time, _enc(date))

    def run(self, code, name=None):
        return self._wrap(self.rt.execute, _enc(code), name=_enc(name) if name else None)

    def run_file(self, path):
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            raise LuaConstsError("Lua 파일이 없습니다: %s" % path)
        with open(path, "rb") as f:
            code = f.read()
        if code.startswith(b"\xef\xbb\xbf"):
            code = code[3:]
        self._wrap(self.rt.execute, code, name=("@" + os.path.basename(path)).encode("utf-8"))
        self.files.append(path)
        return self

    def has(self, name):
        return self._wrap(self.rt.eval(b"function(k) return rawget(_G, k) ~= nil end"), _enc(name))

    def raw(self, name):
        return self.g[_enc(name)]

    def get(self, name, raw=False):
        return self.to_py(self.g[_enc(name)], raw)

    def set(self, name, value):
        self.g[_enc(name)] = self.to_lua(value)

    def call(self, name, *args, raw=False):
        fn = self.g[_enc(name)]
        if fn is None:
            raise LuaConstsError("Lua 전역 함수 %s 가 없습니다" % name)
        res = self._wrap(fn, *[self.to_lua(a) for a in args])
        if isinstance(res, tuple):
            return tuple(self.to_py(r, raw) for r in res)
        return self.to_py(res, raw)


def load(path, stubs=None, os_time=None, os_date=None):
    """새 `Lua` 에 stubs 를 넣고 파일을 실행해 돌려준다.

    인자: path, stubs(dict, 선택), os_time/os_date(선택 — `Lua` 와 같음)
    반환: Lua
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성 (다음 배치 shape.CX 가 CB Paint 를 읽을 때 같이 쓴다)
    """
    lua = Lua(stubs=stubs, os_time=os_time, os_date=os_date)
    lua.run_file(path)
    return lua


def read_globals(path, names=None, stubs=None):
    """파일을 실행하고 전역 값을 {이름: 파이썬 값} 으로 돌려준다. names 가 없으면 실행으로 새로 생긴 전역 전부
    (함수는 뺀다).

    인자: path, names(이름 목록, 선택), stubs(dict, 선택)
    반환: dict
    비용: 없음(컴파일 시점)
    출처: 새로 작성
    """
    lua = Lua(stubs=stubs)
    before = set(lua.g.keys())
    lua.run_file(path)
    if names is None:
        names = []
        for k in lua.g.keys():
            if k in before or not isinstance(k, bytes):
                continue
            if _lua_type(lua.g[k]) == "function":
                continue
            names.append(k.decode("utf-8", "surrogateescape"))
        names.sort()
    return {n: lua.get(n) for n in names}


def find_lua_file(name, candidates, env=None):
    """이름이 name 인 Lua 파일을 찾는다.

    인자: name(파일 이름), candidates(폴더 또는 파일 경로 목록 — 앞에서부터), env(환경 변수 이름 — 값이 있으면 그것만 본다)
    반환: (절대 경로, 찾은 자리 설명)
    비용: 없음(컴파일 시점)
    출처: 새로 작성
    """
    if env and os.environ.get(env):
        p = os.environ[env]
        f = p if os.path.isfile(p) else os.path.join(p, name)
        if not os.path.isfile(f):
            raise LuaConstsError("환경 변수 %s=%s 에 %s 가 없습니다" % (env, p, name))
        return os.path.abspath(f), "환경 변수 %s" % env
    tried = []
    for c in candidates:
        if not c:
            continue
        f = c if (c.lower().endswith(".lua") or os.path.isfile(c)) else os.path.join(c, name)
        tried.append(f)
        if os.path.isfile(f):
            return os.path.abspath(f), c
    raise LuaConstsError("%s 를 찾지 못했습니다. 찾아본 곳:\n  %s" % (name, "\n  ".join(tried)))


# ---------------------------------------------------------------------------------------------
# CtrigAsm 트리거 함수 스텁 (컴파일 시점 호출 기록)
# ---------------------------------------------------------------------------------------------

# TEP 상수 값 (eudplib constenc 와 같은 번호). 스텁은 모양만 기록하므로 값의 뜻은 쓰지 않는다.
TEP_CONSTS = {
    "AtLeast": 0,
    "AtMost": 1,
    "Exactly": 10,
    "SetTo": 7,
    "Add": 8,
    "Subtract": 9,
    "Set": 2,
    "Cleared": 3,
}
FP_VALUE = 7  # CtrigAsm 관례: 트리거 주인 = P8
_OBSERVERS = {b"Ob1": 128, b"Ob2": 129, b"Ob3": 130, b"Ob4": 131}


class Term:
    """기록한 조건·액션·식 하나: `op`(이름 문자열)와 `args`(튜플)."""

    __slots__ = ("args", "op")

    def __init__(self, op, *args):
        self.op = op
        self.args = args

    def __repr__(self):
        return "%s(%s)" % (self.op, ", ".join(repr(a) for a in self.args))

    def __eq__(self, other):
        return isinstance(other, Term) and self.op == other.op and self.args == other.args

    def __hash__(self):
        return hash(self.op)


class Ref:
    """CtrigAsm 저장 칸(Ccode 또는 변수) — 번호는 만든 순서."""

    __slots__ = ("kind", "n")

    def __init__(self, kind, n):
        self.kind = kind
        self.n = n

    def __repr__(self):
        return "%s%d" % (self.kind, self.n)


class Node:
    """기록한 트리거 구조 하나.

    kind: "if"(CIf, 보존) | "once"(CIfOnce) | "trig"(TriggerX/DoActions…) | "read"(f_Read) | "mov"(CMov) |
          "add"(CAdd) | "call"(파이썬 콜백 — 예: SCRDB_Receiver 의 Write)
    conds/acts: Term 목록, body: 블록 안 Node 목록(if/once), preserved: trig 의 보존 여부, args: read/mov/add/call 인자
    """

    __slots__ = ("acts", "args", "body", "conds", "kind", "preserved")

    def __init__(self, kind, conds=(), acts=(), body=None, preserved=True, args=()):
        self.kind = kind
        self.conds = list(conds)
        self.acts = list(acts)
        self.body = body
        self.preserved = preserved
        self.args = args

    def __repr__(self):
        head = "%s%s" % (self.kind, "" if self.preserved else "*")
        parts = []
        if self.conds:
            parts.append("if %r" % self.conds)
        if self.acts:
            parts.append("do %r" % self.acts)
        if self.args:
            parts.append("args %r" % (self.args,))
        if self.body is not None:
            parts.append("body[%d]" % len(self.body))
        return "<%s %s>" % (head, " ".join(parts))

    def walk(self):
        yield self
        for n in self.body or ():
            yield from n.walk()


class CtrigTrace:
    """CtrigAsm 트리거 함수 스텁을 `Lua` 에 넣고, 불린 순서대로 트리(`Node`)를 기록한다.

    넣는 이름: FP, AtLeast/AtMost/Exactly, SetTo/Add/Subtract, Set/Cleared, preserved/Preserved,
    CIf/CIfOnce/CIfEnd, TriggerX, DoActions/DoActions2/DoActionsX/DoActions2X, SetMemory/Memory, Deaths/DeathsX,
    SetDeaths/SetDeathsX, CD/SetCD/CV, LocalPlayerID, SetCp, PlayWAV, Switch, CreateCcode/CreateCcodeArr,
    CreateVar/CreateVars, DtoA, _Mul, f_Read, CMov, CAdd, PushErrorMsg(→ `LuaStubError`).
    모르는 함수를 부르면 Lua 오류로 멈춘다(원본 라이브러리가 바뀐 것을 알아채게).
    - `root`: 최상위 Node 목록. `take()`: root 를 돌려주고 비운다. `callback(name)`: 불리면 "call" Node 를 남기는 파이썬 함수.
    - 인자 모양은 CtrigAsm v5.5 와 같다(`MapSource/Library/CtrigAsm v5.5.lua` DoActions:6882, TriggerX:7035,
      CIfOnce:10397, CIf:10444, f_Read:36149, CMov:20936, CAdd:21587, LocalPlayerID:43393, CreateCcode:75959,
      `LibraryFor322.lua` SetCD:606, CV:690, CD:740). DoActions* 는 플래그가 없으면 보존, TriggerX 는 플래그 표에
      preserved 가 있을 때만 보존, CIfOnce 는 1회, CIf 는 보존.
    비용: 없음(컴파일 시점)
    출처: 새로 작성 (SCR_DB 헤더·알림음 계획 추출, 시험의 Lua 수신기 모델)
    """

    PRESERVED = Term("flag", "preserved")

    def __init__(self, lua):
        self.lua = lua
        self.root = []
        self.stack = [self.root]
        self.counts = {"ccode": 0, "var": 0}
        g = {
            "FP": FP_VALUE,
            "preserved": self.PRESERVED,
            "Preserved": self.PRESERVED,
            "PushErrorMsg": self._error,
            "CIf": self._cif,
            "CIfOnce": self._cifonce,
            "CIfEnd": self._cifend,
            "TriggerX": self._triggerx,
            "DoActions": self._doactions,
            "DoActions2": self._doactions2,
            "DoActionsX": self._doactionsx,
            "DoActions2X": self._doactions2,
            "SetMemory": lambda a, m, v: Term("SetMemory", a, m, v),
            "Memory": lambda a, c, v: Term("Memory", a, c, v),
            "Deaths": lambda p, c, v, u: Term("DeathsX", p, c, v, u, 0xFFFFFFFF),
            "DeathsX": lambda p, c, v, u, m: Term("DeathsX", p, c, v, u, m),
            "SetDeaths": lambda p, m, v, u: Term("SetDeathsX", p, m, v, u, 0xFFFFFFFF),
            "SetDeathsX": lambda p, m, v, u, k: Term("SetDeathsX", p, m, v, u, k),
            "CD": self._cd,
            "SetCD": self._setcd,
            "CV": self._cv,
            "LocalPlayerID": self._localplayer,
            "SetCp": lambda p: Term("SetCp", p),
            "PlayWAV": lambda s: Term("PlayWAV", s.decode("utf-8", "surrogateescape") if isinstance(s, bytes) else s),
            "Switch": lambda sw, st: Term("Switch", sw, st),
            "CreateCcode": lambda: self._ref("ccode"),
            "CreateCcodeArr": self._ccodearr,
            "CreateVar": lambda p=None: self._ref("var"),
            "CreateVars": self._vars,
            "DtoA": self._dtoa,
            "_Mul": lambda a, b: Term("Mul", a, b),
            "f_Read": self._fread,
            "CMov": self._cmov,
            "CAdd": self._cadd,
        }
        g.update(TEP_CONSTS)
        for k, v in g.items():
            lua.g[k.encode()] = v

    # --- 기록 ---
    def take(self):
        root = self.root
        self.root = []
        self.stack = [self.root]
        return root

    def _emit(self, node):
        self.stack[-1].append(node)
        return node

    def _flat(self, x):
        if x is None:
            return []
        if _lua_type(x) == "table":
            out = []
            for k in sorted(k for k in x.keys() if isinstance(k, int)):
                out.extend(self._flat(x[k]))
            return out
        return [x]

    def _preserved(self, flags, default):
        if flags is None:
            return default
        return any(f == self.PRESERVED for f in self._flat(flags))

    def _ref(self, kind):
        self.counts[kind] += 1
        return Ref(kind, self.counts[kind])

    def callback(self, name):
        def fn(*args):
            self._emit(Node("call", args=(name,) + tuple(args)))

        return fn

    # --- 스텁 ---
    @staticmethod
    def _error(msg):
        if isinstance(msg, bytes):
            msg = msg.decode("utf-8", "replace")
        raise LuaStubError(str(msg))

    def _block(self, kind, conds, acts):
        node = self._emit(Node(kind, self._flat(conds), self._flat(acts), body=[], preserved=(kind == "if")))
        self.stack.append(node.body)

    def _cif(self, player, conds=None, acts=None, unpack=None):
        self._block("if", conds, acts)

    def _cifonce(self, player, conds=None, acts=None, unpack=None):
        self._block("once", conds, acts)

    def _cifend(self, acts=None, unpack=None):
        if self._flat(acts):
            raise LuaConstsError("CtrigTrace: CIfEnd(Actions) 는 흉내 내지 않습니다")
        if len(self.stack) <= 1:
            raise LuaConstsError("CtrigTrace: 짝이 없는 CIfEnd")
        self.stack.pop()

    def _triggerx(self, player, conds=None, acts=None, flags=None, index=None):
        self._emit(Node("trig", self._flat(conds), self._flat(acts), preserved=self._preserved(flags, False)))

    def _doactions(self, player, acts=None, flags=None):
        self._emit(Node("trig", (), self._flat(acts), preserved=self._preserved(flags, True)))

    def _doactionsx(self, player, acts=None, flags=None, index=None):
        self._doactions(player, acts, flags)

    def _doactions2(self, player, acts=None, flags=None):
        acts = self._flat(acts)
        keep = self._preserved(flags, True)
        for i in range(0, len(acts), 64):
            self._emit(Node("trig", (), acts[i : i + 64], preserved=keep))

    def _cd(self, code, value=None, cmp=None):
        return Term("CD", code, 1 if value is None else value, TEP_CONSTS["Exactly"] if cmp is None else cmp)

    def _setcd(self, code, value=None):
        return Term("SetCD", code, 1 if value is None else value)

    def _cv(self, var, value=None, cmp=None):
        return Term("CV", var, 1 if value is None else value, TEP_CONSTS["Exactly"] if cmp is None else cmp)

    def _localplayer(self, player, cmp=None):
        player = _OBSERVERS.get(player, player)
        return Term("Memory", 0x512684, TEP_CONSTS["Exactly"] if cmp is None else cmp, player)

    def _ccodearr(self, n):
        return self.lua.to_lua([self._ref("ccode") for _ in range(int(n))])

    def _vars(self, n, player=None):
        return tuple(self._ref("var") for _ in range(int(n)))

    @staticmethod
    def _dtoa(player, unit):
        if not isinstance(player, int) or not isinstance(unit, int):
            raise LuaConstsError("CtrigTrace: DtoA 는 숫자 플레이어·유닛만 받습니다 (%r, %r)" % (player, unit))
        return 0x58A364 + 0x30 * unit + 4 * player

    def _fread(self, player, src, out=None, epdout=None, mask=None, clear=None):
        if not isinstance(src, int):
            raise LuaConstsError("CtrigTrace: f_Read 입력은 주소 숫자만 흉내 냅니다 (%r)" % (src,))
        if epdout is not None:
            raise LuaConstsError("CtrigTrace: f_Read 의 EPD 출력은 흉내 내지 않습니다")
        self._emit(Node("read", args=(src, out, 0xFFFFFFFF if mask is None else mask, clear)))

    def _cmov(self, player, dest, src, dev=None, mask=None, clear=None):
        if dev is not None or clear is not None:
            raise LuaConstsError("CtrigTrace: CMov 의 Deviation/Clear 는 흉내 내지 않습니다")
        self._emit(Node("mov", args=(dest, src, 0xFFFFFFFF if mask is None else mask)))

    def _cadd(self, player, dest, src, operand=None, mask=None):
        if mask is not None:
            raise LuaConstsError("CtrigTrace: CAdd 의 Mask 는 흉내 내지 않습니다")
        self._emit(Node("add", args=(dest, src, 0 if operand is None else operand)))


def trace_digest(nodes):
    """기록한 트리의 모양 지문(sha256 16진). 칸 번호는 처음 나온 순서로 다시 매긴다(모양만 비교)."""
    names = {}

    def norm(x):
        if isinstance(x, Ref):
            key = id(x)
            if key not in names:
                names[key] = "%s#%d" % (x.kind, len(names))
            return names[key]
        if isinstance(x, Term):
            return [x.op] + [norm(a) for a in x.args]
        if isinstance(x, (list, tuple)):
            return [norm(a) for a in x]
        if isinstance(x, bytes):
            return x.decode("utf-8", "replace")
        if callable(x):
            return "<fn>"
        return x

    def node(n):
        return [n.kind, n.preserved, norm(n.conds), norm(n.acts), norm(n.args),
                [node(c) for c in n.body] if n.body is not None else None]

    text = json.dumps([node(n) for n in nodes], ensure_ascii=False, sort_keys=True, default=repr)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------------------------
# SCR_DB 코어
# ---------------------------------------------------------------------------------------------


def scrdb_core_candidates():
    """`find_scrdb_core` 가 보는 자리(환경 변수 제외, 앞에서부터)."""
    out = [
        os.path.join(os.path.dirname(ROOT), "MapSource", "Library"),
        os.path.join(os.path.expanduser("~"), "MapSource", "Library"),
    ]
    if os.name == "nt":
        prof = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        out.append(os.path.join(prof, "Desktop", "Stormcoast Fortress", "ScmDraft 2", "MapSource", "Library"))
    out.append(REFERENCE_LIBRARY)
    seen, uniq = set(), []
    for p in out:
        k = os.path.normcase(os.path.abspath(p))
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return uniq


def find_scrdb_core(path=None):
    """SCR_DB_Core.lua 위치를 정한다(모듈 docstring 의 순서). 반환: (절대 경로, 찾은 자리 설명)."""
    if path:
        f = path if os.path.isfile(path) else os.path.join(path, SCRDB_CORE_NAME)
        if not os.path.isfile(f):
            raise LuaConstsError("SCR_DB 코어가 없습니다: %s" % f)
        return os.path.abspath(f), "지정한 경로"
    return find_lua_file(SCRDB_CORE_NAME, scrdb_core_candidates(), env=SCRDB_CORE_ENV)


# 헤더 계획을 뽑을 때 두 번 넣는 설정 (값이 모두 달라 출처를 가릴 수 있게 고른 수)
_PROBE_CFGS = (
    {"SaveKey": "probe_a", "AnchorBase": 0x594000, "Humans": 3, "Channels": 2, "MsqcAddr": 0x58F500,
     "MsqcDeath": 41, "XferBase": 0x590000, "XferStride": 23, "SlotBase": 0x591000, "SlotStride": 31,
     "MaxPlayers": 11, "SlotCount": 17, "KeyMode": "ordinal", "ManifestPath": "probe_a.json", "nfields": 4,
     "time": 1000003},
    {"SaveKey": "probe_b", "AnchorBase": 0x595000, "Humans": 5, "Channels": 6, "MsqcAddr": 0x58F600,
     "MsqcDeath": 43, "XferBase": 0x590400, "XferStride": 29, "SlotBase": 0x591400, "SlotStride": 37,
     "MaxPlayers": 13, "SlotCount": 19, "KeyMode": "ordinal", "ManifestPath": "probe_b.json", "nfields": 9,
     "time": 2000005},
)


class ScrdbCore:
    """`SCR_DB_Core.lua` 에서 읽은 런처 약속(레이아웃)과, 트리거 함수를 스텁으로 돌려 뽑은 계획.

    값 (전부 Lua 전역에서 왔다):
    - `layout`(SCRDB_LAYOUT_VERSION), `magic`(시그니처 8개), `table_players`, `index`(SCRDB_I dict),
      `total`(SCRDB_TOTAL), `toggle_a`/`toggle_b`, `tag_mask`/`tag_key`/`tag_lo`/`tag_hi`, `payload`,
      `echo_mask`, `word_ready`/`word_saved`
    계획 (스텁 기록에서 뽑음):
    - `anchor_once`: 1회 블록의 트리거별 액션 목록 [[(칸 번호, 수정자 이름, 값 출처), …], …] — 값 출처는
      `("const", 값)` 또는 `("cfg", Lua Cfg 키)`(예: "BuildId", "FieldHash", "#Fields")
    - `anchor_every`: 매 사이클 트리거 목록 [(조건 [(주소 이름, 비교, 값)], 액션 [(칸, 수정자, 값)]), …]
    - `notify`: [(코드, wav 이름), …], `notify_index`: 알림 칸 번호
    - `receiver_digest`: SCRDB_Receiver 기록 모양 지문(eudext 수신기가 따라간 Lua 판인지 확인용)
    함수 (Lua 를 그대로 부른다): `slot(base, k, i)`, `field_hash(fields)`, `json(value)`(bytes),
    `assign_ids(fields)`, `setup(cfg, os_time)`(검증·BuildId·FieldHash·id), `manifest_bytes(cfg, os_time, os_date)`.
    `lua(os_time=None, os_date=None)`: 코어를 읽고 `CtrigTrace` 를 넣은 새 (Lua, CtrigTrace).
    `path`, `sha256`, `source`(찾은 자리).
    비용: 없음(컴파일 시점). 처음 읽을 때 수 ms(Lua 실행 몇 번).
    출처: MapSource/Library/SCR_DB_Core.lua (레이아웃 7, MapSource b57b6fe)
    """

    def __init__(self, path, source=""):
        self.path, self.sha256, self.size, self.mtime = file_info(path)
        self.source = source
        lua, _tr = self.lua()
        self.layout = lua.get("SCRDB_LAYOUT_VERSION")
        self.magic = tuple(lua.get("SCRDB_MAGIC"))
        self.table_players = lua.get("SCRDB_TABLE_PLAYERS")
        self.index = dict(lua.get("SCRDB_I"))
        self.total = lua.get("SCRDB_TOTAL")
        self.toggle_a = lua.get("SCRDB_TOGGLE_A")
        self.toggle_b = lua.get("SCRDB_TOGGLE_B")
        self.tag_mask = lua.get("SCRDB_TAG_MASK")
        self.tag_key = lua.get("SCRDB_TAG_KEY")
        self.tag_lo = lua.get("SCRDB_TAG_LO")
        self.tag_hi = lua.get("SCRDB_TAG_HI")
        self.payload = lua.get("SCRDB_PAYLOAD")
        self.echo_mask = lua.get("SCRDB_ECHO_MASK")
        self.word_ready = lua.get("SCRDB_WORD_READY")
        self.word_saved = lua.get("SCRDB_WORD_SAVED")
        self._check_values()
        self.anchor_once, self.anchor_every = self._anchor_plan()
        self.notify, self.notify_index = self._notify_plan()
        self.receiver_digest = self._receiver_digest()

    def __repr__(self):
        return "<ScrdbCore layout %s %s sha256 %s>" % (self.layout, self.path, self.sha256[:12])

    # --- 실행기 ---
    def lua(self, os_time=None, os_date=None):
        lua = Lua(os_time=os_time, os_date=os_date)
        tr = CtrigTrace(lua)
        lua.run_file(self.path)
        return lua, tr

    def _check_values(self):
        ints = ("layout", "table_players", "total", "toggle_a", "toggle_b", "tag_mask", "tag_key", "tag_lo", "tag_hi",
                "payload", "echo_mask", "word_ready", "word_saved")
        for n in ints:
            v = getattr(self, n)
            if isinstance(v, bool) or not isinstance(v, int):
                raise LuaConstsError("SCR_DB 코어 %s: %s 가 정수가 아닙니다 (%r)" % (self.path, n, v))
        if len(self.magic) != 8 or not all(isinstance(x, int) and 0 <= x <= 0xFFFFFFFF for x in self.magic):
            raise LuaConstsError("SCR_DB 코어 %s: SCRDB_MAGIC 이 32비트 정수 8개가 아닙니다" % self.path)
        for k, v in self.index.items():
            if not (isinstance(v, int) and 0 <= v < self.total):
                raise LuaConstsError("SCR_DB 코어 %s: SCRDB_I.%s = %r 가 0..%d 밖입니다" % (self.path, k, v, self.total - 1))

    def word_mask(self):
        """MSQC 워드에 실리는 비트 전부(토글 + 꼬리표 + 페이로드)."""
        return self.toggle_a | self.toggle_b | self.echo_mask

    # --- Lua 함수 ---
    def slot(self, base, k, i):
        lua, _ = self.lua()
        return lua.call("SCRDB_Slot", base, k, i)

    def field_hash(self, fields):
        lua, _ = self.lua()
        return lua.call("SCRDB_FieldHash", list(fields))

    def json(self, value):
        lua, _ = self.lua()
        return lua.call("SCRDB_Json", value, raw=True)

    def assign_ids(self, fields):
        """반환: (id 가 붙은 필드 목록, 겹친 이름 목록) — Lua 가 표에 id 를 붙인 결과."""
        lua, _ = self.lua()
        t = lua.to_lua(list(fields))
        dups = lua.to_py(lua._wrap(lua.raw("SCRDB_AssignIds"), t))
        return lua.to_py(t), dups

    def _run_setup(self, lua, cfg):
        c = dict(cfg)
        c.setdefault("ManifestPath", "unused.json")
        t = lua.to_lua(c)
        lua._wrap(lua.raw("SCRDB_Setup"), t)
        return t

    def setup(self, cfg, os_time=None):
        """Lua `SCRDB_Setup` 으로 설정을 검사·보완한다. 반환: 설정 dict(BuildId·FieldHash·DupNames·필드 id 포함).

        검사 실패는 `LuaStubError`(Lua 의 메시지 그대로).
        """
        lua, _ = self.lua(os_time=os_time)
        self._run_setup(lua, cfg)
        return lua.get("SCRDB_Cfg")

    def manifest_bytes(self, cfg, os_time=None, os_date=None):
        """Lua `SCRDB_Setup` + `SCRDB_WriteManifest` 가 쓰는 매니페스트 파일 내용(bytes)."""
        lua, _ = self.lua(os_time=os_time, os_date=os_date)
        fd, tmp = tempfile.mkstemp(prefix="scrdb_manifest_", suffix=".json")
        os.close(fd)
        try:
            c = dict(cfg)
            c["ManifestPath"] = tmp
            self._run_setup(lua, c)
            lua.call("SCRDB_WriteManifest")
            with open(tmp, "rb") as f:
                return f.read()
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass

    # --- 계획 추출 ---
    def _probe(self, which, fn_names):
        p = _PROBE_CFGS[which]
        lua, tr = self.lua(os_time=p["time"])
        cfg = {k: v for k, v in p.items() if k not in ("nfields", "time")}
        cfg["Fields"] = [{"name": "f%d" % n, "mode": "arr", "index": n} for n in range(p["nfields"])]
        self._run_setup(lua, cfg)
        tr.take()
        out = {}
        for fn in fn_names:
            lua.call(fn)
            out[fn] = tr.take()
        after = lua.get("SCRDB_Cfg")
        nums = {k: v for k, v in after.items() if isinstance(v, int) and not isinstance(v, bool)}
        nums["#Fields"] = p["nfields"]
        return out, nums

    def _addr_index(self, addr, base):
        off = addr - base
        if off % 4 or not 0 <= off // 4 < self.total:
            raise LuaConstsError("SCR_DB 코어 계획: 표지 블록 밖 주소 0x%X" % addr)
        return off // 4

    def _anchor_plan(self):
        a, na = self._probe(0, ["SCRDB_Anchor"])
        b, nb = self._probe(1, ["SCRDB_Anchor"])
        ta, tb = a["SCRDB_Anchor"], b["SCRDB_Anchor"]

        def source(va, vb):
            if va == vb:
                return ("const", va)
            keys = [k for k in na if na[k] == va and nb.get(k) == vb]
            if len(keys) != 1:
                raise LuaConstsError("SCR_DB 코어 계획: 헤더 값 %r/%r 의 출처를 가릴 수 없습니다 (%s)" % (va, vb, keys))
            return ("cfg", keys[0])

        def acts(nodes_a, nodes_b, base_a, base_b):
            out = []
            for xa, xb in zip(nodes_a, nodes_b):
                if xa.op != "SetMemory" or xb.op != "SetMemory":
                    raise LuaConstsError("SCR_DB 코어 계획: 표지 블록 액션이 SetMemory 가 아닙니다 (%r)" % (xa,))
                ia, ib = self._addr_index(xa.args[0], base_a), self._addr_index(xb.args[0], base_b)
                if ia != ib or xa.args[1] != xb.args[1]:
                    raise LuaConstsError("SCR_DB 코어 계획: 두 번 돌린 결과의 모양이 다릅니다")
                out.append((ia, _mod_name(xa.args[1]), source(xa.args[2], xb.args[2])))
            return out

        if len(ta) != len(tb) or not ta or ta[0].kind != "once" or ta[0].conds or ta[0].acts:
            raise LuaConstsError("SCR_DB 코어 계획: SCRDB_Anchor 가 조건 없는 CIfOnce 로 시작하지 않습니다")
        ba, bb = na["AnchorBase"], nb["AnchorBase"]
        once = []
        for xa, xb in zip(ta[0].body, tb[0].body):
            if xa.kind != "trig" or xa.conds:
                raise LuaConstsError("SCR_DB 코어 계획: 1회 블록 안에 액션 트리거가 아닌 것이 있습니다 (%r)" % (xa,))
            once.append(acts(xa.acts, xb.acts, ba, bb))
        every = []
        for xa, xb in zip(ta[1:], tb[1:]):
            if xa.kind != "trig" or not xa.preserved or len(xa.conds) != len(xb.conds):
                raise LuaConstsError("SCR_DB 코어 계획: 매 사이클 부분에 보존 트리거가 아닌 것이 있습니다 (%r)" % (xa,))
            conds = []
            for ca, cb in zip(xa.conds, xb.conds):
                if ca.op != "Memory" or ca != cb or ca.args[0] != 0x512684:
                    raise LuaConstsError("SCR_DB 코어 계획: 매 사이클 조건은 LocalPlayerID 만 흉내 냅니다 (%r)" % (ca,))
                conds.append(("local_player", _cmp_name(ca.args[1]), ca.args[2]))
            every.append((conds, acts(xa.acts, xb.acts, ba, bb)))
        return once, every

    def _notify_plan(self):
        a, na = self._probe(0, ["SCRDB_Notify"])
        base = na["AnchorBase"]
        sounds = []
        nidx = None
        for blk in a["SCRDB_Notify"]:
            ok = (blk.kind == "if" and len(blk.conds) == 1 and blk.conds[0].op == "Memory" and len(blk.acts) == 1
                  and blk.acts[0].op == "SetMemory")
            if not ok:
                raise LuaConstsError("SCR_DB 코어 계획: SCRDB_Notify 모양이 예상과 다릅니다 (%r)" % (blk,))
            addr, cmp_, code = blk.conds[0].args
            idx = self._addr_index(addr, base)
            zero = blk.acts[0].args
            if _cmp_name(cmp_) != "Exactly" or zero != (addr, TEP_CONSTS["SetTo"], 0) or (nidx not in (None, idx)):
                raise LuaConstsError("SCR_DB 코어 계획: SCRDB_Notify 조건·지우기 모양이 다릅니다 (%r)" % (blk,))
            nidx = idx
            wavs = set()
            for i, t in enumerate(blk.body):
                want_c = [Term("Memory", 0x512684, TEP_CONSTS["Exactly"], i)]
                if t.kind != "trig" or not t.preserved or t.conds != want_c or len(t.acts) != 3:
                    raise LuaConstsError("SCR_DB 코어 계획: 알림음 트리거 모양이 다릅니다 (%r)" % (t,))
                if t.acts[0] != Term("SetCp", i) or t.acts[1].op != "PlayWAV" or t.acts[2] != Term("SetCp", FP_VALUE):
                    raise LuaConstsError("SCR_DB 코어 계획: 알림음 액션 모양이 다릅니다 (%r)" % (t,))
                wavs.add(t.acts[1].args[0])
            if len(blk.body) != 8 or len(wavs) != 1:
                raise LuaConstsError("SCR_DB 코어 계획: 알림음은 P1~P8 에게 같은 소리여야 합니다")
            sounds.append((code, wavs.pop()))
        return sounds, nidx

    def _receiver_digest(self):
        lua, tr = self.lua(os_time=_PROBE_CFGS[0]["time"])
        p = _PROBE_CFGS[0]
        cfg = {k: v for k, v in p.items() if k not in ("nfields", "time")}
        cfg["Fields"] = [{"name": "f0", "mode": "arr", "index": 0}]
        cfg["Humans"], cfg["Channels"] = 1, 1
        self._run_setup(lua, cfg)
        tr.take()
        lua.call("SCRDB_Receiver", tr.callback("Write"))
        return trace_digest(tr.take())

    def as_dict(self):
        """명령줄 출력·문서용 요약."""
        return {
            "path": self.path,
            "sha256": self.sha256,
            "source": self.source,
            "layout": self.layout,
            "magic": ["0x%08X" % x for x in self.magic],
            "table_players": self.table_players,
            "total": self.total,
            "index": dict(sorted(self.index.items(), key=lambda kv: kv[1])),
            "word": {
                "toggle_a": hex(self.toggle_a), "toggle_b": hex(self.toggle_b), "tag_mask": hex(self.tag_mask),
                "tag_key": hex(self.tag_key), "tag_lo": hex(self.tag_lo), "tag_hi": hex(self.tag_hi),
                "payload": hex(self.payload), "echo_mask": hex(self.echo_mask),
                "ready": hex(self.word_ready), "saved": hex(self.word_saved),
            },
            "anchor_once": [[list(a[:2]) + [list(a[2])] for a in trig] for trig in self.anchor_once],
            "anchor_every": [[[list(c) for c in conds], [list(a[:2]) + [list(a[2])] for a in acts]]
                             for conds, acts in self.anchor_every],
            "notify": [list(x) for x in self.notify],
            "notify_index": self.notify_index,
            "receiver_digest": self.receiver_digest,
        }


def _mod_name(v):
    for k in ("SetTo", "Add", "Subtract"):
        if TEP_CONSTS[k] == v:
            return k
    raise LuaConstsError("알 수 없는 수정자 %r" % (v,))


def _cmp_name(v):
    for k in ("AtLeast", "AtMost", "Exactly"):
        if TEP_CONSTS[k] == v:
            return k
    raise LuaConstsError("알 수 없는 비교 %r" % (v,))


_core_cache = {}


def scrdb_core(path=None, quiet=False):
    """SCR_DB 코어를 찾아 읽는다(파일 내용이 같으면 캐시). 저장소 사본(reference)을 쓰면 경고한다.

    인자: path(선택: 파일 또는 폴더), quiet(True 면 경고·안내 줄을 내지 않음)
    반환: ScrdbCore
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다 (scrdb.setup 이 부른다)
    출처: DESIGN 4.18 (a)
    """
    f, src = find_scrdb_core(path)
    _p, sha, size, mtime = file_info(f)
    key = (os.path.normcase(f), sha)
    core = _core_cache.get(key)
    if core is None:
        core = ScrdbCore(f, src)
        _core_cache[key] = core
        if not quiet:
            if os.path.normcase(os.path.dirname(f)) == os.path.normcase(os.path.abspath(REFERENCE_LIBRARY)):
                warn("scrdb: 저장소 사본 %s 을 씁니다 — MapSource 최신본이 아닐 수 있습니다(%s 로 지정 가능)", f, SCRDB_CORE_ENV)
            print("[eudext.scrdb] Lua 코어 %s (레이아웃 %s, sha256 %s)" % (f, core.layout, sha[:12]))
    return core


# ---------------------------------------------------------------------------------------------
# 명령줄
# ---------------------------------------------------------------------------------------------


def main(argv=None):
    import argparse

    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="eudext Lua 상수 읽기")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s1 = sub.add_parser("scrdb", help="SCR_DB 코어의 약속 값·계획")
    s1.add_argument("--core", default=None)
    s1.add_argument("--json", action="store_true")
    s2 = sub.add_parser("get", help="Lua 파일의 전역 값")
    s2.add_argument("file")
    s2.add_argument("names", nargs="*")
    args = ap.parse_args(argv)
    if args.cmd == "scrdb":
        core = scrdb_core(args.core, quiet=True)
        d = core.as_dict()
        if args.json:
            print(json.dumps(d, ensure_ascii=False, indent=1))
        else:
            print("파일   %s (%s)" % (d["path"], d["source"]))
            print("sha256 %s" % d["sha256"])
            print("레이아웃 %s, 칸 %s, 플레이어 칸 %s" % (d["layout"], d["total"], d["table_players"]))
            print("시그니처 %s" % " ".join(d["magic"]))
            print("칸 번호 %s" % ", ".join("%s=%d" % kv for kv in d["index"].items()))
            print("워드 %s" % ", ".join("%s=%s" % kv for kv in d["word"].items()))
            for n, trig in enumerate(core.anchor_once):
                print("1회 블록 트리거 %d: 액션 %d개 (%s … %s)" % (n + 1, len(trig), trig[0], trig[-1]))
            for conds, acts in core.anchor_every:
                print("매 사이클: %s → %s" % (conds, acts))
            print("알림음(칸 %s): %s" % (core.notify_index, core.notify))
            print("수신기 지문 %s" % core.receiver_digest)
        return 0
    vals = read_globals(args.file, args.names or None)
    print(json.dumps(vals, ensure_ascii=False, indent=1, default=repr))
    return 0


if __name__ == "__main__":
    sys.exit(main())
