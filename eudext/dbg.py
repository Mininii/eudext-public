"""디버그 브리지 — 게임 중 값을 외부 리더가 읽는 블록 (DESIGN 4.21).

CtrigAsm 맵용 `theSeed\\MapLogic\\DebugBridge.lua`(블록 배치 v1)와 **같은 형식**의 블록을 eudplib 으로 쓴다.
외부 리더(`eudext/tools/debugbridge/dbg_reader.py`, 원본 DPS_Enhance eudplib-port `tools/debugbridge`)가
StarCraft 메모리에서 서명을 찾아 읽고, 자동 판정 도구(`eudext/tools/ingame_auto.py`)가 판정 명세와 맞춰 본다.

    import eudext.dbg as dbg;                                   // epScript
    const bridge = dbg.setup(map_name="02_i64_check");          // 맨 먼저 (모듈 전역 const)
    var frame;
    const w = dbg.watch("frame", frame);                         // 변수 사본을 매 프레임
    function afterTriggerExec() {
        frame += 1;
        dbg.hit("tick");                                         // 지날 때마다 +1
        dbg.check("C3-1", some == 5);                            // 판정 카운터 (통과·전체)
        if (frame == 24) { dbg.result("C3-7", ok, 23); dbg.mark("done"); }
        DoActions(dbg.probe("act"));                             // 액션 목록에 넣는 카운터
        if (frame == 30) { dbg.suite_begin("s8", phase=4); … dbg.suite_end("s8"); }   // 점검 단계
    }

## 블록 배치 v1 (dword 인덱스, 주소 = 블록 + 4·인덱스 — DebugBridge.lua 와 같다)

| 인덱스 | 내용 |
|---|---|
| 0~7 | 서명 `SIGNATURE` — 게임 시작 때 SetMemory 여덟 개로 조립(맵 파일에는 32바이트 간격으로 흩어져 연속 사본이 없다) |
| 8 | 레이아웃 판 1 |
| 9 | 빌드 ID (심볼 JSON 과 짝) |
| 10 | 블록 자신의 EUD 주소 |
| 11 | 용량 = 감시 칸 수 W · 프로브 칸 수 P << 16 |
| 12 | seq 시작 (매 프레임 값 복사 전에 +1) |
| 13 | 게임 프레임 (0x57F23C 사본, 매 프레임) |
| 14 | 로컬 플레이어 (0x512684 사본, 시작 1회) |
| 15 | 사용 개수 (감시 · 프로브 << 16) |
| 16~19 | 0x57EEE8 부터 4 dword (플레이어 정보, 시작 1회 — 리더 `--diag` 용) |
| 20~23 | 0x57FD3C 부터 4 dword (맵 경로, 시작 1회) |
| 24.. | 감시 칸 W 개. **첫 칸은 eudext 표지**(맵 이름 CRC32, 시작 1회) |
| 24+W | seq 끝 (매 프레임 값 복사 뒤에 +1) — 리더는 seq 시작 == seq 끝 인 읽기만 쓴다 |
| 25+W.. | 프로브 칸 P 개 (hit·probe·check·result·mark·단계 — 사건이 날 때 맵이 직접 쓴다) |

eudext 가 감시 칸·프로브 칸에 싣는 것(기존 리더는 이름 붙은 숫자로 보여 주고, eudext 사본 리더는 풀어서 보여 준다):
- `watch(이름, EUDVariable)` 1칸, `watch(이름, 상수 주소·Cell·EUDLightVariable·페이로드 주소)` 1칸(매 프레임 읽기),
  `watch(이름, Int64)` 2칸(lo, hi), `watch(이름, Int128)` 4칸, `snapshot(이름, 주소, n)`·`snapshot_text` n칸.
  `snapshot(…, every=0)` 은 매 프레임 복사하지 않고 `capture(이름)` 자리에서만 복사한다(채팅 버퍼처럼 큰 칸).
- `hit`·`probe` 1칸(같은 이름은 한 칸), `check` 2칸(통과, 전체), `result` 3칸(통과, 전체, 보고 횟수), `mark` 1칸.
- 단계(suite): 처음 쓸 때 전체 칸 3(지금 단계 번호, 마지막으로 시작한 단계 번호, 마지막 사건 프레임) + 단계마다 4칸
  (상태 0 미실행·1 도는 중·2 끝, 시작 프레임, 끝 프레임, 맵 판정 0·1 통과·2 실패). 프레임 = seq 와 같이 느는 변수.
  단계 번호는 `suite_begin(…, phase=N)` 또는 등록 순서. 코드에서 begin 과 end 사이에 등록한 항목은 심볼에 `suite` 로 묶인다.
  맵이 멈추거나 튕기면 자동 판정이 마지막으로 본 "지금 단계"·프레임으로 어느 점검 도중이었는지 남긴다.

## 위치 (`setup(addr=…)`)

- **기본 `"top"`**: CtrigAsm void 구역 맨 위(`VoidAreaLimit` = 0x5967F0) 바로 아래, 16의 배수로 내림. 기본 용량(W 64, P 256)이면
  **0x596280~0x5967E4** — DebugBridge.lua 와 같은 자리다. 근거: 이 자리는 theSeed·DPS 인게임에서 DebugBridge 로 쓰여 SC:R 이 읽고 쓰는
  것을 확인했고, CtrigAsm 은 void 를 아래(0x58F500)부터 채우며 SCR_DB(0x58F500~0x594438)·MSQC 채널도 아래쪽이라 맨 위가 가장 덜 쓰인다.
  1.16.1 미러 구역(0x57F0E0~0x59F0E0)이라 리더 `--peek` 가 블록과 같은 오프셋으로 다른 미러 주소를 읽을 수 있다.
- **정수 주소**: 맵이 그 칸을 다른 데 쓰지 않을 때(예: 하이브리드 맵에서 DebugBridge.lua 와 함께 쓰면 겹치므로 옮긴다).
  미러 구역 밖이면 오류(`allow_outside_mirror=True` 로 풀기). SCR_DB(`scrdb.setup`)가 있으면 그 칸과 겹치는지 검사한다.
- **`"payload"`**: 페이로드의 `Db` 에 둔다(맵의 void 칸을 전혀 쓰지 않는다). 리더는 서명으로 찾으므로 읽기는 되지만,
  페이로드는 SC:R 에서 미러 구역과 다른 곳에 놓여 **`--peek`(미러 주소 직접 읽기)·`--diag` 의 선형 진단은 쓸 수 없다**.
  게임이 끝나도 옛 블록이 메모리에 남을 수 있다(리더·자동 판정은 seq 가 움직이는 블록만 고른다).

## 규칙

- 블록은 **맵만 쓰고 게임 로직은 읽지 않는다** → 로컬 분기 안의 hit 도 디싱크를 만들지 않는다(값은 PC 마다 다를 수 있다).
  매 프레임 복사 코드는 모든 PC 에서 같은 경로로 돈다. 싱글·LAN 시험용(리더가 외부 프로세스 메모리를 읽는다).
- 매 프레임 코드는 **게임 루프 시작점**(`_compat.on_game_loop_start` — euddraft 가 beforeTriggerExec 앞에 부름)에 둔다:
  seq 시작 +1 → 게임 프레임 → 감시 값 → seq 끝 +1. 보이는 값은 **앞 프레임 끝**의 값이다.
- 시작 1회 코드(미러 블록의 쓰는 칸 지우기 → 머리 → 정적 사본 → 서명)는 `setup` 을 모듈 전역에서 부르면 가장 이른 시작 목록(`EUDOnStart`),
  빌드 중에 부르면 주 함수 뒤 시작 목록에 들어간다. 둘 다 주 함수보다 먼저 실행된다. **`setup` 을 다른 dbg 호출보다 먼저** 부른다.
- 등록(`watch`/`hit`/`check` …)은 주 함수·시작 코드를 만드는 동안 끝나야 한다(게임 루프 훅에서 칸을 정한다). 늦으면 오류.
- 끄기: `setup(enable=False)` 또는 모듈 속성 `dbg.enabled = False`(setup 전), 빌드 환경 `EUDEXT_DBG=0`(부트 `Dbg : 0`)이면
  코드와 상관없이 꺼진다. 꺼지면 **트리거를 하나도 만들지 않고**, `probe()` 는 꺼진(비활성 표시) 액션을 돌려준다.
  epScript 인자 식(`dbg.check("x", a == b)` 의 `a == b`)은 호출 전에 계산되므로 그 식이 내는 트리거는 남는다.
  `setup` 없이 부른 dbg 함수도 아무것도 하지 않는다.
- 심볼 JSON(리더 `--symbols` 형식 + `eudext` 확장)은 게임 루프 훅에서 쓴다. 위치: `setup(symbols=파일 또는 폴더)` >
  환경 `EUDEXT_DBG_DIR`(부트 `DbgDir`) > `EUDEXT_WORK/dbg` > `<임시 폴더>/eudext_work/dbg`. 파일 이름
  `DebugBridge_<맵 이름>_<빌드 ID>.json` 과 최신 사본 `DebugBridge_symbols.json`. **C:\\Temp 에는 쓰지 않는다.**

출처: 블록 배치·서명·정적 사본·seq 규칙 = theSeed `MapLogic/DebugBridge.lua`(c5d0776, 사용자 작성), 심볼 형식 = 같은 파일
`DBG_WriteSymbols`, 페이로드 블록 방식 = DPS_Enhance eudplib-port `eud/ctrig/profile.py`(CounterBlock).
"""

import json
import os
import re
import sys
import tempfile
import time
import zlib

from eudplib import (
    EPD,
    Add,
    Condition,
    IsConstExpr,
    Db,
    DoActions,
    EUDElse,
    EUDEndExecuteOnce,
    EUDEndIf,
    EUDExecuteOnce,
    EUDIf,
    EUDOnStart,
    EUDVariable,
    Forward,
    RawTrigger,
    SeqCompute,
    SetMemoryEPD,
    SetTo,
    f_dwread_epd,
    f_repmovsd_epd,
    unProxy,
)

import eudext
from eudext import _compat, _parts
from eudext.errors import fail, require

__all__ = [
    "DEFAULT_PROBES",
    "DEFAULT_TOP",
    "DEFAULT_WATCH_SLOTS",
    "HDR",
    "LAYOUT_VERSION",
    "MIRROR_REGION",
    "SIGNATURE",
    "SUITE_ENDED",
    "SUITE_IDLE",
    "SUITE_RUNNING",
    "VOID_REGION",
    "Bridge",
    "check",
    "enabled",
    "f_check",
    "f_enabled",
    "f_hit",
    "f_mark",
    "f_mark_action",
    "f_probe",
    "f_result",
    "f_setup",
    "f_snapshot",
    "f_snapshot_text",
    "f_suite_begin",
    "f_suite_end",
    "f_capture",
    "capture",
    "f_watch",
    "hit",
    "layout",
    "mark",
    "mark_action",
    "probe",
    "reset",
    "result",
    "setup",
    "snapshot",
    "snapshot_text",
    "suite",
    "suite_begin",
    "suite_end",
    "symbols_doc",
    "watch",
]

# --- 배치 v1 (DebugBridge.lua DBG_I / dbg_reader.py 와 같아야 한다) ---------------------------------
LAYOUT_VERSION = 1
SIGNATURE = (0x44445545, 0x52424742, 0x9E3779B9, 0x7F4A7C15, 0xF39CC060, 0x5CEDC834, 0xB5297A4D, 0x1B873593)
HDR = 24
H_VERSION, H_BUILD, H_SELF, H_CAPS, H_SEQ_BEGIN, H_GAME_FRAME, H_LOCAL_PLAYER, H_USED = range(8, 16)
HEADER_INDEX = {"Version": 8, "Build": 9, "Self": 10, "Caps": 11, "SeqBegin": 12, "GameFrame": 13,
                "LocalPlayer": 14, "Used": 15, "PlayerInfo": 16, "MapPath": 20}
# (이름, EUD 주소, 블록 인덱스, dword 수) — 게임 시작 때 한 번 복사
STATIC_COPIES = (("local_player", 0x512684, 14, 1), ("player_info[0]", 0x57EEE8, 16, 4), ("map_path", 0x57FD3C, 20, 4))
GAME_FRAME_EUD = 0x57F23C
MIRROR_REGION = (0x57F0E0, 0x59F0E0)  # 1.16.1 주소가 SC:R 에서 같은 오프셋으로 읽히는 구역 (scrdb.MIRROR_REGION 과 같음)
VOID_REGION = (0x58F500, 0x5967F0)  # CtrigAsm VoidAreaOffset ~ VoidAreaLimit
DEFAULT_TOP = VOID_REGION[1]
DEFAULT_WATCH_SLOTS = 64
DEFAULT_PROBES = 256
MAX_TOTAL = 0x4000  # 리더가 받는 블록 크기 상한 (dbg_reader.find_blocks)
SYMBOLS_FORMAT = "eud-debug-bridge"
EXT_FORMAT = "eudext-dbg"
EXT_VERSION = 1
MARKER_NAME = "eudext.map"

# 모듈 속성: setup(enable=None) 이 읽는 기본값. 빌드 환경 EUDEXT_DBG=0 이면 늘 꺼진다.
enabled = True

_NAME_RE = re.compile(r"^[^\x00-\x1f]{1,96}$")
_SKIP_TAIL = ("/eudext/dbg.py",)


def _env_off():
    return os.environ.get("EUDEXT_DBG", "").strip().lower() in ("0", "off", "false", "no")


def _site():
    """호출한 자리 "파일:줄" (eudext.dbg·eudplib 안쪽 프레임은 건너뛴다)."""
    f = sys._getframe(1)
    try:
        while f is not None:
            fn = f.f_code.co_filename or "?"
            norm = fn.replace("\\", "/").lower()
            if not norm.endswith(_SKIP_TAIL) and "/eudplib/" not in norm:
                # f_lineno 는 줄 정보가 없는 프레임(epScript 가 만든 lambda — 줄 번호 -1)에서 None 이다(Python 3.10)
                return "%s:%d" % (os.path.basename(fn), f.f_lineno or 0)
            f = f.f_back
        return "?"
    finally:
        del f


def _check_name(name, what):
    if not isinstance(name, str) or not _NAME_RE.match(name):
        fail("dbg.%s: 이름은 제어 문자 없는 1~96자 문자열이어야 합니다 (%r)", what, name)
    return name


def _crc(text):
    return zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF


def _default_map_name():
    """euddraft 안이면 eds 의 [main] output 파일 이름(확장자 뺌), 아니면 "map"."""
    eds = sys.argv[1] if len(sys.argv) > 1 else ""
    if eds.lower().endswith(".eds") and os.path.isfile(eds):
        try:
            with open(eds, encoding="utf-8-sig", errors="replace") as f:
                section = None
                for raw in f:
                    line = raw.strip()
                    if line.startswith("[") and line.endswith("]"):
                        section = line[1:-1].strip().lower()
                    elif section == "main":
                        m = re.match(r"output\s*[:=]\s*(.+)$", line, re.I)
                        if m:
                            return os.path.splitext(os.path.basename(m.group(1).strip().replace("\\", "/")))[0]
        except OSError:
            pass
    return "map"


def _default_symbols_dir():
    env = os.environ.get("EUDEXT_DBG_DIR")
    if env:
        return env
    work = os.environ.get("EUDEXT_WORK") or os.path.join(tempfile.gettempdir(), "eudext_work")
    return os.path.join(work, "dbg")


# --- 등록 항목 -------------------------------------------------------------------------------------


class _Item:
    """감시 칸 묶음 또는 프로브 칸 묶음 하나. `fwd` = 첫 칸의 EPD (게임 루프 훅에서 정한다)."""

    __slots__ = ("area", "count", "every", "extra", "fwd", "index", "kind", "name", "no", "signed", "sites", "src",
                 "srcdesc", "suite")

    def __init__(self, area, kind, name, count, src=None, srcdesc="", signed=False, every=1, extra=None, suite=None):
        self.area = area  # "watch" | "probe"
        self.kind = kind
        self.name = name
        self.count = count
        self.src = src
        self.srcdesc = srcdesc
        self.signed = signed
        self.every = every
        self.extra = extra or {}
        self.suite = suite  # 이 항목이 속한 단계 이름 (없으면 None)
        self.sites = []
        self.fwd = Forward()
        self.no = Forward() if kind == "suite" else None  # 단계 번호 (1부터, 게임 루프 훅에서 정한다)
        self.index = None

    def epd(self, k=0):
        return self.fwd + k if k else self.fwd


# 단계(suite) 칸: 단계마다 [상태, 시작 프레임, 끝 프레임, 판정], 전체 [지금 단계, 마지막으로 시작한 단계, 마지막 사건 프레임]
SUITE_IDLE, SUITE_RUNNING, SUITE_ENDED = 0, 1, 2
SUITE_VERDICT_NONE, SUITE_VERDICT_PASS, SUITE_VERDICT_FAIL = 0, 1, 2
SUITES_NAME = "__suites__"


class _Config:
    __slots__ = ("addr", "allow_outside", "build_id", "db", "enable", "frame", "map_name", "probe_cap", "symbols", "tag",
                 "watch_cap", "where")

    @property
    def total(self):
        return HDR + self.watch_cap + 1 + self.probe_cap

    @property
    def seq_end(self):
        return HDR + self.watch_cap

    @property
    def probe_start(self):
        return HDR + self.watch_cap + 1

    def base_epd(self):
        return EPD(self.db) if self.where == "payload" else EPD(self.addr)

    def self_value(self):
        return self.db if self.where == "payload" else self.addr


class Bridge:
    """디버그 브리지 상태 (모듈에 하나 — `dbg._bridge`). 공개 함수는 모듈 함수(`dbg.watch` …)를 쓴다.

    빌드 밖(모듈 전역)에서 한 설정·등록은 계속 남고, 빌드 중에 한 것은 그 빌드에만 쓰인다(datpatch 와 같은 규칙).
    인자: 없음
    반환: -
    비용: 없음(상태만)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const bridge = dbg.setup(…);` 가 이 객체를 돌려준다(메서드는 쓰지 않아도 된다)
    출처: 새로 작성
    """

    def __init__(self):
        self._cfg_persist = None
        self._cfg_build = None
        self._persist = []
        self._build = []
        self._hook_start1 = False
        self._hook_loop = False
        self._new_build()
        self.last_symbols = None
        self.last_doc = None
        self.unset_calls = 0

    def _new_build(self):
        self._cfg_build = None
        self._build = []
        self._start2 = False
        self._init_emitted = False
        self._finalized = False
        self._used = None
        self._in_loop_hook = False
        self._open_suites = []  # 코드 순서로 열린 단계 (항목의 단계 이름을 정한다)
        self._zero = None  # 미러 블록 지우기 서브루틴 (시작 코드가 부르고 게임 루프 훅이 본문을 만든다)

    # --- 상태 ---
    @property
    def cfg(self):
        return self._cfg_build or self._cfg_persist

    def active(self):
        c = self.cfg
        return c is not None and c.enable

    def items(self):
        return self._persist + self._build

    def _phase(self):
        return _compat.onstart_phase()

    def _target(self):
        return self._persist if self._phase() == 0 and not self._in_loop_hook else self._build

    def _guard_late(self, what):
        if self._finalized or self._in_loop_hook:
            fail("dbg.%s: 게임 루프 훅에서 칸을 이미 정했습니다 — dbg 등록은 주 함수·시작 코드를 만드는 동안에 하세요", what)

    def _find(self, area, kind, name):
        for it in self.items():
            if it.area == area and it.kind == kind and it.name == name:
                return it
        return None

    def _add(self, item, what):
        self._guard_late(what)
        self._target().append(item)
        return item

    def current_suite(self, suite=None):
        if suite is not None:
            return _check_name(suite, "suite")
        return self._open_suites[-1] if self._open_suites else None

    def counter(self, kind, name, count, what, suite=None):
        it = self._find("probe", kind, name)
        if it is None:
            it = self._add(_Item("probe", kind, name, count, suite=self.current_suite(suite)), what)
        it.sites.append(_site())
        return it

    def suite_item(self, name, what, phase=None):
        """단계 칸(4)과 전체 단계 칸(3). phase 를 주면 단계 번호로 고정한다."""
        g = self._find("probe", "suites", SUITES_NAME)
        if g is None:
            g = self._add(_Item("probe", "suites", SUITES_NAME, 3), what)
        s = self.counter("suite", name, 4, what, suite=name)
        if phase is not None:
            if isinstance(phase, bool) or not isinstance(phase, int) or not 1 <= phase <= 0xFFFF:
                fail("dbg.%s: phase 는 1~65535 정수입니다 (%r)", what, phase)
            old = s.extra.get("phase")
            if old is not None and old != phase:
                fail("dbg.%s: 단계 %r 의 번호가 %d 와 %d 로 다릅니다", what, name, old, phase)
            s.extra["phase"] = phase
        return s, g

    # --- 설정 ---
    def setup(self, map_name=None, addr="top", watch_slots=DEFAULT_WATCH_SLOTS, probes=DEFAULT_PROBES, enable=None,
              build_id=None, tag=None, symbols=None, allow_outside_mirror=False):
        if self._finalized or self._in_loop_hook:
            fail("dbg.setup: 이번 빌드의 블록을 이미 정했습니다 — setup 은 맨 먼저 부르세요")
        if self._init_emitted:
            fail("dbg.setup: 이번 빌드의 시작 코드를 이미 만들었습니다 — setup 은 다른 코드보다 먼저, 한 번만 부르세요")
        c = _Config()
        c.enable = bool(enabled if enable is None else enable) and not _env_off()
        for label, v, lo, hi in (("watch_slots", watch_slots, 1, 0xFFFF), ("probes", probes, 0, 0xFFFF)):
            if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
                fail("dbg.setup: %s 는 %d~%d 정수여야 합니다 (%r)", label, lo, hi, v)
        c.watch_cap, c.probe_cap = watch_slots, probes
        require(c.total <= MAX_TOTAL, "dbg.setup: 블록이 너무 큽니다 (%d dword > %d — 리더 한도). watch_slots·probes 를 줄이세요",
                c.total, MAX_TOTAL)
        c.map_name = _check_name(map_name if map_name is not None else _default_map_name(), "setup(map_name)")
        c.tag = str(tag) if tag is not None else "eudext %s %s" % (eudext.__version__, time.strftime("%Y-%m-%d %H:%M:%S"))
        if build_id is None:
            build_id = ((int(time.time()) * 2654435761) ^ _crc(c.map_name)) & 0x7FFFFFFF or 1
        if isinstance(build_id, bool) or not isinstance(build_id, int) or not 0 < build_id <= 0xFFFFFFFF:
            fail("dbg.setup: build_id 는 1~0xFFFFFFFF 정수여야 합니다 (%r)", build_id)
        c.build_id = build_id
        c.symbols = symbols
        c.allow_outside = bool(allow_outside_mirror)
        c.db = None
        c.frame = EUDVariable() if c.enable else None  # seq 와 같이 느는 프레임 수 (단계 기록용)
        if isinstance(addr, str) and addr.lower() == "payload":
            c.where, c.addr = "payload", None
            if c.enable:
                c.db = Db(4 * c.total)
        elif isinstance(addr, str) and addr.lower() == "top":
            c.where = "mirror"
            c.addr = (DEFAULT_TOP - 4 * c.total) & ~15
            if c.addr < VOID_REGION[0]:
                fail("dbg.setup: 기본 자리(void 맨 위)에 블록 %d dword 가 들어가지 않습니다 — 용량을 줄이거나 addr 를 주세요", c.total)
        elif isinstance(addr, int) and not isinstance(addr, bool):
            c.where, c.addr = "mirror", addr & 0xFFFFFFFF
            if c.addr % 4:
                fail("dbg.setup: addr 0x%X 는 4의 배수여야 합니다", c.addr)
            if not c.allow_outside and not (MIRROR_REGION[0] <= c.addr and c.addr + 4 * c.total <= MIRROR_REGION[1]):
                fail("dbg.setup: 블록 0x%X~0x%X 가 1.16.1 미러 구역(0x%X~0x%X) 밖입니다 — 리더 --peek 이 안 되고 SC:R 이 막을 수 "
                     "있습니다(allow_outside_mirror=True 로 풀기)", c.addr, c.addr + 4 * c.total, *MIRROR_REGION)
        else:
            fail("dbg.setup: addr 는 \"top\", \"payload\" 또는 정수 주소입니다 (%r)", addr)
        if self._phase() == 0:
            self._cfg_persist = c
        else:
            self._cfg_build = c
        if c.enable:
            self._register_hooks()
        return self

    def _register_hooks(self):
        phase = self._phase()
        if phase == 0:
            if not self._hook_start1:
                EUDOnStart(self._start1_hook)
                self._hook_start1 = True
        elif phase == 1:
            if not self._start2:
                EUDOnStart(self._start2_hook)  # 빌드 중 → 주 함수 뒤에 생성되는 시작 목록
                self._start2 = True
        else:  # 시작 목록을 만드는 중 — 그 자리에 바로 낸다(한 번 실행되는 코드)
            self._emit_init()
        if not self._hook_loop:
            _compat.on_game_loop_start(self._loop_hook)
            self._hook_loop = True

    # --- 시작 1회 ---
    def _start1_hook(self):
        if self.active() and self._cfg_build is None and not self._init_emitted:
            self._emit_init()

    def _start2_hook(self):
        if self.active() and not self._init_emitted:
            self._emit_init()

    def _emit_init(self):
        c = self.cfg
        self._init_emitted = True
        self._used = Forward()
        base = c.base_epd()
        if c.where == "mirror":
            # 같은 SC 프로세스의 앞 게임이 남긴 값을 지운다. 쓰는 칸만 지우므로 본문은 칸을 정한 뒤(게임 루프 훅)에 만든다
            self._zero = _parts.SubLabel("dbg.zero")
            _parts.call_sub(self._zero)
        RawTrigger(actions=[
            SetMemoryEPD(base + H_VERSION, SetTo, LAYOUT_VERSION),
            SetMemoryEPD(base + H_BUILD, SetTo, c.build_id),
            SetMemoryEPD(base + H_SELF, SetTo, c.self_value()),
            SetMemoryEPD(base + H_CAPS, SetTo, c.watch_cap | c.probe_cap << 16),
            SetMemoryEPD(base + H_USED, SetTo, self._used),
            SetMemoryEPD(base + HDR, SetTo, _crc(c.map_name)),
        ])
        for _name, eud, index, count in STATIC_COPIES:
            if count == 1:
                f_dwread_epd(EPD(eud), ret=[base + index])
            else:
                f_repmovsd_epd(base + index, EPD(eud), count)
        # 서명은 맨 마지막 (리더가 반쯤 채운 블록을 보지 않게)
        RawTrigger(actions=[SetMemoryEPD(base + i, SetTo, v) for i, v in enumerate(SIGNATURE)])

    # --- 매 프레임 (게임 루프 시작점) ---
    def _loop_hook(self):
        if not self.active() or self._finalized:
            return
        self._in_loop_hook = True
        try:
            self._finalize()
        finally:
            self._in_loop_hook = False
            self._finalized = True

    def _layout(self):
        c = self.cfg
        widx = HDR + 1  # 첫 감시 칸은 eudext 표지
        pidx = c.probe_start
        watches = [it for it in self.items() if it.area == "watch"]
        probes = [it for it in self.items() if it.area == "probe"]
        need_w = 1 + sum(it.count for it in watches)
        need_p = sum(it.count for it in probes)
        if need_w > c.watch_cap:
            fail("dbg: 감시 칸이 모자랍니다 (필요 %d = 표지 1 + 감시 %d, watch_slots=%d) — setup(watch_slots=…) 를 늘리세요",
                 need_w, need_w - 1, c.watch_cap)
        if need_p > c.probe_cap:
            fail("dbg: 프로브 칸이 모자랍니다 (필요 %d, probes=%d) — setup(probes=…) 를 늘리세요", need_p, c.probe_cap)
        for it in watches:
            it.index, widx = widx, widx + it.count
        for it in probes:
            it.index, pidx = pidx, pidx + it.count
        return need_w, need_p

    def _check_overlap(self):
        c = self.cfg
        if c.where != "mirror":
            return
        lo, hi = c.addr, c.addr + 4 * c.total
        mod = sys.modules.get("eudext.scrdb")
        db = getattr(mod, "_current", None) if mod is not None else None
        for label, r in (getattr(db, "_regions", None) or {}).items():
            if lo < r[1] and r[0] < hi:
                fail("dbg: 블록 0x%X~0x%X 가 SCR_DB %s 0x%X~0x%X 와 겹칩니다 — dbg.setup(addr=…) 로 옮기세요", lo, hi, label, r[0], r[1])

    def _finalize(self):
        c = self.cfg
        self._check_overlap()
        need_w, need_p = self._layout()
        base = c.base_epd()
        for it in self.items():
            if it.fwd.IsSet():
                it.fwd.Reset()
            it.fwd << base + it.index
        self._number_suites()
        if not self._init_emitted:
            # 시작 목록에 못 들어간 경우(게임 루프 훅 직전에 setup) — 첫 프레임에 한 번
            if EUDExecuteOnce()():
                self._emit_init()
            EUDEndExecuteOnce()
        self._used << (need_w | need_p << 16)
        if self._zero is not None:
            # 지울 칸: 서명 8 · seq 시작 · 게임 프레임 · 쓰는 감시 칸(표지 포함) · seq 끝 · 쓰는 프로브 칸
            idx = list(range(8)) + [H_SEQ_BEGIN, H_GAME_FRAME] + list(range(HDR, HDR + need_w)) + [c.seq_end] + \
                list(range(c.probe_start, c.probe_start + need_p))
            acts = [SetMemoryEPD(base + i, SetTo, 0) for i in idx]
            with self._zero.define():
                for i in range(0, len(acts), 64):
                    RawTrigger(actions=acts[i:i + 64])

        RawTrigger(actions=[SetMemoryEPD(base + H_SEQ_BEGIN, Add, 1), c.frame.AddNumber(1)])
        f_dwread_epd(EPD(GAME_FRAME_EUD), ret=[base + H_GAME_FRAME])
        pairs = []
        for it in self.items():
            if it.area != "watch":
                continue
            if it.kind == "var":
                pairs.append((it.epd(), SetTo, it.src))
            elif it.kind in ("i64", "i128"):
                pairs.extend((it.epd(k), SetTo, v) for k, v in enumerate(it.src))
        if pairs:
            SeqCompute(pairs)
        for it in self.items():
            if it.area != "watch" or it.kind not in ("mem", "pmem", "text", "dwords") or it.every == 0:
                continue  # every == 0 은 capture() 자리에서만 복사한다
            if it.every > 1:
                cd = EUDVariable(0)
                if EUDIf()(cd.Exactly(0)):
                    self._emit_copy(it)
                    cd << it.every - 1
                if EUDElse()():
                    cd -= 1
                EUDEndIf()
            else:
                self._emit_copy(it)
        RawTrigger(actions=SetMemoryEPD(base + c.seq_end, Add, 1))
        self._write_symbols(need_w, need_p)

    def _number_suites(self):
        """단계 번호: phase 로 정한 번호를 먼저, 나머지는 등록 순서대로 비어 있는 번호."""
        suites = [it for it in self.items() if it.kind == "suite"]
        used = {}
        for it in suites:
            fixed = it.extra.get("phase")
            if fixed is not None:
                if fixed in used and used[fixed] != it.name:
                    fail("dbg: 단계 번호 %d 를 %r 와 %r 가 같이 씁니다", fixed, used[fixed], it.name)
                used[fixed] = it.name
        nxt = 1
        for it in suites:
            no = it.extra.get("phase")
            if no is None:
                while nxt in used:
                    nxt += 1
                no = nxt
                used[no] = it.name
            if it.no.IsSet():
                it.no.Reset()
            it.no << no
            it.extra["no"] = no

    def _emit_copy(self, it):
        src = it.src
        if isinstance(src, _PtrSrc):  # 실행 중 주소 → EPD 로 바꿔서
            t = EUDVariable()
            t << src.ptr
            f_repmovsd_epd(it.epd(), EPD(t), it.count)
        elif _compat.is_var(src):  # 실행 중 EPD
            f_repmovsd_epd(it.epd(), src, it.count)
        elif it.count == 1:
            f_dwread_epd(src, ret=[it.epd()])
        else:
            f_repmovsd_epd(it.epd(), src, it.count)

    # --- 심볼 ---
    def symbols_doc(self, need_w, need_p):
        c = self.cfg
        watches = [{"name": MARKER_NAME, "slot": HDR, "kind": "const", "src": "0x%08X" % _crc(c.map_name), "site": "eudext.dbg"}]
        probes = []
        ext_w, checks, results, marks, hits, texts, suites = [], [], [], [], [], [], []
        suite_slots = None
        for it in self.items():
            site = it.sites[0] if it.sites else ""
            su = it.suite
            if it.area == "watch":
                if it.kind in ("i64", "i128"):
                    parts = ("lo", "hi") if it.kind == "i64" else ("w0", "w1", "w2", "w3")
                    for k, p in enumerate(parts):
                        watches.append({"name": "%s.%s" % (it.name, p), "slot": it.index + k, "kind": "var",
                                        "src": it.srcdesc, "site": site})
                elif it.kind in ("text", "dwords"):
                    for k in range(it.count):
                        watches.append({"name": "%s[%d]" % (it.name, k), "slot": it.index + k, "kind": it.kind,
                                        "src": it.srcdesc, "site": site})
                    texts.append({"name": it.name, "kind": it.kind, "slot": it.index, "count": it.count,
                                  "every": it.every, "src": it.srcdesc, "site": site, "suite": su})
                else:
                    watches.append({"name": it.name, "slot": it.index, "kind": it.kind, "src": it.srcdesc, "site": site})
                if it.kind not in ("text", "dwords"):
                    ext_w.append({"name": it.name, "kind": it.kind, "slot": it.index, "count": it.count,
                                  "signed": it.signed, "src": it.srcdesc, "site": site, "suite": su})
                continue
            if it.kind == "probe":
                probes.append({"name": it.name, "index": it.index, "sites": it.sites})
                hits.append({"name": it.name, "index": it.index, "sites": it.sites, "suite": su})
            elif it.kind == "check":
                probes.append({"name": "check:%s.pass" % it.name, "index": it.index, "sites": it.sites})
                probes.append({"name": "check:%s.total" % it.name, "index": it.index + 1, "sites": it.sites})
                checks.append({"name": it.name, "pass": it.index, "total": it.index + 1, "sites": it.sites, "suite": su})
            elif it.kind == "result":
                for k, p in enumerate(("pass", "total", "reports")):
                    probes.append({"name": "result:%s.%s" % (it.name, p), "index": it.index + k, "sites": it.sites})
                results.append({"name": it.name, "pass": it.index, "total": it.index + 1, "reports": it.index + 2,
                                "sites": it.sites, "suite": su})
            elif it.kind == "mark":
                probes.append({"name": "mark:%s" % it.name, "index": it.index, "sites": it.sites})
                marks.append({"name": it.name, "index": it.index, "sites": it.sites, "suite": su})
            elif it.kind == "suite":
                for k, p in enumerate(("state", "begin", "end", "verdict")):
                    probes.append({"name": "suite:%s.%s" % (it.name, p), "index": it.index + k, "sites": it.sites})
                suites.append({"name": it.name, "no": it.extra.get("no"), "state": it.index, "begin": it.index + 1,
                               "end": it.index + 2, "verdict": it.index + 3, "sites": it.sites})
            elif it.kind == "suites":
                for k, p in enumerate(("current", "last", "frame")):
                    probes.append({"name": "suite.%s" % p, "index": it.index + k, "sites": []})
                suite_slots = {"current": it.index, "last": it.index + 1, "frame": it.index + 2}
        return {
            "format": SYMBOLS_FORMAT,
            "layout_version": LAYOUT_VERSION,
            "build_id": c.build_id,
            "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "signature": list(SIGNATURE),
            "block_eud": c.addr if c.where == "mirror" else None,
            "total_dwords": c.total,
            "header": dict(HEADER_INDEX),
            "watch_start": HDR,
            "watch_cap": c.watch_cap,
            "seq_end": c.seq_end,
            "probe_start": c.probe_start,
            "probe_cap": c.probe_cap,
            "static_copies": [{"name": n, "eud": e, "index": i, "count": k} for n, e, i, k in STATIC_COPIES],
            "dynamic_copies": [{"name": "game_frame", "eud": GAME_FRAME_EUD, "index": H_GAME_FRAME, "count": 1}],
            "watches": watches,
            "probes": probes,
            "vars": [],
            "mems": [],
            "eudext": {
                "format": EXT_FORMAT,
                "version": EXT_VERSION,
                "eudext_version": eudext.__version__,
                "map_name": c.map_name,
                "build_tag": c.tag,
                "where": c.where,
                "marker": _crc(c.map_name),
                "used": [need_w, need_p],
                "watches": ext_w,
                "texts": texts,
                "hits": hits,
                "checks": checks,
                "results": results,
                "marks": marks,
                "suites": suites,
                "suite_slots": suite_slots,
                "suite_states": {"idle": SUITE_IDLE, "running": SUITE_RUNNING, "ended": SUITE_ENDED},
                "result_names": [x["name"] for x in checks] + [x["name"] for x in results if x["name"] not in
                                                                 {y["name"] for y in checks}],
            },
        }

    def _symbols_paths(self):
        c = self.cfg
        p = c.symbols
        if p and str(p).lower().endswith(".json"):
            return [os.path.abspath(p)]
        d = os.path.abspath(p or _default_symbols_dir())
        safe = re.sub(r"[^0-9A-Za-z_.-]+", "_", c.map_name)[:60] or "map"
        return [os.path.join(d, "DebugBridge_%s_%08X.json" % (safe, c.build_id)), os.path.join(d, "DebugBridge_symbols.json")]

    def _write_symbols(self, need_w, need_p):
        doc = self.symbols_doc(need_w, need_p)
        text = json.dumps(doc, ensure_ascii=False, indent=1)
        paths = self._symbols_paths()
        for path in paths:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp, path)
        self.last_symbols = paths[0]
        self.last_doc = doc
        print("[eudext.dbg] 블록 %s 0x%s, 감시 %d/%d, 프로브 %d/%d, 빌드 %08X, 심볼 %s" % (
            self.cfg.where, "%X" % self.cfg.addr if self.cfg.addr is not None else "(페이로드)", need_w, self.cfg.watch_cap,
            need_p, self.cfg.probe_cap, self.cfg.build_id, paths[0]))

    def reset(self):
        """설정·등록을 모두 지운다(시험용). 등록한 훅은 남는다(꺼져 있으면 아무것도 내지 않음)."""
        self._cfg_persist = None
        self._persist = []
        self._new_build()


_bridge = Bridge()


@_compat.register_build_reset
def _reset_build():
    _bridge._new_build()


# ---------------------------------------------------------------------------------------------
# 값 분류
# ---------------------------------------------------------------------------------------------


class _PtrSrc:
    """실행 중 주소를 담은 변수 (복사 직전에 EPD 로 바꾼다)."""

    __slots__ = ("ptr",)

    def __init__(self, ptr):
        self.ptr = ptr


def _addr_epd(src, what):
    """주소 원천 → (EPD 식, 설명). 상수 주소·주소식·Cell/EUDLightVariable·EUDArray·StringBuffer·Db."""
    cls = type(src).__name__
    if cls == "StringBuffer":
        from eudplib import GetMapStringAddr

        return EPD(GetMapStringAddr(src.StringIndex)), "StringBuffer"
    if cls == "EUDArray":
        return _compat.eudarray_epd(src), "EUDArray"
    if _compat.is_varbase(src) and not _compat.is_var(src):  # Cell, EUDLightVariable
        return EPD(src.getValueAddr()), cls
    s = unProxy(src)
    if isinstance(s, bool):
        fail("dbg.%s: 참거짓은 주소가 아닙니다", what)
    if isinstance(s, int):
        a = s & 0xFFFFFFFF
        if a % 4:
            fail("dbg.%s: 주소 0x%X 는 4의 배수여야 합니다", what, a)
        return EPD(a), "0x%X" % a
    if _compat.is_varbase(s) and not _compat.is_var(s):
        return EPD(s.getValueAddr()), type(s).__name__
    if _compat.is_const(s) and not _compat.is_var(s):
        return EPD(s), "payload:%s" % type(s).__name__
    fail("dbg.%s: 주소로 쓸 수 없는 값입니다 (%r)", what, src)


# ---------------------------------------------------------------------------------------------
# 공개 함수
# ---------------------------------------------------------------------------------------------


def f_setup(map_name=None, addr="top", watch_slots=DEFAULT_WATCH_SLOTS, probes=DEFAULT_PROBES, enable=None,
            build_id=None, tag=None, symbols=None, allow_outside_mirror=False):
    """디버그 브리지를 켠다(블록 위치·용량·이름). 다른 dbg 호출보다 먼저, 모듈 전역에서 부르는 것을 권한다.

    인자: map_name(자동 판정이 맵을 알아보는 이름 — 기본 eds 출력 파일 이름), addr("top"(기본, void 맨 위 0x5967F0 아래)·
          "payload"·정수 주소), watch_slots(감시 칸 수, 기본 64 — 첫 칸은 표지), probes(프로브 칸 수, 기본 256),
          enable(None = 모듈 속성 `enabled`, 환경 EUDEXT_DBG=0 이면 늘 꺼짐), build_id(심볼 짝 번호, 기본 시각·이름 CRC),
          tag(빌드 표시 글), symbols(심볼 JSON 파일 또는 폴더), allow_outside_mirror(정수 주소가 미러 구역 밖이어도 허용)
    반환: Bridge
    비용: 시작 1회 = 쓰는 칸 지우기(서브루틴 1, 미러만) + 머리 1 + 정적 사본 3회(dwread 1 + repmovsd 2) + 서명 1
          (실행 약 370, 한 번 페이로드 약 5KB) /
          매 프레임 = seq 2 + 게임 프레임 읽기 1(실행 약 36) + 감시 몫(watch 참고). docs/COSTS.md "dbg"
    CP: 바꾸지 않음(읽기 함수는 CP 캐시 값으로 되돌린다)
    로컬: 공유 안전 (블록은 맵만 쓰고 게임 로직은 읽지 않는다)
    epScript: `const bridge = dbg.setup(map_name="02_i64_check");`
    출처: DebugBridge.lua `DBG_Init`(WatchCap 64·ProbeCap 256·VoidAreaLimit 아래)
    """
    return _bridge.setup(map_name=map_name, addr=addr, watch_slots=watch_slots, probes=probes, enable=enable,
                         build_id=build_id, tag=tag, symbols=symbols, allow_outside_mirror=allow_outside_mirror)


def f_enabled():
    """지금 브리지가 켜져 있는가 (컴파일 시점 상수 1/0).

    인자: 없음
    반환: int (1 = 켜짐)
    비용: 없음
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `if (dbg.enabled()) { … }` (조건 트리거 1개가 생긴다 — 트리거를 아예 안 만들려면 파이썬에서 판단)
    출처: 새로 작성
    """
    return 1 if _bridge.active() else 0


def _inactive():
    if _bridge.cfg is None:
        _bridge.unset_calls += 1
    return not _bridge.active()


def f_watch(name, src, signed=False, suite=None):
    """값을 매 프레임 블록의 감시 칸에 복사한다(seq 안 — 찢어지지 않은 사본).

    인자: name(이름), src(EUDVariable → 1칸 / 상수 주소·`Cell`·`EUDLightVariable`·페이로드 주소식 → 1칸 읽기 /
          `Int64` → 2칸(lo, hi) / `Int128` → 4칸), signed(리더·판정이 부호 있는 값으로 볼지),
          suite(묶을 단계 이름 — 없으면 코드에서 열려 있는 단계)
    반환: None
    비용: 변수 = 매 프레임 변수 트리거 1 (여러 개는 SeqCompute 한 줄에 묶임, 64액션마다 +1) /
          주소 = 매 프레임 `f_dwread_epd` 1회(호출 1~2, 실행 약 36). 호출 자리 0
    CP: 바꾸지 않음
    로컬: 공유 안전 (로컬 값도 넣을 수 있다 — 블록은 게임 로직이 읽지 않는다)
    epScript: `const w = dbg.watch("frame", frame);`  `dbg.watch("hp", i64value, signed=true);`
    출처: DebugBridge.lua `DBG_Watch`(변수·상수 주소)
    """
    _check_name(name, "watch")
    if _inactive():
        return None
    b = _bridge
    if any(it.area == "watch" and it.name == name for it in b.items()):
        fail("dbg.watch: 감시 이름 %r 이 이미 있습니다", name)
    su = b.current_suite(suite)
    cls = type(src).__name__
    if cls == "Int64":
        it = _Item("watch", "i64", name, 2, src=(src.lo, src.hi), srcdesc="Int64", signed=bool(signed), suite=su)
    elif cls == "Int128":
        it = _Item("watch", "i128", name, 4, src=(src.w0, src.w1, src.w2, src.w3), srcdesc="Int128",
                   signed=bool(signed), suite=su)
    elif cls not in ("StringBuffer", "EUDArray") and _compat.is_var(unProxy(src)):
        s = unProxy(src)
        it = _Item("watch", "var", name, 1, src=s, srcdesc=type(s).__name__, signed=bool(signed), suite=su)
    else:
        epd, desc = _addr_epd(src, "watch")
        # 상수 주소는 리더 --diag 가 직접 읽기와 견주는 "mem", 페이로드·변수 칸 주소는 "pmem"
        kind = "mem" if desc.startswith("0x") else "pmem"
        it = _Item("watch", kind, name, 1, src=epd, srcdesc=desc, signed=bool(signed), suite=su)
    b._add(it, "watch")
    it.sites.append(_site())
    return None


def f_snapshot(name, src, n, every=1, text=False, is_epd=False, suite=None):
    """주소에서 n dword 를 매 프레임(또는 every 프레임마다) 감시 칸에 복사한다(문자열 버퍼·배열 표시 판정용).

    인자: name, src(상수 주소·`StringBuffer`·`EUDArray`·`Db`·주소식·`Cell`, 또는 실행 중 주소를 담은 EUDVariable —
          `is_epd=True` 면 그 변수가 EPD), n(dword 수, 1~4096), every(복사 간격 프레임, 기본 1. **0 이면 매 프레임 복사하지
          않고 `capture(name)` 을 부른 자리에서만** — 채팅 버퍼처럼 큰 칸), text(리더가 글로 풀지), suite(단계 이름)
    반환: None
    비용: 매 프레임 `f_repmovsd_epd`(단어당 실행 약 35) + every>1 이면 분기 2~3. 변수 주소는 EPD 계산이 더 든다
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `dbg.snapshot("arr", arr, 8);`  `dbg.snapshot_text("chat", 0x640B58, 600, every=0);` + `dbg.capture("chat");`
    출처: 새로 작성
    """
    _check_name(name, "snapshot")
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 4096:
        fail("dbg.snapshot: n 은 1~4096 정수(dword 수)여야 합니다 (%r)", n)
    if isinstance(every, bool) or not isinstance(every, int) or not 0 <= every <= 0xFFFF:
        fail("dbg.snapshot: every 는 0~65535 정수여야 합니다 (%r)", every)
    if _inactive():
        return None
    b = _bridge
    if any(it.area == "watch" and it.name == name for it in b.items()):
        fail("dbg.snapshot: 감시 이름 %r 이 이미 있습니다", name)
    kind = "text" if text else "dwords"
    su = b.current_suite(suite)
    if type(src).__name__ not in ("StringBuffer", "EUDArray") and _compat.is_var(unProxy(src)):
        s = unProxy(src)
        if is_epd:
            it = _Item("watch", kind, name, n, src=s, srcdesc="EPD 변수", every=every, suite=su)
        else:
            it = _Item("watch", kind, name, n, src=_PtrSrc(s), srcdesc="주소 변수", every=every, suite=su)
    else:
        epd, desc = _addr_epd(src, "snapshot")
        it = _Item("watch", kind, name, n, src=epd, srcdesc=desc, every=every, suite=su)
    b._add(it, "snapshot")
    it.sites.append(_site())
    return None


def f_snapshot_text(name, src, n, every=1, is_epd=False, suite=None):
    """문자열 버퍼를 n dword 만큼 매 프레임 복사한다 — 리더·자동 판정이 UTF-8 글로 풀어 본다(`snapshot(…, text=True)`).

    인자: name, src(`StringBuffer`·`Db`·상수 주소·주소 변수), n(dword 수 — 글 바이트 ÷ 4 올림), every, is_epd, suite
    반환: None
    비용: `snapshot` 과 같다 (단어당 실행 약 35 — 218바이트 줄 55단어면 약 1,900/프레임, 무거우면 every)
    CP: 바꾸지 않음
    로컬: 공유 안전 (로컬 버퍼도 된다 — 표시 판정용)
    epScript: `dbg.snapshot_text("line", sb, 16);`
    출처: 새로 작성
    """
    return f_snapshot(name, src, n, every=every, text=True, is_epd=is_epd, suite=suite)


def _off_action():
    act = SetMemoryEPD(EPD(DEFAULT_TOP - 4), Add, 0)
    act.fields[9] |= 2  # 비활성 표시 (SC·에뮬레이터가 건너뛴다)
    return act


def f_probe(name, suite=None):
    """실행될 때마다 이름 카운터를 1 올리는 **액션**을 돌려준다(같은 이름은 한 칸을 같이 쓴다).

    인자: name, suite(단계 이름)
    반환: Action (꺼져 있으면 효과 없는 비활성 액션)
    비용: 액션 1 (트리거를 만들지 않는다)
    CP: 바꾸지 않음
    로컬: 공유 안전 (로컬 분기 안에서도 디싱크 없음 — 값은 PC 마다 다를 수 있다)
    epScript: `DoActions(dbg.probe("buy"));`
    출처: DebugBridge.lua `DBG_Probe`
    """
    _check_name(name, "probe")
    if _inactive():
        return _off_action()
    it = _bridge.counter("probe", name, 1, "probe", suite)
    return SetMemoryEPD(it.epd(), Add, 1)


def _raw_ok(c):
    """그 조건을 RawTrigger 칸에 그대로 넣을 수 있는가 (eudplib `Condition.CheckArgs` 와 같은 규칙).

    값 칸에 **변수**가 든 조건(eudplib 의 변수끼리 비교 `a == b`)은 RawTrigger 가 받지 못한다 → `EUDIf` 로 보낸다.
    """
    if not isinstance(c, Condition):
        return False
    f = c.fields
    return all(IsConstExpr(f[i]) for i in range(3)) and all(isinstance(f[i], int) for i in range(3, 9))


def _plain_conds(cond):
    """RawTrigger 에 바로 넣을 수 있는 조건 목록이면 목록, 아니면 None."""
    if isinstance(cond, Condition):
        return [cond] if _raw_ok(cond) else None
    if isinstance(cond, (list, tuple)) and 0 < len(cond) <= 16 and all(_raw_ok(c) for c in cond):
        return list(cond)
    return None


def _const_truth(cond):
    if isinstance(cond, bool):
        return cond
    if isinstance(cond, int):
        return cond != 0
    return None


def _emit_if(cond, act_true, act_false=None):
    """cond 가 참이면 act_true, 거짓이면 act_false (조건 목록이면 트리거로, 아니면 EUDIf)."""
    t = _const_truth(cond)
    if t is not None:
        acts = act_true if t else act_false
        if acts:
            RawTrigger(actions=acts)
        return
    conds = _plain_conds(cond)
    if conds is not None:
        if act_false:
            RawTrigger(actions=act_false)  # 먼저 거짓 쪽을 쓰고 참이면 덮는다 (같은 칸에만 쓴다)
        RawTrigger(conditions=conds, actions=act_true)
        return
    if EUDIf()(cond):
        DoActions(act_true)
    if act_false:
        if EUDElse()():
            DoActions(act_false)
    EUDEndIf()


def f_hit(name, cond=None, suite=None):
    """이 자리를 지날 때마다(조건이 있으면 참일 때만) 이름 카운터를 1 올린다.

    인자: name, cond(선택: Condition·조건 목록·EUDVariable·EUDIf 가 받는 것), suite(단계 이름)
    반환: None
    비용: 호출 자리 1 (조건이 Condition 목록이 아니면 EUDIf 2~3)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `dbg.hit("tick");`  `dbg.hit("big", v >= 100);`
    출처: DebugBridge.lua `DBG_Hit`
    """
    _check_name(name, "hit")
    if _inactive():
        return None
    it = _bridge.counter("probe", name, 1, "hit", suite)
    _emit_if(True if cond is None else cond, SetMemoryEPD(it.epd(), Add, 1))
    return None


def f_check(name, cond, suite=None):
    """판정 카운터: 전체 +1, 조건이 참이면 통과 +1 (자동 판정은 통과 == 전체 == 기대 수를 본다).

    인자: name(판정 이름 — 확인 항목 번호, 단계로 묶으려면 "c3.1" 처럼 단계 이름을 앞에), cond(Condition·조건 목록·
          EUDVariable(≠0 이면 참)·상수), suite(단계 이름 — 없으면 코드에서 열려 있는 단계)
    반환: None
    비용: 호출 자리 2 (조건이 Condition 목록이 아니면 EUDIf 로 3~4, 상수면 1)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `dbg.check("C3-1", r == 5);`
    출처: 새로 작성
    """
    _check_name(name, "check")
    if _inactive():
        return None
    it = _bridge.counter("check", name, 2, "check", suite)
    ok, total = SetMemoryEPD(it.epd(0), Add, 1), SetMemoryEPD(it.epd(1), Add, 1)
    t = _const_truth(cond)
    if t is not None:
        RawTrigger(actions=[total, ok] if t else [total])
        return None
    RawTrigger(actions=total)
    _emit_if(cond, ok)
    return None


def _value(v, what):
    v = unProxy(v)
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v & 0xFFFFFFFF
    if _compat.is_var(v) or _compat.is_const(v):
        return v
    fail("dbg.%s: 값은 정수·EUDVariable 이어야 합니다 (%r)", what, v)


def f_result(name, passed, total, suite=None):
    """판정 결과를 지금 보고한다: 통과 수·전체 수를 칸에 쓰고 보고 횟수 +1 (맵이 스스로 센 점검 결과).

    인자: name, passed(정수·EUDVariable), total(정수·EUDVariable), suite(단계 이름)
    반환: None
    비용: 호출 자리 1 (변수면 변수 트리거 실행 +1씩)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `dbg.result("C3-7", okCount, 23);`
    출처: 새로 작성
    """
    _check_name(name, "result")
    p, t = _value(passed, "result"), _value(total, "result")
    if _inactive():
        return None
    it = _bridge.counter("result", name, 3, "result", suite)
    SeqCompute([(it.epd(2), Add, 1), (it.epd(0), SetTo, p), (it.epd(1), SetTo, t)])
    return None


def f_mark(name, value=1, suite=None):
    """완료 표식(또는 단계 번호)을 칸에 쓴다. 자동 판정은 기본으로 표식 "done" 이 0 이 아니게 되기를 기다린다.

    인자: name, value(정수·EUDVariable, 기본 1), suite(단계 이름)
    반환: None
    비용: 호출 자리 1
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `dbg.mark("done");`  `dbg.mark("stage", stage);`
    출처: 새로 작성
    """
    _check_name(name, "mark")
    v = _value(value, "mark")
    if _inactive():
        return None
    it = _bridge.counter("mark", name, 1, "mark", suite)
    SeqCompute([(it.epd(), SetTo, v)])
    return None


def f_mark_action(name, value=1, suite=None):
    """`mark` 의 액션판(상수 값만) — 트리거 액션 목록에 넣는다.

    인자: name, value(상수), suite(단계 이름)
    반환: Action (꺼져 있으면 비활성 액션)
    비용: 액션 1
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `DoActions(dbg.mark_action("done"));`
    출처: 새로 작성
    """
    _check_name(name, "mark_action")
    v = _value(value, "mark_action")
    if _compat.is_var(v):
        fail("dbg.mark_action: 값은 상수만 됩니다 — 변수는 dbg.mark(name, v)")
    if _inactive():
        return _off_action()
    it = _bridge.counter("mark", name, 1, "mark_action", suite)
    return SetMemoryEPD(it.epd(), SetTo, v)


# --- 단계(suite) ---------------------------------------------------------------------------------


def f_capture(name):
    """`snapshot(…, every=0)` 으로 등록한 칸을 **지금** 복사한다(사건 순간의 버퍼를 남길 때).

    seq 밖에서 쓰므로 리더·자동 판정은 두 번 읽어 같은지로 확인한다.
    인자: name(snapshot 이름)
    반환: None
    비용: 호출 자리 = `f_repmovsd_epd` 호출 1~2 (실행 단어당 약 35)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `dbg.capture("chat");`
    출처: 새로 작성 (분류 문서 2절 chat 스냅숏)
    """
    _check_name(name, "capture")
    if _inactive():
        return None
    b = _bridge
    b._guard_late("capture")
    for it in b.items():
        if it.area == "watch" and it.name == name and it.kind in ("text", "dwords"):
            it.sites.append(_site())
            b._emit_copy(it)
            return None
    fail("dbg.capture: snapshot 으로 등록한 이름이 아닙니다 (%r) — 먼저 dbg.snapshot(…, every=0)", name)


def f_suite_begin(name, phase=None):
    """점검 단계 시작을 블록에 남긴다: 그 단계 상태 = 도는 중, 시작 프레임, 전체 칸의 "지금 단계"·"마지막 단계"·사건 프레임.

    맵이 도중에 멈추거나 튕기면 자동 판정 도구가 마지막으로 본 "지금 단계" 로 어느 점검 도중이었는지 알린다.
    코드에서 `suite_begin` 과 `suite_end` 사이에 있는 check·result·hit·mark·watch 는 이 단계에 묶인다(심볼 `suite`).
    단계 번호는 phase(주면) 또는 등록 순서(1부터, 빈 번호)다. 한 번에 하나씩 차례로 도는 것을 전제로 한다(끝나면 "지금 단계" 는 0).
    인자: name(단계 이름 — 결과 이름 앞머리와 같게 두기를 권장: "c3" → "c3.1", "c3.2"), phase(선택: 단계 번호 1~65535 —
          통합 맵의 phase 번호)
    반환: None
    비용: 호출 자리 2 (상수 쓰기 1 + 프레임 변수 사본 1, 실행 +2)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `dbg.suite_begin("s8", phase=4);`
    출처: 새로 작성 (통합 점검 맵 요청, 2026-09-18)
    """
    _check_name(name, "suite_begin")
    if _inactive():
        return None
    b = _bridge
    s, g = b.suite_item(name, "suite_begin", phase)
    b._open_suites.append(name)
    frame = b.cfg.frame
    SeqCompute([(s.epd(0), SetTo, SUITE_RUNNING), (s.epd(3), SetTo, SUITE_VERDICT_NONE), (g.epd(0), SetTo, s.no),
                (g.epd(1), SetTo, s.no), (s.epd(1), SetTo, frame)])
    SeqCompute([(g.epd(2), SetTo, frame)])
    return None


def f_suite_end(name, ok=None):
    """점검 단계 끝을 블록에 남긴다: 상태 = 끝, 끝 프레임, "지금 단계" = 0, (ok 를 주면) 단계 판정 = 통과/실패.

    인자: name, ok(선택: 맵이 스스로 낸 단계 판정 — Condition·조건 목록·EUDVariable·상수)
    반환: None
    비용: 호출 자리 2 (+ ok 가 조건이면 1~3)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `dbg.suite_end("c3");`  `dbg.suite_end("c3", okCount == 12);`
    출처: 새로 작성
    """
    _check_name(name, "suite_end")
    if _inactive():
        return None
    b = _bridge
    s, g = b.suite_item(name, "suite_end")
    if name in b._open_suites:
        del b._open_suites[len(b._open_suites) - 1 - b._open_suites[::-1].index(name)]
    frame = b.cfg.frame
    SeqCompute([(s.epd(0), SetTo, SUITE_ENDED), (g.epd(0), SetTo, 0), (s.epd(2), SetTo, frame)])
    SeqCompute([(g.epd(2), SetTo, frame)])
    if ok is not None:
        _emit_if(ok, SetMemoryEPD(s.epd(3), SetTo, SUITE_VERDICT_PASS), SetMemoryEPD(s.epd(3), SetTo, SUITE_VERDICT_FAIL))
    return None


class suite:  # noqa: N801 — 파이썬 전용 컨텍스트 관리자 (epScript 는 suite_begin/suite_end)
    """`with dbg.suite("c3"): …` — 앞뒤에 suite_begin/suite_end 를 낸다(파이썬 전용).

    인자: name, ok(선택: 끝에서 suite_end 에 넘길 판정)
    반환: -
    비용: suite_begin + suite_end
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다 (`dbg.suite_begin("c3"); … dbg.suite_end("c3");`)
    출처: 새로 작성
    """

    def __init__(self, name, ok=None):
        self.name = name
        self.ok = ok

    def __enter__(self):
        f_suite_begin(self.name)
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            f_suite_end(self.name, self.ok)
        return False


def reset():
    """설정·등록을 모두 지운다(시험용 — 한 프로세스에서 여러 맵을 빌드할 때). 훅은 남고 꺼진 상태가 된다.

    인자: 없음
    반환: None
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    _bridge.reset()


def layout():
    """이번 빌드의 블록 정보 dict (시험·도구용): where, addr, total, seq_end, probe_start, build_id, map_name, db, items.

    인자: 없음
    반환: dict 또는 None(설정 없음). items = {(종류, 이름): (첫 칸 인덱스, 칸 수)} — 게임 루프 훅 뒤에만 인덱스가 있다
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    c = _bridge.cfg
    if c is None:
        return None
    return {"where": c.where, "addr": c.addr, "db": c.db, "total": c.total, "seq_end": c.seq_end,
            "probe_start": c.probe_start, "watch_cap": c.watch_cap, "probe_cap": c.probe_cap, "build_id": c.build_id,
            "map_name": c.map_name, "enable": c.enable, "tag": c.tag,
            "items": {(it.kind, it.name): (it.index, it.count) for it in _bridge.items()}}


def symbols_doc():
    """마지막으로 쓴 심볼 문서(dict) — 시험·도구용."""
    return _bridge.last_doc


# 파이썬 별칭 (DESIGN 3.1)
setup = f_setup
watch = f_watch
snapshot = f_snapshot
snapshot_text = f_snapshot_text
probe = f_probe
hit = f_hit
check = f_check
result = f_result
mark = f_mark
mark_action = f_mark_action
suite_begin = f_suite_begin
suite_end = f_suite_end
capture = f_capture
