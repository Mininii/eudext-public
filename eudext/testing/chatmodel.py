"""채팅 버퍼 모델 (DESIGN 5.1 표 "채팅 버퍼(0x640B60) 바이트 — 11줄·홀짝 정렬·0x640B58") — WP17.

에뮬레이터 메모리 위의 SC 채팅 버퍼를 읽고 쓰는 도우미와, 원본 채팅 효과 블록(HTextEff + CDPrint)을 파이썬으로 옮긴
참조 모델 `TypewriterRef` 를 둔다. `textfx`·`chat`·`misc.ObserverChat`(WP19) 시험이 쓴다.
공용 `scmodel.py` 대신 이 파일에 둔다(배치 E 에서 scmodel 은 WP11 몫).

    from eudext.testing import chatmodel
    suite = Suite("t_chat", memory={"text": True}, prep=lambda m: chatmodel.install(m))
    cm = chatmodel.chat_model(suite.machine)
    cm.push_line(b"\\r\\r!Hhello")        # SC 가 DisplayText 한 줄을 쓰는 것처럼: [0x640B58] 칸에 쓰고 포인터 +1
    cm.cells(3), cm.raw(3), cm.visible(3), cm.active(3), cm.hide(3)

## 모델 사실과 가정

| 항목 | 모델 | 근거 |
|---|---|---|
| 줄 k 원문 | `0x640B60 + 218·k`, 218바이트, NUL 로 끝남 | R4a E.1, CtrigAsm f_ChatOffset |
| 셀 정렬 | 짝수 줄 = 원문 0바이트부터, 홀수 줄 = +2 바이트부터 dword 54개 | CtrigAsm CDPrint 0x640B62, eudplib f_getnextchatdst |
| 다음 줄 | `[0x640B58]` = 다음에 쓸 slot(0~10). 한 줄 쓰면 +1, 11 이면 0 | eudplib cpprint.py f_gettextptr, CtrigAsm FixText |
| 줄이 꺼짐 | 원문 첫 바이트 = 0 | CtrigAsm `TTDisplay` 주석, R4a E.1 |
| DisplayText | CP == 이 PC 번호(0x512684)일 때만 글을 `\\n` 으로 나눠 줄마다 쓴다. 217바이트 넘으면 자른다 | SC 동작(가정: 폭에 따른 줄 넘김은 흉내 내지 않음) |
| 줄 뒤 바이트 | 새 줄을 쓸 때 NUL 뒤는 그대로 둔다(strcpy 가정, `clear_rest=True` 면 0) | **가정** |
| 표시 시간 | 메모리 위치 **미확인** → 파이썬 쪽 나이(`advance()`)로만 흉내, `expire` 프레임이 지나면 첫 바이트 0 | **가정** (R4a E.5) |
| 사용자 채팅 | `push_line(b"이름: 글")` 로 흉내(원문 앞에 이름이 붙는다 — 실제 바이트 배치는 인게임 확인 D17-5) | **가정** |

설치: `install(machine, display=True, next_line=None, lines=None, clear_rest=False, expire=None)` →
`machine.chat_model`(= `chat_model(machine)`). harness 에서는 `Suite(prep=lambda m: chatmodel.install(m))`
(scmodel 글 기록 `memory={"text": True}` 과 같이 쓰면 DisplayText 처리기를 이어 붙인다 — 기록도 남는다).
상태는 모두 에뮬레이터 메모리에 있어 스냅숏·`Suite.reset()` 으로 되돌아간다(줄 나이만 파이썬 쪽).
"""

from eudext import textfx as tfx
from eudext.testing import scmodel

__all__ = [
    "ACT_DISPLAY_TEXT",
    "CELLS",
    "CHAT_BUF",
    "ChatModel",
    "LINES",
    "LINE_BYTES",
    "NEXT_LINE_ADDR",
    "TypewriterRef",
    "chat_model",
    "install",
    "line_cell_addr",
    "line_ptr",
]

CHAT_BUF = 0x640B60
NEXT_LINE_ADDR = 0x640B58
LINE_BYTES = 218
LINES = 11
CELLS = 54
LOCAL_PLAYER_ADDR = 0x512684
CP_ADDR = 0x6509B0
ACT_DISPLAY_TEXT = 9
M32 = 0xFFFFFFFF


def line_ptr(slot):
    """줄 slot 의 원문 주소."""
    return CHAT_BUF + LINE_BYTES * slot


def line_cell_addr(slot, i):
    """줄 slot 의 셀 i 주소 (홀수 줄은 원문 +2 바이트부터)."""
    return line_ptr(slot) + (slot & 1) * 2 + 4 * i


def _visible_bytes(data):
    out = bytearray()
    for b in data:
        if b == 0:
            break
        if b < 0x20 and b != 0x0A:
            continue  # 색 코드·0x0D·정렬 코드는 보이지 않는다
        out.append(b)
    return bytes(out)


class ChatModel:
    """채팅 버퍼 읽기·쓰기 도우미 (`install` 이 만든다). 모듈 docstring 의 표가 모델의 사실·가정이다."""

    def __init__(self, machine, display=True, clear_rest=False, expire=None, strings=None):
        self.m = machine
        self.display = display
        self.clear_rest = clear_rest
        self.expire = expire
        self.age = [None] * LINES  # 파이썬 쪽 줄 나이(프레임) — 표시 시간 가정
        self.pushed = []  # (slot, bytes) 기록
        self._strings = strings

    # --- 주소·읽기 ---
    @staticmethod
    def line_ptr(slot):
        return line_ptr(slot)

    @staticmethod
    def cell_addr(slot, i):
        return line_cell_addr(slot, i)

    def raw(self, slot, n=LINE_BYTES):
        """줄 원문 바이트(기본 218바이트)."""
        return self.m.read_bytes(line_ptr(slot), n)

    def text(self, slot):
        """줄 원문의 NUL 앞까지."""
        r = self.raw(slot)
        i = r.find(b"\0")
        return r if i < 0 else r[:i]

    def cell(self, slot, i):
        return self.m.dw(line_cell_addr(slot, i))

    def cells(self, slot, n=CELLS):
        return [self.cell(slot, i) for i in range(n)]

    def set_cell(self, slot, i, value):
        self.m.setdw(line_cell_addr(slot, i), value)

    def set_cells(self, slot, values, start=0):
        for j, v in enumerate(values):
            self.set_cell(slot, start + j, v)

    def active(self, slot):
        """줄이 떠 있는가 (원문 첫 바이트 ≠ 0)."""
        return self.m.db(line_ptr(slot)) != 0

    def hide(self, slot):
        """줄을 끈다 (원문 첫 바이트 = 0, SC 표시 시간이 끝난 것처럼)."""
        self.m.setdb(line_ptr(slot), 0)
        self.age[slot] = None

    def unhide(self, slot, first):
        """꺼진 줄의 첫 바이트를 되돌린다 (시험용 — SC 가 하는 일은 아니다)."""
        self.m.setdb(line_ptr(slot), first)

    def visible(self, slot):
        """화면에 보일 글(원문에서 NUL 앞, 0x0D·색 코드·U+200B 를 뺀 것)을 str 로. 꺼진 줄은 ''."""
        if not self.active(slot):
            return ""
        return _visible_bytes(self.raw(slot)).decode("utf-8", "replace").replace("\u200b", "")

    @property
    def next_slot(self):
        return self.m.dw(NEXT_LINE_ADDR)

    @next_slot.setter
    def next_slot(self, v):
        self.m.setdw(NEXT_LINE_ADDR, v % LINES)

    def row_slot(self, row):
        """화면 위치 row 의 slot (CtrigAsm CD__GetLine 식)."""
        return (row + self.next_slot) % LINES

    def buffer(self):
        """비교용: 11줄 원문 전체 바이트."""
        return self.m.read_bytes(CHAT_BUF, LINE_BYTES * LINES)

    # --- 쓰기 ---
    def write_raw(self, slot, data, clear_rest=None):
        """줄 slot 에 원문을 쓴다(포인터는 그대로). data 뒤에 NUL 하나. 217바이트 넘으면 자른다."""
        data = bytes(data)[: LINE_BYTES - 1]
        clear = self.clear_rest if clear_rest is None else clear_rest
        body = data + b"\0"
        if clear:
            body = body + bytes(LINE_BYTES - len(body))
        self.m.write_bytes(line_ptr(slot), body)
        self.age[slot] = 0

    def push_line(self, data):
        """SC 가 한 줄을 띄우는 것처럼: slot = [0x640B58] 에 쓰고 포인터 +1(11 → 0). 반환: slot."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        slot = self.next_slot % LINES
        self.write_raw(slot, data)
        self.next_slot = slot + 1
        self.pushed.append((slot, bytes(data)))
        return slot

    def push_text(self, text):
        """DisplayText 한 번: `\\n` 으로 나눈 줄마다 push_line. 반환: slot 목록."""
        if isinstance(text, str):
            text = text.encode("utf-8")
        return [self.push_line(part) for part in bytes(text).split(b"\n")]

    def clear(self, next_line=0):
        """버퍼 전체를 0 으로, 포인터 = next_line."""
        self.m.write_bytes(CHAT_BUF, bytes(LINE_BYTES * LINES))
        self.next_slot = next_line
        self.age = [None] * LINES

    def advance(self, frames=1):
        """파이썬 쪽 줄 나이를 늘리고, `expire` 가 있으면 그보다 오래된 줄을 끈다(표시 시간 가정)."""
        for s in range(LINES):
            if self.age[s] is None:
                continue
            self.age[s] += frames
            if self.expire is not None and self.age[s] >= self.expire:
                self.hide(s)

    # --- DisplayText 훅 ---
    def _string(self, sid):
        if self._strings is None:
            tm = scmodel.text_model(self.m)
            self._strings = tm.strings if tm is not None else scmodel.string_table()
        return self._strings.get(sid)

    def on_display(self, fields):
        if not self.display:
            return
        if self.m.dw(CP_ADDR) != self.m.dw(LOCAL_PLAYER_ADDR):
            return
        s = self._string(fields[1])
        if s is not None:
            self.push_text(s)


def chat_model(machine):
    """machine 에 끼운 ChatModel (없으면 None)."""
    return getattr(machine, "chat_model", None)


def install(machine, display=True, next_line=None, lines=None, clear_rest=False, expire=None, strings=None):
    """채팅 버퍼 모델을 machine 에 끼운다. 반환: ChatModel (`machine.chat_model` 에도 둔다).

    인자: display(DisplayText 를 버퍼에 쓸지), next_line(주면 0x640B58 을 그 값으로),
          lines({slot: bytes} — 미리 쓸 줄, 포인터는 그대로), clear_rest(새 줄의 NUL 뒤를 0 으로),
          expire(표시 시간 가정 — 프레임), strings({번호: bytes} — 없으면 글 기록 모델 또는 지금 맵에서 읽는다)
    처리기: DisplayText(9) — 이미 처리기가 있으면(scmodel 글 기록) 먼저 그것을 부른다.
    """
    model = ChatModel(machine, display=display, clear_rest=clear_rest, expire=expire, strings=strings)
    if getattr(machine, "chat_model", None) is not None and hasattr(machine, "_chatmodel_prev"):
        prev = machine._chatmodel_prev  # 다시 끼울 때는 앞 채팅 모델 처리기를 잇지 않는다
        if machine.act_handlers.get(ACT_DISPLAY_TEXT) is not machine._chatmodel_handler:
            prev = machine.act_handlers.get(ACT_DISPLAY_TEXT)  # 그 사이 다른 모델(글 기록)이 새로 끼워졌다
    else:
        prev = machine.act_handlers.get(ACT_DISPLAY_TEXT)
    machine.chat_model = model

    def handler(m, fields, prev=prev):
        if prev is not None:
            prev(m, fields)
        m.chat_model.on_display(fields)

    machine.act_handlers[ACT_DISPLAY_TEXT] = handler
    machine._chatmodel_prev = prev
    machine._chatmodel_handler = handler
    if next_line is not None:
        model.next_slot = next_line
    for slot, data in (lines or {}).items():
        model.write_raw(slot, data)
    return model


# =============================================================================================
# 참조 타자기 (원본 동작)
# =============================================================================================


def _is_blank(c):
    return (c & 0xFFFFFF00) == 0x0D0D0D00


def _is_space(c):
    return (c & 0x0000FF00) == 0x00002000


class TypewriterRef:
    """원본 채팅 효과 블록의 한 사이클(MSF_Respect_V/GunData.lua:2879~2936 + CDPrint, UERE 속도·소리)을 파이썬으로.

    원본처럼 드러내는 줄의 셀 1..52 를 **매 프레임 다시** 쓴다(eudext 구현은 새 셀만 쓴다 — 버퍼 결과가 같아야 한다).
    인자: `chat.Typewriter` 와 같은 뜻(marker, speed, erase, sound(bool — 소리 횟수만 센다), nul_cell, rule, every)
    사용: `ref.frame(cm, run=True)` — run=False 면 아무것도 안 한다(대상 밖·enable 거짓)
    """

    def __init__(self, marker=b"\r\r!H", speed=1, erase=2, sound=False, nul_cell=True, rule="ctrig", every=None):
        self.marker = marker.encode("utf-8") if isinstance(marker, str) else bytes(marker)
        self.speed = speed
        self.erase = erase
        self.sound = sound
        self.nul_cell = nul_cell
        self.rule = rule
        self.every = every
        self.st = [0] * LINES
        self.k = [0] * LINES
        self.arch = [[tfx.BLANK] * 52 for _ in range(LINES)]
        self.tc = 0
        self.sounds = 0

    def frame(self, cm, run=True):
        if not run:
            return
        due = True
        if self.every is not None:
            self.tc = max(self.tc - 1, 0)
            due = self.tc == 0
        for s in range(LINES):
            raw = cm.raw(s)
            cell0 = cm.cell(s, 0)
            h = self.st[s]
            if raw.startswith(self.marker):
                h = 3
            elif not tfx.is_marker_cell(cell0):
                h = 0
            if h == 3:
                if (cell0 & 0xF0FFFF00) != 0x8080E200:
                    self._convert(cm, s)
                elif cm.active(s) and tfx.is_marker_cell(cell0):
                    self._reveal(cm, s, due)
            self.st[s] = h
        if self.nul_cell:
            for s in range(LINES):
                cm.set_cell(s, 53, 0)
        if self.every is not None and self.tc == 0:
            self.tc = self.every

    def _convert(self, cm, s):
        self.k[s] = 0
        data = cm.m.read_bytes(line_ptr(s), LINE_BYTES + 16)  # 스캐너는 NUL 뒤 몇 바이트까지 앞보기한다
        res = tfx.scan_const(data, 52, self.rule)
        arch = [tfx.BLANK] * 52
        arch[: len(res.cells)] = res.cells
        for idx, color in res.extra.items():
            if idx < 52:
                arch[idx] = (arch[idx] & ~0xFF) | color
        for i in range(self.erase):
            arch[i] = tfx.BLANK
        self.arch[s] = arch
        cm.set_cells(s, [tfx.MARK_U200B] + [tfx.BLANK] * 52 + [0])

    def _reveal(self, cm, s, due):
        k = self.k[s]
        line = [tfx.BLANK] * 52
        line[:k] = self.arch[s][:k]
        cm.set_cells(s, line, start=1)
        if k <= 51 and due:
            if self.sound and k >= 1:
                c = self.arch[s][k - 1]
                if not _is_blank(c) and not _is_space(c):
                    self.sounds += 1
            self.k[s] = min(k + self.speed, 52)
