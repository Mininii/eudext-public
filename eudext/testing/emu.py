"""eudplib 페이로드를 게임 없이 돌려 보는 작은 트리거 에뮬레이터 (연산·흐름 검증용).

출처: DPS_eud `eud/tests/emu.py`(eudplib 0.76.14 용)를 eudplib 0.81 로 옮김.
0.81 에서 바뀐 점:
- SaveMap 가로채기는 `eudext._compat.capture_payload()` 경유(0.81 에서도 `maprw.savemap.apply_injector`,
  `maprw.injector.apply_injector.initialize_payload` 두 이름을 바꿔 끼우는 방식이 그대로 된다).
- 0.81 페이로드는 CompressPayload(True) 만 된다(적층 필수). 재배치 표(prttable/orttable)·RlocInt(offset, rlocmode)는 같다.
- euddraft 처럼 주 루프 앞에서 게임 루프 시작점을 정한다(`EUDLoopNewUnit` 등이 이 지점을 쓴다).
- SC 모델 확장은 `scmodel` 이 조건·액션 처리기 표(`cond_handlers`, `act_handlers`)에 끼운다.
- 메모리 초기값 표, 바이트 읽기·쓰기, 스냅숏/복원, 흉내 못 낸 조건·액션 집계를 더했다.

지원: 트리거 연결 목록(next 자기수정 포함), 보존/비활성 플래그, Deaths/Memory 조건(마스크 포함),
SetDeaths/SetMemory 액션(SetTo/Add/Subtract, 마스크 포함, Subtract 는 0 포화), CurrentPlayer(0x6509B0),
Always/Never, 비활성 조건·액션 건너뛰기, (scmodel) Switch/SetSwitch. 그 밖의 조건은 거짓, 그 밖의 액션은 기록만.
실행하지 않는 것: euddraft 3단계(TRIG 재연결·인라인 코드), 플레이어 목록 여러 개, TRIG 섹션 트리거.

사용:
    from eudplib import *
    from eudext.testing import emu
    LoadMap(base); CompressPayload(True)
    v = EUDVariable()
    prog = emu.Program(body)              # body: 한 사이클 분량의 코드를 만드는 함수
    prog.watch("v", v.getValueAddr())     # 확인할 주소 (ConstExpr 도 됨)
    m = prog.build()                      # 페이로드 생성 + 재배치 → Machine
    m.cycle(3)                            # 3 사이클 실행
    m.var("v"), m.dw(addr), m.ends        # 결과
"""

import os
import random
import struct
import tempfile
from collections import Counter

from eudplib import EUDEndInfLoop, EUDInfLoop, EUDObject, Never, RawTrigger, SaveMap, SetMemory, SetTo
from eudplib import EUDDoEvents

from eudext import _compat

BASE = 0x10000000  # 페이로드를 올릴 주소 (4의 배수)
EPD0 = 0x58A364
CP_ADDR = 0x6509B0
END = 0x80000000
M32 = 0xFFFFFFFF

COND_SIZE = 20
ACT_SIZE = 32
TRIG_FLAGS = 8 + 16 * COND_SIZE + 64 * ACT_SIZE  # = 2376

__all__ = ["BASE", "CP_ADDR", "END", "EPD0", "Machine", "Program", "EmuError"]


class EmuError(RuntimeError):
    """에뮬레이터 실행 오류 (페이로드 밖 점프, 실행 한도, 흉내 못 내는 필드 값)."""


class _Probe(EUDObject):
    """페이로드를 쓰는 단계에서 식들의 (offset, rlocmode) 를 기록한다."""

    def __new__(cls, *a, **k):
        return super().__new__(cls)

    def __init__(self, exprs):
        super().__init__()
        self.exprs = exprs
        self.result = None

    def GetDataSize(self):  # noqa: N802
        return 4

    def WritePayload(self, buf):  # noqa: N802
        self.result = {}
        for name, e in self.exprs.items():
            r = e.Evaluate() if hasattr(e, "Evaluate") else e
            self.result[name] = r
        buf.WriteDword(0)


def _reloc_value(r, base):
    if isinstance(r, int):
        return r & M32
    off, mode = r.offset, r.rlocmode
    return (off + mode * (base // 4)) & M32


class Program:
    """에뮬레이터용 페이로드를 만든다.

    인자: body(코드를 만드는 함수), loop(True 면 EUDInfLoop + EUDDoEvents 안에 넣는다 — 사이클마다 body 한 번),
          game_loop_start(True 면 euddraft 처럼 루프 시작에서 게임 루프 시작점을 정한다),
          setup(선택: 루프 앞, 첫 사이클에 한 번 실행할 코드를 만드는 함수)
    """

    def __init__(self, body, loop=True, game_loop_start=True, setup=None):
        self.body = body
        self.loop = loop
        self.game_loop_start = game_loop_start
        self.setup = setup
        self.exprs = {}
        self.payload_size = None

    def watch(self, name, expr):
        """이름으로 읽을 주소를 등록한다(EUDVariable 이면 값 칸)."""
        if hasattr(expr, "getValueAddr"):
            expr = expr.getValueAddr()
        self.exprs[name] = expr

    def _main(self, probe):
        # 탐침을 페이로드에 붙잡아 둔다 (흐름 안에 있지만 Never 라 실행되지 않는 트리거가 주소를 참조)
        RawTrigger(conditions=Never(), actions=SetMemory(probe, SetTo, 0))
        if self.setup is not None:
            self.setup()
        if self.loop:
            if EUDInfLoop()():
                if self.game_loop_start:
                    _compat.set_game_loop_start()
                self.body()
                EUDDoEvents()
            EUDEndInfLoop()
        else:
            self.body()

    def build(self, base=BASE, out=None):
        """SaveMap 을 돌려 페이로드를 얻고 base 에 재배치한 Machine 을 돌려준다.

        LoadMap 은 호출하는 쪽 몫이다. 같은 프로세스에서 여러 번 불러도 된다(`_compat.reset_build_state` 를 먼저 부른다).
        out: SaveMap 이 쓰는 파일(기본: 임시 폴더). 이 파일은 STR·TRIG 가 채워지지 않은 불완전한 맵이다.
        """
        _compat.reset_build_state()
        probe = _Probe(self.exprs)
        if out is None:
            out = os.path.join(tempfile.gettempdir(), "eudext_emu_out.scx")
        with _compat.capture_payload() as cap:
            cap["on_root"] = lambda root: probe.exprs.__setitem__("__root__", root)
            try:
                SaveMap(out, lambda: self._main(probe))
            except Exception:
                if cap["payload"] is None:
                    raise
        payload = cap["payload"]
        if payload is None or probe.result is None:
            raise EmuError("페이로드를 잡지 못했습니다 (eudplib SaveMap 흐름이 바뀌었을 수 있음)")
        data = bytearray(payload.data)
        for prt in payload.prttable:
            v = struct.unpack_from("<I", data, prt)[0]
            struct.pack_into("<I", data, prt, (v + base // 4) & M32)
        for ort in payload.orttable:
            v = struct.unpack_from("<I", data, ort)[0]
            struct.pack_into("<I", data, ort, (v + base) & M32)
        self.payload_size = len(data)
        addrs = {k: _reloc_value(v, base) for k, v in probe.result.items()}
        return Machine(bytes(data), base, addrs)


class Machine:
    """재배치된 페이로드와 희소 메모리(dict: 4의 배수 주소 → dword). 없는 주소는 0."""

    def __init__(self, data, base, addrs):
        self.mem = {}
        pad = -len(data) & 3
        data = data + bytes(pad)
        for i in range(0, len(data), 4):
            v = struct.unpack_from("<I", data, i)[0]
            if v:
                self.mem[base + i] = v
        self.base = base
        self.limit_addr = base + max(len(data), 4)
        self.addrs = addrs
        self.root = addrs["__root__"]
        self.log = []
        self.log_limit = 20000
        self.unknown = Counter()
        self.steps = 0
        self.ends = []
        self.last = 0
        self.rng = random.Random(0)
        # condtype → fn(machine, fields) -> bool,  acttype → fn(machine, fields) -> None
        self.cond_handlers = {}
        self.act_handlers = {}

    # --- 메모리 ---
    def dw(self, addr):
        return self.mem.get(addr & M32, 0)

    def setdw(self, addr, v):
        addr &= M32
        if addr & 3:
            raise EmuError("정렬 안 된 주소 쓰기 0x%X" % addr)
        self.mem[addr] = v & M32

    def db(self, addr):
        addr &= M32
        return (self.dw(addr & ~3) >> (8 * (addr & 3))) & 0xFF

    def setdb(self, addr, v):
        addr &= M32
        a = addr & ~3
        sh = 8 * (addr & 3)
        self.setdw(a, (self.dw(a) & ~(0xFF << sh)) | ((v & 0xFF) << sh))

    def read_bytes(self, addr, n):
        return bytes(self.db(addr + i) for i in range(n))

    def write_bytes(self, addr, data):
        for i, b in enumerate(data):
            self.setdb(addr + i, b)

    def var(self, name):
        """watch 로 등록한 이름의 dword 값."""
        return self.dw(self.addrs[name])

    def set_var(self, name, value):
        self.setdw(self.addrs[name], value)

    def addr(self, name):
        return self.addrs[name]

    def init_mem(self, table):
        """{주소: 값} 표를 쓴다. 값이 bytes 면 바이트 단위로 쓴다."""
        for a, v in table.items():
            if isinstance(v, (bytes, bytearray)):
                self.write_bytes(a, v)
            else:
                self.setdw(a, v)

    def snapshot(self):
        return (dict(self.mem), self.rng.getstate())

    def restore(self, snap):
        mem, rng = snap
        self.mem = dict(mem)
        self.rng.setstate(rng)

    # --- 실행 ---
    def _log(self, item):
        if len(self.log) < self.log_limit:
            self.log.append(item)

    def epd_addr(self, player, unit):
        """Deaths/SetDeaths 의 (player, unit) → 주소. 특수 플레이어(12, 14~26)는 None."""
        if player == 13:
            player = self.dw(CP_ADDR)
        elif 12 <= player <= 26:
            return None
        idx = (unit * 12 + player) & M32  # 데스 테이블 = [유닛][플레이어]
        return (EPD0 + 4 * idx) & M32

    def _cond(self, t, i):
        o = t + 8 + i * COND_SIZE
        w3 = self.dw(o + 12)
        ctype = (w3 >> 24) & 0xFF
        if ctype == 0:
            return None
        w4 = self.dw(o + 16)
        flags = (w4 >> 8) & 0xFF
        if flags & 2:
            return True
        if ctype == 22:
            return True
        if ctype == 23:
            return False
        locid, player, amount = self.dw(o), self.dw(o + 4), self.dw(o + 8)
        unit, cmp_ = w3 & 0xFFFF, (w3 >> 16) & 0xFF
        eudx = (w4 >> 16) & 0xFFFF
        if ctype == 15:
            a = self.epd_addr(player, unit)
            if a is None:
                raise EmuError("Deaths 의 특수 플레이어 %d" % player)
            v = self.dw(a)
            if eudx == 0x4353:
                v &= locid
            if cmp_ == 0:
                return v >= amount
            if cmp_ == 1:
                return v <= amount
            if cmp_ == 10:
                return v == amount
            raise EmuError("Deaths 비교 코드 %d" % cmp_)
        h = self.cond_handlers.get(ctype)
        if h is not None:
            fields = (locid, player, amount, unit, cmp_, ctype, w4 & 0xFF, flags, eudx)
            return bool(h(self, fields))
        self.unknown[("cond", ctype)] += 1
        self._log(("cond?", ctype))
        return False

    def _act(self, t, i):
        o = t + 8 + 16 * COND_SIZE + i * ACT_SIZE
        w6 = self.dw(o + 24)
        atype = (w6 >> 16) & 0xFF
        if atype == 0:
            return False
        w7 = self.dw(o + 28)
        flags = w7 & 0xFF
        if flags & 2:
            return True
        locid, strid, wavid, time_, p1, p2 = (self.dw(o + k) for k in range(0, 24, 4))
        unit, amount = w6 & 0xFFFF, (w6 >> 24) & 0xFF
        eudx = (w7 >> 16) & 0xFFFF
        if atype == 45:
            a = self.epd_addr(p1, unit)
            if a is None:
                raise EmuError("SetDeaths 의 특수 플레이어 %d" % p1)
            old, v = self.dw(a), p2
            m = locid if eudx == 0x4353 else M32
            if amount == 7:
                new = (old & ~m) | (v & m)
            elif amount == 8:
                new = (old & ~m) | (((old & m) + (v & m)) & m)
            elif amount == 9:
                s = (old & m) - (v & m)
                new = (old & ~m) | (max(s, 0) & m)
            else:
                raise EmuError("SetDeaths 수정자 %d" % amount)
            self.setdw(a, new)
            return True
        h = self.act_handlers.get(atype)
        fields = (locid, strid, wavid, time_, p1, p2, unit, atype, amount, flags, eudx)
        if h is not None:
            h(self, fields)
        else:
            self.unknown[("act", atype)] += 1
        self._log(("act", atype, strid, p1, p2, unit))
        return True

    def cycle(self, n=1, limit=5_000_000):
        """n 사이클 실행. 사이클마다 (실행한 트리거 수, 끝난 곳) 을 self.ends 에 남긴다 — 정상 끝은 END."""
        for _ in range(n):
            t = self.root
            start = self.steps
            while t not in (0, END):
                if not (self.base - 8 <= t < self.limit_addr):
                    self.ends.append((self.steps - start, t))
                    raise EmuError("페이로드 밖으로 점프: 0x%X (직전 0x%X)" % (t, self.last))
                self.last = t
                self.steps += 1
                if self.steps - start > limit:
                    self.ends.append((self.steps - start, t))
                    raise EmuError("실행 한도 초과 (무한 루프?) 마지막 트리거 0x%X" % t)
                flags = self.dw(t + TRIG_FLAGS)
                if not (flags & 8):
                    ok = True
                    for i in range(16):
                        r = self._cond(t, i)
                        if r is None:
                            break
                        if not r:
                            ok = False
                            break
                    if ok:
                        for i in range(64):
                            if not self._act(t, i):
                                break
                        if not (flags & 4):
                            self.setdw(t + TRIG_FLAGS, self.dw(t + TRIG_FLAGS) | 8)
                t = self.dw(t + 4)
            self.ends.append((self.steps - start, t))
        return self.ends[-1]

    def last_steps(self):
        """마지막 사이클에서 실행한 트리거 수."""
        return self.ends[-1][0] if self.ends else 0
