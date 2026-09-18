"""CX Paint 도형 — lupa 로 CB Paint 를 그대로 돌려 좌표를 얻고, 좌표표(4B/점)로 싣는다 (DESIGN 4.13).

    from eudext.shape import CX, Shape, ShapeSet
    cx = CX(extra=["CSMakeSpiral.lua", "CS_Addon.lua"], seed=1234)     # lib_dir 기본 = 저장소 reference/MapSource/Library
    ring = cx.call("CSMakeCircle", 6, 32, 0, 37, 0)                     # Shape (점 37개)
    star = cx.eval("CS_Rotate(CSMakeStar(5,72,60,0,CS_Level('Star',5,4),0), 15)")
    cx.run_file("MapShapes/Boss.lua"); boss = cx.get("SH_Boss")         # 맵별 Lua 도형 그대로
    fade = ring.sweep("right", px_per_cycle=32)                         # 정렬 + LoopMax 스케줄이 붙은 새 Shape
    shapes = ShapeSet([ring, star, fade])                               # storage="db"(4B/점) | "varray"(144B/점, 읽기 빠름)
    x, y = shapes.point_at(sid, i); n = shapes.count(sid)               # 상태 없는 점 읽기 (spawn 이 씀)

epScript (클래스·메서드 이름은 번역되지 않는다):

    import eudext.shape as shape;
    const cx = shape.CX(seed=1234);
    const ring = cx.call("CSMakeCircle", 6, 32, 0, 37, 0);
    const shapes = shape.ShapeSet(list(ring, ring.sweep("right", px_per_cycle=32)));
    const x, y = shapes.point_at(0, i);

## 부트 (lupa 는 이 모듈만 쓴다 — DESIGN 2.3·2.4)

euddraft 안에서는 lupa 를 **부트 중에만** 불러올 수 있다. eds 의 부트 줄에 `Preload : shape` 를 넣는다.
lupa(번들 파이썬 3.14 용 cp314 휠)는 `VenvSite` 로 주거나, 없으면 이 모듈이 다음 폴더를 차례로 찾는다:
환경 변수 `EUDEXT_LUPA_SITE`(`os.pathsep` 구분) → 저장소 `.tools/euddraft_site` → `~/.venvs/euddraft011_site`
(Windows 설치 안내의 위치). 그래서 eds 에 `VenvSite` 를 적지 않아도 Linux·Windows 양쪽에서 빌드된다.
lupa 가 없어도 `Shape`/`ShapeSet` 은 쓸 수 있다(`CX` 를 만들 때만 오류).

## 좌표와 각도 (사용자 결정 D5·D6 — 옵션 없음)

- **정수화는 TEP 와 같은 0 방향 자르기**(`int()`, `floor` 아님). 반올림과는 1,700점 원에서 1,184점이 다르다.
  TEP 규칙: CtrigAsm 파일 배열(`SaveFileArr` → `bit32.band`)은 `(lua_Integer)` 캐스트 뒤 아래 32비트다
  (TrigEditPlus `Encoder/src/linit.c:37`). DPS 이식판 `ctrig/classic.py _i32` 와 같은 규칙이고, 거기서 오류가 나는
  NaN·무한대는 MSVC x64 캐스트 값(0x8000000000000000)의 아래 32비트 = **0** 으로 둔다. NaN 은 원점에 극좌표 함수
  (`CS_MoveRA` 등)를 쓸 때 생기며(`atan(0/0)`), 원본 관용구 `CS_FixShape` 도 0 으로 되돌린다. 무한대는 경고한다.
- 도형 각도는 CB Paint 가 lupa 안에서 계산하므로 원본과 같다: **0° = 12시, 각이 늘면 시계 방향**
  (`CSMakeCircle` 첫 껍질의 첫 점이 (0, −R), `CS_Rotate(…, 45)` 가 시계 방향). 런타임 점 변환(`plot` 의 `pt.rotate`)은
  CtrigAsm CA_ 함수처럼 0 = +x 이므로 기준점이 90° 어긋난다(회전 방향은 같다). 원본 그대로다.
- `Hollow` 를 준 `CSMake*` 는 선언 개수(`Shape[1]`)보다 많은 점을 표 뒤에 남긴다 → **`Shape[1]` 개까지만** 읽는다
  (원본 `CSPlot`·`CAPlot` 과 같다). `CSMakeGraph*` 는 "호 길이 StepSize 로 Number 번 행진" 이라 곡선 길이와 맞지 않으면
  닫히지 않는다 — 원본 그대로 둔다.
- **수학 함수는 정확 반올림**(옵션 없음): `new_lua_runtime()` 이 Lua `math.sin/cos/tan/asin/acos/atan/exp/log` 를
  `eudext._crmath`(decimal 고정밀 + Ziv 반올림)로 바꾼다. C 라이브러리의 1ulp 차이가 자르기(D6)를 거쳐 점을 바꾸기 때문이다
  (star 6번째 점 y: 참값 48, 정확 반올림·원본 플러그인 TrigEditPlus3.0.sdp·Windows ucrt = 47, glibc·mingw(tepc) = 48 —
  2026-09-17 Windows 측정). 표본 1,592도형에서 원본 플러그인과 좌표 차이 0점. 그래서 결과는 OS 와 무관하고 원본 플러그인과 같다.
  `math.sqrt`·`rad`·`deg`·사칙연산은 IEEE 로 이미 같다. `^` 는 바꿀 수 없다(CB Paint 는 `^2` = 곱셈과 `CS_Round` 의 `10^Digit` 뿐).
- 원본 난수: CB Paint 최상위가 `math.randomseed(os.time())` 를 부른다 → 모든 Lua 파일을 읽은 **뒤에**
  `math.randomseed(seed)` 로 다시 시드를 준다(기본 0, 빌드마다 같은 결과). `seed=None` 이면 원본처럼 시각 시드.

## 저장 (ShapeSet)

- `storage="db"`(기본): 점 하나 = dword `(x+0x8000) | (y+0x8000)<<16` (좌표 −32768 ~ 32767). 도형별 시작 EPD·점 수·
  스케줄 EPD 는 주소표(theSeed `CAPlotIndexed.lua` 방식 — 도형 수와 무관한 트리거로 읽는다). 점 읽기는 eudplib
  `f_readgen_epd` 한 벌(비트 32개를 x·y 로 나눠 더하고 편향을 뺀다).
- `storage="varray"`: 점 하나 = 72B 변수 원소 둘(x, y — 좌표 32비트 그대로). 읽기는 원소 사슬로 점프(실행 약 9).
  1,700점에 245KB 라 도형이 크면 "db" 가 낫다.
- LoopMax 스케줄 = `{밴드 수, c1, c2, …}` dword 배열(원본 형식). 도형 번호(sid)는 0부터.
- `dedupe=True`(기본): 좌표 내용이 같은 도형은 좌표를 한 번만 싣고(시작 주소를 같이 쓴다), 좌표·스케줄이 모두 같으면
  같은 sid 를 준다. 같은 Shape 객체는 늘 같은 sid.
- 표는 게으르게 만든다: **SaveMap 이 페이로드를 모으기 전까지 `add()` 로 도형을 더할 수 있다**(spawn 이 push 때 등록).
  페이로드를 쓰는 동안 더하면 오류, 다 쓴 뒤에 더한 도형은 다음 빌드에 실린다(시험 프로세스).
  변수 sid 는 실행 중에 도형 수와 비교해 범위 밖이면 빈 도형(점 0)으로 읽는다(주소표 밖을 읽지 않게).

출처: CB Paint v2.5(`reference/MapSource/Library/CB Paint v2.5.lua` — CBP), theSeed `Engine/CAPlotIndexed.lua`(CAPI),
theSeed `MapConfig/Shape.lua:938` GunFadeShape(sweep), DPS_Enhance eudplib-port a7aad90 `eud/ctrig/luart.py:19`
(bit32 흉내·latin-1 런타임·BOM 떼기), `eud/ctrig/classic.py:27` `_i32`, R4b B1~B8, 실험 `docs/proto/lupa_cbpaint_exp.py`.
"""

import functools
import math
import os
import struct
import sys
import weakref

from eudplib import (
    EPD,
    AtMost,
    EUDElse,
    EUDEndIf,
    EUDFunc,
    EUDIf,
    EUDObject,
    EUDVariable,
    Forward,
    MemoryEPD,
    NextTrigger,
    PopTriggerScope,
    PushTriggerScope,
    RawTrigger,
    SeqCompute,
    SetNextPtr,
    SetTo,
    f_dwread_epd,
    f_readgen_epd,
    unProxy,
)

from eudext import _compat, _crmath, _parts
from eudext.errors import EudextError, check_choice, fail, warn

M32 = 0xFFFFFFFF
BIAS = 0x8000
COORD_MIN = -0x8000
COORD_MAX = 0x7FFF
VARRAY_STEP = 144  # 점 하나 = 72B 원소 둘
STORAGES = ("db", "varray")
LIB_FILE = "CB Paint v2.5.lua"
LUPA_SITE_ENV = "EUDEXT_LUPA_SITE"
SWEEP_MODES = ("right", "left", "down", "up", "in", "out")

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_PKG_DIR)
DEFAULT_LIB_DIR = os.path.join(_ROOT, "reference", "MapSource", "Library")

__all__ = [
    "BIAS",
    "CX",
    "DEFAULT_LIB_DIR",
    "LIB_FILE",
    "LUPA_SOURCE",
    "STORAGES",
    "SWEEP_MODES",
    "Shape",
    "ShapeSet",
    "VARRAY_STEP",
    "decode_point",
    "encode_point",
    "f_decode_point",
    "f_encode_point",
    "f_tep_int",
    "import_lupa",
    "install_tep_shims",
    "lua_load",
    "lua_load_file",
    "lua_to_py",
    "lupa_site_candidates",
    "new_lua_runtime",
    "tep_int",
]


# =============================================================================================
# lupa 적재 — tools/lua_consts.py(WP18)와 합칠 수 있게 작은 함수로 나눴다
# =============================================================================================

_lupa_mod = None
_lupa_errors = []
LUPA_SOURCE = None  # lupa 를 불러온 곳 ("기본 경로" 또는 후보 폴더)


def lupa_site_candidates():
    """lupa 를 기본 경로에서 못 불러올 때 찾아볼 폴더 목록(순서대로).

    인자: 없음
    반환: list[str] — 환경 변수 `EUDEXT_LUPA_SITE`(os.pathsep 구분), 저장소 `.tools/euddraft_site`,
          `~/.venvs/euddraft011_site`
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: DESIGN 2.1 표(Windows `C:\\Users\\whatd\\.venvs\\euddraft011_site`, Ubuntu `.tools/euddraft_site`)
    """
    out = []
    env = os.environ.get(LUPA_SITE_ENV)
    if env:
        out.extend(p for p in env.split(os.pathsep) if p)
    out.append(os.path.join(_ROOT, ".tools", "euddraft_site"))
    out.append(os.path.join(os.path.expanduser("~"), ".venvs", "euddraft011_site"))
    return out


def _forget_lupa():
    for name in [m for m in sys.modules if m == "lupa" or m.startswith("lupa.")]:
        del sys.modules[name]


def import_lupa():
    """`lupa.lua54` 모듈을 돌려준다. 기본 경로에 없으면 `lupa_site_candidates()` 폴더를 sys.path 끝에 붙여 본다.

    euddraft 안에서는 부트(`Preload : shape`) 중에 불려야 한다 — 그 뒤에는 euddraft 가 sys.path 를 되돌린다.
    인자: 없음
    반환: 모듈 `lupa.lua54`
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: DPS_Enhance eudplib-port a7aad90 `dps_eud.py:17~31`(VenvSite 를 뒤에 붙이기), R4b B2
    """
    global _lupa_mod, LUPA_SOURCE
    if _lupa_mod is not None:
        return _lupa_mod
    try:
        import lupa.lua54 as lua54

        _lupa_mod = lua54
        LUPA_SOURCE = "기본 경로"
        return lua54
    except ImportError as e:
        _lupa_errors.append("기본 경로: %s" % e)
        _forget_lupa()
    for site in lupa_site_candidates():
        if not os.path.isdir(os.path.join(site, "lupa")):
            continue
        added = site not in sys.path
        if added:
            sys.path.append(site)
        try:
            import lupa.lua54 as lua54

            _lupa_mod = lua54
            LUPA_SOURCE = site
            print("[eudext.shape] lupa %s 를 불러왔습니다: %s" % (getattr(sys.modules.get("lupa"), "__version__", "?"), site))
            return lua54
        except ImportError as e:
            _lupa_errors.append("%s: %s" % (site, e))
            _forget_lupa()
            if added:
                sys.path.remove(site)
    fail(
        "lupa(Lua 5.4)를 불러올 수 없습니다. euddraft 에서는 eds 부트 줄에 'Preload : shape' 를 넣고, 번들 파이썬(3.14)용 "
        "lupa 폴더를 'VenvSite : <폴더>' 나 환경 변수 %s 로 알려 주세요. 시도: %s",
        LUPA_SITE_ENV,
        " / ".join(_lupa_errors) or "없음",
    )


# eudext.shape 를 import 하는 순간(부트의 Preload) lupa 를 미리 불러 둔다. 실패해도 여기서는 멈추지 않는다.
try:
    import_lupa()
except EudextError:
    pass

# Lua 를 부르는 구간의 C 로캘 가드(Windows 사용자 로캘에서 문자 분류가 달라지는 것을 막는다 — tools/lua_consts 모듈 docstring
# "로캘"). lua_consts 도 import 때 lupa 를 불러오므로 위 import_lupa() 뒤에 가져온다(폴더 찾기로 올린 lupa 를 같이 쓰게).
from eudext.tools.lua_consts import lua_c_locale  # noqa: E402


# TEP lbitlib 의미(결과 0..2^32-1, 소수는 0 방향 자르기). 출처: DPS_Enhance eudplib-port a7aad90 eud/ctrig/luart.py:19~74
BIT32_LUA = r"""
local M = {}
local MASK = 0xFFFFFFFF
local function u(x)
    if type(x) == "string" then x = tonumber(x) end
    if type(x) ~= "number" then error("bit32: number expected, got " .. type(x), 3) end
    local i = math.tointeger(x)
    if i == nil then
        local t = x >= 0 and math.floor(x) or math.ceil(x)
        i = math.tointeger(t) or math.tointeger(math.fmod(t, 4294967296.0)) or 0
    end
    return i & MASK
end
local function nargs(...) return select('#', ...) end
function M.band(...) local r = MASK for i = 1, nargs(...) do r = r & u((select(i, ...))) end return r end
function M.bor(...) local r = 0 for i = 1, nargs(...) do r = r | u((select(i, ...))) end return r end
function M.bxor(...) local r = 0 for i = 1, nargs(...) do r = r ~ u((select(i, ...))) end return r end
function M.btest(...) return M.band(...) ~= 0 end
function M.bnot(x) return (~u(x)) & MASK end
local function shift(x, disp)
    x = u(x); disp = math.tointeger(disp) or error("bit32: bad shift", 3)
    if disp <= -32 or disp >= 32 then return 0 end
    if disp >= 0 then return (x << disp) & MASK else return (x >> -disp) & MASK end
end
function M.lshift(x, d) return shift(x, d) end
function M.rshift(x, d) return shift(x, -(math.tointeger(d) or error("bit32: bad shift", 2))) end
function M.arshift(x, d)
    x = u(x); d = math.tointeger(d) or error("bit32: bad shift", 2)
    if d < 0 or (x & 0x80000000) == 0 then return shift(x, -d) end
    if d >= 32 then return MASK end
    return ((x >> d) | ~(MASK >> d)) & MASK
end
local function rot(x, d)
    x = u(x); d = (math.tointeger(d) or error("bit32: bad rotate", 3)) & 31
    return ((x << d) | (x >> (32 - d))) & MASK
end
function M.lrotate(x, d) return rot(x, d) end
function M.rrotate(x, d) return rot(x, -d) end
local function fw(f, w)
    f = math.tointeger(f); w = math.tointeger(w or 1)
    if f < 0 then error("bit32: field cannot be negative", 3) end
    if w <= 0 then error("bit32: width must be positive", 3) end
    if f + w > 32 then error("bit32: trying to access non-existent bits", 3) end
    return f, w
end
function M.extract(x, f, w) f, w = fw(f, w) return (u(x) >> f) & ((1 << w) - 1) end
function M.replace(x, v, f, w)
    f, w = fw(f, w)
    local m = ((1 << w) - 1)
    return ((u(x) & ~(m << f)) | ((u(v) & m) << f)) & MASK
end
return M
"""

# CB Paint·맵 도형 Lua 가 기대하는 TEP/CtrigAsm 전역 (R4b B2 "CX Paint 에 더 필요한 shim")
TEP_SHIMS_LUA = r"""
math.atan2 = math.atan2 or function(y, x) return math.atan(y, x) end
if PushErrorMsg == nil then PushErrorMsg = function(msg) error(msg, 2) end end
if exists == nil then
    exists = function(file)
        local ok, err, code = os.rename(file, file)
        if not ok and code == 13 then return true end
        return ok, err
    end
end
if isdir == nil then isdir = function(path) return exists(path .. "/") end end
"""

# 도형 표 {n, {x,y}, …} → (n, 좌표 바이트). 첫 n 점만 읽는다(Hollow 함정). 점이 없으면 (nil, 번호)
_SHAPE_PACK_LUA = r"""
return function(t)
    if type(t) ~= "table" then return nil, -1 end
    local n = t[1]
    if math.type(n) == nil then return nil, -1 end
    if math.type(n) == "float" then
        if n ~= math.floor(n) then return nil, -2 end
        n = math.tointeger(n)
    end
    if n < 0 then return nil, -2 end
    local parts, buf = {}, {}
    for i = 1, n do
        local p = t[i + 1]
        if type(p) ~= "table" or type(p[1]) ~= "number" or type(p[2]) ~= "number" then return nil, i end
        buf[#buf + 1] = p[1] + 0.0
        buf[#buf + 1] = p[2] + 0.0
        if #buf >= 4096 then
            parts[#parts + 1] = string.pack("<" .. string.rep("d", #buf), table.unpack(buf))
            buf = {}
        end
    end
    if #buf > 0 then parts[#parts + 1] = string.pack("<" .. string.rep("d", #buf), table.unpack(buf)) end
    return n, table.concat(parts)
end
"""


def new_lua_runtime():
    """lupa Lua 5.4 런타임 하나(latin-1 — Lua 바이트열과 파이썬 str 이 1:1)에 TEP `bit32` 흉내와 정확 반올림 `math` 를 넣어 돌려준다.

    `math.sin/cos/tan/asin/acos/atan/exp/log` 는 `eudext._crmath` 구현(원본 플러그인과 같은 좌표, OS 무관 — 모듈 설명
    "좌표와 각도")으로 바뀐다. 옵션은 없다(D5·D6).

    인자: 없음
    반환: `lupa.lua54.LuaRuntime`
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: DPS_Enhance eudplib-port a7aad90 `eud/ctrig/luart.py:147~155`, `_crmath.install_lua`(TEP Lua 5.4.4 lmathlib.c 의 뜻)
    주의: 이 런타임으로 Lua 를 직접 부를 때는 `lua_c_locale()`(tools/lua_consts)로 감싼다 — Windows 사용자 로캘에서는
          Lua 문자 분류(`%c` 등)가 원본 TEP 와 달라진다. `CX` 메서드와 `lua_load` 는 이미 감싼다.
    """
    lua54 = import_lupa()
    L = lua54.LuaRuntime(unpack_returned_tuples=True, register_eval=False, encoding="latin-1")
    with lua_c_locale():
        L.globals()["bit32"] = L.execute(BIT32_LUA)
        _crmath.install_lua(L)
    return L


def install_tep_shims(L, file_dir=None):
    """CB Paint 가 쓰는 TEP 전역을 채운다: `math.atan2`, `PushErrorMsg`, `exists`/`isdir`, `FileDirectory`.

    인자: L(런타임), file_dir(CSSave·BMP 함수가 쓰는 폴더 — 끝에 `/` 를 붙여 `FileDirectory` 로 둔다. None 이면 두지 않음)
    반환: None
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: R4b B2, CtrigAsm `SaveTempFileInit`(exists/isdir), 실험 `docs/proto/lupa_cbpaint_exp.py:28~43`
    """
    with lua_c_locale():
        L.execute(TEP_SHIMS_LUA)
    if file_dir is not None:
        d = os.path.abspath(file_dir).replace("\\", "/")
        if not d.endswith("/"):
            d += "/"
        L.globals()["FileDirectory"] = d


def lua_load(L, source, chunkname):
    """Lua 소스(바이트 또는 str)를 실행하고 청크의 반환값을 돌려준다. UTF-8 BOM 은 뗀다(TEP 와 같음).

    인자: L, source(bytes | str), chunkname(오류 메시지에 쓰는 이름, 예: "@파일.lua")
    반환: 청크 반환값(lupa 값)
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: DPS_Enhance eudplib-port a7aad90 `eud/ctrig/luart.py:199~208` run_bytes
    """
    if isinstance(source, str):
        source = source.encode("utf-8")
    if source.startswith(b"\xef\xbb\xbf"):
        source = source[3:]
    with lua_c_locale():  # 청크 실행도 "C" 문자 분류로 (tools/lua_consts 모듈 docstring "로캘")
        loader = L.eval("function(src, name) return assert(load(src, name)) end")
        # latin-1 런타임: 바이트를 그대로 넘긴다 (한글 등 UTF-8 은 바이트열로 들어간다)
        return loader(source.decode("latin-1"), chunkname.encode("utf-8").decode("latin-1"))()


def lua_load_file(L, path):
    """Lua 파일을 바이트로 읽어 실행한다(`lua_load` — BOM 뗌, 청크 이름 "@파일 이름").

    인자: L(런타임), path(파일 경로)
    반환: 청크 반환값(lupa 값)
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: DPS_Enhance eudplib-port a7aad90 `eud/ctrig/luart.py:210` run_file
    """
    with open(path, "rb") as f:
        src = f.read()
    return lua_load(L, src, "@" + os.path.basename(path))


def lua_to_py(value):
    """lupa 값을 파이썬 값으로: 표는 1..n 연속 키면 list, 아니면 dict(재귀), 나머지는 그대로.

    인자: value
    반환: 파이썬 값
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성 (tools/lua_consts 와 공유 후보)
    """
    lua54 = import_lupa()
    if lua54.lua_type(value) != "table":
        return value
    items = list(value.items())
    keys = [k for k, _v in items]
    if keys and all(isinstance(k, int) for k in keys) and sorted(keys) == list(range(1, len(keys) + 1)):
        d = dict(items)
        return [lua_to_py(d[i]) for i in range(1, len(keys) + 1)]
    return {k: lua_to_py(v) for k, v in items}


# =============================================================================================
# 좌표 정수화 (D6)
# =============================================================================================


def f_tep_int(v):
    """TEP 파일 배열(`bit32.band`)이 실수 좌표를 정수로 바꾸는 규칙 — 0 방향 자르기, NaN·무한대 → 0, 32비트 부호 있는 값.

    인자: v(int | float)
    반환: int (−2³¹ ~ 2³¹−1)
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const k = shape.tep_int(2.7);` (컴파일 시점 값)
    출처: TrigEditPlus v3.0 `Encoder/src/linit.c:37` luaL_checkinteger_Fix, DPS a7aad90 `ctrig/classic.py:27` _i32
    """
    if isinstance(v, bool):
        v = int(v)
    if isinstance(v, int):
        t = v
    elif isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return 0
        t = int(v)  # 0 방향
        if not -(1 << 63) <= t < (1 << 63):
            return 0  # (lua_Integer) 넘침 → 0x8000000000000000 의 아래 32비트
    else:
        fail("shape.tep_int: 숫자가 아닙니다 (%r)", v)
    t &= M32
    return t - (1 << 32) if t & 0x80000000 else t


tep_int = f_tep_int


def f_encode_point(x, y):
    """점 (x, y) → "db" 저장 dword `(x+0x8000) | (y+0x8000)<<16`.

    인자: x, y(정수 −32768 ~ 32767 — 밖이면 EudextError)
    반환: int (0 ~ 0xFFFFFFFF)
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const w = shape.encode_point(-3, 5);`
    출처: DESIGN 4.13, R4b B7
    """
    for name, v in (("x", x), ("y", y)):
        if isinstance(v, bool) or not isinstance(v, int) or not COORD_MIN <= v <= COORD_MAX:
            fail("shape: 좌표 %s=%r 는 저장할 수 없습니다 (정수 −32768 ~ 32767, storage='varray' 는 32비트)", name, v)
    return (x + BIAS) | ((y + BIAS) << 16)


def f_decode_point(w):
    """`encode_point` 의 반대: dword → (x, y).

    인자: w(정수 — 32비트로 읽음)
    반환: (x, y) 정수
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const x, y = shape.decode_point(w);`
    출처: DESIGN 4.13
    """
    w &= M32
    return (w & 0xFFFF) - BIAS, (w >> 16) - BIAS


encode_point = f_encode_point
decode_point = f_decode_point


# =============================================================================================
# Shape
# =============================================================================================


def _check_counts(counts, npts, what):
    try:
        counts = tuple(unProxy(c) for c in counts)
    except TypeError:
        fail("%s: 스케줄은 정수 목록이어야 합니다 (%r)", what, counts)
    if not counts:
        fail("%s: 스케줄이 비었습니다 (밴드가 하나 이상 있어야 합니다)", what)
    for c in counts:
        if isinstance(c, bool) or not isinstance(c, int) or not 0 <= c <= M32:
            fail("%s: 스케줄 값 %r 는 0 이상 정수여야 합니다", what, c)
    if sum(counts) < npts and counts[-1] == 0:
        fail(
            "%s: 스케줄 합 %d 가 점 수 %d 보다 작고 마지막 밴드가 0 이라 찍기가 끝나지 않습니다 (마지막 밴드가 계속 되풀이된다)",
            what, sum(counts), npts,
        )
    return counts


class Shape:
    """컴파일 시점 도형 — 정수 점 목록(0 방향 자르기) + 선택적 LoopMax 스케줄.

    인자: points((x, y) 목록 — 정수 또는 실수, 실수는 TEP 규칙으로 자른다), schedule(사이클별 점 수 목록 또는 None),
          name(표시용)
    속성: `points`(정수 (x, y) 튜플), `raw`(받은 값 그대로 — sweep 의 정렬 기준), `schedule`(튜플 또는 None),
          `nan_count`(NaN 이라 0 으로 둔 좌표 수), `len(s)`, `s[i]`, `for p in s`
    메서드: `bounds()`, `sweep(mode, px_per_cycle)`, `with_schedule(counts)`, `from_points(points)`
    비용: 없음(컴파일 시점 값). ShapeSet 에 넣으면 점마다 4B
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const s = shape.Shape.from_points(list(list(0, 0), list(32, 0)));` (list 는 FlattenList 라 중첩이 풀린다 —
              epScript 에서는 `shape.Shape.from_flat(list(0, 0, 32, 0))` 를 쓴다)
    출처: CB Paint Shape 형식 `{n, {x,y}, …}`(CBP:8, R4b B1)
    """

    dont_flatten = True  # epScript list(a, b) = FlattenList 가 점을 풀어 버리지 않게
    __slots__ = ("_hash", "_pts", "_raw", "_sched", "name", "nan_count", "__weakref__")

    def __init__(self, points=(), schedule=None, name=None):
        raw = []
        pts = []
        nan = 0
        inf = 0
        for k, p in enumerate(points):
            try:
                x, y = p[0], p[1]
            except (TypeError, IndexError, KeyError):
                fail("Shape: 점 %d 가 (x, y) 꼴이 아닙니다 (%r)", k, p)
            x, y = unProxy(x), unProxy(y)
            for v in (x, y):
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    fail("Shape: 점 %d 의 좌표 %r 는 숫자가 아닙니다", k, v)
                if isinstance(v, float):
                    if math.isnan(v):
                        nan += 1
                    elif math.isinf(v):
                        inf += 1
            raw.append((x, y))
            pts.append((f_tep_int(x), f_tep_int(y)))
        if inf:
            warn("Shape %s: 무한대 좌표 %d개를 0 으로 둡니다 (TEP 캐스트와 같음) — 도형 식을 확인하세요", name or "", inf)
        self._raw = tuple(raw)
        self._pts = tuple(pts)
        self.nan_count = nan
        self.name = name
        self._sched = None if schedule is None else _check_counts(schedule, len(pts), "Shape %s" % (name or ""))
        self._hash = hash((self._pts, self._sched))

    # --- 만들기 ---
    @classmethod
    def from_points(cls, points, schedule=None, name=None):
        """점 목록으로 만든다(= 생성자). 출처: DESIGN 4.13 `Shape.from_points`."""
        return cls(points, schedule=schedule, name=name)

    @classmethod
    def from_flat(cls, values, schedule=None, name=None):
        """평평한 목록 `[x0, y0, x1, y1, …]` 으로 만든다(epScript `list(…)` 는 중첩을 풀기 때문)."""
        values = list(values)
        if len(values) % 2:
            fail("Shape.from_flat: 값 개수 %d 가 짝수가 아닙니다", len(values))
        return cls(list(zip(values[0::2], values[1::2])), schedule=schedule, name=name)

    # --- 읽기 ---
    @property
    def points(self):
        return self._pts

    @property
    def raw(self):
        return self._raw

    @property
    def schedule(self):
        return self._sched

    def __len__(self):
        return len(self._pts)

    def __iter__(self):
        return iter(self._pts)

    def __getitem__(self, i):
        return self._pts[i]

    def __eq__(self, other):
        if not isinstance(other, Shape):
            return NotImplemented
        return self._pts == other._pts and self._sched == other._sched

    def __ne__(self, other):
        r = self.__eq__(other)
        return r if r is NotImplemented else not r

    def __hash__(self):
        return self._hash

    def __repr__(self):
        extra = "" if self._sched is None else ", 스케줄 %d밴드" % len(self._sched)
        return "<Shape %s점 %d%s>" % ((self.name + " ") if self.name else "", len(self._pts), extra)

    def bounds(self):
        """(최소 x, 최소 y, 최대 x, 최대 y) — 정수 점 기준. 점이 없으면 None."""
        if not self._pts:
            return None
        xs = [p[0] for p in self._pts]
        ys = [p[1] for p in self._pts]
        return min(xs), min(ys), max(xs), max(ys)

    # --- 스케줄 ---
    def with_schedule(self, counts):
        """같은 점에 LoopMax 스케줄(사이클별 점 수, 원본 `{밴드 수, c1, …}` 의 c 부분)을 붙인 새 Shape.

        인자: counts(0 이상 정수 목록, 비면 오류. 합이 점 수보다 작으면 마지막 밴드가 되풀이된다 — 그 값이 0 이면 오류)
        반환: Shape
        비용: 스케줄 배열 (밴드 수 + 1) × 4B
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `const s2 = ring.with_schedule(list(1, 6, 12, 18));`
        출처: CAPlotIndexed LoopMax(CAPI:140~146, 232~237), S1 6.2
        """
        return Shape(self._raw, schedule=counts, name=self.name)

    def sweep(self, mode="right", px_per_cycle=32):
        """한 방향으로 쓸고 지나가는 순서로 정렬하고, 선단이 사이클마다 px_per_cycle 픽셀씩 나아가는 스케줄을 붙인 새 Shape.

        theSeed `GunFadeShape` 와 같다: 정렬 기준 값(자)이 작은 점이 먼저(같으면 원래 순서 — 안정 정렬), 밴드 =
        floor((자 − 최솟값) / px_per_cycle) + 1, **빈 밴드는 0 으로 남긴다**(그 사이클은 쉰다 → 속도가 밀도와 무관).
        자는 자르기 전 좌표(`raw`)로 잰다(원본과 같음).
        인자: mode("right" 왼→오 | "left" 오→왼 | "in" 바깥→안(|x|) | "out" 안→바깥(|x|) | "down" 위→아래 | "up" 아래→위),
              px_per_cycle(양수)
        반환: Shape (새 객체 — 원본과 다른 sid 를 받는다)
        비용: 스케줄 배열 (밴드 수 + 1) × 4B
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `const fade = ring.sweep("right", px_per_cycle=32);`
        출처: theSeed MapConfig/Shape.lua:938 GunFadeShape ("right"/"left"/"in"), "out"/"down"/"up" 은 같은 규칙의 확장
        """
        check_choice("Shape.sweep mode", mode, SWEEP_MODES)
        ppc = unProxy(px_per_cycle)
        if isinstance(ppc, bool) or not isinstance(ppc, (int, float)) or not ppc > 0:
            fail("Shape.sweep: px_per_cycle 은 양수여야 합니다 (%r)", px_per_cycle)
        keyf = {
            "right": lambda p: p[0],
            "left": lambda p: -p[0],
            "in": lambda p: -abs(p[0]),
            "out": lambda p: abs(p[0]),
            "down": lambda p: p[1],
            "up": lambda p: -p[1],
        }[mode]
        for p in self._raw:
            if any(isinstance(v, float) and math.isnan(v) for v in p):
                fail("Shape.sweep: NaN 좌표가 있어 정렬할 수 없습니다 (CS_FixShape 로 먼저 고치세요)")
        order = sorted(range(len(self._raw)), key=lambda i: keyf(self._raw[i]))  # sorted 는 안정 정렬
        pts = [self._raw[i] for i in order]
        counts = []
        if pts:
            lo = keyf(pts[0])
            for p in pts:
                b = int(math.floor((keyf(p) - lo) / ppc)) + 1
                while len(counts) < b:
                    counts.append(0)
                counts[b - 1] += 1
        else:
            counts = [0]
        name = "%s~%s%s" % (self.name or "shape", mode, ppc)
        if not pts:
            s = Shape((), name=name)
            s._sched = (0,)
            s._hash = hash((s._pts, s._sched))
            return s
        return Shape(pts, schedule=counts, name=name)

    # --- Lua ---
    def _key(self):
        return (self._pts, self._sched)


# =============================================================================================
# CX — lupa 다리
# =============================================================================================


class CX:
    """CB Paint 를 lupa 로 그대로 돌리는 컴파일 시점 런타임 하나.

    인자: lib_dir(CB Paint 폴더, 기본 = 환경 변수 `EUDEXT_CBPAINT_DIR` > 저장소 `reference/MapSource/Library`),
          extra(더 읽을 Lua 파일 — lib_dir 기준 상대 경로 또는 절대 경로. 예: `["CSMakeSpiral.lua", "CS_Addon.lua"]`,
          나중에 읽은 정의가 이긴다), seed(모든 파일을 읽은 뒤 `math.randomseed(seed)`, 기본 0, None = 원본의 시각 시드),
          file_dir(CSSave·BMP 함수의 `FileDirectory`, 기본 = `EUDEXT_WORK`/cx_files), lib(주 파일 이름)
    메서드: `call(함수 이름, *인자)` → Shape, `invoke(함수 이름, *인자)` → 파이썬 값, `eval(식)` → Shape,
            `value(식)` → 파이썬 값, `run(코드)`, `run_file(경로)`,
            `get(전역 이름)` → Shape, `shape(lupa 표)` → Shape, `reseed(seed)`, `to_lua(값)`, `lua`(런타임), `globals`
    인자 변환: list/tuple → Lua 표(재귀), dict → 표, Shape → `{n, {x,y}, …}`(자르기 전 좌표 `raw` — Lua 안에서 이어 계산한
              것과 같다), None → nil
    반환: Shape 는 표의 `[1]` 개 점만 읽는다(Hollow). 좌표는 TEP 규칙으로 자른다(모듈 설명)
    비용: 트리거 0 (컴파일 시점). CB Paint 적재 약 0.06초, 1,700점 원 0.006초(R4b B3)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const cx = shape.CX(seed=1234);` → `const ring = cx.call("CSMakeCircle", 6, 32, 0, 37, 0);`
    출처: R4b B2·B3, 실험 `docs/proto/lupa_cbpaint_exp.py`, DPS a7aad90 `eud/ctrig/luart.py`
    """

    def __init__(self, lib_dir=None, extra=(), seed=0, file_dir=None, lib=LIB_FILE):
        if lib_dir is None:
            lib_dir = os.environ.get("EUDEXT_CBPAINT_DIR") or DEFAULT_LIB_DIR
        self.lib_dir = os.path.abspath(lib_dir)
        if file_dir is None:
            import tempfile

            work = os.environ.get("EUDEXT_WORK") or os.path.join(tempfile.gettempdir(), "eudext_work")
            file_dir = os.path.join(work, "cx_files")
        os.makedirs(file_dir, exist_ok=True)
        self.file_dir = file_dir
        self.lua = new_lua_runtime()
        install_tep_shims(self.lua, file_dir)
        with lua_c_locale():
            self._pack = self.lua.execute(_SHAPE_PACK_LUA)
        self._lua_type = import_lupa().lua_type
        self.files = []
        main = lib if os.path.isabs(lib) else os.path.join(self.lib_dir, lib)
        if not os.path.isfile(main):
            fail("CX: CB Paint 파일이 없습니다: %s (lib_dir 또는 환경 변수 EUDEXT_CBPAINT_DIR 로 폴더를 알려 주세요)", main)
        self._load(main)
        if isinstance(extra, str):
            extra = [extra]
        for e in extra:
            p = e if os.path.isabs(e) else os.path.join(self.lib_dir, e)
            if not os.path.isfile(p):
                fail("CX: extra 파일이 없습니다: %s", p)
            self._load(p)
        self.seed = seed
        if seed is not None:
            self.reseed(seed)

    def __repr__(self):
        return "<shape.CX %s (+%d) seed=%r>" % (os.path.basename(self.files[0]), len(self.files) - 1, self.seed)

    # --- 내부 ---
    def _err(self, what, e):
        text = str(e)
        try:
            text = text.encode("latin-1").decode("utf-8")  # Lua 쪽 UTF-8 바이트열을 되돌린다
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        text = text.strip().splitlines()
        raise EudextError("CX %s: Lua 오류: %s" % (what, " / ".join(text[:6]))) from None

    def _load(self, path):
        lua54 = import_lupa()
        try:
            r = lua_load_file(self.lua, path)
        except lua54.LuaError as e:
            self._err("파일 %s" % os.path.basename(path), e)
        self.files.append(path)
        return r

    @property
    def globals(self):
        return self.lua.globals()

    def reseed(self, seed):
        """`math.randomseed(seed)` (정수). 출처: R4b B2 (원본은 로드 때 os.time 시드)."""
        seed = unProxy(seed)
        if isinstance(seed, bool) or not isinstance(seed, int):
            fail("CX.reseed: 정수 시드여야 합니다 (%r)", seed)
        with lua_c_locale():
            self.lua.globals().math.randomseed(seed)
        self.seed = seed

    def to_lua(self, value):
        """파이썬 값 → Lua 값 (클래스 설명의 인자 변환)."""
        value = unProxy(value)
        if value is None or isinstance(value, (bool, int, float, str, bytes)):
            if isinstance(value, bytes):
                return value.decode("latin-1")
            return value
        if isinstance(value, Shape):
            # 자르기 전 좌표(raw)를 넘긴다 — Lua 안에서 이어 계산한 것과 같은 결과
            t = self.lua.table(len(value))
            for k, (x, y) in enumerate(value.raw):
                t[k + 2] = self.lua.table(x, y)
            return t
        if self._lua_type(value) is not None:
            return value
        if isinstance(value, dict):
            return self.lua.table_from({k: self.to_lua(v) for k, v in value.items()})
        if isinstance(value, (list, tuple)):
            return self.lua.table_from([self.to_lua(v) for v in value])
        fail("CX: Lua 로 넘길 수 없는 값입니다 (%r)", value)

    def shape(self, value, name=None):
        """Lua 도형 표 `{n, {x,y}, …}` → Shape. 표의 [1] 개 점만 읽는다(Hollow 로 남은 뒤쪽 점은 버림)."""
        with lua_c_locale():
            n, data = self._pack(value)
        if n is None:
            if data == -1:
                fail("CX: 도형 표가 아닙니다 (%s%r) — {점 수, {x,y}, …} 꼴이어야 합니다", name + ": " if name else "",
                     self._lua_type(value) or value)
            if data == -2:
                fail("CX: 도형 %s 의 점 수가 0 이상 정수가 아닙니다", name or "")
            fail("CX: 도형 %s 의 %d 번째 점이 없거나 {x, y} 꼴이 아닙니다 (선언 점 수보다 표가 짧음)", name or "", data)
        raw = data.encode("latin-1")
        vals = struct.unpack("<%dd" % (len(raw) // 8), raw)
        pts = [(_as_num(vals[2 * k]), _as_num(vals[2 * k + 1])) for k in range(n)]
        return Shape(pts, name=name)

    # --- 공개 ---
    def call(self, fname, *args):
        """Lua 전역 함수 fname(*args) 를 불러 도형을 받는다. 예: `cx.call("CSMakeCircle", 6, 32, 0, 37, 0)`."""
        lua54 = import_lupa()
        f = self.lua.globals()[fname]
        if f is None:
            fail("CX.call: Lua 함수 %s 가 없습니다", fname)
        try:
            with lua_c_locale():
                r = f(*[self.to_lua(a) for a in args])
        except lua54.LuaError as e:
            self._err("%s(…)" % fname, e)
        if isinstance(r, tuple):
            r = r[0] if r else None
        return self.shape(r, name=fname)

    def invoke(self, fname, *args):
        """Lua 전역 함수를 불러 반환값을 파이썬 값으로 받는다(도형이 아닌 결과 — CSSave·CS_Level 등)."""
        lua54 = import_lupa()
        f = self.lua.globals()[fname]
        if f is None:
            fail("CX.invoke: Lua 함수 %s 가 없습니다", fname)
        try:
            with lua_c_locale():
                r = f(*[self.to_lua(a) for a in args])
        except lua54.LuaError as e:
            self._err("%s(…)" % fname, e)
        if isinstance(r, tuple):
            r = r[0] if r else None
        return lua_to_py(r)

    def value(self, expr):
        """Lua 식 하나의 값(파이썬 값으로 바꿈 — `lua_to_py`). 예: `cx.value("CS_Level('Star', 5, 3)")`."""
        lua54 = import_lupa()
        try:
            r = lua_load(self.lua, "return " + expr, "=(eudext 식)")
        except lua54.LuaError as e:
            self._err("식 %r" % expr, e)
        if isinstance(r, tuple):
            r = r[0] if r else None
        return lua_to_py(r)

    def eval(self, expr, name=None):
        """Lua 식 하나를 계산해 도형으로 받는다. 예: `cx.eval("CS_Rotate(CSMakeStar(5,72,60,0,15,0), 15)")`."""
        lua54 = import_lupa()
        try:
            r = lua_load(self.lua, "return " + expr, "=(eudext 식)")
        except lua54.LuaError as e:
            self._err("식 %r" % expr, e)
        if isinstance(r, tuple):
            r = r[0] if r else None
        return self.shape(r, name=name or expr[:40])

    def run(self, code, name="=(eudext)"):
        """Lua 코드 조각을 실행한다(전역 정의 등). 반환: 청크 반환값(lupa 값)."""
        lua54 = import_lupa()
        try:
            return lua_load(self.lua, code, name)
        except lua54.LuaError as e:
            self._err("코드 %s" % name, e)

    def run_file(self, path):
        """맵별 Lua 도형 파일을 그대로 실행한다(상대 경로는 지금 작업 폴더 기준, 없으면 lib_dir 기준). 반환: 청크 반환값."""
        p = path
        if not os.path.isabs(p) and not os.path.isfile(p):
            p = os.path.join(self.lib_dir, path)
        if not os.path.isfile(p):
            fail("CX.run_file: 파일이 없습니다: %s", path)
        return self._load(os.path.abspath(p))

    def get(self, name):
        """Lua 전역 변수 name 의 도형(`run_file` 로 정의한 것 등)."""
        v = self.lua.globals()[name]
        if v is None:
            fail("CX.get: Lua 전역 %s 가 없습니다", name)
        return self.shape(v, name=name)


def _as_num(v):
    if math.isfinite(v) and v == int(v):
        return int(v)
    return v


# =============================================================================================
# ShapeSet — 좌표표
# =============================================================================================

_live_words = weakref.WeakSet()


class _Lazy:
    """페이로드를 쓸 때 값을 정하는 칸 (인자 없는 함수)."""

    __slots__ = ("fn",)

    def __init__(self, fn):
        self.fn = fn


class _Words(EUDObject):
    """나중에 채워도 되는 dword 배열. 값: int, ConstExpr, 또는 `_Lazy`.

    SaveMap 이 모으기(CollectDependency)를 시작하면 굳고, 페이로드를 다 쓰면(두 번째 WritePayload — eudplib 0.81 은
    할당 단계와 쓰기 단계에서 한 번씩 부른다) 풀린다. 한 프로세스 여러 빌드에서 다음 빌드용으로 더할 수 있다.
    빌드가 도중에 실패하면 `reset_build_state` 가 푼다.
    """

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls)

    def __init__(self, label):
        super().__init__()
        self.label = label
        self.items = []
        self._state = 0  # 0 = 열림, 1 = 이 빌드가 모으는 중
        self._writes = 0
        _live_words.add(self)

    @property
    def frozen(self):
        return self._state == 1 and self._writes < 2

    def thaw(self):
        self._state = 0
        self._writes = 0

    def extend(self, values):
        if self.frozen:
            fail("ShapeSet(%s): 페이로드를 쓰는 동안에는 도형을 더할 수 없습니다", self.label)
        off = len(self.items)
        self.items.extend(values)
        return off

    def _values(self):
        out = []
        for v in self.items or [0]:
            if isinstance(v, _Lazy):
                v = v.fn()
            if isinstance(v, int):
                v &= M32
            out.append(v)
        return out

    def GetDataSize(self):  # noqa: N802
        if self._state == 0:
            self._state = 1
        return 4 * max(1, len(self.items))

    def CollectDependency(self, emitbuffer):  # noqa: N802
        self._state = 1
        self._writes = 0
        for v in self._values():
            if not isinstance(v, int):
                emitbuffer.WriteDword(v)

    def WritePayload(self, emitbuffer):  # noqa: N802
        self._state = 1
        run = []
        for v in self._values():
            if isinstance(v, int):
                run.append(v)
                continue
            if run:
                emitbuffer.WriteBytes(struct.pack("<%dI" % len(run), *run))
                run = []
            emitbuffer.WriteDword(v)
        if run:
            emitbuffer.WriteBytes(struct.pack("<%dI" % len(run), *run))
        self._writes += 1


@_compat.register_build_reset
def _thaw_words():
    # 한 프로세스 여러 빌드(시험): 빌드가 도중에 끊겼어도 다음 빌드에서는 다시 더할 수 있다
    for w in list(_live_words):
        w.thaw()


@functools.lru_cache(maxsize=None)
def _db_reader():
    """"db" 점 읽기 한 벌: EPD → (x, y). 비트 32개를 x(아래 16)·y(위 16)로 나눠 더하고 편향(0x8000)을 뺀다."""
    return f_readgen_epd(
        M32,
        ((-BIAS) & M32, lambda b: b if b <= 0xFFFF else 0),
        ((-BIAS) & M32, lambda b: b >> 16),
    )


@functools.lru_cache(maxsize=None)
def _varray_index_fn():
    """i → 144·i (i < 2¹⁶, 넘치면 아래 16비트만). 16비트 뺄셈 사슬."""

    @EUDFunc
    def vidx(i):
        r = EUDVariable()
        r << 0
        for k in range(15, -1, -1):
            # 조건 i ≥ 2^k 가 보장하므로 Subtract(포화)가 wrap 과 같다 (DESIGN 3.5-7)
            RawTrigger(conditions=i.AtLeast(1 << k), actions=[i.SubtractNumber(1 << k), r.AddNumber(VARRAY_STEP << k)])
        return r

    return vidx


def _as_int_or_var(x, fname, what):
    x = unProxy(x)
    if isinstance(x, bool):
        x = int(x)
    if isinstance(x, int):
        if not 0 <= x <= M32:
            fail("%s: %s 상수 %d 가 범위 밖입니다", fname, what, x)
        return x
    if _compat.is_var(x):
        return x
    if _compat.is_const(x):
        v = EUDVariable()
        v << x
        return v
    if _compat.is_varbase(x) or hasattr(x, "getValueAddr"):
        return f_dwread_epd(EPD(x.getValueAddr()))
    fail("%s: %s 로 쓸 수 없는 값입니다 (%r)", fname, what, x)


class ShapeSet:
    """도형 여러 개의 좌표표. 트리거 수가 도형 수·점 수와 무관하다(DESIGN 3.8).

    인자: shapes(Shape 목록 — 나중에 `add` 로 더해도 된다), storage("db" 4B/점 | "varray" 144B/점, 읽기 실행이 약 30 적음),
          dedupe(좌표 내용이 같으면 한 번만 싣기, 기본 True), name(표시용)
    메서드(컴파일 시점): `add(shape)` → sid(0부터), `sid_of(shape)`, `len(ss)`, `ss[sid]` → Shape, `shapes`,
          `stored_points`(실제로 실은 점 수), `data_bytes`, `max_count`
    메서드(실행): `count(sid)`, `start(sid)`, `schedule(sid)`, `lookup(sid)` → (start, count, schedule),
          `point_at(sid, i)`, `point_from(start, i)`, `read_at(cursor)` — sid·i 가 상수면 파이썬 값/상수식(트리거 0)
    커서: "db" 는 점의 EPD(다음 점 = +1), "varray" 는 원소 주소(다음 점 = +144). `step` 속성이 그 간격이다.
          start(sid) 가 첫 점의 커서다. 번호 간격은 plot·spawn 안에서만 쓴다(3.9).
    비용: 좌표 4B/점("db") 또는 144B/점("varray") + 도형당 12B(주소표 3칸) + 스케줄 (밴드+1)×4B. 트리거 0.
          읽기 비용은 메서드 설명.
    CP: 읽기는 CP 를 잠깐 옮기고 되돌린다("db" — eudplib f_readgen_epd). 바꾸지 않음
    로컬: 공유 안전
    epScript: `const shapes = shape.ShapeSet(list(ring, star));` → `const x, y = shapes.point_at(sid, i);`
    출처: theSeed CAPlotIndexed.lua(주소표로 도형 선택, 도형당 트리거 0 에 가깝게), R4b B5·B7, S1 11-3
    """

    dont_flatten = True

    def __init__(self, shapes=(), storage="db", dedupe=True, name=None):
        check_choice("ShapeSet storage", storage, STORAGES)
        if not isinstance(dedupe, bool):
            fail("ShapeSet: dedupe 는 True/False 여야 합니다 (%r)", dedupe)
        self.storage = storage
        self.dedupe = dedupe
        self.name = name or "shapes%d" % id(self)
        self.step = 1 if storage == "db" else VARRAY_STEP
        self._shapes = []
        self._by_obj = {}
        self._refs = []
        self._by_key = {}
        self._data = {}
        self._sched_off = {}
        self.stored_points = 0
        self.max_count = 0
        lbl = self.name
        self._pts = _Words(lbl + ".points") if storage == "db" else None
        self._scheds = _Words(lbl + ".schedules")
        self._tstart = _Words(lbl + ".start")
        self._tcount = _Words(lbl + ".count")
        self._tsched = _Words(lbl + ".schedule")
        self._hdr = _Words(lbl + ".n")
        self._hdr.extend([_Lazy(lambda: len(self._shapes))])
        self._fns = {}
        if storage == "varray":
            self._rx = EUDVariable()
            self._ry = EUDVariable()
            PushTriggerScope()
            self._tramp = RawTrigger(nextptr=0)  # 원소 y 뒤에 오는 곳 (읽는 자리가 next 를 고친다)
            self._jump = RawTrigger(nextptr=0)  # 커서 값을 next 에 받아 원소로 점프
            PopTriggerScope()
        if isinstance(shapes, (Shape, str)) or not hasattr(shapes, "__iter__"):
            fail("ShapeSet: shapes 는 Shape 목록이어야 합니다 (%r)", shapes)
        for s in shapes:
            self.add(s)

    def __repr__(self):
        return "<ShapeSet %s: 도형 %d, 점 %d (%s)>" % (self.name, len(self._shapes), self.stored_points, self.storage)

    # --- 컴파일 시점 ---
    def __len__(self):
        return len(self._shapes)

    def __getitem__(self, sid):
        return self._shapes[sid]

    @property
    def shapes(self):
        return tuple(self._shapes)

    @property
    def data_bytes(self):
        """좌표 바이트 수(주소표·스케줄 제외)."""
        return self.stored_points * (4 if self.storage == "db" else 2 * 72)

    def sid_of(self, shape):
        """이미 넣은 도형의 sid. 없으면 EudextError."""
        sid = self._by_obj.get(id(shape))
        if sid is None and self.dedupe and isinstance(shape, Shape):
            sid = self._by_key.get(shape._key())
        if sid is None:
            fail("ShapeSet %s: 넣지 않은 도형입니다 (%r)", self.name, shape)
        return sid

    def add(self, shape):
        """도형을 넣고 sid(0부터)를 돌려준다. 같은 객체는 같은 sid, dedupe 면 같은 내용도 같은 sid.

        인자: shape(Shape — (x, y) 목록이면 Shape 로 바꾼다)
        반환: int
        비용: 없음(컴파일 시점). SaveMap 이 페이로드를 쓰기 시작한 뒤에 부르면 EudextError
        """
        if not isinstance(shape, Shape):
            if isinstance(shape, (list, tuple)):
                shape = Shape(shape)
            else:
                fail("ShapeSet.add: Shape 가 아닙니다 (%r)", shape)
        sid = self._by_obj.get(id(shape))
        if sid is None:
            for w in self._words():
                if w.frozen:
                    fail("ShapeSet %s: 페이로드를 쓰기 시작한 뒤에는 도형을 더할 수 없습니다 (%r)", self.name, shape)
        if sid is not None:
            return sid
        key = shape._key()
        if self.dedupe and key in self._by_key:
            sid = self._by_key[key]
            self._by_obj[id(shape)] = sid
            self._refs.append(shape)  # id 가 다른 객체에 다시 쓰이지 않게 붙잡아 둔다
            return sid
        pts = shape.points
        start = self._data.get(pts) if self.dedupe else None
        if start is None:
            start = self._store(pts, shape)
            if self.dedupe:
                self._data[pts] = start
        sched = 0
        if shape.schedule is not None:
            counts = shape.schedule
            off = self._sched_off.get(counts) if self.dedupe else None
            if off is None:
                off = self._scheds.extend((len(counts),) + counts)
                if self.dedupe:
                    self._sched_off[counts] = off
            sched = EPD(self._scheds) + off
        sid = len(self._shapes)
        self._tstart.extend([start])
        self._tcount.extend([len(pts)])
        self._tsched.extend([sched])
        self._shapes.append(shape)
        self._refs.append(shape)
        self._by_obj[id(shape)] = sid
        if self.dedupe:
            self._by_key[key] = sid
        self.max_count = max(self.max_count, len(pts))
        return sid

    def _words(self):
        return [w for w in (self._pts, self._scheds, self._tstart, self._tcount, self._tsched, self._hdr) if w is not None]

    def _store(self, pts, shape):
        self.stored_points += len(pts)
        if self.storage == "db":
            words = []
            for x, y in pts:
                if not COORD_MIN <= x <= COORD_MAX or not COORD_MIN <= y <= COORD_MAX:
                    fail("ShapeSet %s: 도형 %r 의 점 (%d, %d) 이 저장 범위(−32768 ~ 32767) 밖입니다 (storage='varray' 는 32비트)",
                         self.name, shape, x, y)
                words.append((x + BIAS) | ((y + BIAS) << 16))
            off = self._pts.extend(words)
            return EPD(self._pts) + off
        if not pts:
            return 0
        fw = Forward()
        triples = []
        for k, (x, y) in enumerate(pts):
            triples.append((self._rx, x & M32, fw + 72 * (2 * k + 1)))
            triples.append((self._ry, y & M32, self._tramp))
        fw << _compat.custom_varray(triples)
        return fw

    # --- sid 해석 ---
    def resolve(self, sid, fname="ShapeSet.resolve"):
        """도형 번호 해석: `Shape` 이면 등록(같은 객체는 같은 번호)하고 번호를, 정수면 범위를 검사해 그대로, 변수면 그대로 돌려준다.

        인자: sid(Shape | 0부터 정수 | EUDVariable), fname(오류 문구에 쓸 호출 이름)
        반환: int 또는 EUDVariable
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 공유 안전
        epScript: 쓰지 않는다(spawn 등 다른 모듈이 부른다)
        출처: WP12 요청으로 `_sid` 를 공개 이름으로 올림
        """
        return self._sid(sid, fname)

    def _sid(self, sid, fname):
        if isinstance(sid, Shape):
            return self.add(sid)
        sid = unProxy(sid)
        if isinstance(sid, bool):
            sid = int(sid)
        if isinstance(sid, int):
            if not 0 <= sid < len(self._shapes):
                fail("%s: 도형 번호 %d 가 범위 밖입니다 (도형 %d개, 0부터)", fname, sid, len(self._shapes))
            return sid
        return _as_int_or_var(sid, fname, "sid")

    def _const_start(self, sid):
        return self._tstart.items[sid]

    def _const_sched(self, sid):
        return self._tsched.items[sid]

    def _table_fn(self, which):
        fn = self._fns.get(which)
        if fn is not None:
            return fn
        tables = {"start": [self._tstart], "count": [self._tcount], "schedule": [self._tsched],
                  "all": [self._tstart, self._tcount, self._tsched]}[which]
        hdr = self._hdr

        @EUDFunc
        def look(sid):
            outs = [EUDVariable() for _ in tables]
            # 범위 검사: [도형 수 ≤ sid] 이면 빈 도형 (amount 는 실행 중에 채운다 — Forward 자리 표시, DESIGN 3.4)
            cond = MemoryEPD(EPD(hdr), AtMost, _parts.placeholder())
            SeqCompute([(EPD(cond) + 2, SetTo, sid)])
            if EUDIf()(cond):
                SeqCompute([(o, SetTo, 0) for o in outs])
            if EUDElse()():
                for o, t in zip(outs, tables):
                    f_dwread_epd(EPD(t) + sid, ret=[o])
            EUDEndIf()
            return outs[0] if len(outs) == 1 else tuple(outs)

        self._fns[which] = look
        return look

    # --- 실행 ---
    def count(self, sid):
        """도형의 점 수. 상수 sid → 파이썬 정수(트리거 0), 변수 → EUDVariable(범위 밖이면 0).

        비용: 변수 sid 본문 8(ShapeSet 마다 1벌, eudplib 읽기 함수 제외) / 호출 1 / 실행 약 47(범위 밖 약 11)
        epScript: `const n = shapes.count(sid);`
        """
        s = self._sid(sid, "ShapeSet.count")
        if isinstance(s, int):
            return len(self._shapes[s].points)
        return self._table_fn("count")(s)

    def start(self, sid):
        """첫 점의 커서("db" = EPD, "varray" = 원소 주소). 상수 sid → 상수식, 변수 → EUDVariable(범위 밖이면 0).

        비용: `count` 와 같다. epScript: `const c = shapes.start(sid);`
        """
        s = self._sid(sid, "ShapeSet.start")
        if isinstance(s, int):
            return self._const_start(s)
        return self._table_fn("start")(s)

    def schedule(self, sid):
        """LoopMax 스케줄 배열의 EPD(칸 0 = 밴드 수, 칸 k = k 번째 사이클 점 수). 없으면 0.

        비용: `count` 와 같다. epScript: `const e = shapes.schedule(sid);`
        """
        s = self._sid(sid, "ShapeSet.schedule")
        if isinstance(s, int):
            return self._const_sched(s)
        return self._table_fn("schedule")(s)

    def lookup(self, sid, *, ret=None):
        """(start, count, schedule) 를 한 번에. 변수 sid 는 본문 12(1벌, 읽기 함수 제외) / 호출 1 / 실행 약 127(범위 밖 약 15).

        상수 sid 는 (상수식, 정수, 상수식 또는 0). spawn 이 작업을 넣을 때 캐시하는 용도.
        epScript: `const st, n, sc = shapes.lookup(sid);`
        """
        s = self._sid(sid, "ShapeSet.lookup")
        if isinstance(s, int):
            vals = (self._const_start(s), len(self._shapes[s].points), self._const_sched(s))
            if ret is None:
                return vals
            SeqCompute([(unProxy(r), SetTo, v) for r, v in zip(ret, vals)])
            return tuple(ret)
        if ret is None:
            return self._table_fn("all")(s)
        return self._table_fn("all")(s, ret=list(ret))

    def read_at(self, cursor, *, ret=None):
        """커서가 가리키는 점 (x, y) — 부호 있는 32비트 EUDVariable 두 개.

        인자: cursor(상수식 또는 EUDVariable — `start()` + k·`step`), ret([x 변수, y 변수], 선택)
        반환: (x, y)
        비용: "db" = eudplib 읽기 본문 36(모든 ShapeSet 이 1벌 공유) / 호출 2 / 실행 약 40.
              "varray" = 호출 3~4 / 실행 약 9 (원소 사슬로 점프, ShapeSet 의 x·y 받는 변수에서 복사)
        CP: 바꾸지 않음("db" 는 잠깐 옮겼다 되돌림)
        epScript: `const x, y = shapes.read_at(c);`
        """
        cur = unProxy(cursor)
        if self.storage == "db":
            if ret is None:
                return _db_reader()(cur)
            return _db_reader()(cur, ret=[unProxy(r) for r in ret])
        cont = Forward()
        if _compat.is_var(cur):
            RawTrigger(
                nextptr=cur.GetVTable(),
                actions=[
                    cur.QueueAssignTo(EPD(self._jump) + 1),
                    SetNextPtr(cur.GetVTable(), self._jump),
                    SetNextPtr(self._tramp, cont),
                ],
            )
        else:
            RawTrigger(nextptr=self._jump, actions=[SetNextPtr(self._jump, cur), SetNextPtr(self._tramp, cont)])
        cont << NextTrigger()
        if ret is None:
            x, y = EUDVariable(), EUDVariable()
        else:
            x, y = (unProxy(r) for r in ret)
        SeqCompute([(x, SetTo, self._rx), (y, SetTo, self._ry)])
        return x, y

    def point_from(self, start, i, *, ret=None):
        """start(첫 점 커서)에서 i 번째 점 (x, y). i 는 도형의 점 수보다 작아야 한다(검사하지 않는다).

        비용: `read_at` + 커서 계산("db" 변수 i: 트리거 1, "varray" 변수 i: 곱 본문 19 / 실행 약 20)
        epScript: `const x, y = shapes.point_from(st, i);`
        """
        st = unProxy(start)
        iv = _as_int_or_var(i, "ShapeSet.point_from", "i")
        if isinstance(iv, int):
            cur = st + iv * self.step
        elif self.storage == "db":
            cur = iv + st
        else:
            cur = _varray_index_fn()(iv)
            cur += st
        return self.read_at(cur, ret=ret)

    def point_at(self, sid, i, *, ret=None):
        """도형 sid 의 i 번째 점 (x, y) — 상태 없는 읽기(spawn 이 씀, S1 11-3).

        인자: sid(0부터, 상수·변수), i(0부터, 상수·변수), ret([x, y] 변수, 선택)
        반환: 둘 다 상수면 파이썬 정수 (x, y)(ret 가 있으면 그 변수에 넣음), 아니면 EUDVariable 두 개.
              변수 sid 가 범위 밖이면 읽지 않고 (0, 0). i 는 점 수보다 작아야 한다(검사하지 않는다 — "varray" 는 원소 사슬
              밖으로 점프하므로 특히 주의)
        비용: 상수 sid = `point_from`(실행 42). 변수 sid = 주소표 읽기(`lookup`) + `point_from` — 실행 "db" 172, "varray" 163
              (도형 18개·3,900점 ShapeSet 에서도 같다).
              점마다 부르는 곳은 `lookup` 으로 start·count 를 한 번 받고 `point_from` 을 쓴다
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `const x, y = shapes.point_at(0, i);`
        출처: S1 11-3, CAPI:327~328 (시작 주소 + 점 번호)
        """
        s = self._sid(sid, "ShapeSet.point_at")
        iv = _as_int_or_var(i, "ShapeSet.point_at", "i")
        if not isinstance(s, int):
            # 범위 밖 sid 는 읽지 않고 (0, 0) — 주소표 밖·원소 사슬 밖으로 가지 않게
            st, n, _sc = self._table_fn("all")(s)
            if ret is None:
                x, y = EUDVariable(), EUDVariable()
            else:
                x, y = (unProxy(r) for r in ret)
            if EUDIf()(n.AtLeast(1)):
                self.point_from(st, iv, ret=[x, y])
            if EUDElse()():
                SeqCompute([(x, SetTo, 0), (y, SetTo, 0)])
            EUDEndIf()
            return x, y
        if isinstance(s, int):
            n = len(self._shapes[s].points)
            if n == 0:
                fail("ShapeSet.point_at: 도형 %d 에는 점이 없습니다 (읽을 수 없다)", s)
            if isinstance(iv, int):
                if not 0 <= iv < n:
                    fail("ShapeSet.point_at: 점 번호 %d 가 범위 밖입니다 (도형 %d 의 점 %d개)", iv, s, n)
                x, y = self._shapes[s].points[iv]
                if ret is None:
                    return x, y
                SeqCompute([(unProxy(ret[0]), SetTo, x & M32), (unProxy(ret[1]), SetTo, y & M32)])
                return tuple(ret)
        return self.point_from(self._const_start(s), iv, ret=ret)
