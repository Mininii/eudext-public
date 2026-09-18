"""bgm — 배경음악: 곡 표(길이 자동 측정)·조각 이어 재생·돌려 쓰기·플레이어별 재생·관전자 끄기 (DESIGN 4.17, S5 B절).

정본 명세는 `docs/spec/S5_dat_bgm.md` B절(B.9 API, B.10 시험 기대값, B.11 인게임).

    from eudext import bgm, sync, players as pl

    OP   = bgm.track("GRAVITY_OP.ogg")                       # MPQAddWave("staredit\\wav\\GRAVITY_OP.ogg", 절대 경로), 길이 자동
    BOSS = bgm.track("SBoss.ogg", length_ms=368000)          # 수동 길이 (옛 맵 값 이식)
    LV10 = bgm.chunks("LV10_{:03d}.ogg", range(1, 273))      # 조각 이어 재생 (조각마다 실측 길이)
    ROT  = bgm.rotation(["BGM1_1.ogg", "BGM1_2.ogg"], length_ms=45000)   # 요청마다 돌아가며

    bus = sync.Bus("msqc", qc_unit=49)
    player = bgm.Player(mode="synced", targets=pl.humans(),
                        elapsed=bus.value(bgm.clock.local_dt(), latch=True))

    def beforeTriggerExec():
        player.tick()                                        # 사이클마다 한 번
        if EUDIf()(boss_appeared):
            player.request(BOSS)                             # 공유 요청 (전원)
        EUDEndIf()

epScript:

    import eudext.bgm as bgm;
    const OP = bgm.track("GRAVITY_OP.ogg");                  // → bgm.f_track
    const LV = bgm.chunks("LV10_{:03d}.ogg", 1, 273);        // (또는 py_range(1, 273))
    const player = bgm.Player(mode="local", targets="all");
    function beforeTriggerExec() { player.tick(); }
    function afterTriggerExec() { if (…) { player.request(OP); } }

## 두 모드 (DESIGN 3.7)

| | `local` (TPL `IBGM_EPD` 방식) | `synced` (LIB `Install_BGMSystem` + `IBGM_EPDX` 방식) |
|---|---|---|
| 남은 시간·곡·조각 | **이 PC 의 로컬 메모리** (각 PC 가 자기 사용자 몫 한 칸만) | **공유 메모리**, 플레이어별 칸(0~7) + 관전자 칸(8) |
| 줄어드는 양 | 이 PC 의 실제 경과 ms(`bgm.clock.local_dt()`) | `elapsed`(동기화된 값 — 보통 `bus.value(bgm.clock.local_dt(), latch=True)` 의 방장 몫) |
| 요청·끔 비트 | 공유 칸 (모든 PC 가 같게 지운다) | 공유 칸 |
| `current/chunk/remaining/is_playing` | 로컬 값(`LocalValue`/`LocalCondition`) — 표시에만 | 공유 안전 — 보스 패턴 동기화에 쓸 수 있다 |

- 소리는 **로컬 사용자에게만** 낸다: 재생 함수가 CP 를 `f_getuserplayerid()` 로 잠깐 바꾸고 되돌린다(DESIGN 3.6 —
  eudplib `PlayWAVAll` 은 CP 를 되돌리지 않는다). 끈 플레이어(`mute`)·관전자 로컬 끄기(`observer_toggle_key`)는 소리만 막고
  곡 상태는 그대로 흐른다(다시 켜면 다음 조각·곡부터 들린다).
- 재생 본문은 **곡 수·대상 수와 무관한 1벌**이다: 칸 루프(CP = 기록 EPD + 칸)와 공유 함수 3개(`start`, `play_mine`, 재생).
  곡 표 = `EUDArray` 두 개(길이, 문자열 번호 — 문자열 표는 `method="patch"` 일 때만) + 곡별 (시작 칸, 개수, 돌려 쓰기 칸).
- 요청 처리는 `tick()` 안에서만 한다: `request/stop/loop` 는 요청 칸에 쓰기만 하고 다음 `tick()` 이 적용한다.
- 재생 방식(7절 D18): `method="switch"`(기본, `EUDSwitch` 로 칸마다 `PlayWAV` 트리거 — 확실) /
  `method="patch"`(문자열 번호를 읽어 `PlayWAV` 한 트리거의 문자열 칸을 채움 — **인게임 D16-1 확인 전에는 쓰지 않는다**).
- 한 곡의 기록 칸: 남은 ms(REM), 곡(SONG), 표 칸(SLOT), 조각 번호(CHUNK), 남은 조각 수(LEFT), 반복(LOOP), 끔(MUTE), 요청(REQ),
  대상(EN), 돌려 쓰기 카운터(곡마다 1). 끔 비트는 타이머와 다른 칸이다(S5 B.12 — LIB 는 같은 dword 라 끈 플레이어가 늘 "재생 중").

## 소리 파일 (S5 B.6)

- `track`/`chunks`/`rotation` 이 **선언하는 순간** `MPQAddWave(이름, 절대 경로)` 를 부른다(euddraft 는 맵을 먼저 읽고 플러그인을
  불러오므로 된다 — 2026-09-17 실측). 같은 이름을 두 번 넣으면 eudplib 중복 오류(`EPError`, S5 B.10).
  같은 프로세스에서 `LoadMap` 을 다시 하면 eudplib 이 목록을 비우므로, 빌드마다 표를 굳힐 때 빠진 파일을 다시 넣는다.
- 이름 규칙: 기본 `staredit\\wav\\<파일명>`(옛 맵 `PlayWAV` 문자열과 같음). `mpq_name=` 으로 바꾼다. 맵에 이미 든 소리는 `add=False`.
- 길이: `struct` 로 헤더만 읽는다(번들 파이썬에 `wave` 모듈이 없다, DESIGN 2.4). 형식은 확장자가 아니라 앞 4바이트
  (`RIFF` = WAV: data 크기 ÷ 프레임 크기 ÷ 표본율 — PCM 이 아니면 fact 표본 수 또는 byte rate, `OggS` = Ogg: 마지막 페이지
  granule ÷ 표본율(Vorbis·FLAC), Opus 는 (granule − pre-skip) ÷ 48000). **내림 정수 ms**. 모르는 형식은 `length_ms` 가 있어야 한다.
- 옛 맵은 길이를 실제보다 짧게 적곤 했다(곡 사이 겹침) → `length_ms`(수동)와 `trim_ms`(자동 − n)를 둘 다 둔다.

## 시계 (`bgm.clock`, NormalTurboSet 대체 — 7절 D20)

- `local_dt()`: 이 PC 의 지난 사이클 이후 실제 ms(`0x51CE8C` 아래 16비트 차이). **로컬 값** — 공유 로직에 쓰지 않는다(S5 B.12).
- `half()`: 사이클마다 0/1 이 번갈아 나오는 공유 조건(참 = 1 인 사이클). `dt2(elapsed)`: 연속 두 사이클 합(1 인 사이클에 갱신).
- `update()`: 위 값을 갱신하는 코드(빌드에 한 번). `Player.tick()` 이 자동으로 낸다.

출처: TPL `func.lua:843~953` IBGM_EPD(로컬형), LIB `LibraryFor322.lua:765~957` AddBGM·Install_BGMSystem·NormalTurboSet,
UERE `func.lua:431~460` IBGM_EPDX, M2 `System.lua:117~150`(조각 이어 재생), euddraft `plugins/bgmplayer.py`(0x51CE8C 타이머),
`lib/soundlooper.py`(EUDSwitch 로 조각마다 PlayWAV). DPS 이식판(e7efff2)에는 BGM 코드가 없어 새로 작성했다.
"""

import os
import struct
import sys

from eudplib import (
    EPD,
    AddCurrentPlayer,
    AtLeast,
    AtMost,
    CurrentPlayer,
    Db,
    Deaths,
    DoActions,
    EncodePlayer,
    EPError,
    EUDArray,
    EUDBranch,
    EUDBreak,
    EUDElse,
    EUDElseIf,
    EUDEndIf,
    EUDEndSwitch,
    EUDFunc,
    EUDIf,
    EUDJump,
    EUDJumpIf,
    EUDJumpIfNot,
    EUDOnStart,
    EUDReturn,
    EUDSwitch,
    EUDSwitchCase,
    EUDVariable,
    EncodeString,
    Exactly,
    ExprProxy,
    Forward,
    Memory,
    MemoryEPD,
    MPQAddWave,
    MPQCheckFile,
    NextTrigger,
    PlayWAV,
    RawTrigger,
    SeqCompute,
    SetCurrentPlayer,
    SetDeaths,
    SetMemory,
    SetNextPtr,
    SetTo,
    Subtract,
    Add,
    f_dwread_cp,
    f_dwread_epd,
    f_dwwrite_epd,
    f_getcurpl,
    f_getuserplayerid,
    f_maskread_epd,
    f_setcurpl,
    unProxy,
)

from eudext import _compat, _parts
from eudext import local as _local
from eudext import players as _pl
from eudext import sync as _sync
from eudext.errors import EudextError, check_choice, fail

__all__ = [
    "BUSY_POLICIES",
    "METHODS",
    "MODES",
    "OBSERVER_CELL",
    "Player",
    "STOP_ID",
    "TIME_ADDR",
    "Track",
    "WAV_DIR",
    "chunks",
    "clock",
    "clock_update",
    "f_chunks",
    "f_clock_update",
    "f_measure_ms",
    "f_rotation",
    "f_set_dir",
    "f_songs",
    "f_sound_info",
    "f_table",
    "f_track",
    "measure_ms",
    "rotation",
    "set_dir",
    "songs",
    "sound_info",
    "table",
    "track",
]

WAV_DIR = "staredit\\wav\\"
TIME_ADDR = 0x51CE8C  # 실제 시간 ms 의 보수(시간이 흐르면 줄어든다) — bgmplayer: now = 0xFFFFFFFF − read
CP_ADDR = 0x6509B0

MODES = ("local", "synced")
BUSY_POLICIES = ("drop", "replace", "queue")
METHODS = ("switch", "patch")

# 기록 칸(유닛 자리 = 필드). 칸 k 의 필드 f 는 EPD(기록) + 12·f + k — CP = EPD(기록) + k 이면 Deaths(CurrentPlayer, …, f)
F_REM, F_SONG, F_SLOT, F_CHUNK, F_LEFT, F_LOOP, F_MUTE, F_REQ, F_EN = range(9)
F_ROT0 = 9  # 돌려 쓰기 곡 r 의 카운터 = 필드 F_ROT0 + r
STRIDE = 12
OBSERVER_CELL = 8  # 관전자(128~131) 몫 칸
NO_CELL = 9  # 이 PC 가 어느 칸에도 해당하지 않음

# 요청 값: 곡 번호(1~0xFFFE) | 반복 | 강제. 정지 = STOP_ID(+강제)
STOP_ID = 0xFFFF
REQ_LOOP = 0x10000
REQ_FORCE = 0x20000
MAX_SONGS = 0xFFFE

_TIME_MASK = 0xFFFF  # 경과 시간은 아래 16비트 차이로 잰다 (한 사이클에 65초 넘게 흐르지 않는다고 본다)


# =============================================================================================
# 소리 길이 (struct 만 — DESIGN 2.4)
# =============================================================================================


def _crc_table():
    tab = []
    for i in range(256):
        r = i << 24
        for _ in range(8):
            r = ((r << 1) ^ 0x04C11DB7) if r & 0x80000000 else (r << 1)
        tab.append(r & 0xFFFFFFFF)
    return tab


_OGG_CRC = _crc_table()


def _ogg_crc(data):
    crc = 0
    for b in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ _OGG_CRC[((crc >> 24) ^ b) & 0xFF]
    return crc


def _ogg_page(buf, pos, strict=True):
    """buf[pos:] 의 Ogg 페이지 → (granule, serial, flags, 전체 길이) 또는 None (CRC 까지 확인)."""
    if pos + 27 > len(buf) or buf[pos:pos + 4] != b"OggS" or buf[pos + 4] != 0:
        return None
    nseg = buf[pos + 26]
    if pos + 27 + nseg > len(buf):
        return None
    body = sum(buf[pos + 27:pos + 27 + nseg])
    total = 27 + nseg + body
    if pos + total > len(buf):
        return None
    if strict:
        page = bytearray(buf[pos:pos + total])
        want = struct.unpack_from("<I", page, 22)[0]
        page[22:26] = b"\0\0\0\0"
        if _ogg_crc(page) != want:
            return None
    granule, serial = struct.unpack_from("<qI", buf, pos + 6)
    return granule, serial, buf[pos + 5], total


def _ogg_info(f, size):
    head = f.read(min(size, 1 << 16))
    first = _ogg_page(head, 0, strict=False)
    if first is None:
        return None
    serial = first[1]
    nseg = head[26]
    body = head[27 + nseg:27 + nseg + 64]
    info = {"kind": "ogg", "channels": None}
    preskip = 0
    if body[:7] == b"\x01vorbis" and len(body) >= 16:
        info["codec"] = "vorbis"
        info["channels"] = body[11]
        rate = struct.unpack_from("<I", body, 12)[0]
    elif body[:8] == b"OpusHead" and len(body) >= 12:
        info["codec"] = "opus"
        info["channels"] = body[9]
        preskip = struct.unpack_from("<H", body, 10)[0]
        rate = 48000  # Opus granule 은 늘 48kHz
    elif body[:5] == b"\x7fFLAC" and len(body) >= 30:
        info["codec"] = "flac"
        rate = (body[27] << 12) | (body[28] << 4) | (body[29] >> 4)
        info["channels"] = ((body[29] >> 1) & 7) + 1
    else:
        return None
    if not rate:
        return None
    info["rate"] = rate
    # 마지막 페이지(같은 serial, granule ≥ 0)를 끝에서부터 찾는다. 창을 넓혀 가며.
    window = 1 << 16
    granule = None
    while granule is None:
        start = max(0, size - window)
        f.seek(start)
        buf = f.read(size - start)
        pos = buf.rfind(b"OggS")
        while pos >= 0:
            pg = _ogg_page(buf, pos)
            if pg is not None and pg[1] == serial and pg[0] >= 0:
                granule = pg[0]
                break
            pos = buf.rfind(b"OggS", 0, pos)
        if start == 0:
            break
        window <<= 2
    if granule is None:
        return None
    info["samples"] = max(granule - preskip, 0)
    info["ms"] = info["samples"] * 1000 // rate
    return info


def _wav_info(f, size):
    head = f.read(12)
    if len(head) < 12 or head[:4] != b"RIFF" or head[8:12] != b"WAVE":
        return None
    pos = 12
    fmt = None
    fact = None
    data = None
    while pos + 8 <= size:
        f.seek(pos)
        ch = f.read(8)
        cid = ch[:4]
        clen = struct.unpack_from("<I", ch, 4)[0]
        body = pos + 8
        remain = size - body
        if cid == b"fmt ":
            fb = f.read(min(clen, 64))
            if len(fb) < 14:
                return None
            tag, channels, rate, byte_rate, align = struct.unpack_from("<HHIIH", fb)
            bits = struct.unpack_from("<H", fb, 14)[0] if len(fb) >= 16 else 0
            if tag == 0xFFFE and len(fb) >= 26:  # WAVE_FORMAT_EXTENSIBLE → 부분 형식 GUID 앞 2바이트
                tag = struct.unpack_from("<H", fb, 24)[0]
            fmt = (tag, channels, rate, byte_rate, align, bits)
        elif cid == b"fact" and clen >= 4:
            fact = struct.unpack("<I", f.read(4))[0]
        elif cid == b"data":
            data = min(clen, remain)
            if clen > remain:  # 스트리밍 헤더(크기 미상) 또는 잘린 파일
                break
        if clen > remain:
            break
        pos = body + clen + (clen & 1)
    if fmt is None or data is None:
        return None
    tag, channels, rate, byte_rate, align, bits = fmt
    info = {"kind": "wav", "codec": "pcm" if tag in (1, 3) else "wav(0x%X)" % tag, "channels": channels, "rate": rate,
            "bits": bits}
    if tag in (1, 3) and align and rate:
        info["samples"] = data // align
        info["ms"] = info["samples"] * 1000 // rate
    elif fact is not None and rate:
        info["samples"] = fact
        info["ms"] = fact * 1000 // rate
    elif byte_rate:
        info["ms"] = data * 1000 // byte_rate
    else:
        return None
    return info


def f_sound_info(path):
    """소리 파일 헤더를 읽어 형식·길이를 돌려준다(형식은 앞 4바이트로 판별). 모르는 형식이면 None.

    인자: path(파일 경로)
    반환: dict(kind="wav"|"ogg", codec, channels, rate, ms(내림 정수), samples …) 또는 None
    비용: 없음(컴파일 시점, 파일 헤더와 끝 부분만 읽는다)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: S5 B.6 `bgm/measure_len.py`(640/641 성공), euddraft `lib/soundlooper.py`(tinytag 길이 측정)
    """
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        magic = f.read(4)
        f.seek(0)
        if magic == b"RIFF":
            return _wav_info(f, size)
        if magic == b"OggS":
            return _ogg_info(f, size)
    return None


def f_measure_ms(path):
    """소리 파일 길이(내림 정수 ms). 모르는 형식이면 EudextError.

    인자: path(파일 경로)
    반환: int
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const ms = bgm.measure_ms("a.ogg");` (→ `f_measure_ms`, 경로는 set_dir 기준이 아니다)
    출처: S5 B.6
    """
    info = f_sound_info(path)
    if info is None or "ms" not in info:
        fail("소리 길이를 잴 수 없습니다: %s (앞 4바이트가 RIFF/OggS 가 아니거나 헤더가 깨짐) — length_ms= 로 길이를 주세요", path)
    return info["ms"]


sound_info = f_sound_info
measure_ms = f_measure_ms


# =============================================================================================
# 곡 표 (컴파일 시점)
# =============================================================================================

_dir = [None]
_slots = []  # _Slot
_songs = []  # Track
_extra = []  # 곡 표 밖 소리 이름(busy_sound) — 재생 함수에만 칸이 생긴다
_HERE = os.path.dirname(os.path.abspath(__file__))


def _caller_dir():
    f = sys._getframe(1)
    while f is not None:
        fn = f.f_code.co_filename
        if fn and not fn.startswith("<") and "eudplib" not in fn and os.path.dirname(os.path.abspath(fn)) != _HERE:
            d = os.path.dirname(os.path.abspath(fn))
            if os.path.isdir(d):
                return d
        f = f.f_back
    return None


def f_set_dir(path):
    """상대 경로 소리 파일의 기준 폴더를 정한다(없으면 부른 파일의 폴더 → 작업 폴더 순서로 찾는다).

    인자: path(폴더. 상대 경로면 부른 파일의 폴더 또는 작업 폴더 기준), None 이면 기준 폴더 없음
    반환: 이전 값
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `bgm.set_dir("MSF_UE_RE_BGM");` (→ `f_set_dir`)
    출처: S5 B.9 (`bgm.set_dir`), 맵별 `*_BGMInput.py` 의 `Path :` 설정
    """
    old = _dir[0]
    if path is None:
        _dir[0] = None
        return old
    if not isinstance(path, str) or not path:
        fail("set_dir: 폴더 경로 문자열이어야 합니다 (%r)", path)
    p = path.replace("\\", "/") if os.sep == "/" else path
    if not os.path.isabs(p):
        base = _caller_dir()
        cand = [os.path.join(b, p) for b in (base, os.getcwd()) if b]
        found = [c for c in cand if os.path.isdir(c)]
        p = found[0] if found else cand[-1]
    if not os.path.isdir(p):
        fail("set_dir: 폴더가 없습니다: %s", p)
    _dir[0] = os.path.abspath(p)
    return old


set_dir = f_set_dir


def _resolve(file):
    p = file.replace("\\", "/") if os.sep == "/" else file
    if os.path.isabs(p):
        return p, [p]
    tried = []
    for base in (_dir[0], _caller_dir(), os.getcwd()):
        if base:
            c = os.path.abspath(os.path.join(base, p))
            if c not in tried:
                tried.append(c)
            if os.path.isfile(c):
                return c, tried
    return None, tried


class _Slot:
    __slots__ = ("add", "length", "name", "path", "song")

    def __init__(self, name, path, length, add):
        self.name = name
        self.path = path
        self.length = length
        self.add = add
        self.song = None


def _check_int(name, v, lo, hi):
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        fail("%s: %d ~ %d 정수여야 합니다 (%r)", name, lo, hi, v)
    return v


def _make_slot(file, length_ms, trim_ms, mpq_name, add):
    if not isinstance(file, str) or not file:
        fail("소리 파일 이름은 문자열이어야 합니다 (%r)", file)
    _check_int("trim_ms", trim_ms, 0, 0x7FFFFFFF)
    if length_ms is not None:
        _check_int("length_ms", length_ms, 1, 0x7FFFFFFF)
    path, tried = _resolve(file)
    if path is None and (add or length_ms is None):
        fail("소리 파일을 찾을 수 없습니다: %s (찾은 곳: %s) — bgm.set_dir() 로 폴더를 정하거나, 맵에 이미 든 소리면 "
             "add=False, length_ms= 를 주세요", file, ", ".join(tried) or "-")
    if length_ms is None:
        length = f_measure_ms(path)
    else:
        length = length_ms
    length -= trim_ms
    if length < 1:
        fail("%s: 길이 %d ms 에서 trim_ms %d 를 빼면 1 ms 보다 짧습니다", file, length + trim_ms, trim_ms)
    if mpq_name is None:
        mpq_name = WAV_DIR + os.path.basename(file.replace("\\", "/"))
    elif not isinstance(mpq_name, str) or not mpq_name:
        fail("mpq_name 은 문자열이어야 합니다 (%r)", mpq_name)
    return _Slot(mpq_name, path, length, bool(add))


def _norm_key(name):
    return name.replace("/", "\\").lower()


def _register(slots):
    """MPQAddWave 를 모두 부른다(하나라도 겹치면 아무것도 넣지 않고 오류)."""
    seen = set()
    for s in slots:
        k = _norm_key(s.name)
        if k in seen:
            fail("같은 MPQ 이름이 한 선언 안에 두 번 있습니다: %s", s.name)
        seen.add(k)
    for s in slots:
        if not s.add:
            continue
        try:
            MPQCheckFile(s.name)
        except EPError as e:
            raise EudextError(
                "MPQ 에 같은 이름의 파일이 이미 있습니다: %s — 같은 소리를 두 번 선언했거나 입력 맵에 들어 있습니다"
                "(입력 맵의 소리는 add=False). eudplib: %s" % (s.name, e)
            ) from e
    for s in slots:
        if s.add:
            MPQAddWave(s.name, s.path)


class Track(ExprProxy):
    """곡 하나(한 파일·조각 여럿·돌려 쓰기). `bgm.track/chunks/rotation` 이 만든다. 값은 곡 번호(1부터)다.

    `player.request(곡)` 에 넘기고, `player.current(p) == 곡` 처럼 번호로 비교할 수 있다(ExprProxy).
    인자: (내부에서 만든다)
    반환: -
    속성: `id`(곡 번호), `kind`("track"|"chunks"|"rotation"), `start`(첫 표 칸), `count`(칸 수), `names`, `lengths`, `files`
    비용: 없음(컴파일 시점). 표 칸 하나 = 길이 표 4B (+ patch 방식이면 문자열 표 4B)
    CP: 해당 없음
    로컬: 공유 안전
    epScript: `const OP = bgm.track("op.ogg");` → `player.request(OP);`, `if (player.current(0) == OP) { … }`
    출처: LIB `AddBGM`(번호 반환), TPL `WAVData` 표
    """

    __slots__ = ("count", "id", "kind", "rot", "start")

    def __init__(self, sid, kind, start, count, rot=None):
        super().__init__(sid)
        self.id = sid
        self.kind = kind
        self.start = start
        self.count = count
        self.rot = rot

    def __repr__(self):
        return "<bgm.Track %d %s %s×%d>" % (self.id, self.kind, self.names[0], self.count)

    def _slots(self):
        return _slots[self.start:self.start + self.count]

    @property
    def names(self):
        return [s.name for s in self._slots()]

    @property
    def lengths(self):
        return [s.length for s in self._slots()]

    @property
    def files(self):
        return [s.path for s in self._slots()]


def _add_song(kind, slots, rot=None):
    if len(_songs) >= MAX_SONGS:
        fail("곡은 %d 개까지입니다", MAX_SONGS)
    _register(slots)
    t = Track(len(_songs) + 1, kind, len(_slots), len(slots), rot)
    for s in slots:
        s.song = t
    _slots.extend(slots)
    _songs.append(t)
    return t


def f_track(file, length_ms=None, trim_ms=0, mpq_name=None, add=True):
    """곡 하나를 선언한다: MPQ 에 넣고(`MPQAddWave(이름, 절대 경로)`) 길이를 잰다.

    인자: file(파일 경로 — 상대 경로는 set_dir → 부른 파일 폴더 → 작업 폴더), length_ms(수동 길이, 없으면 자동 측정),
          trim_ms(길이에서 뺄 ms), mpq_name(기본 `staredit\\wav\\<파일명>`), add(False = 맵에 이미 든 소리 — 넣지 않음)
    반환: Track (곡 번호 = 선언 순서, 1부터)
    비용: 없음(컴파일 시점). 표 칸 1
    CP: 해당 없음
    로컬: 공유 안전
    epScript: `const OP = bgm.track("GRAVITY_OP.ogg");` (→ `f_track`)
    출처: LIB `AddBGM(번호, 파일, ms)`, S5 B.9
    """
    return _add_song("track", [_make_slot(file, length_ms, trim_ms, mpq_name, add)])


def f_chunks(pattern, indices, stop=None, *, length_ms=None, trim_ms=0, add=True, mpq_dir=WAV_DIR):
    """여러 조각을 이어 재생하는 곡을 선언한다(조각마다 실측 길이). 조각 번호는 `player.chunk(p)`(0부터).

    인자: pattern(`"LV10_{:03d}.ogg"` 처럼 `str.format` 자리 하나), indices(range·목록, 또는 시작 정수 — 이때 stop 은 끝(제외)),
          length_ms(모든 조각 같은 길이, 없으면 조각마다 측정), trim_ms(조각마다 뺄 ms), add, mpq_dir(MPQ 이름 앞머리)
    반환: Track (kind="chunks")
    비용: 없음(컴파일 시점). 표 칸 = 조각 수 (switch 방식이면 재생 함수에 조각마다 트리거 1)
    CP: 해당 없음
    로컬: 공유 안전
    epScript: `const LV = bgm.chunks("LV10_{:03d}.ogg", 1, 273);` 또는 `…, py_range(1, 273));` (→ `f_chunks`)
    출처: M2 `System.lua:117~150`(BGM001~364), UERE `Destr0yer.lua:43~55`(LV10_001~272), S5 B.5
    """
    if not isinstance(pattern, str):
        fail("chunks: pattern 은 문자열이어야 합니다 (%r)", pattern)
    if isinstance(indices, int) and not isinstance(indices, bool):
        if stop is None:
            fail("chunks: 시작 번호만 주었습니다 — chunks(pattern, 시작, 끝) 또는 chunks(pattern, range(…))")
        indices = range(indices, _check_int("chunks stop", stop, 0, 1 << 30))
    elif stop is not None:
        fail("chunks: indices 가 정수가 아니면 stop 을 줄 수 없습니다")
    try:
        idx = list(indices)
    except TypeError:
        fail("chunks: indices 는 range·목록이어야 합니다 (%r)", indices)
    if not idx:
        fail("chunks: 조각이 없습니다")
    slots = []
    for i in idx:
        try:
            file = pattern.format(i)
        except (IndexError, KeyError, ValueError) as e:
            fail("chunks: pattern %r 에 번호 %r 를 넣을 수 없습니다 (%s)", pattern, i, e)
        name = mpq_dir + os.path.basename(file.replace("\\", "/"))
        slots.append(_make_slot(file, length_ms, trim_ms, name, add))
    return _add_song("chunks", slots)


def _flat_files(files):
    if isinstance(files, str):
        return [files]
    out = []
    try:
        for x in files:
            out.extend(_flat_files(x))
    except TypeError:
        fail("rotation: 파일 이름 목록이어야 합니다 (%r)", files)
    return out


def f_rotation(files, length_ms=None, trim_ms=0, add=True):
    """요청마다 다음 파일을 고르는 곡(TPL 조각 표)을 선언한다. 대상(칸)마다 카운터가 따로 돈다.

    인자: files(파일 이름 목록 — epScript 는 `list("a.ogg", "b.ogg")`), length_ms(공통 길이, 없으면 파일마다 측정),
          trim_ms, add
    반환: Track (kind="rotation")
    비용: 없음(컴파일 시점). 표 칸 = 파일 수, 기록 칸에 카운터 필드 1(칸 12개)
    CP: 해당 없음
    로컬: 공유 안전
    epScript: `const ROT = bgm.rotation(list("BGM1_1.ogg", "BGM1_2.ogg"), length_ms=45000);` (→ `f_rotation`)
    출처: TPL `func.lua:876~908`(대상마다 Ccode 카운터, 공통 길이), BRZ `Interface.lua:25~31`
    """
    names = _flat_files(files)
    if not names:
        fail("rotation: 파일이 없습니다")
    slots = [_make_slot(f, length_ms, trim_ms, None, add) for f in names]
    rot = sum(1 for t in _songs if t.kind == "rotation")
    return _add_song("rotation", slots, rot=rot)


def f_songs():
    """지금까지 선언한 곡 목록(Track, 번호 순).

    인자: 없음
    반환: list[Track]
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    return list(_songs)


def f_table():
    """곡 표 요약(시험·디버그용): 칸별 (MPQ 이름, 길이 ms, 곡 번호)와 곡별 (번호, 종류, 시작, 개수).

    인자: 없음
    반환: dict(slots=[(name, ms, song_id)…], songs=[(id, kind, start, count)…])
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성 (S5 B.10 "표" 기대값 확인용)
    """
    return {
        "slots": [(s.name, s.length, s.song.id) for s in _slots],
        "songs": [(t.id, t.kind, t.start, t.count) for t in _songs],
    }


track = f_track
chunks = f_chunks
rotation = f_rotation
songs = f_songs
table = f_table


# =============================================================================================
# 빌드별 표 (곡 표 굳히기, 재생 함수)
# =============================================================================================

_tables_state = {"tables": None}


class _Tables:
    """한 빌드의 곡 표. 처음 코드를 낼 때 굳힌다(그 뒤에 선언한 곡·busy_sound 는 이 빌드에서 쓰면 오류)."""

    def __init__(self):
        for s in _slots:  # LoadMap 이 eudplib MPQ 목록을 비웠으면 다시 넣는다
            if s.add:
                try:
                    MPQCheckFile(s.name)
                except EPError:
                    continue
                MPQAddWave(s.name, s.path)
        self.extra = list(_extra)
        self.names = [s.name for s in _slots] + self.extra
        self.nslots = len(_slots)
        self.nsongs = len(_songs)
        self.nrot = sum(1 for t in _songs if t.kind == "rotation")
        if not self.nsongs:
            fail("bgm: 선언한 곡이 없습니다 — tick/request 앞에서 bgm.track/chunks/rotation 으로 곡을 선언하세요")
        self.lentab = EUDArray([s.length for s in _slots])
        self.starttab = EUDArray([0] + [t.start for t in _songs])
        self.counttab = EUDArray([0] + [t.count for t in _songs])
        # 돌려 쓰기 곡: 카운터 필드의 CP 오프셋(12·필드), 아니면 0
        self.rottab = EUDArray([0] + [STRIDE * (F_ROT0 + t.rot) if t.kind == "rotation" else 0 for t in _songs])
        self._strtab = None
        self._play = {}

    def extra_slot(self, name):
        if name not in self.extra:
            fail("bgm: busy_sound %s 는 이 빌드의 곡 표가 굳은 뒤에 만든 플레이어의 것입니다 — 플레이어는 모듈 최상위에서 만드세요", name)
        return self.nslots + self.extra.index(name)

    def strtab(self):
        if self._strtab is None:
            self._strtab = EUDArray([EncodeString(n) for n in self.names])
        return self._strtab

    def play_func(self, method, repeat):
        """재생 함수(빌드마다 새로 — 문자열 번호를 굽는다). slot → 이 PC 사용자에게 PlayWAV×repeat."""
        key = (method, repeat)
        fn = self._play.get(key)
        if fn is not None:
            return fn
        names = self.names
        tables = self

        @EUDFunc
        def _bgm_play(slot):
            back = EUDVariable()
            back << f_getcurpl()
            user = unProxy(f_getuserplayerid())
            if method == "patch":
                sid = tables.strtab()[slot]
                f_setcurpl(user)
                DoActions([PlayWAV(sid) for _ in range(repeat)])
            else:
                f_setcurpl(user)
                EUDSwitch(slot)
                for i, n in enumerate(names):
                    if EUDSwitchCase()(i):
                        DoActions([PlayWAV(n) for _ in range(repeat)])
                        EUDBreak()
                EUDEndSwitch()
            f_setcurpl(back)

        self._play[key] = _bgm_play
        return _bgm_play


def _tables():
    t = _tables_state["tables"]
    if t is None:
        t = _Tables()
        _tables_state["tables"] = t
    return t


# =============================================================================================
# 시계 (NormalTurboSet 대체)
# =============================================================================================


def _host_value(value):
    """sync.Value → 가장 작은 번호의 (지금 있는) 사람 플레이어가 보낸 값(새 변수). 사람이 없으면 0."""
    e = EUDVariable()
    e << 0
    hs = _pl.f_humans()
    if not hs:
        fail("bgm: 맵에 사람 플레이어가 없어 동기화 경과 시간을 고를 수 없습니다")
    for i, h in enumerate(hs):
        if (EUDIf if i == 0 else EUDElseIf)()(_pl.f_is_human(h)):
            e << value.get(h)
    EUDEndIf()
    return e


def _elapsed_var(elapsed, what):
    if isinstance(elapsed, _sync.Value):
        return _host_value(elapsed)
    if isinstance(elapsed, bool):
        fail("%s: elapsed 가 올바르지 않습니다 (%r)", what, elapsed)
    if isinstance(elapsed, int):
        v = EUDVariable()
        v << (elapsed & 0xFFFFFFFF)
        return v
    u = unProxy(elapsed)
    if _compat.is_var(u):
        return u
    fail("%s: elapsed 는 sync.Value(bus.value(...)), EUDVariable, 정수 중 하나여야 합니다 (%r)", what, elapsed)


class _Clock:
    """`bgm.clock` — 경과 시간과 반 박자 도우미 (NormalTurboSet 대체, 7절 D20). 모듈에 하나.

    인자: 없음 (`bgm.clock` 을 쓴다)
    반환: -
    비용: `update()` = 호출 자리 8 / 실행 30 (시간 읽기 16비트, 2026-09-17) — 빌드에 한 번(사이클마다 실행)
    CP: 바꾸지 않음
    로컬: `local_dt()` 는 로컬 값, `half()`·`dt2(동기화 값)` 은 공유 안전
    epScript: `const el = bus.value(bgm.clock.local_dt(), latch=True);`, `if (bgm.clock.half()) { … }`
    출처: LIB `NormalTurboSet`(:946~957), UERE `IBGM_EPDX` Option_NT(func.lua:442~453), bgmplayer `f_time`
    """

    __slots__ = ("_dt", "_half", "_prev", "_used")

    def __init__(self):
        self._dt = None
        self._prev = None
        self._half = None
        self._used = False

    def __repr__(self):
        return "<bgm.clock>"

    def _vars(self):
        if self._dt is None:
            self._dt = _local.LocalValue()
            self._prev = EUDVariable()
            self._half = EUDVariable()
        return self._dt, self._prev, self._half

    def local_dt(self):
        """이 PC 에서 지난 사이클 이후 흐른 실제 ms(LocalValue). `update()` 가 사이클마다 채운다.

        인자: 없음
        반환: LocalValue (모듈에 하나 — 선언 시점에 불러 `bus.value(...)` 에 넘긴다)
        비용: 변수 1 (계산은 update())
        CP: 바꾸지 않음
        로컬: **로컬 전용** — 공유 상태에 쓰면 디싱크(LIB 인자 4 `IBGM_EPD`·RESV 의 함정, S5 B.12). 동기화는 `bus.value(...)`
        epScript: `const el = bus.value(bgm.clock.local_dt(), latch=True);`
        출처: TPL `func.lua:847~853`(0x51CE8C 차이), bgmplayer `f_time`
        """
        self._used = True
        return self._vars()[0]

    f_local_dt = local_dt

    def half_value(self):
        """0/1 이 사이클마다 번갈아 나오는 공유 변수(update() 가 바꾼다).

        인자: 없음
        반환: EUDVariable (0 또는 1)
        비용: 변수 1
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `const h = bgm.clock.half_value();`
        출처: LIB `NormalTurboSet` 데스(Player, 214)
        """
        self._used = True
        return self._vars()[2]

    def half(self):
        """반 박자 조건: 값이 1 인 사이클에 참(0,1,0,1…). `NTCond()` 대체(`NTCond2()` 는 `EUDNot`).

        인자: 없음
        반환: Condition (새 객체)
        비용: 조건 1
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `if (bgm.clock.half()) { … }`
        출처: LIB `NTCond`/`NTCond2`
        """
        return Memory(self.half_value().getValueAddr(), Exactly, 1)

    f_half = half

    def dt2(self, elapsed):
        """두 사이클 경과 합: 0 인 사이클에 A ← e, 1 인 사이클에 B ← e + A. B 를 돌려준다(1 인 사이클에 갱신).

        사이클마다 한 번 부른다(부른 자리에 코드를 낸다).
        인자: elapsed — 동기화된 값(sync.Value 는 가장 작은 번호의 사람 몫), EUDVariable, 정수
        반환: EUDVariable (B)
        비용: 호출 자리 약 5 / 실행 3~4 (+ sync.Value 이면 읽기 약 40)
        CP: 바꾸지 않음
        로컬: elapsed 가 동기화 값이면 공유 안전. LocalValue 를 넣으면 결과도 로컬 값
        epScript: `const d = bgm.clock.dt2(el);`
        출처: UERE `IBGM_EPDX` Option_NT = {A, B} (func.lua:442~453)
        """
        e = _elapsed_var(elapsed, "clock.dt2")
        half = self.half_value()
        a, b = EUDVariable(), EUDVariable()
        if isinstance(e, _local.LocalValue):
            b = _local.LocalValue()
        with _local.allow() if isinstance(e, _local.LocalValue) else _nullctx():
            if EUDIf()(half.Exactly(0)):
                a << e
            if EUDElse()():
                b << a
                b += e
            EUDEndIf()
        return b

    f_dt2 = dt2

    def update(self):
        """`local_dt()`·`half()` 값을 갱신하는 코드를 낸다(빌드에 한 번 — 두 번째부터는 아무것도 내지 않는다).

        `Player.tick()` 이 부른다. 플레이어 없이 시계만 쓰면 사이클마다 도는 자리에서 한 번 부른다.
        인자: 없음
        반환: None
        비용: 호출 자리 8 / 실행 30 (0x51CE8C 아래 16비트 읽기 + 차이 + 반 박자 2, 2026-09-17) — 시작 때 1회 읽기
        CP: 바꾸지 않음(읽기 함수가 되돌림)
        로컬: 경과 시간은 로컬 값에만 쓴다. 반 박자는 공유 변수(모든 PC 에서 같게 돈다)
        epScript: `bgm.clock.update();`
        출처: LIB `NormalTurboSet`, bgmplayer `f_time`
        """
        if _clock_state["emitted"]:
            return
        _clock_state["emitted"] = True
        dt, prev, half = self._vars()
        with _local.allow():
            cur = f_maskread_epd(EPD(TIME_ADDR), _TIME_MASK)
            # 0x51CE8C 는 시간이 흐르면 줄어든다 → dt = (prev − cur) mod 2^16
            dt << prev
            dt += _TIME_MASK + 1
            _parts.isub32(dt, cur)
            RawTrigger(conditions=dt.AtLeast(_TIME_MASK + 1), actions=dt.SubtractNumber(_TIME_MASK + 1))
            prev << cur
        RawTrigger(actions=half.AddNumber(1))
        RawTrigger(conditions=half.Exactly(2), actions=half.SetNumber(0))

        def _init():
            with _local.allow():
                f_maskread_epd(EPD(TIME_ADDR), _TIME_MASK, ret=[prev])

        EUDOnStart(_init)

    f_update = update


class _nullctx:
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


clock = _Clock()
_clock_state = {"emitted": False}


def f_clock_update():
    """= `bgm.clock.update()` (epScript 모듈 함수 모양).

    인자: 없음
    반환: None
    비용: `clock.update()` 와 같음
    CP: 바꾸지 않음
    로컬: `clock.update()` 참고
    epScript: `bgm.clock_update();`
    출처: 새로 작성
    """
    clock.update()


clock_update = f_clock_update

# =============================================================================================
# 플레이어
# =============================================================================================

_players = []


@_compat.register_build_reset
def _reset_build():
    _tables_state["tables"] = None
    _clock_state["emitted"] = False
    for p in _players:
        p._ps = None


def _cell_of_const(e, what):
    if isinstance(e, bool) or not isinstance(e, int):
        fail("%s: 플레이어 번호가 아닙니다 (%r)", what, e)
    if 0 <= e <= 7:
        return e
    if 8 <= e <= 11 or 128 <= e <= 131:
        return OBSERVER_CELL
    fail("%s: 플레이어 번호는 0~7, 관전자 128~131(P9~P12) 입니다 (%r)", what, e)


def _player_arg(p, what):
    """p → ("const", 칸) 또는 ("var", EUDVariable)."""
    if p is CurrentPlayer:
        fail("%s: CurrentPlayer 는 받지 않습니다 — 번호 상수나 변수를 넘기세요", what)
    e = EncodePlayer(p)
    if _compat.is_var(e):
        return "var", unProxy(e)
    if isinstance(e, int) and e == 13:
        fail("%s: CurrentPlayer 는 받지 않습니다 — 번호 상수나 변수를 넘기세요", what)
    return "const", _cell_of_const(e, what)


class _PS:
    """플레이어 하나의 빌드별 상태."""

    def __init__(self, player):
        pl = player
        t = _tables()
        self.tables = t
        self.cells = pl._resolve_cells()
        if not self.cells:
            fail("bgm.Player: 대상이 비었습니다 (targets=%r, observers=%r)", pl._targets, pl.observers)
        synced = pl.mode == "synced"
        if synced:
            self.lo, self.hi = self.cells[0], self.cells[-1]
        else:
            self.lo = self.hi = 0
        self.nf = F_ROT0 + t.nrot
        init = bytearray(4 * STRIDE * self.nf)
        if synced:
            for c in self.cells:
                struct.pack_into("<I", init, 4 * (STRIDE * F_EN + c), 1)
        self.rec = Db(bytes(init))
        self.B = EPD(self.rec)
        # 공유 요청 칸 (local 모드: REQ 칸 0~11, MUTE 칸 12~23 / synced 모드는 기록 안의 REQ·MUTE 필드)
        self.shared = Db(4 * 2 * STRIDE) if not synced else None
        self.req_all = EUDVariable()
        self.pending = EUDVariable()  # 1 = 새 요청, 2 = 기다리는 요청(queue)
        self.active = EUDVariable()  # SONG ≠ 0 인 칸 수
        self.ended = EUDVariable()  # 이번 사이클에 끝난 곡이 있음
        self.go = EUDVariable()
        self.keep = EUDVariable()
        self.all_eff = EUDVariable()
        self.lnew = EUDVariable()  # local: 새 요청을 받았음
        self.dt = EUDVariable()
        self.r = EUDVariable()
        self.myslot = EUDVariable(NO_CELL)  # 로컬: 이 PC 의 칸
        self.en_local = EUDVariable()  # 로컬: 이 PC 사용자가 대상인가
        self.req_epd = EUDVariable()  # 로컬: EPD(shared) + myslot
        self.obs_off = EUDVariable()  # 로컬: 관전자 끄기
        self.obs_prev = EUDVariable()  # 로컬: 키 이전 상태
        self.ok = EUDVariable()
        # 캐시: 조각 넘김(칸 → 길이), 시작(곡 → 시작 칸·남은 조각·길이)
        self.cslot = EUDVariable()
        self.cache_ok = EUDVariable()
        self.cr, self.crslot, self.crleft, self.crlen = EUDVariable(), EUDVariable(), EUDVariable(), EUDVariable()
        self.v_slot, self.v_left, self.v_len = EUDVariable(), EUDVariable(), EUDVariable()
        self.chk = Forward()  # play_mine 의 판정 트리거 (시작 때 조건 칸을 채운다)
        self.adv = Forward()  # 조각 넘김 캐시 트리거
        self.sub = Forward()  # 남은 시간 빼기 트리거
        self.ticked = False
        self.start_fn = None
        self.mine_fn = None
        self.body_fn = None
        self.busy_slot = t.extra_slot(pl._busy_name) if pl._busy_name is not None else None
        self.play = t.play_func(pl.method, pl.repeat)

    # 주소
    def addr(self, field, cell):
        return self.rec + 4 * (STRIDE * field + cell)

    def epd(self, field, cell):
        return self.B + STRIDE * field + cell


class Player:
    """배경음악 재생기. 곡 표(`bgm.track/chunks/rotation`)를 대상 플레이어에게 재생한다(S5 B.9).

    인자:
      mode — "local"(남은 시간을 각 PC 가 로컬로 셈, 요청만 공유) | "synced"(모든 상태 공유, `elapsed` 필요)
      targets — 대상: None/"humans"/`players.Humans`(맵의 사람 슬롯), "all"(0~7 + 관전자), `players.Everyone`,
                `players.All`, `players.Observers`, 번호(0~7, P1~P8, 관전자 128~131·P9~P12)나 그 목록. 컴파일 시점 목록
      elapsed — synced 전용: `bus.value(bgm.clock.local_dt(), latch=True)`(방장 = 지금 있는 가장 작은 번호의 사람 몫),
                EUDVariable(동기화된 값), 정수. local 모드는 None(이 PC 시계) 또는 변수
      max_elapsed — 한 사이클 경과가 이보다 크면 그 사이클은 0 으로 본다(UERE `Dt ≤ 2500`, 일시정지·못 받은 값 0xFFFFFFFF). None = 검사 없음
      busy — 재생 중 요청: "drop"(버림, TPL·LIB 기본) | "replace"(바로 바꿈) | "queue"(끝나면 적용 — 전원 요청은 모든 대상이 끝난 사이클에)
      busy_sound — drop 으로 버릴 때 그 플레이어에게 낼 소리(MPQ 이름 문자열 또는 Track — 첫 칸). None = 없음
      observers — 관전자(128~131) 몫 칸(8)을 둔다
      observer_toggle_key — 관전자가 이 키를 누를 때마다 자기 PC 에서 소리를 끄고 켠다(로컬, 채팅 중 제외). None = 없음
      lead_ms — 남은 시간 보정(bgmplayer 는 −42). 음수면 0 에서 멈추고 1 ms 는 남긴다
      method — "switch"(EUDSwitch, 기본) | "patch"(PlayWAV 문자열 칸 채우기 — 인게임 D16-1 확인 전)
      repeat — 한 번 재생에 PlayWAV 를 부르는 횟수(기존 맵 관례 2, 인게임 D16-2)
    반환: -
    메서드: `request(곡, p=None, loop=False, force=False)`, `stop(p=None)`, `loop(곡, p=None, force=False)`, `mute(p=None, on=True)`,
            `is_playing(p=None)`, `current(p=None)`, `chunk(p=None)`, `remaining(p=None)`, `tick()`, `last_dt()`
    비용: 재생기마다 본문 1벌 = 루프 + start + play_mine — synced 131 / local 141 트리거(관전자 끄기 키 +6),
          곡 수·대상 수와 무관(대상 1명 = 11명). 재생 함수(같은 method·repeat 끼리 1벌) = switch 19 + 칸 수 / patch 12.
          재생기 1개 페이로드 약 45~49KB. `tick()` 호출 자리 1(+ 빌드 첫 시계 8). 실행: 곡 없음 8~11, 재생 중 빼기만
          local 37 / synced 8칸 62, 조각 경계 8칸 273, 전원 요청 → 8칸 시작 580 (2026-09-17, docs/COSTS.md "bgm (WP16)")
    CP: 바꾸지 않음(안에서 기록 칸·이 PC 사용자로 옮기고 되돌린다)
    로컬: local 모드의 상태 값은 로컬 전용, synced 모드는 elapsed 가 동기화 값이면 공유 안전. 소리는 늘 이 PC 사용자에게만
    epScript: `const player = bgm.Player(mode="synced", targets=pl.humans(), elapsed=el);` → `player.tick();`
    출처: TPL `IBGM_EPD`(로컬형), LIB `Install_BGMSystem` + UERE `IBGM_EPDX`(공유형), M2 조각 이어 재생, S5 B.9
    """

    def __init__(self, mode="local", targets=None, elapsed=None, max_elapsed=2500, busy="drop", busy_sound=None,
                 observers=True, observer_toggle_key="DELETE", lead_ms=0, method="switch", repeat=2):
        self.mode = check_choice("bgm.Player mode", mode, MODES)
        self.busy = check_choice("bgm.Player busy", busy, BUSY_POLICIES)
        self.method = check_choice("bgm.Player method", method, METHODS)
        self.repeat = _check_int("bgm.Player repeat", repeat, 1, 16)
        self.lead_ms = _check_int("bgm.Player lead_ms", lead_ms, -600000, 600000)
        if max_elapsed is not None:
            _check_int("bgm.Player max_elapsed", max_elapsed, 1, 0x7FFFFFFE)
        self.max_elapsed = max_elapsed
        self.observers = bool(observers)
        if mode == "synced":
            if elapsed is None:
                fail("bgm.Player(mode='synced'): elapsed 가 필요합니다 — elapsed=bus.value(bgm.clock.local_dt(), latch=True)")
            if isinstance(unProxy(elapsed), _local.LocalValue):
                fail("bgm.Player(mode='synced'): elapsed 에 로컬 값(LocalValue)을 넣으면 디싱크입니다 — "
                     "bus.value(bgm.clock.local_dt()) 로 동기화한 값을 넣으세요")
        if elapsed is not None:
            ok = isinstance(elapsed, _sync.Value) or _compat.is_var(unProxy(elapsed)) or (
                isinstance(elapsed, int) and not isinstance(elapsed, bool) and elapsed >= 0)
            if not ok:
                fail("bgm.Player: elapsed 는 sync.Value, EUDVariable, 0 이상 정수 중 하나입니다 (%r)", elapsed)
            if mode == "local" and isinstance(elapsed, _sync.Value):
                fail("bgm.Player(mode='local'): elapsed 에 sync.Value 를 넣지 않습니다 — 동기화 시간은 mode='synced'")
        self.elapsed = elapsed
        if observer_toggle_key is not None:
            _local.f_key_code(observer_toggle_key)
        self.toggle_key = observer_toggle_key
        self._busy_name = None
        if busy_sound is not None:
            if isinstance(busy_sound, Track):
                name = busy_sound.names[0]
            elif isinstance(busy_sound, str) and busy_sound:
                name = busy_sound
            else:
                fail("bgm.Player busy_sound 는 MPQ 소리 이름이나 Track 입니다 (%r)", busy_sound)
            if name not in _extra:
                _extra.append(name)
            self._busy_name = name
        self._targets = targets
        self._ps = None
        _players.append(self)

    def __repr__(self):
        return "<bgm.Player %s busy=%s method=%s>" % (self.mode, self.busy, self.method)

    # ---------------------------------------------------------------------------------------
    # 대상·상태
    # ---------------------------------------------------------------------------------------

    def _resolve_cells(self):
        cells = set()

        def add(x):
            if isinstance(x, str):
                if x == "humans":
                    cells.update(_pl.f_humans())
                elif x == "all":
                    cells.update(range(8))
                    cells.add(OBSERVER_CELL)
                else:
                    fail("bgm.Player targets: 알 수 없는 이름 %r ('humans', 'all')", x)
                return
            if x is None or x is _pl.Humans:
                cells.update(_pl.f_humans())
                return
            if x is _pl.Everyone:
                cells.update(_pl.f_humans())
                cells.add(OBSERVER_CELL)
                return
            if x is _pl.Observers:
                cells.add(OBSERVER_CELL)
                return
            if x is _pl.All:
                cells.update(range(8))
                return
            if isinstance(x, (list, tuple, set, frozenset, range)):
                for y in x:
                    add(y)
                return
            if isinstance(x, _pl.Targets):
                fail("bgm.Player targets: 이 Targets 는 받지 않습니다 (%r) — 번호 목록, 'humans', 'all', "
                     "players.Humans/Everyone/All/Observers 를 쓰세요", x)
            e = EncodePlayer(x)
            if _compat.is_var(e):
                fail("bgm.Player targets 는 컴파일 시점 목록입니다 (변수 %r)", x)
            cells.add(_cell_of_const(e, "bgm.Player targets"))

        add(self._targets)
        if self.observers:
            cells.add(OBSERVER_CELL)
        return sorted(cells)

    def _state(self):
        if self._ps is None:
            self._ps = _PS(self)
        return self._ps

    def cells(self):
        """이 빌드의 대상 칸 목록(0~7 = 플레이어, 8 = 관전자). 맵을 읽은 뒤(빌드 중)에 부른다.

        인자: 없음
        반환: list[int]
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: 쓰지 않는다
        출처: 새로 작성
        """
        return list(self._state().cells)

    def state_region(self):
        """기록 칸의 (주소 식, dword 수, 필드 수) — 시험·디버그용(공유 상태 비교).

        인자: 없음
        반환: (ConstExpr, int, int)
        비용: 없음
        CP: 해당 없음
        로컬: synced 모드는 공유 메모리, local 모드는 로컬 메모리
        epScript: 쓰지 않는다
        출처: 새로 작성
        """
        ps = self._state()
        return ps.rec, STRIDE * ps.nf, ps.nf

    def shared_region(self):
        """local 모드의 공유 요청·끔 칸 (주소 식, dword 수) — 시험용. synced 모드는 None.

        인자: 없음
        반환: (ConstExpr, int) 또는 None
        비용: 없음
        CP: 해당 없음
        로컬: 공유 메모리
        epScript: 쓰지 않는다
        출처: 새로 작성
        """
        ps = self._state()
        return None if ps.shared is None else (ps.shared, 2 * STRIDE)

    def control_vars(self):
        """공유 제어 변수 {이름: EUDVariable} — 시험용(req_all, pending, active; synced 는 셋 다 공유, local 은 active 가 로컬).

        인자: 없음
        반환: dict
        비용: 없음
        CP: 해당 없음
        로컬: 위 참고
        epScript: 쓰지 않는다
        출처: 새로 작성
        """
        ps = self._state()
        return {"req_all": ps.req_all, "pending": ps.pending, "active": ps.active}

    def last_dt(self):
        """지난 `tick()` 이 쓴 경과 ms(max_elapsed 적용 뒤) 변수. 인게임 표시·디버그용.

        인자: 없음
        반환: EUDVariable (local 모드는 로컬 값)
        비용: 없음
        CP: 해당 없음
        로컬: local 모드 = 로컬 전용, synced 모드 = 공유 안전
        epScript: `printAll("dt {}", player.last_dt());`
        출처: 새로 작성
        """
        return self._state().dt

    # ---------------------------------------------------------------------------------------
    # 요청·끄기
    # ---------------------------------------------------------------------------------------

    def _song_code(self, ps, song, what):
        n = ps.tables.nsongs
        if isinstance(song, Track):
            if song.id > len(_songs) or _songs[song.id - 1] is not song:
                fail("%s: 이 프로세스에서 선언한 곡이 아닙니다 (%r)", what, song)
            if song.id > n:
                fail("%s: %r 는 이 빌드의 곡 표가 굳은 뒤(tick/request 뒤)에 선언했습니다 — 곡은 모듈 최상위에서 먼저 선언하세요",
                     what, song)
            return song.id
        u = unProxy(song)
        if _compat.is_var(u):
            return u
        if isinstance(u, bool) or not isinstance(u, int) or not 1 <= u <= n:
            fail("%s: 곡은 Track, 곡 번호(1~%d) 또는 변수입니다 (%r)", what, n, song)
        return u

    def _write_req(self, ps, p, code, what):
        synced = self.mode == "synced"
        if p is None:
            DoActions(SetMemory(ps.req_all.getValueAddr(), SetTo, code), ps.pending.SetNumber(1))
            return
        kind, cell = _player_arg(p, what)
        if synced:
            base_addr, base_epd = ps.rec + 4 * STRIDE * F_REQ, ps.B + STRIDE * F_REQ
        else:
            base_addr, base_epd = ps.shared, EPD(ps.shared)
        if kind == "const":
            DoActions(SetMemory(base_addr + 4 * cell, SetTo, code), ps.pending.SetNumber(1))
            return
        c = EUDVariable()
        c << cell
        RawTrigger(conditions=c.AtLeast(OBSERVER_CELL), actions=c.SetNumber(OBSERVER_CELL))
        c += base_epd
        f_dwwrite_epd(c, code)
        DoActions(ps.pending.SetNumber(1))

    def request(self, song, p=None, loop=False, force=False):
        """곡을 요청한다. 다음 `tick()` 이 적용한다(재생 중이면 busy 정책, force=True 면 바로 바꿈).

        인자: song(Track·곡 번호·변수), p(None = 모든 대상, 번호 0~7·관전자 128~131 상수, 또는 변수 0~7(8 이상은 관전자 칸)),
              loop(True = 끝나면 같은 곡 다시 — 돌려 쓰기는 다음 파일), force(True = busy 정책을 무시하고 바꿈)
        반환: None
        비용: 상수 = 호출 자리 1 / 실행 1, 변수 곡·변수 p = 호출 5 / 실행 8 (2026-09-17)
        CP: 바꾸지 않음
        로컬: 공유 동작 — 모든 PC 에서 같은 조건으로 부른다(로컬 조건 안에서 부르면 디싱크)
        epScript: `player.request(BOSS);`, `player.request(BOSS, p);`, `player.request(OP, loop=True);`
        출처: TPL `IBGM_EPD` Input 칸, LIB `BGMTypeV`, UERE `ReserveBGM`
        """
        ps = self._state()
        code = self._song_code(ps, song, "request")
        flags = (REQ_LOOP if loop else 0) | (REQ_FORCE if force else 0)
        if isinstance(code, int):
            code |= flags
        elif flags:
            code = code + flags
        self._write_req(ps, p, code, "request")

    def loop(self, song, p=None, force=False):
        """= `request(song, p, loop=True, force=force)`: 끝나면 같은 곡을 다시 튼다(`stop()` 까지).

        인자: song, p, force — `request` 와 같음
        반환: None
        비용: `request` 와 같음
        CP: 바꾸지 않음
        로컬: 공유 동작
        epScript: `player.loop(BOSS);`
        출처: UERE `ReserveBGM` 재예약(func.lua:251~258)
        """
        self.request(song, p, loop=True, force=force)

    def stop(self, p=None):
        """재생을 멈춘다(다음 tick 에 곡 0·남은 시간 0·반복 끔). 이미 난 소리는 멈추지 않는다(SC 에 멈춤 액션이 없다).

        인자: p(None = 모든 대상, 번호 상수 또는 변수)
        반환: None
        비용: `request` 와 같음
        CP: 바꾸지 않음
        로컬: 공유 동작
        epScript: `player.stop();`
        출처: S5 B.9 (원본에는 정지가 없었다)
        """
        self._write_req(self._state(), p, STOP_ID | REQ_FORCE, "stop")

    def mute(self, p=None, on=True):
        """플레이어의 공유 끔 비트를 바꾼다(곡 상태는 흐르고 소리만 막는다). **공유 입력으로만** 바꾼다.

        인자: p(None = 모든 칸, 번호 상수 또는 변수), on(True/False, 0/1 또는 변수)
        반환: None
        비용: 상수 = 호출 1 / 실행 1, 모든 칸 = 1 / 1 (2026-09-17). 변수 p 는 호출 약 5
        CP: 바꾸지 않음
        로컬: 공유 동작 — 로컬 키로 바로 부르면 디싱크(sync 로 보낸 펄스로 부른다)
        epScript: `player.mute(p, 1);`, `player.mute(p, 0);`
        출처: LIB 끔 비트(데스 12 윗바이트), UERE `Player_interface.lua:522~534`
        """
        ps = self._state()
        synced = self.mode == "synced"
        if isinstance(on, bool):
            val = int(on)
        else:
            val = unProxy(on)
            if not _compat.is_var(val) and val not in (0, 1):
                fail("mute: on 은 True/False, 0/1 또는 변수입니다 (%r)", on)
        if synced:
            base_addr, base_epd = ps.rec + 4 * STRIDE * F_MUTE, ps.B + STRIDE * F_MUTE
        else:
            base_addr, base_epd = ps.shared + 4 * STRIDE, EPD(ps.shared) + STRIDE
        if p is None:
            DoActions([SetMemory(base_addr + 4 * c, SetTo, val) for c in range(OBSERVER_CELL + 1)])
            return
        kind, cell = _player_arg(p, "mute")
        if kind == "const":
            DoActions(SetMemory(base_addr + 4 * cell, SetTo, val))
            return
        c = EUDVariable()
        c << cell
        RawTrigger(conditions=c.AtLeast(OBSERVER_CELL), actions=c.SetNumber(OBSERVER_CELL))
        c += base_epd
        f_dwwrite_epd(c, val)

    # ---------------------------------------------------------------------------------------
    # 읽기
    # ---------------------------------------------------------------------------------------

    def _field_epd(self, ps, field, p, what):
        """(EPD 식 또는 변수, 로컬인가)."""
        if self.mode == "local":
            return ps.epd(field, 0), True
        if p is None:
            fail("%s: synced 모드는 플레이어 번호가 필요합니다", what)
        kind, cell = _player_arg(p, what)
        if kind == "const":
            return ps.epd(field, cell), False
        c = EUDVariable()
        c << cell
        RawTrigger(conditions=c.AtLeast(OBSERVER_CELL), actions=c.SetNumber(OBSERVER_CELL))
        c += ps.B + STRIDE * field
        return c, False

    def _read(self, field, p, what):
        ps = self._state()
        epd, is_local = self._field_epd(ps, field, p, what)
        if is_local:
            lv = _local.LocalValue()
            with _local.allow():
                f_dwread_epd(epd, ret=[lv])
            return lv
        return f_dwread_epd(epd)

    def is_playing(self, p=None):
        """재생 중인가(곡 ≠ 0). local 모드는 이 PC 의 상태(p 무시).

        인자: p(synced: 번호 상수 또는 변수 — 변수면 조건을 쓰는 자리에서 칸을 채운다)
        반환: Condition (local 모드는 LocalCondition)
        비용: 조건 1 (변수 p = 호출 자리 +3)
        CP: 바꾸지 않음
        로컬: local 모드 = 로컬 전용, synced = 공유 안전
        epScript: `if (player.is_playing(0)) { … }`
        출처: LIB `Deaths(CP, AtMost, 0, DeathUnit)` 판정의 반대
        """
        ps = self._state()
        epd, is_local = self._field_epd(ps, F_SONG, p, "is_playing")
        cond = MemoryEPD(epd, AtLeast, 1)
        if is_local:
            return _local.LocalCondition.wrap(cond)
        return cond

    def current(self, p=None):
        """지금 곡 번호(0 = 없음). Track 과 비교할 수 있다(`player.current(0) == BOSS`).

        인자: p(synced: 번호 상수 또는 변수, local: 무시)
        반환: EUDVariable (local 모드는 LocalValue)
        비용: 호출 자리 2~4 / 실행 약 37
        CP: 바꾸지 않음
        로컬: local 모드 = 로컬 전용, synced = 공유 안전
        epScript: `const s = player.current(0);`
        출처: 새로 작성
        """
        return self._read(F_SONG, p, "current")

    def chunk(self, p=None):
        """조각 번호(0부터, `chunks` 곡에서 보스 패턴·가사 동기화용). 곡이 끝나면 마지막 값이 남는다.

        인자: p(synced: 번호 상수 또는 변수, local: 무시)
        반환: EUDVariable (local 모드는 LocalValue)
        비용: 호출 자리 2~4 / 실행 약 37
        CP: 바꾸지 않음
        로컬: local 모드 = 로컬 전용, synced = 공유 안전(UERE `Destr0yer.lua` 처럼 패턴에 쓸 수 있다)
        epScript: `const c = player.chunk(0);`
        출처: UERE `Destr0yer.lua:52~55` (FP 데스 439 = 조각 번호)
        """
        return self._read(F_CHUNK, p, "chunk")

    def remaining(self, p=None):
        """지금 조각(곡)의 남은 ms.

        인자: p(synced: 번호 상수 또는 변수, local: 무시)
        반환: EUDVariable (local 모드는 LocalValue)
        비용: 호출 자리 2~4 / 실행 약 37
        CP: 바꾸지 않음
        로컬: local 모드 = 로컬 전용, synced = 공유 안전
        epScript: `const ms = player.remaining(0);`
        출처: TPL `Arr[3]`(Delay), LIB 데스(p, 12) 아래 3바이트
        """
        return self._read(F_REM, p, "remaining")

    # ---------------------------------------------------------------------------------------
    # tick
    # ---------------------------------------------------------------------------------------

    def tick(self):
        """사이클마다 한 번: 경과 시간을 빼고, 끝난 조각·곡을 넘기고, 요청을 적용하고, 소리를 낸다.

        빌드에 한 번만 부른다(두 번이면 오류). 시계(`bgm.clock.update()`)도 여기서 낸다.
        인자: 없음
        반환: None
        비용: 호출 자리 1 (+ 빌드 첫 시계 8) / 실행: 곡 없음 8~11, 재생 중 빼기만 local 37 · synced 8칸 62,
              조각 경계 8칸 273, 전원 요청 → 8칸 시작 580 (2026-09-17, docs/COSTS.md "bgm (WP16)")
        CP: 바꾸지 않음
        로컬: 모드 설명 참고. 모든 PC 에서 같은 자리·같은 조건으로 부른다
        epScript: `function beforeTriggerExec() { player.tick(); }`
        출처: TPL `IBGM_EPD` 본문, LIB `Install_BGMSystem`, UERE `IBGM_EPDX`
        """
        ps = self._state()
        if ps.ticked:
            fail("bgm.Player.tick(): 한 빌드에 한 번만 부릅니다 (사이클마다 도는 자리에 한 번)")
        ps.ticked = True
        clock.update()
        self._prepare()
        ps.body_fn()

    def _prepare(self):
        ps = self._state()
        if ps.body_fn is None:
            if self.mode == "local" and self.elapsed is None:
                clock.local_dt()
            ps.body_fn = self._make_body(ps)
            ps.body_fn.size()  # 본문(과 start·play_mine·재생 함수)을 지금 만든다 — 시작 코드가 그 안의 판정 트리거를 채운다
            self._register_init(ps)
        return ps

    def body_sizes(self):
        """본문 트리거 수 {"body", "start", "play_mine", "play"} (시험·비용용). 부르면 이 빌드의 본문을 만든다.

        인자: 없음
        반환: dict — body(루프 1벌), start(곡 시작), play_mine(판정 + 재생 호출), play(재생 함수 — 같은 method·repeat 인
              플레이어끼리 한 벌. switch 방식은 칸마다 트리거 1)
        비용: 없음(측정만)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: 쓰지 않는다
        출처: 새로 작성 (S5 B.10 "targets 1명과 11명 빌드에서 본문 트리거 수가 같다")
        """
        ps = self._prepare()
        return {"body": ps.body_fn.size(), "start": ps.start_fn.size(), "play_mine": ps.mine_fn.size(),
                "play": ps.play.size()}

    # --- 시작 때 1회 ---
    def _register_init(self, ps):
        player = self

        def _init():
            u = unProxy(f_getuserplayerid())
            ms = ps.myslot
            with _local.allow():
                RawTrigger(actions=ms.SetNumber(NO_CELL))
                if EUDIf()(u.AtMost(7)):
                    ms << u
                EUDEndIf()
                RawTrigger(conditions=[u.AtLeast(128), u.AtMost(131)], actions=ms.SetNumber(OBSERVER_CELL))
                if player.mode == "synced":
                    ptr = EUDVariable()
                    ptr << ms
                    ptr += ps.B
                    SeqCompute([(EPD(ps.chk + 8 + 8), SetTo, ptr)])  # play_mine 조건 0 의 비교값 = 이 PC 칸
                else:
                    for c in ps.cells:  # 이 PC 칸이 대상인가 (시작 때 1회, 대상 칸마다 트리거 1)
                        RawTrigger(conditions=ms.Exactly(c),
                                   actions=[ps.en_local.SetNumber(1), SetMemory(ps.addr(F_EN, 0), SetTo, 1)])
                    ps.req_epd << ms
                    ps.req_epd += EPD(ps.shared)
                    mepd = EUDVariable()
                    mepd << ps.req_epd
                    mepd += STRIDE
                    SeqCompute([(EPD(ps.chk + 8 + 4), SetTo, mepd)])  # play_mine 조건 0 의 칸 = 공유 끔 칸[이 PC]

        EUDOnStart(_init)

    # --- 부품 ---
    def _lead(self, v):
        lead = self.lead_ms
        if lead > 0:
            RawTrigger(actions=v.AddNumber(lead))
        elif lead < 0:
            RawTrigger(conditions=v.AtLeast(-lead + 1), actions=v.SubtractNumber(-lead))
            RawTrigger(conditions=v.AtMost(-lead), actions=v.SetNumber(1))

    def _make_mine(self, ps):
        synced = self.mode == "synced"
        play = ps.play

        @EUDFunc
        def _bgm_play_mine(slot):
            # 이 칸이 이 PC 사용자 몫이고, 끄지 않았고, 관전자 로컬 끄기가 아니면 재생 (판정 칸은 시작 때 채운다)
            ph = _parts.placeholder()
            if synced:
                conds = [Memory(CP_ADDR, Exactly, ph), Deaths(CurrentPlayer, Exactly, 0, F_MUTE)]
            else:
                conds = [MemoryEPD(ph, Exactly, 0)]
            conds.append(ps.obs_off.Exactly(0))
            with _local.allow():
                RawTrigger(actions=ps.ok.SetNumber(0))
                ps.chk << RawTrigger(conditions=conds, actions=ps.ok.SetNumber(1))
                if EUDIf()(ps.ok.Exactly(1)):
                    play(slot)
                EUDEndIf()

        return _bgm_play_mine

    def _make_start(self, ps):
        t = ps.tables
        mine = ps.mine_fn
        player = self
        CP = CurrentPlayer

        @EUDFunc
        def _bgm_start(r):
            # CP = 캐시 = EPD(기록) + 칸. r = 곡 번호 | 반복 (강제 비트는 뗀 것), 또는 STOP_ID
            if EUDIf()(r.Exactly(STOP_ID)):
                RawTrigger(conditions=Deaths(CP, AtLeast, 1, F_SONG),
                           actions=[ps.active.SubtractNumber(1), ps.ended.SetNumber(1)])
                DoActions(SetDeaths(CP, SetTo, 0, F_SONG), SetDeaths(CP, SetTo, 0, F_REM),
                          SetDeaths(CP, SetTo, 0, F_LOOP), SetDeaths(CP, SetTo, 0, F_LEFT))
                EUDReturn()
            EUDEndIf()
            RawTrigger(actions=SetDeaths(CP, SetTo, 0, F_LOOP))
            RawTrigger(conditions=r.AtLeast(REQ_LOOP), actions=[r.SubtractNumber(REQ_LOOP), SetDeaths(CP, SetTo, 1, F_LOOP)])
            RawTrigger(conditions=r.Exactly(0), actions=r.SetNumber(0xFFFFFFFF))  # 반복 비트만 있는 요청(곡 0)
            if EUDIf()([r.AtLeast(t.nsongs + 1)]):  # 모르는 번호는 무시
                RawTrigger(actions=SetDeaths(CP, SetTo, 0, F_LOOP))
                EUDReturn()
            EUDEndIf()
            RawTrigger(conditions=Deaths(CP, Exactly, 0, F_SONG), actions=ps.active.AddNumber(1))
            DoActions(SetDeaths(CP, SetTo, r, F_SONG), SetDeaths(CP, SetTo, 0, F_CHUNK))
            done = Forward()
            # 캐시: 앞 칸이 같은 곡으로 시작했으면 표를 다시 읽지 않는다 (돌려 쓰기 곡은 캐시에 넣지 않는다)
            if EUDIf()(r == ps.cr):
                SeqCompute([(ps.v_slot, SetTo, ps.crslot), (ps.v_left, SetTo, ps.crleft), (ps.v_len, SetTo, ps.crlen)])
                EUDJump(done)
            EUDEndIf()
            if t.nrot:
                cpo = t.rottab[r]
                if EUDIf()(cpo.AtLeast(1)):
                    st = t.starttab[r]
                    cnt = t.counttab[r]
                    epd = EUDVariable()
                    epd << f_getcurpl()
                    epd += cpo
                    c = f_dwread_epd(epd)
                    ps.v_slot << st
                    ps.v_slot += c
                    c += 1
                    if EUDIf()(c >= cnt):
                        c << 0
                    EUDEndIf()
                    f_dwwrite_epd(epd, c)
                    ps.v_left << 0
                    ps.v_len << t.lentab[ps.v_slot]
                    player._lead(ps.v_len)
                    EUDJump(done)
                EUDEndIf()
            ps.v_slot << t.starttab[r]
            ps.v_left << t.counttab[r]
            RawTrigger(actions=ps.v_left.SubtractNumber(1))
            ps.v_len << t.lentab[ps.v_slot]
            player._lead(ps.v_len)
            SeqCompute([(ps.cr, SetTo, r), (ps.crslot, SetTo, ps.v_slot), (ps.crleft, SetTo, ps.v_left),
                        (ps.crlen, SetTo, ps.v_len)])
            done << NextTrigger()
            DoActions(SetDeaths(CP, SetTo, ps.v_slot, F_SLOT), SetDeaths(CP, SetTo, ps.v_left, F_LEFT),
                      SetDeaths(CP, SetTo, ps.v_len, F_REM))
            mine(ps.v_slot)

        return _bgm_start

    def _emit_advance(self, ps):
        t = ps.tables
        CP = CurrentPlayer
        if EUDIf()(Deaths(CP, AtLeast, 1, F_LEFT)):
            # 다음 조각
            DoActions(SetDeaths(CP, Subtract, 1, F_LEFT), SetDeaths(CP, Add, 1, F_CHUNK), SetDeaths(CP, Add, 1, F_SLOT))
            miss, tj, after = Forward(), Forward(), Forward()
            ph_slot, ph_len = _parts.placeholder(), _parts.placeholder()
            # 캐시: 앞 칸이 같은 표 칸으로 넘어갔으면 길이를 다시 읽지 않는다 (조건 1 = 칸 번호, 액션 1 = 길이)
            ps.adv << RawTrigger(
                nextptr=miss,
                conditions=[ps.cache_ok.Exactly(1), Deaths(CP, Exactly, ph_slot, F_SLOT)],
                actions=[SetNextPtr(ps.adv, tj), SetDeaths(CP, SetTo, ph_len, F_REM)],
            )
            tj << RawTrigger(nextptr=after, actions=SetNextPtr(ps.adv, miss))
            miss << NextTrigger()
            f_dwread_cp(STRIDE * F_SLOT, ret=[ps.cslot])
            ln = t.lentab[ps.cslot]
            self._lead(ln)
            DoActions(SetDeaths(CP, SetTo, ln, F_REM), ps.cache_ok.SetNumber(1))
            SeqCompute([(EPD(ps.adv + 8 + 20 + 8), SetTo, ps.cslot), (EPD(ps.adv + 8 + 320 + 32 + 20), SetTo, ln)])
            after << NextTrigger()
            ps.mine_fn(ps.cslot)
        if EUDElseIf()(Deaths(CP, Exactly, 1, F_LOOP)):
            # 반복: 같은 곡을 처음부터 (돌려 쓰기는 다음 파일)
            r = f_dwread_cp(STRIDE * F_SONG)
            r += REQ_LOOP
            ps.start_fn(r)
        if EUDElse()():
            DoActions(SetDeaths(CP, SetTo, 0, F_SONG), ps.active.SubtractNumber(1), ps.ended.SetNumber(1))
        EUDEndIf()

    def _emit_requests(self, ps):
        CP = CurrentPlayer
        synced = self.mode == "synced"
        B = ps.B
        if synced:
            RawTrigger(actions=ps.all_eff.SetNumber(0))
            SeqCompute([(ps.all_eff, SetTo, ps.req_all)])
            if self.busy == "queue":
                RawTrigger(conditions=ps.active.AtLeast(1), actions=ps.all_eff.SetNumber(0))
        DoActions(*SetCurrentPlayer(B + ps.lo), ps.keep.SetNumber(0))
        rloop = NextTrigger()
        rclear, rnext, rend, forced = Forward(), Forward(), Forward(), Forward()
        EUDJumpIfNot(Deaths(CP, AtLeast, 1, F_EN), rclear)
        r = ps.r
        if synced:
            # 칸 요청이 없으면 읽지 않고 전원 요청을 쓴다
            if EUDIf()(Deaths(CP, AtLeast, 1, F_REQ)):
                f_dwread_cp(STRIDE * F_REQ, ret=[r])
            if EUDElse()():
                r << ps.all_eff
            EUDEndIf()
        else:
            f_dwread_cp(STRIDE * F_REQ, ret=[r])
        EUDJumpIf(r.Exactly(0), rclear)
        _parts.jump_if(r.AtLeast(REQ_FORCE), forced, acts=r.SubtractNumber(REQ_FORCE))
        if self.busy != "replace":
            EUDJumpIfNot(Deaths(CP, AtLeast, 1, F_SONG), forced)
            if self.busy == "drop":
                if ps.busy_slot is not None:
                    ps.mine_fn(ps.busy_slot)
                EUDJump(rclear)
            else:  # queue: 이 칸의 요청을 남긴다 (전원 요청은 all_eff = 0 이라 여기 오지 않는다)
                DoActions(ps.keep.SetNumber(1))
                EUDJump(rnext)
        forced << NextTrigger()
        ps.start_fn(r)
        rclear << RawTrigger(actions=SetDeaths(CP, SetTo, 0, F_REQ))
        rnext << NextTrigger()
        EUDBranch(Memory(CP_ADDR, AtMost, B + ps.hi - 1), rloop, rend, _actions=AddCurrentPlayer(1))
        rend << NextTrigger()
        if synced:
            if self.busy == "queue":
                RawTrigger(conditions=[ps.req_all.AtLeast(1), ps.all_eff.Exactly(0)], actions=ps.keep.SetNumber(1))
                RawTrigger(conditions=ps.all_eff.AtLeast(1), actions=ps.req_all.SetNumber(0))
                RawTrigger(actions=ps.pending.SetNumber(0))
                RawTrigger(conditions=ps.keep.AtLeast(1), actions=ps.pending.SetNumber(2))
            else:
                DoActions(ps.req_all.SetNumber(0), ps.pending.SetNumber(0))
        else:
            DoActions(ps.lnew.SetNumber(0))

    def _emit_toggle(self, ps):
        code = _local.f_key_code(self.toggle_key)
        skip = Forward()
        EUDJumpIfNot(ps.myslot.Exactly(OBSERVER_CELL), skip)
        RawTrigger(conditions=[_local.f_key_held(code), ps.obs_prev.Exactly(0), _local.f_not_typing()],
                   actions=ps.obs_off.AddNumber(1))
        RawTrigger(conditions=ps.obs_off.Exactly(2), actions=ps.obs_off.SetNumber(0))
        RawTrigger(conditions=_local.f_key_held(code), actions=ps.obs_prev.SetNumber(1))
        RawTrigger(conditions=_local.f_key_held(code, held=False), actions=ps.obs_prev.SetNumber(0))
        skip << NextTrigger()

    def _emit_local_requests(self, ps):
        skip = Forward()
        EUDJumpIf(ps.pending.Exactly(0), skip)
        if EUDIf()(ps.en_local.Exactly(1)):
            my = f_dwread_epd(ps.req_epd)
            if EUDIf()(my.Exactly(0)):
                my << ps.req_all
            EUDEndIf()
            if EUDIf()(my.AtLeast(1)):
                DoActions(SetMemory(ps.addr(F_REQ, 0), SetTo, my), ps.lnew.SetNumber(1))
            EUDEndIf()
        EUDEndIf()
        # 공유 칸은 모든 PC 가 같게 지운다
        DoActions([SetMemory(ps.shared + 4 * c, SetTo, 0) for c in range(OBSERVER_CELL + 1)],
                  ps.req_all.SetNumber(0), ps.pending.SetNumber(0))
        skip << NextTrigger()

    def _make_body(self, ps):
        player = self
        synced = self.mode == "synced"

        @EUDFunc
        def _bgm_body():
            with _local.allow():
                player._emit_body(ps, synced)

        # 공유 함수는 본문보다 먼저 정의만 해 둔다 (본문은 처음 부를 때 만들어진다)
        ps.mine_fn = self._make_mine(ps)
        ps.start_fn = self._make_start(ps)
        return _bgm_body

    def _emit_body(self, ps, synced):
        CP = CurrentPlayer
        B = ps.B
        dt = ps.dt
        # 1. 경과 시간
        if synced:
            dt << _elapsed_var(self.elapsed, "bgm.Player")
        elif self.elapsed is None:
            dt << clock.local_dt()
        else:
            dt << _elapsed_var(self.elapsed, "bgm.Player")
        if self.max_elapsed is not None:
            RawTrigger(conditions=dt.AtLeast(self.max_elapsed + 1), actions=dt.SetNumber(0))
        # 2. 관전자 로컬 끄기
        if self.toggle_key is not None and self.observers:
            self._emit_toggle(ps)
        # 3. 요청 모으기 (local)
        if not synced:
            self._emit_local_requests(ps)
        done = Forward()
        RawTrigger(actions=ps.ended.SetNumber(0))
        if synced:
            EUDJumpIf([ps.active.Exactly(0), ps.pending.Exactly(0)], done)
        else:
            EUDJumpIf(ps.en_local.Exactly(0), done)
            EUDJumpIf([Memory(ps.addr(F_SONG, 0), Exactly, 0), Memory(ps.addr(F_REQ, 0), Exactly, 0)], done)
        orig = EUDVariable()
        orig << f_getcurpl()
        # 4. 남은 시간 빼기 + 끝난 조각·곡 넘기기
        adv_skip = Forward()
        EUDJumpIf(ps.active.Exactly(0), adv_skip)
        EUDJumpIf(dt.Exactly(0), adv_skip)
        SeqCompute([(EPD(ps.sub + 8 + 320 + 20), SetTo, dt)])
        DoActions(*SetCurrentPlayer(B + ps.lo))
        loop = NextTrigger()
        ps.sub << RawTrigger(actions=SetDeaths(CP, Subtract, _parts.placeholder(), F_REM))
        cont, end = Forward(), Forward()
        EUDJumpIfNot([Deaths(CP, Exactly, 0, F_REM), Deaths(CP, AtLeast, 1, F_SONG)], cont)
        self._emit_advance(ps)
        cont << NextTrigger()
        EUDBranch(Memory(CP_ADDR, AtMost, B + ps.hi - 1), loop, end, _actions=AddCurrentPlayer(1))
        end << NextTrigger()
        adv_skip << NextTrigger()
        # 5. 요청 적용
        rq_skip = Forward()
        RawTrigger(actions=ps.go.SetNumber(0))
        if synced:
            RawTrigger(conditions=ps.pending.Exactly(1), actions=ps.go.SetNumber(1))
            RawTrigger(conditions=[ps.pending.Exactly(2), ps.ended.Exactly(1)], actions=ps.go.SetNumber(1))
        else:
            RawTrigger(conditions=ps.lnew.Exactly(1), actions=ps.go.SetNumber(1))
            RawTrigger(conditions=[Memory(ps.addr(F_REQ, 0), AtLeast, 1), ps.ended.Exactly(1)], actions=ps.go.SetNumber(1))
        EUDJumpIf(ps.go.Exactly(0), rq_skip)
        self._emit_requests(ps)
        rq_skip << NextTrigger()
        f_setcurpl(orig)
        done << NextTrigger()
