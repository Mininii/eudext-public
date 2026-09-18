"""eudext.pool — 오브젝트 풀 (건물 스택 `Gun_Line`·TStruct 대체). DESIGN 4.11, 정본 명세 docs/spec/S2_pool.md 6절.

레코드 여러 개를 고정 용량 풀에 두고, 매 프레임 **살아 있는 레코드만** 돈다. 원본 건물 스택처럼 방문하면 레코드의
필드를 **레지스터(필드마다 EUDVariable 하나)** 에 한꺼번에 싣고, 본문은 레지스터를 쓰고(필드 조건 = 변수 조건),
방문 끝에 바뀔 수 있는 필드만 되쓴다.

    from eudext.pool import Pool, Field

    guns = Pool("Gun", "unit! x! y! owner timer phase done gunid", capacity=36,
                aliases={0: "unit", 1: "x", 2: "y", 4: "owner", 7: "timer"})
    h = guns.alloc(unit=u, x=x, y=y, gunid=3)       # 핸들, 0 = 넘침 (guns.dropped += 1)
    for g in guns.each():                           # 살아 있는 것만. 루프 중 free·alloc 안전
        g.timer += 16                               # -= 는 wrap, 포화는 g.isub_sat("timer", v)
        guns.dispatch("gunid", {3: boss_a, 4: boss_b})
        if EUDIf()(g.done >= 1):
            guns.free_current()                     # 원본 Gun_DoSuspend / TS_Suspend (= 반납, 일시 정지가 아님)
        EUDEndIf()
    guns.Line(5, Exactly, 0); guns.SetLine(7, Add, 1)   # 옛 줄 번호 별칭 (SetLine(…, Subtract, …) 은 포화)

epScript (`import eudext.pool as pool;`):

    const guns = pool.Pool("Gun", "unit! x! y! owner timer phase done gunid", capacity=36);
    const g = guns.cur;                             // 레지스터 보기는 const 로
    foreach (_ : guns.each()) { g.timer += 16; if (g.done >= 1) { guns.free_current(); continue; } }

## 저장 배치 (빌드마다 EUDCustomVarBuffer 에 한 덩어리)

- 레코드 r = 72B 변수 원소 E 개의 **사슬**(E = F + 2, `index=True` 면 F + 3). 원소 k 는 "레지스터 k ← 값" 한 액션을
  실행하고 원소 k+1 로 간다(eudplib 0.81 `EUDQueue` 기법, `_compat.custom_varray`). 숨은 원소: `_addr`(레코드 주소),
  (`_index`), `_h`(핸들). 마지막 원소 `_h` 의 **next 칸이 곧 생존 표시**다: 살아 있으면 `T_alive`, 반납이면 `T_dead`.
  그래서 방문 때 생존 판정 트리거가 따로 없다.
- **핸들 = 마지막 원소 next 칸의 EPD** (0 = 없음). CP 를 핸들에 두면 필드 k 값 칸이 `CP + 18(k−E+1) + 86`,
  생존 칸이 `CP + 0` 이라 곱셈·나눗셈 없이 CP 연속 쓰기로 필드를 쓴다. (S2 초안의 "레코드 주소" 에서 바꿈 —
  쓰기마다 주소→EPD 변환이 필요했기 때문.)
- 살아 있는 목록 L = 72B 원소 2×cap 개. 원소 i 는 **자기 next 칸에** 레코드 주소를 쓰는 원소라, 뛰어들면 곧바로
  그 레코드 사슬로 간다. 순회 포인터는 트리거 C 의 next 칸 하나. 2×cap 인 까닭: 한 프레임 안에서 앞에서 빠진 레코드가
  자리를 차지한 채(최대 cap) 루프 중 새 레코드가 끝에 붙을 수 있다(최대 cap). 정리 뒤 길이는 cap 이하.
- 빈 칸 스택 FS = dword cap 개(번호). 꺼낼 때 CP 로 번호 비트 b 개만 읽으면서 핸들·주소를 한꺼번에 더한다(b = 번호 비트 수).
- 쓰레기 레코드(TRASH): 넘침 때 alloc 호출 자리의 필드 쓰기가 갈 곳.

## 한 프레임 (each 호출 자리마다)

    머리: 빈 풀이면 끝(실행 2). 아니면 C·T_alive·T_tail 등의 next 를 이 자리로 고침 + 목록 끝 주소를 C 의 조건에 복사
    C(끝인가?) → L[i] → 사슬 E 칸 → T_alive(포인터 +72, flag=1, 쓰기 포인터 +1) → 본문 → T_tail(flag==0 이면 반납 경로)
      → 되쓰기(W+4) → (앞에서 빠진 레코드가 있으면 MOVE: 목록 앞으로 당김) → C
    반납·표시된 레코드: T_dead / FREEP → DEAD(빈 칸 스택에 번호 넣기, 이후 MOVE 켬) → C
    끝: 루프 중 alloc 이 있었으면 그 레코드들을 본문 없이 한 번 더 훑어 압축(2단계), 빠진 것이 있었으면 목록 끝을 고침.

"빠진 레코드가 있었나" 는 비교 트리거 없이 **다음 트리거 주소를 바꿔 두는 방식**으로 기억한다(K 칸).

## 되쓰기 목록

본문을 만드는 동안(each 호출 자리가 열려 있는 동안) 보기 객체(`g`, `pool.cur`)로 접근한 필드 중 `readonly` 가 아닌 것을
**풀 전체에서 합쳐** 모든 호출 자리가 같은 되쓰기 코드(W 필드)를 쓴다. 목록은 주 함수 생성이 끝난 뒤
(`_compat.on_start_after_main`) 정해지므로, 본문을 epScript 함수로 나눠도 그 함수가 **루프 안에서 처음 불리면** 잡힌다.
루프 밖에서 먼저 만든 함수가 필드를 쓰면 `g.touch("name")` 이나 `writeback="all"` 을 쓴다(S2 8-25).

## 한 프로세스 여러 빌드

공유 코드는 빌드마다 새로 만든다(`_compat.register_build_reset`). 레지스터·저장 원소 객체는 빌드 사이에 재사용한다.
EUDFunc 본문 안의 each·alloc 은 첫 빌드의 공유 코드를 가리키므로 **첫 빌드에서만 맞다**(문자열 번호 문제와 같은 제약).

출처: S2 6절(설계·의사코드), eudplib 0.81 `collections/eudqueue.py`(사슬 순회), `core/eudstruct/vararray.py`(원소 배치),
`memio/modcurpl.py`(CP 캐시 되돌리기), 원본 문구 MSF_Respect_V `GunData.lua:26, 244, 312, 2976`.
"""

import inspect
import weakref

from eudplib import (
    Add,
    AtLeast,
    AtMost,
    CurrentPlayer,
    Db,
    Deaths,
    DeathsX,
    DisplayText,
    EPD,
    EUDBreak,
    EUDCreateBlock,
    EUDElse,
    EUDEndIf,
    EUDEndSwitch,
    EUDIf,
    EUDLightVariable,
    EUDPopBlock,
    EUDSwitch,
    EUDSwitchCase,
    EUDSwitchDefault,
    EUDVariable,
    Exactly,
    Forward,
    IsConstExpr,
    Memory,
    MemoryX,
    NextTrigger,
    PlayWAV,
    PopTriggerScope,
    PushTriggerScope,
    RawTrigger,
    SetDeaths,
    SetMemory,
    SetNextPtr,
    SetNextTrigger,
    SetTo,
    Subtract,
    VProc,
    f_dwread_epd,
    f_dwwrite_epd,
    unProxy,
)

from eudext import _compat, _parts, cmp
from eudext.errors import check_choice, fail, require, warn

__all__ = ["BUZZ_WAV", "Field", "Pool"]

M32 = 0xFFFFFFFF
CP_ADDR = 0x6509B0
CP_EPD = EPD(CP_ADDR)
BUZZ_WAV = "sound\\Misc\\Buzz.wav"
_BLOCK = "eudext_pool_each"

# 보기 객체 멤버와 겹치면 안 되는 이름
_RESERVED = {
    "handle", "index", "alive", "pool", "touch", "isub_sat", "cur", "fields", "capacity", "count", "dropped",
}


def _msg_full(name):
    # 원본 G_SendErrT (MSF_Respect_V GunData.lua:26) 에서 "f_Gun" 을 풀 이름으로, "G_Send" 를 alloc 으로
    return ("\x07『 \x08ERROR : \x04%s의 목록이 가득 차 alloc을 실행할 수 없습니다! "
            "스크린샷으로 제작자에게 제보해주세요!\x07 』" % name)


def _msg_unknown(name, field):
    # 원본 GunCaseErrT (MSF_Respect_V GunData.lua:312)
    return ("\x07『 \x08ERROR : \x04%s: 등록되지 않은 %s 값이 작동하여 자동으로 반납하였습니다. "
            "등록해주세요.\x07 』" % (name, field))


def _msg_double_free(name):
    return "\x07『 \x03TESTMODE OP \x04: %s free — 이미 반납된 핸들이라 무시했습니다 \x07』" % name


# ---------------------------------------------------------------------------------------------
# 필드 선언
# ---------------------------------------------------------------------------------------------


class Field:
    """풀 레코드의 필드 선언.

    인자: name(파이썬 식별자, 밑줄로 시작 금지), init(alloc 에서 값을 안 줬을 때의 기본값 — 정수 상수),
          signed(True 면 `Line`·epScript 비교(`g.f >= v`)가 `cmp` 의 부호 있는 비교를 쓴다. 저장은 같다),
          readonly(True 면 alloc 때만 쓰는 필드 — 되쓰기에서 빠지고 보기로 대입하면 컴파일 오류)
    반환: Field
    비용: 없음(선언)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `pool.Pool("P", list(pool.Field("dir", signed=true), "x! y! timer"), capacity=8)`
              (문자열 선언은 이름 뒤 `!` = readonly)
    출처: S2 6.2
    """

    __slots__ = ("init", "name", "readonly", "signed")

    def __init__(self, name, init=0, signed=False, readonly=False):
        if not isinstance(name, str) or not name.isidentifier():
            fail("Field: 필드 이름은 파이썬 식별자여야 합니다 (%r)", name)
        if name.startswith("_"):
            fail("Field %s: 밑줄로 시작하는 이름은 숨은 필드용으로 예약돼 있습니다", name)
        if name in _RESERVED:
            fail("Field %s: 보기 객체 멤버와 겹치는 이름입니다 (예약: %s)", name, ", ".join(sorted(_RESERVED)))
        init = unProxy(init)
        if isinstance(init, bool) or not isinstance(init, int):
            fail("Field %s: init 은 정수 상수여야 합니다 (%r)", name, init)
        if not -(1 << 31) <= init <= M32:
            fail("Field %s: init 범위 밖 %d", name, init)
        self.name = name
        self.init = init & M32
        self.signed = bool(signed)
        self.readonly = bool(readonly)

    def __repr__(self):
        flags = "".join(("!" if self.readonly else "", " signed" if self.signed else ""))
        return "Field(%s%s)" % (self.name, flags)


def _parse_fields(fields):
    items = []

    def add_str(s):
        for tok in s.split():
            ro = tok.endswith("!")
            items.append(Field(tok.rstrip("!"), readonly=ro))

    if isinstance(fields, str):
        add_str(fields)
    elif isinstance(fields, (list, tuple)):
        for it in fields:
            it = unProxy(it)
            if isinstance(it, Field):
                items.append(it)
            elif isinstance(it, str):
                add_str(it)
            elif isinstance(it, bytes):
                add_str(it.decode("utf-8"))
            else:
                fail("Pool: 필드 선언은 문자열이나 Field 여야 합니다 (%r). epScript 는 공백으로 나눈 문자열 하나 "
                     "또는 list(...) 를 쓴다 ([...] 는 EUDArray 가 된다)", it)
    else:
        fail("Pool: fields 는 공백으로 나눈 문자열 또는 목록이어야 합니다 (%r)", fields)
    require(items, "Pool: 필드가 하나도 없습니다")
    seen = set()
    for f in items:
        if f.name in seen:
            fail("Pool: 필드 이름 중복 %s", f.name)
        seen.add(f.name)
    return items


_CMP_NAMES = {"exactly": "eq", "atleast": "ge", "atmost": "le"}


def _cmp_kind(t):
    if isinstance(t, str):
        k = _CMP_NAMES.get(t.lower())
    else:
        k = {10: "eq", 0: "ge", 1: "le"}.get(_enc_cmp(t))
    if k is None:
        fail("Line: 비교는 Exactly/AtLeast/AtMost 만 됩니다 (%r)", t)
    return k


def _enc_cmp(t):
    from eudplib import EncodeComparison

    try:
        v = EncodeComparison(t)
    except Exception:  # noqa: BLE001
        return None
    return v if isinstance(v, int) else None


def _mod_kind(m):
    from eudplib import EncodeModifier

    if isinstance(m, str):
        k = {"setto": 7, "add": 8, "subtract": 9}.get(m.lower())
    else:
        try:
            k = EncodeModifier(m)
        except Exception:  # noqa: BLE001
            k = None
    if k not in (7, 8, 9):
        fail("SetLine: 수정자는 SetTo/Add/Subtract 만 됩니다 (%r)", m)
    return k


def _is_const(v):
    v = unProxy(v)
    if isinstance(v, bool):
        return True
    return isinstance(v, int) or (IsConstExpr(v) and not _compat.is_var(v))


def _const(v):
    v = unProxy(v)
    if isinstance(v, bool):
        v = int(v)
    if isinstance(v, int):
        if not -(1 << 31) <= v <= M32:
            fail("pool: 32비트 범위 밖 상수 %d", v)
        return v & M32
    return v


def _as_var(v):
    """값을 VProc 에 넣을 수 있는 EUDVariable 로 (상수면 None)."""
    v = unProxy(v)
    if _is_const(v):
        return None
    if isinstance(v, EUDVariable):
        return v
    if _compat.is_varbase(v) and hasattr(v, "getValueAddr"):
        return f_dwread_epd(EPD(v.getValueAddr()))
    t = EUDVariable()
    t << v
    return t


# ---------------------------------------------------------------------------------------------
# 빌드 상태
# ---------------------------------------------------------------------------------------------

_POOLS = weakref.WeakSet()


def _reset_all():
    for p in list(_POOLS):
        p._m = None


_compat.register_build_reset(_reset_all)


def _emit_cp_writes_restore(acts, nxt):
    """acts(CP 상대 쓰기 목록)를 트리거에 싣고 마지막에 CP 를 eudplib 캐시 값으로 되돌린 뒤 nxt 로 간다.
    반환: 마지막 트리거의 "next 로 가는 액션"(값 칸 = 액션 + 20)."""
    cache = _compat.cpcache_var()
    vt = cache.GetVTable()
    k_act = SetNextPtr(vt, nxt)
    tail = [cache.SetDest(CP_EPD), k_act]
    acts = list(acts)
    while len(acts) + len(tail) > 64:
        RawTrigger(actions=acts[:64])
        acts = acts[64:]
    RawTrigger(nextptr=vt, actions=acts + tail)
    return k_act


class _Machine:
    """풀 하나의 빌드별 공유 코드(순회 부품·반납·압축·alloc 핵심·보고 문구)."""

    def __init__(self, p):
        self.p = p
        self.finalized = False
        self.wb_fields = frozenset()
        self.force_all = False
        cache = _compat.cpcache_var()
        vt = cache.GetVTable()
        E = p._E
        self.C = C = Forward()
        self.T_alive = T_alive = Forward()
        self.T_dead = T_dead = Forward()
        self.X2 = X2 = Forward()
        self.T_tail = T_tail = Forward()
        self.MOVE = MOVE = Forward()
        self.DEAD = DEAD = Forward()
        self.FREEP = FREEP = Forward()
        self.K_slot = Forward()  # "빠진 레코드가 있었나" 를 기억하는 next 칸 주소
        self.tail_default = Forward()  # T_tail 의 기본 다음 (되쓰기 시작 또는 C)
        self.freep_reset = Forward()  # 반납 경로가 T_tail 에 되돌려 둘 값 (되쓰기 시작 또는 MOVE)
        self.alloc_entry = Forward()
        self.ret_full = Forward()
        with _compat.isolated_scope():
            # C: next 칸 = 순회 포인터(L 원소 주소). 포인터가 목록 끝(조건 amount, 머리에서 복사)에 닿으면 끝으로.
            self.c_cond = Memory(C + 4, AtLeast, 0)  # 실행 중 채우지만 부정하지 않는 조건(3.4 해당 없음)
            self.c_act = SetNextPtr(C, 0)
            C << RawTrigger(nextptr=0, conditions=self.c_cond, actions=self.c_act)
            T_alive << RawTrigger(
                nextptr=0,  # 호출 자리의 본문 (머리가 고침)
                actions=[SetMemory(C + 4, Add, 72), p._flag.SetNumber(1),
                         p._w_epd.AddNumber(18), p._w_addr.AddNumber(72)],
            )
            T_dead << RawTrigger(nextptr=DEAD, actions=SetMemory(C + 4, Add, 72))
            X2 << RawTrigger(nextptr=0)  # 본문 없는 방문(2단계·EUDBreak 뒤): C 또는 MOVE
            T_tail << RawTrigger(nextptr=self.tail_default, conditions=p._flag.Exactly(0),
                                 actions=SetNextPtr(T_tail, FREEP))
            def removal():
                return [SetMemory(self.K_slot, SetTo, MOVE), SetNextPtr(X2, MOVE)]

            # FREEP: 본문이 free_current 한 레코드 — 생존 칸에 T_dead, 쓰기 포인터 되돌림
            FREEP << NextTrigger()
            VProc(p._reg_h, [p._reg_h.QueueAssignTo(CP_EPD), SetNextPtr(T_tail, self.freep_reset), *removal(),
                             p._w_epd.AddNumber(-18 & M32), p._w_addr.AddNumber(-72 & M32)])
            RawTrigger(nextptr=vt, actions=[SetDeaths(CurrentPlayer, SetTo, T_dead, 0),
                                            cache.SetDest(CP_EPD), SetNextPtr(vt, DEAD)])
            # DEAD: 번호를 빈 칸 스택에
            DEAD << NextTrigger()
            if p._reg_index is not None:
                idx = p._reg_index
            else:
                idx = p._dead_idx
                p._emit_index(p._reg_h, idx)
            pa = SetDeaths(0, SetTo, 0, 0)
            VProc([p._fs_top, idx], [p._fs_top.QueueAssignTo(EPD(pa) + 4), idx.QueueAssignTo(EPD(pa) + 5), *removal()])
            RawTrigger(nextptr=C, actions=[pa, p._fs_top.AddNumber(1), p._free_n.AddNumber(1),
                                           p._removed.SetNumber(1)])
            # MOVE: 이 레코드 주소를 목록의 쓰기 자리(w_epd − 18)로 (T_alive 가 w_epd 를 이미 올렸다)
            MOVE << NextTrigger()
            ma = SetDeaths(0, SetTo, 0, 0)
            VProc([p._w_epd, p._reg_addr], [p._w_epd.QueueAssignTo(EPD(ma) + 4), p._reg_addr.QueueAssignTo(EPD(ma) + 5)])
            RawTrigger(nextptr=C, actions=[SetMemory(ma + 16, Add, -18 & M32), ma])
            # alloc 핵심: 빈 칸 스택에서 번호 → 핸들·주소, 목록 끝에 붙이기
            self.alloc_entry << NextTrigger()
            S0, POP, FULL = Forward(), Forward(), Forward()
            S0 << RawTrigger(nextptr=POP, conditions=p._free_n.Exactly(0), actions=SetNextPtr(S0, FULL))
            POP << NextTrigger()
            VProc(p._fs_top, [p._fs_top.AddNumber(M32), p._fs_top.QueueAssignTo(CP_EPD),
                              p._out_h.SetNumber(p._H0), p._out_addr.SetNumber(p._A0), p._free_n.AddNumber(M32),
                              p._count.AddNumber(1), p._appended.AddNumber(1)])
            for k in range(p._bits):
                RawTrigger(conditions=DeathsX(CurrentPlayer, AtLeast, 1, 0, 1 << k),
                           actions=[p._out_h.AddNumber((18 * E) << k), p._out_addr.AddNumber((72 * E) << k)])
            la = SetDeaths(0, SetTo, 0, 0)
            VProc([p._live_end_epd, p._out_addr],
                  [p._live_end_epd.QueueAssignTo(EPD(la) + 4), p._out_addr.QueueAssignTo(EPD(la) + 5)])
            self.ret_ok = SetNextPtr(vt, 0)  # 호출 자리가 값 칸을 고친다
            RawTrigger(nextptr=vt, actions=[la, p._live_end.AddNumber(72), p._live_end_epd.AddNumber(18),
                                            cache.SetDest(CP_EPD), self.ret_ok])
            self.labels = {"S0": S0, "POP": POP, "FULL": FULL}  # 시험·진단용
            FULL << RawTrigger(actions=[SetNextPtr(S0, POP), p._dropped.AddNumber(1), p._out_h.SetNumber(p._TRASH_H)])
            p._report(p.on_full, "full")
            self.ret_full << RawTrigger(nextptr=0)  # 호출 자리가 고친다
        phase = _compat.onstart_phase()
        if phase < 2:
            _compat.on_start_after_main(self.finalize)
        else:
            self.force_all = True
            self.finalize()

    # --- 되쓰기 코드 (주 함수 생성 뒤) ---
    def finalize(self):
        if self.finalized:
            return
        self.finalized = True
        p = self.p
        names = p._wb_names(self.force_all)
        self.wb_fields = frozenset(names)
        if not names:
            self.tail_default << self.C
            self.K_slot << self.T_tail + 4
            self.freep_reset << self.MOVE
            return
        with _compat.isolated_scope():
            entry = NextTrigger()
            regs, queue, acts = [], [p._reg_h.QueueAssignTo(CP_EPD)], []
            cur = 0
            for name in names:
                off = p._off(p._kidx[name])
                acts.append(SetMemory(CP_ADDR, Add, (off - cur) & M32))
                cur = off
                a = SetDeaths(CurrentPlayer, SetTo, 0, 0)
                acts.append(a)
                regs.append(p._reg[name])
                queue.extend(p._reg[name].QueueAssignTo(EPD(a) + 5))
            VProc([p._reg_h, *regs], queue)
            k_act = _emit_cp_writes_restore(acts, self.C)
        self.tail_default << entry
        self.K_slot << k_act + 20
        self.freep_reset << entry


# ---------------------------------------------------------------------------------------------
# 레지스터 보기
# ---------------------------------------------------------------------------------------------


class _View:
    """레지스터 보기(`pool.cur`, `each()` 가 주는 것). 필드 이름 = 그 필드의 레지스터 EUDVariable.

    - `g.x` 는 레지스터 EUDVariable 을 돌려준다(본문 생성 중이면 되쓰기 목록에 넣는다).
    - `g.x = v` → `레지스터 << v`. readonly 필드면 컴파일 오류.
    - epScript `g.x += v` → `iaddattr`, `g.x -= v` → `isubattr`(**wrap**, `_parts.isub32`), `g.x == v` → `eqattr` 등
      (signed 필드는 부호 있는 비교).
    - 파이썬 `g.x -= g.x` 는 eudplib 버그로 0xFFFFFFFF 가 된다 → `g.x = 0` 으로 쓴다(DESIGN 3.5).
    - `g.handle`(핸들 레지스터), `g.index`(번호: `index=True` 면 레지스터, 아니면 계산 — 실행 b+약 8),
      `g.alive`(방문 중 생존 1비트, EUDLightVariable), `g.isub_sat(name, v)`(포화), `g.touch(*names)`.
    """

    __slots__ = ("_pool",)

    def __init__(self, pool):
        object.__setattr__(self, "_pool", pool)

    def __getattr__(self, name):
        p = object.__getattribute__(self, "_pool")
        if name not in p._kidx:
            raise AttributeError("풀 %s 에 필드 %r 가 없습니다" % (p.name, name))
        p._touch(name)
        return p._reg[name]

    def __setattr__(self, name, value):
        p = object.__getattribute__(self, "_pool")
        if name not in p._kidx:
            fail("풀 %s 에 필드 %r 가 없습니다", p.name, name)
        p._assign(name, value)

    def __repr__(self):
        p = object.__getattribute__(self, "_pool")
        return "<pool %s 레지스터 보기 — epScript 에서는 var 가 아니라 const 로 묶는다>" % p.name

    def __bool__(self):
        fail("레지스터 보기는 참거짓으로 쓸 수 없습니다 (필드 조건은 g.x == v, guns.Line(...))")

    @property
    def pool(self):
        return object.__getattribute__(self, "_pool")

    @property
    def handle(self):
        return self.pool._reg_h

    @property
    def index(self):
        p = self.pool
        if p._reg_index is not None:
            return p._reg_index
        return p.index_of(p._reg_h)

    @property
    def alive(self):
        return self.pool._flag

    def touch(self, *names):
        """되쓰기 목록에 필드를 넣는다(레지스터를 본문 밖에서 꺼내 둔 경우). 반환: None."""
        p = self.pool
        for n in names:
            if n not in p._kidx:
                fail("touch: 풀 %s 에 필드 %r 가 없습니다", p.name, n)
            p._touch(n, force=True)

    def isub_sat(self, name, v):
        """필드 ← max(필드 − v, 0) (**포화**). 반환: 레지스터."""
        p = self.pool
        p._check_writable(name)
        p._touch(name, force=True)
        return _parts.isub_sat32(p._reg[name], v)

    # epScript 통로 (_ATTW)
    def _rw(self, name):
        p = self.pool
        if name not in p._kidx:
            raise AttributeError(name)
        p._check_writable(name)
        p._touch(name, force=True)
        return p._reg[name]

    def iaddattr(self, name, v):
        self._rw(name).__iadd__(v)

    def isubattr(self, name, v):
        _parts.isub32(self._rw(name), v)

    def imulattr(self, name, v):
        r = self._rw(name)
        r << r * v

    def imodattr(self, name, v):
        r = self._rw(name)
        r << r % v

    def ilshiftattr(self, name, v):
        r = self._rw(name)
        r << _shl(r, v)

    def irshiftattr(self, name, v):
        r = self._rw(name)
        r << (r >> v)

    def iandattr(self, name, v):
        self._rw(name).__iand__(v)

    def iorattr(self, name, v):
        self._rw(name).__ior__(v)

    def ixorattr(self, name, v):
        self._rw(name).__ixor__(v)

    # epScript 비교 통로 (_ATTC) — 읽기만이라 되쓰기 목록에 넣지 않는다
    def _cmpattr(self, name, op, v):
        p = self.pool
        if name not in p._kidx:
            raise AttributeError(name)
        return p._cond(name, op, v)

    def eqattr(self, name, v):
        return self._cmpattr(name, "eq", v)

    def neattr(self, name, v):
        return self._cmpattr(name, "ne", v)

    def leattr(self, name, v):
        return self._cmpattr(name, "le", v)

    def geattr(self, name, v):
        return self._cmpattr(name, "ge", v)

    def ltattr(self, name, v):
        return self._cmpattr(name, "lt", v)

    def gtattr(self, name, v):
        return self._cmpattr(name, "gt", v)


def _shl(r, v):
    # EUDVariable 의 << 는 대입이므로 시프트는 곱셈으로 (상수만)
    v = unProxy(v)
    if not isinstance(v, int):
        fail("g.x <<= v: 시프트 양은 상수만 됩니다")
    return r * (1 << (v & 31))


_UNSIGNED = {"eq": cmp.eq, "ne": cmp.ne, "le": cmp.le, "ge": cmp.ge, "lt": cmp.lt, "gt": cmp.gt}
_SIGNED = {"eq": cmp.eq, "ne": cmp.ne, "le": cmp.sle, "ge": cmp.sge, "lt": cmp.slt, "gt": cmp.sgt}


# ---------------------------------------------------------------------------------------------
# 풀
# ---------------------------------------------------------------------------------------------


class Pool:
    """고정 용량 오브젝트 풀 (건물 스택 `Gun_Line`, TStruct 대체).

    인자: name(표시용·오류 문구), fields(공백으로 나눈 문자열 — 이름 뒤 `!` = readonly — 또는 str/Field 목록),
          capacity(레코드 수, 1 이상 상수), aliases({옛 줄 번호: 필드 이름} — 없으면 필드 순서가 번호),
          alias_base(0 = Gun_Line 식, 1 = TSLine 식), on_full("report" 원본 문구 + Buzz ×3 | "silent" | 함수),
          on_unknown(dispatch 기본 가지: "report" 문구 + Buzz ×2 + 반납 | "silent" 반납만 | 함수),
          writeback("accessed" 본문에서 접근한 쓰기 가능 필드 | "all"), debug(True: 이중 해제 문구, alloc/free 시험 문구,
          루프 밖 free_current 컴파일 오류, 방문 밖 `cur` 대입 경고), index(True: 번호를 사슬에 실어 `g.index` 를 공짜로 —
          레코드당 72B·방문당 실행 1 더)
    반환: Pool
    비용: 저장 = cap × ((F+2)×72 + 148) + (F+2)×72 + 쓰레기 레코드 약 72F B = S2 목표식 cap×((F+3)×72+76)+(F+3)×72
          와 같다 (index=True 면 레코드당 72B 더).
          매 프레임 = 빈 풀 2 / 레코드 있으면 고정 8 + 방문마다 F+10+W (W = 되쓰는 필드 수, 0 이면 F+6)
          + 앞에서 빠진 레코드 뒤 방문마다 3. 공유 코드는 풀마다 약 2b+30 트리거(빌드당 1벌, 페이로드 약 20~26KB)
          (2026-09-17, docs/COSTS.md "pool (WP11)")
    CP: 바꾸지 않음(안에서 잠깐 옮기고 eudplib CP 캐시 값으로 되돌림)
    로컬: 공유 안전. 로컬 값(키·마우스)으로 alloc·필드 쓰기를 하면 디싱크(DESIGN 3.7)
    epScript: `const guns = pool.Pool("Gun", "unit! x! y! owner timer", capacity=36, alias_base=1);`
    출처: S2 6절, CtrigAsm 건물 스택(MSF_Respect_V GunData.lua)·TStruct(MapSource Library/TStruct.lua),
          eudplib 0.81 collections/eudqueue.py (사슬 순회)
    """

    def __init__(self, name, fields, capacity, aliases=None, alias_base=0, on_full="report", on_unknown="report",
                 writeback="accessed", debug=False, index=False):
        _compat.check_pool()
        if isinstance(name, bytes):
            name = name.decode("utf-8")
        require(isinstance(name, str) and name, "Pool: name 은 문자열이어야 합니다 (%r)", name)
        self.name = name
        self._fields = _parse_fields(fields)
        capacity = unProxy(capacity)
        require(isinstance(capacity, int) and not isinstance(capacity, bool) and 1 <= capacity <= 0x100000,
                "Pool %s: capacity 는 1 이상 상수여야 합니다 (%r)", name, capacity)
        self.capacity = capacity
        check_choice("alias_base", alias_base, (0, 1))
        self.alias_base = alias_base
        if not (on_full in ("report", "silent") or callable(on_full)):
            fail("Pool %s: on_full 은 \"report\"·\"silent\"·함수 중 하나 (%r)", name, on_full)
        if not (on_unknown in ("report", "silent") or callable(on_unknown)):
            fail("Pool %s: on_unknown 은 \"report\"·\"silent\"·함수 중 하나 (%r)", name, on_unknown)
        self.on_full = on_full
        self.on_unknown = on_unknown
        check_choice("writeback", writeback, ("accessed", "all"))
        self.writeback = writeback
        self.debug = bool(debug)
        self.use_index = bool(index)
        self._kidx = {f.name: k for k, f in enumerate(self._fields)}
        self._fmap = {f.name: f for f in self._fields}
        # 옛 줄 번호
        if aliases is None:
            self._aliases = {alias_base + k: f.name for k, f in enumerate(self._fields)}
        else:
            require(isinstance(aliases, dict), "Pool %s: aliases 는 {번호: 이름} dict 여야 합니다", name)
            self._aliases = {}
            for n, fname in aliases.items():
                n = unProxy(n)
                require(isinstance(n, int) and n >= alias_base, "Pool %s: 줄 번호 %r (alias_base=%d)", name, n,
                        alias_base)
                if isinstance(fname, bytes):
                    fname = fname.decode("utf-8")
                require(fname in self._kidx, "Pool %s: aliases 의 %r 는 필드가 아닙니다", name, fname)
                self._aliases[n] = fname
        F = len(self._fields)
        self._F = F
        self._E = E = F + 2 + (1 if self.use_index else 0)
        if E + 1 > 33:
            warn("Pool %s: 레코드당 저장((필드 %d + 숨은 %d + 목록 1) × 72B)이 CtrigAsm 트리거 한 개(2,416B)보다 큽니다 — "
                 "케이스 전용 칸은 전역으로 빼세요 (S2 6.2)", name, F, E - F)
        self._bits = max(1, (capacity - 1).bit_length())
        # 레지스터
        self._reg = {f.name: EUDVariable() for f in self._fields}
        self._reg_addr = EUDVariable()
        self._reg_h = EUDVariable()
        self._reg_index = EUDVariable() if self.use_index else None
        self._flag = EUDLightVariable(0)
        # 저장: 사슬 cap×E 원소 + 목록 cap 원소 (한 덩어리 — 서로 가리키는 두 덩어리는 eudplib 수집 중 오류)
        D = Forward()
        self._S = D
        self._L = D + 72 * E * capacity
        self._H0 = self._handle_const(0)
        self._A0 = D
        trip = []
        dests = [EPD(self._reg[f.name].getValueAddr()) for f in self._fields]
        dests.append(EPD(self._reg_addr.getValueAddr()))
        if self.use_index:
            dests.append(EPD(self._reg_index.getValueAddr()))
        dests.append(EPD(self._reg_h.getValueAddr()))
        for r in range(capacity):
            base = D + 72 * E * r
            vals = [0] * F + [base]
            if self.use_index:
                vals.append(r)
            vals.append(self._handle_const(r))
            for k in range(E):
                nxt = base + 72 * (k + 1) if k < E - 1 else 0  # 마지막 next = 생존 표시 (처음엔 0 = 빈 칸)
                trip.append((dests[k], vals[k], nxt))
        # 목록은 2×용량: 한 프레임 안에서 "앞에서 빠졌지만 아직 자리를 차지한 레코드(최대 cap)" 뒤에
        # "루프 중 새로 잡은 레코드(최대 cap)" 가 붙을 수 있다. 정리 뒤 길이는 늘 cap 이하.
        for i in range(2 * capacity):
            trip.append((EPD(self._L + 72 * i) + 1, 0, 0))
        D << _compat.custom_varray(trip)
        # 빈 칸 스택 (꺼내는 순서 0, 1, 2 …)
        self._FS = Db(b"".join((capacity - 1 - k).to_bytes(4, "little") for k in range(capacity)))
        # 필드 k 값 칸 = EPD(시작) + 18k + 87 (k ≤ E−1), 생존 칸 = EPD(시작) + 18(E−1) + 1 → 18E + 69 칸 이상
        self._TRASH = Db(4 * (18 * E + 100))
        self._TRASH_H = EPD(self._TRASH) + 18 * (E - 1) + 1
        # 상태
        self._fs_top = EUDVariable(EPD(self._FS) + capacity)
        self._free_n = EUDVariable(capacity)
        self._count = EUDVariable(0)
        self._dropped = EUDVariable(0)
        self._live_end = EUDVariable(self._L)
        self._live_end_epd = EUDVariable(EPD(self._L) + 87)
        self._w_epd = EUDVariable()
        self._w_addr = EUDVariable()
        self._snap = EUDVariable()  # 이번 each 가 시작할 때의 목록 끝 주소
        self._removed = EUDLightVariable(0)
        self._appended = EUDLightVariable(0)
        self._out_h = EUDVariable()
        self._out_addr = EUDVariable()
        self._dead_idx = EUDVariable()
        self._ix_t = EUDVariable()
        self._index_func = None
        self._accessed = set()
        self._active = 0
        self._cases = {}
        self._sites = []
        self._m = None
        self._view = _View(self)
        _POOLS.add(self)

    # ------------------------------------------------------------------ 내부 도우미
    def _handle_const(self, r):
        return EPD(self._S + 72 * (self._E * r + self._E - 1)) + 1

    def _off(self, k):
        """핸들(= CP) 에서 필드 k 값 칸까지의 EPD 차이."""
        return 18 * (k - self._E + 1) + 86

    def _mach(self):
        if self._m is None:
            self._m = _Machine(self)
        return self._m

    def _resolve(self, n):
        n = unProxy(n)
        if isinstance(n, bytes):
            n = n.decode("utf-8")
        if isinstance(n, str):
            if n not in self._kidx:
                fail("풀 %s 에 필드 %r 가 없습니다", self.name, n)
            return n
        if isinstance(n, int) and not isinstance(n, bool):
            name = self._aliases.get(n)
            if name is None:
                fail("풀 %s: 줄 %d 에 이름이 없다 — aliases 에 넣어라 (alias_base=%d)", self.name, n, self.alias_base)
            return name
        fail("풀 %s: 줄 번호는 정수 상수나 필드 이름이어야 합니다 (%r)", self.name, n)

    def _check_writable(self, name):
        if self._fmap[name].readonly:
            fail("풀 %s: %s 는 readonly 필드입니다 — alloc 때만 쓴다 (다른 값이 필요하면 readonly 를 빼라)", self.name, name)

    def _touch(self, name, force=False):
        if not (force or self._active):
            return
        if self._fmap[name].readonly:
            return
        self._accessed.add(name)
        m = self._m
        if m is not None and m.finalized and name not in m.wb_fields:
            fail("풀 %s: 되쓰기 목록이 정해진 뒤(주 함수 생성 뒤) 필드 %s 를 새로 접근했습니다 — "
                 "writeback=\"all\" 이나 루프 안에서 g.touch(\"%s\") 를 쓰세요", self.name, name, name)

    def _wb_names(self, force_all=False):
        writable = [f.name for f in self._fields if not f.readonly]
        if self.writeback == "all" or force_all:
            return writable
        return [n for n in writable if n in self._accessed]

    def _assign(self, name, value):
        self._check_writable(name)
        if self.debug and not self._active:
            warn("풀 %s: 방문 중이 아닌 곳에서 cur.%s 에 대입합니다 (레코드에 저장되지 않음)", self.name, name)
        self._touch(name)
        r = self._reg[name]
        if unProxy(value) is r:
            return
        r << value

    def _cond(self, name, op, v):
        table = _SIGNED if self._fmap[name].signed else _UNSIGNED
        return table[op](self._reg[name], v)

    def _emit_index(self, src, out):
        """out ← (src − H0) ÷ (18E) — 핸들 → 번호 (실행 b + 2)."""
        step = 18 * self._E
        t = self._ix_t
        VProc(src, [src.QueueAssignTo(t), out.SetNumber(0)])
        for k in reversed(range(self._bits)):
            c = step << k
            RawTrigger(conditions=t.AtLeast(self._H0 + c), actions=[t.AddNumber(-c & M32), out.AddNumber(1 << k)])

    def _report(self, how, kind, field=None):
        if how == "silent":
            return
        if callable(how):
            try:
                n = len(inspect.signature(how).parameters)
            except (TypeError, ValueError):
                n = 0
            how(self) if n else how()
            return
        from eudext import players

        if kind == "full":
            players.run_as(players.Everyone, DisplayText(_msg_full(self.name)), *[PlayWAV(BUZZ_WAV)] * 3)
        else:
            players.run_as(players.Everyone, DisplayText(_msg_unknown(self.name, field)), *[PlayWAV(BUZZ_WAV)] * 2)

    def _debug_print(self, fmt, *args):
        from eudplib import f_printAll

        f_printAll(fmt, *args)

    def _handle_var(self, h, what):
        h = unProxy(h)
        if isinstance(h, EUDVariable):
            return h
        if isinstance(h, int) and not isinstance(h, bool):
            fail("풀 %s.%s: 핸들은 변수여야 합니다 (상수 %d)", self.name, what, h)
        if _compat.is_var(h) or _compat.is_varbase(h):
            return _as_var(h)
        fail("풀 %s.%s: 핸들은 alloc 이 돌려준 변수여야 합니다 (%r)", self.name, what, h)

    # ------------------------------------------------------------------ 공개 멤버
    @property
    def fields(self):
        """필드 이름 튜플(선언 순서)."""
        return tuple(f.name for f in self._fields)

    @property
    def cur(self):
        """레지스터 보기(`each()` 가 주는 것과 같은 객체). `pool.cur.timer` = timer 레지스터 EUDVariable.

        epScript: `const g = guns.cur;` (var 에 담지 않는다)
        """
        return self._view

    @property
    def count(self):
        """논리 개수 EUDVariable (alloc +1, 살아 있던 레코드 free −1). 원본 `Actived_Gun` 대체."""
        return self._count

    @property
    def dropped(self):
        """넘침 누적 수 EUDVariable (alloc·alloc_n 이 빈 칸이 모자라 실패한 횟수)."""
        return self._dropped

    def full(self):
        """빈 칸 스택이 비었나 → 새 Condition.

        루프 밖·방문을 마친 레코드의 free 는 다음 each 정리 때 빈 칸이 된다(S2 6.4, T9).
        비용: 0 트리거 / CP: 바꾸지 않음 / epScript: `if (guns.full()) { … }`
        """
        return self._free_n.Exactly(0)

    def alloc(self, **init):
        """레코드 하나를 잡아 모든 필드를 쓰고 핸들을 돌려준다. 빈 칸이 없으면 0 (dropped += 1, on_full).

        인자: init(필드 이름=값 — 상수·변수·식. 안 준 필드는 Field.init)
        반환: 새 EUDVariable 핸들 (0 = 실패). 루프 중에 잡은 레코드는 **다음 each 부터** 돈다.
        비용: 호출 자리 4 (+ 필드 30개마다 1) / 실행 b + 15 + (변수 값 수) (b = 번호 비트 수: cap 8 → 18, cap 128 → 22)
              공유 핵심 약 b + 8 트리거(+ 넘침 문구)는 빌드당 1벌 (2026-09-17, docs/COSTS.md)
        CP: 바꾸지 않음
        로컬: 공유 안전(값이 로컬이면 디싱크)
        epScript: `const h = guns.alloc(unit=u, x=x, y=y);  if (h == 0) { … }`
        출처: S2 6.4, 원본 G_Send / TS_SendX (식 값 허용)
        """
        m = self._mach()
        h = EUDVariable()
        self._emit_alloc_into(m, h, init)
        return h

    def _init_values(self, init):
        vals = {}
        for key, v in init.items():
            if key not in self._kidx:
                fail("풀 %s.alloc: 필드 %r 가 없습니다", self.name, key)
            vals[key] = unProxy(v)
        out = []
        for f in self._fields:
            out.append((self._kidx[f.name], vals.get(f.name, f.init)))
        return out

    def _emit_alloc_into(self, m, h, init):
        vals = self._init_values(init)
        after = Forward()
        RawTrigger(nextptr=m.alloc_entry,
                   actions=[SetMemory(m.ret_ok + 20, SetTo, after), SetNextPtr(m.ret_full, after)])
        after << NextTrigger()
        used = {id(self._out_h), id(h)}
        vars_, queue, acts = [], [*self._out_h.QueueAssignTo(h), *h.QueueAssignTo(CP_EPD)], []
        cur = 0
        for k, v in vals:
            off = self._off(k)
            acts.append(SetMemory(CP_ADDR, Add, (off - cur) & M32))
            cur = off
            if _is_const(v):
                acts.append(SetDeaths(CurrentPlayer, SetTo, _const(v), 0))
                continue
            var = _as_var(v)
            if id(var) in used:
                t = EUDVariable()
                t << var
                var = t
            used.add(id(var))
            a = SetDeaths(CurrentPlayer, SetTo, 0, 0)
            acts.append(a)
            vars_.append(var)
            queue.extend(var.QueueAssignTo(EPD(a) + 5))
        acts.append(SetMemory(CP_ADDR, Add, (0 - cur) & M32))
        acts.append(SetDeaths(CurrentPlayer, SetTo, m.T_alive, 0))
        VProc([self._out_h, h, *vars_], queue)
        nxt = Forward()
        _emit_cp_writes_restore(acts, nxt)
        nxt << NextTrigger()
        RawTrigger(conditions=self._out_h.Exactly(self._TRASH_H), actions=h.SetNumber(0))
        if self.debug:
            if EUDIf()(h.AtLeast(1)):
                self._debug_print("\x07『 \x03TESTMODE OP \x04: %s alloc 성공. 핸들 {} 개수 {} \x07』" % self.name,
                                  h, self._count)
            EUDEndIf()

    def alloc_n(self, k, inits=None, **init):
        """레코드 k 개를 **원자적으로** 잡는다: 빈 칸이 k 개 이상일 때만 모두 잡고, 모자라면 하나도 잡지 않는다.

        인자: k(1 ~ capacity 상수), inits(선택: 레코드마다 {필드: 값} dict 목록, 길이 k), init(모든 레코드 공통 값)
        반환: 핸들 EUDVariable 의 파이썬 목록(길이 k). 실패면 모두 0 (dropped += 1 한 번, on_full 한 번)
        비용: 호출 자리 = 약 4 + k × alloc / 실행 = 분기 약 2 + k × alloc (k=3, F=4: 56)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `const hs = guns.alloc_n(3, unit=u);  if (hs[0] == 0) { … }`
        출처: S1 11-7 (spawn 층 여러 개를 한 번에)
        """
        k = unProxy(k)
        require(isinstance(k, int) and 1 <= k <= self.capacity, "풀 %s.alloc_n: k 는 1 ~ %d 상수 (%r)", self.name,
                self.capacity, k)
        if inits is not None:
            inits = list(inits)
            require(len(inits) == k, "풀 %s.alloc_n: inits 길이 %d ≠ k %d", self.name, len(inits), k)
        m = self._mach()
        hs = [EUDVariable() for _ in range(k)]
        if EUDIf()(self._free_n.AtLeast(k)):
            for i in range(k):
                d = dict(init)
                if inits is not None:
                    d.update(inits[i] or {})
                self._emit_alloc_into(m, hs[i], d)
        if EUDElse()():
            RawTrigger(actions=[self._dropped.AddNumber(1)] + [h.SetNumber(0) for h in hs])
            self._report(self.on_full, "full")
        EUDEndIf()
        return hs

    def free(self, h):
        """핸들 h 의 레코드를 반납한다. 이미 반납된 핸들·0 은 무시(debug 면 문구).

        - h 가 지금 방문 중인 레코드면 `free_current()` 와 같다(방문 끝에 빈 칸이 된다).
        - 그 밖(루프 밖, 이미 방문한 레코드, 아직 안 돈 레코드)은 생존 표시만 지운다 — 빈 칸 스택에는 **다음 each 정리 때**
          들어간다(S2 6.4, T2·T5·T9). 아직 안 돈 레코드는 이번 루프에서 돌지 않는다(T4).
        인자: h(alloc 이 돌려준 핸들 변수)
        반환: None
        비용: 호출 자리 5 / 실행 방문 중이 아닌 레코드 6, 방문 중 레코드 7 (2026-09-17, docs/COSTS.md)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `guns.free(h);`
        출처: S2 6.3·6.12
        """
        m = self._mach()
        h = self._handle_var(h, "free")
        dbg = EUDLightVariable() if self.debug else None
        acts = [SetDeaths(CurrentPlayer, SetTo, m.T_dead, 0), self._count.AddNumber(M32)]
        if dbg is not None:
            acts.append(dbg.SetNumber(1))
        self._split_current(
            h,
            pre=[dbg.SetNumber(0)] if dbg is not None else [],
            mem_conds=[Deaths(CurrentPlayer, Exactly, m.T_alive, 0), h.AtLeast(self._H0)],
            mem_acts=acts,
            cur_acts=[self._flag.SetNumber(0), self._count.AddNumber(M32)],
        )
        if dbg is not None:
            if EUDIf()(dbg.Exactly(0)):
                from eudext import players

                players.run_as(players.Everyone, DisplayText(_msg_double_free(self.name)))
            EUDEndIf()

    def _split_current(self, h, pre, mem_conds, mem_acts, cur_acts):
        """CP ← h, "CP == 방문 중 핸들" 이면 [flag==1] → cur_acts, 아니면 [mem_conds] → mem_acts (CP 상대), 끝에 CP 되돌림.

        실행: 아닌 경로 = 준비 1 + h 1 + reg_h 1 + 판정 1 + 메모리 1 + CP 되돌림 1 = 6, 방문 중 경로 = 7.
        루프 밖에서는 방문 중 핸들이 0 이라 h = 0 은 방문 중 경로(flag = 0 → 아무 일 없음)로 간다.
        """
        if h is self._reg_h:  # g.handle 그대로 — 방문 중 레코드 (루프 밖이면 flag = 0 이라 아무 일 없음)
            RawTrigger(actions=pre) if pre else None
            RawTrigger(conditions=self._flag.Exactly(1), actions=cur_acts)
            return
        cache = _compat.cpcache_var()
        vt = cache.GetVTable()
        cur_cond = Memory(CP_ADDR, Exactly, 0)  # amount 는 실행 중에 채운다 (부정하지 않는다)
        T_cur, MEM, CURP, END = Forward(), Forward(), Forward(), Forward()
        VProc([h, self._reg_h], [*h.QueueAssignTo(CP_EPD), *self._reg_h.QueueAssignTo(EPD(cur_cond) + 2),
                                 cache.SetDest(CP_EPD), SetNextPtr(vt, END), *pre])
        T_cur << RawTrigger(nextptr=MEM, conditions=cur_cond, actions=SetNextPtr(T_cur, CURP))
        MEM << RawTrigger(nextptr=vt, conditions=mem_conds, actions=mem_acts)
        CURP << RawTrigger(actions=SetNextPtr(T_cur, MEM))
        RawTrigger(nextptr=vt, conditions=self._flag.Exactly(1), actions=cur_acts)
        END << NextTrigger()

    def free_current(self):
        """지금 방문 중인 레코드를 반납한다(원본 `Gun_DoSuspend`·`TS_Suspend`·Seed `G.Finish()` — **일시 정지가 아니라 반납**).

        레지스터는 지우지 않으므로 본문의 나머지는 계속 옛 값을 본다. 방문 끝에서 되쓰기를 생략하고 빈 칸 스택에 넣는다
        (같은 프레임 뒤쪽 alloc 이 재사용). 두 번 불러도 한 번만 센다. 루프 밖에서 부르면 아무 일도 하지 않는다
        (debug=True 면 컴파일 오류).
        인자: 없음
        반환: None
        비용: 호출 자리 1 / 실행 1
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `if (g.done >= 1) { guns.free_current(); continue; }`
        출처: S2 2.6, 6.3
        """
        if self.debug and not self._active:
            fail("풀 %s.free_current: each 루프 밖입니다", self.name)
        RawTrigger(conditions=self._flag.Exactly(1), actions=[self._flag.SetNumber(0), self._count.AddNumber(M32)])

    def is_alive(self, h):
        """핸들 h 의 레코드가 살아 있나 → Condition (앞 계산을 부르는 순간 낸다).

        인자: h(핸들 변수)
        반환: 새 Condition (`[결과 1비트 ≥ 1]`, EUDNot 가능)
        비용: 호출 자리 5 / 실행 6~7 (+ 조건 소비)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `if (guns.is_alive(h)) { … }`
        """
        m = self._mach()
        h = self._handle_var(h, "is_alive")
        r = EUDLightVariable()
        self._split_current(
            h,
            pre=[r.SetNumber(0)],
            mem_conds=[Deaths(CurrentPlayer, Exactly, m.T_alive, 0), h.AtLeast(self._H0)],
            mem_acts=[r.SetNumber(1)],
            cur_acts=[r.SetNumber(1)],
        )
        return r.AtLeast(1)

    def index_of(self, h, ret=None):
        """핸들 → 레코드 번호(0 ~ capacity−1). 루프 안에서는 `g.index` 를 쓴다.

        인자: h(핸들 변수 — 유효한 핸들이어야 한다. 0 이면 결과 0), ret(선택: 결과를 받을 EUDVariable)
        반환: EUDVariable
        비용: 공유 EUDFunc 1벌(본문 b + 4) / 호출 자리 약 3 / 실행 약 b + 10 (cap 8 → 13)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `const i = guns.index_of(h);`
        """
        if self._index_func is None:
            from eudplib import EUDFunc

            pool = self

            @EUDFunc
            def _pool_index_of(hh):
                out = EUDVariable()
                if EUDIf()(hh.AtLeast(pool._H0)):
                    pool._emit_index(hh, out)
                if EUDElse()():
                    out << 0
                EUDEndIf()
                return out

            self._index_func = _pool_index_of
        h = unProxy(h)
        if ret is not None:
            return self._index_func(h, ret=[ret])
        return self._index_func(h)

    def get(self, h, name):
        """방문 중이 아닌 레코드의 필드를 읽는다(느린 경로). h 가 지금 방문 중인 레코드면 레지스터를 읽는다.

        인자: h(핸들 변수), name(필드 이름 또는 옛 줄 번호)
        반환: 새 EUDVariable
        비용: 호출 자리 7 / 실행 약 42 (`f_dwread_epd` 36)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `const t = guns.get(h, "timer");`
        """
        name = self._resolve(name)
        h = self._handle_var(h, "get")
        out = EUDVariable()
        if EUDIf()(cmp.eq(h, self._reg_h)):
            out << self._reg[name]
        if EUDElse()():
            f_dwread_epd(self._field_epd(h, name), ret=[out])
        EUDEndIf()
        return out

    def _field_epd(self, h, name):
        # h + 오프셋을 새 변수에 (h 가 eudplib rvalue 여도 바꾸지 않는다 — `h + c` 는 rvalue 를 제자리에서 고친다)
        t = EUDVariable()
        VProc(h, h.QueueAssignTo(t))
        RawTrigger(actions=t.AddNumber(self._off(self._kidx[name]) & M32))
        return t

    def set(self, h, name, v):
        """방문 중이 아닌 레코드의 필드를 쓴다(느린 경로). h 가 방문 중인 레코드면 레지스터에 쓴다(되쓰기 목록에 넣음).

        readonly 필드도 쓸 수 있다(방문 중이면 레지스터와 저장 칸 둘 다).
        인자: h(핸들 변수), name(필드 이름 또는 옛 줄 번호), v(값)
        반환: None
        비용: 호출 자리 8 / 실행 9
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `guns.set(h, "timer", 0);`
        """
        name = self._resolve(name)
        h = self._handle_var(h, "set")
        ro = self._fmap[name].readonly
        if not ro:
            self._touch(name, force=True)
        epd = self._field_epd(h, name)
        if EUDIf()(cmp.eq(h, self._reg_h)):
            self._reg[name] << v
            if ro:
                f_dwwrite_epd(epd, self._reg[name])
        if EUDElse()():
            f_dwwrite_epd(epd, v)
        EUDEndIf()

    # ------------------------------------------------------------------ 순회
    def each(self, handle=False):
        """살아 있는 레코드마다 한 번씩 레지스터에 싣고 본문을 돈다 (파이썬 `for`, epScript `foreach`).

        규칙(S2 6.5): 루프 시작 때 목록 길이를 고정하고, 그 안에서 방문 전에 반납되지 않은 레코드만 할당 순서대로 정확히
        한 번 방문한다. 루프 중 alloc 한 레코드는 다음 each 부터. 현재 레코드를 free 하면 방문 끝에 되쓰기를 생략하고 빈 칸이
        된다. `EUDContinue()` = 방문 꼬리(되쓰기)로. `EUDBreak()` = 이번 방문을 마치고 남은 레코드는 본문 없이 정리만.
        같은 풀의 each 중첩은 컴파일 오류, 다른 풀은 된다. 호출 자리가 여럿이어도 된다(자리마다 머리·끝 코드 1벌).
        본문 안의 "게임당 한 번" 구조(EUDExecuteOnce, 보존 안 한 트리거)는 **풀 전체에서 한 번**이 된다(원본과 같은 함정).
        **순서 보장**: `alloc`/`alloc_n` 은 레코드를 살아 있는 목록 끝에 차례로 이어 붙이고, 이 루프는 넣은 순서로 돈다
        (압축해도 순서 유지). `spawn` 이 "다음 층 = 바로 뒤 레코드" 로 이 보장에 기댄다(WP12) — 순서를 바꾸면 t_spawn 이 알려 준다.
        인자: handle(True 면 (g, h) 를 준다 — h 는 핸들 레지스터)
        반환: 제너레이터 (한 번 돈다)
        비용: 호출 자리 8~12 트리거(+ 본문) / 실행: 빈 풀 2, 아니면 고정 8 + 방문마다 F+10+W (W=0 이면 F+6)
              (+ 앞에서 레코드가 빠진 뒤 방문마다 이동 3, 빠진 레코드마다 F+b+11, 루프 중 alloc 이 있으면
              2단계 머리 4 + 새 레코드마다 F+6) (2026-09-17, docs/COSTS.md)
        CP: 바꾸지 않음 (본문이 바꾼 CP 는 본문 책임)
        로컬: 공유 안전
        epScript: `foreach (g : guns.each()) { … }` / `foreach (g, h : guns.each(handle=true)) { … }`
        출처: S2 6.5·6.12, eudplib 0.81 EUDQueue 순회
        """
        if self._active:
            fail("풀 %s: 같은 풀의 each 를 중첩할 수 없습니다 (레지스터를 함께 씀)", self.name)
        m = self._mach()
        C = m.C
        BODY, CHECK, FIN, T5, BRK = Forward(), Forward(), Forward(), Forward(), Forward()
        T0, t1, T2, t3, T4, t4b = Forward(), Forward(), Forward(), Forward(), Forward(), Forward()
        # 머리
        T0 << RawTrigger(nextptr=t1, conditions=self._live_end.Exactly(self._L), actions=SetNextPtr(T0, T5))
        t1 << NextTrigger()
        VProc([self._live_end, self._snap], [
            *self._live_end.QueueAssignTo(self._snap),
            *self._snap.QueueAssignTo(EPD(m.c_cond) + 2),
            SetNextPtr(C, self._L),
            SetMemory(m.c_act + 20, SetTo, CHECK),
            SetNextPtr(m.T_alive, BODY),
            SetNextPtr(m.T_tail, m.tail_default),
            SetMemory(m.K_slot, SetTo, C),
            SetNextPtr(m.X2, C),
            self._w_epd.SetNumber(EPD(self._L) + 87),
            self._w_addr.SetNumber(self._L),
            self._removed.SetNumber(0),
            self._appended.SetNumber(0),
        ])
        SetNextTrigger(C)
        # EUDBreak 자리 (흐름 밖)
        PushTriggerScope()
        BRK << RawTrigger(nextptr=m.T_tail, actions=SetNextPtr(m.T_alive, m.X2))
        PopTriggerScope()
        # 본문
        BODY << NextTrigger()
        EUDCreateBlock(_BLOCK, {"contpoint": m.T_tail, "loopend": BRK, "pool": self})
        self._active += 1
        try:
            yield (self._view, self._reg_h) if handle else self._view
        finally:
            self._active -= 1
        EUDPopBlock(_BLOCK)
        SetNextTrigger(m.T_tail)
        # 1단계 끝: 루프 중 alloc 이 있었으면 그 레코드들을 본문 없이 정리
        CHECK << NextTrigger()
        T2 << RawTrigger(nextptr=t3, conditions=self._appended.Exactly(0), actions=SetNextPtr(T2, FIN))
        t3 << NextTrigger()
        # C 가 끝으로 갈 때 자기 next(순회 포인터)를 덮었으므로 1단계 끝 = snap 에서 다시 시작
        VProc([self._snap, self._live_end], [
            *self._snap.QueueAssignTo(EPD(C) + 1),
            *self._live_end.QueueAssignTo(EPD(m.c_cond) + 2),
            SetMemory(m.c_act + 20, SetTo, FIN),
            SetNextPtr(m.T_alive, m.X2),
        ])
        SetNextTrigger(C)
        # 끝: 빠진 레코드가 있었으면 목록 끝 = 쓰기 포인터
        FIN << NextTrigger()
        T4 << RawTrigger(nextptr=t4b, conditions=self._removed.Exactly(0), actions=SetNextPtr(T4, T5))
        t4b << NextTrigger()
        VProc([self._w_addr, self._w_epd],
              [*self._w_addr.QueueAssignTo(self._live_end), *self._w_epd.QueueAssignTo(self._live_end_epd)])
        T5 << RawTrigger(actions=[self._reg_h.SetNumber(0), self._flag.SetNumber(0), SetNextPtr(T0, t1),
                                  SetNextPtr(T2, t3), SetNextPtr(T4, t4b)])
        self._sites.append({"T0": T0, "t1": t1, "BODY": BODY, "CHECK": CHECK, "t3": t3, "FIN": FIN, "t4b": t4b,
                            "T5": T5, "BRK": BRK})  # 시험·진단용 라벨

    # ------------------------------------------------------------------ 유형별 처리
    def case(self, *values):
        """`dispatch` 가 쓸 유형 본문을 등록하는 데코레이터: `@guns.case(131, 132) def f(g): …`.

        같은 값을 두 번 등록하면 컴파일 오류(원본 GCase_Duplicated). 본문 함수는 인자 0개 또는 1개(보기 객체).
        반환: 데코레이터
        비용: 없음(등록)
        epScript: 쓰지 않는다 (epScript 는 `switch (g.unit) { case 131: …; break; }`)
        """
        require(values, "풀 %s.case: 값이 없습니다", self.name)
        vals = []
        for v in values:
            v = unProxy(v)
            require(isinstance(v, int) and not isinstance(v, bool), "풀 %s.case: 정수 상수만 (%r)", self.name, v)
            if v in self._cases:
                fail("풀 %s.case: 값 %d 를 두 번 등록했습니다 (GCase_Duplicated)", self.name, v)
            vals.append(v)

        def deco(fn):
            for v in vals:
                self._cases[v] = fn
            return fn

        return deco

    def dispatch(self, field, cases=None, default="unknown"):
        """필드 값으로 유형별 본문을 고른다: `EUDSwitch(레지스터)` + 등록된 본문 인라인 + 기본 가지.

        인자: field(필드 이름 또는 옛 줄 번호), cases(선택: {값: 함수} — 없으면 `case()` 로 등록한 것),
              default("unknown" = on_unknown(원본: 문구 + Buzz ×2 + free_current), None = 기본 가지 없음, 함수)
        반환: None
        비용: EUDSwitch + 경우 끝 점프 = 실행 약 log2(경우 수) + 4 (26경우 9, 2026-09-17)
        CP: 바꾸지 않음(본문이 바꾸는 대로)
        로컬: 공유 안전
        epScript: `switch (g.gunid) { case 3: bossA(); break; default: guns.free_current(); }` 를 그대로 쓴다
        출처: S2 6.6, 원본 CIf_GCase (MSF_Respect_V GunData.lua:316)
        """
        name = self._resolve(field)
        table = dict(self._cases if cases is None else cases)
        for v in table:
            require(isinstance(v, int) and not isinstance(v, bool), "풀 %s.dispatch: 값은 정수 상수 (%r)", self.name, v)
        EUDSwitch(self._reg[name])
        for v in sorted(table, key=lambda x: x & M32):
            if EUDSwitchCase()(v & M32):
                self._call_case(table[v])
                EUDBreak()
        if default is not None:
            if EUDSwitchDefault()():
                if default == "unknown":
                    self._report(self.on_unknown, "unknown", name)
                    if not callable(self.on_unknown):
                        self.free_current()
                else:
                    self._call_case(default)
                EUDBreak()
        EUDEndSwitch()

    def _call_case(self, fn):
        if _compat.is_eudfunc(fn):
            try:
                n = fn._argn
            except AttributeError:
                n = 0
            fn(self._view) if n else fn()
            return
        try:
            n = len([p for p in inspect.signature(fn).parameters.values()
                     if p.default is inspect.Parameter.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
        except (TypeError, ValueError):
            n = 0
        fn(self._view) if n else fn()

    # ------------------------------------------------------------------ 옛 줄 번호 별칭 (S2 6.9)
    def Line(self, n, t, v, mask=None):  # noqa: N802
        """옛 `Gun_Line(n, T, v[, m])`/`TSLine` → Condition (레지스터 비교, 추가 트리거 0 — 변수 v 면 cmp 몫).

        인자: n(줄 번호 — alias_base 기준 — 또는 필드 이름), t(Exactly/AtLeast/AtMost), v(상수·변수),
              mask(선택: 상수 v 만. 원시 비트 비교라 부호를 보지 않는다)
        반환: Condition 또는 조건 목록 (signed 필드는 부호 있는 비교)
        비용: 상수 0 / 변수 cmp 와 같음(호출 1 / 실행 2)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `if (guns.Line(5, Exactly, 0)) { … }`
        출처: MSF 계열 Gun_Line, TStruct TSLine (S2 6.9)
        """
        name = self._resolve(n)
        kind = _cmp_kind(t)
        if mask is not None:
            mask = _const(mask)
            if not _is_const(v):
                fail("풀 %s.Line: mask 는 상수 값에만 씁니다", self.name)
            return MemoryX(self._reg[name].getValueAddr(), {"eq": Exactly, "ge": AtLeast, "le": AtMost}[kind],
                           _const(v), mask)
        return self._cond(name, kind, v)

    def LineRange(self, n, a, b):  # noqa: N802
        """옛 `Gun_LineRange(n, a, b)` → `[필드 ≥ a, 필드 ≤ b]` (signed 필드는 부호 있는 비교). 비용: 상수 0."""
        name = self._resolve(n)
        out = []
        for c in (self._cond(name, "ge", a), self._cond(name, "le", b)):
            out.extend(c if isinstance(c, list) else [c])
        return out

    def SetLine(self, n, mod, v, mask=None):  # noqa: N802
        """옛 `Gun_SetLine(n, M, v[, m])`/`SetTSLine` — **바로 실행**한다(문장).

        `M=Subtract` 는 원본 SC 액션처럼 **포화**(0 에서 멈춤, DESIGN 3.5 CtrigAsm 이름 규칙). `Add` 는 wrap.
        mask 는 SetTo 에만(마스크 Add/Subtract 식은 인게임 확인 전, DESIGN 3.5-8).
        인자: n(줄 번호 또는 필드 이름), mod(SetTo/Add/Subtract), v(상수·변수), mask(선택)
        반환: None (epScript 는 반환값을 버리므로 액션을 돌려주지 않는다. 액션이 필요하면 SetLineAct)
        비용: 상수 = 호출 1 / 실행 1, 변수 = 호출 1 / 실행 2~3
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `guns.SetLine(7, Add, 1);  guns.SetLine(11, Subtract, 1);`
        """
        name = self._resolve(n)
        self._check_writable(name)
        k = _mod_kind(mod)
        self._touch(name)
        r = self._reg[name]
        if mask is not None:
            if k != 7:
                fail("풀 %s.SetLine: 마스크 Add/Subtract 는 인게임 확인 전이라 막았습니다 (SetTo 만)", self.name)
            _parts.set_masked(r, v, _const(mask))
            return
        if k == 7:
            if _is_const(v):
                RawTrigger(actions=r.SetNumber(_const(v)))
            elif unProxy(v) is not r:
                r << v
        elif k == 8:
            if _is_const(v):
                RawTrigger(actions=r.AddNumber(_const(v)))
            else:
                r += v
        else:
            _parts.isub_sat32(r, _const(v) if _is_const(v) else v)

    def SetLineAct(self, n, mod, v):  # noqa: N802
        """`SetLine` 의 액션판 (RawTrigger/DoActions 액션 목록에 넣을 때). 변수 v 는 DoActions/Trigger 안에서만.

        `Subtract` 는 SC 액션 그대로 포화. 반환: Action. 비용: 액션 1.
        epScript: `DoActions(guns.SetLineAct(7, Add, 1));`
        """
        name = self._resolve(n)
        self._check_writable(name)
        k = _mod_kind(mod)
        self._touch(name)
        modifier = {7: SetTo, 8: Add, 9: Subtract}[k]
        return SetMemory(self._reg[name].getValueAddr(), modifier, _const(v) if _is_const(v) else unProxy(v))

    def line(self, n):
        """옛 `Var_TempTable[n+1]`/`TS_VarArr[n]` → 그 필드의 레지스터 EUDVariable (계산식에 그대로)."""
        name = self._resolve(n)
        self._touch(name)
        return self._reg[name]

    # ------------------------------------------------------------------ 시험·진단용
    def _debug_info(self):
        """시험용: 내부 주소·변수 (주소는 ConstExpr, 상태는 EUDVariable)."""
        return {
            "S": self._S, "L": self._L, "FS": self._FS, "TRASH": self._TRASH,
            "fs_top": self._fs_top, "free_n": self._free_n, "live_end": self._live_end,
            "live_end_epd": self._live_end_epd, "count": self._count, "dropped": self._dropped,
            "reg_h": self._reg_h, "reg_addr": self._reg_addr,
        }

    def __repr__(self):
        return "Pool(%r, %s, capacity=%d)" % (self.name, " ".join(
            f.name + ("!" if f.readonly else "") for f in self._fields), self.capacity)
