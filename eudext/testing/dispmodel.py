"""표시 모델 (DESIGN 5.1 표 "DisplayText 캡처 — 표시 대상 판정·13번째 줄·TBL") — WP6b.

scmodel 의 글 기록(WP11)은 문자열을 **빌드 직후 표**에서 읽는다. display 는 문자열 버퍼(맵 문자열 메모리)를 실행 중에 고치므로
이 모델은 게임처럼 문자열 표를 메모리에 올리고 **DisplayText 순간의 메모리**를 읽는다. 공용 `scmodel.py`·`chatmodel.py` 는
고치지 않고 처리기를 이어 붙인다(`chatmodel.install(m, strings=live_strings(m))` 로 채팅 줄도 실행 중 글로 쓸 수 있다).

    from eudext.testing import dispmodel
    suite = Suite("t_display", memory={"text": True, "units": {}}, prep=lambda m: dispmodel.install(m, tbl={92: (b"old", 64)}))
    dm = dispmodel.disp_model(suite.machine)
    dm.shown()            # 이 PC 화면에 뜬 글(바이트) 목록 — CP == 이 PC 번호인 DisplayText
    dm.line13()           # 0x641598 의 C 문자열, dm.line13_shown = 이 PC 에서 CCMU 가 난 횟수
    dm.tbl(92)            # TBL 92 번 문자열(NUL 까지), dm.tbl_raw(92) = 자리 전체

## 모델 사실과 가정

| 항목 | 모델 | 근거 |
|---|---|---|
| 맵 문자열 메모리 | STRx 구역 전체를 0x191943C8 에 올린다(`install` 때) | eudplib `string/cpstr.py` `_STR_ADDRESS` |
| DisplayText(9) | 문자열 번호의 주소에서 NUL 까지 읽는다(최대 `max_text` 바이트). 보임 = CP == 이 PC 번호(0x512684) | SC 동작(G8 1.5), 관전자 CP 128~131 도 같은 규칙(**인게임 확인 E6-1**) |
| PlayWAV(8) | 소리 이름(빌드 표) 기록, 들림 = CP == 이 PC 번호 | 같음 |
| CreateUnit(44) 실패 | `[0x628438] == 0` 이면 실패. 플레이어(13 = CP)가 이 PC 면 **그 순간** 13번째 줄(0x641598)에 `CCMU_TEXT` + NUL 을 쓰고 표시 횟수를 센다 | **가정**(G8 1.7 — SC 가 오류 문구를 복사하고 표시 시간을 건다) |
| TBL | `[0x6D5A30]` = 가짜 stat_txt 주소, 0 번 word = 개수, 2·id 번째 word = 오프셋(id 는 1부터). 문자열 자리 뒤는 `?` 로 채워 넘침·잔재를 본다. 오프셋은 일부러 4 배수가 아니게 둘 수 있다(`misalign`) | eudplib `GetTBLAddr`(string/tblprint.py:30), S3 8.1 `tbl_layout` |
| 이름 | 0x57EEEB + 36p(eudplib·display) 와 0x6D0FDC + 36p(DPL·numfmt.dp.name20)에 같은 25바이트 | S3 11-1 (두 표가 같다는 것은 **인게임 확인 E6-5**) |

상태는 모두 에뮬레이터 메모리에 있어 `Suite.reset()`/`restart()` 로 되돌아간다(기록 `records` 와 `line13_shown` 만 파이썬 쪽 — `clear()`).
"""

from collections import namedtuple

from eudext.testing import scmodel

__all__ = [
    "CCMU_TEXT",
    "DispModel",
    "DispRecord",
    "LINE13_ADDR",
    "LiveStrings",
    "NAME_ADDR",
    "NAME_TABLE_DPL",
    "STR_ADDR",
    "TBL_BASE",
    "TBL_PTR_ADDR",
    "disp_model",
    "install",
    "live_strings",
    "visible",
]

STR_ADDR = 0x191943C8
TBL_PTR_ADDR = 0x6D5A30
TBL_BASE = 0x1C000000
LINE13_ADDR = 0x641598
LINE_BYTES = 218
NAME_ADDR = 0x57EEEB
NAME_TABLE_DPL = 0x6D0FDC
NAME_STRUCT = 36
CP_ADDR = 0x6509B0
LOCAL_PLAYER_ADDR = 0x512684
FIRST_UNUSED = 0x628438
ACT_PLAY_WAV = 8
ACT_DISPLAY_TEXT = 9
ACT_CREATE_UNIT = 44
CCMU_TEXT = b"\x06<CCMU>"
M32 = 0xFFFFFFFF

DispRecord = namedtuple("DispRecord", "kind cp local shown strid data cycle")
DispRecord.__doc__ = """표시 모델 기록 한 줄.

kind: "text" | "wav" | "ccmu", cp: 실행 때 CP, local: 이 PC 번호, shown: 이 PC 화면에 보이나(들리나),
strid: 문자열 번호(ccmu 는 None), data: 글 바이트(text — 실행 순간 메모리) / 소리 이름 / CreateUnit 플레이어(ccmu), cycle: 사이클
"""


def visible(data):
    """글 바이트 → 화면에 보이는 글(str): NUL 앞까지, 0x01~0x1F(줄바꿈 제외)·0x0D 를 뺀다."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    end = data.find(b"\0")
    if end >= 0:
        data = data[:end]
    return bytes(b for b in data if b >= 0x20 or b == 0x0A).decode("utf-8", "replace")


def _cstr(m, addr, limit):
    out = bytearray()
    for i in range(limit):
        b = m.db(addr + i)
        if b == 0:
            break
        out.append(b)
    return bytes(out)


class LiveStrings:
    """{문자열 번호: 실행 중 메모리의 글} 처럼 쓰는 보기 (`chatmodel.install(strings=…)` 에 넘긴다)."""

    def __init__(self, model):
        self.model = model

    def get(self, sid, default=None):
        return self.model.string(sid, default)

    def __getitem__(self, sid):
        r = self.model.string(sid)
        if r is None:
            raise KeyError(sid)
        return r


class DispModel:
    """표시 모델 (`install` 이 만든다). 모듈 docstring 의 표가 사실·가정이다."""

    def __init__(self, machine, max_text=2048):
        self.m = machine
        self.max_text = max_text
        self.records = []
        self.line13_shown = 0
        self.offsets = {}
        self.static = {}
        self.tbl_entries = {}

    # --- 문자열 ---
    def load_strings(self):
        import struct

        from eudext import _compat

        sec = bytes(_compat.chk_string_section())
        wide = _compat.chk_string_section_name() == "STRx"
        fmt, size = ("<I", 4) if wide else ("<H", 2)
        self.m.write_bytes(STR_ADDR, sec)
        n = struct.unpack_from(fmt, sec, 0)[0] if len(sec) >= size else 0
        self.offsets = {}
        for i in range(1, n + 1):
            if size * (i + 1) > len(sec):
                break
            self.offsets[i] = struct.unpack_from(fmt, sec, size * i)[0]
        self.static = scmodel.string_table()

    def string_addr(self, sid):
        off = self.offsets.get(sid)
        return None if off is None else STR_ADDR + off

    def string(self, sid, default=None):
        """문자열 번호의 지금 메모리 글(NUL 앞까지)."""
        a = self.string_addr(sid)
        if a is None:
            return default
        return _cstr(self.m, a, self.max_text)

    # --- 처리기 ---
    def _cycle(self):
        return len(self.m.ends)

    def _local(self):
        return self.m.dw(LOCAL_PLAYER_ADDR)

    def on_display(self, fields):
        sid = fields[1]
        cp, local = self.m.dw(CP_ADDR), self._local()
        self.records.append(DispRecord("text", cp, local, cp == local, sid, self.string(sid, b""), self._cycle()))

    def on_wav(self, fields):
        wid = fields[2]
        cp, local = self.m.dw(CP_ADDR), self._local()
        name = self.static.get(wid, b"")
        self.records.append(DispRecord("wav", cp, local, cp == local, wid, name, self._cycle()))

    def on_create(self, fields):
        if self.m.dw(FIRST_UNUSED) != 0:
            return
        player = fields[4]
        if player == 13:
            player = self.m.dw(CP_ADDR)
        local = self._local()
        shown = player == local
        self.records.append(DispRecord("ccmu", self.m.dw(CP_ADDR), local, shown, None, player, self._cycle()))
        if shown:
            self.m.write_bytes(LINE13_ADDR, CCMU_TEXT + b"\0")
            self.line13_shown += 1

    # --- 읽기 ---
    def texts(self, cp=None, shown=None):
        return [
            r.data for r in self.records
            if r.kind == "text" and (cp is None or r.cp == cp) and (shown is None or r.shown == shown)
        ]  # fmt: skip

    def shown(self):
        """이 PC 화면에 뜬 글 목록(바이트)."""
        return self.texts(shown=True)

    def wavs(self, shown=None):
        return [r.data for r in self.records if r.kind == "wav" and (shown is None or r.shown == shown)]

    def ccmu(self):
        """CreateUnit 실패 기록 [(플레이어, 보임)]."""
        return [(r.data, r.shown) for r in self.records if r.kind == "ccmu"]

    def line13(self):
        return _cstr(self.m, LINE13_ADDR, LINE_BYTES)

    def line13_raw(self, n=LINE_BYTES + 2):
        return self.m.read_bytes(LINE13_ADDR, n)

    def clear(self):
        del self.records[:]
        self.line13_shown = 0

    # --- 이름 ---
    def set_names(self, names):
        """{p: bytes} 를 두 이름 표에 쓴다(25바이트 칸, 뒤는 0). 이름이 25바이트면 NUL 이 없다."""
        for p, name in names.items():
            if isinstance(name, str):
                name = name.encode("utf-8")
            name = bytes(name)[:25]
            body = name + bytes(25 - len(name))
            self.m.write_bytes(NAME_ADDR + NAME_STRUCT * p, body)
            self.m.write_bytes(NAME_TABLE_DPL + NAME_STRUCT * p, body)

    def set_name_raw(self, p, raw):
        """0x57EEEB 칸에 바이트를 그대로 쓴다(NUL 뒤 잔재 시험용)."""
        self.m.write_bytes(NAME_ADDR + NAME_STRUCT * p, bytes(raw))

    # --- TBL ---
    def set_tbl(self, entries, misalign=True):
        """{id: bytes | (bytes, 자리 크기)} 로 가짜 stat_txt 를 만든다. 자리 뒤 4바이트까지 `?` 로 채운다."""
        count = max(entries) if entries else 0
        base = TBL_BASE
        pos = 2 * (count + 1) + 8
        self.m.setdw(TBL_PTR_ADDR, base)
        self.m.write_bytes(base, (count & 0xFFFF).to_bytes(2, "little"))
        self.tbl_entries = {}
        for tid in range(1, count + 1):
            e = entries.get(tid, b"")
            data, cap = (e if isinstance(e, tuple) else (e, len(e) + 1))
            data = data.encode("utf-8") if isinstance(data, str) else bytes(data)
            if misalign and pos % 4 == 0:
                pos += 1
            self.m.write_bytes(base + 2 * tid, (pos & 0xFFFF).to_bytes(2, "little"))
            body = (data + b"\0")[:cap].ljust(cap, b"?") + b"????"
            self.m.write_bytes(base + pos, body)
            self.tbl_entries[tid] = (pos, cap)
            pos += cap + 4

    def tbl_addr(self, tid):
        return TBL_BASE + self.tbl_entries[tid][0]

    def tbl(self, tid):
        pos, cap = self.tbl_entries[tid]
        return _cstr(self.m, TBL_BASE + pos, cap + 4)

    def tbl_raw(self, tid, extra=4):
        pos, cap = self.tbl_entries[tid]
        return self.m.read_bytes(TBL_BASE + pos, cap + extra)


def disp_model(machine):
    """machine 에 끼운 DispModel (없으면 None)."""
    return getattr(machine, "disp_model", None)


def live_strings(machine):
    """실행 중 메모리 글 보기 — `chatmodel.install(machine, strings=live_strings(machine))`."""
    return LiveStrings(machine.disp_model)


def install(machine, tbl=None, names=None, max_text=2048, misalign=True):
    """표시 모델을 끼운다. 반환: DispModel (`machine.disp_model`).

    인자: tbl({id: bytes | (bytes, 자리 크기)} — 주면 가짜 stat_txt), names({p: bytes} — 두 이름 표),
          max_text(DisplayText 로 읽을 최대 바이트), misalign(TBL 오프셋을 4 배수가 아니게)
    처리기: DisplayText(9)·PlayWAV(8)·CreateUnit(44) — 이미 있는 처리기(scmodel 글 기록·유닛 모델)를 **먼저** 부른다.
    CreateUnit 은 유닛 모델보다 먼저 실패 여부를 본다(유닛 모델이 0x628438 을 바꾸기 전).
    """
    model = DispModel(machine, max_text=max_text)
    machine.disp_model = model
    model.load_strings()
    prev = {k: machine.act_handlers.get(k) for k in (ACT_DISPLAY_TEXT, ACT_PLAY_WAV, ACT_CREATE_UNIT)}
    for k in prev:
        if prev[k] is not None and getattr(prev[k], "_dispmodel", False):
            prev[k] = prev[k]._prev  # 다시 끼울 때는 앞 표시 모델을 잇지 않는다

    def h_text(m, f, prev=prev[ACT_DISPLAY_TEXT]):
        if prev is not None:
            prev(m, f)
        m.disp_model.on_display(f)

    def h_wav(m, f, prev=prev[ACT_PLAY_WAV]):
        if prev is not None:
            prev(m, f)
        m.disp_model.on_wav(f)

    def h_create(m, f, prev=prev[ACT_CREATE_UNIT]):
        m.disp_model.on_create(f)
        if prev is not None:
            prev(m, f)

    for k, h in ((ACT_DISPLAY_TEXT, h_text), (ACT_PLAY_WAV, h_wav), (ACT_CREATE_UNIT, h_create)):
        h._dispmodel = True
        h._prev = prev[k]
        machine.act_handlers[k] = h
    if tbl:
        model.set_tbl(tbl, misalign=misalign)
    if names:
        model.set_names(names)
    return model
