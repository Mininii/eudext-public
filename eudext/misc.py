"""misc — 기타 소기능: 관전자 채팅, 방장, 부대 지정, 카운트다운, 와이드 판정, 나가면 멈춤 (DESIGN 4.19).

관전자 채팅(`ObserverChat`)이 이 모듈의 핵심이다(4맵 복붙 블록 대체, 정본 명세 `docs/spec/S6_chat.md` 2절·4.3).
나머지는 사용 0~2회라 원리가 문서로 확실한 것만 작게 두었다(방장 번호, 카운트다운, 부대 지정 주소, 와이드 판정).
`unsafe_exit_trap` 은 **실험(위험) 기능**이다 — 기본으로 막혀 있고 인게임 검증 전까지 쓰지 않는다(DESIGN 7절 D10).

    from eudext import misc, chat, local

    obs = misc.ObserverChat()                 # END=관전자·HOME=전체·INSERT=대상없음 (원본 기본, 딜레이 버그 고침)
    def afterTriggerExec():
        obs.tick()                            # 매 프레임 한 번 (안에서 로컬 분기)
        local.update()                        # 엣지 캐시 (edge=True 이거나 delay=0 일 때 필요)

epScript:

    import eudext.misc as misc;
    const obs = misc.ObserverChat();
    function afterTriggerExec() { obs.tick(); }

## 관전자 채팅 (S6 2·4.3)

관전자(로컬 번호 128~131) PC 에서만, 채팅창이 닫혀 있을 때 END/HOME/INSERT 로 채팅 대상 모드를
관전자(5)/전체(2)/대상없음(3)으로 정하고, 채팅창이 열린 매 프레임 `0x68C144` 를 그 값으로 덮는다. **모두 로컬.**
원본 버그(B1, S6 2.7): 딜레이 감소 트리거가 Ob1(128) 조건으로만 만들어져 Ob2~Ob4 는 첫 입력 뒤 키가 영구히 막혔다.
eudext 는 상태를 라이브러리 전용 변수에 두고 관전자 구역 안에서 줄여 **모든 슬롯에서** 두 번째 입력이 먹힌다.

넣지 않은 것: `ObserverChatToPlayer`(개별 대상 — `0x57F1D8` 공유성 미확인, mode="player" 자리만 예약),
음소거(`TogglePlayerModerate` — 공유성 미확인), `ObserverDrop`(의도적 디싱크, DESIGN D10 제외).

출처: 원본 `reference/MapSource/Library/ObserverChat.lua`(1,066줄)·`ObserverChatAlways.lua`(52줄),
공통 블록 4맵(S6 2.4: Stella_II/MapLogic/System.lua:2883, MSF_Respect_V/Interface.lua:2838, MSF_Memory_2/Interface.lua:989,
MSF_Breeze/Interface.lua:1164), 상시판 theSeed/MapLogic/ObserverChat.lua:14, eudplib 0.81 `eudlib/utilf/userpl.py`(DisplayTextAll·IsUserCP).
DPS_Enhance eudplib-port(a7aad90)에는 대응 코드가 없다.
"""

from eudplib import (
    AtLeast,
    AtMost,
    CenterView,
    DoActions,
    DisplayTextAll,
    EncodePlayer,
    EPD,
    EUDElse,
    EUDEndIf,
    EUDElseIf,
    EUDFunc,
    EUDIf,
    EUDLightBool,
    EUDOnStart,
    EUDVariable,
    Exactly,
    Forward,
    Memory,
    MemoryX,
    PlayWAVAll,
    PopTriggerScope,
    PushTriggerScope,
    RawTrigger,
    SetMemory,
    SetTo,
    f_dwepdread_epd,
    f_dwwrite_epd,
    f_getuserplayerid,
    f_memcmp,
    f_setcurpl,
    f_setcurpl2cpcache,
    f_setloc,
)

from eudext import _compat, cmp, local
from eudext.errors import check_choice, fail, warn

__all__ = [
    "Countdown",
    "HOST_NAME_ADDR",
    "HOTKEY_BASE",
    "MODE_VALUES",
    "ObserverChat",
    "PLAYER_NAME_ADDR",
    "HostNameIs",
    "HotkeyUnit",
    "SetHotkeyUnit",
    "alpha_id",
    "f_HostNameIs",
    "f_HotkeyUnit",
    "f_SetHotkeyUnit",
    "f_host_player",
    "f_is_widescreen",
    "f_unsafe_exit_trap",
    "host_player",
    "hotkey_addr",
    "is_widescreen",
    "unsafe_exit_trap",
]

# --- 주소 (R4b D1·D2·D5, S6 2.3) ---------------------------------------------------------
CHAT_TARGET_ADDR = 0x68C144  # 채팅 입력 대상 (0 = 닫힘, ≥1 = 입력 중). 로컬
LOCAL_PLAYER_ADDR = 0x512684  # 로컬 플레이어 번호 (관전자 128~131). 로컬
HOST_NAME_ADDR = 0x6D0F78  # 방장 이름 16바이트
PLAYER_NAME_ADDR = 0x6D0FDC  # 플레이어 이름 표, +0x24·p 마다 16바이트
HOTKEY_BASE = 0x57FE60  # 부대 지정 표: +0x360·p + 0x30·g + 0x4·i (플레이어·그룹·칸)
PTS_ADDR = 0x51A280  # 플레이어별 트리거 목록 표 (12바이트/플레이어, +8 = tstart)

MODE_VALUES = {"ob": 5, "all": 2, "none": 3}
"""관전자 채팅 모드 이름 → `0x68C144` 값 (S6 2.3). "player"(4)는 공유성 미확인이라 넣지 않았다."""

DEFAULT_KEYS = {"END": "ob", "HOME": "all", "INSERT": "none"}
DEFAULT_NOTICE = {
    "ob": "\x1C채팅→관전자\x04에게 메세지를 보냅니다.",
    "all": "\x07채팅→전체\x04에게 메세지를 보냅니다.",
    "none": "\x02채팅→대상없음\x04에게 메세지를 보냅니다.(귓말 명령어 등 전용)",
}
DEFAULT_SLOTS = (128, 129, 130, 131)
DEFAULT_SOUND = "staredit\\wav\\button3.wav"


# =============================================================================================
# 관전자 채팅
# =============================================================================================


def _check_slots(slots):
    if isinstance(slots, int):
        slots = (slots,)
    slots = tuple(slots)
    if not slots:
        fail("ObserverChat: slots 가 비었습니다")
    for s in slots:
        if isinstance(s, bool) or not isinstance(s, int) or not 128 <= s <= 131:
            fail("ObserverChat: slots 는 관전자 번호 128~131 이어야 합니다 (%r)", s)
    return tuple(sorted(set(slots)))


class ObserverChat:
    """관전자 채팅 대상 전환 (원본 `ObserverChatToOb/ToAll/ToNone` 블록 대체, S6 4.3). 원본 딜레이 버그(B1)를 고친다.

    인자:
      keys(누를 키 → 모드 이름 dict, 기본 END=ob·HOME=all·INSERT=none. `always` 와 함께 주면 오류),
      delay(재발동 대기 프레임, 기본 10. 0 이면 엣지 판정만),
      edge(True 면 누르는 순간에만(권장), 기본 False = 원본처럼 누르는 동안 delay 마다 반복),
      notice(모드 이름 → 안내 문구 dict, 기본 S6 4.3. None 이면 문구 없음),
      decorate(True 면 문구를 `strdesign.design()` 으로 꾸민다 — 판이 정해져 있을 때만, 기본 True),
      typewriter(`chat.Typewriter` 를 주면 문구를 `tw.mark()` 로 감싼다 — 원본의 "\\x0D\\x0D!H" 효과. tick 은 맵이 따로 부른다),
      sound(문구와 함께 낼 WAV, 기본 button3.wav. None 이면 없음),
      always(None | "all" — 키 없이 늘 전체 채팅(OBA 판, theSeed). keys 와 함께 주면 오류 — ResV 충돌 방지 B2),
      slots(관전자 번호 튜플, 기본 (128,129,130,131))
    반환: -
    비용: 키 3개 기준 본문 ≈ 12 트리거(1벌) / tick 호출 자리 = 관전자 판정 + 3. 관전자가 아닌 PC 는 판정 1개
          (2026-09-17, docs/COSTS.md "misc (WP19)")
    CP: 바꾸지 않음 (문구를 낼 때 잠깐 옮기고 캐시 값으로 되돌린다)
    로컬: **로컬 전용** — 상태 변수·모든 쓰기가 관전자 PC 에서만 바뀐다. 공유 로직이 읽지 않는다
    epScript: `const obs = misc.ObserverChat(); … obs.tick();`
    출처: S6 4.3, ObserverChat.lua:322~656·897~1063, ObserverChatAlways.lua:20~52
    """

    def __init__(self, keys=None, delay=10, edge=False, notice="default", decorate=True, typewriter=None,
                 sound=DEFAULT_SOUND, always=None, slots=DEFAULT_SLOTS):
        if always is not None:
            always = check_choice("ObserverChat: always", always, ("all",))
            if keys is not None:
                fail("ObserverChat: always 와 keys 는 함께 쓸 수 없습니다 (상시판과 키 모드 충돌 — S6 2.7-B2)")
        self.always = always
        if keys is None:
            keys = {} if always is not None else dict(DEFAULT_KEYS)
        norm = {}
        for kname, mname in keys.items():
            local.f_key_code(kname)  # 잘못된 키 이름이면 여기서 오류
            if mname == "player":
                fail("ObserverChat: mode='player'(ToPlayer) 는 공유성 미확인이라 넣지 않았습니다 (설계만, S6 4.3)")
            if mname not in MODE_VALUES:
                fail("ObserverChat: 모드는 %s 중 하나여야 합니다 (%r)", "/".join(MODE_VALUES), mname)
            norm[kname] = mname
        self.keys = norm
        if isinstance(delay, bool) or not isinstance(delay, int) or delay < 0:
            fail("ObserverChat: delay 는 0 이상 정수여야 합니다 (%r)", delay)
        self.delay = delay
        self.edge = bool(edge)
        self.use_edge = self.edge or delay == 0
        self.notice = dict(DEFAULT_NOTICE) if notice == "default" else (None if notice is None else dict(notice))
        self.decorate = bool(decorate)
        self.typewriter = typewriter
        if sound is not None and not isinstance(sound, (str, bytes)):
            fail("ObserverChat: sound 는 WAV 이름(str) 또는 None 이어야 합니다 (%r)", sound)
        self.sound = sound
        self.slots = _check_slots(slots)
        # 로컬 전용 상태 (공유 로직이 읽지 않는다)
        self.mode = EUDVariable(MODE_VALUES["all"] if always == "all" else 0)
        self.wait = EUDVariable(0)
        self._body = None

    def __repr__(self):
        return "<ObserverChat keys=%r always=%r>" % (list(self.keys), self.always)

    def _mode_values(self):
        if self.always is not None:
            return {MODE_VALUES[self.always]}
        return {MODE_VALUES[m] for m in self.keys.values()}

    def _slot_conds(self):
        """관전자 슬롯 판정 (평범한 조건 — tick 의 바깥 EUDIf 에 놓는다. 로컬 값이지만 자체 완결 기능이라 경고 없음)."""
        s = self.slots
        lo, hi = s[0], s[-1]
        if s == tuple(range(lo, hi + 1)):
            if lo == hi:
                return Memory(LOCAL_PLAYER_ADDR, Exactly, lo)
            return [Memory(LOCAL_PLAYER_ADDR, AtLeast, lo), Memory(LOCAL_PLAYER_ADDR, AtMost, hi)]
        # 이어지지 않는 슬롯 집합: OR 을 깃발로
        flag = EUDLightBool()
        RawTrigger(actions=flag.Clear())
        for p in s:
            RawTrigger(conditions=Memory(LOCAL_PLAYER_ADDR, Exactly, p), actions=flag.Set())
        return flag.IsSet()

    def _decorate_text(self, text):
        if not self.decorate:
            return text
        try:
            import eudext.strdesign as sd
        except Exception:  # noqa: BLE001
            return text
        if sd.f_get_style() is None:  # 판을 안 정했으면 원문 그대로 (문구에 이미 색 코드가 있다)
            return text
        return sd.f_design(text)

    def _notice_text(self, modename):
        if not self.notice or modename not in self.notice:
            return None
        text = self._decorate_text(self.notice[modename])
        if self.typewriter is not None:
            text = self.typewriter.mark(text)
        return text

    def _emit_notice(self, modename):
        text = self._notice_text(modename)
        if text is None and self.sound is None:
            return
        acts = []
        if text is not None:
            acts.append(DisplayTextAll(text))  # CP 를 이 PC(관전자)로 옮겨 표시 — 되돌리지 않는다
        if self.sound is not None:
            acts.append(PlayWAVAll(self.sound))
        DoActions(acts)
        f_setcurpl2cpcache()  # CP 를 캐시 값으로 되돌린다 (원본은 FP 로 되돌렸다 — S6 6-10)

    def _key_conds(self, kname):
        if self.use_edge:
            return list(local.f_key_pressed(kname))  # LocalConditions (엣지 2)
        return [local.f_key_held(kname)]  # 레벨 1

    def _emit_body(self):
        with local.f_allow():
            if self.always is not None:
                # 관전자면 채팅창이 열릴 때 늘 전체(2) — OBA 와 같음 (트리거 1개)
                RawTrigger(conditions=Memory(CHAT_TARGET_ADDR, AtLeast, 1),
                           actions=SetMemory(CHAT_TARGET_ADDR, SetTo, MODE_VALUES["all"]))
                return
            # 1) 딜레이 감소 — 관전자 구역 안이라 모든 슬롯에서 (B1 수정). SubtractNumber 는 0 에서 멈춤
            if self.delay:
                RawTrigger(conditions=self.wait.AtLeast(1), actions=self.wait.SubtractNumber(1))
            # 2) 채팅창이 닫혀 있고 대기 0 이면: 눌린 첫 키의 모드로
            gate = [Memory(CHAT_TARGET_ADDR, Exactly, 0)]
            if self.delay:
                gate.append(self.wait.Exactly(0))
            if EUDIf()(gate):
                first = True
                for kname, mname in self.keys.items():
                    conds = self._key_conds(kname)
                    if first:
                        EUDIf()(conds)
                        first = False
                    else:
                        EUDElseIf()(conds)
                    acts = [self.mode.SetNumber(MODE_VALUES[mname])]
                    if self.delay:
                        acts.append(self.wait.SetNumber(self.delay))
                    DoActions(acts)
                    self._emit_notice(mname)
                if not first:
                    EUDEndIf()
            EUDEndIf()
            # 3) 채팅창이 열려 있으면 정한 모드로 0x68C144 덮기
            for mv in sorted(self._mode_values()):
                RawTrigger(conditions=[Memory(CHAT_TARGET_ADDR, AtLeast, 1), self.mode.Exactly(mv)],
                           actions=SetMemory(CHAT_TARGET_ADDR, SetTo, mv))

    def _get_body(self):
        if self._body is None:
            @EUDFunc
            def observer_chat_body():
                self._emit_body()

            self._body = observer_chat_body
        return self._body

    def tick(self):
        """한 프레임 분량 — 이 PC 가 관전자(slots)이면 처리. 매 프레임 한 번 부른다.

        인자: 없음
        반환: None
        비용: 호출 자리 = 관전자 판정 + 본문 호출 3. 관전자가 아니면 판정 1개
        CP: 바꾸지 않음 (문구는 잠깐 옮기고 되돌린다)
        로컬: **로컬 전용** — 안에서 관전자 분기 (공유 흐름 어디서 불러도 된다)
        epScript: `obs.tick();`
        출처: S6 4.3, ObserverChat 공통 블록(4맵)
        """
        body = self._get_body()
        if EUDIf()(self._slot_conds()):
            body()
        EUDEndIf()

    f_tick = tick


# =============================================================================================
# 방장 번호·이름 (R4b D1)
# =============================================================================================

_host_var = None


def _reset_host():
    global _host_var
    _host_var = None


_compat.register_build_reset(_reset_host)


def f_host_player():
    """방장의 플레이어 번호(0~7)를 담은 변수. 게임 시작 때 한 번 계산한다(관전자 방장이면 0xFFFFFFFF = 미발견).

    방장 이름(0x6D0F78, 16바이트)을 플레이어 이름 표(0x6D0FDC + 0x24·p)와 16바이트씩 비교한다(R4b D1).
    인자: 없음
    반환: EUDVariable (빌드마다 한 개를 같이 쓴다)
    비용: 시작 트리거 = f_memcmp 본문 1벌 + 플레이어마다 호출 2 (1회) / 호출 자리 0 (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: **공유(추측)** — 방 정보라 모든 PC 가 같다고 본다. `0x6D0FDC` 표의 공유성·싱글 동작은 인게임 확인 전(F19-1)
    epScript: `const host = misc.host_player();`
    출처: CtrigAsm `GetHostPlayerID`(v5.5.lua:80111), R4b D1, eudplib `f_memcmp`(memio/mblockio.py:76)
    """
    global _host_var
    if _host_var is None:
        hv = EUDVariable(0xFFFFFFFF)
        _host_var = hv

        def _init():
            found = EUDLightBool()
            for p in range(8):
                r = f_memcmp(HOST_NAME_ADDR, PLAYER_NAME_ADDR + 0x24 * p, 16)
                RawTrigger(conditions=[found.IsCleared(), r.Exactly(0)],
                           actions=[hv.SetNumber(p), found.Set()])

        EUDOnStart(_init)
    return _host_var


host_player = f_host_player


def f_HostNameIs(name):  # noqa: N802 — 조건 이름 (대문자)
    """방장 이름이 name 으로 시작하는가 (`0x6D0F78`, 16바이트까지) — 조건.

    인자: name(str 또는 bytes, ≤ 16바이트)
    반환: Condition 또는 조건 목록(AND). 매 호출 새 객체
    비용: 조건 = ceil(바이트/4) 개 (트리거 0)
    CP: 바꾸지 않음
    로컬: 공유(추측 — host_player 와 같음)
    epScript: `if (misc.HostNameIs("Natori")) { … }` (→ `f_HostNameIs`)
    출처: CtrigAsm `HostName`(v5.5.lua:80055), R4b D1
    """
    if isinstance(name, str):
        name = name.encode("utf-8")
    if not isinstance(name, (bytes, bytearray)):
        fail("HostNameIs: 이름은 str 또는 bytes 여야 합니다 (%r)", name)
    name = bytes(name)
    if len(name) > 16:
        fail("HostNameIs: 이름은 16바이트 이하여야 합니다 (%d바이트)", len(name))
    groups = {}
    for i, b in enumerate(name):
        base = HOST_NAME_ADDR + (i & ~3)
        sh = 8 * (i & 3)
        v, m = groups.get(base, (0, 0))
        groups[base] = (v | (b << sh), m | (0xFF << sh))
    conds = [MemoryX(base, Exactly, v, m) for base, (v, m) in sorted(groups.items())]
    return conds[0] if len(conds) == 1 else conds


HostNameIs = f_HostNameIs


# =============================================================================================
# 부대 지정 (R4b D2) — 공유성 미확인, 로컬로 볼 것 (인게임 확인 항목)
# =============================================================================================


def _hk_check(p, g, i):
    if isinstance(p, bool) or not isinstance(p, int) or not 0 <= p <= 11:
        fail("hotkey: 플레이어는 0~11 이어야 합니다 (%r)", p)
    if isinstance(g, bool) or not isinstance(g, int) or not 0 <= g <= 17:
        fail("hotkey: 그룹은 0~17 이어야 합니다 (가이드북은 0~9, %r)", g)
    if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i <= 11:
        fail("hotkey: 칸은 0~11 이어야 합니다 (%r)", i)


def hotkey_addr(p, g, i):
    """플레이어 p·그룹 g·칸 i 의 부대 지정 주소 `0x57FE60 + 0x360·p + 0x30·g + 0x4·i` (컴파일 시점).

    인자: p(0~11), g(0~17), i(0~11)
    반환: int
    비용: 트리거 0
    CP: 해당 없음
    로컬: 해당 없음 (주소 계산만)
    epScript: `const a = misc.hotkey_addr(0, 0, 0);`
    출처: CtrigAsm `_HotKeyUnit`(v5.5.lua:80827), R4b D2
    """
    _hk_check(p, g, i)
    return HOTKEY_BASE + 0x360 * p + 0x30 * g + 0x4 * i


def alpha_id(unit_id, index):
    """부대 지정 칸에 들어가는 알파 ID `(index+1) | (unit_id << 11)` (컴파일 시점, BW 인덱스 기준).

    인자: unit_id(유닛 종류 번호 0~65535), index(유닛 순번 0~2047)
    반환: int
    비용: 트리거 0
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const a = misc.alpha_id(0, 5);`
    출처: R4b D2 (INT 1.4 `(idx+1) | uid<<11`)
    """
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index <= 2047:
        fail("alpha_id: index 는 0~2047 이어야 합니다 (%r)", index)
    if isinstance(unit_id, bool) or not isinstance(unit_id, int) or not 0 <= unit_id <= 0xFFFF:
        fail("alpha_id: unit_id 는 0~65535 이어야 합니다 (%r)", unit_id)
    return ((index + 1) | (unit_id << 11)) & 0xFFFFFFFF


def f_HotkeyUnit(p, g, i, cmp=Exactly, alpha=0):  # noqa: N802
    """부대 지정 칸(p, g, i)이 alpha 인가 — 조건 (상수 주소).

    인자: p(0~11), g(0~17), i(0~11), cmp(AtLeast/AtMost/Exactly), alpha(알파 ID 상수)
    반환: Condition (Memory). 그룹·칸이 변수면 `Deaths(EPD(base+0x360p+4i), cmp, alpha, g)` 트릭을 직접 쓴다(R4b D2)
    비용: 조건 1
    CP: 바꾸지 않음
    로컬: **미확인** — 공유성 인게임 확인 전(F19-2). 확인 전에는 표시·로컬 판정에만 쓴다
    epScript: `if (misc.HotkeyUnit(0, 0, 0, Exactly, misc.alpha_id(0, 5))) { … }` (→ `f_HotkeyUnit`)
    출처: CtrigAsm `HotkeyUnit`(v5.5.lua:80795), R4b D2
    """
    return Memory(hotkey_addr(p, g, i), cmp, alpha)


HotkeyUnit = f_HotkeyUnit


def f_SetHotkeyUnit(p, g, i, mod=SetTo, alpha=0):  # noqa: N802
    """부대 지정 칸(p, g, i)을 alpha 로 — 액션 (상수 주소).

    인자: p(0~11), g(0~17), i(0~11), mod(SetTo/Add/Subtract), alpha(알파 ID)
    반환: Action (SetMemory)
    비용: 액션 1
    CP: 바꾸지 않음
    로컬: **미확인** — 공유성 인게임 확인 전(F19-2)
    epScript: `DoActions(misc.SetHotkeyUnit(0, 0, 0, SetTo, misc.alpha_id(0, 5)));` (→ `f_SetHotkeyUnit`)
    출처: CtrigAsm `SetHotkeyUnit`(v5.5.lua:80795), R4b D2
    """
    return SetMemory(hotkey_addr(p, g, i), mod, alpha)


SetHotkeyUnit = f_SetHotkeyUnit


# =============================================================================================
# 카운트다운 (Timer/Stage — DESIGN 4.19)
# =============================================================================================


class Countdown:
    """0 에서 멈추는 카운트다운(공유). `tick()` 이 매 프레임 줄이고 `done()` 은 0 인지 본다.

    단계(Stage)는 `EUDSwitch(cd.v)` 로 나눈다(원본 `NormalTurboSet`·스테이지 관용구 — DESIGN 4.19).
    인자: start(초기값, 기본 0 — 정수 또는 EUDVariable)
    반환: -
    비용: `tick` 액션 1(포화) / `done`·`at_least` 조건 1
    CP: 바꾸지 않음
    로컬: 공유 안전 (공유 변수)
    epScript: `const cd = misc.Countdown(240); … cd.tick(); if (cd.done()) { … }`
    출처: DESIGN 4.19, CtrigAsm 스테이지 관용구 (SC Subtract = 포화, S8)
    """

    def __init__(self, start=0):
        if _compat.is_var(start):
            self.v = EUDVariable(0)
            self.v << start
        else:
            if isinstance(start, bool) or not isinstance(start, int) or start < 0:
                fail("Countdown: start 는 0 이상 정수 또는 EUDVariable 이어야 합니다 (%r)", start)
            self.v = EUDVariable(start)

    def __repr__(self):
        return "<Countdown>"

    def tick(self, step=1):
        """값을 step 만큼 줄인다(0 에서 멈춤). 매 프레임 한 번.

        인자: step(1 이상 정수, 기본 1)
        반환: None
        비용: 액션 1 (포화 뺄셈)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `cd.tick();`
        출처: DESIGN 4.19, SC Subtract 포화
        """
        if isinstance(step, bool) or not isinstance(step, int) or step < 1:
            fail("Countdown.tick: step 은 1 이상 정수여야 합니다 (%r)", step)
        DoActions(self.v.SubtractNumber(step))

    f_tick = tick

    def done(self):
        """값이 0 인가 — 조건.

        인자: 없음
        반환: Condition
        비용: 조건 1
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `if (cd.done()) { … }`
        출처: DESIGN 4.19
        """
        return self.v.Exactly(0)

    f_done = done

    def at_least(self, n):
        """남은 값이 n 이상인가 — 조건.

        인자: n(정수)
        반환: Condition
        비용: 조건 1
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `if (cd.at_least(24)) { … }`
        출처: DESIGN 4.19
        """
        return self.v.AtLeast(n)

    f_at_least = at_least

    def set(self, n):
        """남은 값을 n 으로 (재시작).

        인자: n(정수 또는 EUDVariable)
        반환: None
        비용: 대입 트리거
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `cd.set(240);`
        출처: DESIGN 4.19
        """
        self.v << n

    f_set = set

    def add(self, n):
        """남은 값을 n 만큼 늘린다(wrap).

        인자: n(정수 또는 EUDVariable)
        반환: None
        비용: 액션 1
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `cd.add(24);`
        출처: DESIGN 4.19
        """
        DoActions(self.v.AddNumber(n))

    f_add = add


# =============================================================================================
# 와이드 스크린 판정 (R4b D5) — 로컬, 실험
# =============================================================================================

_widescreen_warned = False


def _reset_widescreen():
    global _widescreen_warned
    _widescreen_warned = False


_compat.register_build_reset(_reset_widescreen)


def f_is_widescreen(loc, into=None):
    """이 PC 가 와이드 스크린인가(1) 아닌가(0)를 담은 **로컬 값**. `loc` 는 판정에 쓰는 버릴 로케이션이다.

    원리(R4b D5 FindSDLocal): 화면을 저장 → loc 를 화면 중앙 안쪽 점에 두고 CenterView →
    반폭(loc.x − 새 화면.x)이 320(4:3)이 아니면 와이드 → 저장한 화면으로 되돌린다.
    **실험 기능**: 인게임 검증 전이다(F19-3). 결과는 로컬 값이므로 공유 로직에 그대로 쓰면 디싱크다 —
    동기화하려면 `sync.Bus.value()` 로 보낸다. `loc` 는 이 함수 뒤 판정 위치에 남는다.
    인자: loc(로케이션 이름 또는 1부터 번호 — eudext 로케이션 규칙), into(결과 LocalValue, 선택)
    반환: `local.LocalValue` (1 = 와이드, 0 = 일반)
    비용: 호출 자리 약 20 (화면 읽기 2회 + CenterView 2회)
    CP: 바꾸지 않음 (안에서 이 PC 로 옮기고 되돌린다)
    로컬: **로컬 전용** — CenterView 는 로컬 화면만 움직인다
    epScript: `const w = misc.is_widescreen("SDProbe"); bus.value(w);`
    출처: CtrigAsm `FindSDLocal`(Extra.lua:280), R4b D5, eudplib `f_setloc`/`CenterView`
    """
    global _widescreen_warned
    if not _widescreen_warned:
        warn("misc.is_widescreen 은 실험 기능입니다 (인게임 검증 전, F19-3) — 결과는 로컬 값입니다")
        _widescreen_warned = True
    out = into if into is not None else local.LocalValue()
    with local.f_allow():
        f_setcurpl(f_getuserplayerid())
        sx, sy = local.f_screen_xy()  # 저장 (LocalValue 짝)
        px = sx + 320  # 화면 중앙 안쪽 점 (가장자리를 피한다)
        py = sy + 240
        f_setloc(loc, px, py, px, py)
        DoActions(CenterView(loc))
        nx, ny = local.f_screen_xy()
        # 반폭 = px − nx. 320 이면 일반, 아니면 와이드
        half = px - nx
        halfy = py - ny
        if EUDIf()(cmp.ne(half, 320)):
            out << 1
        if EUDElse()():
            out << 0
        EUDEndIf()
        # 저장한 화면으로 되돌린다: loc 중앙 = 저장 화면 + 반폭 → CenterView 하면 화면.x = 저장 화면.x
        rx = sx + half
        ry = sy + halfy
        f_setloc(loc, rx, ry, rx, ry)
        DoActions(CenterView(loc))
    f_setcurpl2cpcache()
    return out


is_widescreen = f_is_widescreen


# =============================================================================================
# 나가면 멈춤 (ExitDrop / exit_trap) — R4b D4, 최상 위험, 실험 기능 (DESIGN 7절 D10)
# =============================================================================================

_trap_trigger = None
_tstart_epd = {}  # list_owner → EPD(tstart) 변수 (게임 시작 때 한 번)


def _reset_trap():
    global _trap_trigger, _tstart_epd
    _trap_trigger = None
    _tstart_epd = {}


_compat.register_build_reset(_reset_trap)


def _trap():
    global _trap_trigger
    if _trap_trigger is None:
        PushTriggerScope()
        t = Forward()
        t << RawTrigger(nextptr=t)  # 자기 순환 — 정상 실행은 절대 들어가지 않는다 (R4b D4)
        PopTriggerScope()
        _trap_trigger = t
    return _trap_trigger


def _tstart_epd_of(owner):
    if owner not in _tstart_epd:
        ev = EUDVariable()
        _tstart_epd[owner] = ev

        def _init(owner=owner, ev=ev):
            # pts + 12·owner + 8 = 이 목록의 tstart 트리거 주소. 그 EPD 를 얻는다
            _v, epd = f_dwepdread_epd(EPD(PTS_ADDR + 12 * owner + 8))
            ev << epd

        EUDOnStart(_init)
    return _tstart_epd[owner]


def f_unsafe_exit_trap(target, list_owner=7, enable=False):
    """**실험(최상 위험) 기능**: 대상 PC 가 게임을 나가면 스타를 멈추게 한다(ExitDrop 원리, R4b D4).

    원리: 대상 PC 에서만 `list_owner`(절대 나가지 않는 컴퓨터) 목록의 첫 실행 트리거(eudplib `tstart`)의 next 를
    자기 순환 트리거로 바꾼다. 정상 실행은 tstart 가 매 프레임 자기 next 를 되돌려 순환에 들어가지 않고,
    게임을 떠날 때 SC 가 트리거 목록을 따라가다 순환에 걸려 멈춘다(**추측** — 인게임 검증 전).
    **매 프레임(메인 루프 끝) 부른다** — 부르지 않으면 다음 틱에 풀린다. 조건부로 켜려면 자기 EUDIf 로 감싼다.

    기본으로 막혀 있다(`enable=True` 이중 확인 필요). SC 정리 루틴 동작이 추측이라 목록 주인 선택이 틀리면
    **다른 플레이어나 전원이 멈출 수 있다**(D8). 인게임 확인(F19-4) 전까지 실험 기능으로 둔다.
    인자: target(가둘 PC — 0~7 또는 관전자 128~131), list_owner(순환을 심을 목록 주인, 기본 7 = P8 컴퓨터),
          enable(True 여야 켜진다 — 안 주면 빌드 오류)
    반환: None
    비용: 시작 1회(tstart EPD 읽기) + 호출 자리 약 3 (로컬 조건 + 쓰기)
    CP: 바꾸지 않음
    로컬: **로컬 전용** — 이 PC 의 트리거 next 포인터만 바꾼다(게임 액션은 모든 PC 에서 같다)
    epScript: `misc.unsafe_exit_trap(P1, enable=true);` (매 프레임)
    출처: CtrigAsm `ExitDrop`(v5.5.lua:83529), R4b D4, eudplib `inj_finalizer.py`(tstart 크래시 방지 구조)
    """
    if not enable:
        fail("misc.unsafe_exit_trap 은 실험(최상 위험) 기능입니다 — enable=True 로 명시해야 켜집니다. "
             "인게임 검증(F19-4) 전까지 쓰지 마세요 (목록 주인을 잘못 고르면 게임이 멈출 수 있습니다).")
    warn("misc.unsafe_exit_trap: 실험 기능을 켰습니다 (R4b D4, 인게임 검증 전 F19-4). "
         "list_owner 는 절대 나가지 않는 컴퓨터(기본 P8)여야 합니다")
    code = EncodePlayer(target)
    if not (isinstance(code, int) and (0 <= code <= 7 or 128 <= code <= 131)):
        fail("unsafe_exit_trap: target 은 0~7 또는 관전자 128~131 이어야 합니다 (%r)", target)
    ow = EncodePlayer(list_owner)
    if not (isinstance(ow, int) and 0 <= ow <= 7):
        fail("unsafe_exit_trap: list_owner 는 0~7(컴퓨터 P8=7 권장)이어야 합니다 (%r)", list_owner)
    tstart_epd = _tstart_epd_of(ow)
    trap = _trap()
    with local.f_allow():
        if EUDIf()(Memory(LOCAL_PLAYER_ADDR, Exactly, code)):
            f_dwwrite_epd(tstart_epd + 1, trap)  # tstart + 4 = next → 자기 순환 트랩
        EUDEndIf()


unsafe_exit_trap = f_unsafe_exit_trap
