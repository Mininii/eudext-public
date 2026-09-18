"""동기화 입력 시험 모델 (DESIGN 5.1 표 "플레이어 목록 여러 개, before/afterTriggerExec 순서, 수신 펄스 주입").

WP13 이 `tests/t_sync.py` 안에 만든 모델을 WP18(2026-09-17)에서 옮겼다. `t_sync`(sync 소비자)와 `t_scrdb`(SCR_DB
수신기)가 같이 쓴다. 개발 venv 전용 — 맵 빌드에서 불러오지 않는다.

모델
- `RecvModel`: MSQC 0.11 `ReceiveQC`(plugins/MSQC.py:1031~1183)가 **출력 칸**에 쓰는 규칙만 흉내 낸다. 사람 플레이어마다
  매 사이클 펄스 칸 = 0, 값 칸 = −1(`sync.IDLE_VALUE`)로 지운 뒤, 받은 비트마다 펄스 칸 += 증가량, 받은 값은 칸에 쓴다.
  플러그인 코드를 돌리지 않고 에뮬레이터 메모리에 바로 쓴다(빠르다).
- `RefState`: sync 소비자 참조 모델 — level 은 Down 만 → 1, Up 만 → 0, 둘 다/없음 → 그대로. 걸쇠는 받은 값.
- `TurnSim`: 네트워크 턴 모델(INT 1.3, 5.1). 프레임 f 에 보낸 명령은 지연(latency) 뒤 첫 턴 경계(turn 의 배수)에서
  실행되고, 같은 (플레이어, QC 유닛)의 여러 명령 중 **마지막 것만** 남는다.
- `QCUnits`: MSQC 플러그인 **실제 코드**(`load_plugin`)를 에뮬레이터에서 돌릴 때의 가짜 QC 유닛.
  플러그인 `Respawn` 의 CreateUnitWithProperties 를 `testing/scmodel` 유닛 모델(기본, 빈 칸 목록 0x628438)로 받고,
  수신은 QC 유닛 CUnit+0x10(moveTarget)에 비트·값을 주입해서 흉내 낸다(SendQC 의 게임 명령은 흉내 내지 않는다).
- 도우미: `pairs_of`/`settings_of`(eds 줄 → euddraft 설정 dict), `load_plugin`/`unload_plugin`(플러그인 원문을 이
  프로세스에서 settings 와 함께 실행), `set_humans`(불러온 맵 chk 의 OWNR 에서 사람 슬롯 바꾸기).

사용 (MSQC 실제 코드 + 소비자):

    LoadMap(BASE_MAP); set_humans([0, 1, 3])
    mod = load_plugin(MSQC_PY, "MSQC", settings_of(sync.eds_sections()["MSQC"]))
    prog = emu.Program(lambda: (mod.beforeTriggerExec(), …), setup=mod.onPluginStart)
    m = prog.build(); unload_plugin("MSQC")
    scmodel.install_game_memory(m, players=[…])
    qc = QCUnits(m, mod, [0, 1, 3])          # 유닛 모델 설치 (CreateUnit 처리기)
    m.cycle()                                # 시작 코드 + Respawn
    qc.inject_bits(hi, [["array", "eudext_b_p1", 1]]); qc.inject_value(hi, 21, 0x40001); m.cycle()
"""

import sys
import types
import warnings

from eudplib import GetChkTokenized

from eudext.testing import scmodel

__all__ = [
    "CUNIT0",
    "CUNIT_SIZE",
    "QCUnits",
    "RecvModel",
    "RefState",
    "TurnSim",
    "WAYPOINT_BASE",
    "load_plugin",
    "pairs_of",
    "set_humans",
    "settings_of",
    "unload_plugin",
]

CUNIT0 = scmodel.UNIT_TABLE
CUNIT_SIZE = scmodel.UNIT_SIZE
WAYPOINT_BASE = 64 * 65537  # QC 유닛 moveTarget 기준값 (MSQC.py:650, sync.MSQC_WAYPOINT_BASE)


# ---------------------------------------------------------------------------------------------
# eds 줄·플러그인
# ---------------------------------------------------------------------------------------------


def pairs_of(lines):
    """eds 줄 → [(풀린 키, 값)] (euddraft readconfig 처럼 키의 `\\x` 이스케이프를 푼다). 값이 없으면 None."""
    from eudext.tools import edsgen

    out = []
    for line in lines:
        k = edsgen.line_key(line)
        v = line.split(" : ", 1)[1] if " : " in line else None
        out.append((k, v))
    return out


def settings_of(fragment_lines):
    """eds 줄 목록 → euddraft 플러그인 `settings` dict."""
    return {k: v for k, v in pairs_of(fragment_lines)}


def load_plugin(path, name, settings):
    """플러그인 원문(.py)을 settings 와 함께 이 프로세스에서 실행하고 `sys.modules[name]` 에 등록한다.

    인자: path(플러그인 파일), name(모듈 이름 — MSQC/NSQC 는 sync.verify 가 이 이름으로 찾는다), settings(dict)
    반환: 모듈 (onInit 까지 실행된 상태 — 모듈 최상위 코드가 설정을 해석한다)
    옛 플러그인의 `'\\g'` 이스케이프 SyntaxWarning 은 숨긴다. 다 쓰면 `unload_plugin(name)`.
    """
    with open(path, encoding="utf-8") as f:
        src = f.read()
    mod = types.ModuleType(name)
    mod.__dict__["settings"] = dict(settings)
    sys.modules[name] = mod
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        code = compile(src, path, "exec")
    exec(code, mod.__dict__)
    return mod


def unload_plugin(name):
    """`load_plugin` 이 등록한 모듈을 지운다(없으면 무시)."""
    sys.modules.pop(name, None)


def set_humans(humans, others=5):
    """지금 불러온 맵의 OWNR 에서 humans(0~7 번호 목록)를 사람(6)으로, 나머지 0~7 을 others(기본 5 = 컴퓨터)로 바꾼다.

    MSQC·sync·scrdb 는 이 표로 사람 플레이어를 정한다. LoadMap 뒤, 선언·빌드 전에 부른다.
    반환: 바꾸기 전 OWNR 바이트
    """
    chk = GetChkTokenized()
    old = chk.getsection("OWNR")
    ownr = bytearray(old)
    for p in range(8):
        ownr[p] = 6 if p in humans else others
    chk.setsection("OWNR", bytes(ownr))
    return bytes(old)


# ---------------------------------------------------------------------------------------------
# 출력 칸 모델·참조 모델·턴 모델 (WP13 t_sync 에서 옮김)
# ---------------------------------------------------------------------------------------------


class RecvModel:
    """MSQC ReceiveQC 가 출력 칸에 쓰는 규칙을 에뮬레이터 메모리에 흉내 낸다.

    인자: machine(emu.Machine), humans(사람 플레이어 번호 목록 — 이 플레이어 칸만 지우고 쓴다)
    - `add(channel, addr)`: sync 채널(`sync.Pulse` 또는 값 채널)과 그 출력 EUDArray 칸 0 주소를 등록.
    - `apply(received)`: received = {플레이어: {채널: True(펄스) 또는 값}} — 이번 사이클에 실행된 명령의 결과.
      등록한 모든 채널의 사람 칸을 지우고(펄스 0, 값 채널은 `channel.idle`) 받은 것을 쓴다.
    출처: euddraft 0.11.0.1 plugins/MSQC.py:1031~1183 (ReceiveQC), WP13 t_sync.py
    """

    def __init__(self, machine, humans):
        self.m = machine
        self.humans = list(humans)
        self.chans = []  # (채널, 주소)

    def add(self, ch, addr):
        self.chans.append((ch, addr))

    def apply(self, received):
        from eudext import sync

        m = self.m
        for p in self.humans:
            for ch, a in self.chans:
                if isinstance(ch, sync.Pulse):
                    m.setdw(a + 4 * p, 0)
                else:
                    m.setdw(a + 4 * p, ch.idle)
            addr = dict((id(c), x) for c, x in self.chans)
            for ch, v in received.get(p, {}).items():
                a = addr.get(id(ch))
                if a is None:
                    continue
                if isinstance(ch, sync.Pulse):
                    m.setdw(a + 4 * p, m.dw(a + 4 * p) + ch.inc)
                else:
                    m.setdw(a + 4 * p, v)


class RefState:
    """sync 소비자 참조 모델: level 은 Down 만 → 1, Up 만 → 0, 둘 다/없음 → 그대로. 걸쇠는 받은 값.

    - `step(received, level_pairs, latches, players)`: received 는 RecvModel 과 같은 모양, level_pairs = [(Down 채널, Up 채널)],
      latches = 걸쇠 채널 목록. 상태는 `level[(id(Down), p)]`, `latch[(id(채널), p)]`.
    출처: DESIGN 4.12 "초안과 달라진 점" 2, WP13 t_sync.py
    """

    def __init__(self):
        self.level = {}
        self.latch = {}

    def step(self, received, level_pairs, latches, players):
        for p in players:
            r = received.get(p, {})
            for down, up in level_pairs:
                d, u = down in r, up in r
                if d and not u:
                    self.level[(id(down), p)] = 1
                elif u and not d:
                    self.level[(id(down), p)] = 0
            for ch in latches:
                if ch in r:
                    self.latch[(id(ch), p)] = r[ch]


class TurnSim:
    """프레임별 송신 → 턴 경계에서 실행 → (플레이어, QC 유닛)마다 마지막 명령만 (INT 1.3, 5.1).

    인자: units({채널: QC 유닛 번호} — 같은 유닛에 실린 채널끼리 서로 덮는다), latency(프레임), turn(턴 길이, 프레임)
    - `send(frame, player, sent)`: sent = {채널: 값} 을 그 프레임에 보냈다.
    - `execute(frame)`: 이 프레임에 실행되는 것 {플레이어: {채널: 값}} (턴 경계가 아니면 {}).
    - `pending()`: 아직 실행되지 않은 명령 수.
    출처: WP13 t_sync.py (INT 5.1 — 한 턴 안의 여러 프레임 값은 마지막 것만)
    """

    def __init__(self, units, latency, turn):
        self.units = units  # 채널 → QC 유닛 번호
        self.latency = latency
        self.turn = turn
        self.queue = []  # (보낸 프레임, 플레이어, 유닛, {채널: 값})

    def send(self, frame, player, sent):
        by_unit = {}
        for ch, v in sent.items():
            by_unit.setdefault(self.units[ch], {})[ch] = v
        for u, d in by_unit.items():
            self.queue.append((frame, player, u, d))

    def execute(self, frame):
        if frame % self.turn:
            return {}
        due = [q for q in self.queue if q[0] + self.latency <= frame]
        self.queue = [q for q in self.queue if q[0] + self.latency > frame]
        last = {}
        for _f, p, u, d in due:  # 같은 (플레이어, 유닛) 은 뒤 명령이 덮어쓴다
            last[(p, u)] = d
        out = {}
        for (p, _u), d in last.items():
            out.setdefault(p, {}).update(d)
        return out

    def pending(self):
        return len(self.queue)


# ---------------------------------------------------------------------------------------------
# 가짜 QC 유닛 (MSQC 실제 코드용)
# ---------------------------------------------------------------------------------------------


class QCUnits:
    """MSQC 플러그인이 만드는 QC 유닛(사람 × QCCount)과 moveTarget 주입.

    인자: machine, plugin(`load_plugin` 으로 불러온 MSQC 모듈 — onInit 결과 `QCCount`, `qc_rets`, `xy_rets`, `bit_xy`,
          `map_x` 를 읽는다), humans(사람 번호 목록, 플러그인과 같은 순서), model("units" = scmodel 유닛 모델을 끼운다
          (없을 때만), "simple" = CreateUnit 마다 0x628438 을 336 늘리기만 하는 처리기 — WP13 방식)
    칸 순서: `Respawn` 이 사람 순서(hi) × QC 번호(n)로 만든다 → 유닛 칸 = hi·QCCount + n (빈 칸 목록이 0 부터 차례일 때).
    - `waypoint(hi, n)`: 그 QC 유닛의 CUnit+0x10 주소. `all_reset()`: 모든 moveTarget 이 기준값인가(수신 뒤 되돌림 확인).
    - `inject_bits(hi, rets)`: 불리언 채널(`qc_rets` 원소 — ["array", 이름, 증가량] 또는 ["deaths", 유닛, 증가량])을 받게 한다.
    - `inject_value(hi, target, value)`: val 채널(`xy_rets` 의 3번째 칸 = 출력 배열 이름 또는 데스 유닛)에 값을 싣는다.
    - `v2pos(value)`: MSQC 가 val 을 좌표로 바꾸는 식의 역(플러그인 `f_pos2vread_epd` 가 되돌린다).
    출처: WP13 t_sync.py section_msqc_e2e, euddraft 0.11.0.1 plugins/MSQC.py:562 Respawn, 1031 ReceiveQC
    """

    def __init__(self, machine, plugin, humans, model="units"):
        self.m = machine
        self.plugin = plugin
        self.humans = list(humans)
        self.qccount = plugin.QCCount
        self.nbits = len(plugin.bit_xy)
        self.ngroups = -(-len(plugin.qc_rets) // self.nbits) if plugin.qc_rets else 0
        self.index = {tuple(r): i for i, r in enumerate(plugin.qc_rets)}
        self.xyindex = {r[2]: j for j, r in enumerate(plugin.xy_rets) if r[0] == "val"}
        self.map_x = plugin.map_x
        if model == "units":
            if scmodel.unit_model(machine) is None:
                scmodel.install_units(machine)
        elif model == "simple":
            machine.setdw(scmodel.FIRST_UNUSED, CUNIT0)

            def create_unit(m, fields):
                m.setdw(scmodel.FIRST_UNUSED, m.dw(scmodel.FIRST_UNUSED) + CUNIT_SIZE)

            machine.act_handlers[scmodel.ACT_CREATE_UNIT_PROPS] = create_unit
            machine.act_handlers[scmodel.ACT_CREATE_UNIT] = create_unit
        else:
            raise ValueError("model 은 'units' 또는 'simple'")

    def expected_head(self):
        """Respawn 뒤 0x628438 이 가리켜야 할 주소(빈 칸 목록이 0 부터 차례일 때)."""
        return CUNIT0 + CUNIT_SIZE * self.qccount * len(self.humans)

    def waypoint(self, hi, n):
        return CUNIT0 + CUNIT_SIZE * (hi * self.qccount + n) + 0x10

    def all_reset(self):
        return all(self.m.dw(self.waypoint(hi, n)) == WAYPOINT_BASE
                   for hi in range(len(self.humans)) for n in range(self.qccount))

    def v2pos(self, v):
        mx = self.map_x
        return (v & ((1 << mx) - 1)) | ((v >> mx) << 16)

    def inject_bits(self, hi, rets):
        per_unit = {}
        for r in rets:
            i = self.index[tuple(r)]
            per_unit.setdefault(i // self.nbits, 0)
            per_unit[i // self.nbits] += self.plugin.bit_xy[i % self.nbits]
        for n, bits in per_unit.items():
            self.m.setdw(self.waypoint(hi, n), WAYPOINT_BASE + bits)

    def inject_value(self, hi, target, value):
        j = self.xyindex[target]
        self.m.setdw(self.waypoint(hi, self.ngroups + j), WAYPOINT_BASE + 1 + self.v2pos(value))
