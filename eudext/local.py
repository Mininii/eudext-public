"""로컬 입력 — 키·마우스·채팅 중·화면·로컬 플레이어 (DESIGN 4.12, 3.7). **표시 전용**.

이 모듈의 값은 모두 **각 PC 에서만 다른 로컬 메모리**에서 나온다(R4b A1). 공유 상태(데스값, 유닛,
로케이션, 공유 변수)를 이 값으로 바꾸면 곧바로 디싱크다. 공유 로직에 쓰려면 `eudext.sync` 로 보낸다.

    from eudext import local
    with local.only(p):                       # 이 PC 가 p 일 때만 (표시 전용 구역)
        if EUDIf()(local.key_pressed("X")):   # 누르는 순간 (엣지)
            DoActions(DisplayText("X"))
        EUDEndIf()
    local.update()                            # 모든 소비자 뒤 1회 (엣지 캐시 갱신)

epScript (`with` 가 없으므로 `begin`/`end` 짝):

    import eudext.local as local;
    function afterTriggerExec() {
        local.begin();                         // 표시 전용 구역 (인자 없음 = 분기 없이 표시만)
        if (local.key_pressed("X")) { printAll("X"); }
        local.end();
        local.update();
    }

표식 (3.7):
- `LocalCondition`(eudplib `Condition` 하위 클래스)·`LocalConditions`(list 하위 클래스): 로컬 조건.
  `.eds` 에 MSQC/NSQC 조건 표기가 있으면 `sync` 의 `guard=` 로 그대로 넘길 수 있다.
  `local.only()`/`local.begin()`/`local.allow()` 밖에서 트리거에 놓이면 빌드 경고(EPWarning)를 낸다.
- `LocalValue`(EUDVariable 하위 클래스): 로컬 값. 이 값이 **다른 변수·함수 인자·액션 값으로 흘러가면**
  (`shared << lv`, `f(lv)`, `lv + 1`, `SetMemory(…, lv)`) 구역 밖에서는 빌드 경고를 낸다.
  `sync.Bus.value(lv)` 는 플러그인이 메모리를 직접 읽으므로 경고가 없다.
  한계: `lv + 1` 의 결과(보통 EUDVariable)에는 표식이 남지 않는다. `local.strict(True)` 면 경고 대신 오류.

엣지(`key_pressed`/`key_released`/`mouse_pressed`/`mouse_released`/`key_toggle`/`track_mouse`)는
`local.update()` 가 갱신하는 로컬 캐시를 쓴다. **update() 는 모든 소비자 뒤에 한 번** 둔다(보통
afterTriggerExec 끝). 같은 빌드에서 update() 를 낸 뒤에 새 키를 처음 쓰면 오류다(그 키는 갱신되지 않으므로)
→ `local.watch_keys(…)` 로 미리 등록하거나 update() 를 뒤로 옮긴다. `sync` 훅 플러그인(`tools/edsgen`
`EdsDoc.add_sync(hook=True)`)을 쓰면 훅의 afterTriggerExec(맵 플러그인보다 뒤)가 update() 를 대신 낸다.

주소 근거: R4b A1, CtrigAsm v5.5 `ParseKeyName`/`MousePress`/`NotTyping`(80174~80328),
MSQC.py(euddraft 0.11.0.1 번들) `KeyUpdate`/`KeyDown`/`MouseUpdate`.
"""

import contextlib
import os
import sys

from eudplib import (
    EPD,
    AtLeast,
    AtMost,
    Condition,
    CurrentPlayer,
    Db,
    EncodePlayer,
    EUDEndIf,
    EUDIf,
    EUDOnStart,
    EUDVariable,
    Exactly,
    IsEUDVariable,
    IsUserCP,
    Memory,
    MemoryX,
    RawTrigger,
    SetMemoryX,
    SetTo,
    f_getuserplayerid,
    f_maskread_epd,
)

from eudext import _compat
from eudext.errors import EudextError, fail, warn

__all__ = [
    "BUTTONS",
    "CHAT_TARGET_ADDR",
    "KEYS",
    "KEY_STATE_ADDR",
    "LOCAL_PLAYER_ADDR",
    "LocalCondition",
    "LocalConditions",
    "LocalValue",
    "MOUSE_BUTTON_ADDR",
    "MOUSE_X_ADDR",
    "MOUSE_Y_ADDR",
    "MouseTracker",
    "SCREEN_X_ADDR",
    "SCREEN_Y_ADDR",
    "allow",
    "begin",
    "button_bit",
    "button_name",
    "end",
    "in_region",
    "is_local",
    "is_observer",
    "key_code",
    "key_held",
    "key_pressed",
    "key_released",
    "key_toggle",
    "msqc_key_name",
    "mouse_held",
    "mouse_map_xy",
    "mouse_pressed",
    "mouse_released",
    "mouse_screen_xy",
    "not_typing",
    "only",
    "player",
    "screen_xy",
    "strict",
    "track_mouse",
    "track_screen",
    "typing",
    "update",
    "watch_buttons",
    "watch_keys",
]

# --- 로컬 메모리 주소 (R4b A1) -------------------------------------------------------------
KEY_STATE_ADDR = 0x596A18  # + 가상 키 코드 = 1바이트 키 상태 (누르고 있으면 1)
MOUSE_BUTTON_ADDR = 0x6CDDC0  # 마우스 버튼 비트 L=2, R=8, M=32
MOUSE_X_ADDR = 0x6CDDC4  # 화면 기준 마우스 X
MOUSE_Y_ADDR = 0x6CDDC8  # 화면 기준 마우스 Y
SCREEN_X_ADDR = 0x62848C  # 화면 왼쪽 위의 맵 좌표 X
SCREEN_Y_ADDR = 0x6284A8  # 화면 왼쪽 위의 맵 좌표 Y
CHAT_TARGET_ADDR = 0x68C144  # 채팅 입력 대상. 0 = 채팅창 닫힘
LOCAL_PLAYER_ADDR = 0x512684  # 로컬 플레이어 번호 (관전자 128~131)

# 좌표 읽기 마스크: 맵 최대 256타일 = 8192px, 화면 마우스는 SC:R 와이드까지 여유 있게 (NSQC 는 0x3FF/0x1FF)
SCREEN_MASK = 0x1FFF
MOUSE_X_MASK = 0x7FF
MOUSE_Y_MASK = 0x3FF

# --- 키 이름 표 ---------------------------------------------------------------------------
# 출처: CtrigAsm v5.5.lua ParseKeyName (80175~80228) = MSQC.py/NSQC.py KeyCodeDict (같은 표, 같은 순서).
# 이름 → 가상 키 코드. 한 코드에 이름이 둘 이상이면 앞의 것이 MSQC 표기다.
# fmt: off
_KEY_TABLE = (
    ("LBUTTON", 0x01), ("RBUTTON", 0x02), ("CANCEL", 0x03), ("MBUTTON", 0x04),
    ("XBUTTON1", 0x05), ("XBUTTON2", 0x06), ("BACK", 0x08), ("TAB", 0x09),
    ("CLEAR", 0x0C), ("ENTER", 0x0D), ("NX5", 0x0E), ("SHIFT", 0x10),
    ("LCTRL", 0x11), ("LALT", 0x12), ("PAUSE", 0x13), ("CAPSLOCK", 0x14),
    ("RALT", 0x15), ("JUNJA", 0x17), ("FINAL", 0x18), ("RCTRL", 0x19), ("ESC", 0x1B),
    ("CONVERT", 0x1C), ("NONCONVERT", 0x1D), ("ACCEPT", 0x1E), ("MODECHANGE", 0x1F),
    ("SPACE", 0x20), ("PGUP", 0x21), ("PGDN", 0x22), ("END", 0x23), ("HOME", 0x24),
    ("LEFT", 0x25), ("UP", 0x26), ("RIGHT", 0x27), ("DOWN", 0x28),
    ("SELECT", 0x29), ("PRINTSCREEN", 0x2A), ("EXECUTE", 0x2B), ("SNAPSHOT", 0x2C),
    ("INSERT", 0x2D), ("DELETE", 0x2E), ("HELP", 0x2F),
    ("0", 0x30), ("1", 0x31), ("2", 0x32), ("3", 0x33), ("4", 0x34),
    ("5", 0x35), ("6", 0x36), ("7", 0x37), ("8", 0x38), ("9", 0x39),
    ("A", 0x41), ("B", 0x42), ("C", 0x43), ("D", 0x44), ("E", 0x45), ("F", 0x46),
    ("G", 0x47), ("H", 0x48), ("I", 0x49), ("J", 0x4A), ("K", 0x4B), ("L", 0x4C),
    ("M", 0x4D), ("N", 0x4E), ("O", 0x4F), ("P", 0x50), ("Q", 0x51), ("R", 0x52),
    ("S", 0x53), ("T", 0x54), ("U", 0x55), ("V", 0x56), ("W", 0x57), ("X", 0x58),
    ("Y", 0x59), ("Z", 0x5A),
    ("LWIN", 0x5B), ("RWIN", 0x5C), ("APPS", 0x5D), ("SLEEP", 0x5F),
    ("NUMPAD0", 0x60), ("NUMPAD1", 0x61), ("NUMPAD2", 0x62), ("NUMPAD3", 0x63),
    ("NUMPAD4", 0x64), ("NUMPAD5", 0x65), ("NUMPAD6", 0x66), ("NUMPAD7", 0x67),
    ("NUMPAD8", 0x68), ("NUMPAD9", 0x69),
    ("NUMPAD*", 0x6A), ("NUMPAD+", 0x6B), ("SEPARATOR", 0x6C), ("NUMPAD-", 0x6D),
    ("NUMPAD.", 0x6E), ("NUMPAD/", 0x6F),
    ("F1", 0x70), ("F2", 0x71), ("F3", 0x72), ("F4", 0x73), ("F5", 0x74),
    ("F6", 0x75), ("F7", 0x76), ("F8", 0x77), ("F9", 0x78), ("F10", 0x79),
    ("F11", 0x7A), ("F12", 0x7B), ("F13", 0x7C), ("F14", 0x7D), ("F15", 0x7E),
    ("F16", 0x7F), ("F17", 0x80), ("F18", 0x81), ("F19", 0x82), ("F20", 0x83),
    ("F21", 0x84), ("F22", 0x85), ("F23", 0x86), ("F24", 0x87),
    ("NUMLOCK", 0x90), ("SCROLL", 0x91), ("OEM_FJ_JISHO", 0x92),
    ("OEM_FJ_MASSHOU", 0x93), ("OEM_FJ_TOUROKU", 0x94),
    ("OEM_FJ_LOYA", 0x95), ("OEM_FJ_ROYA", 0x96),
    ("LSHIFT", 0xA0), ("RSHIFT", 0xA1), ("LCONTROL", 0xA2), ("RCONTROL", 0xA3),
    ("LMENU", 0xA4), ("RMENU", 0xA5),
    ("BROWSER_BACK", 0xA6), ("BROWSER_FORWARD", 0xA7), ("BROWSER_REFRESH", 0xA8),
    ("BROWSER_STOP", 0xA9), ("BROWSER_SEARCH", 0xAA), ("BROWSER_FAVORITES", 0xAB),
    ("BROWSER_HOME", 0xAC),
    ("VOLUME_MUTE", 0xAD), ("VOLUME_DOWN", 0xAE), ("VOLUME_UP", 0xAF),
    ("MEDIA_NEXT_TRACK", 0xB0), ("MEDIA_PLAY_PAUSE", 0xB3),
    ("MEDIA_PREV_TRACK", 0xB1), ("MEDIA_STOP", 0xB2),
    ("LAUNCH_MAIL", 0xB4), ("LAUNCH_MEDIA_SELECT", 0xB5), ("LAUNCH_APP1", 0xB6),
    ("LAUNCH_APP2", 0xB7),
    ("SEMICOLON", 0xBA), ("=", 0xBB), (",", 0xBC), ("-", 0xBD), (".", 0xBE), ("/", 0xBF),
    ("`", 0xC0), ("ABNT_C1", 0xC1), ("ABNT_C2", 0xC2),
    ("[", 0xDB), ("|", 0xDC), ("]", 0xDD), ("'", 0xDE), ("OEM_8", 0xDF),
    ("OEM_AX", 0xE1), ("OEM_102", 0xE2), ("ICO_HELP", 0xE3), ("ICO_00", 0xE4),
    ("PROCESSKEY", 0xE5), ("ICO_CLEAR", 0xE6), ("PACKET", 0xE7), ("OEM_RESET", 0xE9),
    ("OEM_JUMP", 0xEA), ("OEM_PA1", 0xEB), ("OEM_PA2", 0xEC), ("OEM_PA3", 0xED),
    ("OEM_WSCTRL", 0xEE), ("OEM_CUSEL", 0xEF),
    ("OEM_ATTN", 0xF0), ("OEM_FINISH", 0xF1), ("OEM_COPY", 0xF2), ("OEM_AUTO", 0xF3),
    ("OEM_ENLW", 0xF4), ("OEM_BACKTAB", 0xF5), ("ATTN", 0xF6), ("CRSEL", 0xF7),
    ("EXSEL", 0xF8), ("EREOF", 0xF9), ("PLAY", 0xFA), ("ZOOM", 0xFB), ("NONAME", 0xFC),
    ("PA1", 0xFD), ("OEM_CLEAR", 0xFE), ("_NONE_", 0xFF),
)
# fmt: on
# NSQC 가이드북(Ctrig Assembler v5.4 Guide Book 27장) 표기: 0xDC 를 `\\`(= 역슬래시 한 글자)로 적는다.
_KEY_ALIASES = (("\\", 0xDC),)

KEYS = dict(_KEY_TABLE)
KEYS.update(_KEY_ALIASES)
_MSQC_NAME = {}
for _n, _c in _KEY_TABLE:
    _MSQC_NAME.setdefault(_c, _n)
del _n, _c

# 마우스 버튼 (MSQC MouseButtonDict, CtrigAsm ParseMouseName)
BUTTONS = {"L": 2, "LEFT": 2, "R": 8, "RIGHT": 8, "M": 32, "MIDDLE": 32}
_BUTTON_NAME = {2: "L", 8: "R", 32: "M"}


def f_key_code(key):
    """키 이름(또는 코드)을 가상 키 코드로 바꾼다.

    인자: key — `KEYS` 의 이름(대소문자 무시, CtrigAsm·MSQC 표기와 NSQC 의 `\\`) 또는 0~255 정수
    반환: int
    비용: 없음(컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `const k = local.key_code("X");`
    출처: CtrigAsm `ParseKeyName`(80174)
    """
    if isinstance(key, bool):
        fail("key_code: 키 이름이 아닙니다 (%r)", key)
    if isinstance(key, int):
        if not 0 <= key <= 0xFF:
            fail("key_code: 가상 키 코드는 0~255 입니다 (%d)", key)
        return key
    if isinstance(key, str):
        name = key.strip()
        code = KEYS.get(name.upper()) if name else None
        if code is None and name:
            code = KEYS.get(name)
        if code is not None:
            return code
    fail("알 수 없는 키 이름 %r (local.KEYS 참고, 예: 'X', 'SPACE', 'F12', 'NUMPAD1')", key)


def f_msqc_key_name(key):
    """MSQC/NSQC eds 에 쓸 키 이름(플러그인 표의 이름)을 돌려준다.

    인자: key(이름 또는 코드)
    반환: str (예: 0xDC → '|', 0xBB → '=')
    비용: 없음
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: MSQC.py KeyCodeDict
    """
    code = f_key_code(key)
    name = _MSQC_NAME.get(code)
    if name is None:
        fail("가상 키 코드 0x%02X 는 MSQC/NSQC 표에 없습니다 (로컬 판정만 가능)", code)
    return name


def f_button_bit(button):
    """마우스 버튼 이름을 0x6CDDC0 의 비트로 바꾼다 (L=2, R=8, M=32).

    인자: button — 'L'/'LEFT', 'R'/'RIGHT', 'M'/'MIDDLE' (대소문자 무시)
    반환: int
    비용: 없음
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: CtrigAsm `ParseMouseName`, MSQC MouseButtonDict
    """
    if isinstance(button, str):
        bit = BUTTONS.get(button.strip().upper())
        if bit is not None:
            return bit
    fail("마우스 버튼은 'L', 'R', 'M' 중 하나입니다 (%r)", button)


def f_button_name(button):
    """마우스 버튼의 MSQC 표기('L'/'R'/'M')를 돌려준다.

    인자: button('L'/'LEFT'/'R'/'RIGHT'/'M'/'MIDDLE', 대소문자 무시)
    반환: str
    비용: 없음(컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: MSQC MouseButtonDict
    """
    return _BUTTON_NAME[f_button_bit(button)]


# ---------------------------------------------------------------------------------------------
# 표식과 구역
# ---------------------------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_region_stack = []  # begin() 마다 (분기 여부)
_allow_depth = 0
_strict = False
_auto_update = False  # sync 훅이 update() 를 대신 낼 때 True


def f_strict(on=True):
    """구역 밖 로컬 값·조건 사용을 경고 대신 오류로 한다(기본 경고).

    인자: on(bool)
    반환: 이전 값
    비용: 없음
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `local.strict(1);`
    출처: 새로 작성 (DESIGN 3.7)
    """
    global _strict
    old, _strict = _strict, bool(on)
    return old


def f_in_region():
    """지금 `only()`/`begin()`/`allow()` 구역 안에서 코드를 만들고 있으면 True (컴파일 시점).

    인자: 없음
    반환: bool
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    return bool(_region_stack) or _allow_depth > 0


_SKIP_FILES = {os.path.join(_HERE, n).replace("\\", "/") for n in ("local.py", "sync.py", "_parts.py", "_compat.py")}
_SKIP_DIR = os.path.join(_HERE, "testing").replace("\\", "/") + "/"


def _caller_site():
    """경고에 적을 사용자 코드 위치 (eudplib·eudext 부품·시험 틀 프레임은 건너뛴다)."""
    f = sys._getframe(2)
    while f is not None:
        fn = f.f_code.co_filename.replace("\\", "/")
        if "/eudplib/" not in fn and fn not in _SKIP_FILES and not fn.startswith(_SKIP_DIR):
            return (fn, f.f_lineno)
        f = f.f_back
    return ("?", 0)


def _check_region(what):
    if f_in_region():
        return
    site = _caller_site()
    key = (what, site)
    if key in _st.warned:
        return
    _st.warned.add(key)
    msg = (
        "%s 이(가) local.only()/begin()/allow() 구역 밖에서 쓰였습니다 (%s:%d). "
        "로컬 값으로 공유 상태를 바꾸면 디싱크입니다 — 표시 전용이면 구역으로 감싸고, "
        "공유 로직이면 eudext.sync 로 보내세요." % (what, os.path.basename(site[0]), site[1])
    )
    if _strict:
        raise EudextError(msg)
    warn(msg)


class LocalCondition(Condition):
    """로컬 조건 표식 (eudplib `Condition` 하위 클래스, DESIGN 3.7).

    `.eds` 에 MSQC/NSQC 조건 표기(예: 'KeyDown(X)', 'NotTyping')가 있으면 `sync` guard 로 쓸 수 있다.
    구역(`only`/`begin`/`allow`) 밖에서 트리거에 놓이면 빌드 경고를 낸다.
    인자: eudplib Condition 과 같다
    반환: -
    비용: 조건 1
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `if (local.key_held("X")) { … }`
    출처: 새로 작성
    """

    eds = None

    def SetParentTrigger(self, trg, index):  # noqa: N802
        _check_region("로컬 조건(LocalCondition)")
        return super().SetParentTrigger(trg, index)

    @classmethod
    def wrap(cls, cond, eds=None):
        """eudplib Condition 을 표식이 붙은 사본으로 바꾼다."""
        f = cond.fields
        ret = cls(*f[:8], eudx=f[8])
        ret.eds = eds
        return ret


class LocalConditions(list):
    """로컬 조건 여러 개(AND) 표식 (list 하위 클래스, eudplib 이 평평하게 펼친다).

    인자: conds(조건 목록), eds(MSQC 조건 표기 — ';' 로 이은 것, 없으면 None)
    반환: -
    비용: 조건 수만큼
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `if (local.key_pressed("X")) { … }`
    출처: 새로 작성 (DESIGN 3.7)
    """

    eds = None

    def __init__(self, conds=(), eds=None):
        super().__init__(conds)
        self.eds = eds


class LocalValue(EUDVariable):
    """로컬 값 표식 (EUDVariable 하위 클래스, DESIGN 3.7).

    이 값이 다른 변수·함수 인자·액션 값으로 흘러가면(SetDest) 구역 밖에서 빌드 경고를 낸다.
    비교(`AtLeast`/`AtMost`/`Exactly`)는 `LocalCondition` 을 돌려준다.
    인자: initval(기본 0)
    반환: -
    비용: 변수 1 (72B)
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `const lv = local.LocalValue();`
    출처: 새로 작성
    """

    __slots__ = ()

    def SetDest(self, dest):  # noqa: N802
        _check_region("로컬 값(LocalValue)")
        return super().SetDest(dest)

    def AtLeast(self, value):  # noqa: N802
        return LocalCondition.wrap(super().AtLeast(value))

    def AtMost(self, value):  # noqa: N802
        return LocalCondition.wrap(super().AtMost(value))

    def Exactly(self, value):  # noqa: N802
        return LocalCondition.wrap(super().Exactly(value))


def f_is_local(x):
    """x 가 로컬 표식(LocalValue/LocalCondition/LocalConditions)이면 True (컴파일 시점).

    인자: x
    반환: bool
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성 (DESIGN 3.7)
    """
    return isinstance(x, (LocalValue, LocalCondition, LocalConditions))


def _player_cond(p):
    if p is None:
        return None
    if IsEUDVariable(p):
        return Memory(LOCAL_PLAYER_ADDR, Exactly, p)
    if p is CurrentPlayer:
        return IsUserCP()
    try:
        code = EncodePlayer(p)
    except Exception:  # noqa: BLE001
        fail("local.only: 플레이어가 아닙니다 (%r)", p)
    if code == 13:
        return IsUserCP()
    if not (isinstance(code, int) and (0 <= code <= 11 or 128 <= code <= 131)):
        fail("local.only: 플레이어 번호는 0~11 또는 관전자 128~131 입니다 (%r)", p)
    return Memory(LOCAL_PLAYER_ADDR, Exactly, code)


def f_begin(p=None):
    """표시 전용 구역을 연다. p 가 있으면 이 PC 가 p 일 때만 안쪽을 실행한다(`EUDIf`).

    반드시 `local.end()` 로 닫는다. 안에서는 로컬 값·조건 경고가 나지 않는다.
    안에서는 **표시 액션만** 쓴다(DisplayText, PlayWAV, CenterView, 로컬 전용 변수, StringBuffer).
    인자: p — None(분기 없음), 0~11, 관전자 128~131, EUDVariable, CurrentPlayer(= IsUserCP)
    반환: None
    비용: p 가 있으면 분기 트리거 1(+EndIf) / 없으면 0
    CP: 바꾸지 않음
    로컬: 로컬 전용 구역
    epScript: `local.begin(p); … local.end();`
    출처: DESIGN 3.7, eudplib `IsUserCP`
    """
    cond = _player_cond(p)
    if cond is not None:
        EUDIf()(cond)
    _region_stack.append(cond is not None)


def f_end():
    """`begin()` 으로 연 구역을 닫는다(분기가 있었으면 `EUDEndIf`).

    인자: 없음
    반환: None
    비용: begin 에 분기가 있었으면 EndIf 트리거 0~1
    CP: 바꾸지 않음
    로컬: 로컬 전용 구역 끝
    epScript: `local.end();`
    출처: 새로 작성
    """
    if not _region_stack:
        fail("local.end(): 열린 local.begin() 이 없습니다")
    if _region_stack.pop():
        EUDEndIf()


@contextlib.contextmanager
def f_only(p=None):
    """`with local.only(p):` — `begin(p)` … `end()` (파이썬 전용). 안쪽에서 예외가 나면 구역 기록만 되돌린다.

    인자: p — `begin` 과 같다
    반환: 컨텍스트 관리자
    비용: `begin` 과 같다
    CP: 바꾸지 않음
    로컬: 로컬 전용 구역 (안에서는 표시 액션만)
    epScript: `with` 가 없으므로 `local.begin(p); … local.end();`
    출처: DESIGN 3.7
    """
    f_begin(p)
    depth = len(_region_stack)
    try:
        yield
    except BaseException:
        del _region_stack[depth - 1 :]
        raise
    f_end()


@contextlib.contextmanager
def f_allow():
    """분기 없이 로컬 표식 경고만 끄는 구역(`with local.allow():`). 이미 `IsUserCP()` 등으로 감싼 코드나 라이브러리 내부 계산에 쓴다.

    인자: 없음
    반환: 컨텍스트 관리자
    비용: 없음
    CP: 바꾸지 않음
    로컬: 안쪽 코드가 공유 상태를 바꾸지 않는다는 것을 호출자가 보장한다
    epScript: 쓰지 않는다 (`local.begin();` … `local.end();` 가 같은 일을 한다)
    출처: 새로 작성
    """
    global _allow_depth
    _allow_depth += 1
    try:
        yield
    finally:
        _allow_depth -= 1


# ---------------------------------------------------------------------------------------------
# 빌드별 상태
# ---------------------------------------------------------------------------------------------


class _BuildState:
    def __init__(self):
        self.update_count = 0  # 이 빌드에서 update() 를 낸 횟수
        self.player = None
        self.warned = set()


_st = _BuildState()
_keys = {}  # 가상 키 코드 → 이름 (엣지 캐시 대상, 누적)
_buttons = {}  # 비트 → 이름
_toggles = []  # (코드, guard 조건 목록, LocalValue)
_trackers = []  # MouseTracker
_KEY_CACHE = None  # Db(32): 256비트 = 키마다 1비트
_MOUSE_CACHE = None  # Db(4)


def _reset():
    global _st, _allow_depth
    _st = _BuildState()
    del _region_stack[:]
    _allow_depth = 0


_compat.register_build_reset(_reset)


def f_set_auto_update(on=True):
    """sync 훅 플러그인이 부른다: True 면 맵 코드의 `local.update()` 는 아무것도 내지 않고 훅이 대신 낸다."""
    global _auto_update
    _auto_update = bool(on)


def _key_cache():
    global _KEY_CACHE
    if _KEY_CACHE is None:
        _KEY_CACHE = Db(32)
    return _KEY_CACHE


def _mouse_cache():
    global _MOUSE_CACHE
    if _MOUSE_CACHE is None:
        _MOUSE_CACHE = Db(4)
    return _MOUSE_CACHE


def _late(what):
    if _st.update_count and not _auto_update:
        fail(
            "local.update() 를 낸 뒤에 %s 를 처음 썼습니다 — 이 입력의 캐시는 갱신되지 않습니다. "
            "update() 를 모든 소비자 뒤(afterTriggerExec 끝)로 옮기거나 local.watch_keys()/watch_buttons() 로 "
            "미리 등록하세요.",
            what,
        )


def _register_key(code):
    if code not in _keys:
        _late("키 %s 의 엣지" % _MSQC_NAME.get(code, hex(code)))
        _keys[code] = _MSQC_NAME.get(code, "0x%02X" % code)
    return code


def _register_button(bit):
    if bit not in _buttons:
        _late("마우스 %s 의 엣지" % _BUTTON_NAME[bit])
        _buttons[bit] = _BUTTON_NAME[bit]
    return bit


def f_watch_keys(*keys):
    """엣지 캐시를 쓸 키를 미리 등록한다(`update()` 를 소비자보다 먼저 내야 할 때).

    인자: 키 이름들
    반환: None
    비용: 키마다 update() 트리거 2
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `local.watch_keys("X", "SPACE");`
    출처: MSQC.py RegisterKeyOffset
    """
    for k in keys:
        _register_key(f_key_code(k))


def f_watch_buttons(*buttons):
    """엣지 캐시를 쓸 마우스 버튼을 미리 등록한다(`update()` 를 소비자보다 먼저 내야 할 때).

    인자: 버튼 이름들('L', 'R', 'M')
    반환: None
    비용: 버튼마다 update() 트리거 2
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `local.watch_buttons("L");`
    출처: MSQC.py RegisterMouseOffset
    """
    for b in buttons:
        _register_button(f_button_bit(b))


# ---------------------------------------------------------------------------------------------
# 조건
# ---------------------------------------------------------------------------------------------


def _key_raw(code, held):
    r = code % 4
    m = 1 << (8 * r)
    return MemoryX(KEY_STATE_ADDR + code - r, Exactly, m if held else 0, m)


def _key_cache_raw(code, set_):
    n = 1 << (code % 32)
    return MemoryX(_key_cache() + 4 * (code // 32), Exactly, n if set_ else 0, n)


def f_key_held(key, held=True):
    """키를 누르고 있는가(레벨). held=False 면 누르고 있지 않은가.

    인자: key(이름·코드), held(bool)
    반환: LocalCondition — `MemoryX(0x596A18 + 코드, Exactly, 1, 1)` (eds: `KeyPress(이름)`, held=False 는 표기 없음)
    비용: 조건 1 / 호출 자리 0
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `if (local.key_held("LCTRL")) { … }`
    출처: CtrigAsm `KeyPress(K, "Down"/"Up")`, MSQC `KeyPress`
    """
    code = f_key_code(key)
    eds = ("KeyPress(%s)" % _MSQC_NAME[code]) if held and code in _MSQC_NAME else None
    return LocalCondition.wrap(_key_raw(code, held), eds)


def f_key_pressed(key):
    """키를 누르는 순간(엣지). `local.update()` 가 갱신하는 캐시와 비교한다.

    인자: key
    반환: LocalConditions (조건 2, eds: `KeyDown(이름)`)
    비용: 조건 2 / 호출 자리 0 / update() 에 키마다 트리거 2 (같은 키는 한 번)
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `if (local.key_pressed("X")) { … }`
    출처: CtrigAsm `TTKeyPress(K, "Down")`, MSQC `KeyDown`/`KeyUpdate`(Db(32) 캐시)
    """
    code = _register_key(f_key_code(key))
    eds = ("KeyDown(%s)" % _MSQC_NAME[code]) if code in _MSQC_NAME else None
    return LocalConditions(
        [LocalCondition.wrap(_key_raw(code, True)), LocalCondition.wrap(_key_cache_raw(code, False))], eds
    )


def f_key_released(key):
    """키를 떼는 순간(엣지). `local.update()` 가 갱신하는 캐시와 비교한다.

    인자: key
    반환: LocalConditions (조건 2, eds: `KeyUp(이름)`)
    비용: 조건 2 / 호출 자리 0 / update() 에 키마다 트리거 2 (같은 키는 한 번)
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `if (local.key_released("X")) { … }`
    출처: CtrigAsm `TTKeyPress(K, "Up")`, MSQC `KeyUp`
    """
    code = _register_key(f_key_code(key))
    eds = ("KeyUp(%s)" % _MSQC_NAME[code]) if code in _MSQC_NAME else None
    return LocalConditions(
        [LocalCondition.wrap(_key_raw(code, False)), LocalCondition.wrap(_key_cache_raw(code, True))], eds
    )


def _mouse_raw(bit, held):
    return MemoryX(MOUSE_BUTTON_ADDR, Exactly, bit if held else 0, bit)


def _mouse_cache_raw(bit, set_):
    return MemoryX(_mouse_cache(), Exactly, bit if set_ else 0, bit)


def f_mouse_held(button, held=True):
    """마우스 버튼을 누르고 있는가(레벨).

    인자: button('L'/'R'/'M'), held(bool)
    반환: LocalCondition — `MemoryX(0x6CDDC0, Exactly, 비트, 비트)` (eds: `MousePress(L)`)
    비용: 조건 1
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `if (local.mouse_held("L")) { … }`
    출처: CtrigAsm `MousePress`, MSQC `MousePress`
    """
    bit = f_button_bit(button)
    eds = ("MousePress(%s)" % _BUTTON_NAME[bit]) if held else None
    return LocalCondition.wrap(_mouse_raw(bit, held), eds)


def f_mouse_pressed(button):
    """마우스 버튼을 누르는 순간(엣지).

    인자: button('L'/'R'/'M')
    반환: LocalConditions (조건 2, eds: `MouseDown(L)`)
    비용: 조건 2 / 호출 자리 0 / update() 에 버튼마다 트리거 2
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `if (local.mouse_pressed("L")) { … }`
    출처: CtrigAsm `TTMousePress`, MSQC `MouseDown`/`MouseUpdate`(Db(4) 캐시)
    """
    bit = _register_button(f_button_bit(button))
    return LocalConditions(
        [LocalCondition.wrap(_mouse_raw(bit, True)), LocalCondition.wrap(_mouse_cache_raw(bit, False))],
        "MouseDown(%s)" % _BUTTON_NAME[bit],
    )


def f_mouse_released(button):
    """마우스 버튼을 떼는 순간(엣지).

    인자: button('L'/'R'/'M')
    반환: LocalConditions (조건 2, eds: `MouseUp(L)`)
    비용: 조건 2 / 호출 자리 0 / update() 에 버튼마다 트리거 2
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `if (local.mouse_released("R")) { … }`
    출처: CtrigAsm `TTMousePress(K, "Up")`, MSQC `MouseUp`
    """
    bit = _register_button(f_button_bit(button))
    return LocalConditions(
        [LocalCondition.wrap(_mouse_raw(bit, False)), LocalCondition.wrap(_mouse_cache_raw(bit, True))],
        "MouseUp(%s)" % _BUTTON_NAME[bit],
    )


def f_typing():
    """채팅 입력 중인가.

    인자: 없음
    반환: LocalCondition — `Memory(0x68C144, AtLeast, 1)` (eds: `0x68C144, AtLeast, 1`)
    비용: 조건 1
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `if (local.typing()) { … }`
    출처: CtrigAsm `IsTyping`
    """
    return LocalCondition.wrap(Memory(CHAT_TARGET_ADDR, AtLeast, 1), "0x%X, AtLeast, 1" % CHAT_TARGET_ADDR)


def f_not_typing():
    """채팅 입력 중이 아닌가.

    인자: 없음
    반환: LocalCondition — `Memory(0x68C144, Exactly, 0)` (eds: `NotTyping`)
    비용: 조건 1
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `if (local.not_typing()) { … }`
    출처: CtrigAsm `NotTyping`, 맵 원시 조건 27곳(R1)
    """
    return LocalCondition.wrap(Memory(CHAT_TARGET_ADDR, Exactly, 0), "NotTyping")


def f_is_observer():
    """이 PC 가 관전자(128~131)인가.

    인자: 없음
    반환: LocalConditions (조건 2, eds: 메모리 조건 두 개)
    비용: 조건 2
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `if (local.is_observer()) { … }`
    출처: ObserverChat(OBC:76), eudplib userpl.py
    """
    return LocalConditions(
        [
            LocalCondition.wrap(Memory(LOCAL_PLAYER_ADDR, AtLeast, 128)),
            LocalCondition.wrap(Memory(LOCAL_PLAYER_ADDR, AtMost, 131)),
        ],
        "0x%X, AtLeast, 128; 0x%X, AtMost, 131" % (LOCAL_PLAYER_ADDR, LOCAL_PLAYER_ADDR),
    )


# ---------------------------------------------------------------------------------------------
# 값
# ---------------------------------------------------------------------------------------------


def f_player():
    """이 PC 의 플레이어 번호(관전자 128~131)를 담은 LocalValue. 게임 시작 때 한 번 채운다.

    인자: 없음
    반환: LocalValue (빌드마다 한 개를 같이 쓴다)
    비용: 변수 1, 시작 트리거 1~2 / 호출 자리 0 / 읽기(대입) 실행 2 (2026-09-16 측정)
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `const me = local.player();`
    출처: eudplib `f_getuserplayerid`(0x512684)
    """
    if _st.player is None:
        lv = LocalValue()
        _st.player = lv

        def _init():
            with f_allow():
                lv << f_getuserplayerid()

        EUDOnStart(_init)
    return _st.player


def _read_pair(xaddr, xmask, yaddr, ymask, into, add=None):
    x, y = into if into is not None else (LocalValue(), LocalValue())
    with f_allow():
        rx = f_maskread_epd(EPD(xaddr), xmask)
        ry = f_maskread_epd(EPD(yaddr), ymask)
        if add is not None:
            ax = f_maskread_epd(EPD(add[0]), add[1])
            ay = f_maskread_epd(EPD(add[2]), add[3])
            rx = rx + ax
            ry = ry + ay
        x << rx
        y << ry
    return x, y


def f_screen_xy(into=None):
    """화면 왼쪽 위의 맵 좌표(픽셀, 0x1FFF 마스크)를 읽는다.

    인자: into — (x, y) 변수 짝(선택, 없으면 새 LocalValue 두 개)
    반환: (x, y)
    비용: 호출 자리 4 / 실행 36 / 페이로드 약 1.5KB (2026-09-16 측정, 새 변수 포함)
    CP: 바꾸지 않음(읽기 함수가 복구)
    로컬: 로컬 전용
    epScript: `const s = local.screen_xy();` → `s[0]`, `s[1]`
    출처: 0x62848C/0x6284A8 (CtrigAsm 80424, NSQC 258)
    """
    return _read_pair(SCREEN_X_ADDR, SCREEN_MASK, SCREEN_Y_ADDR, SCREEN_MASK, into)


def f_mouse_screen_xy(into=None):
    """마우스의 화면 좌표(픽셀)를 읽는다(X 는 0x7FF, Y 는 0x3FF 마스크).

    인자: into — (x, y) 변수 짝(선택)
    반환: (x, y)
    비용: `screen_xy` 와 같다
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `const m = local.mouse_screen_xy();`
    출처: 0x6CDDC4/0x6CDDC8 (NSQC 249~283, DPS mouse.lua:16)
    """
    return _read_pair(MOUSE_X_ADDR, MOUSE_X_MASK, MOUSE_Y_ADDR, MOUSE_Y_MASK, into)


def f_mouse_map_xy(into=None):
    """마우스의 맵 좌표 = 화면 위치 + 화면 안 마우스 위치.

    인자: into — (x, y) 변수 짝(선택)
    반환: (x, y) LocalValue
    비용: 호출 자리 8 / 실행 69 / 페이로드 약 3.6KB (2026-09-16 측정) — 여러 곳에서 쓰면 `track_mouse()` 로 한 번만 읽는다
    CP: 바꾸지 않음
    로컬: 로컬 전용 (동기화하려면 `track_mouse()` + `sync.Bus.value()` 또는 `Bus.mouse_location()`)
    epScript: `const m = local.mouse_map_xy();`
    출처: R4b A1, theSeed MouseInput.lua:81~88, NSQC 249~283
    """
    return _read_pair(
        SCREEN_X_ADDR, SCREEN_MASK, SCREEN_Y_ADDR, SCREEN_MASK, into,
        add=(MOUSE_X_ADDR, MOUSE_X_MASK, MOUSE_Y_ADDR, MOUSE_Y_MASK),
    )


class MouseTracker:
    """`local.update()` 가 매 사이클 채우는 좌표 짝. `.x`, `.y` 는 LocalValue.

    `sync.Bus.value(tracker.x)` 로 보내면 플러그인이 다음 사이클 앞에서 그 값을 읽는다(1사이클 늦음).
    인자: kind('map' = 마우스 맵 좌표, 'screen' = 화면 위치) — `track_mouse()`/`track_screen()` 이 만든다
    반환: -
    비용: update() 에 좌표 읽기 1회(실행 약 70 / 36)
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `const mouse = local.track_mouse();` → `mouse.x`
    출처: 새로 작성
    """

    __slots__ = ("kind", "x", "y")

    def __init__(self, kind):
        self.kind = kind
        self.x = LocalValue()
        self.y = LocalValue()

    def __repr__(self):
        return "<local.MouseTracker %s>" % self.kind

    def _emit(self):
        if self.kind == "map":
            f_mouse_map_xy(into=(self.x, self.y))
        else:
            f_screen_xy(into=(self.x, self.y))


def _tracker(kind):
    for t in _trackers:
        if t.kind == kind:
            return t
    _late("track_%s()" % ("mouse" if kind == "map" else "screen"))
    t = MouseTracker(kind)
    _trackers.append(t)
    return t


def f_track_mouse():
    """마우스 맵 좌표를 `update()` 때마다 갱신하는 추적기(모듈에 하나).

    인자: 없음
    반환: MouseTracker (`.x`, `.y`)
    비용: update() 에 `mouse_map_xy` 한 번 (실행 69)
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `const mouse = local.track_mouse();` → `bus.value(mouse.x)`
    출처: 새로 작성
    """
    return _tracker("map")


def f_track_screen():
    """화면 위치를 `update()` 때마다 갱신하는 추적기(모듈에 하나).

    인자: 없음
    반환: MouseTracker (`.x`, `.y`)
    비용: update() 에 `screen_xy` 한 번 (실행 36)
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `const scr = local.track_screen();`
    출처: 새로 작성
    """
    return _tracker("screen")


def f_key_toggle(key, guard=None):
    """키를 누를 때마다 0/1 이 바뀌는 로컬 값 (DPS `KeyToggleFunc` 대체). `update()` 가 바꾼다.

    인자: key, guard — 추가 조건(LocalCondition/목록, 예: `local.not_typing()`). 기본 없음
    반환: LocalValue (0 또는 1)
    비용: update() 에 트리거 2 (+ 키 엣지 2)
    CP: 바꾸지 않음
    로컬: 로컬 전용
    epScript: `const show = local.key_toggle("TAB", guard=local.not_typing());`
    출처: DPS function.lua:1081~1110 `KeyToggleFunc`
    """
    code = _register_key(f_key_code(key))
    conds = []
    for g in _flat(guard):
        if not isinstance(g, Condition):
            fail("key_toggle: guard 는 조건이어야 합니다 (%r)", g)
        conds.append(g)
    lv = LocalValue()
    _late("key_toggle(%s)" % _MSQC_NAME.get(code, code))
    _toggles.append((code, conds, lv))
    return lv


def _flat(x):
    if x is None:
        return []
    if isinstance(x, (list, tuple)):
        out = []
        for i in x:
            out.extend(_flat(i))
        return out
    return [x]


def _plain(cond):
    """표식 없는 사본 (update 본문은 구역 검사를 받지 않는다)."""
    f = cond.fields
    return Condition(*f[:8], eudx=f[8])


def f_update():
    """엣지 캐시·토글·추적기를 갱신한다. **모든 소비자 뒤에 사이클마다 한 번**.

    sync 훅 플러그인을 쓰면(`EdsDoc.add_sync(hook=True)`) 훅이 대신 내므로 이 호출은 아무것도 내지 않는다.
    인자: 없음
    반환: None
    비용: 키·버튼마다 트리거 2 / 토글마다 1 / 추적기마다 `mouse_map_xy` 1회 (실행도 같은 수 + 읽기)
    CP: 바꾸지 않음
    로컬: 로컬 전용 (로컬 캐시만 바꾼다)
    epScript: `function afterTriggerExec() { local.update(); }`
    출처: MSQC.py `KeyUpdate`/`MouseUpdate`(Db(32)/Db(4) 캐시), CtrigAsm TT 모드 20/21
    """
    if _auto_update:
        return
    _emit_update()


def _emit_update():
    _st.update_count += 1
    with f_allow():
        # 토글: 엣지를 보고 바꾼다 → 캐시 갱신보다 앞
        for code, conds, lv in _toggles:
            # 0 → 1, 1 → 2 → 0 (마스크 Add 는 인게임 식 확인 전이라 쓰지 않는다, DESIGN 3.5-8)
            edge = [_key_raw(code, True), _key_cache_raw(code, False)] + [_plain(c) for c in conds]
            RawTrigger(conditions=edge, actions=lv.AddNumber(1))
            RawTrigger(conditions=Memory(lv.getValueAddr(), Exactly, 2), actions=lv.SetNumber(0))
        cache = _key_cache() if _keys else None
        for code in _keys:
            r = code % 4
            m = 1 << (8 * r)
            n = 1 << (code % 32)
            slot = cache + 4 * (code // 32)
            RawTrigger(
                conditions=[MemoryX(KEY_STATE_ADDR + code - r, Exactly, m, m), MemoryX(slot, Exactly, 0, n)],
                actions=SetMemoryX(slot, SetTo, n, n),
            )
            RawTrigger(
                conditions=[MemoryX(KEY_STATE_ADDR + code - r, Exactly, 0, m), MemoryX(slot, Exactly, n, n)],
                actions=SetMemoryX(slot, SetTo, 0, n),
            )
        mcache = _mouse_cache() if _buttons else None
        for bit in _buttons:
            RawTrigger(
                conditions=[MemoryX(MOUSE_BUTTON_ADDR, Exactly, bit, bit), MemoryX(mcache, Exactly, 0, bit)],
                actions=SetMemoryX(mcache, SetTo, bit, bit),
            )
            RawTrigger(
                conditions=[MemoryX(MOUSE_BUTTON_ADDR, Exactly, 0, bit), MemoryX(mcache, Exactly, bit, bit)],
                actions=SetMemoryX(mcache, SetTo, 0, bit),
            )
        for t in _trackers:
            t._emit()


def _emit_update_from_hook():
    """sync 훅 플러그인의 afterTriggerExec 가 부른다."""
    _emit_update()


# --- epScript·파이썬 공용 이름 (3.1: 모듈 함수는 f_이름, 파이썬 별칭은 이름) ------------------
key_code = f_key_code
msqc_key_name = f_msqc_key_name
button_bit = f_button_bit
button_name = f_button_name
strict = f_strict
in_region = f_in_region
is_local = f_is_local
begin = f_begin
end = f_end
only = f_only
allow = f_allow
set_auto_update = f_set_auto_update
watch_keys = f_watch_keys
watch_buttons = f_watch_buttons
key_held = f_key_held
key_pressed = f_key_pressed
key_released = f_key_released
mouse_held = f_mouse_held
mouse_pressed = f_mouse_pressed
mouse_released = f_mouse_released
typing = f_typing
not_typing = f_not_typing
is_observer = f_is_observer
player = f_player
screen_xy = f_screen_xy
mouse_screen_xy = f_mouse_screen_xy
mouse_map_xy = f_mouse_map_xy
track_mouse = f_track_mouse
track_screen = f_track_screen
key_toggle = f_key_toggle
update = f_update
