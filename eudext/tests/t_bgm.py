"""`bgm` 시험 (S5 B.10): 길이 측정(합성 wav·ogg), 곡 표·MPQ 등록, 옵션 검사, local/synced 재생기(파이썬 참조 모델과
무작위 차등 — 요청·끝남·반복·조각·돌려 쓰기·busy 정책·끄기·관전자 끄기 키·CP 복구), 여러 PC 의 공유 상태 일치,
sync.Value 경과 시간(방장 고르기·걸쇠), 시계(half·dt2·local_dt), 본문 트리거 수(대상 1명 = 11명),
epScript 예제·인게임 맵 번역·에뮬레이터 실행·euddraft 빌드(MPQAddWave 확인).

python tests/t_bgm.py
비용 표: python tools/cost.py tests/t_bgm.py [--append --bytes]

소리 파일은 저장소에 두지 않는다 — 작업 폴더(EUDEXT_WORK)에 합성한다(`examples/bgm_ingame_build.py` 의 합성기를 쓴다).
수신 펄스 주입은 이 파일 안의 작은 도우미로 한다(t_sync.py 를 import 하지 않는다).
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402
import struct  # noqa: E402
import subprocess  # noqa: E402
import wave  # noqa: E402 — 개발 venv 에만 있다(교차 확인용). 패키지 본체는 쓰지 않는다
from collections import Counter  # noqa: E402

from eudplib import (  # noqa: E402
    EPError,
    EUDBreak,
    EUDEndSwitch,
    EUDSwitch,
    EUDSwitchCase,
    EUDVariable,
    Exactly,
    LoadMap,
    CompressPayload,
    Memory,
    MPQCheckFile,
    P2,
    P10,
    f_setcurpl,
    unProxy,
)

from eudext import _compat, bgm, local, sync  # noqa: E402
from eudext import players as pl  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing import BASE_MAP, emu, scmodel  # noqa: E402
from eudext.testing.harness import Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

EX = os.path.join(_common.PKG, "examples")
sys.path.insert(0, EX)
import bgm_ingame_build as snd  # noqa: E402 — 합성기(wav·ogg)

sys.path.remove(EX)

M32 = 0xFFFFFFFF
SND = os.path.join(_common.WORK, "t_bgm_snd")
shutil.rmtree(SND, ignore_errors=True)
os.makedirs(SND, exist_ok=True)
TIME_ADDR = 0x51CE8C
KEY_DELETE_BYTE = 0x596A18 + 0x2E
TYPING_ADDR = 0x68C144
PTYPE = 0x57EEE8
BASE_MULTI = os.path.join(_common.PKG, "testing", "base_multi.scx")  # P1~P4 사람


def S(name):
    return os.path.join(SND, name)


# =============================================================================================
# 0. 소리 파일 합성 (모듈을 불러올 때 — 아래 선언이 파일을 쓴다)
# =============================================================================================

# S5 B.6 실측 표의 길이를 내는 granule (44100Hz): 파일 자체는 읽을 수 없는 헤더뿐인 Ogg
B10_OGG = {
    "GBGM1.ogg": (1459530, 33095),
    "finale_start_op.ogg": (6657680, 150967),
    "BGM364.ogg": (39320, 891),
    "ikasu001.ogg": (55708, 1263),
    "LV10_001.ogg": (29402, 666),
    "GRAVITY_OP.ogg": (4217522, 95635),
    "BGM_167.ogg": (2647376, 60031),
}
for _n, (_g, _ms) in B10_OGG.items():
    snd.write_ogg(S(_n), _g)
for _i in range(2, 273):
    snd.write_ogg(S("LV10_%03d.ogg" % _i), 29402)
for _i in range(1, 4):
    snd.write_ogg(S("TR%d.ogg" % _i), 44100 * _i)
snd.write_tone(S("short.wav"), 1000)
snd.write_tone(S("med.wav"), 100)
snd.write_tone(S("boss.wav"), 50)
for _i, _ms in enumerate((400, 600, 300), 1):
    snd.write_tone(S("ch_%02d.wav" % _i), _ms)
for _i in range(1, 4):
    snd.write_tone(S("r%d.wav" % _i), 10)
snd.write_tone(S("q1.wav"), 500)
snd.write_tone(S("q2.wav"), 800)
snd.write_tone(S("skip.wav"), 100)

# =============================================================================================
# 1. 곡 표 — B.10 "track 3개(칸 0~2) 다음 chunks 272개" 를 맨 먼저 선언한다
# =============================================================================================

bgm.set_dir(SND)
TR = [bgm.track("TR%d.ogg" % i) for i in range(1, 4)]
LV10 = bgm.chunks("LV10_{:03d}.ogg", range(1, 273))
TABLE_FIRST = bgm.table()
SHORT = bgm.track("short.wav")
MED = bgm.track("med.wav", length_ms=2500)
BOSS = bgm.track("boss.wav", length_ms=368000)
CH3 = bgm.chunks("ch_{:02d}.wav", 1, 4)
ROT = bgm.rotation(["r1.wav", "r2.wav", "r3.wav"], length_ms=700)
ROT2 = bgm.rotation(["q1.wav", "q2.wav"])
SKIP = bgm.track("skip.wav")
SONGS = [SHORT, MED, BOSS, CH3, ROT, ROT2, LV10] + TR

# 재생기 (모듈 최상위 — busy_sound 는 곡 표가 굳기 전에 만든다)
DT = EUDVariable()
PLAYERS = {
    # local
    "L_drop": bgm.Player(mode="local", targets=[0, 1, 2], elapsed=DT, busy="drop", busy_sound=SKIP),
    "L_repl": bgm.Player(mode="local", targets=[0, 1], elapsed=DT, busy="replace", observers=False),
    "L_queue": bgm.Player(mode="local", targets=[0, 1, 2], elapsed=DT, busy="queue", lead_ms=-42),
    "L_patch": bgm.Player(mode="local", targets="all", elapsed=DT, method="patch", repeat=1, lead_ms=100,
                          max_elapsed=None, busy_sound="staredit\\wav\\nowhere.wav"),
    # synced
    "S_drop": bgm.Player(mode="synced", targets=[0, 1, 2], elapsed=DT, busy="drop", busy_sound=SKIP),
    "S_queue": bgm.Player(mode="synced", targets=[0, 1, 2], elapsed=DT, busy="queue", observers=False, repeat=1),
    "S_repl": bgm.Player(mode="synced", targets=[P2], elapsed=DT, busy="replace", max_elapsed=None, method="patch",
                         lead_ms=-42),
    "S_all": bgm.Player(mode="synced", targets="all", elapsed=DT, busy="queue", lead_ms=250, repeat=3),
}
BUS = sync.Bus("msqc", qc_unit=49, name="bgmt", players=[0, 1, 2])
VAL = BUS.value(bgm.clock.local_dt(), latch=True)
VAL_RAW = BUS.value(0x58F500, latch=False)
PS_VAL = bgm.Player(mode="synced", targets=[0, 1, 2], elapsed=VAL, observers=False)
PS_RAW = bgm.Player(mode="synced", targets=[0, 1, 2], elapsed=VAL_RAW, observers=False, repeat=1)
PL_CLOCK = bgm.Player(mode="local", targets=[0], observers=False, repeat=1)
PS_ONE = bgm.Player(mode="synced", targets=[0], elapsed=DT)
PS_ELEVEN = bgm.Player(mode="synced", targets=list(range(7)) + [128, 129, P10, 131], elapsed=DT)


# =============================================================================================
# 2. 파이썬 쪽 시험 (측정·표·옵션)
# =============================================================================================


def check_measure(ck):
    # B.10 실측 표 (±1, 내림) — 합성 Ogg
    for n, (_g, ms) in B10_OGG.items():
        ck.eq("B.10 길이 " + n, bgm.measure_ms(S(n)), ms)
    info = bgm.sound_info(S("GBGM1.ogg"))
    ck.eq("ogg info", (info["kind"], info["codec"], info["rate"], info["channels"]), ("ogg", "vorbis", 44100, 2))
    # 형식 판별: 확장자 .wav + 내용 OggS
    shutil.copyfile(S("ikasu001.ogg"), S("ogg_as.wav"))
    ck.eq("OggS 내용의 .wav", bgm.measure_ms(S("ogg_as.wav")), 1263)
    # WAV 여러 형식 — 개발 venv 의 wave 모듈과 대조 (PCM)
    rng = random.Random(3)
    cases = []
    for rate in (8000, 11025, 22050, 44100, 48000):
        for bits in (8, 16, 24):
            for ch in (1, 2):
                ms = rng.randrange(1, 3000)
                ext = rng.random() < 0.3
                cases.append((rate, bits, ch, ms, ext, rng.random() < 0.4))
    for k, (rate, bits, ch, ms, ext, junk) in enumerate(cases):
        p = S("pcm_%d.wav" % k)
        frames = snd.write_tone(p, ms, rate=rate, bits=bits, channels=ch, extensible=ext, junk=junk)
        want = frames * 1000 // rate
        got = bgm.measure_ms(p)
        ok = got == want
        try:
            with wave.open(p, "rb") as w:
                ok = ok and w.getnframes() * 1000 // w.getframerate() == got
        except wave.Error:
            pass  # 3.13 wave 는 일부 확장 형식을 못 읽는다 — 합성 값과만 비교
        ck.true("pcm %r" % ((rate, bits, ch, ms, ext, junk),), ok, "got %r want %r" % (got, want))
    # float(3), IMA ADPCM(0x11) fact/byte rate, 홀수 크기 청크 뒤 data, 잘린 data
    snd.write_raw_wav(S("float.wav"), tag=3, rate=44100, channels=2, bits=32, data=bytes(8 * 44100 * 3 // 2))
    ck.eq("float 32", bgm.measure_ms(S("float.wav")), 1500)
    snd.write_raw_wav(S("adpcm_fact.wav"), tag=0x11, rate=22050, channels=1, bits=4, data=bytes(5000), fact=33075,
                      byte_rate=11100, align=512)
    ck.eq("adpcm fact", bgm.measure_ms(S("adpcm_fact.wav")), 1500)
    snd.write_raw_wav(S("adpcm_br.wav"), tag=0x11, rate=22050, channels=1, bits=4, data=bytes(11100 * 2),
                      byte_rate=11100, align=512)
    ck.eq("adpcm byte rate", bgm.measure_ms(S("adpcm_br.wav")), 2000)
    snd.write_raw_wav(S("odd.wav"), tag=1, rate=8000, channels=1, bits=8, data=bytes(8000), pre_chunks=[(b"LIST", b"abc")])
    ck.eq("홀수 청크 뒤 data", bgm.measure_ms(S("odd.wav")), 1000)
    snd.write_raw_wav(S("trunc.wav"), tag=1, rate=8000, channels=1, bits=8, data=bytes(4000), data_size=8000)
    ck.eq("잘린 data (있는 만큼)", bgm.measure_ms(S("trunc.wav")), 500)
    snd.write_raw_wav(S("stream.wav"), tag=1, rate=8000, channels=1, bits=8, data=bytes(2000), data_size=M32)
    ck.eq("크기 미상 data", bgm.measure_ms(S("stream.wav")), 250)
    # Ogg 변형: Opus(pre-skip), FLAC, 본문 속 가짜 OggS, 다른 serial, 64KB 넘는 꼬리, granule −1 페이지
    snd.write_ogg(S("opus.ogg"), 48000 * 2 + 312, codec="opus", preskip=312)
    ck.eq("opus pre-skip", bgm.measure_ms(S("opus.ogg")), 2000)
    snd.write_ogg(S("flac.ogg"), 96000 * 3 + 50, codec="flac", rate=96000)
    ck.eq("flac", bgm.measure_ms(S("flac.ogg")), 3000)
    snd.write_ogg(S("junk.ogg"), 44100 * 5, fake_oggs=True, other_serial=44100 * 99, tail_junk=300000,
                  last_unset=True)
    ck.eq("ogg 가짜 OggS·다른 serial·긴 꼬리", bgm.measure_ms(S("junk.ogg")), 5000)
    ck.eq("ogg 가짜 OggS info", bgm.sound_info(S("junk.ogg"))["samples"], 44100 * 5)
    # 모르는 형식
    with open(S("x.mp3"), "wb") as f:
        f.write(b"ID3\x03" + bytes(100))
    ck.eq("모르는 형식 info", bgm.sound_info(S("x.mp3")), None)
    ck.raises("모르는 형식 측정", EudextError, bgm.measure_ms, S("x.mp3"))
    with open(S("bad.wav"), "wb") as f:
        f.write(b"RIFF\x10\0\0\0AVI LIST")
    ck.eq("RIFF 이지만 WAVE 아님", bgm.sound_info(S("bad.wav")), None)
    with open(S("bad.ogg"), "wb") as f:
        f.write(b"OggS" + bytes(40))
    ck.eq("OggS 이지만 코덱 헤더 없음", bgm.sound_info(S("bad.ogg")), None)


def check_table(ck):
    # B.10 표: track 3개(칸 0~2) 다음 chunks 272개 → 칸 275, 조각 곡 (시작, 개수) = (3, 272)
    t = TABLE_FIRST
    ck.eq("표 칸 수", len(t["slots"]), 275)
    ck.eq("표 곡", t["songs"][:3], [(1, "track", 0, 1), (2, "track", 1, 1), (3, "track", 2, 1)])
    ck.eq("조각 곡 (시작, 개수)", t["songs"][3], (4, "chunks", 3, 272))
    ck.eq("표 이름", [s[0] for s in t["slots"][:4]],
          ["staredit\\wav\\TR1.ogg", "staredit\\wav\\TR2.ogg", "staredit\\wav\\TR3.ogg", "staredit\\wav\\LV10_001.ogg"])
    ck.eq("표 길이", [s[1] for s in t["slots"][:5]], [1000, 2000, 3000, 666, 666])
    ck.eq("표 길이 272", sorted(set(s[1] for s in t["slots"][3:])), [666])
    ck.eq("Track", (LV10.id, LV10.kind, LV10.start, LV10.count, len(LV10.names)), (4, "chunks", 3, 272, 272))
    ck.eq("Track 값", (unProxy(LV10), LV10 == 4, int(unProxy(SHORT))), (4, True, SHORT.id))
    ck.eq("rotation", (ROT.kind, ROT.rot, ROT.lengths, ROT2.rot, ROT2.lengths), ("rotation", 0, [700] * 3, 1, [500, 800]))
    ck.eq("수동·자동 길이", (SHORT.lengths, MED.lengths, BOSS.lengths, CH3.lengths), ([1000], [2500], [368000], [400, 600, 300]))
    ck.true("repr", "chunks" in repr(LV10), repr(LV10))
    ck.eq("songs", bgm.songs()[:4], TR + [LV10])
    ck.eq("MPQ 이름·경로", (SHORT.names, SHORT.files), (["staredit\\wav\\short.wav"], [S("short.wav")]))


def check_declare_errors(ck):
    n0 = len(bgm.songs())
    snd.write_tone(S("tz.wav"), 1000)
    ck.eq("trim_ms", bgm.track("tz.wav", trim_ms=400, mpq_name="staredit\\wav\\tz_trim.wav").lengths, [600])
    ck.raises("trim 초과", EudextError, bgm.track, "tz.wav", trim_ms=1000, mpq_name="staredit\\wav\\tz2.wav")
    ck.raises("없는 파일", EudextError, bgm.track, "none.wav")
    t = bgm.track("none.wav", length_ms=5, add=False)
    ck.eq("add=False 없는 파일", (t.lengths, t.files), ([5], [None]))
    ck.raises("모르는 형식 길이 없음", EudextError, bgm.track, "x.mp3")
    ck.eq("모르는 형식 + length_ms", bgm.track("x.mp3", length_ms=1234).lengths, [1234])
    snd.write_ogg(S("zero.ogg"), 0)
    ck.raises("길이 0", EudextError, bgm.track, "zero.ogg")
    ck.raises("length_ms 0", EudextError, bgm.track, "tz.wav", length_ms=0, mpq_name="staredit\\wav\\tz3.wav")
    ck.raises("파일 이름 형식", EudextError, bgm.track, 3)
    ck.raises("mpq_name 형식", EudextError, bgm.track, "tz.wav", mpq_name=5)
    ck.raises("chunks 시작만", EudextError, bgm.chunks, "ch_{:02d}.wav", 1)
    ck.raises("chunks 빈 범위", EudextError, bgm.chunks, "ch_{:02d}.wav", range(3, 3))
    ck.raises("chunks 자리 없음", EudextError, bgm.chunks, "ch_{0}{1}.wav", [1])
    ck.raises("chunks pattern 형식", EudextError, bgm.chunks, 5, [1])
    ck.raises("chunks stop 과 목록", EudextError, bgm.chunks, "ch_{:02d}.wav", [1], 3)
    ck.raises("chunks 한 선언 안 중복", EudextError, bgm.chunks, "ch_01.wav{}", ["", ""], add=False, length_ms=1)
    ck.raises("rotation 빈 목록", EudextError, bgm.rotation, [])
    ck.raises("rotation 형식", EudextError, bgm.rotation, 5)
    old = bgm.set_dir(os.path.relpath(SND, os.getcwd()))
    ck.eq("set_dir 상대 경로", old, SND)
    bgm.set_dir(SND)
    ck.raises("set_dir 없는 폴더", EudextError, bgm.set_dir, "/nonexistent/dir")
    ck.raises("set_dir 형식", EudextError, bgm.set_dir, 3)
    ck.eq("선언 실패는 곡을 늘리지 않음", len(bgm.songs()), n0 + 3)
    # 옵션 검사
    P = bgm.Player
    for label, kw in [
        ("mode", dict(mode="x")), ("busy", dict(busy="skip")), ("method", dict(method="x")), ("repeat", dict(repeat=0)),
        ("lead", dict(lead_ms=10 ** 7)), ("max_elapsed", dict(max_elapsed=0)), ("synced elapsed 없음", dict(mode="synced")),
        ("synced LocalValue", dict(mode="synced", elapsed=bgm.clock.local_dt())),
        ("local sync.Value", dict(elapsed=VAL)), ("elapsed 형식", dict(elapsed="x")), ("elapsed 음수", dict(elapsed=-1)),
        ("busy_sound 형식", dict(busy_sound=3)), ("키", dict(observer_toggle_key="NOKEY")),
    ]:
        ck.raises("Player " + label, EudextError, P, **kw)
    ck.eq("Player repr", repr(PLAYERS["L_drop"]), "<bgm.Player local busy=drop method=switch>")


def check_mpq(ck):
    """LoadMap 뒤: 선언이 MPQAddWave 를 부르고, 같은 이름 두 번은 eudplib 중복 오류(EPError)."""
    LoadMap(BASE_MAP)
    snd.write_tone(S("a.ogg"), 100)  # 이름만 .ogg (내용 WAV)
    n0 = len(bgm.songs())
    t = bgm.track("a.ogg")
    ck.raises("MPQ 등록 이름", EPError, MPQCheckFile, "staredit\\wav\\a.ogg")
    ck.raises("같은 곡 두 번 → 중복 오류", EPError, bgm.track, "a.ogg")
    ck.eq("두 번째는 곡이 늘지 않음", (len(bgm.songs()), t.id), (n0 + 1, n0 + 1))
    try:
        MPQCheckFile("staredit\\wav\\nothing_here.ogg")
        ck.true("없는 이름은 통과", True)
    except EPError as e:
        ck.true("없는 이름은 통과", False, str(e))
    snd.write_tone(S("b_new.ogg"), 5)
    ck.raises("chunks 가운데 중복 → 아무것도 넣지 않음", EPError, bgm.chunks, "{}", ["b_new.ogg", "a.ogg"],
              length_ms=5, add=True)
    try:
        MPQCheckFile("staredit\\wav\\b_new.ogg")
        ck.true("중복 선언은 앞 파일도 넣지 않음", True)
    except EPError as e:
        ck.true("중복 선언은 앞 파일도 넣지 않음", False, str(e))
    # 곡 표가 굳은 뒤(빌드 안) 선언한 곡·busy_sound 는 이 빌드에서 쓰면 오류 — _Tables 가 LoadMap 이 비운 MPQ 목록을 다시 채운다
    _compat.reset_build_state()
    LoadMap(BASE_MAP)
    early = bgm.Player(targets=[0])
    early.cells()  # 표를 굳힌다
    ck.raises("다시 채운 MPQ 목록", EPError, MPQCheckFile, "staredit\\wav\\short.wav")
    late = bgm.track("tz.wav", mpq_name="staredit\\wav\\late.wav")
    ck.raises("굳은 뒤 선언한 곡 요청", EudextError, early.request, late)
    ck.raises("굳은 뒤 곡 번호", EudextError, early.request, late.id)
    ck.raises("굳은 뒤 busy_sound", EudextError, bgm.Player(busy_sound="staredit\\wav\\late2.wav").cells)
    _compat.reset_build_state()
    LoadMap(BASE_MAP)
    nxt = bgm.Player(targets=[0])
    nxt.cells()
    ck.true("다음 빌드는 늦은 곡도 표에 있음", nxt._ps.tables.nsongs >= late.id, "")
    _compat.reset_build_state()


def check_targets(ck):
    """대상 해석 (맵을 읽은 뒤 — base.scx 는 P1 만 사람)."""
    LoadMap(BASE_MAP)
    _compat.reset_build_state()
    cases = [
        (None, True, [0, 8]), ("humans", False, [0]), ("all", False, list(range(9))), (pl.Everyone, False, [0, 8]),
        (pl.Observers, False, [8]), (pl.All, False, list(range(8))), ([P2, 128], False, [1, 8]),
        ((3, 131, range(5, 7)), False, [3, 5, 6, 8]), (P10, False, [8]),
    ]
    for tg, obs, want in cases:
        p = bgm.Player(targets=tg, observers=obs)
        ck.eq("targets %r" % (tg,), p.cells(), want)
    for tg in ("xx", 12, [200], EUDVariable(), pl.Targets(1), pl.Allies(0)):
        p = bgm.Player(targets=tg, observers=False)
        ck.raises("targets 오류 %r" % (tg,), EudextError, p.cells)
    p = bgm.Player(targets=[], observers=False)
    ck.raises("빈 대상", EudextError, p.cells)
    _compat.reset_build_state()


def python_checks(ck):
    check_table(ck)
    check_measure(ck)
    check_declare_errors(ck)
    check_mpq(ck)
    check_targets(ck)


# =============================================================================================
# 3. 참조 모델
# =============================================================================================

F_REM, F_SONG, F_SLOT, F_CHUNK, F_LEFT, F_LOOP, F_MUTE, F_REQ, F_EN = range(9)
STOP, LOOP, FORCE = 0xFFFF, 0x10000, 0x20000


def cell_of(p):
    return p if p < 8 else 8


def slot_of_user(u):
    if u <= 7:
        return u
    if 128 <= u <= 131:
        return 8
    return 9


class Ref:
    """bgm.Player 한 개의 참조 모델 (한 PC 에서 본 모습)."""

    def __init__(self, player, cells, user, extra_names):
        tb = bgm.table()
        self.lens = [s[1] for s in tb["slots"]]
        self.names = [s[0] for s in tb["slots"]] + list(extra_names)
        self.songs = {t.id: t for t in bgm.songs()}
        self.nsongs = len(self.songs)
        self.p = player
        self.synced = player.mode == "synced"
        self.cells = cells
        self.lo, self.hi = (cells[0], cells[-1]) if self.synced else (0, 0)
        nrot = sum(1 for t in self.songs.values() if t.kind == "rotation")
        self.nf = 9 + nrot
        self.rec = [[0] * 12 for _ in range(self.nf)]
        self.user = user
        self.my = slot_of_user(user)
        if self.synced:
            for c in cells:
                self.rec[F_EN][c] = 1
            self.en_local = 0
        else:
            self.en_local = 1 if self.my in cells else 0
            self.rec[F_EN][0] = self.en_local
        self.shared = [0] * 24
        self.req_all = self.pending = self.active = 0
        self.lnew = 0
        self.obs_off = self.obs_prev = 0
        self.plays = []
        self.stats = Counter()
        self.busy_slot = None if player._busy_name is None else self.names.index(player._busy_name, len(self.lens))
        self.last_dt = 0

    # --- 요청 (케이스 본문의 op) ---
    def op(self, op, song, p):
        c = cell_of(p)
        if op == 1:
            self.req(song, None)
        elif op == 2:
            self.req(song, c)
        elif op == 3:
            self.req(song + FORCE, None)
        elif op == 4:
            self.req(song + LOOP, None)
        elif op == 5:
            self.req(STOP + FORCE, None)
        elif op == 6:
            self.req(STOP + FORCE, c)
        elif op in (7, 8):
            self.mute(c, 1 if op == 7 else 0)
        elif op in (9, 10):
            for k in range(9):
                self.mute(k, 1 if op == 9 else 0)
        elif op == 11:
            self.req(BOSS.id, 1)
        elif op == 12:
            self.req(song + LOOP + FORCE, c)
        elif op == 13:
            self.mute(c, song)
        elif op == 14:
            self.req(CH3.id, 8)

    def req(self, code, cell):
        if cell is None:
            self.req_all = code & M32
        elif self.synced:
            self.rec[F_REQ][cell] = code & M32
        else:
            self.shared[cell] = code & M32
        self.pending = 1

    def mute(self, cell, v):
        if self.synced:
            self.rec[F_MUTE][cell] = v
        else:
            self.shared[12 + cell] = v

    # --- tick ---
    def adj(self, ln):
        lead = self.p.lead_ms
        if lead > 0:
            return (ln + lead) & M32
        if lead < 0:
            return ln + lead if ln >= -lead + 1 else 1
        return ln

    def play(self, k, slot):
        if self.synced:
            mine = k == self.my and self.rec[F_MUTE][k] == 0 and self.obs_off == 0
        else:
            mine = self.shared[12 + self.my] == 0 and self.obs_off == 0
        if mine:
            self.plays += [(self.user, self.names[slot])] * self.p.repeat
        else:
            self.stats["소리 막힘"] += 1

    def start(self, k, r):
        R = self.rec
        if r == STOP:
            self.stats["정지"] += 1
            if R[F_SONG][k] >= 1:
                self.active = max(self.active - 1, 0)
                self.ended = 1
            R[F_SONG][k] = R[F_REM][k] = R[F_LOOP][k] = R[F_LEFT][k] = 0
            return
        R[F_LOOP][k] = 0
        if r >= LOOP:
            r -= LOOP
            R[F_LOOP][k] = 1
        if r == 0:
            r = M32
        if r >= self.nsongs + 1:
            R[F_LOOP][k] = 0
            self.stats["모르는 번호"] += 1
            return
        self.stats["시작 " + self.songs[r].kind] += 1
        if R[F_SONG][k] == 0:
            self.active += 1
        R[F_SONG][k] = r
        R[F_CHUNK][k] = 0
        t = self.songs[r]
        if t.kind == "rotation":
            f = 9 + t.rot
            c = R[f][k]
            slot = t.start + c
            c += 1
            if c >= t.count:
                c = 0
            R[f][k] = c
            left = 0
        else:
            slot = t.start
            left = t.count - 1
        R[F_SLOT][k], R[F_LEFT][k], R[F_REM][k] = slot, left, self.adj(self.lens[slot])
        self.play(k, slot)

    def tick(self, dt, key=0, typing=0):
        R = self.rec
        mx = self.p.max_elapsed
        if mx is not None and dt > mx:
            dt = 0
        self.last_dt = dt
        if self.p.toggle_key is not None and self.p.observers and self.my == 8:
            if key and self.obs_prev == 0 and not typing:
                self.stats["관전자 키"] += 1
                self.obs_off += 1
            if self.obs_off == 2:
                self.obs_off = 0
            self.obs_prev = 1 if key else 0
        if not self.synced and self.pending:
            if self.en_local:
                my = self.shared[self.my]
                if my == 0:
                    my = self.req_all
                if my:
                    R[F_REQ][0] = my
                    self.lnew = 1
            for c in range(9):
                self.shared[c] = 0
            self.req_all = self.pending = 0
        self.ended = 0
        if self.synced:
            if self.active == 0 and self.pending == 0:
                return
        else:
            if not self.en_local or (R[F_SONG][0] == 0 and R[F_REQ][0] == 0):
                return
        if self.active and dt:
            for k in range(self.lo, self.hi + 1):
                R[F_REM][k] = max(R[F_REM][k] - dt, 0)
                if R[F_REM][k] == 0 and R[F_SONG][k] >= 1:
                    if R[F_LEFT][k] >= 1:
                        self.stats["조각 넘김"] += 1
                        R[F_LEFT][k] -= 1
                        R[F_CHUNK][k] += 1
                        R[F_SLOT][k] += 1
                        R[F_REM][k] = self.adj(self.lens[R[F_SLOT][k]])
                        self.play(k, R[F_SLOT][k])
                    elif R[F_LOOP][k] == 1:
                        self.stats["반복"] += 1
                        self.start(k, R[F_SONG][k] + LOOP)
                    else:
                        self.stats["곡 끝"] += 1
                        R[F_SONG][k] = 0
                        self.active = max(self.active - 1, 0)
                        self.ended = 1
        if self.synced:
            go = self.pending == 1 or (self.pending == 2 and self.ended)
        else:
            go = self.lnew == 1 or (R[F_REQ][0] >= 1 and self.ended)
        if not go:
            return
        queue = self.p.busy == "queue"
        all_eff = 0
        if self.synced:
            all_eff = self.req_all
            if queue and self.active >= 1:
                all_eff = 0
        keep = 0
        for k in range(self.lo, self.hi + 1):
            if R[F_EN][k] == 0:
                R[F_REQ][k] = 0
                continue
            r = R[F_REQ][k]
            if self.synced and r == 0:
                r = all_eff
            if r == 0:
                R[F_REQ][k] = 0
                continue
            if r >= FORCE:
                r -= FORCE
            elif self.p.busy != "replace" and R[F_SONG][k] >= 1:
                if self.p.busy == "drop":
                    self.stats["버림"] += 1
                    if self.busy_slot is not None:
                        self.play(k, self.busy_slot)
                    R[F_REQ][k] = 0
                    continue
                keep = 1
                self.stats["기다림(칸)"] += 1
                continue
            self.start(k, r)
            R[F_REQ][k] = 0
        if self.synced:
            if queue:
                if self.req_all >= 1 and all_eff == 0:
                    self.stats["기다림(전원)"] += 1
                    keep = 1
                if all_eff >= 1:
                    self.req_all = 0
                self.pending = 2 if keep else 0
            else:
                self.req_all = self.pending = 0
        else:
            self.lnew = 0

    def shared_state(self):
        """모든 PC 에서 같아야 하는 값."""
        if self.synced:
            return (tuple(tuple(r) for r in self.rec), self.req_all, self.pending, self.active)
        return (tuple(self.shared), self.req_all, self.pending)


# =============================================================================================
# 4. 에뮬레이터 빌드 (local / synced 재생기)
# =============================================================================================


def string_table():
    fn = getattr(scmodel, "string_table", None)
    if fn is not None:
        return fn()
    sec = _compat.chk_string_section()  # STR (16비트 표) 가정
    n = struct.unpack_from("<H", sec, 0)[0]
    out = {}
    for i in range(1, n + 1):
        off = struct.unpack_from("<H", sec, 2 * i)[0]
        out[i] = sec[off:sec.find(b"\0", off)]
    return out


class Recorder:
    """PlayWAV(8) 기록: (CP, 파일 이름). 문자열 표는 빌드 직후에 읽는다."""

    def __init__(self, machine):
        self.m = machine
        self.strings = {k: v.decode("utf-8", "replace") for k, v in string_table().items()}
        self.log = []
        machine.act_handlers[8] = self.on_wav

    def on_wav(self, m, f):
        self.log.append((m.dw(0x6509B0), self.strings.get(f[2], "?%d" % f[2])))

    def take(self):
        out, self.log = self.log, []
        return out


OPS = ("op", "song", "p", "op2", "song2", "p2")
STATS = {}


def op_case(player, t):
    """케이스 본문: 요청 op 두 개 → CP 설정 → tick → CP 확인. 상태는 watch 로 본다."""
    for a, b, c in (("op", "song", "p"), ("op2", "song2", "p2")):
        op, song, p = t.var(a), t.var(b), t.var(c)
        EUDSwitch(op)
        if EUDSwitchCase()(1):
            player.request(song)
            EUDBreak()
        if EUDSwitchCase()(2):
            player.request(song, p)
            EUDBreak()
        if EUDSwitchCase()(3):
            player.request(song, force=True)
            EUDBreak()
        if EUDSwitchCase()(4):
            player.loop(song)
            EUDBreak()
        if EUDSwitchCase()(5):
            player.stop()
            EUDBreak()
        if EUDSwitchCase()(6):
            player.stop(p)
            EUDBreak()
        if EUDSwitchCase()(7):
            player.mute(p, True)
            EUDBreak()
        if EUDSwitchCase()(8):
            player.mute(p, 0)
            EUDBreak()
        if EUDSwitchCase()(9):
            player.mute(None, True)
            EUDBreak()
        if EUDSwitchCase()(10):
            player.mute(None, False)
            EUDBreak()
        if EUDSwitchCase()(11):
            player.request(BOSS, 1)
            EUDBreak()
        if EUDSwitchCase()(12):
            player.loop(song, p, force=True)
            EUDBreak()
        if EUDSwitchCase()(13):
            player.mute(p, song)
            EUDBreak()
        if EUDSwitchCase()(14):
            player.request(CH3, 128)
            EUDBreak()
        EUDEndSwitch()
        op << 0
    DT << t.var("dt")
    cpv = t.var("cp")
    f_setcurpl(cpv)
    player.tick()
    t.flag("cp_raw", Memory(0x6509B0, Exactly, cpv))
    t.flag("cp_cache", Memory(0x6509B0, Exactly, _compat.cpcache_var()))
    f_setcurpl(0)
    watch_state(player, t)


def watch_state(player, t):
    rec, _n, _nf = player.state_region()
    t.watch("rec", rec)
    sh = player.shared_region()
    if sh is not None:
        t.watch("shared", sh[0])
    for k, v in player.control_vars().items():
        t.watch(k, v.getValueAddr())
    t.watch("dtv", player.last_dt().getValueAddr())


def read_state(s, name, player, ref):
    m = s.machine
    base = m.addr("%s.rec" % name)
    rec = tuple(tuple(m.dw(base + 4 * (12 * f + c)) for c in range(12)) for f in range(ref.nf))
    if ref.synced:
        return (rec, m.var("%s.req_all" % name), m.var("%s.pending" % name), m.var("%s.active" % name))
    sb = m.addr("%s.shared" % name)
    return (tuple(m.dw(sb + 4 * i) for i in range(24)), m.var("%s.req_all" % name), m.var("%s.pending" % name))


def local_view(s, name, ref):
    m = s.machine
    base = m.addr("%s.rec" % name)
    return tuple(m.dw(base + 4 * (12 * f)) for f in range(ref.nf)), m.var("%s.active" % name)


def ref_local_view(ref):
    return tuple(ref.rec[f][0] for f in range(ref.nf)), ref.active


def gen_ops(rng, synced):
    """한 사이클의 입력(op 두 개, dt, 키, 채팅 중)."""
    ids = [t.id for t in SONGS] + [SKIP.id]
    inp = {}
    for a, b, c in (("op", "song", "p"), ("op2", "song2", "p2")):
        r = rng.random()
        if r < 0.55:
            op = 0
        elif r < 0.68:
            op = 1
        elif r < 0.76:
            op = 2
        else:
            op = rng.choice((3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14))
        song = rng.choice(ids)
        if op == 13:
            song = rng.randrange(2)
        elif rng.random() < 0.03:
            song = rng.choice((len(bgm.songs()) + 1, 0x7777))  # 모르는 번호는 무시
        inp[a], inp[b], inp[c] = op, song, rng.choice((0, 1, 2, 3, 128, 130))
    inp["dt"] = rng.choice((0, 1, 40, 42, 100, 250, 333, 666, 700, 999, 1000, 2500, 2501, 3000, M32))
    inp["cp"] = rng.randrange(8)
    return inp, rng.random() < 0.3, rng.random() < 0.1


def run_scenario(s, name, player, users, rng_seed, cycles):
    """같은 무작위 입력열을 이 PC 번호들로 돌려 사이클마다 참조 모델과 비교한다(판정 = 사이클 수).

    비교: 공유 상태(synced = 기록 칸 전부 + 요청·대기·곡 수, local = 공유 요청·끔 칸 + 요청 변수), local 모드의 이 PC 칸,
    이번 사이클 소리(CP, 파일 이름) 목록, tick 뒤 CP·CP 캐시, 쓴 경과 시간.
    반환: {user: (공유 상태 목록, 사이클별 소리 목록)}
    """
    rec = s.machine.bgm_rec
    results = {}
    for user in users:
        s.restart(local_player=user)
        rec.take()
        ref = Ref(player, player.cells(), user, bgm_extra())
        rng = random.Random(rng_seed)
        states, plays = [], []
        key = 0
        ok = True
        for cyc in range(cycles):
            inp, key_on, typing = gen_ops(rng, ref.synced)
            key = (1 - key) if key_on else key
            s.machine.setdb(KEY_DELETE_BYTE, key)
            s.machine.setdw(TYPING_ADDR, 1 if typing else 0)
            for a, b, c in (("op", "song", "p"), ("op2", "song2", "p2")):
                ref.op(inp[a], inp[b], inp[c])
            ref.tick(inp["dt"] & M32, key, typing)
            r = s.run(name, inp)
            got_plays = rec.take()
            label = "u%d c%d" % (user, cyc)
            if r.error:
                ok = s.expect_true(name, False, label + " 실행", r.error)
                break
            want = ref.shared_state()
            got = read_state(s, name, player, ref)
            lv = local_view(s, name, ref) if not ref.synced else None
            rv = ref_local_view(ref) if not ref.synced else None
            ok = (got == want and got_plays == ref.plays and r["cp_raw"] == 1 and r["cp_cache"] == 1
                  and r["dtv"] == ref.last_dt and lv == rv)
            if not ok:
                # 한 번 어긋나면 이 PC 번호는 멈춘다 (모델을 에뮬레이터 상태로 맞추지 않는다)
                s.expect_true(name, False, label, "inp=%r\n got=%r\nwant=%r\n 소리 %r / %r, cp %r %r, dt %r / %r, 이 PC 칸 %r / %r" % (
                    inp, got, want, got_plays, ref.plays, r["cp_raw"], r["cp_cache"], r["dtv"], ref.last_dt, lv, rv))
                break
            s.expect_true(name, True, label)
            states.append(want)
            plays.append(list(ref.plays))
            ref.plays = []
        s.expect_true(name, ok and len(states) == cycles, "u%d %d 사이클 모두" % (user, cycles))
        results[user] = (states, plays)
        STATS.setdefault(name, Counter()).update(ref.stats)
    return results


def bgm_extra():
    return list(bgm._extra)  # 곡 표 밖 소리(busy_sound) — 재생 함수의 칸 순서


def build_players_suite():
    s = Suite("t_bgm players", memory={"local_player": 0, "players": ["human"] * 3})
    for name, player in PLAYERS.items():
        s.case(name)(lambda t, player=player: op_case(player, t))
    return s


def run_players(s, ck):
    m = s.build()
    m.bgm_rec = Recorder(m)
    users_local = (0, 1, 2, 128)
    for i, (name, player) in enumerate(PLAYERS.items()):
        cycles = 700
        res = run_scenario(s, name, player, users_local, 100 + i, cycles)
        if player.mode == "synced":
            base = None
            for user, (states, plays) in res.items():
                if base is None:
                    base = states
                ck.true("%s 공유 상태 u0 = u%d" % (name, user), states == base, "")
                ck.true("%s u%d 소리는 이 PC 에게만" % (name, user),
                        all(cp == user for cyc in plays for cp, _n in cyc), "")
        else:
            base = None
            for user, (states, _plays) in res.items():
                if base is None:
                    base = states
                ck.true("%s 공유 칸 u0 = u%d" % (name, user), states == base, "")
        n_play = sum(len(c) for _st, pls in res.values() for c in pls)
        ck.true("%s 소리 기록이 있음" % name, n_play > 0, "")
    for name, st in STATS.items():
        print("  %s 무작위 사건: %s" % (name, dict(sorted(st.items()))))
        need = ["시작 track", "시작 chunks", "시작 rotation", "조각 넘김", "곡 끝", "반복", "정지", "모르는 번호", "소리 막힘"]
        need += {"drop": ["버림"], "queue": ["기다림(칸)"], "replace": []}[PLAYERS[name].busy]
        if PLAYERS[name].busy == "queue" and PLAYERS[name].mode == "synced":
            need.append("기다림(전원)")  # local 모드는 전원 요청을 자기 칸에 합친다
        if PLAYERS[name].observers:
            need.append("관전자 키")
        ck.true("%s 무작위 사건이 모두 나옴" % name, all(st[k] > 0 for k in need), repr([k for k in need if not st[k]]))
    b10_local(s, ck)
    b10_synced(s, ck)
    return s


def b10_local(s, ck):
    """B.10 local 모드 기대값 (L_drop)."""
    name, player = "L_drop", PLAYERS["L_drop"]
    rec = s.machine.bgm_rec
    s.restart(local_player=1)
    rec.take()

    def cyc(**inp):
        full = {k: 0 for k in OPS}
        full.update({"dt": 0, "cp": 0})
        full.update(inp)
        r = s.run(name, full)
        view, active = local_view(s, name, _dummy_ref(player))
        return r, view, active, rec.take()

    r, v, act, plays = cyc(op=1, song=BOSS.id)
    ck.eq("B.10 local 요청 BOSS", (v[F_REM], v[F_SONG], v[F_REQ], s.machine.var(name + ".req_all"), act),
          (368000, BOSS.id, 0, 0, 1))
    ck.eq("B.10 local 소리", plays, [(1, "staredit\\wav\\boss.wav")] * 2)
    r, v, act, plays = cyc(op=1, song=SHORT.id, dt=1000)
    ck.eq("B.10 재생 중 요청 → drop", (v[F_REM], v[F_SONG], v[F_REQ], plays),
          (367000, BOSS.id, 0, [(1, "staredit\\wav\\skip.wav")] * 2))
    for _ in range(366):
        r, v, act, plays = cyc(dt=1000)
    ck.eq("B.10 367초 뒤", (v[F_REM], v[F_SONG], act), (1000, BOSS.id, 1))
    r, v, act, plays = cyc(dt=1000)
    ck.eq("B.10 368초 → 끝", (v[F_REM], v[F_SONG], act, plays), (0, 0, 0, []))
    r, v, act, plays = cyc(op=1, song=SHORT.id, dt=1000)
    ck.eq("B.10 다음 요청 재생", (v[F_REM], v[F_SONG], plays), (1000, SHORT.id, [(1, "staredit\\wav\\short.wav")] * 2))
    # 조각: LV10 → 조각 0, 남은 666 → … → 조각 271 뒤 끝
    r, v, act, plays = cyc(op=3, song=LV10.id, dt=0)
    ck.eq("B.10 LV10 요청", (v[F_SONG], v[F_CHUNK], v[F_REM], v[F_LEFT], plays[:1]),
          (LV10.id, 0, 666, 271, [(1, "staredit\\wav\\LV10_001.ogg")]))
    seen = [plays]
    chunks = [v[F_CHUNK]]
    for _ in range(272):
        r, v, act, plays = cyc(dt=666)
        seen.append(plays)
        chunks.append(v[F_CHUNK])
    names = [n for pl_ in seen for _cp, n in pl_]
    ck.eq("B.10 LV10 272조각 순서", names, [n for n in LV10.names for _ in range(2)])
    ck.eq("B.10 LV10 조각 번호", chunks, list(range(272)) + [271])
    ck.eq("B.10 LV10 끝", (v[F_SONG], v[F_REM], act), (0, 0, 0))
    # 반복: loop(CH3) → 끝나면 조각 0 부터
    r, v, act, plays = cyc(op=4, song=CH3.id)
    for dt in (400, 600, 300):
        r, v, act, p2 = cyc(dt=dt)
        plays += p2
    ck.eq("loop 조각 곡 다시", (v[F_SONG], v[F_CHUNK], v[F_LOOP], [n for _c, n in plays]),
          (CH3.id, 0, 1, [n for n in CH3.names + CH3.names[:1] for _ in range(2)]))
    r, v, act, plays = cyc(op=5)
    ck.eq("stop", (v[F_SONG], v[F_REM], v[F_LOOP], act, plays), (0, 0, 0, 0, []))
    # 돌려 쓰기: 요청마다 다음 파일
    got = []
    for _ in range(4):
        r, v, act, plays = cyc(op=3, song=ROT.id, dt=0)
        got += [n for _c, n in plays[::2]]
    ck.eq("rotation 순서", got, ["staredit\\wav\\r1.wav", "staredit\\wav\\r2.wav", "staredit\\wav\\r3.wav",
                                 "staredit\\wav\\r1.wav"])
    # 끄기: 이 PC(1) 끔 → 소리 없음, 상태는 흐름
    r, v, act, plays = cyc(op=7, p=1, op2=3, song2=SHORT.id)
    ck.eq("mute → 소리 없음", (v[F_SONG], v[F_REM], plays), (SHORT.id, 1000, []))
    r, v, act, plays = cyc(op=8, p=1, op2=3, song2=MED.id)
    ck.eq("unmute → 소리", (v[F_SONG], plays), (MED.id, [(1, "staredit\\wav\\med.wav")] * 2))
    # 대상이 아닌 PC (L_repl 대상 0,1 — 이 PC 2)
    name2, p2 = "L_repl", PLAYERS["L_repl"]
    s.restart(local_player=2)
    rec.take()
    full = {k: 0 for k in OPS}
    full.update({"dt": 0, "cp": 0, "op": 1, "song": SHORT.id})
    s.run(name2, full)
    v, act = local_view(s, name2, _dummy_ref(p2))
    ck.eq("대상 아닌 PC", (v[F_SONG], v[F_EN], act, rec.take(), s.machine.var(name2 + ".pending")), (0, 0, 0, [], 0))


def _dummy_ref(player):
    class R:
        nf = 9 + sum(1 for t in bgm.songs() if t.kind == "rotation")

    return R


def b10_synced(s, ck):
    """B.10 synced 기대값: elapsed 3000 → 그대로, 끈 플레이어 → 기록 없음, queue → 전원 0 이 된 사이클에 적용."""
    rec = s.machine.bgm_rec
    name = "S_drop"
    s.restart(local_player=1)
    rec.take()
    nf = _dummy_ref(None).nf

    def cyc(nm, **inp):
        full = {k: 0 for k in OPS}
        full.update({"dt": 0, "cp": 0})
        full.update(inp)
        s.run(nm, full)
        m = s.machine
        base = m.addr("%s.rec" % nm)
        rec_ = [[m.dw(base + 4 * (12 * f + c)) for c in range(12)] for f in range(nf)]
        return rec_, rec.take()

    R, plays = cyc(name, op=7, p=1, op2=1, song2=BOSS.id)
    ck.eq("S 끈 플레이어 → 기록 없음", ([R[F_SONG][c] for c in (0, 1, 2, 8)], R[F_MUTE][1], plays),
          ([BOSS.id] * 4, 1, []))
    R, plays = cyc(name, dt=3000)
    ck.eq("S elapsed 3000 → 그대로", [R[F_REM][c] for c in (0, 1, 2, 8)], [368000] * 4)
    R, plays = cyc(name, dt=2500)
    ck.eq("S elapsed 2500 → 뺌", [R[F_REM][c] for c in (0, 1, 2, 8)], [365500] * 4)
    R, plays = cyc(name, op=8, p=1, op2=3, song2=SHORT.id)
    ck.eq("S 켠 뒤 강제 요청 → 이 PC 칸만 소리", plays, [(1, "staredit\\wav\\short.wav")] * 2)
    # queue: 칸마다 길이가 다른 곡 → 전원 요청은 모두 끝난 사이클에 적용
    nq = "S_queue"
    R, plays = cyc(nq, op=2, song=SHORT.id, p=0, op2=2, song2=MED.id, p2=1)
    R, plays = cyc(nq, op=2, song=CH3.id, p=2)
    ck.eq("queue 준비", [R[F_SONG][c] for c in range(3)], [SHORT.id, MED.id, CH3.id])
    R, plays = cyc(nq, op=1, song=BOSS.id, dt=500)
    ck.eq("queue 기다림", ([R[F_SONG][c] for c in range(3)], s.machine.var(nq + ".pending"),
                          s.machine.var(nq + ".req_all")), ([SHORT.id, MED.id, CH3.id], 2, BOSS.id))
    t_all = None
    for i in range(1, 20):
        R, plays = cyc(nq, dt=250)
        if [R[F_SONG][c] for c in range(3)] == [BOSS.id] * 3:
            t_all = i
            break
        ck.true("queue 중간 c%d" % i, BOSS.id not in [R[F_SONG][c] for c in range(3)], repr(R[F_SONG][:3]))
    # 남은 시간: SHORT 1000, MED 2500, CH3 1300(400+600+300) → 500 뒤 250 씩: MED 가 2000/250 = 8 사이클째 끝
    ck.eq("queue 전원 0 인 사이클에 적용", (t_all, plays), (8, [(1, "staredit\\wav\\boss.wav")]))
    ck.eq("queue 적용 뒤", (s.machine.var(nq + ".pending"), s.machine.var(nq + ".req_all")), (0, 0))


# =============================================================================================
# 5. sync.Value 경과 시간, 시계, 본문 크기, 오류 케이스
# =============================================================================================


def build_misc_suite():
    s = Suite("t_bgm misc", base_map=BASE_MULTI, memory={"local_player": 0, "players": ["human"] * 3},
              init_mem={TIME_ADDR: 0x40000123})

    @s.case("clock")
    def _(t):
        # 이 빌드의 첫 tick → 시계 update 가 여기에 생긴다
        e = t.var("e")
        for a in ("op",):
            op, song = t.var(a), t.var("song")
            EUDSwitch(op)
            if EUDSwitchCase()(1):
                PL_CLOCK.request(song)
                EUDBreak()
            EUDEndSwitch()
            op << 0
        PL_CLOCK.tick()
        t.out("half", bgm.clock.half_value())
        t.flag("halfc", bgm.clock.half())
        t.out("b", bgm.clock.dt2(e))
        with local.allow():
            t.out("ldt", bgm.clock.local_dt())
        watch_state(PL_CLOCK, t)

    @s.case("value")
    def _(t):
        sync.update()
        op, song = t.var("op"), t.var("song")
        EUDSwitch(op)
        if EUDSwitchCase()(1):
            PS_VAL.request(song)
            EUDBreak()
        EUDEndSwitch()
        op << 0
        PS_VAL.tick()
        watch_state(PS_VAL, t)
        t.watch("vout", VAL.out.addr())
        t.watch("vlatch", VAL.latch.addr())

    @s.case("raw")
    def _(t):
        op, song = t.var("op"), t.var("song")
        EUDSwitch(op)
        if EUDSwitchCase()(1):
            PS_RAW.request(song)
            EUDBreak()
        EUDEndSwitch()
        op << 0
        PS_RAW.tick()
        watch_state(PS_RAW, t)
        t.watch("rout", VAL_RAW.out.addr())

    @s.case("sizes")
    def _(t):
        a = PS_ONE.body_sizes()
        b = PS_ELEVEN.body_sizes()
        PS_ONE.tick()
        PS_ELEVEN.tick()
        SIZES["one"], SIZES["eleven"] = a, b
        SIZES["cells"] = (PS_ONE.cells(), PS_ELEVEN.cells())

    @s.case("tick_twice", expect_build_error=EudextError, expect_message="한 번")
    def _(t):
        p = bgm.Player(targets=[0], elapsed=5)
        p.tick()
        p.tick()

    @s.case("bad_song", expect_build_error=EudextError, expect_message="곡은")
    def _(t):
        PS_ONE.request(0)

    @s.case("bad_song2", expect_build_error=EudextError, expect_message="선언한 곡이 아닙니다")
    def _(t):
        fake = bgm.Track(1, "track", 0, 1)
        PS_ONE.request(fake)

    @s.case("bad_p", expect_build_error=EudextError, expect_message="CurrentPlayer")
    def _(t):
        from eudplib import CurrentPlayer

        PS_ONE.mute(CurrentPlayer)

    @s.case("bad_p2", expect_build_error=EudextError, expect_message="0~7")
    def _(t):
        PS_ONE.request(SHORT, 20)

    @s.case("bad_mute", expect_build_error=EudextError, expect_message="on 은")
    def _(t):
        PS_ONE.mute(0, 3)

    @s.case("synced_no_p", expect_build_error=EudextError, expect_message="번호가 필요")
    def _(t):
        PS_ONE.current()

    @s.case("reads")
    def _(t):
        # synced 읽기 (상수·변수 p) + local 읽기 (LocalValue)
        pv = t.var("pv")
        t.out("cur0", PS_ONE.current(0))
        t.out("curv", PS_ELEVEN.current(pv))
        t.out("chunkv", PS_ELEVEN.chunk(pv))
        t.out("remv", PS_ELEVEN.remaining(pv))
        t.flag("playv", PS_ELEVEN.is_playing(pv))
        t.flag("play8", PS_ELEVEN.is_playing(130))
        with local.allow():
            t.out("lcur", PL_CLOCK.current())
            t.flag("lplay", PL_CLOCK.is_playing())
        LOCAL_TYPES.append((type(PL_CLOCK.current()).__name__, type(PL_CLOCK.is_playing()).__name__))
        rec, _n, _f = PS_ELEVEN.state_region()
        t.watch("rec11", rec)

    return s


SIZES = {}
LOCAL_TYPES = []


def run_misc(s, ck):
    m = s.build()
    rec = Recorder(m)
    ck.eq("본문 크기 대상 1명 = 11명", SIZES["one"], SIZES["eleven"])
    ck.eq("대상 칸", SIZES["cells"], ([0, 8], [0, 1, 2, 3, 4, 5, 6, 8]))
    print("  본문 크기:", SIZES["one"])
    ck.eq("local 읽기 형식", LOCAL_TYPES[0], ("LocalValue", "LocalCondition"))
    # --- 시계 ---
    T = 0x40000123
    rng = random.Random(7)
    halfs, bs, ldts = [], [], []
    es = [rng.randrange(0, 3000) for _ in range(12)]
    deltas = [5, 100, 0, 42, 65535, 1, 300, 0x123, 7, 9, 0x10000 + 5, 60]
    for i in range(12):
        T = (T - deltas[i]) & M32
        m.setdw(TIME_ADDR, T)
        r = s.run("clock", {"e": es[i]})
        halfs.append((r["half"], r["halfc"]))
        bs.append(r["b"])
        ldts.append(r["ldt"])
    ck.eq("half 0,1,0,1…", halfs, [(i % 2 ^ 1, i % 2 ^ 1) for i in range(12)])
    want_b, a, b = [], 0, 0
    for i, e in enumerate(es):
        if i % 2 == 1:  # half 가 0 인 사이클에 A ← e
            a = e
        else:
            b = a + e
        want_b.append(b)
    ck.eq("dt2 = 연속 두 사이클 합", bs, want_b)
    ck.eq("local_dt = 0x51CE8C 차이 (16비트)", ldts, [d & 0xFFFF for d in deltas])
    # 시계로 도는 local 재생기: 400ms 씩 흐르면 SHORT(1000) 는 세 번째 사이클에 끝, 5000 은 무시(max 2500)
    rec.take()
    T = (T - 10) & M32
    m.setdw(TIME_ADDR, T)
    s.run("clock", {"op": 1, "song": SHORT.id, "e": 0})
    got = []
    for d in (400, 5000, 400, 400):
        T = (T - d) & M32
        m.setdw(TIME_ADDR, T)
        s.run("clock", {"e": 0})
        base = m.addr("clock.rec")
        got.append((m.dw(base + 4 * 12 * F_SONG), m.dw(base), m.var("clock.dtv")))
    ck.eq("시계 재생기", (got, rec.take()), ([(SHORT.id, 600, 400), (SHORT.id, 600, 0), (SHORT.id, 200, 400), (0, 0, 400)],
                                        [(0, "staredit\\wav\\short.wav")]))
    # --- sync.Value: 방장(가장 작은 번호의 사람) 몫, 걸쇠 ---
    out = m.addr("value.vout")
    latch = m.addr("value.vlatch")
    s.run("value", {"op": 1, "song": BOSS.id})
    base = m.addr("value.rec")

    def inject(vals):
        for p in range(3):
            m.setdw(out + 4 * p, vals.get(p, M32))

    seq = [({0: 50, 1: 70}, 50), ({}, 50), ({1: 9}, 50), ({0: 2600, 2: 1}, 0), ({0: 30}, 30)]
    rems = []
    for vals, want_dt in seq:
        inject(vals)
        s.run("value", {})
        rems.append((m.var("value.dtv"), m.dw(base)))
        ck.eq("Value dt %r" % (vals,), m.var("value.dtv"), want_dt)
    ck.eq("Value 남은 시간", [x[1] for x in rems], [368000 - 50, 368000 - 100, 368000 - 150, 368000 - 150, 368000 - 180])
    ck.eq("걸쇠 칸", [m.dw(latch + 4 * p) for p in range(3)], [30, 9, 1])
    # 방장(P1)이 나감 → P2 몫
    m.setdb(PTYPE, 0)
    inject({0: 1000, 1: 11})
    s.run("value", {})
    ck.eq("방장이 나가면 다음 사람 몫", m.var("value.dtv"), 11)
    inject({})
    s.run("value", {})
    ck.eq("P2 걸쇠 유지", m.var("value.dtv"), 11)
    m.setdb(PTYPE, 2)
    # 걸쇠 없는 값(UERE 방식): 못 받은 사이클 0xFFFFFFFF → max_elapsed 로 0
    out2 = m.addr("raw.rout")
    s.run("raw", {"op": 1, "song": BOSS.id})
    base2 = m.addr("raw.rec")
    got = []
    for v0 in (40, M32, 60, M32):
        for p in range(3):
            m.setdw(out2 + 4 * p, v0 if p == 0 else M32)
        s.run("raw", {})
        got.append((m.var("raw.dtv"), m.dw(base2)))
    ck.eq("걸쇠 없는 값", got, [(40, 367960), (0, 367960), (60, 367900), (0, 367900)])
    # --- 읽기 ---
    s.restart(local_player=0)
    r = s.run("reads", {"pv": 1})
    ck.eq("synced·local 읽기 (곡 없음)", {k: r[k] for k in ("cur0", "curv", "chunkv", "remv", "playv", "play8", "lcur", "lplay")},
          dict(cur0=0, curv=0, chunkv=0, remv=0, playv=0, play8=0, lcur=0, lplay=0))
    rb = m.addr("reads.rec11")
    for f, v in ((F_SONG, 7), (F_CHUNK, 3), (F_REM, 99)):
        m.setdw(rb + 4 * (12 * f + 1), v)
    m.setdw(rb + 4 * (12 * F_SONG + 8), 2)
    for pv, want in ((1, dict(curv=7, chunkv=3, remv=99, playv=1, play8=1)),
                     (0, dict(curv=0, chunkv=0, remv=0, playv=0, play8=1)),
                     (130, dict(curv=2, chunkv=0, remv=0, playv=1, play8=1))):
        r = s.run("reads", {"pv": pv})
        ck.eq("synced 변수 p 읽기 %d" % pv, {k: r[k] for k in want}, want)
    for cname in ("tick_twice", "bad_song", "bad_song2", "bad_p", "bad_p2", "bad_mute", "synced_no_p"):
        ck.true("빌드 오류 " + cname, s.cases[cname].caught is not None, "")
    return s


# =============================================================================================
# 6. epScript 예제·인게임 맵
# =============================================================================================


def eps_checks(ck):
    for name, needles in (
        ("bgm_example.eps", ("bgm.f_track(\"bgm_op.wav\")", "bgm.f_chunks(", "bgm.f_rotation(FlattenList([",
                             "bgm.Player(mode=\"local\"", "player.tick()", "player.request(OP)",
                             "player.loop(LOOPED, force=True)", "bgm.clock.half()")),
        ("bgm_ingame.eps", ("bgm.Player(", "bus.value(bgm.clock.local_dt(), latch=True)", "method=\"patch\"",
                            "lead_ms=-42", "player_s.tick()")),
    ):
        src = open(os.path.join(EX, name), encoding="utf-8").read()
        out, nerr = _compat.eps_compile(name, src)
        ck.eq("eps 오류 " + name, nerr, 0)
        for nd in needles:
            ck.true("eps %s: %s" % (name, nd), out is not None and nd in out, "")


def eps_emulate(ck):
    """예제를 작업 폴더에서 EPSLoader 로 싣고 에뮬레이터에서 돌린다(소리 순서)."""
    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_bgm_eps")
    shutil.rmtree(work, ignore_errors=True)
    snd.generate(work, which="example", build_eds=False)
    LoadMap(BASE_MAP)
    CompressPayload(True)
    cwd = os.getcwd()
    os.chdir(work)
    try:
        mod = build._load_plugin(os.path.join(work, "bgm_example.eps"), {})
    finally:
        os.chdir(cwd)

    def body():
        mod.beforeTriggerExec()
        mod.afterTriggerExec()

    prog = emu.Program(body)
    prog.watch("frame", mod.frame)
    m = prog.build()
    scmodel.install(m, local_player=0)
    m.setdw(TIME_ADDR, 0x7FFFFFFF)
    rec = Recorder(m)
    m.cycle(2)
    T = 0x7FFFFFFF
    timeline = []
    for f in range(700):
        T -= 42
        m.setdw(TIME_ADDR, T)
        m.cycle()
        for cp, n in rec.take():
            timeline.append((m.var("frame"), cp, n))
    names = [n for _f, _c, n in timeline]
    print("  예제 소리: %r" % [(f, n.split("\\")[-1]) for f, _c, n in timeline[::2]])
    ck.eq("예제 소리 CP", sorted(set(c for _f, c, _n in timeline)), [0])
    w = "staredit\\wav\\"
    ck.eq("예제 소리 순서", names[::2][:6], [w + "bgm_op.wav", w + "bgm_piece_01.wav", w + "bgm_piece_02.wav",
                                          w + "bgm_piece_03.wav", w + "bgm_rot1.wav", w + "bgm_rot2.wav"])
    ck.true("예제 반복 곡", names.count(w + "bgm_loop.wav") >= 4, repr(names[-6:]))
    ck.eq("예제 흉내 못 낸 액션(글·로케일 판별 CreateUnit 빼고)", sorted(k for k in m.unknown if k[1] not in (9, 44)), [])


def ingame_emulate(ck):
    """인게임 확인 맵을 에뮬레이터에서 돌려 소리 순서·표시 줄 수를 확인한다."""
    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_bgm_ingame")
    shutil.rmtree(work, ignore_errors=True)
    snd.generate(work, which="ingame", build_eds=False)
    LoadMap(BASE_MULTI)
    CompressPayload(True)
    cwd = os.getcwd()
    os.chdir(work)
    try:
        mod = build._load_plugin(os.path.join(work, "bgm_ingame.eps"), {})
    finally:
        os.chdir(cwd)

    def body():
        mod.beforeTriggerExec()
        mod.afterTriggerExec()

    prog = emu.Program(body)
    prog.watch("frame", mod.frame)
    prog.watch("step", mod.step)
    m = prog.build()
    scmodel.install(m, local_player=0, players=["human"] * 4)
    m.setdw(TIME_ADDR, 0x7FFFFFFF)
    rec = Recorder(m)
    texts = []
    m.act_handlers[9] = lambda mm, f: texts.append(rec.strings.get(f[1], "?"))
    m.cycle(2)
    T = 0x7FFFFFFF
    timeline = []
    for f in snd.INGAME_FRAMES_RANGE:
        T -= 42
        m.setdw(TIME_ADDR, T)
        m.cycle()
        for cp, n in rec.take():
            if cp == 0:
                timeline.append((m.var("frame"), n.split("\\")[-1]))
    got = snd.summarize_ingame(timeline)
    print("  인게임 맵 소리 요약: %r" % (got,))
    ck.eq("인게임 맵 소리 요약", got, snd.INGAME_EXPECT)
    ck.eq("인게임 맵 단계", m.var("step"), snd.INGAME_LAST_STEP)
    ck.true("인게임 맵 표시 줄", any("[D16-1]" in x for x in texts) and any("[D16-3]" in x for x in texts), repr(texts[:5]))


def mpq_check(path, names):
    """names 중 MPQ 에서 꺼낼 수 없는 것 목록, 꺼낸 파일의 앞 4바이트 모음 (출력 맵에는 (listfile) 이 없다)."""
    missing, magics = [], set()
    for n in names:
        data = _compat.mpq_read_file(path, n)
        if data is None:
            missing.append(n)
        else:
            magics.add(data[:4])
    return missing, magics


def _run_builder(work, *args):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run([sys.executable, os.path.join(EX, "bgm_ingame_build.py"), "--work", work, *args],
                       capture_output=True, env=env, cwd=_common.WORK, timeout=900)
    return p.returncode, p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")


def eps_build(ck):
    """빌드 도우미(명령줄)로 예제·인게임 맵을 euddraft 빌드하고 MPQ 에 소리가 들었는지 본다.

    인게임 맵은 선언 수집(sync.collect)에서 Bus 이름을 쓰므로 이 프로세스(이미 같은 맵 소스를 불러옴)가 아닌 새 프로세스에서 돈다.
    """
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    for which in ("example", "ingame"):
        work = os.path.join(_common.WORK, "t_bgm_build_" + which)
        shutil.rmtree(work, ignore_errors=True)
        rc, out = _run_builder(work, "--which", which)
        print("  " + (out.strip().splitlines() or ["-"])[-1])
        ck.true("euddraft " + which, rc == 0, out[-3000:])
        out_map = os.path.join(work, "build", "bgm_%s_out.scx" % which)
        if rc != 0 or not os.path.isfile(out_map):
            continue
        want = snd.expected_mpq(which)
        missing, magics = mpq_check(out_map, want)
        ck.true("MPQ 에 소리 %s (%d개)" % (which, len(want)), not missing, repr(missing[:5]))
        ck.eq("MPQ 소리 내용 " + which, magics, {b"RIFF"})
        ck.eq("MPQ 에 없는 이름은 넣지 않음 " + which, mpq_check(out_map, ["staredit\\wav\\d16_nofile.wav"])[0],
              ["staredit\\wav\\d16_nofile.wav"])
        log = open(os.path.join(work, "build", "euddraft.log"), encoding="utf-8").read()
        ck.true("eps compiled " + which, '[epScript] Compiling "bgm_%s.eps"' % which in log, "")
    # [MSQC] 줄이 선언과 다르면 빌드 전에 멈춘다
    bad = os.path.join(_common.WORK, "t_bgm_bad.eds")
    with open(os.path.join(EX, "bgm_ingame.eds"), encoding="utf-8") as f:
        text = f.read().replace("KeyDown(B)", "KeyDown(V)")
    with open(bad, "w", encoding="utf-8") as f:
        f.write(text)
    work = os.path.join(_common.WORK, "t_bgm_build_bad")
    shutil.rmtree(work, ignore_errors=True)
    rc, out = _run_builder(work, "--which", "ingame", "--eds", bad, "--no-run")
    ck.true("[MSQC] 불일치 검출", rc != 0 and "선언과 다릅니다" in out and "KeyDown(B)" in out, out[-1500:])


# =============================================================================================
# 7. 비용 측정 항목 (tools/cost.py)
# =============================================================================================

COST_MEMORY = {"local_player": 0, "players": ["human"] * 8}
COST_DT = EUDVariable()
_cost_players = {}


@_compat.register_build_reset
def _cost_reset():
    _cost_players.clear()


def _cp(key, **kw):
    """준비 케이스가 만든 재생기(아직 tick 안 함), 없으면 새로 (페이로드 측정은 40벌)."""
    p = _cost_players.get(key)
    if p is None or p._ps is None or p._ps.ticked:
        p = bgm.Player(**kw)
        _cost_players[key] = p
        p._prepare()
        p.body_sizes()
    return p


def _cost_setup(key, poke=None, **kw):
    def setup(t):
        bgm.clock.update()
        p = _cp(key, **kw)
        from eudplib import DoActions, SetMemory

        acts = [COST_DT.SetNumber(40)]
        if poke is not None:
            acts += poke(p)
        DoActions(acts)

    return setup


def _cost_tick(key, **kw):
    def build(t):
        _cp(key, **kw).tick()

    return build


LOCAL_KW = dict(mode="local", targets=[0], observers=False, elapsed=COST_DT)
SYNC8_KW = dict(mode="synced", targets=list(range(8)), observers=False, elapsed=COST_DT)


def _poke_local_playing(p):
    from eudplib import SetMemory

    ps = p._ps
    return [SetMemory(ps.addr(F_SONG, 0), SetTo_, SHORT.id), SetMemory(ps.addr(F_REM, 0), SetTo_, 100000),
            ps.active.SetNumber(1)]


def _poke_sync(song, rem, left=0, slot=0):
    def poke(p):
        from eudplib import SetMemory

        ps = p._ps
        acts = [ps.active.SetNumber(8)]
        for c in range(8):
            acts += [SetMemory(ps.addr(F_SONG, c), SetTo_, song), SetMemory(ps.addr(F_REM, c), SetTo_, rem),
                     SetMemory(ps.addr(F_LEFT, c), SetTo_, left), SetMemory(ps.addr(F_SLOT, c), SetTo_, slot)]
        return acts

    return poke


def _poke_req_all(p):
    ps = p._ps
    return [ps.req_all.SetNumber(BOSS.id), ps.pending.SetNumber(1)]


from eudplib import SetTo as SetTo_  # noqa: E402


def _cost_request_const(t):
    _cp("req", **SYNC8_KW).request(BOSS)


def _cost_request_var(t):
    _cp("reqv", **SYNC8_KW).request(t.var("song"), t.var("p"))


def _cost_mute(t):
    _cp("mute", **SYNC8_KW).mute(3, True)


def _cost_bodies(kw, key):
    def build(t):
        p = bgm.Player(**kw)
        p.body_sizes()

    return build


def _cost_play(method, repeat):
    def build(t):
        from eudext.bgm import _tables

        tb = _tables()
        tb._play.pop((method, repeat), None)  # 시험 전용: 이 빌드에 이미 만든 재생 함수를 한 벌 더 만든다
        tb.play_func(method, repeat).size()

    return build


def _cost_clock(t):
    bgm._clock_state["emitted"] = False  # 시험 전용: 준비 케이스가 이미 낸 시계를 한 벌 더 낸다
    bgm.clock.update()


COST_CASES = [
    CostCase("tick local 곡 없음", _cost_tick("l0", **LOCAL_KW), setup=_cost_setup("l0", **LOCAL_KW),
             target={"call": 10}, note="시계 update 는 준비 케이스. 페이로드 = 재생기 1개 전체(40벌 ÷ 40)"),
    CostCase("tick local 재생 중(빼기만)", _cost_tick("l1", **LOCAL_KW),
             setup=_cost_setup("l1", poke=_poke_local_playing, **LOCAL_KW), target={"call": 10}),
    CostCase("tick synced 8칸 곡 없음", _cost_tick("s0", **SYNC8_KW), setup=_cost_setup("s0", **SYNC8_KW),
             target={"call": 10}),
    CostCase("tick synced 8칸 재생 중(빼기만)", _cost_tick("s1", **SYNC8_KW),
             setup=_cost_setup("s1", poke=_poke_sync(3, 100000), **SYNC8_KW), target={"call": 10}),
    CostCase("tick synced 8칸 조각 넘김(캐시)", _cost_tick("s2", **SYNC8_KW),
             setup=_cost_setup("s2", poke=_poke_sync(4, 40, left=5, slot=3), **SYNC8_KW), target={"call": 10},
             note="8칸이 같은 칸으로 넘어감 — 첫 칸만 길이를 읽는다"),
    CostCase("tick synced 전원 요청 → 8칸 시작", _cost_tick("s3", **SYNC8_KW),
             setup=_cost_setup("s3", poke=_poke_req_all, **SYNC8_KW), target={"call": 10},
             note="첫 칸만 표를 읽고 나머지는 캐시"),
    CostCase("request 상수(전원)", _cost_request_const, setup=_cost_setup("req", **SYNC8_KW)),
    CostCase("request 변수 곡·변수 p", _cost_request_var, inputs={"song": 3, "p": 2}, setup=_cost_setup("reqv", **SYNC8_KW)),
    CostCase("mute 상수", _cost_mute, setup=_cost_setup("mute", **SYNC8_KW)),
    CostCase("본문 synced (루프+start+play_mine)", _cost_bodies(SYNC8_KW, "b1"),
             note="호출 자리 칸 = 새 재생기 본문 트리거 합(재생 함수는 이미 있음, 실행 없음). 페이로드는 tick 없이 닿는 부분만 — 재생기 1개 전체는 tick 행"),
    CostCase("본문 local (루프+start+play_mine)", _cost_bodies(LOCAL_KW, "b2"), note="위와 같음"),
    CostCase("재생 함수 switch ×2 (칸 %d)" % (len(bgm.table()["slots"]) + len(bgm._extra)), _cost_play("switch", 2),
             note="호출 자리 칸 = 함수 본문. 칸마다 트리거 1 + 고정 19. 페이로드는 재생기 행에 들어 있다"),
    CostCase("재생 함수 patch ×2", _cost_play("patch", 2), note="호출 자리 칸 = 함수 본문(칸 수와 무관)"),
    CostCase("clock.update", _cost_clock, note="빌드에 한 번(사이클마다 실행). 시작 때 시간 읽기 1회"),
]


def main():
    ck = Checker("t_bgm (python)")
    python_checks(ck)
    s1 = build_players_suite()
    run_players(s1, ck)
    ok1 = s1.report()
    s2 = build_misc_suite()
    run_misc(s2, ck)
    ok2 = s2.report()
    cke = Checker("t_bgm (epScript)")
    eps_checks(cke)
    eps_emulate(cke)
    ingame_emulate(cke)
    eps_build(cke)
    finish(ok1, ok2, ck.report(), cke.report())


if __name__ == "__main__":
    main()
