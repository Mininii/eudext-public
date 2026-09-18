"""SCR_DB 시험 참조 (t_scrdb 가 쓴다).

- `LuaFrame`: Lua 코어의 `SCRDB_Anchor` → `SCRDB_Receiver(Write)` → `SCRDB_Notify` 를 `tools/lua_consts.CtrigTrace` 로
  기록한 트리를 파이썬으로 한 사이클씩 실행한다(CtrigAsm 의미: CIf = 보존 분기, CIfOnce·플래그 없는 TriggerX = 1회,
  DoActions* = 보존, f_Read = 마스크 읽기, CMov/CAdd = 대입). **Lua 원본을 그대로 따라가는 참조 구현**이라
  eudext 수신기와 차등 시험을 할 수 있다.
- `LauncherModel`: DPS `tools/scr_db_launcher.py`(e7efff2) 의 MSQC 전송(항목 = 워드 3개를 같은 채널로, 채널별 락스텝,
  에코 확인·다시 보내기, 끝에 되읽기 대조, 준비·저장 완료 워드) 을 프레임 단위로 흉내 낸다.
"""

from eudext.tools.lua_consts import FP_VALUE, TEP_CONSTS, Ref, Term

M32 = 0xFFFFFFFF
DEATHS_BASE = 0x58A364
_CMP = {TEP_CONSTS["AtLeast"]: lambda a, b: a >= b, TEP_CONSTS["AtMost"]: lambda a, b: a <= b,
        TEP_CONSTS["Exactly"]: lambda a, b: a == b}


class LuaFrame:
    """Lua 판 SCR_DB 한 사이클 실행 모델.

    인자: core(ScrdbCore), cfg(Lua Cfg dict — ScrDb._lua_in), build_id(os.time 고정값)
    - `cycle(mem)`: mem = {주소: dword} (없는 칸 0) 를 고친다. 반환 없음. 이번 사이클의 `writes`[(i, key, val)]·
      `sounds`[(CP, wav)] 를 남긴다. 상태(Ccode·변수·1회 실행 표시)는 사이클을 넘어 남는다.
    - `flag(name, i)`: "LauncherReady"/"SaveDone"/"Activity" 의 i 번 Ccode 값.
    - `nodes`: 기록한 트리(Anchor + Receiver + Notify [+ CloseLoad — `close_load` 조건(Term 목록)을 주면]).
    - `close_load`: `SCRDB_CloseLoad(Conds)` 도 기록해 사이클 끝에 실행한다(선택).
    """

    def __init__(self, core, cfg, build_id, close_load=None):
        lua, tr = core.lua(os_time=build_id)
        core._run_setup(lua, cfg)
        self.cfg = lua.get("SCRDB_Cfg")
        self.flags = {n: lua.get("SCRDB_" + n) for n in ("LauncherReady", "SaveDone", "Activity")}
        tr.take()
        lua.call("SCRDB_Anchor")
        self.anchor = tr.take()
        lua.call("SCRDB_Receiver", tr.callback("Write"))
        self.receiver = tr.take()
        lua.call("SCRDB_Notify")
        self.notify = tr.take()
        self.close = []
        if close_load is not None:  # SCRDB_CloseLoad(Conds) — conds 는 Term 목록
            lua.call("SCRDB_CloseLoad", list(close_load))
            self.close = tr.take()
        self.nodes = self.anchor + self.receiver + self.notify + self.close
        self.cc = {}
        self.vars = {}
        self.done = set()
        self.mem = None
        self.cp = FP_VALUE
        self.writes = []
        self.sounds = []

    def flag(self, name, i):
        return self.cc.get(self.flags[name][i].n, 0)

    # --- 값 ---
    def _get(self, addr):
        return self.mem.get(addr & M32, 0)

    def _set(self, addr, v):
        self.mem[addr & M32] = v & M32

    def _val(self, x):
        if isinstance(x, Ref):
            return (self.cc if x.kind == "ccode" else self.vars).get(x.n, 0)
        if isinstance(x, Term):
            if x.op == "Mul":
                return (self._val(x.args[0]) * self._val(x.args[1])) & M32
            raise ValueError("모르는 식 %r" % (x,))
        if isinstance(x, bool) or not isinstance(x, int):
            raise ValueError("값이 아닙니다 %r" % (x,))
        return x & M32

    def _cond(self, t):
        a = t.args
        if t.op == "DeathsX":
            p, cmp_, v, u, mask = a
            return _CMP[cmp_](self._get(DEATHS_BASE + 4 * (12 * u + p)) & mask, v & M32)
        if t.op == "Memory":
            addr, cmp_, v = a
            return _CMP[cmp_](self._get(addr), v & M32)
        if t.op in ("CD", "CV"):
            ref, v, cmp_ = a
            return _CMP[cmp_](self._val(ref), self._val(v))
        raise ValueError("모르는 조건 %r" % (t,))

    def _act(self, t):
        a = t.args
        if t.op == "SetMemory":
            addr, mod, v = a
            self._modify(addr, mod, self._val(v), M32)
        elif t.op == "SetDeathsX":
            p, mod, v, u, mask = a
            self._modify(DEATHS_BASE + 4 * (12 * u + p), mod, self._val(v), mask)
        elif t.op == "SetCD":
            ref, v = a
            self.cc[ref.n] = self._val(v)
        elif t.op == "SetCp":
            self.cp = a[0]
        elif t.op == "PlayWAV":
            self.sounds.append((self.cp, a[0]))
        else:
            raise ValueError("모르는 액션 %r" % (t,))

    def _modify(self, addr, mod, v, mask):
        old = self._get(addr)
        if mod == TEP_CONSTS["SetTo"]:
            new = (old & ~mask) | (v & mask)
        elif mod == TEP_CONSTS["Add"]:
            new = (old & ~mask) | ((old + v) & mask)
        elif mod == TEP_CONSTS["Subtract"]:
            new = (old & ~mask) | (max((old & mask) - (v & mask), 0) & mask)
        else:
            raise ValueError("모르는 수정자 %r" % (mod,))
        self._set(addr, new)

    def _set_ref(self, ref, v):
        (self.cc if ref.kind == "ccode" else self.vars)[ref.n] = v & M32

    def _exec(self, n):
        if n.kind in ("trig", "if", "once"):
            once = n.kind == "once" or (n.kind == "trig" and not n.preserved)
            if once and id(n) in self.done:
                return
            if not all(self._cond(c) for c in n.conds):
                return
            for t in n.acts:
                self._act(t)
            if once:
                self.done.add(id(n))
            for c in n.body or ():
                self._exec(c)
        elif n.kind == "read":
            src, out, mask, _clear = n.args
            self._set_ref(out, self._get(src) & mask)
        elif n.kind == "mov":
            dest, src, mask = n.args
            v = self._val(src)
            if isinstance(dest, Ref):
                self._set_ref(dest, v & mask)
            else:
                self._modify(dest, TEP_CONSTS["SetTo"], v, mask)
        elif n.kind == "add":
            dest, x, y = n.args
            self._set_ref(dest, self._val(x) + self._val(y))
        elif n.kind == "call":
            _name, i, key, val = n.args
            self.writes.append((i if isinstance(i, int) else self._val(i), self._val(key), self._val(val)))
        else:
            raise ValueError("모르는 노드 %r" % (n,))

    def cycle(self, mem, parts=("anchor", "receiver", "notify", "close")):
        self.mem = mem
        self.writes = []
        self.sounds = []
        self.cp = FP_VALUE
        for part in parts:
            for n in getattr(self, part):
                self._exec(n)


class LauncherModel:
    """런처 한 대(플레이어 player)의 MSQC 전송 모델 — 프레임마다 `frame(read)` 를 부른다.

    인자: core(ScrdbCore), anchor(표지 블록 주소), player, channels, timeout(한 배치를 기다리는 사이클 수), max_retry
    - `load(items)`: items = [(키, 값 주소, 값)] — 불러오기 계획(항목마다 워드 3개, 채널 = 순번 % 채널 수). 끝나면
      되읽기 대조(2번) 뒤 준비 워드(0xFFFE)를 채널 0 으로.
    - `saved()`: 저장 완료 워드(0xFFFD)를 채널 0 으로.
    - `frame(read)`: read(주소) → dword. 반환 {채널: 이번 프레임에 로컬 칸에 둔 값(0 이면 보내지 않음)}.
    - `busy`, `log`, `resent`, `lost`.
    출처: DPS_Enhance eudplib-port tools/scr_db_launcher.py (e7efff2) msqc_send_batch:995, write_plan:746,
          do_load:1163, sync_toggles:962
    """

    def __init__(self, core, anchor, player, channels, timeout=6, max_retry=8):
        self.core = core
        self.anchor = anchor
        self.player = player
        self.channels = channels
        self.timeout = timeout
        self.max_retry = max_retry
        self.toggle = [None] * channels
        self.jobs = []  # ("words", {k: [워드…]}) | ("verify", items) | ("done", 이름)
        self.batch = None  # {k: 워드}
        self.before = {}
        self.waited = 0
        self.pos = {}
        self.queues = {}
        self.items = []
        self.rounds = 0
        self.retries = {}
        self.log = []
        self.resent = 0
        self.lost = 0
        self.local = {k: 0 for k in range(channels)}

    # --- 표지 블록 ---
    def _slot(self, base, k):
        return self.anchor + 4 * (base + k * self.core.table_players + self.player)

    def count(self, read, k):
        return read(self._slot(self.core.index["MsqcCount"], k))

    def echo(self, read, k):
        return read(self._slot(self.core.index["MsqcEcho"], k))

    def sync_toggles(self, read):
        for k in range(self.channels):
            n = self.count(read, k)
            self.toggle[k] = self.core.toggle_a if n % 2 == 0 else self.core.toggle_b

    # --- 일 ---
    def _plan_words(self, items):
        c = self.core
        queues = {k: [] for k in range(self.channels)}
        for n, (key, _addr, value) in enumerate(items):
            v = value & M32
            queues[n % self.channels] += [c.tag_key | (key & c.payload), c.tag_lo | (v & c.payload),
                                          c.tag_hi | ((v >> 16) & c.payload)]
        return queues

    def load(self, items):
        self.items = list(items)
        self.rounds = 0
        self.jobs.append(("words", self._plan_words(self.items)))
        self.jobs.append(("verify", None))

    def ready(self):
        self.jobs.append(("words", {0: [self.core.word_ready]}))

    def saved(self):
        self.jobs.append(("words", {0: [self.core.word_saved]}))

    @property
    def busy(self):
        return bool(self.jobs) or self.batch is not None

    def _next_batch(self, read):
        while self.jobs and self.batch is None:
            kind, data = self.jobs[0]
            if kind == "verify":
                self.jobs.pop(0)
                bad = [(k, a, v) for k, a, v in self.items if read(a) != v & M32]
                if bad and self.rounds < 2:
                    self.rounds += 1
                    self.log.append("어긋난 항목 %d개 - 다시 보냅니다" % len(bad))
                    self.items = bad
                    self.jobs.insert(0, ("verify", None))
                    self.jobs.insert(0, ("words", self._plan_words(bad)))
                    continue
                if bad:
                    self.log.append("경고: %d개 항목이 끝내 맞지 않았습니다" % len(bad))
                self.ready()
                continue
            if not self.queues:
                self.queues = {k: list(w) for k, w in data.items() if w}
                self.pos = {k: 0 for k in self.queues}
            batch = {k: self.queues[k][self.pos[k]] for k in self.queues if self.pos[k] < len(self.queues[k])}
            if not batch:
                self.jobs.pop(0)
                self.queues = {}
                continue
            self.batch = batch
            self.before = {k: self.count(read, k) for k in batch}
            self.waited = 0

    def frame(self, read):
        if None in self.toggle:
            self.sync_toggles(read)
        if self.batch is not None:
            self.waited += 1
            acked = {k for k in self.batch if self.count(read, k) != self.before[k]}
            if len(acked) == len(self.batch) or self.waited > self.timeout:
                c = self.core
                for k, w in self.batch.items():
                    self.toggle[k] = c.toggle_b if self.toggle[k] == c.toggle_a else c.toggle_a
                    ok = k in acked and self.echo(read, k) == (w & c.echo_mask)
                    if k not in acked:
                        self.lost += 1
                    if ok:
                        self.pos[k] += 1
                        self.retries[k] = 0
                    else:
                        self.resent += 1
                        self.retries[k] = self.retries.get(k, 0) + 1
                        if self.retries[k] > self.max_retry:
                            self.log.append("채널 %d 전송이 끊겼습니다" % k)
                            self.pos[k] = len(self.queues[k])
                self.batch = None
        if self.batch is None:
            self._next_batch(read)
        c = self.core
        for k in range(self.channels):
            if self.batch is not None and k in self.batch:
                self.local[k] = self.toggle[k] | (self.batch[k] & c.echo_mask)
            else:
                self.local[k] = 0
        return dict(self.local)
