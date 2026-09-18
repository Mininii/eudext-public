"""display — DisplayPrint 대체: 대상·원소·13번째 줄·TBL·틀 (DESIGN 4.7, docs/spec/S3_display.md 7절) — WP6b.

    from eudext import display as dp, players
    from eudext.display import PName, LocalName, Byte, Bytes, Pick, Part
    from eudext.numfmt import Dec, Man, Per, Gauge

    dp.show(P1, "\\x07HP ", hp, " / ", hp_max)                     # 맨 변수 = 부호 있는 10진 (D17)
    dp.show(dp.LOCAL, "\\x04보유 ", Man(gold, colors="dps", after=0x04), update_if=time5.Exactly(0))
    dp.show(players.Everyone, "\\x13", PName(p), "\\x04 님 입장", sound="staredit\\\\wav\\\\ding.ogg")
    dp.show_line13(gcp, "\\x08골드가 부족합니다 (", need, ")")       # 13번째 줄(오류 줄), hold=(15, 5000)
    dp.set_tbl(92, "\\x08자동사냥 \\x1C", Dec(level), "\\x04단계")     # 버튼 설명(stat_txt.tbl), 끝 U+2009 + NUL
    t = dp.Template("남은 적 ", n); DoActions(SetMissionObjectives(t.string)); t.update()
    with dp.pinned():                                              # FixText(1)…(2): 매 프레임 같은 줄
        dp.show(dp.LOCAL, "…"); dp.show(dp.LOCAL, "…")
    dp.max_len("Lv ", lv, layout=False)                            # 컴파일 시점 최대 바이트 (TBL capacity 계획)
    sh = dp.show(…); sh.string_id, sh.addr, sh.slots               # 반환값 Shown (시험·고급용)

epScript (`import eudext.display as dp;` — 모듈 함수는 f_ 로 번역된다: `dp.show(…)` → `dp.f_show(…)`):

    dp.show(dp.LOCAL, "\\x07HP ", hp, " / ", nf.Man(gold, colors="dps", after=0x04));
    dp.show_line13(P1, "\\x08ERROR \\x04: 골드 부족");
    dp.begin_pinned(); dp.show(P1, "…"); dp.end_pinned();          // with 가 없으므로 짝으로
    const t = dp.Template("남은 적 ", n);  t.update();  DoActions(SetMissionObjectives(t.string));
    dp.show(P1, list(sd.wrap(dp.PName(0), "님")));                   // 목록(파이썬 list·tuple)은 펼친다

## 원소(parts) — S3 7.3

| 원소 | 뜻 | 최대 바이트 |
|---|---|---|
| `str` / `bytes` | 컴파일 시점 상수(UTF-8). 목록·튜플은 펼친다(`*sd.wrap(…)` 대신 `sd.wrap(…)` 도 됨) | 그 길이 |
| `int` 상수 | 부호 있는 10진 상수(32비트 범위는 32비트로 읽는다: `0xFFFFFFFF` → `-1`, 그 밖은 64비트) | — |
| `EUDVariable`·`EUDLightVariable`·`Cell`·상수식 | 실행 중 값, **부호 있는** 10진(DPL V 원소, D17). 부호 없는 값은 `Dec(v)` | 11 |
| `Int64` | 부호 있는 64비트 10진(W 원소) | 20 |
| `numfmt.Dec/Hex/Man/Per/Gauge`, `numfmt.dp.*` | 서식 객체 그대로 | 그 객체의 `max_len` |
| `PName(p, color="player")` | 플레이어 p(0~7 상수·변수) 이름(0x57EEEB + 36p, D15). `color`: `"player"`(DPL 색표 08,0E,0F,10,11,15,16,17) / None / 색 바이트. 변수 p ≥ 8 이면 아무것도 쓰지 않는다 | 1 + 25 |
| `LocalName(color="player")` | 이 PC 의 이름(`PName(f_getuserplayerid())`) — 관전자면 빈 글 | 1 + 25 |
| `Byte(v)` | v 의 하위 1바이트(색 코드·글자 — DPL 숫자 원소 `x[2]`). 0 이면 0x0D | 1 |
| `Bytes(v1, v2, …)` | 여러 바이트 이어서(DPL V 목록) | n |
| `Pick(i, table, default="")` | 번호 → 상수 문자열 표(dict·list)에서 실행 중에 고른 글(DPL 맨 함수 + print_utf8_A) | 표의 최대 |
| `Part` 하위 클래스 | `fmt()`(eudplib 인쇄 가능 값)와 `max_len` 만 구현하면 된다. 이미 있는 값은 `Part.of(값, max_len)` | max_len |

## 대상(target) — S3 7.6 (판정은 `players.contains_user`)

상수 0~7·P1~P8 · 관전자 128~131·P9~P12 · `EUDVariable` · `CurrentPlayer` · `Force1`~`Force4`·`AllPlayers`(컴파일 시점 표 —
맵 FORC. TEP `SetForces` 표와 다르면 `players.set_table`) · `players.Humans`/`Observers`/`Everyone`/`Allies`/`Targets` · 목록 ·
`dp.LOCAL`(모든 PC 가 각자 자기 화면에 — DPS `LCP`, 관전자 포함). `show_line13` 은 관전자·`LOCAL` 을 받지 않는다(원본과 같음).

## 의미와 알고리즘

- **틀(template) 버퍼**: 호출 자리마다 맵 문자열 하나(중복 합치기 없음)를 만들고 상수 원소는 **그 문자열에 굽는다**(DPL 틀과 같은 방식).
  실행 중 원소는 4바이트 경계에 맞춘 **자리(slot)**(크기 = max_len 을 4 배수로 올림)를 받고, 자리의 남는 바이트와 맞춤 바이트는 0x0D
  (보이지 않는 글자 — DPL·eudplib 과 같은 가정, 인게임 E6-7)다. 그래서 상수 글자는 실행 비용이 0 이고, 갱신은 자리만 다시 쓴다.
  보이는 글은 원소를 이어 붙인 것과 같다. 바이트 길이는 (자리 크기 − 실제 길이)만큼 길어진다(DPL 보다 짧다: V 16 → 12).
- 자리 쓰기: 고정 길이 서식(맨 변수 = `Dec(v, sign="-", width=12)`, Int64 = 폭 20, `numfmt.dp.dec16` 등)·`Man`·`Gauge` 는 numfmt 꼬리가
  **자리 단어에 바로 쓴다**(복사 없음, 오른쪽 맞춤). 그 밖(가변 길이 `Dec`·`Pick`·이름·사용자 Part)은 자리를 0x0D 로 지운 뒤
  `f_dbstr_print`(바이트 복사, 왼쪽 맞춤). `Byte`/`Bytes` 는 마스크 쓰기.
- `show`: [every 시계 1] → `EUDIf(contains_user(target))` → (갱신: [조건이면] 지우기·색 1 + 자리마다 1~3) → 표시 1
  (`DisplayTextAll` + 소리 + CP 되돌리기를 한 트리거에). 서식은 이 PC 가 대상일 때만 만든다(S3 7.1-1).
  상수만 있으면 버퍼 없이 `players.run_as(target, DisplayText(글))`(LOCAL 은 `DisplayTextAll`).
- `every=N`: 호출 자리 시계(`EUDLightVariable`)가 모든 PC 에서 매 호출 1 씩 줄고(포화), 0 인 호출에서 갱신하고 N 으로 되돌린다
  (대상이 된 PC 는 바로 갱신). `update_if=조건`: 참일 때만 갱신. 둘 다 주면 둘 다 참일 때. 표시는 매 호출.
- `pin=True`: 표시 직전 0x640B58(다음 채팅 줄)을 읽어 두고 표시한 뒤 되돌린다(FixTextPreset 3). `pinned()` 는 블록 앞뒤로 같은 일(FixText 1·2).
- `show_line13`: 공유 — 대상마다 `f_raise_CCMU(p)`(+ `hold`), 로컬 — 이 PC 가 대상이면 0x641598 에 틀 전체 + NUL 을 쓰고 자리를 채운다.
  틀 길이가 217바이트를 넘으면 빌드 오류. **공유 조건에서만 부른다**(로컬 구역 안이면 빌드 경고 — CCMU 는 공유 동작).
- `set_tbl`: `GetTBLAddr(id)` 에 원소를 **바이트 그대로 이어서**(0x0D 채움 없음) `f_dbstr_print` 로 쓰고 tail(기본 U+2009) + NUL(eos, D16).
  모든 PC 에서 쓴다. capacity 를 주면 최대 길이(+NUL)가 넘을 때 빌드 오류.
- `Template`: 틀 버퍼만 만들고(`t.string` = 문자열 번호) `t.update()` 가 모든 PC 에서 자리를 쓴다(로컬 분기 없음).

## 원본(DisplayPrint)과 다른 점 — 옮길 때 주의

1. **CP 를 되돌린다**(DESIGN 3.6). 원본은 대상 V·FP 로 남겼다(S3 9-1).
2. 맨 `EUDVariable` 은 부호 있는 10진(원본과 같음). eudplib `f_sprintf("{}")` 는 부호 없음(S3 9-2).
3. 숫자 원소(`x[2]` = 변수 번호)는 `Byte(var)`, V.fwc 는 `Dec(v, fullwidth=True)`, V 목록은 `Bytes(*vs)`, 맨 함수는 `Pick` (S3 7.5).
4. 이름은 0x57EEEB(eudplib 과 같음, D15). 옛 바이트 그대로는 `numfmt.dp.name20(p)`(0x6D0FDC).
5. 틀 버퍼를 호출 자리끼리 나누지 않는다(원본은 글자가 같은 틀끼리 버퍼를 나눠 썼다, S3 9-10).
6. TBL 끝에 NUL 을 쓴다(`eos=True`, D16 — 원본 호환은 `eos=False`). TBL 의 맨 변수는 0x0D 채움 없이 가변 길이(옛 16B 배치는 `numfmt.dp.dec16`).
7. `PName` 변수 p ≥ 8 이면 빈 글(원본은 이전 내용이 남았다). `Byte` 0 은 0x0D(원본은 NUL 이라 뒤가 잘렸다).

비용(docs/COSTS.md "display (WP6b)"): 모듈 docstring 아래 함수마다. CP: 모든 함수가 호출자의 CP 를 바꾸지 않는다.
로컬: 버퍼·13번째 줄·TBL·0x640B58 은 PC 마다 달라도 되는 표시 구역이다(S3 7.1-4). 공유 로직이 읽지 않는다.
출처: docs/spec/S3_display.md(DPL = MapSource/Library/DisplayPrint.lua), DPS_Enhance eudplib-port e7efff2 `eud/spec/G8_text_scrdb.md` 1.5~1.9,
`eud/ctrig/text.py`(직접 쓰기 `_direct`·FixText), eudplib 0.81 `string/cpprint.py`(f_raise_CCMU·PName 주소)·`strbuffer.py`·`tblprint.py`·`userpl.py`.
"""

import contextlib
import copy

from eudplib import (
    EPD,
    Condition,
    CurrentPlayer,
    Db,
    DisplayText,
    DisplayTextAll,
    DoActions,
    EncodeString,
    EUDArray,
    EUDBreak,
    EUDEndIf,
    EUDEndSwitch,
    EUDFunc,
    EUDIf,
    EUDLightVariable,
    EUDOnStart,
    EUDReturn,
    EUDSwitch,
    EUDSwitchCase,
    EUDVArray,
    EUDWhile,
    EUDEndWhile,
    EUDVariable,
    EUDXVariable,
    EncodePlayer,
    EncodeUnit,
    Exactly,
    Forward,
    GetMapStringAddr,
    GetTBLAddr,
    MemoryX,
    NextTrigger,
    PlayWAV,
    PlayWAVAll,
    RawTrigger,
    SetDeaths,
    SetMemory,
    SetMemoryEPD,
    SetMemoryX,
    SetTo,
    VProc,
    f_bwrite_epd,
    f_dbstr_print,
    f_dwread_epd,
    f_dwwrite_epd,
    f_repmovsd_epd,
    f_getuserplayerid,
    f_gettextptr,
    f_raise_CCMU,
    f_setcurpl2cpcache,
    ptr2s,
    unProxy,
)

from eudext import _compat, _parts, i64, local, numfmt, players
from eudext.errors import EudextError, fail, warn

M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1
D = 0x0D
TBL_TAIL = "\u2009"  # S3 7.2 tail 기본값 (U+2009 가는 공백 — 원본 DisplayPrintTbl 의 E2 80 89)
LINE13_ADDR = 0x641598  # 0x640B60 + 12·218 (13번째 줄 = 오류 줄)
LINE_BYTES = 218
LINE13_MAX = 217  # NUL 자리를 뺀 최대 바이트
TEXT_PTR_ADDR = 0x640B58  # 다음 채팅 줄 번호 (로컬)
NAME_ADDR = 0x57EEEB  # 플레이어 구조체(0x57EEE0, 36B) +11 = 이름 (eudplib PName 과 같음, DESIGN 7절 D15)
NAME_STRUCT = 36
NAME_MAX = 25
DPL_COLORS = numfmt.DPL_COLORS  # DPL:1155 ColorCode (P1~P8)
_N_DUMMY = 24

__all__ = [
    "Byte",
    "Bytes",
    "DPL_COLORS",
    "LINE13_ADDR",
    "LINE13_MAX",
    "LOCAL",
    "LocalName",
    "NAME_ADDR",
    "PName",
    "Part",
    "Pick",
    "Shown",
    "TBL_TAIL",
    "Template",
    "begin_pinned",
    "end_pinned",
    "f_begin_pinned",
    "f_end_pinned",
    "f_max_len",
    "f_pinned",
    "f_set_tbl",
    "f_show",
    "f_show_line13",
    "max_len",
    "pinned",
    "set_tbl",
    "show",
    "show_line13",
]

# 직접 쓰기에서 버리는 반환 칸(쓰기만 하고 읽지 않는다 — 호출 자리끼리 나눠 써도 된다)과 부분 단어 임시 칸
_DUMMY = [EUDVariable() for _ in range(_N_DUMMY)]
_TMP = EUDVariable()
# pin=True 가 표시 직전에 0x640B58 을 담아 두는 칸 (읽기·되돌리기가 같은 호출 안이라 호출 자리끼리 나눠 쓴다)
_PIN = EUDXVariable(EPD(TEXT_PTR_ADDR), SetTo, 0)

_state = {"ids": [], "pins": []}


@_compat.register_build_reset
def _reset_build():
    # 앞 빌드(앞 LoadMap)에서 만든 문자열 번호의 주소 조회만 지운다 — 지금 맵에서 만든 것(모듈 전역 Template)은 둔다
    token = _compat.string_map_token()
    stale = [sid for sid, tok in _state["ids"] if tok is not token]
    _compat.forget_mapstring_addrs(stale)
    _state["ids"] = [(sid, tok) for sid, tok in _state["ids"] if tok is token]
    del _state["pins"][:]
    # eudplib 은 GetMapStringAddr(상수) 주소를 첫 빌드에서만 푼다 → 빌드마다 다시 건다 (한 프로세스 여러 빌드 — 시험·도구)
    _compat.refresh_mapstring_queries()


def _new_string(content):
    sid = _compat.force_add_string(content)
    _state["ids"].append((sid, _compat.string_map_token()))
    return sid


def _up4(n):
    return -(-n // 4) * 4


def _flag(name, v):
    if isinstance(v, bool) or (isinstance(v, int) and v in (0, 1)):
        return bool(v)
    fail("display: %s 는 True/False 여야 합니다 (%r)", name, v)


def _chunked(acts, conds=None):
    for i in range(0, len(acts), 64):
        RawTrigger(conditions=conds, actions=acts[i : i + 64])


# =============================================================================================
# 대상: dp.LOCAL
# =============================================================================================


class _Local:
    """`dp.LOCAL` — 모든 PC 가 각자 자기 화면에 찍는 대상(DPS `LCP` 관용구, 관전자 포함)."""

    __slots__ = ()
    dont_flatten = True

    def __repr__(self):
        return "dp.LOCAL"

    def __bool__(self):
        raise EudextError("dp.LOCAL 은 대상 표식입니다 (조건이 아닙니다)")


LOCAL = _Local()


def _has_local(target):
    if target is LOCAL:
        return True
    if isinstance(target, (list, tuple)):
        return any(_has_local(x) for x in target)
    return False


# =============================================================================================
# 원소 (Part)
# =============================================================================================


class Part:
    """원소 확장용 기반 클래스 (S3 7.3). `fmt()` 와 `max_len` 만 구현하면 된다.

    - `fmt()`: 이 자리에 필요한 트리거를 내고 eudplib 인쇄 가능 값(bytes·str·`ptr2s`·`epd2s`·`Db`)을 돌려준다.
      display 는 이 값을 자리로 복사한다(`f_dbstr_print`). 로컬 분기 안에서 불릴 수 있으므로 공유 상태를 바꾸지 않는다.
    - `max_len`: 출력 최대 바이트(NUL 제외). 넘으면 뒤 원소를 덮는다.
    - `const_bytes()`(선택): 값이 컴파일 시점에 정해지면 그 바이트(틀에 굽는다).
    - `Part.of(값, max_len)`: 이미 있는 인쇄 가능 값(예: `StringBuffer`, `epd2s(…)`)을 원소로.
    인자: 없음(하위 클래스 몫)
    반환: -
    비용: 하위 클래스 fmt() + 자리 지우기 1 + 복사(바이트당 실행 약 35, docs/COSTS.md)
    CP: fmt() 는 CP 를 바꾸지 않아야 한다
    로컬: fmt() 는 로컬 분기 안에서 불릴 수 있다
    epScript: 파이썬에서 정의해 import 한다
    출처: S3 7.3 (DPL 함수 원소 `{f, …}` 의 일반화)
    """

    dont_flatten = True
    max_len = None

    def fmt(self):  # pragma: no cover — 하위 클래스
        raise NotImplementedError("Part.fmt() 를 구현하세요")

    def const_bytes(self):
        return None

    def __format__(self, spec):
        raise EudextError("display: 원소는 format()/f-문자열에 쓸 수 없습니다. 인쇄 함수에 그대로 넘기거나 .fmt()")

    def __iter__(self):
        raise TypeError("display 원소는 펼칠 수 없습니다")

    def __repr__(self):
        return "<eudext.display.%s max_len=%s>" % (type(self).__name__, self.max_len)

    # --- display 내부 훅 (하위 클래스가 더 싼 경로를 줄 수 있다) ---
    def _exact(self):
        """바이트 그대로 이어 쓰는 곳(TBL)에 넘길 인쇄 가능 값 목록."""
        return [self.fmt()]

    def _slot(self):
        return _CopySlot(self)

    @staticmethod
    def of(value, max_len):
        """인쇄 가능 값(또는 fmt() 를 가진 객체)을 원소로 감싼다.

        인자: value(bytes·str·ptr2s·epd2s·Db·StringBuffer 등), max_len(최대 바이트, 1~4096 정수)
        반환: Part
        비용: 자리 지우기 1 + 복사(바이트당 실행 약 35)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: 파이썬 전용
        출처: 새로 작성
        """
        return _Wrapped(value, max_len)


def _check_max_len(name, n):
    n = unProxy(n)
    if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= 4096:
        fail("%s: max_len 은 0~4096 정수여야 합니다 (%r)", name, n)
    return n


class _Wrapped(Part):
    def __init__(self, value, max_len):
        if isinstance(value, (list, tuple)) or value is None:
            fail("Part.of: 인쇄 가능한 값 하나를 넘기세요 (%r)", value)
        self._value_obj = value
        self.max_len = _check_max_len("Part.of", max_len)

    def const_bytes(self):
        v = unProxy(self._value_obj)
        if isinstance(v, str):
            return v.encode("utf-8")
        if isinstance(v, (bytes, bytearray)):
            return bytes(v)
        return None

    def fmt(self):
        v = self._value_obj
        f = getattr(v, "fmt", None)
        return f() if callable(f) else v


class _SignedNum(Part):
    """맨 변수·Int64 → 부호 있는 10진 (D17). 틀 자리는 고정 폭(직접 쓰기), TBL 은 가변 길이."""

    def __init__(self, v, bits):
        self._v = v
        self._bits = bits
        self._dec = numfmt.Dec(v, sign="-", bits=bits)
        self.max_len = 11 if bits == 32 else 20

    def const_bytes(self):
        return self._dec.const_bytes()

    def fmt(self):
        return self._dec.fmt()

    def _slot(self):
        width = 12 if self._bits == 32 else 20
        return _numfmt_slot(numfmt.Dec(self._v, sign="-", bits=self._bits, width=width)) or _CopySlot(self)


def _color_byte(name, color):
    if color is None or color == "player":
        return color
    c = unProxy(color)
    if isinstance(c, bool) or not isinstance(c, int) or not 1 <= c <= 255:
        fail('%s: color 는 "player", None, 1~255 색 바이트입니다 (%r)', name, color)
    return c


_EMPTY = []  # 빈 문자열 Db 하나 (EUDObject 라 빌드 사이에 다시 써도 된다)
_name_fn = []


def _empty_db():
    if not _EMPTY:
        _EMPTY.append(Db(4))
    return _EMPTY[0]


def _name_info():
    """공유 본문: p → (이름 주소, 틀 자리 첫 단어 = 색|0D0D0D00, 색 단어 = 색). p ≥ 8 이면 (빈 문자열, 0D×4, 0)."""
    if _name_fn:
        return _name_fn[0]
    empty = _empty_db()

    def fn(p):
        ptr, cslot, cword = EUDVariable(), EUDVariable(), EUDVariable()
        RawTrigger(actions=[ptr.SetNumber(empty), cslot.SetNumber(0x0D0D0D0D), cword.SetNumber(0)])
        for i in range(8):
            RawTrigger(
                conditions=p.Exactly(i),
                actions=[
                    ptr.SetNumber(NAME_ADDR + NAME_STRUCT * i),
                    cslot.SetNumber(0x0D0D0D00 | DPL_COLORS[i]),
                    cword.SetNumber(DPL_COLORS[i]),
                ],
            )
        EUDReturn(ptr, cslot, cword)

    fn.__name__ = "display_name_info"
    f = EUDFunc(fn)
    _name_fn.append(f)
    return f


_NC = {}  # 변형("player" | "plain") → {"base": 원소 0 주소(Forward), "fn": EUDFunc, "registered": bool}
_NC_WORDS = 7  # 이름 칸 28바이트 = 단어 7


@_compat.register_build_reset
def _reset_name_cache():
    for ent in _NC.values():
        ent["registered"] = False


def _nc_elem(base, k):
    return base + 72 * k


def _nc_epd(base, k, field):
    # 72B 원소의 칸 EPD: next +1, dest +86, value +87 (_compat.custom_varray 설명)
    return EPD(base) + 18 * k + field


def _name_cache(variant):
    """이름 캐시: 플레이어 8 × 단어 7 의 72B 원소 사슬(`_compat.custom_varray`) + 게임 시작 때 채우는 고리(빌드마다 한 번 등록).

    원소 (p, j) 로 뛰면 `dest ← 값` 한 번 하고 (p, j+1) 로 간다. (p, 6) 의 next 는 부르는 쪽이 고친다.
    """
    ent = _NC.get(variant)
    if ent is None:
        base = Forward()
        triples = []
        for k in range(8 * _NC_WORDS):
            nxt = _nc_elem(base, k + 1) if k % _NC_WORDS != _NC_WORDS - 1 else 0
            triples.append((EPD(_DUMMY[1].getValueAddr()), 0x0D0D0D0D, nxt))
        base << _compat.custom_varray(triples)
        ent = _NC[variant] = {"base": base, "fn": None, "registered": False}
    if not ent["registered"]:
        ent["registered"] = True
        EUDOnStart(lambda: _name_cache_fill(ent["base"], variant))
    return ent


def _name_cache_fill(base, variant):
    pre = 1 if variant == "player" else 0
    init = bytearray()
    for i in range(8):
        block = bytearray([D]) * (4 * _NC_WORDS)
        if pre:
            block[0] = DPL_COLORS[i]
        init += block
    buf = Db(bytes(init) + b"\0" * 32)
    # 뒤 플레이어부터 복사: 25바이트 이름에 NUL 이 없어 넘쳐도 이미 복사가 끝난 뒤 칸만 덮지 않게 (다음 칸은 먼저 채워져 있다)
    n = EUDVariable()
    dst = EUDVariable()
    src = EUDVariable()
    n << 8
    dst << buf + 4 * _NC_WORDS * 7 + pre
    src << NAME_ADDR + NAME_STRUCT * 7
    if EUDWhile()(n.AtLeast(1)):
        f_dbstr_print(dst, ptr2s(src), EOS=False)
        RawTrigger(actions=[n.SubtractNumber(1), dst.SubtractNumber(4 * _NC_WORDS), src.SubtractNumber(NAME_STRUCT)])
    EUDEndWhile()
    k = EUDVariable()
    se = EUDVariable()
    de = EUDVariable()
    k << 0
    se << EPD(buf)
    de << _nc_epd(base, 0, 87)
    if EUDWhile()(k.AtMost(8 * _NC_WORDS - 1)):
        w = f_dwread_epd(se)
        f_dwwrite_epd(de, w)
        RawTrigger(actions=[k.AddNumber(1), se.AddNumber(1), de.AddNumber(18)])
    EUDEndWhile()


def _name_cache_jump(base, p, dests):
    """원소 사슬 p 를 dests(단어 7개 EPD)로 복사하고 돌아온다 (트리거 1 + 실행 7)."""
    ret = Forward()
    acts = [SetMemoryEPD(_nc_epd(base, _NC_WORDS * p + j, 86), SetTo, dests[j]) for j in range(_NC_WORDS)]
    acts.append(SetMemoryEPD(_nc_epd(base, _NC_WORDS * p + _NC_WORDS - 1, 1), SetTo, ret))
    RawTrigger(nextptr=_nc_elem(base, _NC_WORDS * p), actions=acts)
    ret << NextTrigger()


def _name_cache_fn(variant):
    ent = _name_cache(variant)
    if ent["fn"] is not None:
        return ent["fn"]
    base = ent["base"]

    def fn(p):
        rets = [EUDVariable() for _ in range(_NC_WORDS)]
        RawTrigger(actions=[r.SetNumber(0x0D0D0D0D) for r in rets])
        EUDSwitch(p)
        for i in range(8):
            if EUDSwitchCase()(i):
                _name_cache_jump(base, i, [EPD(r.getValueAddr()) for r in rets])
                EUDBreak()
        EUDEndSwitch()
        EUDReturn(*rets)

    fn.__name__ = "display_name_cache_" + variant
    ent["fn"] = EUDFunc(fn)
    return ent["fn"]


class PName(Part):
    """플레이어 이름 원소 (DPL `PName(p)`).

    인자: p(0~7·P1~P8 상수 또는 변수 — 변수 값이 8 이상이면 아무것도 쓰지 않는다), color("player" = DPL 색표 |
          None = 색 없음 | 1~255 색 바이트), cache(True = 게임 시작 때 이름을 72B 칸 7개씩에 담아 두고 단어째 옮긴다 —
          시작 뒤 SetPName 으로 바꾼 이름은 보이지 않는다. DPL 의 이름 캐시와 같은 방식. TBL(set_tbl)에서는 늘 실시간)
    반환: Part (최대 1 + 25 바이트)
    비용: 실시간 = 이름 복사(바이트당 약 35, 이름 길이 + 1) + 상수 p 는 색 0 / 변수 p 는 공유 본문 11 + 호출 1.
          cache=True = 상수 p 호출 1 / 실행 약 8, 변수 p 공유 본문(EUDSwitch) + 호출 1 / 실행 약 25,
          시작 때 한 번 약 3,000 + 칸 56개(4KB) (docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전 (이름 칸은 모든 PC 가 같다 — LocalName 은 다르다)
    epScript: `dp.show(P1, dp.PName(gcp), "님");`
    출처: DPL:1253 PName·1012 Call_VtoName(주소는 eudplib `PName` 과 같은 0x57EEEB, D15), S3 7.3
    """

    def __init__(self, p, color="player", cache=False):
        self._color = _color_byte("PName", color)
        self._cache = _flag("cache", cache)
        e = EncodePlayer(unProxy(p)) if not isinstance(p, (str, bytes)) else p
        if _compat.is_var(e):
            self._p = e
            self._const = None
        elif isinstance(e, int) and not isinstance(e, bool) and 0 <= e <= 7:
            self._p = e
            self._const = e
        else:
            fail("PName: 플레이어는 0~7(P1~P8) 상수 또는 EUDVariable 입니다 (%r) — 관전자·CurrentPlayer 는 변수로 넘기세요", p)
        self.max_len = (1 if self._color is not None else 0) + NAME_MAX

    def _const_color(self):
        if self._color is None:
            return b""
        if self._color == "player":
            return bytes([DPL_COLORS[self._const]])
        return bytes([self._color])

    def _exact(self):
        if self._const is not None:
            out = []
            c = self._const_color()
            if c:
                out.append(c)
            out.append(ptr2s(NAME_ADDR + NAME_STRUCT * self._const))
            return out
        ptr, cword = EUDVariable(), EUDVariable()
        _name_info()(self._p, ret=[ptr, _DUMMY[0], cword])
        out = []
        if self._color is not None:
            cdb = Db(8)
            if self._color == "player":
                _parts.write_addr(cdb, cword)
            else:  # 고정 색은 p ≤ 7 일 때만
                RawTrigger(actions=SetMemory(cdb, SetTo, 0))
                RawTrigger(conditions=self._p.AtMost(7), actions=SetMemory(cdb, SetTo, self._color))
            out.append(ptr2s(cdb))
        out.append(ptr2s(ptr))
        return out

    def fmt(self):
        """이 자리 버퍼([색][이름] + NUL)를 만들고 ptr2s 를 돌려준다(eudplib 인쇄 함수용)."""
        buf = Db(_up4(self.max_len) + 8)
        items = self._exact()
        f_dbstr_print(buf, *items)
        return ptr2s(buf)

    def _slot(self):
        if self._cache:
            return _NameCacheSlot(self)
        return _NameSlot(self)


class LocalName(PName):
    """이 PC 의 플레이어 이름 = `PName(f_getuserplayerid())`. 관전자(128~131)면 빈 글.

    인자: color, cache(PName 과 같음)
    반환: Part (최대 1 + 25 바이트)
    비용: PName 변수 p 와 같음
    CP: 바꾸지 않음
    로컬: **로컬 값** — 표시 버퍼·TBL 에만 쓴다(모든 PC 가 다른 글을 쓴다)
    epScript: `dp.show(dp.LOCAL, "안녕 ", dp.LocalName());`
    출처: DPL `PName("LocalPlayerID")`(DPL:1014 Call_VtoLPName), S3 7.3
    """

    def __init__(self, color="player", cache=False):
        super().__init__(unProxy(f_getuserplayerid()), color=color, cache=cache)


def _byte_value(name, v):
    u = unProxy(v)
    if isinstance(u, bool) or u is None:
        fail("%s: 정수 상수 또는 EUDVariable 이어야 합니다 (%r)", name, v)
    if isinstance(u, int):
        if not -128 <= u <= 0xFF:
            fail("%s: 바이트 상수는 -128~255 입니다 (%r)", name, v)
        b = u & 0xFF
        return b if b else D
    if _compat.is_var(u):
        return u
    fail("%s: 정수 상수 또는 EUDVariable 이어야 합니다 (%r) — EUDLightVariable·Cell 은 EUDVariable 에 복사하세요", name, v)


class Bytes(Part):
    """바이트 여러 개를 이어 쓰는 원소 (DPL V 목록 `{v1, v2, …}` 의 하위 1바이트씩). 0 은 0x0D 로 바꾼다.

    인자: values(정수 상수 -128~255 또는 EUDVariable — 하위 8비트만 쓴다), 1~64 개
    반환: Part (최대 n 바이트)
    비용: 상수 바이트 = 0(틀에 굽는다) / 변수 바이트 = 쓰기 1~2 + 0 검사 1 (첫 바이트가 아니면 eudplib f_bwrite_epd)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `dp.show(P1, dp.Bytes(on0, on1));`
    출처: DPL:108 V 목록 원소(Call_TBwrite), S3 7.3
    """

    def __init__(self, *values):
        flat = []
        for v in values:
            if isinstance(v, (list, tuple)):
                flat.extend(v)
            else:
                flat.append(v)
        if not 1 <= len(flat) <= 64:
            fail("Bytes: 바이트는 1~64 개입니다 (%d)", len(flat))
        self._vals = [_byte_value("Bytes", v) for v in flat]
        self.max_len = len(self._vals)

    def const_bytes(self):
        if all(isinstance(v, int) for v in self._vals):
            return bytes(self._vals)
        return None

    def fmt(self):
        """이 자리 버퍼(바이트 + NUL)를 채우고 ptr2s 를 돌려준다(상수 바이트는 버퍼 초기값)."""
        c = self.const_bytes()
        if c is not None:
            return c
        init = bytes(v if isinstance(v, int) else D for v in self._vals)
        buf = Db(init + b"\0" * (-len(init) % 4 + 4))
        self._write_vars_only(buf, EPD(buf))
        return ptr2s(buf)

    def _write_consts_only(self, addr, prep):
        for i, v in enumerate(self._vals):
            w, sh = divmod(i, 4)
            if isinstance(v, int):
                prep.append(SetMemoryX(addr + 4 * w, SetTo, v << (8 * sh), 0xFF << (8 * sh)))

    def _write_vars_only(self, addr, epd):
        for i, v in enumerate(self._vals):
            if isinstance(v, int):
                continue
            w, sh = divmod(i, 4)
            if sh == 0:
                _parts.write_addr(addr + 4 * w, v, 0xFF)
            else:
                f_bwrite_epd(epd + w, sh, v)
            RawTrigger(
                conditions=MemoryX(addr + 4 * w, Exactly, 0, 0xFF << (8 * sh)),
                actions=SetMemoryX(addr + 4 * w, SetTo, D << (8 * sh), 0xFF << (8 * sh)),
            )

    def _slot(self):
        return _BytesSlot(self)


class Byte(Bytes):
    """바이트 하나 원소 (DPL 숫자 원소 `x[2]` = 변수의 하위 1바이트 — 색 코드·글자). 0 은 0x0D 로 바꾼다.

    인자: v(정수 상수 -128~255 또는 EUDVariable)
    반환: Part (1 바이트)
    비용: 상수 0 / 변수 = 쓰기 1 + 0 검사 1 (docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `dp.show(P1, dp.Byte(color), "색 글자");`
    출처: DPL:280~285 숫자 원소(변수 번호 → 값의 하위 1바이트), S3 2.3·7.5
    """

    def __init__(self, v):
        super().__init__(v)


def _pick_text(name, s):
    if isinstance(s, str):
        b = s.encode("utf-8")
    elif isinstance(s, (bytes, bytearray)):
        b = bytes(s)
    else:
        fail("%s: 표의 값은 문자열이어야 합니다 (%r)", name, s)
    if b"\0" in b:
        fail("%s: 표의 문자열에 NUL(\\x00) 이 있습니다 (%r)", name, s)
    return b


class Pick(Part):
    """번호로 고르는 상수 문자열 원소 (DPL 맨 함수 원소 `HeroTextFunc` + `print_utf8_A` 대체).

    표는 컴파일 시점에 `Db` 하나로 굽고 주소 표(`EUDArray`)로 찾는다. 같은 Pick 객체를 여러 곳에 쓰면 표를 나눈다.
    인자: index(정수 상수 또는 EUDVariable), table(dict {번호 0~4095: 문자열} 또는 list/tuple), default(표에 없는 번호의 글 —
          epScript 는 `default` 가 예약어라 `missing=` 으로)
    반환: Part (최대 = 표 문자열 중 가장 긴 것)
    비용: 상수 번호 = 0(틀에 굽는다) / 변수 = 범위 자르기 2 + 표 읽기(실행 약 40) + 단어 복사(f_repmovsd_epd, 4바이트당 약 35).
          항목 자료 = 항목 수 × max_len(4 배수) 바이트 (TBL 에 쓰면 NUL 문자열 표를 따로 둔다)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `dp.show(P1, dp.Pick(uid, list("마린", "파벳"), missing="?"));`
    출처: S3 5.7·7.3 (Seed CunitSystem.lua:667, Stel System.lua:1663 의 0x40 바이트 이름 표)
    """

    def __init__(self, index, table, default="", missing=None):
        if missing is not None:  # epScript 는 default 가 예약어라 missing= 으로 넘긴다
            default = missing
        if isinstance(table, dict):
            items = {}
            for k, s in table.items():
                ku = unProxy(k)
                if isinstance(ku, bool) or not isinstance(ku, int) or not 0 <= ku <= 4095:
                    fail("Pick: 표의 번호는 0~4095 정수입니다 (%r)", k)
                items[ku] = _pick_text("Pick", s)
        elif isinstance(table, (list, tuple)):
            if len(table) > 4096:
                fail("Pick: 표가 너무 깁니다 (%d > 4096)", len(table))
            items = {i: _pick_text("Pick", s) for i, s in enumerate(table)}
        else:
            fail("Pick: table 은 dict 또는 list 입니다 (%r) — epScript 는 list(…)", table)
        if not items:
            fail("Pick: 표가 비었습니다")
        self._table = items
        self._default = _pick_text("Pick", default)
        u = unProxy(index)
        if isinstance(u, bool) or u is None:
            fail("Pick: 번호는 정수 상수 또는 EUDVariable 입니다 (%r)", index)
        if isinstance(u, int):
            self._index = u
        elif _compat.is_var(u) or _compat.is_varbase(u):
            self._index = u
        else:
            fail("Pick: 번호는 정수 상수 또는 EUDVariable 입니다 (%r)", index)
        self.max_len = max([len(s) for s in items.values()] + [len(self._default)])
        self._built = None
        self._built_pad = None

    def const_bytes(self):
        if isinstance(self._index, int):
            return self._table.get(self._index, self._default)
        return None

    def _tables(self):
        """TBL(바이트 그대로)용: NUL 로 끝나는 문자열 Db + 주소 표 (마지막 칸 = default)."""
        if self._built is not None:
            return self._built
        n = max(self._table) + 1
        data = bytearray()
        offs = {}
        for s in list(self._table.values()) + [self._default]:
            if s not in offs:
                offs[s] = len(data)
                data += s + b"\0"
        db = Db(bytes(data) + b"\0" * (-len(data) % 4 + 4))
        ptrs = [db + offs[self._table.get(i, self._default)] for i in range(n)] + [db + offs[self._default]]
        self._built = (EUDArray(ptrs), n)
        return self._built

    def _padded(self):
        """틀 자리용: 같은 크기(4 배수)로 0x0D 를 채운 항목 Db + EPD 표 (마지막 칸 = default)."""
        if self._built_pad is not None:
            return self._built_pad
        n = max(self._table) + 1
        size = _up4(max(self.max_len, 1))
        data = bytearray()
        offs = {}
        for s in list(self._table.values()) + [self._default]:
            if s not in offs:
                offs[s] = len(data) // 4
                data += s.ljust(size, bytes([D]))
        db = Db(bytes(data))
        epds = [EPD(db) + offs[self._table.get(i, self._default)] for i in range(n)] + [EPD(db) + offs[self._default]]
        self._built_pad = (EUDArray(epds), n, size)
        return self._built_pad

    def _index_var(self, n):
        t = EUDVariable()
        t << self._index
        RawTrigger(conditions=t.AtLeast(n + 1), actions=t.SetNumber(n))
        return t

    def fmt(self):
        """번호 → 문자열 주소를 읽어 ptr2s 로 돌려준다(상수 번호는 bytes)."""
        c = self.const_bytes()
        if c is not None:
            return c
        arr, n = self._tables()
        return ptr2s(arr[self._index_var(n)])

    def _slot(self):
        return _PickSlot(self)


# =============================================================================================
# 원소 정리
# =============================================================================================


def _flatten(parts, out):
    for p in parts:
        if isinstance(p, (list, tuple)):
            _flatten(p, out)
        else:
            out.append(p)


def _int_text(x):
    if -(1 << 31) <= x < (1 << 32):
        v = x & M32
        s = v - (1 << 32) if v >> 31 else v
    elif -(1 << 63) <= x <= M64:
        v = x & M64
        s = v - (1 << 64) if v >> 63 else v
    else:
        fail("display: 64비트 범위 밖 정수 상수 %d", x)
    return str(s).encode("ascii")


def _is_fmt_obj(p):
    return callable(getattr(type(p), "fmt", None)) and getattr(p, "max_len", None) is not None


def _item(p, fname):
    """원소 하나 → ("c", bytes) | ("d", Part/서식 객체) | None(빈 문자열)."""
    if p is LOCAL:
        fail("%s: dp.LOCAL 은 대상 자리에만 씁니다", fname)
    if p is None or isinstance(p, bool):
        fail("%s: 원소로 쓸 수 없는 값 %r (문자열·변수·Int64·서식 객체·Part)", fname, p)
    if isinstance(p, str):
        b = p.encode("utf-8")
    elif isinstance(p, (bytes, bytearray)):
        b = bytes(p)
    elif isinstance(p, float):
        fail("%s: 실수는 쓸 수 없습니다 (%r) — f-문자열로 바꾸거나 numfmt.Per", fname, p)
    elif isinstance(p, (EUDArray, EUDVArray)) or type(p).__name__ in ("EUDArray", "EUDVArray", "_EUDArrayData"):
        fail("%s: 배열은 원소가 아닙니다 — epScript 에서 목록을 넘기려면 list(a, b) (리스트 리터럴은 EUDArray 가 된다)", fname)
    elif isinstance(p, Part) or (isinstance(p, ptr2s) and _is_fmt_obj(p)):
        c = p.const_bytes()
        if c is not None:
            b = bytes(c)
        else:
            _check_max_len(fname, p.max_len)
            return ("d", p)
    else:
        u = unProxy(p)
        if isinstance(u, i64.Int64):
            n = _SignedNum(u, 64)
            b = n.const_bytes()
            if b is None:
                return ("d", n)
        elif isinstance(u, int) and not isinstance(u, bool):
            b = _int_text(u)
        elif isinstance(u, Condition):
            fail("%s: 조건은 원소가 아닙니다 (%r)", fname, p)
        elif type(u).__name__ in ("_EUDArrayData", "_EUDVArrayData"):
            fail("%s: 배열은 원소가 아닙니다 — epScript 에서 목록을 넘기려면 list(a, b) (리스트 리터럴은 EUDArray 가 된다)", fname)
        elif _compat.is_var(u) or _compat.is_varbase(u) or _compat.is_const(u):
            n = _SignedNum(u, 32)
            b = n.const_bytes()
            if b is None:
                return ("d", n)
        elif _is_fmt_obj(p):
            c = p.const_bytes() if callable(getattr(p, "const_bytes", None)) else None
            if c is not None:
                b = bytes(c)
            else:
                _check_max_len(fname, p.max_len)
                return ("d", p)
        elif isinstance(p, ptr2s) or callable(getattr(p, "fmt", None)) or hasattr(p, "_value"):
            fail("%s: 최대 길이를 모르는 인쇄 값입니다 (%r) — dp.Part.of(값, max_len) 으로 감싸세요", fname, p)
        else:
            fail("%s: 원소로 쓸 수 없는 값 %r", fname, p)
    return ("c", b) if b else None


def _items(parts, fname):
    flat = []
    _flatten(parts, flat)
    out = []
    for p in flat:
        it = _item(p, fname)
        if it is None:
            continue
        if it[0] == "c" and out and out[-1][0] == "c":
            out[-1] = ("c", out[-1][1] + it[1])
        else:
            out.append(it)
    for kind, x in out:
        if kind == "c" and b"\0" in x:
            warn("%s: 상수 원소에 NUL(\\x00) 이 있습니다 — 그 뒤 글은 보이지 않습니다", fname)
            break
    return out


def f_max_len(*parts, layout=False):
    """원소들의 최대 바이트 길이(컴파일 시점). layout=False 면 이어 붙인 길이(TBL), True 면 틀 길이(0x0D 자리 포함 — show·13번째 줄).

    인자: parts(원소들), layout(bool)
    반환: int (NUL 제외)
    비용: 없음(트리거 0)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `const n = dp.max_len("HP ", hp);` (→ `f_max_len`)
    출처: S3 7.1-2, 7.2 capacity
    """
    items = _items(parts, "max_len")
    if layout:
        return _Layout(items).size
    return sum(len(x) if k == "c" else x.max_len for k, x in items)


max_len = f_max_len


# =============================================================================================
# 틀 자리 (slot)
# =============================================================================================


class _Slot:
    """틀 자리 쓰기 계획. size = 4 의 배수. clear = 쓰기 전에 0x0D 로 지워야 하나. align = 보이는 글의 맞춤(시험용)."""

    kind = "copy"
    clear = True
    align = "left"
    size = 0

    def prep(self, addr, epd, off):
        """갱신 첫 트리거에 섞을 상수 액션."""
        return []

    def emit(self, addr, epd, off):  # pragma: no cover
        raise NotImplementedError


class _CopySlot(_Slot):
    def __init__(self, obj):
        self.obj = obj
        self.size = _up4(max(obj.max_len, 1))

    def emit(self, addr, epd, off):
        exact = self.obj._exact() if isinstance(self.obj, Part) else [self.obj.fmt()]
        f_dbstr_print(addr + off, *exact, EOS=False)


class _NameSlot(_Slot):
    kind = "name"

    def __init__(self, part):
        self.part = part
        self.size = _up4(part.max_len)

    def prep(self, addr, epd, off):
        p = self.part
        if p._const is not None:
            c = p._const_color()
            if c:
                return [SetMemoryX(addr + off, SetTo, c[0], 0xFF)]
        return []

    def emit(self, addr, epd, off):
        p = self.part
        c = 1 if p._color is not None else 0
        if p._const is not None:
            f_dbstr_print(addr + off + c, ptr2s(NAME_ADDR + NAME_STRUCT * p._const), EOS=False)
            return
        ptr = EUDVariable()
        if p._color == "player":
            _name_info()(p._p, ret=[ptr, epd + off // 4, _DUMMY[0]])
        else:
            _name_info()(p._p, ret=[ptr, _DUMMY[0], _DUMMY[1]])
            if p._color is not None:
                RawTrigger(conditions=p._p.AtMost(7), actions=SetMemoryX(addr + off, SetTo, p._color, 0xFF))
        f_dbstr_print(addr + off + c, ptr2s(ptr), EOS=False)


class _NameCacheSlot(_Slot):
    kind = "namecache"
    clear = False
    size = 4 * _NC_WORDS

    def __init__(self, part):
        self.part = part
        self.variant = "plain" if part._color is None else "player"

    def emit(self, addr, epd, off):
        p = self.part
        w = epd + off // 4
        ent = _name_cache(self.variant)
        if p._const is not None:
            _name_cache_jump(ent["base"], p._const, [w + j for j in range(_NC_WORDS)])
            if isinstance(p._color, int):
                RawTrigger(actions=SetMemoryX(addr + off, SetTo, p._color, 0xFF))
            return
        _name_cache_fn(self.variant)(p._p, ret=[w + j for j in range(_NC_WORDS)])
        if isinstance(p._color, int):
            RawTrigger(conditions=p._p.AtMost(7), actions=SetMemoryX(addr + off, SetTo, p._color, 0xFF))


class _BytesSlot(_Slot):
    kind = "bytes"
    clear = False

    def __init__(self, part):
        self.part = part
        self.size = _up4(part.max_len)

    def prep(self, addr, epd, off):
        acts = []
        self.part._write_consts_only(addr + off, acts)
        return acts

    def emit(self, addr, epd, off):
        self.part._write_vars_only(addr + off, epd + off // 4)


class _PickSlot(_Slot):
    kind = "pick"
    clear = False

    def __init__(self, part):
        self.part = part
        self.size = _up4(max(part.max_len, 1))

    def emit(self, addr, epd, off):
        arr, n, size = self.part._padded()
        src = arr[self.part._index_var(n)]
        f_repmovsd_epd(epd + off // 4, src, size // 4)


class _Name20Slot(_Slot):
    """numfmt.dp.name20 — DPL 이름 칸 20B 를 자리에 바로 (p ≥ 7 이면 이전 내용 그대로 — DPL 과 같음)."""

    kind = "direct"
    clear = False
    align = "right"
    size = 20

    def __init__(self, obj):
        self.obj = obj

    def emit(self, addr, epd, off):
        f = numfmt._name_tail()
        dests = [epd + off // 4 + j for j in range(5)]
        (arg,) = numfmt._args(self.obj._kind)
        if self.obj._kind[0] == "c":
            f(arg, ret=dests)
            return
        if EUDIf()(arg.AtMost(6)):
            f(arg, ret=dests)
        EUDEndIf()


class _NumSlot(_Slot):
    """numfmt 꼬리가 자리 단어에 바로 쓴다 (`_Fmt._emit_buf(nwords, call)` 훅 — numfmt 비공개 계약, WP6b 조각 design.md)."""

    kind = "direct"
    clear = False
    align = "right"

    def __init__(self, obj, whole, fixed_len=None):
        self.obj = obj
        self.whole = whole
        self.fixed_len = fixed_len
        self.size = _up4(obj.max_len if whole else fixed_len)

    def emit(self, addr, epd, off):
        obj = self.obj
        w0 = off // 4
        nsize = self.size // 4

        def hook(nwords, call):
            if self.whole:
                if nwords != nsize:
                    fail("display 내부: numfmt 배치 단어 수가 다릅니다 (%d != %d)", nwords, nsize)
                call([epd + w0 + j for j in range(nwords)] + [_DUMMY[0]])
                return b""
            S = 4 * nwords - self.fixed_len
            q, r = divmod(S, 4)
            if nwords - q != nsize or q + 1 > _N_DUMMY:
                fail("display 내부: numfmt 고정 배치가 예상과 다릅니다 (단어 %d, 시작 %d)", nwords, S)
            dests = list(_DUMMY[:q])
            first = 0
            if r:
                dests.append(_TMP)
                first = 1
            dests += [epd + w0 + j for j in range(first, nsize)]
            dests.append(_DUMMY[q])
            call(dests)
            if r:
                _parts.write_addr(addr + off, _TMP, (M32 << (8 * r)) & M32)
            return b""

        if "_emit_buf" in getattr(obj, "__dict__", {}):
            fail("display 내부: 서식 객체가 이미 다른 곳에서 쓰는 중입니다")
        obj.__dict__["_emit_buf"] = hook
        try:
            r = obj.fmt()
        finally:
            obj.__dict__.pop("_emit_buf", None)
        if r != b"":
            fail("display 내부: 서식 객체가 직접 쓰기 훅을 부르지 않았습니다 (%r)", obj)


def _numfmt_slot(obj):
    """numfmt 서식 객체 → 직접 쓰기 자리 (못 하면 None).

    - `Man`·`Gauge`: 배치 전체(앞은 0x0D)를 바로 쓴다.
    - `Dec`/`Hex`/`Per` 고정 길이: 출력 단어를 바로(앞 부분 단어는 마스크).
    - 가변 길이지만 채움이 0x0D 이고 오른쪽 맞춤이면 **최대 폭으로 넓힌 같은 서식**(앞을 0x0D 로 채움 — 보이는 글이 같다)을 바로 쓴다.
    numfmt 의 비공개 계약(`_plan()`·`_spec`·`_kind`·`_emit_buf`)에 기댄다 — WP6b 조각 design.md 의 요청 참고.
    """
    NumFmt = getattr(numfmt, "_NumFmt", None)
    if isinstance(obj, (numfmt.Man, numfmt.Gauge)):
        return _NumSlot(obj, whole=True)
    Name20 = getattr(numfmt, "_Name20", None)
    if Name20 is not None and isinstance(obj, Name20) and hasattr(numfmt, "_name_tail") and hasattr(numfmt, "_args"):
        return _Name20Slot(obj)
    if NumFmt is None or not isinstance(obj, NumFmt):
        return None
    try:
        plan = obj._plan()
        if _plan_direct(plan):
            return _NumSlot(obj, whole=False, fixed_len=plan.fixed_len)
        spec = obj._spec
        if not (spec.fill == "\r" and spec.neg_fill == "\r" and spec.align == ">" and spec.neg_align == ">"
                and not spec.prefix and plan.lay.nul is None):  # fmt: skip
            return None
        spec2 = copy.copy(spec)
        spec2.width = plan.max_len // spec.render.U
        plan2 = numfmt._plan(spec2)
        if not (_plan_direct(plan2) and plan2.fixed_len == plan.max_len):
            return None
        obj2 = object.__new__(type(obj))
        NumFmt.__init__(obj2, obj._kind, spec2)
    except AttributeError:
        return None
    return _NumSlot(obj2, whole=False, fixed_len=plan2.fixed_len)


def _plan_direct(plan):
    return bool(plan.fixed and plan.fixed_len and plan.lay.nul is None and plan.END == 4 * (plan.E + plan.lay.W))


def _slot_of(obj):
    if isinstance(obj, Part):
        return obj._slot()
    return _numfmt_slot(obj) or _CopySlot(obj)


class _Layout:
    """틀: 상수는 굽고, 실행 중 원소는 4 배수 자리(0x0D)를 받는다."""

    def __init__(self, items):
        buf = bytearray()
        self.slots = []
        for kind, x in items:
            if kind == "c":
                buf += x
                continue
            sl = _slot_of(x)
            buf += bytes([D]) * (-len(buf) % 4)
            off = len(buf)
            buf += bytes([D]) * sl.size
            self.slots.append((off, sl))
        self.content = bytes(buf)
        self.size = len(buf)

    @property
    def dynamic(self):
        return bool(self.slots)

    def clear_actions(self, addr, epd):
        acts = []
        for off, sl in self.slots:
            if sl.clear:
                acts.extend(SetMemoryEPD(epd + (off // 4) + j, SetTo, 0x0D0D0D0D) for j in range(sl.size // 4))
        return acts

    def prep_actions(self, addr, epd):
        acts = []
        for off, sl in self.slots:
            acts.extend(sl.prep(addr, epd, off))
        return acts

    def emit(self, addr, epd):
        for off, sl in self.slots:
            sl.emit(addr, epd, off)

    def direct_words(self):
        """틀 전체를 쓸 때 건너뛸 단어(직접 쓰기 자리가 모두 덮는 단어)."""
        out = set()
        for off, sl in self.slots:
            if isinstance(sl, _NumSlot):
                first = 1 if (not sl.whole and (sl.size - sl.fixed_len) % 4) else 0
                out.update(off // 4 + j for j in range(first, sl.size // 4))
        return out

    def describe(self):
        return [(off, sl.size, sl.kind, sl.align) for off, sl in self.slots]

    def line_sizes(self):
        return [len(x) for x in self.content.split(b"\n")]


def _check_lines(layout, fname):
    for i, n in enumerate(layout.line_sizes()):
        if n > LINE13_MAX:
            warn("%s: %d번째 줄이 최대 %d바이트(0x0D 자리 포함)로 채팅 줄 버퍼(218)를 넘을 수 있습니다", fname, i + 1, n)
            break


# =============================================================================================
# 갱신 주기 (every / update_if)
# =============================================================================================


def _every(every):
    if every is None:
        return None
    u = unProxy(every)
    if isinstance(u, bool) or not isinstance(u, int):
        fail("display: every 는 1 이상 정수 상수입니다 (%r) — 변수 주기는 update_if=v.Exactly(0)", every)
    if not 1 <= u <= 0x7FFFFFFF:
        fail("display: every 는 1 이상입니다 (%r)", every)
    return u if u > 1 else None


def _update_conds(update_if, fresh=False):
    """update_if → 조건 목록 (fresh=True 면 조건 객체를 복사한다 — 같은 조건을 두 번 트리거에 놓지 않게)."""
    if update_if is None:
        return []
    if callable(update_if) and not isinstance(update_if, (Condition, list, tuple)) and not _compat.is_varbase(
        unProxy(update_if)
    ):
        return _update_conds(update_if(), fresh=False)
    items = update_if if isinstance(update_if, (list, tuple)) else [update_if]
    out = []
    for c in items:
        if isinstance(c, (list, tuple)):
            out.extend(_update_conds(c, fresh))
            continue
        u = unProxy(c)
        if isinstance(u, bool) or c is None:
            fail("display: update_if 는 조건·조건 목록·변수(0 이 아니면 참)입니다 (%r)", c)
        if isinstance(c, Condition):
            if fresh:
                c = copy.copy(c)
                if hasattr(c, "fields"):
                    c.fields = list(c.fields)
            out.append(c)
        elif _compat.is_var(u) or _compat.is_varbase(u):
            out.append(u.AtLeast(1))
        else:
            fail("display: update_if 는 조건·조건 목록·변수(0 이 아니면 참)입니다 (%r)", c)
    return out


class _Gate:
    def __init__(self, every, conds, counter=None):
        self.every = every
        self.conds = conds
        self.c = counter
        if every is not None and self.c is None:
            self.c = EUDLightVariable()

    def tick(self):
        if self.c is not None:
            RawTrigger(actions=self.c.SubtractNumber(1))

    def run(self, prep, body):
        """prep(상수 액션)과 body() 를 갱신 조건 아래 낸다."""
        conds = ([self.c.Exactly(0)] if self.c is not None else []) + list(self.conds)
        if self.c is not None:
            prep = [self.c.SetNumber(self.every)] + prep
        if not conds:
            _chunked(prep)
            body()
            return
        skip = Forward()
        _parts.jump_if_not(conds, skip, acts=prep[:64])
        _chunked(prep[64:])
        body()
        skip << NextTrigger()


# =============================================================================================
# show
# =============================================================================================


def _sound_list(sound):
    if sound is None:
        return []
    items = sound if isinstance(sound, (list, tuple)) else [sound]
    out = []
    for w in items:
        if isinstance(w, (list, tuple)):
            out.extend(_sound_list(w))
        elif isinstance(w, (str, bytes)) and w:
            out.append(w)
        else:
            fail("display: sound 는 소리 파일 이름(문자열) 또는 그 목록입니다 (%r)", w)
    return out


class Shown:
    """`show`·`show_line13` 의 반환값 (시험·고급용): 버퍼 문자열 번호·주소·틀 바이트·자리 목록.

    속성: string_id(int 또는 None — 상수만이면 DisplayText 문자열 번호), addr(버퍼 주소 식 또는 None),
          content(틀 바이트), slots([(오프셋, 크기, 종류, 맞춤)]), size(틀 길이)
    """

    __slots__ = ("addr", "content", "size", "slots", "string_id")

    def __init__(self, string_id, addr, layout):
        self.string_id = string_id
        self.addr = addr
        self.content = layout.content if layout is not None else b""
        self.slots = layout.describe() if layout is not None else []
        self.size = layout.size if layout is not None else 0

    def __repr__(self):
        return "<dp.Shown string=%r size=%d slots=%r>" % (self.string_id, self.size, self.slots)


def _const_target(target):
    """상수 글을 run_as 로 보내도 되는 대상인가 — 목록·값에 변수가 없으면 True.

    `players.Targets`(Humans·Everyone·Force …)는 안을 볼 수 없어 run_as 로 보낸다(Targets 안에 변수를 섞으면
    run_as 처럼 같은 PC 가 두 번 볼 수 있다). 변수가 든 목록·값은 이 PC 판정 1회로 보낸다.
    """
    flat = []
    _flatten([target], flat)
    for x in flat:
        if isinstance(x, players.Targets):
            continue
        if isinstance(x, _Local) or x is None or isinstance(x, (bool, str, bytes)):
            return False
        e = EncodePlayer(unProxy(x))
        if isinstance(e, bool) or not isinstance(e, int):
            return False
    return True


def _display_acts(text_or_id, sounds):
    acts = list(DisplayTextAll(text_or_id)) if text_or_id is not None else []
    for w in sounds:
        acts.extend(PlayWAVAll(w))
    return acts


def f_show(target, *parts, sound=None, every=None, update_if=None, pin=False):
    """대상 PC 화면에 서식 있는 글을 띄운다 (DisplayPrint 대체, S3 7.2).

    인자: target(대상 — 모듈 설명, dp.LOCAL), parts(원소 — 모듈 설명), sound(소리 이름 또는 목록 — 대상 PC 에서 PlayWAV),
          every(N 호출마다 버퍼 갱신, 표시는 매 호출), update_if(조건이 참일 때만 갱신 — 조건·목록·변수),
          pin(True = 표시 앞뒤로 0x640B58 저장·복원 — 같은 줄에 고정)
    반환: Shown (버퍼 정보)
    비용: 상수만 = 상수·players.Targets 대상은 `players.run_as`(호출 1 / 실행 2), 변수가 든 대상은 판정 + 분기 1 + 표시 1. 실행 원소가 있으면 호출 자리 = [every 1] + 대상 판정 0~5 +
          분기 1 + 갱신(지우기 1 + 원소마다 1~3, 조건이 있으면 +1) + 표시 1 (pin +1). 실행 = 원소 서식 + 복사 원소의 바이트당 약 35.
          맨 변수 1개 = 호출 4 / 실행 70~76, 약 2.0KB (2026-09-17, docs/COSTS.md "display (WP6b)")
    CP: 바꾸지 않음 (원본 DisplayPrint 와 다름 — 옮길 때 주의)
    로컬: 공유 조건에서 불러도 되고 로컬 구역에서 불러도 된다(글은 대상 PC 에만 — 버퍼는 표시 구역)
    epScript: `dp.show(P1, "\\x07HP ", hp, " / ", hpmax);` (→ `f_show`)
    출처: DPL:146 DisplayPrint, S3 5.1·7.1·7.2, G8 1.5 (eudplib DisplayTextAll·StringBuffer 방식)
    """
    items = _items(parts, "show")
    sounds = _sound_list(sound)
    pin = _flag("pin", pin)
    n_every = _every(every)
    upd = _update_conds(update_if)  # 상수만이어도 검사한다 (갱신할 것이 없으면 쓰지 않는다)
    local_all = _has_local(target)
    if not any(k == "d" for k, _x in items):
        text = items[0][1] if items else None
        if text is None and not sounds:
            return Shown(None, None, None)
        if pin:
            f_gettextptr(ret=[_PIN])
        if not local_all and _const_target(target):
            # 상수 대상·players.Targets: RotatePlayer 식 (호출 1 / 실행 2 — Humans 는 표시 액션이라 존재 판정 없음)
            acts = ([DisplayText(text)] if text is not None else []) + [PlayWAV(w) for w in sounds]
            players.f_run_as(target, *acts)
            if pin:
                VProc(_PIN, [])
        else:
            # 변수가 든 목록·값이면 이 PC 판정 1회 (같은 PC 가 두 번 들어 있어도 한 번만 보인다)
            if not local_all:
                cond = players.f_contains_user(target)
                EUDIf()(cond)
            f_setcurpl2cpcache(v=[_PIN] if pin else [], actions=_display_acts(text, sounds))
            if not local_all:
                EUDEndIf()
        return Shown(EncodeString(text) if text is not None else None, None, None)
    layout = _Layout(items)
    _check_lines(layout, "show")
    cond = None if local_all else players.f_contains_user(target)
    sid = _new_string(layout.content)
    addr = GetMapStringAddr(sid)
    epd = EPD(addr)
    gate = _Gate(n_every, upd)
    gate.tick()
    if cond is not None:
        EUDIf()(cond)
    with local.f_allow():
        gate.run(layout.clear_actions(addr, epd) + layout.prep_actions(addr, epd), lambda: layout.emit(addr, epd))
        if pin:
            f_gettextptr(ret=[_PIN])
        f_setcurpl2cpcache(v=[_PIN] if pin else [], actions=_display_acts(sid, sounds))
    if cond is not None:
        EUDEndIf()
    return Shown(sid, addr, layout)


show = f_show


# =============================================================================================
# pinned
# =============================================================================================


def f_begin_pinned():
    """고정 구역을 연다: 0x640B58(다음 채팅 줄)을 읽어 둔다. `end_pinned()` 가 되돌린다 (CtrigAsm FixText(1)).

    안의 표시가 매 프레임 같은 줄부터 찍힌다(여러 줄 UI). 중첩해도 된다.
    인자: 없음
    반환: None
    비용: 호출 1 (f_gettextptr 1벌 공유, 실행 약 6) + 칸 72B
    CP: 바꾸지 않음
    로컬: 모든 PC 가 자기 줄 번호를 읽고 되돌린다(표시 구역)
    epScript: `dp.begin_pinned(); … dp.end_pinned();` (→ `f_begin_pinned`)
    출처: CtrigAsm FixText(CA:57175), DPS eudplib-port e7efff2 eud/ctrig/text.py:489 FixText, eudplib FixedText
    """
    x = EUDXVariable(EPD(TEXT_PTR_ADDR), SetTo, 0)
    f_gettextptr(ret=[x])
    _state["pins"].append(x)


def f_end_pinned():
    """`begin_pinned()` 으로 연 고정 구역을 닫는다: 0x640B58 을 읽어 둔 값으로 되돌린다 (CtrigAsm FixText(2)).

    인자: 없음
    반환: None
    비용: 호출 1 / 실행 2
    CP: 바꾸지 않음
    로컬: 표시 구역
    epScript: `dp.end_pinned();` (→ `f_end_pinned`)
    출처: CtrigAsm FixText(CA:57175)
    """
    if not _state["pins"]:
        fail("dp.end_pinned(): 열린 begin_pinned() 이 없습니다")
    x = _state["pins"].pop()
    VProc(x, [])


@contextlib.contextmanager
def pinned():
    """`with dp.pinned():` — `begin_pinned()` … `end_pinned()` (파이썬 전용).

    인자: 없음
    반환: 컨텍스트 관리자
    비용: begin + end (호출 2)
    CP: 바꾸지 않음
    로컬: 표시 구역
    epScript: `dp.begin_pinned(); … dp.end_pinned();`
    출처: CtrigAsm FixText(1)/(2), S3 7.2
    """
    f_begin_pinned()
    depth = len(_state["pins"])
    try:
        yield
    except BaseException:
        del _state["pins"][depth - 1 :]
        raise
    f_end_pinned()


def f_pinned():
    """epScript `dp.pinned()` 안내 — with 가 없으므로 `dp.begin_pinned(); … dp.end_pinned();` 를 쓴다."""
    fail("dp.pinned() 은 파이썬 with 전용입니다 — epScript 는 dp.begin_pinned(); … dp.end_pinned();")


begin_pinned = f_begin_pinned
end_pinned = f_end_pinned


# =============================================================================================
# show_line13
# =============================================================================================


def _hold_fn(hold):
    if hold is None:
        return None
    if callable(hold):
        return lambda p: _parts._flat(hold(p))
    if isinstance(hold, (list, tuple)) and len(hold) == 2:
        unit, value = hold
        u = unProxy(value)
        if isinstance(u, bool) or not (isinstance(u, int) or _compat.is_var(u)):
            fail("show_line13: hold 값은 정수 또는 EUDVariable 입니다 (%r)", value)
        unit = EncodeUnit(unit)
        return lambda p: [SetDeaths(p, SetTo, value, unit)]
    fail("show_line13: hold 는 None, (유닛, 값), 또는 fn(p) -> 액션 입니다 (%r)", hold)


def _ccmu_plan(target):
    """대상 → (상수 번호 목록, 변수 목록, CurrentPlayer 여부, players.Targets 목록)."""
    flat = []
    _flatten([target], flat)
    consts, vars_, current, others = set(), [], False, []
    for x in flat:
        if isinstance(x, players.Targets):
            others.append(x)
            continue
        if x is None or isinstance(x, (bool, str, bytes)):
            fail("show_line13: 대상은 0~7·변수·CurrentPlayer·Force·목록입니다 (%r)", x)
        e = EncodePlayer(unProxy(x))
        if _compat.is_var(e):
            if not any(v is e for v in vars_):
                vars_.append(e)
        elif isinstance(e, bool) or not isinstance(e, int):
            fail("show_line13: 대상은 0~7·변수·CurrentPlayer·Force·목록입니다 (%r)", x)
        elif 0 <= e <= 7:
            consts.add(e)
        elif 8 <= e <= 11 or 128 <= e <= 131:
            fail("show_line13: 관전자(%r)는 13번째 줄 대상이 될 수 없습니다 (CreateUnit 실패 트릭 — 원본과 같음). dp.show 를 쓰세요", x)
        elif e == 13:
            current = True
        elif e == 17:
            consts.update(range(8))
        elif 18 <= e <= 21:
            consts.update(players.f_force_members(e - 17))
        else:
            fail("show_line13: 지원하지 않는 대상 %r", x)
    return sorted(consts), vars_, current, others


def _ccmu(p, hold, guard):
    if guard:
        if EUDIf()(p.AtMost(7)):
            f_raise_CCMU(p)
            if hold is not None:
                _do(hold(p))
        EUDEndIf()
        return
    f_raise_CCMU(p)


def _do(acts):
    acts = _parts._flat(acts)
    if not acts:
        return
    if _parts.all_const(acts):
        _chunked(acts)
    else:
        DoActions(acts)


def f_show_line13(target, *parts, hold=None):
    """13번째 줄(화면 아래 오류 줄)에 글을 띄운다 (DisplayPrintEr 대체, S3 7.2).

    - 공유: 대상마다 `f_raise_CCMU(p)`(유닛 한도 초과 오류를 일부러 띄움) + `hold(p)` 액션.
    - 로컬: 이 PC 가 대상이면 0x641598 에 틀 전체(상수 + 0x0D 자리) + NUL 을 쓰고 자리를 채운다(CCMU **뒤에**).
    인자: target(0~7·P1~P8·변수·CurrentPlayer·Force1~4·AllPlayers·players.Humans 등·목록 — 관전자·LOCAL 불가),
          parts(원소 — 틀 길이 ≤ 217), hold(None | (유닛, 값) → SetDeaths(p, SetTo, 값, 유닛) | fn(p) -> 액션)
    반환: Shown (addr = 0x641598)
    비용: 공유 = 대상마다 호출 1(f_raise_CCMU 1벌, 실행 약 6) — 변수 대상은 +2(p ≤ 7 검사), players.Targets 는 players.each.
          로컬 = 분기 1 + 틀 쓰기 1 + 원소마다 1~3 (docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: **공유 조건에서만 부른다**(로컬 구역 안이면 빌드 경고 — CCMU·hold 는 공유 동작, S3 7.1-5)
    epScript: `dp.show_line13(gcp, "\\x08골드 부족 ", need);` (→ `f_show_line13`)
    출처: DPL:413 DisplayPrintEr, DPS function.lua:310 Print_13X, eudplib f_raise_CCMU(string/cpprint.py:257)·f_eprintln, G8 1.7
    """
    if _has_local(target):
        fail("show_line13: dp.LOCAL 은 쓸 수 없습니다 (13번째 줄은 대상 플레이어의 CreateUnit 실패로 띄운다) — players.Humans 를 쓰세요")
    if local.f_in_region():
        warn("show_line13: 로컬 구역 안에서 불렀습니다 — CreateUnit 실패 트릭은 공유 동작이라 디싱크가 날 수 있습니다")
    items = _items(parts, "show_line13")
    layout = _Layout(items)
    if layout.size > LINE13_MAX:
        fail("show_line13: 틀 길이 %d바이트가 13번째 줄 한도 %d 를 넘습니다 (0x0D 자리 포함, 원소 %r)",
             layout.size, LINE13_MAX, [k for k, _x in items])  # fmt: skip
    if b"\n" in layout.content:
        warn("show_line13: 줄바꿈(\\n)은 13번째 줄에서 뜻이 없습니다")
    hold = _hold_fn(hold)
    consts, vars_, current, others = _ccmu_plan(target)
    # 공유: CreateUnit 실패 트릭
    if current:
        f_raise_CCMU(CurrentPlayer)
        if hold is not None:
            _do(hold(CurrentPlayer))
    hold_acts = []
    for p in consts:
        f_raise_CCMU(p)
        if hold is not None:
            hold_acts.extend(_parts._flat(hold(p)))
    _do(hold_acts)
    for v in vars_:
        _ccmu(v, hold, guard=True)
    if others:
        try:
            each = players.f_each(players.Targets(*others))
            p = each.__enter__()
        except EudextError as e:
            fail("show_line13: %s", e)
        f_raise_CCMU(p)
        if hold is not None:
            _do(hold(p))
        each.__exit__(None, None, None)
    # 로컬: 13번째 줄 쓰기
    addr, epd = LINE13_ADDR, EPD(LINE13_ADDR)
    data = layout.content + b"\0"
    data += b"\0" * (-len(data) % 4)
    skip = layout.direct_words()
    acts = []
    for i in range(0, len(data), 4):
        w = i // 4
        if w in skip:
            continue
        val = int.from_bytes(data[i : i + 4], "little")
        if i + 4 > LINE_BYTES:  # 줄 버퍼(218) 밖 바이트는 건드리지 않는다
            acts.append(SetMemoryX(addr + i, SetTo, val, (1 << (8 * (LINE_BYTES - i))) - 1))
        else:
            acts.append(SetMemory(addr + i, SetTo, val))
    acts += layout.prep_actions(addr, epd)
    # 관전자 PC 는 CCMU 가 뜨지 않으므로 쓰지 않는다 (변수 대상 값이 128~131 인 경우)
    cond = _parts._flat(players.f_contains_user(target)) + [unProxy(f_getuserplayerid()).AtMost(7)]
    EUDIf()(cond)
    with local.f_allow():
        _chunked(acts)
        layout.emit(addr, epd)
    EUDEndIf()
    return Shown(None, addr, layout)


show_line13 = f_show_line13


# =============================================================================================
# set_tbl
# =============================================================================================


def _tbl_id(tbl_id):
    u = unProxy(tbl_id)
    if isinstance(u, bool) or u is None:
        fail("set_tbl: TBL 번호는 1~65535 정수 또는 EUDVariable 입니다 (%r)", tbl_id)
    if isinstance(u, int):
        if not 1 <= u <= 0xFFFF:
            fail("set_tbl: TBL 번호는 1~65535 입니다 (%r)", tbl_id)
        return u
    if _compat.is_var(u) or _compat.is_const(u):
        return u
    fail("set_tbl: TBL 번호는 1~65535 정수 또는 EUDVariable 입니다 (%r)", tbl_id)


def _exact_values(items):
    out = []
    for kind, x in items:
        if kind == "c":
            out.append(x)
        elif isinstance(x, Part):
            out.extend(x._exact())
        else:
            out.append(x.fmt())
    return out


def f_set_tbl(tbl_id, *parts, tail=TBL_TAIL, eos=True, every=None, update_if=None, capacity=None):
    """stat_txt.tbl 문자열(버튼 설명 등)을 바꾼다 (DisplayPrintTbl 대체, S3 7.2). 모든 PC 에서 쓴다.

    원소를 **바이트 그대로 이어서**(0x0D 채움 없음) `GetTBLAddr(tbl_id)` 에 쓰고 tail, NUL(eos) 을 붙인다.
    인자: tbl_id(1~65535 또는 변수), parts(원소), tail(끝에 붙일 문자열 — 기본 U+2009, None = 안 붙임(UTF8OptionOff)),
          (epScript 는 `tail=false`), eos(True = NUL 을 쓴다(D16), False = 원본처럼 안 쓴다), every/update_if(show 와 같음 — 갱신 주기),
          capacity(자리 크기 바이트 — 주면 최대 길이(+NUL)가 넘을 때 빌드 오류)
    반환: int (최대 쓰기 길이, NUL 포함)
    비용: 호출 자리 = [every 1] + [조건 1] + GetTBLAddr 호출 + 원소 서식 + f_dbstr_print(원소마다 1~2).
          실행 = 바이트당 약 35(상수 글자 포함) + 서식 — 자주 부르는 곳은 every/update_if 로 줄인다 (docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전 (TBL 은 표시용 메모리 — LocalName 등 로컬 값을 넣어도 된다)
    epScript: `dp.set_tbl(92, "\\x08자동사냥 ", nf.Dec(lv), "단계", eos=false);` (→ `f_set_tbl`)
    출처: DPL:32 DisplayPrintTbl, eudplib GetTBLAddr·f_settbl(string/tblprint.py), G8 1.8
    """
    tid = _tbl_id(tbl_id)
    eos = _flag("eos", eos)
    if tail is False or (isinstance(tail, int) and not isinstance(tail, bool) and tail == 0):
        tail = None  # epScript 에서는 None 대신 false
    if tail is not None and not isinstance(tail, (str, bytes, bytearray)):
        fail("set_tbl: tail 은 문자열 또는 None 입니다 (%r)", tail)
    items = _items(list(parts) + ([tail] if tail else []), "set_tbl")
    total = sum(len(x) if k == "c" else x.max_len for k, x in items) + (1 if eos else 0)
    if capacity is not None:
        cap = unProxy(capacity)
        if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
            fail("set_tbl: capacity 는 1 이상 정수입니다 (%r)", capacity)
        if total > cap:
            fail("set_tbl: 최대 %d바이트(NUL 포함)가 자리 크기 %d 를 넘습니다", total, cap)
    gate = _Gate(_every(every), _update_conds(update_if))
    gate.tick()

    def body():
        values = _exact_values(items)
        ptr = GetTBLAddr(tid)
        if values:
            f_dbstr_print(ptr, *values, EOS=eos)
        elif eos:
            f_dbstr_print(ptr, b"")

    gate.run([], body)
    return total


set_tbl = f_set_tbl


# =============================================================================================
# Template (DisplaySTRX)
# =============================================================================================


class Template:
    """다른 액션에 넣을 동적 문자열 (DisplaySTRX 대체): `SetMissionObjectives(t.string)`, `DisplayText(t.string)` 등.

    틀 문자열(상수는 굽고 실행 원소는 0x0D 자리)은 처음 쓸 때(`t.string`·`t.addr`·`t.update()`) 맵 문자열 표에 넣는다(트리거 0 —
    epScript 전역 const 로 만들어도 된다). `t.update()` 가 그 자리에서
    자리를 다시 쓴다(**모든 PC** — 로컬 분기 없음). every/update_if 를 주면 update() 호출 자리에서 알아서 거른다
    (update() 는 한 곳에서 매 프레임 부르는 것을 가정한다).
    인자: parts(원소), every(N 번째 update() 마다 갱신), update_if(조건 — update() 마다 복사해 쓴다, 또는 fn() -> 조건)
    반환: Template 객체
    속성: string / string_id(문자열 번호 — 액션의 글 자리에 넣는다), addr(버퍼 주소 식), content(틀), size(틀 길이)
    비용: 만들 때 0. update() = [every 1] + [조건 1] + 지우기 1 + 원소마다 1~3 (docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전(버퍼는 표시용 — 로컬 값을 넣으면 PC 마다 다른 글)
    epScript: `const t = dp.Template("남은 적 ", n);` … `t.update(); DoActions(SetMissionObjectives(t.string));`
    출처: DPL:1305 DisplaySTRX, S3 5.8·7.2 (Seed MissionObjective.lua:93, Stel System.lua:2123)
    """

    def __init__(self, *parts, every=None, update_if=None):
        items = _items(parts, "Template")
        self._layout = _Layout(items)
        self._sid = None
        self._tok = None
        self._addr = None
        self._every = _every(every)
        self._update_if = update_if
        _update_conds(update_if)  # 형식 검사
        self._counter = EUDLightVariable() if self._every is not None else None

    def _ensure(self):
        # 문자열은 처음 쓸 때(맵을 불러온 뒤) 넣는다. 한 프로세스에서 맵을 다시 불러오면 새 번호로 다시 넣는다
        tok = _compat.string_map_token()
        if tok is None:
            fail("Template: 맵을 불러온 뒤(LoadMap)에 문자열을 쓸 수 있습니다")
        if self._sid is None or self._tok is not tok:
            self._sid = _new_string(self._layout.content)
            self._tok = tok
            self._addr = GetMapStringAddr(self._sid)

    def __repr__(self):
        return "<dp.Template string=%r size=%d>" % (self._sid, self._layout.size)

    @property
    def string(self):
        """문자열 번호 (액션의 글 자리에 넣는다)."""
        self._ensure()
        return self._sid

    @property
    def string_id(self):
        self._ensure()
        return self._sid

    @property
    def addr(self):
        """버퍼 주소 식 (strcmp·f_dbstr_print 등에 넘긴다)."""
        self._ensure()
        return self._addr

    @property
    def content(self):
        return self._layout.content

    @property
    def size(self):
        return self._layout.size

    @property
    def slots(self):
        return self._layout.describe()

    def update(self):
        """이 자리에서 실행 원소 자리를 다시 쓴다 (모든 PC).

        인자: 없음
        반환: None
        비용: 클래스 설명
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `t.update();`
        출처: DPL:1305 DisplaySTRX 의 ResetTimer 블록
        """
        if not self._layout.dynamic:
            return
        addr = self.addr
        epd = EPD(addr)
        gate = _Gate(self._every, _update_conds(self._update_if, fresh=True), counter=self._counter)
        gate.tick()
        lay = self._layout
        with local.f_allow():
            gate.run(lay.clear_actions(addr, epd) + lay.prep_actions(addr, epd), lambda: lay.emit(addr, epd))
