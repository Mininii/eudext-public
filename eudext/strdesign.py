"""컴파일 시점 색 문자열 꾸미기 — CtrigAsm 맵들의 `StrDesign`/`StrDesignX`/`StrD` 대체 (DESIGN 4.7, 정본 명세 S7).

트리거를 만들지 않는 **순수 파이썬 함수**다. 입력 문자열 앞뒤에 맵마다 정한 장식(색 코드 + 기호)을 붙일 뿐이고,
결과의 UTF-8 바이트는 원본 Lua 함수의 결과와 **바이트까지 같다**(S7 5절 기대값 156건 + lupa 차등 시험).

    from eudext import strdesign as sd
    sd.set_style("seed")                                   # 맵 설정 맨 앞에서 한 번 (theSeed·Stella_II·MSF-Template)
    DoActions(DisplayText(sd.design("\\x04[\\x1f보스\\x04] 등장"), 4))   # StrDesign
    DoActions(DisplayText(sd.design_x("가운데 줄")))         # StrDesignX (앞에 \\x13 = 가운데 정렬)
    pre, post = sd.parts()                                 # StrD[1], StrD[2]
    items = sd.wrap(hero_name, "\\x04을(를) 처치! ", pts, center=True)   # [머리, *원소, 꼬리] — display 원소 목록용

    import eudext.strdesign as sd;           // epScript (모듈 함수는 f_ 로 번역된다: sd.design → sd.f_design)
    const style = sd.set_style("seed");      // 전역에서 부를 때는 const 에 받는다
    const title = sd.design("보스 등장");     // 전역 문자열 상수도 된다 (eudplib 0.81)
    function show() {
        printAll(title);
        DisplayText(sd.design_x("가운데", style="memory", lead=false));
    }

## 규칙 (S7 3절)

판 `P = (lead, pre, post)` 에 대해

    design(s)                      = lead + pre + s + post              (StrDesign)
    design(s, center=True)         = lead + "\\x13" + pre + s + post     (StrDesignX)
    design(s, center=True, lead=False) =    "\\x13" + pre + s + post     (memory 판 StrDesignX2)
    parts()                        = (pre, post)                        (StrD — 원본은 seed/respect 판에만 있었다)

- 바이트를 그대로 이어 붙인다. 이스케이프·정규화·길이 검사가 없다. 입력의 `\\x00`·`\\n`·색 코드·`\\x13` 도 그대로 남는다.
  `\\n` 이 있으면 장식은 첫 줄 앞과 마지막 줄 뒤에만 붙는다(원본과 같음). `\\x00` 이 있으면 화면에서 거기서 끊기므로 경고한다.
- 앞 공백 1개·뒤 공백 1개는 장식의 일부다(빈 문자열 → 공백 두 개).
- `right=True` 는 `\\x13` 대신 `\\x12`(오른쪽 정렬)를 넣는다. 원본 함수에는 없고, Stella_II 가 `"\\x12"..StrD[1]` 로 직접
  쓰던 모양(`MapLogic/System.lua:1539`)을 위해 둔다.

## 판 (S7 1절) — `STYLES`

| 이름 | 쓰는 맵 | 앞(pre) | 뒤(post) | lead |
|---|---|---|---|---|
| `mcf` | DPS강화하기, MSF_UE_RE, MSF_Breeze, MSF_GaLaXy.2_R, MSF_Memory (Library 판) | `\\x07『 ` | ` \\x07』` | 없음 |
| `seed` | theSeed, Stella_II, MSF-Template | `\\x08。\\x18˙\\x0F+\\x1C˚ ` | ` \\x1C。\\x0F+\\x18.\\x08˚` | 없음 |
| `respect` | MSF_Respect_V | `\\x07。\\x18˙\\x0F+\\x1C˚ ` | ` \\x1C。\\x0F+\\x18.\\x07˚` | 없음 |
| `memory` | MSF_Memory_2 | `\\x07·\\x11·\\x08·\\x07【 ` | ` \\x07】\\x08·\\x11·\\x07·` | `\\r\\r` |

원본은 "Library 판을 먼저 불러오고 맵 판이 전역 함수를 덮어쓰는" 구조라, 맵 판 파일보다 앞에서 실행된 호출은 조용히
`mcf` 장식을 받을 수 있었다(S7 2절). eudext 는 기본 판이 없다 — **`set_style()` 을 부르기 전에 판 없이 `design()` 을 부르면
오류**다. 판을 정하지 않은 호출이 나온 뒤 `set_style()` 로 판을 바꾸면 경고한다.

## 숫자 (S7 3-2, 6절)

`design()` 은 `str`(또는 `bytes`)만 받는다. 파이썬 `str(1/3)` 은 `0.3333333333333333` 인데 Lua 는 `0.33333333333333`
이라 조용히 어긋나기 때문이다. 원본의 `(k[3]/1000).." %"` 를 옮길 때는 `sd.lua_tostring(k3 / 1000) + " %"` 를 쓴다
(Lua 5.4 규칙: 정수 → 10진, 실수 → `%.14g` 뒤 정수 모양이면 `.0` — `100.0`, `1e+15`, `-0.0`).
CtrigAsm 이름 별칭(`StrDesign`, `StrDesignX`, `StrDesignX2`)은 원래 의미대로 숫자를 `lua_tostring` 으로 바꿔 받는다.

## 함정 (S7 7절)

- **판이 맵마다 다르다.** 공용 코드는 판을 가정하지 말고 `design()` 에 맡긴다.
- `memory` 판 결과는 `\\r\\r`(0D 0D)로 시작한다. 채팅 효과 표식 `"\\r\\r!H"`(S6)와 앞 두 바이트가 같으니 4바이트 전체를
  비교한다. 표식이 필요한 줄은 원본처럼 `"\\r\\r!H" + sd.design_x(…, lead=False)` 로 쓴다.
- 장식이 +10~+33 바이트를 더한다(`mcf` +10, `seed`/`respect` +25, `memory` +32 / X +33 / X2 +29). 13번째 줄(218B)·
  TBL·`DisplayPrintEr`(210B)에 넣을 때 넘치기 쉽다.
- 실수 표기: `f"{x/1000} %"` 는 대부분 원본과 같지만 `:g` 서식을 쓰면 `100.0` 이 `100` 이 된다.
- 한 프로세스에서 여러 맵을 빌드하면 판은 빌드 사이에 그대로 남는다(맵마다 `set_style()` 을 다시 부른다).

출처: `MapSource/Library/LibraryFor322.lua:66~74`(mcf), `theSeed/Engine/func.lua:17~30`·`Stella_II/Engine/func.lua:11~24`·
`MSF-Template/func.lua:11~24`(seed), `MSF_Respect_V/func.lua:7~20`(respect), `MSF_Memory_2/func.lua:4~15`(memory);
규칙·기대값 `docs/spec/S7_strdesign.md`; Lua 5.4 `lobject.c` `tostringbuff`(실수 표기). DPS 이식판(e7efff2)에는 같은 코드가 없다.
"""

import math
import types

from eudext import errors as _er

__all__ = [
    "CENTER",
    "MAP_STYLES",
    "RIGHT",
    "STYLES",
    "Style",
    "StrDesign",
    "StrDesignX",
    "StrDesignX2",
    "design",
    "design_x",
    "f_design",
    "f_design_x",
    "f_get_style",
    "f_lua_tostring",
    "f_parts",
    "f_set_style",
    "f_wrap",
    "get_style",
    "lua_tostring",
    "parts",
    "set_style",
    "wrap",
]

CENTER = "\x13"  # SC 가운데 정렬 코드
RIGHT = "\x12"  # SC 오른쪽 정렬 코드

_LUA_INT_MIN = -(1 << 63)
_LUA_INT_MAX = (1 << 63) - 1


class Style:
    """StrDesign 판 하나(불변 값 객체): 앞 장식 `pre`, 뒤 장식 `post`, 줄 머리 `lead`.

    인자: pre(str), post(str), lead(str, 기본 ""), name(str, 선택 — 표시·메시지용. 같음 비교에는 쓰지 않는다)
          bytes 를 주면 UTF-8 로 읽는다.
    반환: Style. 속성 `pre`·`post`·`lead`·`name`, 메서드 `parts()`·`design(…)`(모듈 `design` 과 같은 규칙)
    비용: 0 (컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음(문자열 상수)
    epScript: `const mine = sd.Style("\\x04< ", " \\x04>");` → `sd.set_style(mine)` (대문자라 이름 번역이 없다)
    출처: S7 1절 표(판 4개), 6절 `sd.Style`
    """

    __slots__ = ("_lead", "_name", "_post", "_pre")

    def __init__(self, pre, post, lead="", name=None):
        object.__setattr__(self, "_pre", _style_text("pre", pre))
        object.__setattr__(self, "_post", _style_text("post", post))
        object.__setattr__(self, "_lead", _style_text("lead", lead))
        if name is not None and not isinstance(name, str):
            _er.fail("Style: name 은 문자열이어야 합니다 (받은 값 %r)", name)
        object.__setattr__(self, "_name", name)

    def __setattr__(self, key, value):
        _er.fail("Style 은 바꿀 수 없습니다 (%s). 새 Style(...) 을 만드세요", key)

    def __delattr__(self, key):
        _er.fail("Style 은 바꿀 수 없습니다 (%s)", key)

    @property
    def pre(self):
        """앞 장식(원본 `StrD[1]`)."""
        return self._pre

    @property
    def post(self):
        """뒤 장식(원본 `StrD[2]`)."""
        return self._post

    @property
    def lead(self):
        """줄 머리(정렬 코드보다 앞). `memory` 판만 `"\\r\\r"`."""
        return self._lead

    @property
    def name(self):
        """판 이름(`STYLES` 의 키) 또는 None."""
        return self._name

    def parts(self):
        """`(pre, post)` — 모듈 함수 `parts(style)` 와 같다."""
        return (self._pre, self._post)

    def design(self, text, center=False, lead=True, right=False):
        """이 판으로 꾸민다 — 모듈 함수 `design(text, style=self, …)` 와 같다."""
        return _design(self, text, center, lead, right, "Style.design")

    def _key(self):
        return (self._pre, self._post, self._lead)

    def __eq__(self, other):
        if not isinstance(other, Style):
            return NotImplemented
        return self._key() == other._key()

    def __ne__(self, other):
        if not isinstance(other, Style):
            return NotImplemented
        return self._key() != other._key()

    def __hash__(self):
        return hash(self._key())

    def __repr__(self):
        head = "Style(%r, %r" % (self._pre, self._post)
        if self._lead:
            head += ", lead=%r" % self._lead
        if self._name is not None:
            head += ", name=%r" % self._name
        return head + ")"

    def __reduce__(self):
        return (Style, (self._pre, self._post, self._lead, self._name))


def _style_text(what, s):
    if isinstance(s, (bytes, bytearray)):
        try:
            return bytes(s).decode("utf-8")
        except UnicodeDecodeError:
            _er.fail("Style: %s 가 UTF-8 이 아닙니다 (%r)", what, s)
    if not isinstance(s, str):
        _er.fail("Style: %s 는 문자열이어야 합니다 (받은 값 %r)", what, s)
    return s


# 원본 Lua 문자열 그대로 (글자: 『 U+300E, 』 U+300F, 。 U+3002, ˙ U+02D9, ˚ U+02DA, · U+00B7, 【 U+3010, 】 U+3011)
STYLES = types.MappingProxyType(
    {
        # LibraryFor322.lua:66~74
        "mcf": Style("\x07『 ", " \x07』", name="mcf"),
        # theSeed/Engine/func.lua:17~30 = Stella_II/Engine/func.lua:11~24 = MSF-Template/func.lua:11~24
        "seed": Style("\x08。\x18˙\x0f+\x1c˚ ", " \x1c。\x0f+\x18.\x08˚", name="seed"),
        # MSF_Respect_V/func.lua:7~20
        "respect": Style("\x07。\x18˙\x0f+\x1c˚ ", " \x1c。\x0f+\x18.\x07˚", name="respect"),
        # MSF_Memory_2/func.lua:4~15
        "memory": Style("\x07·\x11·\x08·\x07【 ", " \x07】\x08·\x11·\x07·", lead="\r\r",
                        name="memory"),
    }
)  # 판 이름 → Style (S7 1절). 읽기 전용 — 새 판은 sd.Style(...) 을 set_style/style= 에 직접 넣는다.

# 맵 → 판 (S7 2절 표, 참고용). 새 맵은 이 표를 보고 set_style() 에 판 이름을 넣는다.
MAP_STYLES = types.MappingProxyType(
    {
        "DPS_Enhance": "mcf",
        "MSF_UE_RE": "mcf",
        "MSF_Breeze": "mcf",
        "MSF_GaLaXy.2_R": "mcf",
        "MSF_Memory": "mcf",
        "theSeed": "seed",
        "Stella_II": "seed",
        "MSF-Template": "seed",
        "MSF_Respect_V": "respect",
        "MSF_Memory_2": "memory",
    }
)

_current = None  # set_style 로 정한 판
_implicit_used = False  # 판을 지정하지 않은 design() 이 불렸는가 (판을 나중에 바꾸면 경고)


def _resolve(style, where):
    if style is None:
        if _current is None:
            _er.fail(
                "%s: 판이 정해지지 않았습니다. 맵 설정 맨 앞에서 sd.set_style(\"mcf\"|\"seed\"|\"respect\"|\"memory\") 를 "
                "부르거나 style= 를 주세요 (S7 7-1)",
                where,
            )
        return _current
    if isinstance(style, Style):
        return style
    if isinstance(style, str):
        st = STYLES.get(style)
        if st is None:
            _er.fail("%s: 모르는 판 %r (가능: %s, 또는 sd.Style(...))", where, style, ", ".join(STYLES))
        return st
    _er.fail("%s: style 은 판 이름(str) 또는 sd.Style 이어야 합니다 (받은 값 %r)", where, style)


def _flag(where, name, v):
    if isinstance(v, bool):
        return v
    if isinstance(v, int) and v in (0, 1):
        return bool(v)
    _er.fail("%s: %s 는 True/False 상수여야 합니다 (받은 값 %r)", where, name, v)


def _text(where, text):
    if isinstance(text, str):
        nul = "\x00" in text
    elif isinstance(text, (bytes, bytearray)):
        text = bytes(text)
        nul = b"\x00" in text
    elif text is None or isinstance(text, bool):
        _er.fail("%s: 문자열이 아닌 값 %r (원본 Lua 도 'attempt to concatenate' 오류)", where, text)
    elif isinstance(text, (int, float)):
        _er.fail(
            "%s: 숫자 %r 는 받지 않습니다. 숫자는 f-문자열로 바꾸거나 sd.lua_tostring(x) 를 쓰세요 "
            "(원본과 같은 표기: 정수 10진, 실수 %%.14g + '.0')",
            where,
            text,
        )
    else:
        _er.fail(
            "%s: 컴파일 시점 문자열(str·bytes)만 받습니다 (받은 값 %r). 실행 중 값은 display 원소 목록에 "
            "sd.wrap(...) 이나 sd.parts() 로 끼우세요",
            where,
            text,
        )
    if nul:
        _er.warn("%s: 입력에 \\x00 이 있습니다 — 화면에서는 거기서 끊겨 뒤 장식까지 보이지 않습니다 (S7 7-6): %r", where, text)
    return text


def _head(st, center, lead, right, where):
    center = _flag(where, "center", center)
    lead = _flag(where, "lead", lead)
    right = _flag(where, "right", right)
    if center and right:
        _er.fail("%s: center 와 right 를 함께 켤 수 없습니다", where)
    return (st.lead if lead else "") + (CENTER if center else "") + (RIGHT if right else "") + st.pre


def _design(st, text, center, lead, right, where):
    text = _text(where, text)
    head = _head(st, center, lead, right, where)
    if isinstance(text, bytes):
        return head.encode("utf-8") + text + st.post.encode("utf-8")
    return head + text + st.post


def _pick(style, where):
    global _implicit_used
    st = _resolve(style, where)
    if style is None:
        _implicit_used = True
    return st


def f_set_style(style):
    """이 맵의 StrDesign 판을 정한다. **맵 설정 맨 앞에서 한 번** 부른다.

    인자: style — 판 이름(`"mcf"`, `"seed"`, `"respect"`, `"memory"` — `STYLES`) 또는 `sd.Style(...)`.
          None 은 판을 지운다(시험용 — 그 뒤 판 없는 `design()` 은 다시 오류).
    반환: 정한 Style(None 이면 None). 판을 정하지 않은 `design()` 이 이미 불린 뒤 다른 판으로 바꾸면 경고(`EPWarning`) —
          원본의 "맵 판이 나중에 덮어써서 앞 호출만 Library 판을 받는" 사고를 알린다(S7 2절).
    비용: 0 (컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `const style = sd.set_style("seed");` (전역 문장은 선언만 되므로 const 에 받는다)
    출처: S7 6절 `sd.set_style` (원본에는 없음 — 전역 함수 덮어쓰기 구조를 대신한다)
    """
    global _current, _implicit_used
    if style is None:
        _current = None
        _implicit_used = False
        return None
    st = _resolve(style, "set_style")
    if _current is not None and st != _current and _implicit_used:
        _er.warn(
            "strdesign: 판을 %r 에서 %r 로 바꿉니다. 그 전에 판을 지정하지 않고 만든 문자열은 옛 판 장식입니다 "
            "(set_style 은 맵 설정 맨 앞에서 한 번 — S7 2절)",
            _current.name or _current,
            st.name or st,
        )
    _current = st
    return st


def f_get_style():
    """지금 정한 판(Style) 또는 None.

    인자: 없음
    반환: Style | None
    비용: 0 (컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `const st = sd.get_style();`
    출처: 새로 작성
    """
    return _current


def f_design(text, style=None, center=False, lead=True, right=False):
    """문자열을 판의 장식으로 꾸민다: `lead + ["\\x13"] + pre + text + post` (StrDesign / StrDesignX / StrDesignX2).

    인자: text — 컴파일 시점 문자열(`str`, 또는 `bytes` → 결과도 `bytes`). 숫자·None·런타임 값은 오류
                 (숫자는 `sd.lua_tostring(x)`). `\\x00` 이 있으면 경고.
          style — None(= `set_style` 로 정한 판, 정하지 않았으면 오류) | 판 이름 | `sd.Style`
          center — True 면 pre 앞에 `\\x13`(가운데 정렬, StrDesignX). right — True 면 `\\x12`(오른쪽 정렬). 둘 다는 오류.
          lead — False 면 판의 줄 머리(`memory` 판의 `\\r\\r`)를 뺀다(`memory` 판 StrDesignX2).
    반환: str(또는 bytes). UTF-8 바이트가 원본 Lua 결과와 같다(S7 5절).
    비용: 0 — 트리거를 만들지 않는다(순수 파이썬, 시험으로 확인)
    CP: 바꾸지 않음
    로컬: 해당 없음(문자열 상수). 결과를 `DisplayText` 등에 넣는 쪽의 규칙을 따른다
    epScript: `DisplayText(sd.design("보스 등장"));`, `const s = sd.design("x", style="mcf", center=true);`
    출처: StrDesign/StrDesignX(LibraryFor322.lua:66·71, theSeed/Engine/func.lua:22·27, MSF_Respect_V/func.lua:12·17,
          MSF_Memory_2/func.lua:4·10·13), S7 3절 규칙
    """
    return _design(_pick(style, "design"), text, center, lead, right, "design")


def f_design_x(text, style=None, lead=True):
    """가운데 정렬 판 — `design(text, style=style, center=True, lead=lead)` (StrDesignX).

    인자: text, style, lead — `design` 과 같다. `lead=False` 는 `memory` 판 StrDesignX2.
    반환: str(또는 bytes)
    비용: 0 (컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `DisplayText(sd.design_x("\\x1DExtra Boss\\x04 등장"));`
    출처: StrDesignX(LibraryFor322.lua:71 등), StrDesignX2(MSF_Memory_2/func.lua:13)
    """
    return _design(_pick(style, "design_x"), text, True, lead, False, "design_x")


def f_parts(style=None):
    """판의 `(pre, post)` — 원본 `StrD = {StrD[1], StrD[2]}` 대체.

    가운데에 실행 중 값을 끼울 때 쓴다(원본 `{"\\x13"..StrD[1], PName(i), "…"..StrD[2]}`). 원본에는 seed/respect 판에만
    있었지만 모든 판에서 돌려준다. `lead`·정렬 코드는 들어 있지 않다(필요하면 `wrap`).

    인자: style — `design` 과 같다
    반환: (pre: str, post: str)
    비용: 0 (컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `const pp = sd.parts();` → `pp[0]`, `pp[1]` (파이썬 튜플)
    출처: StrD(theSeed/Engine/func.lua:17, Stella_II/Engine/func.lua:11, MSF_Respect_V/func.lua:7)
    """
    return _pick(style, "parts").parts()


def f_wrap(*items, style=None, center=False, lead=True, right=False):
    """display 원소 목록용: `[머리, *items, 꼬리]` — 머리 = lead + [정렬] + pre, 꼬리 = post.

    이어 붙이면 `design("".join(items), …)` 와 같은 바이트다. items 는 그대로 넣는다(실행 중 값·display 원소 가능 —
    검사는 받는 쪽이 한다). `\\x13`·lead 는 머리 문자열에 합쳐 원소 수를 줄인다.

    인자: items — 가운데 원소들. style/center/lead/right — `design` 과 같다
    반환: list (파이썬 목록 — 파이썬에서는 `dp.show(t, *sd.wrap(…))` 로 펼친다)
    비용: 0 (컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `const items = sd.wrap(name, " 처치!", center=true);` (epScript 에는 펼치기가 없다 — 목록을 받는 API 에 넘긴다)
    출처: Stella_II MapLogic/System.lua:1691 `{"\\x13"..StrD[1], HeroTextFunc, …, "…"..StrD[2]}` 모양, S7 6절
    """
    st = _pick(style, "wrap")
    return [_head(st, center, lead, right, "wrap"), *items, st.post]


def f_lua_tostring(x):
    """Lua 5.4 의 `..` 가 값을 문자열로 바꾸는 규칙 그대로(옮기기용).

    정수는 10진(`5` → `"5"`), 실수는 `%.14g` 로 쓰고 정수 모양이면 `.0` 을 붙인다(`100.0` → `"100.0"`,
    `1/3` → `"0.33333333333333"`, `1e15` → `"1e+15"`, `-0.0` → `"-0.0"`). 문자열·bytes 는 그대로.

    인자: x — int(−2⁶³ ~ 2⁶³−1) | float(유한) | str | bytes. bool·None·inf·nan·범위 밖 정수는 오류
    반환: str(bytes 를 주면 bytes)
    비용: 0 (컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `sd.design(sd.lua_tostring(12500 / 1000) + " %")` — epScript 에는 실수가 없어 거의 파이썬에서 쓴다
    출처: Lua 5.4.4 `lobject.c` `tostringbuff`(LUAI_NUMFFORMAT "%.14g"), S7 3-2 (lupa 차등 시험으로 확인)
    """
    if isinstance(x, str):
        return x
    if isinstance(x, (bytes, bytearray)):
        return bytes(x)
    if x is None or isinstance(x, bool):
        _er.fail("lua_tostring: %r 는 Lua 에서도 문자열로 이어 붙일 수 없습니다", x)
    if isinstance(x, int):
        if not _LUA_INT_MIN <= x <= _LUA_INT_MAX:
            _er.fail("lua_tostring: Lua 정수 범위(64비트) 밖 %d", x)
        return str(x)
    if isinstance(x, float):
        if math.isinf(x) or math.isnan(x):
            _er.fail("lua_tostring: %r 는 화면에 찍을 값이 아닙니다(원본 Lua 는 inf/nan 을 찍는다 — 옮길 코드를 확인하세요)", x)
        s = "%.14g" % x
        if all(c in "-0123456789" for c in s):
            s += ".0"
        return s
    _er.fail("lua_tostring: 숫자·문자열이 아닌 값 %r", x)


def _lua_arg(s):
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return f_lua_tostring(s)
    return s


def StrDesign(s, style=None):  # noqa: N802 — CtrigAsm 이름 별칭
    """CtrigAsm `StrDesign(Str)` 별칭 — `design(s)`. 원래 의미대로 숫자는 `lua_tostring` 으로 바꿔 받는다.

    인자: s(str·bytes·int·float), style(선택)
    반환: str(또는 bytes)
    비용: 0 (컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `DisplayText(sd.StrDesign("…"));` (대문자라 이름 번역이 없다)
    출처: LibraryFor322.lua:66 외 맵 판 4개(S7 1절)
    """
    return _design(_pick(style, "StrDesign"), _lua_arg(s), False, True, False, "StrDesign")


def StrDesignX(s, style=None):  # noqa: N802
    """CtrigAsm `StrDesignX(Str)` 별칭 — `design_x(s)`. 숫자는 `lua_tostring` 으로 바꿔 받는다.

    인자: s, style — `StrDesign` 과 같다
    반환: str(또는 bytes)
    비용: 0 (컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `DisplayText(sd.StrDesignX("…"));`
    출처: LibraryFor322.lua:71 외(S7 1절)
    """
    return _design(_pick(style, "StrDesignX"), _lua_arg(s), True, True, False, "StrDesignX")


def StrDesignX2(s, style=None):  # noqa: N802
    """MSF_Memory_2 `StrDesignX2(Str)` 별칭 — `design_x(s, lead=False)`(줄 머리 없이 가운데 정렬).

    인자: s, style — `StrDesign` 과 같다(원본은 memory 판에만 있었다. 다른 판에서는 `StrDesignX` 와 같다)
    반환: str(또는 bytes)
    비용: 0 (컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `DisplayText("\\r\\r!H" + sd.StrDesignX2("…"));`
    출처: MSF_Memory_2/func.lua:13
    """
    return _design(_pick(style, "StrDesignX2"), _lua_arg(s), True, False, False, "StrDesignX2")


# 파이썬 별칭 (DESIGN 3.1 — epScript 는 f_ 이름으로 번역된다)
set_style = f_set_style
get_style = f_get_style
design = f_design
design_x = f_design_x
parts = f_parts
wrap = f_wrap
lua_tostring = f_lua_tostring
