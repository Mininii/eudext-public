"""동기화 입력 — 선언을 모아 MSQC/NSQC eds 조각을 만들고, 받은 값을 펄스·레벨·걸쇠로 준다 (DESIGN 4.12, 7절 D7).

로컬 입력(`eudext.local`)은 각 PC 에서만 다르다. 공유 로직에 쓰려면 플러그인(MSQC/NSQC)이 숨긴 QC 유닛의
이동 명령에 실어 모든 PC 에 보낸다(R4b A3). 이 모듈은 **전송을 하지 않는다** — 선언을 받아 eds 줄을 만들고,
플러그인이 결과를 쓰는 `EUDArray` 를 읽는 도우미를 준다.

    from eudext import sync
    bus = sync.Bus("msqc", qc_unit=49)                       # 맵에서 안 쓰는 유닛 번호 (기본 58 은 위험)
    jump = bus.key_down("SPACE", guard=sync.not_typing(), level=True)
    mouse = local.track_mouse()
    mx = bus.value(mouse.x)                                   # 받은 사이클에만 갱신되는 걸쇠
    def beforeTriggerExec():
        sync.update()                                         # (훅 플러그인을 쓰면 필요 없음)
        for p in range(8):
            if EUDIf()(jump.pulse(p)): ...                    # 받은 사이클에만 참
            if EUDIf()(jump.level(p)): ...                    # Down/Up 짝으로 만든 누름 상태
            v = mx.get(p)                                     # 마지막으로 받은 값

**빌드 순서** (euddraft 는 eds 를 플러그인보다 먼저 읽는다 → 같은 빌드 안에서 조각을 반영할 수 없다, R4b A7):
1. 선언 모듈을 파이썬으로 실행한다 — `sync.collect("main.eps", map_path=…)` (트리거는 만들지 않는다).
2. eds 를 쓴다 — `tools/edsgen.EdsDoc.add_sync(hook=True)` 또는 `bus.write_eds_fragment(path)`.
3. euddraft 를 돌린다 — `tools/build.py euddraft`. 빌드 안에서 `verify()` 가 [MSQC] 설정이 선언과 같은지 본다.

**받은 값의 성질** (INT 5.1, 3.5): 플러그인은 사람 플레이어마다 매 사이클 출력 칸을 지우고(펄스 0, 값 −1)
네트워크 턴이 실행된 사이클에만 채운다. 한 턴 안의 여러 프레임 값은 **마지막 것만** 남는다(같은 QC 유닛의
다른 키 엣지도 사라질 수 있다). 그래서
- `pulse(p)`: 그 사이클에만 참. 매 프레임 참을 가정하지 않는다.
- `level(p)`: Down 만 오면 1, Up 만 오면 0, 둘 다 오면 그대로(짝이 맞으면 원래 상태) — 엣지를 잃어도 다음 엣지에서 회복.
- `get(p)`(걸쇠): 받은 사이클에만 갱신한 마지막 값.

**출력 칸**
- MSQC: `EUDArray(8)`(플레이어별). 이름을 eudplib 네임스페이스에 `eudext_<버스>_<종류><번호>` 로 등록하고
  eds 에 그 이름을 쓴다 → 데스 유닛 예약이 필요 없다. 등록 객체는 값이 포인터인 사본이다(MSQC 0.11 의
  `_is_epd()` 분기가 경고 없이 맞는 EPD 를 얻는다 — `_compat.eudarray_ptr_view`).
- NSQC(0.9.10.11 판): eudplib 0.81 에서 ReceiveQC 의 `parseArray` 가 이름 문자열(배열 출력·값 원본 이름)을 만나면
  `isUnproxyInstance(v, EUDVArray(8))` 에서 TypeError 로 멈춘다(0.81 의 `EUDVArray(8)` 은 타입이 아니다, 실측)
  → **데스값 출력만** 쓰고, 값 원본은 **메모리 주소(정수)만** 받는다.
  `Bus("nsqc", deaths=range(…))` 로 맵에서 쓰지 않는 데스 유닛 번호를 준다. 데스 칸도 읽는 법은 같다(EPD = 유닛×12 + p).

**전송별 차이** (플러그인 원문 확인, 2026-09-16)

| | MSQC (euddraft 0.11.0.1 번들) | NSQC (0.9.10.11 판, 번들 없음 — 플러그인 폴더에 직접 넣는다) |
|---|---|---|
| 출력 | `EUDArray`(EPD·포인터 둘 다) — 이 모듈이 씀. VArray 는 플러그인 내부 클래스만 | 데스값만 (배열 출력은 0.81 에서 TypeError) |
| `val` 못 받은 사이클 | 배열 −1 (0 과 구분됨) | 데스값 0 (0 과 구분 안 됨 → 걸쇠·received 없음, `dword` 를 쓴다) |
| 키 엣지 캐시 | `Db(32)` (정상) | `EUDArray(8) + 오프셋//8` → **0.81 에서 배열 밖에 씀** → `key_down`/`key_up` 막음 |
| `dword` | 없음 | 있음 (QC 유닛 2마리, 못 받으면 에러코드) |
| `QCDummy` | 없음 | 항상 `Always(); val, 0x58A364 : 227` 을 더함(데스 유닛 227 예약) |
| 조건 | `KeyDown/KeyUp/KeyPress`, `MouseDown/Up/Press`, `NotTyping`, `0x주소, 비교, 값`, `0x주소, 비트`, eudplib 식 | + `MouseMoved`, `ScreenMoved`, `WideScreen` |

자체 전송(`transport="native"`)은 3단계 선택(DESIGN 4.12)이라 만들지 않았다. 같은 줄 문법을 받는 대체
플러그인(예: MapSource `SNQC`, `[SNQC]` 섹션)은 `TRANSPORTS` 에 한 줄을 더해 붙인다.

**금지**(3.9): SCR_DB 채널(`SCRDB_MSQC_*`)을 쓰는 맵에서 eudplib `IsPName`·`f_check_id` 계열 금지 —
그 계열이 P1 칸으로 0x58F524(= SCR_DB 채널 7)를 쓴다(`PNAME_LIGHTVAR_ADDR`).
"""

import os
import sys
import types

from eudplib import (
    EPD,
    AtLeast,
    AtMost,
    CurrentPlayer,
    EncodePlayer,
    EUDArray,
    EUDEndIf,
    EUDIf,
    EUDIfNot,
    EUDNot,
    EUDRegisterObjectToNamespace,
    Exactly,
    GetChkTokenized,
    GetEUDNamespace,
    GetLocationIndex,
    IsEUDVariable,
    LoadMap,
    MemoryEPD,
    RawTrigger,
    SetMemoryEPD,
    SetTo,
    f_dwread_epd,
    f_getcurpl,
)

from eudext import _compat
from eudext import local as _local
from eudext.errors import EudextError, fail, warn

__all__ = [
    "Bus",
    "DEFAULT_QC_UNIT",
    "Guard",
    "IDLE_VALUE",
    "MouseLocation",
    "NSQC_DUMMY_DEATH",
    "PNAME_LIGHTVAR_ADDR",
    "Pulse",
    "SCRDB_MSQC_ADDR",
    "SCRDB_MSQC_CHANNELS",
    "SCRDB_MSQC_DEATH",
    "TRANSPORTS",
    "Transport",
    "Value",
    "bit_guard",
    "buses",
    "collect",
    "eds_fragment",
    "eds_sections",
    "escape_key",
    "flag_guard",
    "guards",
    "hook_source",
    "key_held",
    "memory_guard",
    "mouse_held",
    "mouse_moved",
    "not_typing",
    "raw_guard",
    "screen_moved",
    "scrdb_msqc_lines",
    "update",
    "verify",
    "wide_screen",
    "write_eds_fragment",
    "write_hook",
]

# --- 한 곳에 모은 약속 값 (SCR_DB 도 여기 것을 쓴다, DESIGN 4.18 (d)) --------------------------
MSQC_WAYPOINT_BASE = 64 * 65537  # QC 유닛 moveTarget 기준값 (MSQC/NSQC)
IDLE_VALUE = 0xFFFFFFFF  # 값 채널을 받지 못한 사이클의 출력 (플러그인 vinit)
DEFAULT_QC_UNIT = 58  # 플러그인 기본 QCUnit(Valkyrie) — 맵에서 쓰면 크래시(theSeed EUDEditorEdsGen.lua:51~67)
NSQC_DUMMY_DEATH = 227  # NSQC 기본 QCDummy 데스 유닛
# SCR_DB 런처 레이아웃 7 과 약속한 MSQC 채널 (DPS build_eud.py:37~42, R2 3.1 (d))
SCRDB_MSQC_ADDR = 0x58F508
SCRDB_MSQC_DEATH = 21
SCRDB_MSQC_CHANNELS = 8
# eudplib 0.81 string/pname.py `_get_player_lightvar`: 유닛 436 의 P1 칸 = 0x58F524 = SCR_DB 채널 7
PNAME_LIGHTVAR_ADDR = 0x58F524
NAME_PREFIX = "eudext_"


class Transport:
    """전송 플러그인 한 종류의 성질 (섹션 이름, 플러그인 모듈 이름, 지원 기능). `TRANSPORTS` 표에 둔다.

    인자: name, section(eds 섹션), module(sys.modules 이름), dword, extra_guards, key_edges, settings, note, array_out
    반환: -
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: MSQC.py/NSQC.py 원문 비교 (모듈 머리말 표)
    """

    __slots__ = ("array_out", "dword", "extra_guards", "key_edges", "module", "name", "note", "section", "settings")

    def __init__(self, name, section, module, dword, extra_guards, key_edges, settings, note="", array_out=True):
        self.name = name
        self.section = section  # eds 섹션 이름
        self.module = module  # euddraft 가 sys.modules 에 올리는 이름
        self.dword = dword
        self.extra_guards = frozenset(extra_guards)
        self.key_edges = key_edges  # KeyDown/KeyUp 이 이 eudplib 판에서 안전한가
        self.settings = tuple(settings)  # 받는 설정 키
        self.note = note
        self.array_out = array_out  # EUDArray 출력을 받는가 (아니면 데스값)

    def __repr__(self):
        return "<sync.Transport %s>" % self.name


TRANSPORTS = {
    "msqc": Transport(
        "msqc", "MSQC", "MSQC", dword=False, extra_guards=(), key_edges=True,
        settings=("QCUnit", "QCLoc", "QCPlayer", "QC_XY", "QCDebug"),
        note="euddraft 0.11.0.1 번들 MSQC.py",
    ),
    "nsqc": Transport(
        "nsqc", "NSQC", "NSQC", dword=True, extra_guards=("MouseMoved", "ScreenMoved", "WideScreen"),
        key_edges=False, settings=("QCUnit", "QCLoc", "QCPlayer", "QC_XY", "QCDebug", "QCDummy"),
        note="euddraft 0.9.10.11 판 NSQC.py (0.11 번들에 없음). eudplib 0.81 에서 키 엣지·배열 출력이 깨져 데스값만 쓴다",
        array_out=False,
    ),
}


def f_escape_key(text):
    """eds 키에 쓸 수 있게 `\\`, `:`, `=` 앞에 역슬래시를 붙인다(euddraft readconfig 가 푼다 — 실측).

    인자: text(str)
    반환: str
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: euddraft 0.11 readconfig 키 정규식 `([^\\\\:=]|\\\\.)+` + 실측(`KeyDown(\\=)` → `KeyDown(=)`)
    """
    return str(text).replace("\\", "\\\\").replace(":", "\\:").replace("=", "\\=")


def _unescape_key(text):
    out = []
    it = iter(text)
    for ch in it:
        if ch == "\\":
            out.append(next(it, ""))
        else:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------------------------
# guard (보내는 쪽 조건) — eds 표기만 가진다
# ---------------------------------------------------------------------------------------------


class Guard:
    """보내는 쪽 조건 하나의 eds 표기(`NotTyping`, `KeyPress(LCTRL)`, `0x68C144, Exactly, 0` …).

    트리거 조건이 아니다 — 플러그인이 각 PC 에서 이 조건이 참일 때만 보낸다.
    인자: token(표기, ';' 금지), only(이 전송에서만 되는 조건이면 전송 이름)
    반환: -
    비용: 없음(선언)
    CP: 해당 없음
    로컬: 보내는 PC 의 조건
    epScript: `sync.not_typing()` 같은 함수로 만든다
    출처: MSQC onInit 조건 파서(312~411)
    """

    __slots__ = ("only", "token")

    def __init__(self, token, only=None):
        token = str(token).strip()
        if not token or "\n" in token or ";" in token:
            fail("sync guard 표기가 잘못됐습니다: %r (';' 는 여러 조건을 잇는 구분자라 쓸 수 없다 → sync.guards(…))", token)
        self.token = token
        self.only = only  # 이 전송에서만 되는 조건이면 전송 이름

    def __repr__(self):
        return "Guard(%r)" % self.token


class GuardList(tuple):
    """여러 guard 의 AND (epScript 에서 `[a, b]` 대신 `sync.guards(a, b)`)."""


def f_not_typing():
    """보내는 쪽 조건: 채팅 입력 중이 아닐 때 (eds `NotTyping`).

    인자: 없음
    반환: Guard
    비용: 보내는 쪽 조건 1 (트리거 조건 아님)
    CP: 해당 없음
    로컬: 보내는 PC 의 로컬 조건
    epScript: `bus.key_down("X", guard=sync.not_typing())`
    출처: MSQC/NSQC `NotTyping`
    """
    return Guard("NotTyping")


def f_key_held(key):
    """보내는 쪽 조건: 키를 누르고 있을 때 (eds `KeyPress(이름)`).

    인자: key(이름)
    반환: Guard
    비용: 보내는 쪽 조건 1
    CP: 해당 없음
    로컬: 보내는 PC 의 로컬 조건
    epScript: `guard=sync.key_held("LCTRL")`
    출처: MSQC `KeyPress`
    """
    return Guard("KeyPress(%s)" % _local.f_msqc_key_name(key))


def f_mouse_held(button):
    """보내는 쪽 조건: 마우스 버튼을 누르고 있을 때 (eds `MousePress(L)`).

    인자: button('L'/'R'/'M')
    반환: Guard
    비용: 보내는 쪽 조건 1
    CP: 해당 없음
    로컬: 보내는 PC 의 로컬 조건
    epScript: `guard=sync.mouse_held("R")`
    출처: MSQC `MousePress`
    """
    return Guard("MousePress(%s)" % _local.f_button_name(button))


def f_memory_guard(addr, cmp, value):
    """보내는 쪽 조건: `Memory(addr, cmp, value)` (eds `0x주소, 비교, 값`). 보통 로컬 메모리 주소를 쓴다.

    인자: addr(int), cmp(AtLeast/AtMost/Exactly 또는 그 이름), value(int)
    반환: Guard
    비용: 보내는 쪽 조건 1
    CP: 해당 없음
    로컬: 보내는 PC 에서 평가
    epScript: `guard=sync.memory_guard(0x58F450, "Exactly", 0)`
    출처: MSQC onInit 402~409 (`eval(c[1])`)
    """
    names = {id(AtLeast): "AtLeast", id(AtMost): "AtMost", id(Exactly): "Exactly"}
    if isinstance(cmp, str) and cmp in ("AtLeast", "AtMost", "Exactly"):
        name = cmp
    else:
        name = names.get(id(cmp))
    if name is None:
        fail("memory_guard: 비교는 AtLeast/AtMost/Exactly 입니다 (%r)", cmp)
    if not (isinstance(addr, int) and isinstance(value, int)):
        fail("memory_guard: 주소·값은 정수 상수입니다")
    return Guard("0x%X, %s, %d" % (addr & 0xFFFFFFFF, name, value & 0xFFFFFFFF))


def f_bit_guard(addr, bits):
    """보내는 쪽 조건: `MemoryX(addr, Exactly, bits, bits)` (eds `0x주소, 0x비트`).

    인자: addr(int), bits(0 아닌 int)
    반환: Guard
    비용: 보내는 쪽 조건 1
    CP: 해당 없음
    로컬: 보내는 PC 에서 평가
    epScript: `guard=sync.bit_guard(0x58F454, 0x10)`
    출처: MSQC onInit 405~407
    """
    if not (isinstance(addr, int) and isinstance(bits, int)) or not bits:
        fail("bit_guard: 주소·비트는 0 아닌 정수 상수입니다")
    return Guard("0x%X, 0x%X" % (addr & 0xFFFFFFFF, bits & 0xFFFFFFFF))


def f_raw_guard(text):
    """보내는 쪽 조건: 플러그인이 eval 하는 eudplib 조건 식 그대로 (예: `'Switch("Switch 210", Cleared)'`).

    식 안의 네임스페이스 이름(EUDRegisterObjectToNamespace)은 플러그인이 바꿔 넣는다. 조건은 **보내는 PC 에서**
    평가된다 — 공유 상태를 봐도 되고 로컬 값을 봐도 된다.
    인자: text(';' 없는 한 조건)
    반환: Guard
    비용: 보내는 쪽 조건 1
    CP: 해당 없음
    로컬: 보내는 PC 에서 평가
    epScript: `guard=sync.raw_guard('Switch("Switch 210", Cleared)')`
    출처: MSQC SendQC 875~880 `parseCond`, theSeed EUDEditorEdsGen.lua
    """
    return Guard(text)


def f_flag_guard(var, name=None):
    """보내는 쪽 조건: 변수 `var` 가 1 이상일 때. var 를 네임스페이스에 등록하고 `이름.AtLeast(1)` 을 쓴다.

    var 는 선언(모듈 import) 때 만든 EUDVariable/LocalValue 여야 한다(두 빌드에서 같은 이름).
    인자: var(EUDVariable), name(등록 이름, 기본 자동)
    반환: Guard
    비용: 보내는 쪽 조건 1
    CP: 해당 없음
    로컬: 보내는 PC 의 변수 값으로 평가 (로컬 변수 가능)
    epScript: `const f = local.LocalValue(); … guard=sync.flag_guard(f)`
    출처: MSQC SendQC `parseCond`
    """
    if not IsEUDVariable(var):
        fail("flag_guard: EUDVariable 이 아닙니다 (%r)", var)
    reg = _register_name(name or _auto_name("g"), var)
    return Guard("%s.AtLeast(1)" % reg)


def f_mouse_moved():
    """보내는 쪽 조건(NSQC 전용): 마우스가 움직였을 때 (eds `MouseMoved`).

    인자: 없음
    반환: Guard
    비용: 보내는 쪽 조건 1
    CP: 해당 없음
    로컬: 보내는 PC 의 로컬 조건
    epScript: `bus.when(sync.mouse_moved())`
    출처: NSQC 249~315
    """
    return Guard("MouseMoved", only="nsqc")


def f_screen_moved():
    """보내는 쪽 조건(NSQC 전용): 화면이 움직였을 때 (eds `ScreenMoved`).

    인자: 없음
    반환: Guard
    비용: 보내는 쪽 조건 1
    CP: 해당 없음
    로컬: 보내는 PC 의 로컬 조건
    epScript: `bus.when(sync.screen_moved())`
    출처: NSQC 249~315
    """
    return Guard("ScreenMoved", only="nsqc")


def f_wide_screen():
    """보내는 쪽 조건(NSQC 전용): 와이드 화면일 때 (eds `WideScreen`). 판정에 CenterView·로케이션 이동을 쓴다.

    인자: 없음
    반환: Guard
    비용: 보내는 쪽 조건 1 (NSQC 가 판정 코드를 넣는다)
    CP: 해당 없음
    로컬: 보내는 PC 의 로컬 조건
    epScript: `bus.when(sync.wide_screen())`
    출처: NSQC 317~402
    """
    return Guard("WideScreen", only="nsqc")


def f_guards(*items):
    """guard 여러 개를 AND 로 묶는다 (epScript 는 `[a, b]` 가 EUDArray 로 번역되므로 이것을 쓴다).

    인자: Guard / LocalCondition(표기 있는 것) / 문자열(raw) 들
    반환: GuardList
    비용: 없음(선언)
    CP: 해당 없음
    로컬: 보내는 PC 의 조건
    epScript: `guard=sync.guards(sync.not_typing(), sync.key_held("LCTRL"))`
    출처: 새로 작성
    """
    return GuardList(items)


def _guard_tokens(guard, transport):
    out = []

    def add(g):
        if g is None:
            return
        if isinstance(g, EUDArray):
            fail("guard 에 EUDArray 가 왔습니다 — epScript 의 `[a, b]` 는 배열로 번역됩니다. sync.guards(a, b) 를 쓰세요")
        if isinstance(g, (list, tuple)) and not isinstance(g, _local.LocalConditions):
            for x in g:
                add(x)
            return
        if isinstance(g, Guard):
            if g.only is not None and g.only != transport.name:
                fail("guard %s 는 %s 전용입니다 (이 버스: %s)", g.token, g.only, transport.name)
            tok = g.token
        elif isinstance(g, (_local.LocalCondition, _local.LocalConditions)):
            if g.eds is None:
                fail("이 로컬 조건은 MSQC/NSQC 표기가 없어 guard 로 쓸 수 없습니다 (%r) — sync.raw_guard/memory_guard 를 쓰세요", g)
            tok = g.eds
        elif isinstance(g, str):
            tok = g
            if "\n" in tok or not tok.strip():
                fail("guard 표기가 잘못됐습니다: %r", g)
        else:
            fail("guard 로 쓸 수 없는 값: %r (sync.not_typing() 같은 Guard, local.* 조건, 문자열)", g)
        for t in tok.split(";"):
            t = t.strip()
            if t and t not in out:
                out.append(t)

    add(guard)
    return out


# ---------------------------------------------------------------------------------------------
# 이름·배열
# ---------------------------------------------------------------------------------------------

_name_counter = [0]


def _auto_name(kind):
    _name_counter[0] += 1
    return "%sx_%s%d" % (NAME_PREFIX, kind, _name_counter[0])


def _register_name(name, obj):
    ns = GetEUDNamespace()
    if name in ns:
        if ns[name] is obj:
            return name
        fail("eudplib 네임스페이스에 %s 가 이미 있습니다 — 버스 이름(name=)을 바꾸세요", name)
    EUDRegisterObjectToNamespace(name, obj)
    return name


def _pidx(p):
    if IsEUDVariable(p):
        return p
    if p is CurrentPlayer:
        return f_getcurpl()
    try:
        code = EncodePlayer(p)
    except Exception:  # noqa: BLE001
        fail("플레이어가 아닙니다: %r", p)
    if code == 13:
        return f_getcurpl()
    if not (isinstance(code, int) and 0 <= code <= 7):
        fail("sync 출력은 플레이어 0~7 만 있습니다 (%r)", p)
    return code


def _humans():
    try:
        ownr = GetChkTokenized().getsection("OWNR")
    except Exception:  # noqa: BLE001 — 맵을 읽지 않은 경우
        return None
    return [p for p in range(8) if ownr[p] == 6]


def _in_euddraft():
    return "pluginLoader" in sys.modules and "applyeuddraft" in sys.modules


class _Array:
    """플레이어별 출력 칸 8개 + 플러그인용 이름."""

    __slots__ = ("arr", "epd", "name", "view")

    def __init__(self, init=0, name=None):
        self.arr = EUDArray([init & 0xFFFFFFFF] * 8)
        self.epd = _compat.eudarray_epd(self.arr)
        self.view = None
        self.name = None
        if name is not None:
            self.view = _compat.eudarray_ptr_view(self.arr)
            self.name = _register_name(name, self.view)

    def addr(self):
        """칸 0 의 주소 식 (시험용)."""
        return _compat.eudarray_addr(self.arr)


class _DeathReader:
    """데스 칸(유닛 u, 플레이어 p)을 EUDArray 처럼 읽는다: EPD = u×12 + p."""

    __slots__ = ("epd",)

    def __init__(self, unit):
        self.epd = unit * 12

    def geitem(self, p, v):
        return MemoryEPD(self.epd + p, AtLeast, v)

    def leitem(self, p, v):
        return MemoryEPD(self.epd + p, AtMost, v)

    def eqitem(self, p, v):
        return MemoryEPD(self.epd + p, Exactly, v)

    def neitem(self, p, v):
        return EUDNot(MemoryEPD(self.epd + p, Exactly, v))

    def __getitem__(self, p):
        return f_dwread_epd(self.epd + p)


class _DeathOut:
    """NSQC 출력 칸 = 데스 유닛 하나 (플레이어별 칸 12개 중 0~7)."""

    __slots__ = ("arr", "epd", "name", "unit")

    def __init__(self, unit):
        self.unit = unit
        self.arr = _DeathReader(unit)
        self.epd = unit * 12
        self.name = str(unit)

    def addr(self):
        return 0x58A364 + 4 * self.epd


# ---------------------------------------------------------------------------------------------
# 채널
# ---------------------------------------------------------------------------------------------


class _Channel:
    __slots__ = ("bus", "key", "kind", "out", "value")

    def __init__(self, bus, kind, key, out, value):
        self.bus = bus
        self.kind = kind
        self.key = key  # eds 키 (풀린 형태)
        self.out = out  # _Array
        self.value = value  # eds 값

    def line(self):
        return "%s : %s" % (f_escape_key(self.key), self.value)

    def __repr__(self):
        return "<sync.%s %s>" % (type(self).__name__, self.key)


class Pulse(_Channel):
    """펄스 채널 — 받은 사이클에만 `count(p)` 가 증가량(기본 1)이다. `Bus.key_down` 등이 만든다.

    `level=True` 로 만들면 Up 짝 채널(guard 없음)을 같이 선언하고 `level(p)` 를 준다.
    인자: (Bus 내부에서 만든다)
    반환: -
    비용: 출력 칸 EUDArray 1개(MSQC) 또는 데스 유닛 1개(NSQC), level 이면 상태 EUDArray 1개
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const jump = bus.key_down("SPACE");` → `jump.pulse(p)`
    출처: MSQC ReceiveQC 1053~1088
    """

    __slots__ = ("inc", "lvl", "up")

    def __init__(self, bus, kind, key, out, inc):
        super().__init__(bus, kind, key, out, "%s, %d" % (out.name, inc))
        self.inc = inc
        self.up = None
        self.lvl = None

    def pulse(self, p):
        """받은 사이클이면 참.

        인자: p — 0~7, 변수, CurrentPlayer
        반환: Condition (`MemoryEPD(칸, AtLeast, 1)`, p 가 변수면 eudplib 이 조건을 패치)
        비용: 조건 1 / p 가 CurrentPlayer·변수면 호출 자리 1~2
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `if (jump.pulse(p)) { … }`
        출처: MSQC ReceiveQC 배열 출력(1053~1086)
        """
        return self.out.arr.geitem(_pidx(p), 1)

    def count(self, p):
        """이번 사이클에 받은 값(0 또는 증가량)을 읽는다.

        인자: p — 0~7, 변수, CurrentPlayer
        반환: EUDVariable
        비용: 호출 자리 2 / 실행 37 (`f_dwread_epd`, 2026-09-16 측정)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `const n = fire.count(p);`
        출처: MSQC ReceiveQC (`f_dwadd_epd(칸, 증가량)`)
        """
        return self.out.arr[_pidx(p)]

    def level(self, p):
        """누름 상태(0/1). `level=True` 로 선언한 채널만. `update()` 뒤에 읽는다.

        인자: p — 0~7, 변수, CurrentPlayer
        반환: Condition (`MemoryEPD(상태 칸, Exactly, 1)`)
        비용: 조건 1 (if 포함 호출 자리 2 / 실행 1) / update() 에 사람마다 트리거 2
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `if (jump.level(p)) { … }`
        출처: GOTCHAS 6절(Down/Up 짝으로 레벨), INT 5.1
        """
        if self.lvl is None:
            fail("%s: level() 은 level=True 로 선언한 채널만 됩니다 (Up 짝 채널이 필요)", self.key)
        self.bus._touch(self)
        return self.lvl.arr.eqitem(_pidx(p), 1)

    def level_value(self, p):
        """누름 상태 값(0/1)을 읽는다. `level=True` 로 선언한 채널만.

        인자: p
        반환: EUDVariable
        비용: 호출 자리 2 / 실행 37
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `const held = jump.level_value(p);`
        출처: 새로 작성
        """
        if self.lvl is None:
            fail("%s: level_value() 는 level=True 로 선언한 채널만 됩니다", self.key)
        self.bus._touch(self)
        return self.lvl.arr[_pidx(p)]

    def _emit_update(self, players):
        if self.lvl is None:
            return
        d, u, lv = self.out.epd, self.up.out.epd, self.lvl.epd
        for p in players:
            RawTrigger(
                conditions=[MemoryEPD(d + p, AtLeast, 1), MemoryEPD(u + p, Exactly, 0)],
                actions=SetMemoryEPD(lv + p, SetTo, 1),
            )
            RawTrigger(
                conditions=[MemoryEPD(u + p, AtLeast, 1), MemoryEPD(d + p, Exactly, 0)],
                actions=SetMemoryEPD(lv + p, SetTo, 0),
            )


class Value(_Channel):
    """값 채널(`val`/`dword`) — 받지 못한 사이클의 출력은 `idle`(MSQC val: 0xFFFFFFFF, dword: 에러코드, NSQC val: 없음=0).

    인자: (Bus 내부에서 만든다)
    반환: -
    비용: 출력 칸 1개 + latch 면 EUDArray 1개
    CP: 바꾸지 않음
    로컬: 출력은 공유 안전
    epScript: `const mx = bus.value(mouse.x);` → `mx.get(p)`
    출처: MSQC ReceiveQC 1089~1135, NSQC 1529~1645
    """

    __slots__ = ("idle", "latch", "source")

    def __init__(self, bus, kind, key, out, value, idle, source, latch):
        super().__init__(bus, kind, key, out, value)
        self.idle = idle
        self.source = source
        self.latch = _Array(0) if latch else None

    def received(self, p):
        """이번 사이클에 값을 받았으면 참. (`pulse` 는 같은 함수)

        인자: p — 0~7, 변수, CurrentPlayer
        반환: Condition (val: `AtMost 0xFFFFFFFE`, dword: `EUDNot(Exactly 에러코드)`). NSQC val 은 오류(0 과 구분 불가)
        비용: 조건 1 (if 포함 호출 자리 2 / 실행 1)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `if (mx.received(p)) { … }`
        출처: MSQC vinit(1089~1109: 받기 전 −1)
        """
        if self.idle is None:
            fail("%s: NSQC val 출력(데스값)은 못 받은 사이클이 0 이라 received() 를 줄 수 없습니다 — dword() 를 쓰세요", self.key)
        i = _pidx(p)
        if self.idle == 0xFFFFFFFF:
            return self.out.arr.leitem(i, 0xFFFFFFFE)
        return self.out.arr.neitem(i, self.idle)

    pulse = received

    def raw(self, p):
        """이번 사이클의 출력 칸 그대로(못 받았으면 idle).

        인자: p
        반환: EUDVariable
        비용: 호출 자리 2 / 실행 37
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `const v = mx.raw(p);`
        출처: MSQC ReceiveQC
        """
        return self.out.arr[_pidx(p)]

    def get(self, p):
        """마지막으로 받은 값 (latch=True). latch=False 면 `raw(p)`.

        인자: p — 0~7, 변수, CurrentPlayer
        반환: EUDVariable
        비용: 호출 자리 2 / 실행 37 / update() 에 사람마다 트리거 3(받지 않은 사이클 실행 1, 받은 사이클 + 읽기 약 36)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `const v = mx.get(p);`
        출처: INT 7절 E(걸쇠), 새로 작성
        """
        if self.latch is None:
            return self.raw(p)
        self.bus._touch(self)
        return self.latch.arr[_pidx(p)]

    def _emit_update(self, players):
        if self.latch is None or self.idle is None:
            return
        o, la = self.out.epd, self.latch.epd
        for p in players:
            if self.idle == 0xFFFFFFFF:
                EUDIf()(MemoryEPD(o + p, AtMost, 0xFFFFFFFE))
            else:
                EUDIfNot()(MemoryEPD(o + p, Exactly, self.idle))
            f_dwread_epd(o + p, ret=[la + p])
            EUDEndIf()


class MouseLocation(_Channel):
    """`mouse` 줄 — 사람마다 연속 로케이션에 마우스 맵 좌표를 붙인다(플러그인이 로케이션을 옮긴다).

    MSQC 는 마우스·화면이 움직였을 때만 보내므로 로케이션은 마지막 받은 자리에 머문다(자연스러운 걸쇠).
    인자: (Bus.mouse_location 이 만든다)
    반환: -
    비용: QC 유닛 1마리/사람
    CP: 바꾸지 않음
    로컬: 공유 안전(로케이션은 모든 PC 에서 같다)
    epScript: `const cur = bus.mouse_location("MouseP1");`
    출처: MSQC 315~327, 1114~1120
    """

    __slots__ = ("first",)

    def __init__(self, bus, first):
        if isinstance(first, str):
            value = first
        else:
            value = str(first)
        super().__init__(bus, "mouse", "mouse", None, value)
        self.first = first

    def location(self, p):
        """플레이어 p 의 로케이션 번호(1부터). 맵을 읽은 뒤(빌드 중)에만 부른다.

        MSQC 규칙: 로케이션 = 첫 로케이션 + p − (가장 작은 사람 번호).
        인자: p(사람 플레이어 번호 상수)
        반환: int
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 공유 안전
        epScript: `const loc = cur.location(0);`
        출처: MSQC ReceiveQC 1119~1120 (`f_setloc(mouse_loc + cp)`)
        """
        first = GetLocationIndex(self.first) if isinstance(self.first, str) else self.first
        humans = self.bus._players()
        code = EncodePlayer(p)
        if not isinstance(code, int) or code not in humans:
            fail("mouse_location: 사람 플레이어 번호가 아닙니다 (%r, 사람 %s)", p, humans)
        return first + code - min(humans)


# ---------------------------------------------------------------------------------------------
# 버스
# ---------------------------------------------------------------------------------------------

_buses = []
_hook_active = False


class Bus:
    """동기화 선언 묶음 하나(= eds 섹션 하나의 내용). **모듈을 import 할 때(선언 시점)** 만든다.

    인자: transport("msqc"|"nsqc"), qc_unit(맵에서 쓰지 않는 유닛 번호·이름 — 꼭 주기를 권함),
          qc_loc(1부터 로케이션 번호; eds 에는 0부터로 쓴다), qc_player(0부터), qc_xy((x, y)),
          debug(True/False, 없으면 플러그인 기본 True), qc_dummy(NSQC 데스 유닛, 기본 227),
          name(네임스페이스 이름에 쓰는 영숫자, 기본 b0, b1 …), players(update 를 펼칠 플레이어, 기본 맵의 사람),
          allow_nsqc_key_edges(True 면 NSQC 에서도 key_down/key_up 허용 — 플러그인을 고친 경우만),
          deaths(NSQC 전용: 출력에 쓸 데스 유닛 — 번호 목록, 또는 정수 하나(그 번호부터 필요한 만큼 이어서).
                 맵에서 쓰지 않는 것, 채널마다 하나. 1~65535, QCDummy 제외)
    반환: Bus — 채널 선언 메서드(key_down …)와 eds 조각(eds_lines/eds_fragment)
    비용: 선언만(트리거 없음). 채널마다 EUDArray 1~3개(칸 8개), NSQC 는 데스 유닛 1개 + 상태 EUDArray
    CP: 해당 없음
    로컬: 공유 안전(출력은 모든 PC 에서 같다)
    epScript: `const bus = sync.Bus("msqc", qc_unit=49);`
    출처: R4b A7 스케치, MSQC.py onInit(253~475)
    """

    def __init__(self, transport="msqc", qc_unit=None, qc_loc=None, qc_player=None, qc_xy=None, debug=None,
                 qc_dummy=None, name=None, players=None, allow_nsqc_key_edges=False, deaths=None):
        t = TRANSPORTS.get(str(transport).lower())
        if t is None:
            if str(transport).lower() == "native":
                fail("transport='native'(자체 전송)는 3단계 선택 기능이라 아직 없습니다 (DESIGN 4.12)")
            fail("알 수 없는 전송 %r (가능: %s)", transport, ", ".join(sorted(TRANSPORTS)))
        self.transport = t
        if name is None:
            name = "b%d" % len(_buses)
        name = str(name)
        if not name.replace("_", "").isalnum() or not name.isascii():
            fail("Bus name 은 영문·숫자·밑줄만 됩니다 (%r)", name)
        for b in _buses:
            if b.name == name:
                fail("같은 이름의 Bus 가 이미 있습니다: %s", name)
        self.name = name
        self.settings = []
        if qc_unit is not None:
            if isinstance(qc_unit, bool) or not isinstance(qc_unit, (int, str)):
                fail("qc_unit 은 유닛 번호나 이름입니다 (%r)", qc_unit)
            self.settings.append(("QCUnit", str(qc_unit)))
        if qc_loc is not None:
            if isinstance(qc_loc, bool) or not isinstance(qc_loc, int) or qc_loc < 1:
                fail("qc_loc 은 1부터 세는 로케이션 번호입니다 (%r). 이름은 플러그인이 한 칸 어긋나게 읽어 받지 않는다", qc_loc)
            self.settings.append(("QCLoc", str(qc_loc - 1)))
        if qc_player is not None:
            code = EncodePlayer(qc_player)
            if not isinstance(code, int) or not 0 <= code <= 11:
                fail("qc_player 는 플레이어 0~11 입니다 (%r)", qc_player)
            self.settings.append(("QCPlayer", str(code)))
        if qc_xy is not None:
            x, y = qc_xy
            self.settings.append(("QC_XY", "%d, %d" % (x, y)))
        if debug is not None:
            self.settings.append(("QCDebug", "true" if debug else "false"))
        if qc_dummy is not None:
            if t.name != "nsqc":
                fail("qc_dummy 는 NSQC 전용입니다")
            self.settings.append(("QCDummy", str(qc_dummy)))
        self.qc_unit = qc_unit
        self.qc_dummy = qc_dummy
        self.players = None if players is None else [int(p) for p in players]
        self.allow_key_edges = bool(allow_nsqc_key_edges) or t.key_edges
        self._deaths = []
        self._death_base = None
        self._reserved = {NSQC_DUMMY_DEATH if qc_dummy is None else qc_dummy}
        if deaths is not None:
            if t.array_out:
                fail("deaths 는 NSQC 전용입니다 (MSQC 는 EUDArray 출력이라 데스 유닛이 필요 없다)")
            reserved = self._reserved
            if isinstance(deaths, int) and not isinstance(deaths, bool):
                if not 1 <= deaths <= 65535:
                    fail("deaths: 시작 번호는 1~65535 입니다 (%r)", deaths)
                self._death_base = deaths
                deaths = ()
            for u in deaths:
                if isinstance(u, bool) or not isinstance(u, int) or not 1 <= u <= 65535 or u in reserved:
                    fail("deaths: 1~65535 의 유닛 번호여야 하고 QCDummy(%s)와 겹치면 안 됩니다 (%r)", sorted(reserved), u)
                if u in self._deaths:
                    fail("deaths: 같은 번호가 두 번 있습니다 (%d)", u)
                self._deaths.append(u)
        self.channels = []
        self._by_key = {}
        self._count = 0
        self._raw = []
        self._touched = False
        _buses.append(self)

    def __repr__(self):
        return "<sync.Bus %s %s, 채널 %d>" % (self.name, self.transport.name, len(self.channels))

    # --- 선언 ---
    def _key(self, guard, token):
        toks = _guard_tokens(guard, self.transport)
        if token in toks:
            toks.remove(token)
        return "; ".join(toks + [token])

    def _new_name(self, kind):
        self._count += 1
        return "%s%s_%s%d" % (NAME_PREFIX, self.name, kind, self._count)

    def _out(self, kind, init):
        """출력 칸: MSQC = 이름 붙은 EUDArray, NSQC = 데스 유닛."""
        if self.transport.array_out:
            return _Array(init, self._new_name(kind))
        used = set()
        for b in _buses:
            if b.transport is self.transport:
                used.update(c.out.unit for c in b.channels if isinstance(getattr(c, "out", None), _DeathOut))
        cands = list(self._deaths)
        if self._death_base is not None:
            cands = range(self._death_base, 65536)
        for u in cands:
            if u not in used and u not in self._reserved:
                self._count += 1
                return _DeathOut(u)
        fail("%s 버스: 출력 데스 유닛이 모자랍니다 — Bus(..., deaths=range(…)) 로 맵에서 쓰지 않는 번호를 더 주세요 (지금 %s)",
             self.name, self._deaths)

    def _add(self, ch):
        other = _key_owner(self.transport, ch.key)
        if other is not None:
            fail("같은 eds 줄이 두 번 선언됐습니다: [%s] %s (%s)", self.transport.section, ch.key, other)
        self.channels.append(ch)
        self._by_key[ch.key] = ch
        return ch

    def _pulse(self, kind, token, guard, inc):
        if isinstance(inc, bool) or not isinstance(inc, int) or not 1 <= inc <= 0x7FFFFFFF:
            fail("inc 는 1 이상 정수입니다 (%r)", inc)
        key = self._key(guard, token)
        old = self._by_key.get(key)
        if old is not None and isinstance(old, Pulse) and old.inc == inc:
            return old
        out = self._out("p", 0)
        return self._add(Pulse(self, kind, key, out, inc))

    def _edge_ok(self, what):
        if not self.allow_key_edges:
            fail(
                "%s: NSQC(0.9.10.11 판)는 eudplib 0.81 에서 키 엣지 캐시(EUDArray(8)+오프셋//8)가 배열 밖에 씁니다. "
                "transport='msqc' 를 쓰거나 key_press 를 쓰세요 (플러그인을 고쳤다면 allow_nsqc_key_edges=True)",
                what,
            )

    def _with_level(self, ch, up_token, level):
        if not level:
            return ch
        if ch.lvl is None:
            ch.up = self._pulse(ch.kind + "_up", up_token, None, 1)
            ch.lvl = _Array(0)
        return ch

    def key_down(self, key, guard=None, level=False, inc=1):
        """키를 누르는 순간 → 플레이어별 펄스 (eds `guard; KeyDown(이름) : 배열, inc`).

        인자: key(이름), guard(보내는 쪽 조건), level(True 면 Up 짝도 선언 → `level(p)`), inc(증가량)
        반환: Pulse
        비용: 선언만. 비트 1(level 이면 2) — QC 유닛 하나에 맵 크기에 따라 20~26비트
        CP: 해당 없음
        로컬: 공유 안전(출력)
        epScript: `const jump = bus.key_down("SPACE", guard=sync.not_typing(), level=1);`
        출처: MSQC `KeyDown`, CtrigAsm 맵의 `MSQC_KeySet`/`MSQC_KeyInput`
        """
        self._edge_ok("key_down")
        name = _local.f_msqc_key_name(key)
        ch = self._pulse("key_down", "KeyDown(%s)" % name, guard, inc)
        return self._with_level(ch, "KeyUp(%s)" % name, level)

    def key_up(self, key, guard=None, inc=1):
        """키를 떼는 순간 → 플레이어별 펄스 (eds `guard; KeyUp(이름) : 출력, inc`). NSQC 는 막힌다.

        인자: key, guard, inc
        반환: Pulse
        비용: 선언만. 비트 1
        CP: 해당 없음
        로컬: 공유 안전(출력)
        epScript: `const rel = bus.key_up("SPACE");`
        출처: MSQC `KeyUp`
        """
        self._edge_ok("key_up")
        return self._pulse("key_up", "KeyUp(%s)" % _local.f_msqc_key_name(key), guard, inc)

    def key_press(self, key, guard=None, inc=1):
        """키를 누르고 있는 동안 → 턴마다 펄스 (eds `KeyPress(이름)`). 매 사이클 참이 아니다(INT 5.1).

        인자: key, guard, inc
        반환: Pulse
        비용: 선언만. 비트 1. 누르고 있는 동안 매 프레임 15바이트
        CP: 해당 없음
        로컬: 공유 안전(출력)
        epScript: `const hold = bus.key_press("LSHIFT");`
        출처: MSQC `KeyPress`
        """
        return self._pulse("key_press", "KeyPress(%s)" % _local.f_msqc_key_name(key), guard, inc)

    def mouse_down(self, button, guard=None, level=False, inc=1):
        """마우스 버튼을 누르는 순간 → 펄스 (eds `MouseDown(L)`). level=True 면 `MouseUp` 짝도 선언.

        인자: button('L'/'R'/'M'), guard, level, inc
        반환: Pulse
        비용: 선언만. 비트 1(level 이면 2)
        CP: 해당 없음
        로컬: 공유 안전(출력)
        epScript: `const fire = bus.mouse_down("L", guard=sync.not_typing());`
        출처: MSQC `MouseDown`
        """
        name = _local.f_button_name(button)
        ch = self._pulse("mouse_down", "MouseDown(%s)" % name, guard, inc)
        return self._with_level(ch, "MouseUp(%s)" % name, level)

    def mouse_up(self, button, guard=None, inc=1):
        """마우스 버튼을 떼는 순간 → 펄스 (eds `MouseUp(L)`).

        인자: button, guard, inc
        반환: Pulse
        비용: 선언만. 비트 1
        CP: 해당 없음
        로컬: 공유 안전(출력)
        epScript: `const up = bus.mouse_up("L");`
        출처: MSQC `MouseUp`
        """
        return self._pulse("mouse_up", "MouseUp(%s)" % _local.f_button_name(button), guard, inc)

    def mouse_press(self, button, guard=None, inc=1):
        """마우스 버튼을 누르고 있는 동안 → 턴마다 펄스 (eds `MousePress(L)`).

        인자: button, guard, inc
        반환: Pulse
        비용: 선언만. 비트 1
        CP: 해당 없음
        로컬: 공유 안전(출력)
        epScript: `const drag = bus.mouse_press("L");`
        출처: MSQC `MousePress`
        """
        return self._pulse("mouse_press", "MousePress(%s)" % _local.f_button_name(button), guard, inc)

    def when(self, guard, inc=1):
        """guard 조건들만으로 펄스 (예: `bus.when(sync.memory_guard(0x58F450, "Exactly", 0))`).

        guard 가 하나 이상 있어야 한다. 마지막 조건이 줄의 주 조건이 된다.
        인자: guard(하나 이상), inc
        반환: Pulse
        비용: 선언만. 비트 1
        CP: 해당 없음
        로컬: 공유 안전(출력)
        epScript: `const moved = bus.when(sync.mouse_moved());`
        출처: MSQC 조건 문법 (맨 조건 + 출력)
        """
        toks = _guard_tokens(guard, self.transport)
        if not toks:
            fail("when: 조건이 하나 이상 필요합니다")
        return self._pulse("when", toks[-1], toks[:-1], inc)

    def _source(self, src):
        if isinstance(src, bool):
            fail("값 채널의 원본이 아닙니다: %r", src)
        if isinstance(src, int):
            return "0x%X" % (src & 0xFFFFFFFF), src
        if IsEUDVariable(src):
            if not self.transport.array_out:
                fail("NSQC(0.9.10.11 판)는 eudplib 0.81 에서 원본 이름을 받으면 수신 코드가 TypeError 로 멈춥니다 "
                     "(parseArray 의 EUDVArray(8)) — 원본은 로컬 메모리 주소(정수)로 주세요")
            return _register_name(self._new_name("s"), src), src
        fail("값 채널의 원본은 주소(정수)나 선언 때 만든 변수(LocalValue/EUDVariable)입니다 (%r)", src)

    def value(self, src, latch=True, guard=None):
        """로컬 값을 보낸다 (eds `guard 또는 Always(); val, 원본 : 배열`).

        인자: src — 로컬 메모리 주소(int) 또는 선언 때 만든 변수(`local.track_mouse().x`, LocalValue),
              latch(True 면 `get(p)` = 마지막 받은 값), guard(보내는 쪽 조건, 기본 매 프레임)
        반환: Value — `received(p)`, `get(p)`, `raw(p)` (NSQC 는 latch=False 만, received 없음 — 못 받으면 0)
        비용: 선언만. QC 유닛 1마리/사람. 매 프레임 15바이트(guard 가 참일 때). update() 에 사람마다 분기 + 읽기
        CP: 해당 없음
        로컬: src 는 로컬(보내는 PC 값), 출력은 공유 안전
        epScript: `const mx = bus.value(mouse.x);`
        출처: MSQC `val` (보낼 수 있는 범위 0 ~ 맵에 따라 0x3FFFFF 등 — 빌드 로그 "Sendable value range")
        주의: 원본은 플러그인이 **다음 사이클 앞**에서 읽는다(맵 코드보다 먼저). 변수는 사이클마다 채워 둔다.
        """
        idle = IDLE_VALUE if self.transport.array_out else None
        if idle is None and latch:
            fail("NSQC val 은 데스값으로만 받아 0 과 '못 받음'을 구분할 수 없습니다 — latch=False 로 쓰거나 dword() 를 쓰세요")
        ref, obj = self._source(src)
        toks = _guard_tokens(guard, self.transport) or ["Always()"]
        key = "; ".join(toks + ["val, %s" % ref])
        out = self._out("v", IDLE_VALUE)
        return self._add(Value(self, "val", key, out, out.name, idle, obj, latch))

    def dword(self, src, error=0xFFFFFFFF, latch=True, guard=None):
        """32비트 전체를 보낸다 — **NSQC 전용** (eds `Always(); dword, 원본 : 출력, 0x에러코드`).

        받지 못한(두 반쪽이 다 오지 않은) 사이클의 출력은 error. 원래 값이 error 와 같으면 구분할 수 없다.
        NSQC 는 원본을 메모리 주소(정수)로만 받는다(0.81 에서 이름을 주면 수신 코드가 멈춘다).
        인자: src(주소), error(int), latch, guard
        반환: Value
        비용: QC 유닛 2마리/사람
        CP: 해당 없음
        로컬: src 는 로컬, 출력은 공유 안전
        epScript: `const wide = bus.dword(0x6CDDC4, error=0xFFFFFFFF);`
        출처: NSQC `dword`(573~589, 1336~1386, 1545~1645)
        """
        if not self.transport.dword:
            fail("dword 는 NSQC 전용입니다 (이 버스: %s) — 값 범위가 맞으면 value() 를 쓰세요", self.transport.name)
        if isinstance(error, bool) or not isinstance(error, int):
            fail("dword error 는 정수입니다 (%r)", error)
        error &= 0xFFFFFFFF
        ref, obj = self._source(src)
        toks = _guard_tokens(guard, self.transport) or ["Always()"]
        key = "; ".join(toks + ["dword, %s" % ref])
        out = self._out("d", error)
        return self._add(Value(self, "dword", key, out, "%s, 0x%X" % (out.name, error), error, obj, latch))

    def mouse_location(self, first_location):
        """사람마다 연속 로케이션에 마우스 맵 좌표를 붙인다 (eds `mouse : 로케이션`). 섹션에 하나만.

        인자: first_location — 첫 사람(가장 작은 번호)의 로케이션 이름 또는 1부터 번호. 나머지 사람은 번호가 이어진다
        반환: MouseLocation (`location(p)`)
        비용: QC 유닛 1마리/사람, 마우스·화면이 움직인 프레임에 15바이트
        CP: 해당 없음
        로컬: 공유 안전(로케이션)
        epScript: `const cur = bus.mouse_location("MouseP1");`
        출처: MSQC `mouse`(315~327, 1114~1120), NSQC 가이드북 27장
        """
        if isinstance(first_location, bool) or not isinstance(first_location, (int, str)):
            fail("mouse_location: 로케이션 이름이나 1부터 번호입니다 (%r)", first_location)
        if isinstance(first_location, int) and first_location < 1:
            fail("mouse_location: 로케이션 번호는 1부터입니다 (%r)", first_location)
        return self._add(MouseLocation(self, first_location))

    def raw(self, key, value):
        """eds 줄을 그대로 더한다(SCR_DB 채널 등).

        인자: key(풀린 형태, 예 `Memory(0x58F508,AtLeast,1); val, 0x58F508`), value(값 문자열)
        반환: None
        비용: 선언만
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `bus.raw("Always(); val, 0x58F500", "180");`
        출처: 새로 작성
        """
        key = str(key).strip()
        value = str(value).strip()
        if not key or not value or "\n" in key + value:
            fail("raw: 잘못된 줄 %r : %r", key, value)
        other = _key_owner(self.transport, key)
        if other is not None:
            fail("같은 eds 줄이 두 번 선언됐습니다: %s (%s)", key, other)
        self._raw.append((key, value))

    def scrdb_channels(self):
        """SCR_DB 런처 레이아웃 7 의 MSQC 채널 8줄을 더한다(데스 유닛 21~28 예약). 이 버스를 쓰는 맵은 IsPName 계열 금지(3.9).

        인자: 없음
        반환: None
        비용: 선언만. QC 유닛 8마리/사람
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `bus.scrdb_channels();`
        출처: DPS eudplib-port build_eud.py:37~42 (a7aad90)
        """
        if self.transport.name != "msqc":
            fail("SCR_DB 채널은 MSQC 줄 형식입니다")
        for key, value in _scrdb_pairs():
            self.raw(key, value)

    # --- eds ---
    def _pairs(self):
        out = [p for p in self.settings if p[0] != "QCDummy"]
        out.extend((ch.key, ch.value) for ch in self.channels)  # Up 짝은 Down 바로 뒤에 들어 있다
        out.extend(self._raw)
        out.extend(p for p in self.settings if p[0] == "QCDummy")
        return out

    def eds_lines(self):
        """이 버스의 eds 줄 목록(설정 줄 먼저, 키는 이스케이프한 형태, NSQC QCDummy 는 맨 끝).

        인자: 없음
        반환: [str]
        비용: 없음
        CP: 해당 없음
        로컬: 해당 없음
        epScript: 쓰지 않는다 (빌드 스크립트용)
        출처: 새로 작성
        """
        return ["%s : %s" % (f_escape_key(k), v) for k, v in self._pairs()]

    def eds_fragment(self):
        """`[MSQC]\n…` 형태의 eds 조각(이 버스만, 머리에 `::` 주석 줄). 여러 버스를 합칠 때는 `sync.eds_fragment()`.

        인자: 없음
        반환: str
        비용: 없음
        CP: 해당 없음
        로컬: 해당 없음
        epScript: 쓰지 않는다
        출처: DESIGN 4.12
        """
        return _render_section(self.transport, self._pairs())

    def write_eds_fragment(self, path):
        """eds 조각을 파일로 쓴다(빌드 스크립트가 euddraft 실행 전에 부른다).

        인자: path
        반환: path
        비용: 없음
        CP: 해당 없음
        로컬: 해당 없음
        epScript: 쓰지 않는다
        출처: DESIGN 4.12
        """
        return _write_text(path, self.eds_fragment())

    def describe(self, map_size=None, humans=None):
        """QC 유닛 수·프레임당 최대 바이트를 적은 설명 문자열.

        인자: map_size((가로, 세로) 타일, 선택), humans(사람 수, 선택)
        반환: str
        비용: 없음
        CP: 해당 없음
        로컬: 해당 없음
        epScript: 쓰지 않는다
        출처: INT 3.2(비트 예산)·5.2(대역폭), GB:7815
        """
        nbool = sum(1 for ch in self.channels if isinstance(ch, Pulse)) + sum(
            1 for k, _v in self._raw if "val," not in k and "xy," not in k and "dword," not in k
        )
        nval = sum(1 for ch in self.channels if isinstance(ch, (Value, MouseLocation)) and ch.kind != "dword")
        nval += sum(1 for k, _v in self._raw if "val," in k or "xy," in k)
        ndw = sum(1 for ch in self.channels if ch.kind == "dword")
        lines = ["[%s] 버스 %s: 펄스 %d, 값 %d, dword %d" % (self.transport.section, self.name, nbool, nval, ndw)]
        if map_size is not None:
            w, h = map_size
            bits = (h.bit_length() + 3) + (w.bit_length() + 3)
            groups = -(-nbool // bits) if nbool else 0
            units = groups + nval + 2 * ndw + (1 if self.transport.name == "nsqc" else 0)
            lines.append("  QC 유닛 %d×사람 (불리언 %d비트/유닛), 프레임당 최대 %d바이트 + 선택 복원 26" % (units, bits, 15 * units))
            if humans is not None:
                lines.append("  사람 %d명 → QC 유닛 %d마리" % (humans, units * humans))
        if self.qc_unit is None:
            lines.append("  주의: qc_unit 을 정하지 않았다 — 플러그인 기본 %d(Valkyrie)를 맵에서 쓰면 크래시" % DEFAULT_QC_UNIT)
        return "\n".join(lines)

    # --- 빌드 ---
    def _players(self):
        if self.players is not None:
            return list(self.players)
        h = _humans()
        return h if h else list(range(8))

    def _touch(self, ch):
        if self._touched or _hook_active:
            return
        self._touched = True
        on_main_done = getattr(_compat, "on_start_after_main", None)
        if on_main_done is not None and _compat_phase() == 1:
            on_main_done(_check_updated)

    def _emit_update(self):
        players = self._players()
        for ch in self.channels:
            ch_update = getattr(ch, "_emit_update", None)
            if ch_update is not None:
                ch_update(players)


def _compat_phase():
    fn = getattr(_compat, "onstart_phase", None)
    return fn() if fn is not None else 0


def _key_owner(transport, key):
    for b in _buses:
        if b.transport is not transport:
            continue
        if key in b._by_key:
            return "버스 %s" % b.name
        for k, _v in b._raw:
            if k == key:
                return "버스 %s raw" % b.name
        for k, _v in b.settings:
            if k == key:
                return "버스 %s 설정" % b.name
    return None


def _scrdb_pairs():
    return [
        ("Memory(0x%X,AtLeast,1); val, 0x%X" % (SCRDB_MSQC_ADDR + 4 * k, SCRDB_MSQC_ADDR + 4 * k), str(SCRDB_MSQC_DEATH + k))
        for k in range(SCRDB_MSQC_CHANNELS)
    ]


def f_scrdb_msqc_lines():
    """SCR_DB 런처 레이아웃 7 의 `[MSQC]` 8줄 (DPS build_eud.py 와 같은 뜻, 이 모듈이 단일 출처).

    인자: 없음
    반환: [str] — `Memory(0x58F508,AtLeast,1); val, 0x58F508 : 21` …
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: DPS eudplib-port build_eud.py:37~42 (a7aad90), R2 3.1 (d)
    """
    return ["%s : %s" % (f_escape_key(k), v) for k, v in _scrdb_pairs()]


# ---------------------------------------------------------------------------------------------
# 모듈 단위 도우미
# ---------------------------------------------------------------------------------------------


def f_buses(transport=None):
    """지금까지 선언된 Bus 목록(선언 순서).

    인자: transport(선택: 'msqc'/'nsqc')
    반환: [Bus]
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    if transport is None:
        return list(_buses)
    t = TRANSPORTS[str(transport).lower()]
    return [b for b in _buses if b.transport is t]


def _merged_pairs(transport, buses):
    pairs, seen = [], {}
    for b in buses:
        if b.transport is not transport:
            continue
        for k, v in b._pairs():
            if k in seen:
                if k in transport.settings and seen[k] == v:
                    continue
                fail("[%s] %s 설정이 버스마다 다릅니다 (%s / %s)", transport.section, k, seen[k], v)
            seen[k] = v
            pairs.append((k, v))
    # NSQC 0.9.10.11 은 QCDummy 를 찾으면 설정 dict 의 **마지막 키**를 지운다(onInit 436~437 버그)
    # → QCDummy 를 맨 끝에 두어야 QCDummy 자신이 지워진다.
    settings = [p for p in pairs if p[0] in transport.settings and p[0] != "QCDummy"]
    rest = [p for p in pairs if p[0] not in transport.settings]
    tail = [p for p in pairs if p[0] == "QCDummy"]
    return settings + rest + tail


def _render_section(transport, pairs):
    lines = [":: eudext.sync 가 만든 조각 (%s) — 손으로 고치지 말고 선언을 고친 뒤 다시 만든다" % transport.note,
             "[%s]" % transport.section]
    lines.extend("%s : %s" % (f_escape_key(k), v) for k, v in pairs)
    return "\n".join(lines) + "\n"


def f_eds_sections(buses=None):
    """전송별 eds 줄: {섹션 이름: [줄, …]} (여러 버스 합침, 설정 줄이 앞, 설정이 다르면 오류).

    인자: buses(기본: 모두)
    반환: dict
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다 (tools/edsgen 이 쓴다)
    출처: 새로 작성
    """
    buses = list(_buses) if buses is None else list(buses)
    out = {}
    for t in TRANSPORTS.values():
        pairs = _merged_pairs(t, buses)
        if pairs:
            out[t.section] = ["%s : %s" % (f_escape_key(k), v) for k, v in pairs]
    return out


def f_eds_fragment(buses=None):
    """선언된 버스들의 eds 조각 문자열(`[MSQC]…`, `[NSQC]…`).

    인자: buses(기본: 모두)
    반환: str
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: DESIGN 4.12
    """
    buses = list(_buses) if buses is None else list(buses)
    parts = []
    for t in TRANSPORTS.values():
        pairs = _merged_pairs(t, buses)
        if pairs:
            parts.append(_render_section(t, pairs))
    return "\n".join(parts)


def _write_text(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    return path


def f_write_eds_fragment(path, buses=None):
    """`eds_fragment()` 를 파일로 쓴다(CRLF).

    인자: path, buses(기본: 모두)
    반환: path
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: DESIGN 4.12
    """
    return _write_text(path, f_eds_fragment(buses))


def f_collect(path, map_path=None, settings=None):
    """선언 모듈(.py 또는 .eps)을 실행해 그 안에서 만든 Bus 를 돌려준다(빌드 스크립트 1단계).

    트리거 생성 함수(onPluginStart·beforeTriggerExec …)는 부르지 않는다. 모듈 최상위의 선언
    (`const bus = sync.Bus(…)`, `bus.key_down(…)`)만 실행된다. 모듈이 import 때 맵 정보를 쓰면 map_path 를 준다.
    .eps 는 `_compat.eps_compile` 로 번역해 실행한다(`__epspy__` 를 쓰지 않는다).
    인자: path, map_path(선택: LoadMap), settings(선택: 모듈 전역 settings)
    반환: [Bus]
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다 (빌드 스크립트용)
    출처: DESIGN 5.3 ①, theSeed EUDEditorEdsGen.lua (같은 한계를 빌드 스크립트로 푼다)
    """
    path = os.path.abspath(path)
    if map_path is not None:
        LoadMap(map_path)
    before = len(_buses)
    name = os.path.splitext(os.path.basename(path))[0]
    with open(path, "rb") as f:
        src = f.read()
    if path.endswith(".eps"):
        py, nerr = _compat.eps_compile(os.path.basename(path), src)
        if py is None or nerr:
            fail("collect: epScript 번역 실패 %s (오류 %d)", path, nerr)
        code = compile(py, path, "exec")
    else:
        code = compile(src, path, "exec")
    mod = types.ModuleType(name)
    mod.__dict__["settings"] = dict(settings or {})
    mod.__dict__["__file__"] = path
    d = os.path.dirname(path)
    added = d not in sys.path
    if added:
        sys.path.insert(0, d)
    old_mod = sys.modules.get(name)
    sys.modules[name] = mod
    try:
        exec(code, mod.__dict__)
    finally:
        if added and d in sys.path:
            sys.path.remove(d)
        if old_mod is not None:
            sys.modules[name] = old_mod
        else:
            sys.modules.pop(name, None)
    return _buses[before:]


# ---------------------------------------------------------------------------------------------
# 빌드 안: 갱신·확인·훅
# ---------------------------------------------------------------------------------------------


class _State:
    def __init__(self):
        self.updates = 0
        self.verified = False


_st = _State()


def _reset():
    global _st
    _st = _State()
    for b in _buses:
        b._touched = False


_compat.register_build_reset(_reset)


def f_update():
    """걸쇠(`Value.get`)·레벨(`Pulse.level`) 상태를 갱신한다. **플러그인 수신 뒤, 소비자 앞에서 사이클마다 한 번**.

    보통 맵 플러그인의 beforeTriggerExec 맨 앞. 훅 플러그인(`EdsDoc.add_sync(hook=True)`)을 쓰면 훅이 대신
    내므로 이 호출은 아무것도 내지 않는다. 펄스(`pulse`)만 쓰면 부르지 않아도 된다.
    인자: 없음
    반환: None
    비용: level 채널마다 사람당 트리거 2, latch 채널마다 사람당 분기 1 + 받은 사이클에 읽기 1회
    CP: 바꾸지 않음(읽기 함수가 복구)
    로컬: 공유 안전
    epScript: `function beforeTriggerExec() { sync.update(); … }`
    출처: 새로 작성 (INT 5.1, GOTCHAS 6절 "MouseDown/Up 짝으로 레벨")
    """
    if _hook_active:
        return
    _emit_update()


def _emit_update():
    f_verify()
    _st.updates += 1
    for b in _buses:
        b._emit_update()


def _check_updated():
    if _st.updates == 0 and not _hook_active:
        warn("sync: level()/get()(걸쇠)을 썼지만 이 빌드에 sync.update() 가 없습니다 — 상태가 갱신되지 않습니다. "
             "beforeTriggerExec 맨 앞에서 sync.update() 를 부르거나 훅 플러그인을 쓰세요.")


def _plugin_module(transport):
    m = sys.modules.get(transport.module)
    if m is not None and isinstance(getattr(m, "settings", None), dict):
        return m
    return None


def f_verify(force=False):
    """euddraft 안에서 불러온 [MSQC]/[NSQC] 설정이 선언과 같은지 확인한다(빌드당 한 번).

    - 선언한 줄이 설정에 없거나 값이 다르면 오류(eds 를 다시 만들지 않은 경우).
    - 설정에 `eudext_` 이름을 쓰는 줄이 남았는데 선언에 없으면 오류(옛 조각).
    - 선언한 QCUnit 이 맵 UNIT 구역에 놓여 있으면 오류(theSeed 크래시 사례).
    euddraft 밖(단독 빌드·에뮬레이터)에서 플러그인 모듈이 없으면 건너뛴다.
    인자: force(True 면 다시 확인)
    반환: 확인한 섹션 이름 목록
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다 (update·훅이 부른다)
    출처: 새로 작성 (R4b A7 — 조각이 같은 빌드에 반영되지 않는 문제의 안전장치)
    """
    if _st.verified and not force:
        return []
    _st.verified = True
    checked = []
    in_draft = _in_euddraft() or _hook_active
    for t in TRANSPORTS.values():
        pairs = _merged_pairs(t, _buses)
        if not pairs:
            continue
        mod = _plugin_module(t)
        if mod is None:
            if in_draft:
                fail("eds 에 [%s] 섹션이 없습니다 — 선언(%d줄)을 eds 로 만들어 넣으세요 (tools/edsgen EdsDoc.add_sync)",
                     t.section, len(pairs))
            continue
        actual = {str(k).strip(): str(v).strip() for k, v in mod.settings.items()}
        if "QCDummy" not in actual and hasattr(mod, "QCDummy"):
            actual["QCDummy"] = str(mod.QCDummy).strip()  # NSQC 는 읽은 뒤 설정에서 지운다
        problems = []
        for k, v in pairs:
            got = actual.get(k)
            if got is None:
                problems.append("없음: %s : %s" % (k, v))
            elif got != v:
                problems.append("다름: %s : %s (eds 값 %s)" % (k, v, got))
        mine = {k for k, _v in pairs}
        for k, v in actual.items():
            if k not in mine and NAME_PREFIX in (k + " " + v):
                problems.append("옛 줄: %s : %s" % (k, v))
        if problems:
            fail("[%s] eds 조각이 선언과 다릅니다 — 빌드 스크립트로 eds 를 다시 만드세요:\n  %s",
                 t.section, "\n  ".join(problems[:20]))
        _check_qc_unit(t, pairs)
        checked.append(t.section)
    return checked


def _check_qc_unit(transport, pairs):
    unit = dict(pairs).get("QCUnit")
    try:
        unit = int(unit, 0) if unit is not None else DEFAULT_QC_UNIT
    except ValueError:
        return  # 이름이면 건너뛴다
    try:
        data = GetChkTokenized().getsection("UNIT")
    except Exception:  # noqa: BLE001
        return
    for i in range(0, len(data) - 35, 36):
        if data[i + 8] | (data[i + 9] << 8) == unit:
            fail("[%s] QCUnit %d 이(가) 맵에 놓여 있습니다 — 플러그인이 그 유닛의 dat 를 덮어씁니다. 쓰지 않는 번호를 고르세요",
                 transport.section, unit)


HOOK_SOURCE = '''"""eudext.sync 훅 플러그인 — tools/edsgen 이 만든 파일(고치지 않는다).

eds 순서: [eudext boot] → [MSQC]/[NSQC] → [이 파일] → 맵 플러그인.
- onPluginStart: 불러온 [MSQC]/[NSQC] 설정이 선언과 같은지 확인한다(sync.verify).
- beforeTriggerExec: 플러그인 수신 뒤, 맵 코드 앞에서 걸쇠·레벨을 갱신한다(sync.update).
- afterTriggerExec: 맵 코드 뒤에서 local 엣지 캐시를 갱신한다(local.update). 설정 `LocalUpdate : 0` 이면 끈다.
"""
import eudext.sync as _sync

_sync.hook_loaded(settings)


def onPluginStart():
    _sync.hook_plugin_start()


def beforeTriggerExec():
    _sync.hook_before()


def afterTriggerExec():
    _sync.hook_after()
'''

_hook_local = True


def f_hook_source():
    """훅 플러그인 파일 내용(문자열). `tools/edsgen.EdsDoc.add_sync(hook=True)` 가 eds 옆에 쓴다.

    인자: 없음
    반환: str
    비용: 훅이 내는 트리거 = update() 두 개(sync·local)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    return HOOK_SOURCE


def f_write_hook(path):
    """훅 플러그인 파일을 쓴다(eds 폴더에 둔다).

    인자: path
    반환: path
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    return _write_text(path, HOOK_SOURCE)


def hook_loaded(settings):
    """훅 플러그인이 불러와질 때 부른다(맵 플러그인보다 먼저)."""
    global _hook_active, _hook_local
    _hook_active = True
    opts = {str(k).strip().lower(): str(v).strip() for k, v in (settings or {}).items()}
    _hook_local = opts.get("localupdate", "1") not in ("0", "false", "off")
    if _hook_local:
        _local.f_set_auto_update(True)


def hook_plugin_start():
    f_verify()


def hook_before():
    _emit_update()


def hook_after():
    if _hook_local:
        _local._emit_update_from_hook()


# --- epScript·파이썬 공용 이름 ------------------------------------------------------------------
escape_key = f_escape_key
not_typing = f_not_typing
key_held = f_key_held
mouse_held = f_mouse_held
memory_guard = f_memory_guard
bit_guard = f_bit_guard
raw_guard = f_raw_guard
flag_guard = f_flag_guard
mouse_moved = f_mouse_moved
screen_moved = f_screen_moved
wide_screen = f_wide_screen
guards = f_guards
scrdb_msqc_lines = f_scrdb_msqc_lines
buses = f_buses
eds_sections = f_eds_sections
eds_fragment = f_eds_fragment
write_eds_fragment = f_write_eds_fragment
collect = f_collect
update = f_update
verify = f_verify
hook_source = f_hook_source
write_hook = f_write_hook
