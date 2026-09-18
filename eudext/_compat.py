"""eudplib 판 검사와 비공개 API 접근을 한 곳에 모은다 (DESIGN 2.1, 3.9, 4.1).

eudext 의 다른 모듈은 eudplib 의 비공개 이름(밑줄 이름, `eudplib` 최상위에 공개되지 않은 모듈 속성)을
직접 쓰지 않고 이 모듈의 함수를 부른다. eudplib 을 올릴 때 고칠 곳은 여기 한 곳이다.

기준 판: eudplib 0.81.x (euddraft 0.11.0.1 번들 = 0.81.0).

지금 쓰는 비공개 API (WP0 + 배치 B, 필요한 것만):

| 용도 | eudplib 0.81 위치 | 쓰는 곳 |
|---|---|---|
| CP 캐시 변수·검사 조건 | `core.curpl.GetCPCache`, `cpcache_match_cond` | `_parts.cp_fix` |
| 블록 구조 관리자 교체 | `utils.blockstru.BlockStruManager`, `set_blockstru_manager` | `isolated_scope` (서브루틴, 시험 틀) |
| SaveMap 가로채기 | `maprw.savemap.apply_injector`, `maprw.injector.apply_injector.initialize_payload` | `testing.emu` |
| 빌드 상태 되돌리기 | `maprw.injector.mainloop._start_functions2`, `_game_loop_start`, `_set_game_loop_start`, `core.variable.vbuf._register_new_(custom_)varbuffer`, `ctrlstru.jumptable.register_new_jumpbuffer`, `eudlib.utilf.userpl._rcpc_reset_userp` | `reset_build_state`, `set_game_loop_start` |
| epScript 오류 수 | `epscript.epscompile._load_lib` | `eps_compile` |
| chk 문자열 구역 | `core.mapdata.mapdata.GetChkTokenized`, `core.mapdata.stringmap.get_string_section_name` | `tools.cost` |
| EUDFunc 판별 | `core.eudfunc.eudfuncn.EUDFuncN` | `is_eudfunc` (`tools.cost`) |
| 변수 계열 판별 | `core.variable.vbase.VariableBase` | `is_varbase` (`_parts.isub32`) |
| scdata 디스크립터 배치 | `scdata.offsetmap.member.BaseMember/NotImplementedMember/UnsupportedMember`, `enummember.BaseEnum/Flag`, `memberkind.Bit0Kind/Bit1Kind` | `scdata_*` (`datpatch`, WP15) |
| 시작 단계·게임 루프 훅 | `maprw.injector.mainloop._has_already_started`, `eud_onstart2`, `_on_game_loop_start` | `onstart_phase`, `on_start_after_main`, `on_game_loop_start` (`datpatch`, `sync`), `reset_build_state` |
| 되돌리는 패치 | `eudlib.utilf.mempatch.f_dwpatch_epd`, `f_unpatchall` | `dwpatch_epd`, `unpatch_all` (`datpatch`) |
| EUDFunc 반환 변수 미리 정하기 | `EUDFuncN._frets`, `_retn` (`core/eudfunc/eudf.py` `_EUDPredefineReturn` 방식) | `predefine_returns` (`units`, WP10) |
| 새 유닛 순회 그림자 표 | `eudlib.utilf.listloop._UniqueIdentifier._instances`, `mainloop._game_loop_start_functions` | `reset_new_unit_loops` (`units`, `reset_build_state`) |
| EUDArray 칸 EPD | `EUDArray._epd` | `eudarray_epd`, `eudarray_addr`, `eudarray_ptr_view` (`sync`, WP13) |
| MPQ 읽기 | `bindings._rust.mpqapi` | `mpq_read_file` (`bgm` 시험, WP16) |
| 서식 필드 처리 | `string.fmtprint._EUDFormatter.eudformat_field` | `hook_format_field` (`numfmt`, WP5) |
| 비공개 산술 경로 | `core.calcf.muldiv._const_mul/_const_quot/_const_rem`, `core.calcf.bitwise.f_bitrshift` | `eudplib_calc_caller` (`i64`, WP4) |
| 텍스트 효과 | `string.texteffect.f_cpchar_addstr_epd`, `color_v` | `cpchar_addstr_epd`, `cpchar_color_var` (`textfx` 시험, WP17) |
| 이름 라이트 변수 | `string.pname.PLVarUnit/PLVarMask/_get_player_lightvar` | `pname_lightvar_units` (`scrdb`, WP18) |
| epScript 시프트 식 | `epscript.helper._LSH` | `eps_lshift_caller` (`i64`, WP3) |
| 72B 원소 배열 | `core.eudstruct.vararray._EUDVArrayData` | `custom_varray`, `check_pool` (`pool`, WP11) |
| 맵 문자열 새 칸·주소 조회 | `core.mapdata.stringmap.ForceAddString/strmap`, `string.cpstr._const_strptr/_initialize_queries`, `core.allocator.payload._register_after_collecting_callback` | `force_add_string`, `forget_mapstring_addrs`, `string_map_token`, `refresh_mapstring_queries` (`display`, WP6b) |
"""

import contextlib
import importlib
import warnings

import eudplib as ep

SUPPORTED = (0, 81)
M32 = 0xFFFFFFFF

__all__ = [
    "M32",
    "SUPPORTED",
    "capture_payload",
    "check",
    "check_datpatch",
    "check_pool",
    "chk_string_section",
    "chk_string_section_name",
    "cpcache_cond",
    "cpcache_var",
    "cpchar_addstr_epd",
    "cpchar_color_var",
    "custom_varray",
    "dwpatch_epd",
    "eps_compile",
    "eps_lshift_caller",
    "eudarray_addr",
    "eudarray_epd",
    "eudarray_ptr_view",
    "eudplib_calc_caller",
    "eudplib_version",
    "force_add_string",
    "forget_mapstring_addrs",
    "hook_format_field",
    "is_const",
    "is_eudfunc",
    "is_var",
    "is_varbase",
    "isolated_scope",
    "mpq_read_file",
    "on_game_loop_start",
    "on_start_after_main",
    "onstart_phase",
    "pname_lightvar_units",
    "predefine_returns",
    "refresh_mapstring_queries",
    "register_build_reset",
    "reset_build_state",
    "reset_new_unit_loops",
    "scdata_cast",
    "scdata_epd_subp",
    "scdata_flag_masks",
    "scdata_member_info",
    "scdata_members",
    "set_game_loop_start",
    "split64_const",
    "string_map_token",
    "unpatch_all",
]

# (모듈, 속성) — check() 가 있는지 확인한다.
# WP15 datpatch 가 쓰는 이름 (check_datpatch() 도 따로 확인한다)
_WP15_REQUIRED = (
    ("eudplib.scdata.offsetmap.member", "BaseMember"),
    ("eudplib.scdata.offsetmap.member", "NotImplementedMember"),
    ("eudplib.scdata.offsetmap.member", "UnsupportedMember"),
    ("eudplib.scdata.offsetmap.enummember", "BaseEnum"),
    ("eudplib.scdata.offsetmap.enummember", "Flag"),
    ("eudplib.scdata.offsetmap.memberkind", "Bit0Kind"),
    ("eudplib.scdata.offsetmap.memberkind", "Bit1Kind"),
    ("eudplib.maprw.injector.mainloop", "_has_already_started"),
    ("eudplib.maprw.injector.mainloop", "eud_onstart2"),
    ("eudplib.maprw.injector.mainloop", "_on_game_loop_start"),
    ("eudplib.eudlib.utilf.mempatch", "f_dwpatch_epd"),
    ("eudplib.eudlib.utilf.mempatch", "f_unpatchall"),
)

_REQUIRED = (
    ("eudplib.core.curpl", "GetCPCache"),
    ("eudplib.core.curpl", "cpcache_match_cond"),
    ("eudplib.utils.blockstru", "BlockStruManager"),
    ("eudplib.utils.blockstru", "set_blockstru_manager"),
    ("eudplib.maprw.savemap", "apply_injector"),
    ("eudplib.maprw.injector.apply_injector", "initialize_payload"),
    ("eudplib.maprw.injector.mainloop", "_start_functions2"),
    ("eudplib.maprw.injector.mainloop", "_game_loop_start"),
    ("eudplib.maprw.injector.mainloop", "_set_game_loop_start"),
    ("eudplib.core.variable.vbuf", "_register_new_varbuffer"),
    ("eudplib.core.variable.vbuf", "_register_new_custom_varbuffer"),
    ("eudplib.ctrlstru.jumptable", "register_new_jumpbuffer"),
    ("eudplib.eudlib.utilf.userpl", "_rcpc_reset_userp"),
    ("eudplib.epscript.epscompile", "_load_lib"),
    ("eudplib.core.mapdata.mapdata", "GetChkTokenized"),
    ("eudplib.core.mapdata.stringmap", "get_string_section_name"),
    ("eudplib.core.eudfunc.eudfuncn", "EUDFuncN"),
    ("eudplib.core.variable.vbase", "VariableBase"),
    # 배치 B: WP10 units (predefine_returns 는 EUDFuncN 인스턴스 속성이라 여기서 검사하지 않는다)
    ("eudplib.eudlib.utilf.listloop", "_UniqueIdentifier"),
    ("eudplib.maprw.injector.mainloop", "_game_loop_start_functions"),
    # 배치 C: WP3 i64 (eps_lshift_caller), WP11 pool (custom_varray) — 각 블록의 _WP3/_WP11_REQUIRED 와 같다
    ("eudplib.epscript.helper", "_LSH"),
    ("eudplib.core.eudstruct.vararray", "_EUDVArrayData"),
    # 배치 D: WP16 bgm (mpq_read_file) — 블록의 _WP16_REQUIRED 와 같다
    ("eudplib.bindings._rust", "mpqapi"),
    # WP17 textfx (시험 전용 접근자 cpchar_addstr_epd·cpchar_color_var) — 블록의 _WP17_REQUIRED 와 같다
    ("eudplib.string.texteffect", "f_cpchar_addstr_epd"),
    ("eudplib.string.texteffect", "color_v"),
    # WP18 scrdb (IsPName 라이트 변수 칸 검사) — 블록의 _WP18_REQUIRED 와 같다
    ("eudplib.string.pname", "PLVarUnit"),
    ("eudplib.string.pname", "PLVarMask"),
    ("eudplib.string.pname", "_get_player_lightvar"),
    # WP4 i64 2차 (eudplib_calc_caller) — 블록의 _WP4_REQUIRED 와 같다
    ("eudplib.core.calcf.muldiv", "_const_mul"),
    ("eudplib.core.calcf.muldiv", "_const_quot"),
    ("eudplib.core.calcf.muldiv", "_const_rem"),
    ("eudplib.core.calcf.bitwise", "f_bitrshift"),
    # WP5 numfmt (hook_format_field) — 블록의 _WP5_REQUIRED 와 같다
    ("eudplib.string.fmtprint", "_EUDFormatter"),
    # WP6b display (맵 문자열 새 칸·주소 조회) — 블록의 _WP6b_REQUIRED 와 같다
    ("eudplib.core.mapdata.stringmap", "ForceAddString"),
    ("eudplib.core.mapdata.stringmap", "strmap"),
    ("eudplib.string.cpstr", "_const_strptr"),
    ("eudplib.string.cpstr", "_initialize_queries"),
    ("eudplib.core.allocator.payload", "_register_after_collecting_callback"),
) + _WP15_REQUIRED  # WP13 sync 의 EUDArray._epd 는 인스턴스 속성이라 여기서 검사하지 않는다

_checked = None


def _mod(name):
    return importlib.import_module(name)


def eudplib_version():
    """eudplib 판을 정수 튜플로 돌려준다 (예: (0, 81, 0)).

    인자: 없음
    반환: tuple[int, ...]
    비용: 없음(컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    out = []
    for part in ep.eudplibVersion().split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


def check(strict=False):
    """eudplib 판과 비공개 API 존재를 검사한다. 부트 플러그인과 시험이 부른다.

    판이 0.81.x 가 아니면 경고(strict=True 면 오류), 필요한 비공개 속성이 없으면 오류.
    인자: strict(bool) — 판이 다르면 오류로
    반환: eudplib 판 문자열
    비용: 없음(컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성 (R2 5.6-3)
    """
    global _checked
    from eudext.errors import EudextError

    ver = ep.eudplibVersion()
    if eudplib_version()[:2] != SUPPORTED:
        msg = "[eudext] eudplib %s 은(는) 기준 판(0.%d.x)이 아닙니다. 비공개 API 가 달라졌을 수 있습니다." % (
            ver,
            SUPPORTED[1],
        )
        if strict:
            raise EudextError(msg)
        warnings.warn(msg, ep.EPWarning, stacklevel=2)
    if _checked == ver:
        return ver
    missing = []
    for modname, attr in _REQUIRED:
        try:
            mod = _mod(modname)
        except ImportError:
            missing.append(modname)
            continue
        if not hasattr(mod, attr):
            missing.append("%s.%s" % (modname, attr))
    if missing:
        raise EudextError("eudplib %s 에 eudext 가 쓰는 내부 이름이 없습니다: %s" % (ver, ", ".join(missing)))
    _checked = ver
    return ver


# ---------------------------------------------------------------------------------------------
# 판별 도우미
# ---------------------------------------------------------------------------------------------


def is_const(x):
    """컴파일 시점 상수(int 또는 ConstExpr — 주소식 포함)인가.

    인자: x
    반환: bool (EUDVariable 이면 False)
    비용: 없음
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib `IsConstExpr` 감싸기
    """
    if isinstance(x, bool):
        return True
    return bool(ep.IsConstExpr(x))


def is_var(x):
    """EUDVariable(ExprProxy 로 감싼 것 포함)인가.

    인자: x
    반환: bool
    비용: 없음
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib `IsEUDVariable` 감싸기
    """
    return bool(ep.IsEUDVariable(x))


def is_varbase(x):
    """eudplib 변수 계열(VariableBase: EUDVariable, EUDLightVariable, EUDXVariable …)인가.

    인자: x
    반환: bool
    비용: 없음
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `core/variable/vbase.py` (공개 목록에 없음)
    """
    return isinstance(x, _mod("eudplib.core.variable.vbase").VariableBase)


def split64_const(x):
    """64비트 정수 상수를 (하위 32비트, 상위 32비트) 로 나눈다. 음수는 2의 보수로.

    인자: x(int)
    반환: (lo, hi)
    비용: 없음
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    from eudext.errors import fail

    if isinstance(x, bool) or not isinstance(x, int):
        fail("split64_const: 정수 상수가 아닙니다 (%r)", x)
    if not -(1 << 63) <= x < (1 << 64):
        fail("split64_const: 64비트 범위 밖 %d", x)
    x &= (1 << 64) - 1
    return x & M32, x >> 32


def is_eudfunc(obj):
    """eudplib EUDFunc 로 만든 함수 객체(EUDFuncN)인가.

    인자: obj
    반환: bool
    비용: 없음
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    return isinstance(obj, _mod("eudplib.core.eudfunc.eudfuncn").EUDFuncN)


# ---------------------------------------------------------------------------------------------
# CP 캐시 (eudplib core/curpl.py)
# ---------------------------------------------------------------------------------------------


def cpcache_var():
    """eudplib 이 기억하는 CP 값 변수(EUDXVariable)를 돌려준다.

    인자: 없음
    반환: EUDXVariable (값 칸 = 캐시된 CP)
    비용: 없음
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `core/curpl.py` GetCPCache
    """
    return _mod("eudplib.core.curpl").GetCPCache()


def cpcache_cond():
    """CP 캐시 검사 조건(`Memory(0x6509B0, Exactly, 캐시)`)을 가리키는 Forward 를 돌려준다.

    조건의 amount 칸 주소는 `cpcache_cond() + 8` 이다.
    인자: 없음
    반환: Forward (Condition 으로 설정됨)
    비용: 없음
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `core/curpl.py` cpcache_match_cond
    """
    return _mod("eudplib.core.curpl").cpcache_match_cond()


# ---------------------------------------------------------------------------------------------
# 블록·트리거 범위
# ---------------------------------------------------------------------------------------------


@contextlib.contextmanager
def isolated_scope():
    """새 블록 구조 관리자 + 새 트리거 범위를 연다 (EUDFunc 본문과 같은 격리).

    안에서 만든 트리거는 바깥 흐름에 이어지지 않는다(따로 떨어진 코드).
    안에서 예외가 나면 블록 관리자만 되돌리고 예외를 그대로 올린다(만든 트리거는 버려진다).
    인자: 없음
    반환: 컨텍스트 관리자
    비용: 없음(구조만)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `core/eudfunc/eudfuncn.py:_create_func_body` 의 앞뒤 처리
    """
    from eudext.errors import EudextError

    bs = _mod("eudplib.utils.blockstru")
    bsm = bs.BlockStruManager()
    prev = bs.set_blockstru_manager(bsm)
    try:
        ep.PushTriggerScope()
        yield
        ep.PopTriggerScope()
        if not bsm.empty():
            names = ", ".join(name for name, _data in bsm._blockstru)
            raise EudextError("격리 범위 안에서 블록이 닫히지 않았습니다: %s" % names)
    finally:
        bs.set_blockstru_manager(prev)


# ---------------------------------------------------------------------------------------------
# 빌드 상태
# ---------------------------------------------------------------------------------------------


_build_reset_hooks = []


def register_build_reset(fn):
    """`reset_build_state()` 가 부를 함수를 등록한다(eudext 모듈의 빌드별 상태 초기화용).

    eudplib 0.81.0 의 `RegisterCreatePayloadCallback` 콜백은 프로세스에서 **첫 CreatePayload 때 한 번만**
    불린다(등록 목록이 비워짐, WP0 실측). 그래서 빌드마다 되돌릴 eudext 상태는 이 목록에 등록한다.
    인자: fn(인자 없는 함수)
    반환: fn (데코레이터로 써도 된다)
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: WP0 재측정 (d)
    """
    if fn not in _build_reset_hooks:
        _build_reset_hooks.append(fn)
    return fn


def reset_build_state():
    """한 프로세스에서 SaveMap 을 여러 번 할 때 앞 빌드가 남긴 eudplib 상태를 지운다. SaveMap 앞에서 부른다.

    WP0 실측(eudplib 0.81.0):
    1. `RegisterCreatePayloadCallback` 콜백이 첫 빌드에서만 불린다 → 변수 버퍼(EUDVarBuffer,
       EUDCustomVarBuffer), 점프 버퍼, IsUserCP 등록표가 다음 빌드로 이어져 앞 빌드의 변수가 모두 다시 실린다
       (빈 빌드마다 페이로드 +2.4KB, 값은 정상). 그 콜백들을 여기서 다시 부른다.
    2. 주 함수 안에서 부른 `EUDOnStart` 는 `_start_functions2` 에 쌓여 k 번째 빌드에서 k 번 실행된다 → 비운다.
    3. `_game_loop_start` Forward 가 설정된 채 남아 다음 `_set_game_loop_start()` 가 오류 → 되돌린다.
    4. 빌드가 예외로 끊기면 `_has_already_started` 가 1·2 로 남아 다음 빌드의 `EUDOnStart` 가 실패한다 → 0 으로 되돌린다(WP15 발견).
    5. `EUDLoopNewUnit` 그림자 표 목록(순회마다 571KB)이 다음 빌드에 계속 실린다 → `reset_new_unit_loops()`(WP10 발견).
    6. `register_build_reset` 으로 등록한 eudext 훅을 부른다.
    (`GetMapStringAddr(상수 번호)` 주소 콜백도 첫 빌드에서만 불리지만 여기서는 다시 걸지 않는다 — 늘 걸면 numfmt 의 DESIGN 0.3 예
    시험이 빈 출력을 낸다(2026-09-17 실측). `display` 가 `register_build_reset(refresh_mapstring_queries)` 로 자기 프로세스에서만 건다. D97)
    되돌리지 않는 것: 모듈 전역 `EUDOnStart`(`_start_functions1`, 빌드마다 실행이 맞다),
    이미 만든 EUDFunc 본문(재사용, 결과 정상 — 단 본문에 구운 문자열 번호는 첫 빌드 기준이라 틀어진다),
    LoadMap 으로 읽은 chk(SaveMap 이 STR·TRIG·MRGN 을 고치므로 빌드마다 LoadMap 을 다시 해야 한다),
    EUDTracedFunc 추적표(.epmap, 첫 빌드 뒤에는 기록되지 않을 수 있음).
    인자: 없음
    반환: None
    비용: 없음(컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: WP0 재측정 (d), 배치 B(WP10·WP15) 보강
    """
    vb = _mod("eudplib.core.variable.vbuf")
    vb._register_new_varbuffer()
    vb._register_new_custom_varbuffer()
    _mod("eudplib.ctrlstru.jumptable").register_new_jumpbuffer()
    _mod("eudplib.eudlib.utilf.userpl")._rcpc_reset_userp()
    ml = _mod("eudplib.maprw.injector.mainloop")
    ml._start_functions2.clear()
    if ml._game_loop_start.IsSet():
        ml._game_loop_start.Reset()
    ml._has_already_started = 0
    reset_new_unit_loops()
    for fn in list(_build_reset_hooks):
        fn()


def set_game_loop_start():
    """euddraft payloadMain 처럼 "게임 루프 시작점" 을 지금 위치로 정한다.

    euddraft 는 모든 플러그인의 beforeTriggerExec 앞에서 이것을 부른다(`pluginLoader.py`).
    `EUDLoopNewUnit` 등이 이 지점에 초기화 코드를 붙이므로 단독 빌드·에뮬레이터도 같은 자리에서 부른다.
    인자: 없음
    반환: None
    비용: 트리거 0 (시작점 등록만. 등록된 초기화 코드가 있으면 그만큼)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `maprw/injector/mainloop.py:_set_game_loop_start`
    """
    _mod("eudplib.maprw.injector.mainloop")._set_game_loop_start()


# ---------------------------------------------------------------------------------------------
# SaveMap 가로채기 (testing.emu)
# ---------------------------------------------------------------------------------------------


@contextlib.contextmanager
def capture_payload():
    """SaveMap 동안 재배치 전 페이로드와 루트 트리거를 잡는다. STR·TRIG·MRGN 은 고치지 않는다.

    `with capture_payload() as cap: SaveMap(...)` 뒤 `cap["payload"]`(Payload: data, prttable, orttable),
    `cap["root"]`(main_starter 의 jumper). `cap["on_root"]` 에 함수를 넣으면 루트를 받을 때 부른다.
    인자: 없음
    반환: dict
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: DPS_eud `eud/tests/emu.py:82-110` 의 가로채기를 옮김 (0.81 에서도 두 이름이 같은 자리에 있다)
    """
    sm = _mod("eudplib.maprw.savemap")
    ai = _mod("eudplib.maprw.injector.apply_injector")
    cap = {"payload": None, "root": None, "on_root": None}
    orig_apply, orig_init = sm.apply_injector, ai.initialize_payload

    def fake_init(chkt, payload, mrgndata=None):
        cap["payload"] = payload

    def patched_apply(chkt, root):
        cap["root"] = root
        if cap["on_root"] is not None:
            cap["on_root"](root)
        return orig_apply(chkt, root)

    sm.apply_injector = patched_apply
    ai.initialize_payload = fake_init
    try:
        yield cap
    finally:
        sm.apply_injector, ai.initialize_payload = orig_apply, orig_init


def chk_string_section():
    """지금 불러온 맵 chk 의 문자열 구역(STR 또는 STRx) 바이트를 돌려준다.

    인자: 없음
    반환: bytes
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `core/mapdata`
    """
    chkt = _mod("eudplib.core.mapdata.mapdata").GetChkTokenized()
    name = _mod("eudplib.core.mapdata.stringmap").get_string_section_name()
    return bytes(chkt.getsection(name))


# ---------------------------------------------------------------------------------------------
# epScript
# ---------------------------------------------------------------------------------------------


def eps_compile(filename, code):
    """epScript 소스를 파이썬 소스로 번역한다 (euddraft 0.11.0.1 과 같은 libepScriptLib).

    인자: filename(메시지용 이름), code(str 또는 bytes)
    반환: (번역문 str 또는 None, 오류 수 int)
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `epscript/epscompile.py:epsCompile`
    """
    if isinstance(code, str):
        code = code.encode("utf-8")
    out = ep.epsCompile(filename, code)
    nerr = _mod("eudplib.epscript.epscompile")._load_lib().getErrorCount()
    if out is None:
        return None, nerr
    return out.decode("utf-8"), nerr


# --- WP15 (datpatch) ---
# scdata 디스크립터의 주소 정보, 시작·게임 루프 훅, 되돌리는 패치(f_dwpatch_epd/f_unpatchall) 접근자.
# 판 검사 이름 `_WP15_REQUIRED` 는 파일 머리에 있고 `_REQUIRED` 에 합쳐져 있다(`check()` 도 확인한다).


_wp15_checked = False


def check_datpatch():
    """datpatch 가 쓰는 eudplib 내부 이름이 있는지 확인한다(없으면 EudextError). 한 번만 검사한다.

    인자: 없음
    반환: None
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: WP15 (`check()` 와 같은 방식)
    """
    global _wp15_checked
    if _wp15_checked:
        return
    from eudext.errors import EudextError

    missing = []
    for modname, attr in _WP15_REQUIRED:
        try:
            mod = _mod(modname)
        except ImportError:
            missing.append(modname)
            continue
        if not hasattr(mod, attr):
            missing.append("%s.%s" % (modname, attr))
    if missing:
        raise EudextError("eudplib %s 에 datpatch 가 쓰는 내부 이름이 없습니다: %s" % (ep.eudplibVersion(), ", ".join(missing)))
    _wp15_checked = True


def scdata_members(cls):
    """scdata 클래스(TrgUnit, Weapon …)의 멤버 디스크립터를 정의 순서대로 돌려준다(상속 포함, 별칭 포함).

    인자: cls(EPDOffsetMap 하위 클래스)
    반환: [(이름, 디스크립터)] — 구현 안 된 멤버(NotImplementedMember)도 포함
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `scdata/offsetmap/member.py` BaseMember
    """
    base = _mod("eudplib.scdata.offsetmap.member").BaseMember
    seen = {}
    for klass in reversed(cls.__mro__):
        for name, desc in vars(klass).items():
            if isinstance(desc, base):
                seen[name] = desc
    return list(seen.items())


def scdata_member_info(desc):
    """scdata 멤버 디스크립터의 배치 정보를 dict 로 돌려준다.

    인자: desc(BaseMember)
    반환: {"layout", "offset", "stride", "size", "kind"(종류 클래스 이름), "bit"(비트 멤버면 비트 마스크, 아니면 None),
          "implemented"(False = NotImplementedMember/UnsupportedMember), "enum"(비트 이름 표가 있는 멤버인가)}
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `scdata/offsetmap/member.py:106~122`, `memberkind.py`
    """
    mm = _mod("eudplib.scdata.offsetmap.member")
    mk = _mod("eudplib.scdata.offsetmap.memberkind")
    em = _mod("eudplib.scdata.offsetmap.enummember")
    kind = desc.kind
    bit = None
    if issubclass(kind, mk.Bit1Kind):
        bit = 0x02
    elif issubclass(kind, mk.Bit0Kind):
        bit = 0x01
    return {
        "layout": desc.layout,
        "offset": desc.offset,
        "stride": desc.stride,
        "size": kind.size(),
        "kind": kind.__name__,
        "bit": bit,
        "implemented": not isinstance(desc, (mm.NotImplementedMember, mm.UnsupportedMember)),
        "enum": isinstance(desc, em.BaseEnum),
    }


def scdata_flag_masks(desc):
    """비트 이름 표가 있는 scdata 멤버(baseProperty 등)의 {비트 이름: 마스크} 를 돌려준다. 없으면 빈 dict.

    인자: desc(BaseMember)
    반환: dict
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `scdata/offsetmap/enummember.py` BaseEnum._enum, Flag.mask
    """
    em = _mod("eudplib.scdata.offsetmap.enummember")
    if not isinstance(desc, em.BaseEnum):
        return {}
    out = {}
    for klass in reversed(desc._enum.__mro__):
        for name, flag in vars(klass).items():
            if isinstance(flag, em.Flag):
                out[name] = flag.mask
    return out


def scdata_cast(desc, value):
    """scdata 멤버의 값 변환(이름 문자열 → 번호 등)을 거친 값을 돌려준다(ExprProxy 는 벗긴다).

    인자: desc(BaseMember), value
    반환: int 또는 eudplib 식
    비용: 없음(컴파일 시점, 문자열이면 맵 문자열 표를 쓸 수 있음)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `scdata/offsetmap/memberkind.py` *Kind.cast
    """
    return ep.unProxy(desc.kind.cast(value))


def scdata_epd_subp(desc, instance):
    """scdata 배열 멤버의 (epd, subp) 를 구한다. 번호가 변수면 scdata 의 곱셈·나눗셈 캐시 트리거가 생긴다.

    인자: desc(BaseMember), instance(scdata 객체, 예: `TrgUnit.cast(v)`)
    반환: (epd, subp) — 각각 int 또는 EUDVariable
    비용: 번호 상수 = 0, 변수 = scdata 몫(간격 4 이면 덧셈 1, 아니면 캐시 갱신 트리거)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `scdata/offsetmap/member.py:143` BaseMember._get_epd
    """
    return desc._get_epd(instance)


def onstart_phase():
    """eudplib 시작 코드 단계: 0 = 빌드 밖(모듈 import 등), 1 = 주 함수 생성 중, 2 = 주 함수 뒤 시작 함수 생성 중.

    인자: 없음
    반환: int
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `maprw/injector/mainloop.py` _has_already_started
    """
    return _mod("eudplib.maprw.injector.mainloop")._has_already_started


def on_start_after_main(fn):
    """`fn` 을 "주 함수 코드를 다 만든 뒤" 생성되는 시작 코드 목록에 넣는다(실행은 주 함수보다 먼저, 1회).

    `EUDOnStart` 를 빌드 밖에서 부르면 주 함수보다 먼저 생성돼 그 뒤의 선언을 못 본다. 이 목록은 빌드마다
    `reset_build_state()` 가 비운다.
    인자: fn(인자 없는 함수)
    반환: None
    비용: fn 이 내는 만큼
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `maprw/injector/mainloop.py` eud_onstart2
    """
    _mod("eudplib.maprw.injector.mainloop").eud_onstart2(fn)


def on_game_loop_start(fn):
    """`fn` 을 게임 루프 시작점(매 프레임, beforeTriggerExec 앞)에 코드를 내는 함수로 등록한다.

    주 함수를 다 만든 뒤 불린다. 등록은 프로세스 안에서 계속 남는다(빌드마다 다시 불림).
    등록된 것이 있으면 빌드가 `set_game_loop_start()` 를 써야 한다(euddraft·단독 빌드·에뮬레이터는 씀).
    인자: fn(인자 없는 함수)
    반환: None
    비용: fn 이 내는 만큼(매 프레임 실행)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `maprw/injector/mainloop.py` _on_game_loop_start
    """
    _mod("eudplib.maprw.injector.mainloop")._on_game_loop_start(fn)


def dwpatch_epd(epd, value):
    """되돌릴 수 있는 dword 쓰기: 지금 값을 스택에 넣고 `value` 를 쓴다(`unpatch_all` 이 되돌림).

    인자: epd(상수·변수), value(상수·변수)
    반환: None
    비용: eudplib `f_dwpatch_epd` (EUDFunc, 스택 8192칸을 eudplib 과 공유)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `eudlib/utilf/mempatch.py:43` f_dwpatch_epd (최상위 export 없음)
    """
    _mod("eudplib.eudlib.utilf.mempatch").f_dwpatch_epd(epd, value)


def unpatch_all():
    """`dwpatch_epd`·`f_blockpatch_epd` 로 바꾼 칸을 모두 되돌린다(LIFO).

    인자: 없음
    반환: None
    비용: eudplib `f_unpatchall` (EUDFunc, 패치 수에 비례해 실행)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `eudlib/utilf/mempatch.py:113` f_unpatchall (최상위 export 없음)
    """
    _mod("eudplib.eudlib.utilf.mempatch").f_unpatchall()


# --- WP10 (units) ---


def predefine_returns(func, rets):
    """EUDFunc 의 반환 변수를 본문을 만들기 전에 정해 둔다(본문이 반환 변수에 바로 쓴다 → 반환 복사 트리거가 없다).

    eudplib memio 의 읽기 함수가 쓰는 `_EUDPredefineReturn` 과 같다. 본문 규칙(eudplib 주석):
    반환 변수는 호출마다 반드시 초기화하고, 대상(dest)·modifier 를 바꾸지 않으며, 본문에서 `return` 하지 않고,
    본문 안에서 다른 EUDFunc 를 부르지 않는다.
    인자: func(EUDFunc 로 만든 EUDFuncN, 아직 본문을 만들지 않은 것), rets(EUDVariable 목록)
    반환: func
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `core/eudfunc/eudf.py:155` _EUDPredefineReturn (`_frets`, `_retn` 칸)
    """
    rets = list(rets)
    if not rets or not all(ep.IsEUDVariable(r) for r in rets):
        from eudext.errors import EudextError

        raise EudextError("predefine_returns: 반환 변수는 EUDVariable 목록이어야 합니다 (%r)" % (rets,))
    if getattr(func, "_fstart", None) is not None:
        from eudext.errors import EudextError

        raise EudextError("predefine_returns: 본문을 이미 만든 함수입니다 (%r)" % (func,))
    func._frets = rets
    func._retn = len(rets)
    return func


def reset_new_unit_loops():
    """eudplib `EUDLoopNewUnit` 의 그림자 표 목록을 비운다(한 프로세스에서 여러 번 빌드할 때, `units` 가 등록).

    eudplib 0.81 은 `_UniqueIdentifier._instances`(순회마다 571KB 그림자 표)를 빌드 사이에 비우지 않아, 앞 빌드의
    표가 다음 빌드의 게임 루프 시작 코드에 계속 실린다(값은 맞고 크기만 는다). 목록을 비우고 그 초기화 함수 등록도
    지워, 다음 `EUDLoopNewUnit` 이 처음처럼 다시 등록하게 한다. 앞 빌드에서 만든 EUDFunc 본문 안의 순회는 새 빌드의
    초기화 대상에서 빠진다(게임 시작 때 빈 칸 고유 바이트 복사만 빠짐 — 시험 프로세스에서만 생기는 일).
    인자: 없음
    반환: None
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `eudlib/utilf/listloop.py:68` _UniqueIdentifier, `maprw/injector/mainloop.py:58` _on_game_loop_start
    """
    ui = _mod("eudplib.eudlib.utilf.listloop")._UniqueIdentifier
    if not ui._instances:
        return
    del ui._instances[:]
    ml = _mod("eudplib.maprw.injector.mainloop")
    funcs = ml._game_loop_start_functions
    funcs[:] = [f for f in funcs if getattr(f, "__qualname__", "") != "_UniqueIdentifier.__init__.<locals>.<lambda>"]


# --- WP13 (local/sync) ---


def eudarray_epd(arr):
    """상수 `EUDArray` 의 EPD 식(칸 0). `[main] ptrEUDArray` 설정(EPD 값/포인터 값)과 상관없이 같다.

    인자: arr(EUDArray(n) 또는 EUDArray([상수…]) — 변수에서 만든 배열이 아닌 것)
    반환: ConstExpr (EPD)
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `collections/eudarray.py:87~117` (`_epd` 칸)
    """
    return arr._epd


def eudarray_addr(arr):
    """상수 `EUDArray` 칸 0 의 주소 식(`0x58A364 + 4 × EPD`)."""
    return 0x58A364 + 4 * arr._epd


def eudarray_ptr_view(arr):
    """같은 칸을 가리키되 **값이 포인터인** `EUDArray` 사본을 만든다(플러그인 네임스페이스 등록용).

    MSQC(0.11 번들)는 `array if array._is_epd() else EPD(array)`, NSQC(0.9.10.11 판)는 `EPD(array)` 로 칸을
    구한다. 포인터 값이면 둘 다 경고 없이 맞는 EPD 를 얻는다. 사본 자신의 읽기·쓰기 메서드는 쓰지 않는다.
    인자: arr(상수 EUDArray)
    반환: EUDArray
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `collections/eudarray.py:87` EUDArray(_from=…)
    """
    return ep.EUDArray(_from=0x58A364 + 4 * arr._epd)


# --- WP3 (i64) ---
# epScript 식 `a << b` 는 `eudplib.epscript.helper._LSH(a, b)` 로 번역되고, 값이 변수가 아니면 `a << b` 를 부른다.
# `Int64.__lshift__` 는 대입이라, 이 경로로 불렸는지 보고 막는다(DESIGN 3.2-5).

_WP3_REQUIRED = (("eudplib.epscript.helper", "_LSH"),)


def eps_lshift_caller(depth=2):
    """지금 함수(depth=1 이 부른 쪽의 호출자)를 epScript 식 `a << b` 의 번역 `_LSH` 가 불렀는가.

    인자: depth(int) — `sys._getframe(depth)` 를 본다. `Int64.__lshift__` 안에서 부르면 기본값 2 가 `__lshift__` 의 호출자
    반환: bool
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `epscript/helper.py:522` `_LSH`
    """
    import sys

    try:
        f = sys._getframe(depth)
    except ValueError:
        return False
    return f.f_code.co_name == "_LSH" and f.f_globals.get("__name__") == "eudplib.epscript.helper"


# --- WP11 (pool) ---
# 사슬 저장: 원소마다 목적지(dest)·값·next 를 미리 정한 72B 변수 원소 배열 (eudplib 0.81 EUDQueue 기법, S2 6.12·6.14).

_WP11_REQUIRED = (("eudplib.core.eudstruct.vararray", "_EUDVArrayData"),)

_wp11_checked = False


def check_pool():
    """pool 이 쓰는 eudplib 내부 이름과 모양을 확인한다(없거나 모양이 다르면 EudextError). 한 번만 검사한다.

    `_EUDVArrayData(triples)` 가 (dest, value, nextptr) 세 쌍 목록을 받아 원소마다
    (0xFFFFFFFF, dest, value, 0x072D0000, nextptr) 다섯 칸을 만드는지 본다(S2 6.14).
    인자: 없음
    반환: None
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: WP11, eudplib 0.81 `core/eudstruct/vararray.py:37` _EUDVArrayData
    """
    global _wp11_checked
    if _wp11_checked:
        return
    from eudext.errors import EudextError

    try:
        cls = _mod("eudplib.core.eudstruct.vararray")._EUDVArrayData
        probe = cls([(5, 7, 9)])
        init = probe._init
        ok = len(init) == 1 and tuple(init[0]) == (0xFFFFFFFF, 5, 7, 0x072D0000, 9)
    except Exception as e:  # noqa: BLE001 — 판이 달라 모양이 바뀐 경우
        raise EudextError("eudplib %s 의 _EUDVArrayData 를 pool 이 쓸 수 없습니다: %s" % (ep.eudplibVersion(), e)) from e
    if not ok:
        raise EudextError("eudplib %s 의 _EUDVArrayData 원소 모양이 다릅니다: %r" % (ep.eudplibVersion(), init))
    _wp11_checked = True


def custom_varray(triples):
    """원소마다 (dest, value, next) 를 정한 72B 변수 원소 배열을 만든다. 반환값은 원소 0 의 주소(ConstExpr).

    원소 k 의 주소 = 반환값 + 72·k. 원소로 점프하면 `SetMemoryEPD(dest, SetTo, value)` 한 번을 실행하고 next 로 간다.
    값 칸 EPD = EPD(원소) + 87, dest 칸 EPD = EPD(원소) + 86, next 칸 EPD = EPD(원소) + 1 (vararray.py:602-615).
    원소가 자기 자신·다른 원소를 가리켜야 하면 `Forward` 를 만든 뒤 `fw << custom_varray(...)` 한다(Evaluate 는 빌드 때).
    일반 `EUDVArray` 읽기(목적지를 덮어씀)로 이 배열을 읽지 않는다(S2 8-18).
    인자: triples(list[(dest EPD 또는 변수, value, nextptr)] — value·nextptr 는 int/ConstExpr)
    반환: ConstExpr (EUDCustomVarBuffer 안의 주소, 빌드마다 다시 배치)
    비용: 원소당 72B (EUDCustomVarBuffer), 트리거 0
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `core/eudstruct/vararray.py:37` _EUDVArrayData, `collections/eudqueue.py:25` (_InternalVArray 사용법)
    """
    check_pool()
    cls = _mod("eudplib.core.eudstruct.vararray")._EUDVArrayData
    return cls(list(triples))


def chk_string_section_name():
    """지금 불러온 맵 chk 의 문자열 구역 이름("STR" 또는 "STRx"). `testing.scmodel` 의 글 기록 모델이 쓴다.

    인자: 없음
    반환: str
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `core/mapdata/stringmap.py` get_string_section_name (이미 `_REQUIRED` 에 있음)
    """
    return _mod("eudplib.core.mapdata.stringmap").get_string_section_name()


# --- WP18 (scrdb) ---
# eudplib `IsPName`(이름이 변수이거나 플레이어가 CurrentPlayer 인 경로)은 `_get_player_lightvar()` 로 데스 유닛 436 부터
# 플레이어 칸(0x58F524 + 4·p …)을 1비트씩 나눠 쓴다. SCR_DB MSQC 채널 7(0x58F524)과 겹친다(DESIGN 3.9, R2 3.1 (d)).
# 0.81 의 `f_check_id`·`SetPName` 은 이 칸을 쓰지 않는다(string/pname.py 확인).

_WP18_REQUIRED = (
    ("eudplib.string.pname", "PLVarUnit"),
    ("eudplib.string.pname", "PLVarMask"),
    ("eudplib.string.pname", "_get_player_lightvar"),
)

# eudplib 0.81 string/pname.py:32 `PLVarUnit = ceil((0x58F500 - 0x58A364) / 48)` 과 같은 식 (처음 값)
_PNAME_FIRST_UNIT = -(-(0x58F500 - 0x58A364) // 48)


def pname_lightvar_units():
    """eudplib `IsPName` 이 지금까지 가져간 라이트 변수 데스 유닛 번호 목록(가져간 것이 없으면 빈 목록).

    유닛 u 의 플레이어 p 칸(주소 `0x58A364 + 4·(12·u + p)`, p = 0~7)을 비트 단위로 쓴다.
    인자: 없음
    반환: list[int]
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `string/pname.py:32~43` PLVarUnit·PLVarMask·_get_player_lightvar
    """
    pn = _mod("eudplib.string.pname")
    unit, mask = pn.PLVarUnit, pn.PLVarMask
    last = unit if mask > 0 else unit - 1
    return list(range(_PNAME_FIRST_UNIT, last + 1))


# --- WP17 (textfx/chat) ---
# eudplib 의 런타임 셀 쓰기 `_cpchar_addstr`(string/texteffect.py:28)는 공개 목록에 없다. textfx 는 쓰지 않고
# 시험(`tests/t_textfx.py`)이 rule="eudplib" 스캐너와 결과를 견줄 때만 부른다.

_WP17_REQUIRED = (
    ("eudplib.string.texteffect", "f_cpchar_addstr_epd"),
    ("eudplib.string.texteffect", "color_v"),
)


def cpchar_addstr_epd(src_epd):
    """eudplib `f_cpchar_addstr_epd(src)` 를 부른다: EPD src 의 UTF-8 원문을 CP 칸부터 셀로 쓴다(NUL 셀 없음, CP 는 끝 칸 다음).

    인자: src_epd(EPD 상수·변수 — 원문 첫 바이트가 dword 맨 앞이어야 한다)
    반환: None
    비용: eudplib 본문(공유)
    CP: **바꿈** — 쓴 셀 수만큼 앞으로 (eudplib 그대로. 호출자가 `f_setcurpl`/`f_setcurpl2cpcache` 로 맞춘다)
    로컬: 해당 없음
    epScript: 쓰지 않는다 (시험용)
    출처: eudplib 0.81 `string/texteffect.py:54` f_cpchar_addstr_epd
    """
    _mod("eudplib.string.texteffect").f_cpchar_addstr_epd(src_epd)


def cpchar_color_var():
    """eudplib 런타임 셀의 색 칸 변수 `color_v`(기본 2)를 돌려준다(시험에서 0x0D 로 맞출 때).

    인자: 없음
    반환: EUDVariable
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다 (시험용)
    출처: eudplib 0.81 `string/texteffect.py:24` color_v
    """
    return _mod("eudplib.string.texteffect").color_v


# --- WP4 (i64 2차) ---
# 32비트 변수가 왼쪽인 `v * x`·`v // x`·`v % x`·`v >> x`(x = Int64)는 eudplib 연산자(`core/calcf/_eudvsupport.py`)가 먼저 불려
# `muldiv._const_mul`/`_const_quot`/`_const_rem`·`bitwise.f_bitrshift` 가 Int64 를 상수처럼 다룬다(`number &= 0xFFFFFFFF`
# 가 Int64 를 제자리에서 바꾼다). Int64 는 그 경로로 불렸는지 보고 안내 오류를 낸다.

_WP4_REQUIRED = (
    ("eudplib.core.calcf.muldiv", "_const_mul"),
    ("eudplib.core.calcf.muldiv", "_const_quot"),
    ("eudplib.core.calcf.muldiv", "_const_rem"),
    ("eudplib.core.calcf.bitwise", "f_bitrshift"),
)


def eudplib_calc_caller(depth=2):
    """지금 함수(depth=1 이 부른 쪽의 호출자)를 eudplib 의 32비트 곱셈·나눗셈·시프트 도우미가 불렀는가.

    인자: depth(int) — `sys._getframe(depth)` 를 본다. `Int64.__iand__` 안에서 부르면 기본값 2 가 그 호출자
    반환: bool
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `core/calcf/muldiv.py:174` `_const_mul`·`:302` `_const_quot`·`:360` `_const_rem`,
          `core/calcf/bitwise.py:200` `f_bitrshift`
    """
    import sys

    try:
        f = sys._getframe(depth)
    except ValueError:
        return False
    return f.f_globals.get("__name__") in ("eudplib.core.calcf.muldiv", "eudplib.core.calcf.bitwise")


# --- WP5 (numfmt) ---
# 선택 기능 `numfmt.enable_format_spec()`: eudplib 서식 문자열의 필드 처리(`_EUDFormatter.eudformat_field`)를 감싸
# `{:05d}` 같은 지정자를 numfmt 서식 객체로 바꾼다(R4a C.3-1). 클래스 속성이라 `_format_args`·StringBuffer 모두 적용된다.

_WP5_REQUIRED = (("eudplib.string.fmtprint", "_EUDFormatter"),)


def hook_format_field(hook):
    """eudplib `_EUDFormatter.eudformat_field` 를 감싼다. hook(value, spec) 이 None 이 아니면 그 값을 필드 결과로 쓴다.

    인자: hook(fn(value, format_spec) -> object | None)
    반환: 되돌리는 함수 (부르면 원래 메서드로 돌아간다)
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다 (`numfmt.enable_format_spec` 이 부른다)
    출처: eudplib 0.81 `string/fmtprint.py:17` _EUDFormatter, `:90` eudformat_field
    """
    cls = _mod("eudplib.string.fmtprint")._EUDFormatter
    orig = cls.__dict__["eudformat_field"]

    def eudformat_field(self, value, format_spec):
        r = hook(value, format_spec)
        if r is None:
            return orig(self, value, format_spec)
        return r

    eudformat_field._eudext_orig = orig
    cls.eudformat_field = eudformat_field

    def restore():
        if cls.__dict__.get("eudformat_field") is eudformat_field:
            cls.eudformat_field = orig

    return restore


# --- WP16 (bgm) ---
# 출력 맵 MPQ 에서 파일 꺼내기 — tests/t_bgm.py 가 euddraft 빌드 결과에 소리가 들었는지 본다(출력 맵에는 (listfile) 이 없다).

_WP16_REQUIRED = (("eudplib.bindings._rust", "mpqapi"),)


def mpq_read_file(path, name):
    """scx/scm(MPQ) 파일 안의 name 파일 내용. 없으면 None.

    인자: path(맵 파일 경로), name(MPQ 안 이름, 예 "staredit\\wav\\a.wav")
    반환: bytes 또는 None
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `bindings/_rust` mpqapi.MPQ.open/extract_file (`maprw/loadmap.py` 가 쓰는 것)
    """
    mpq = _mod("eudplib.bindings._rust").mpqapi.MPQ.open(path)
    try:
        return bytes(mpq.extract_file(name))
    except FileNotFoundError:
        return None


# --- WP6b (display) ---
# 호출 자리 문자열(버퍼)을 **중복 제거 없이** 새로 만들고, 빌드가 바뀔 때 그 번호의 주소 조회(Forward)를 지운다.
# eudplib `ForceAddString` 은 최상위에 공개되지 않았다(StringBuffer 가 쓰는 것). `GetMapStringAddr(상수 번호)` 는
# 번호마다 Forward 를 `string.cpstr._const_strptr` 에 남기고 빌드마다 모두 다시 푸는데, 앞 빌드에만 있던 번호가 남으면
# 다음 빌드에서 "non-existing string ID" 오류가 난다(한 프로세스 여러 빌드 — 시험·도구).

_WP6b_REQUIRED = (
    ("eudplib.core.mapdata.stringmap", "ForceAddString"),
    ("eudplib.core.mapdata.stringmap", "strmap"),
    ("eudplib.string.cpstr", "_const_strptr"),
    ("eudplib.string.cpstr", "_initialize_queries"),
    ("eudplib.core.allocator.payload", "_register_after_collecting_callback"),
)


def force_add_string(content):
    """맵 문자열 표에 content 를 **새 번호로**(같은 내용이 있어도 합치지 않고) 넣고 번호(1부터)를 돌려준다.

    인자: content(bytes — str 이면 UTF-8 로 바꾼다. eudplib 은 str 을 cp949 로 바꾸므로 바이트로 넘긴다)
    반환: int
    비용: 없음(컴파일 시점, 문자열 표에 len+1 을 4 배수로 올린 바이트 + 4)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다 (`display` 내부용)
    출처: eudplib 0.81 `core/mapdata/stringmap.py` ForceAddString (StringBuffer 가 버퍼를 만드는 방법)
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    return _mod("eudplib.core.mapdata.stringmap").ForceAddString(bytes(content))


def forget_mapstring_addrs(ids):
    """`GetMapStringAddr(번호)` 가 남긴 주소 조회 중 ids 의 것을 지운다(빌드 되돌리기 훅에서 부른다).

    인자: ids(문자열 번호 모음)
    반환: 지운 개수
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `string/cpstr.py` `_const_strptr`, `_initialize_queries`
    """
    table = _mod("eudplib.string.cpstr")._const_strptr
    n = 0
    for i in list(ids):
        if table.pop(i, None) is not None:
            n += 1
    return n


def string_map_token():
    """지금 불러온 맵의 문자열 표 객체(LoadMap 마다 새로 만들어진다). 같은 빌드인지 가릴 때 `is` 로 비교한다.

    인자: 없음
    반환: 객체(LoadMap 전이면 None)
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `core/mapdata/stringmap.py` 모듈 전역 `strmap`
    """
    return getattr(_mod("eudplib.core.mapdata.stringmap"), "strmap", None)


def refresh_mapstring_queries():
    """이번 빌드에서도 `GetMapStringAddr(상수 번호)` 주소를 풀도록 eudplib 의 수집 뒤 콜백을 다시 건다.

    eudplib 0.81.0 은 이 콜백(`string/cpstr.py` `_initialize_queries`)을 프로세스의 **첫 빌드에서만** 부른다(WP0 의
    create-payload 콜백과 같은 성질, WP6b 실측) → 한 프로세스의 두 번째 빌드부터는 주소가 앞 빌드 값으로 남는다.
    `reset_build_state()` 뒤(빌드 시작)에 부른다. 콜백은 지금 문자열 표에 없는 번호의 조회를 먼저 지운다
    ("non-existing string ID" 오류 방지 — 그 조회를 가진 옛 객체의 주소는 옛 값으로 남는다).
    euddraft(빌드 한 번)에서는 부를 필요가 없다. 첫 빌드에서 두 번 불려도 결과는 같다.
    인자: 없음
    반환: None
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `string/cpstr.py:49~80`, `core/allocator/payload.py:230`
    """
    cp = _mod("eudplib.string.cpstr")
    sm_mod = _mod("eudplib.core.mapdata.stringmap")

    def _refresh():
        sm = getattr(sm_mod, "strmap", None)
        table = cp._const_strptr
        for sid in list(table):
            if sm is None or not isinstance(sid, int) or sm.GetString(sid) is None:
                table.pop(sid, None)
        cp._initialize_queries()

    _mod("eudplib.core.allocator.payload")._register_after_collecting_callback(_refresh)
