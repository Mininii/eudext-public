"""eudext.bgm 확인 맵 빌드 도우미: 소리 파일 합성 + eds 준비 + euddraft (S5 B.11, docs/INGAME_CHECKLIST.md D16-*).

    python eudext/examples/bgm_ingame_build.py --work <작업 폴더> [--which ingame|example] [--ogg <진짜 .ogg>] [--no-run]

- 저장소에는 소리 파일을 두지 않는다. 이 스크립트가 작업 폴더에 WAV 를 합성한다(struct 만 — 사인파 PCM).
- `ingame`(기본): `bgm_ingame.eps` + `bgm_ingame.eds`(기준 맵 `testing/base_multi.scx`, `[MSQC]` 포함).
  eds 의 `[MSQC]` 줄이 맵 소스의 선언과 같은지 먼저 확인한다(`sync.collect`). `--ogg` 로 진짜 Ogg Vorbis 파일을 주면
  `d16_ogg_as.wav` 이름으로 넣는다(D16-6). 주지 않으면 같은 이름의 WAV 를 넣는다(그 항목은 건너뛴다).
- `example`: `bgm_example.eps` + `bgm_example.eds`(기준 맵 `testing/base.scx`).
- 폴더 구성: `<work>/src`(맵 소스·eds·소리) → `tools/build.prepare_eds` 로 `<work>/build` 에 옮기고 소리 폴더도 복사한다.
  맵 소스는 `bgm.set_dir("<소리 폴더>")` 로 자기 옆의 소리 폴더를 찾는다.
- `tools/ingame_maps.py` 에서 부를 때: `generate(work, base_map=…)` → (eds, 출력 맵) 을 받아 `run_euddraft` 만 하면 된다
  (이미 `prepare_eds` 를 거친 eds 다).

이 파일의 합성기(`write_tone`, `write_raw_wav`, `write_ogg`)는 `tests/t_bgm.py` 도 쓴다.
"""

import argparse
import math
import os
import shutil
import struct
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BASE_MAP = os.path.join(PKG, "testing", "base.scx")
BASE_MULTI = os.path.join(PKG, "testing", "base_multi.scx")
WAV_DIR = "staredit\\wav\\"

# =============================================================================================
# WAV 합성
# =============================================================================================


def _pcm_bytes(samples, bits):
    if bits == 8:
        return bytes(max(0, min(255, int(round(s * 127)) + 128)) for s in samples)
    if bits == 16:
        return b"".join(struct.pack("<h", max(-32768, min(32767, int(round(s * 32767))))) for s in samples)
    if bits == 24:
        out = bytearray()
        for s in samples:
            v = max(-8388608, min(8388607, int(round(s * 8388607))))
            out += struct.pack("<i", v)[:3]
        return bytes(out)
    raise ValueError("bits %r" % bits)


def write_raw_wav(path, tag, rate, channels, bits, data, fact=None, byte_rate=None, align=None, pre_chunks=(),
                  data_size=None, extensible=False, junk=False):
    """RIFF/WAVE 파일을 그대로 쓴다. data_size 로 data 청크 크기 칸을 속일 수 있다(잘린·크기 미상 파일)."""
    if align is None:
        align = max(1, channels * bits // 8)
    if byte_rate is None:
        byte_rate = rate * align
    if extensible:
        guid = struct.pack("<H", tag) + b"\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x00\x38\x9b\x71"
        fmt = struct.pack("<HHIIHHHHI", 0xFFFE, channels, rate, byte_rate, align, bits, 22, bits, 0) + guid
    else:
        fmt = struct.pack("<HHIIHH", tag, channels, rate, byte_rate, align, bits)
        if tag not in (1, 3):
            fmt += struct.pack("<H", 0)

    def chunk(cid, body, size=None):
        size = len(body) if size is None else size
        return cid + struct.pack("<I", size & 0xFFFFFFFF) + body + (b"\0" if len(body) & 1 else b"")

    body = b"WAVE"
    for cid, b in pre_chunks:
        body += chunk(cid, b)
    if junk:
        body += chunk(b"JUNK", b"x" * 27)
    body += chunk(b"fmt ", fmt)
    if junk:
        body += chunk(b"LIST", b"INFOISFT" + struct.pack("<I", 5) + b"eudx\0")
    if fact is not None:
        body += chunk(b"fact", struct.pack("<I", fact))
    if data_size is None:
        body += chunk(b"data", data)
        if junk:
            body += chunk(b"id3 ", b"tail")
    else:
        body += b"data" + struct.pack("<I", data_size & 0xFFFFFFFF) + data
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", len(body)) + body)


def tone_samples(n, rate, freq=440.0, amp=0.3, phase=0.0, freq_end=None, fade=0.0):
    """사인파 표본 목록과 끝 위상. freq_end 가 있으면 선형 스윕. fade(초)만큼 앞뒤를 줄인다."""
    out = []
    ph = phase
    fl = int(fade * rate)
    for i in range(n):
        f = freq if freq_end is None else freq + (freq_end - freq) * i / max(1, n)
        g = 1.0
        if fl:
            g = min(1.0, (i + 1) / fl, (n - i) / fl)
        out.append(amp * g * math.sin(ph))
        ph += 2 * math.pi * f / rate
    return out, ph % (2 * math.pi)


def write_tone(path, ms, rate=8000, bits=8, channels=1, extensible=False, junk=False, freq=440.0, amp=0.3,
               phase=0.0, freq_end=None, fade=0.0):
    """ms 길이(표본 수 = rate·ms//1000)의 PCM WAV. 반환: 프레임 수."""
    n = rate * ms // 1000
    samples, _ph = tone_samples(n, rate, freq, amp, phase, freq_end, fade)
    frames = []
    for s in samples:
        frames.extend([s] * channels)
    write_raw_wav(path, 1, rate, channels, bits, _pcm_bytes(frames, bits), extensible=extensible, junk=junk)
    return n


def write_sweep_chunks(folder, pattern, count, chunk_ms, f0, f1, rate=22050, bits=16, amp=0.25):
    """이어지는 스윕을 count 조각으로 나눠 쓴다(위상이 이어져 틈이 없으면 매끄럽게 들린다). 반환: 파일 이름 목록."""
    n = rate * chunk_ms // 1000
    total = n * count
    ph = 0.0
    names = []
    for k in range(count):
        a = f0 + (f1 - f0) * k / count
        b = f0 + (f1 - f0) * (k + 1) / count
        samples, ph = tone_samples(n, rate, a, amp, ph, b)
        name = pattern.format(k + 1)
        write_raw_wav(os.path.join(folder, name), 1, rate, 1, bits, _pcm_bytes(samples, bits))
        names.append(name)
    assert total == n * count
    return names


# =============================================================================================
# Ogg 합성 (헤더만 — 길이 측정 시험용. 재생할 수 없다)
# =============================================================================================


def ogg_crc(data):
    """Ogg 페이지 CRC (다항식 0x04C11DB7, 반사 없음) — 비트 단위로 따로 구현(bgm.py 의 표 방식과 교차 확인)."""
    crc = 0
    for byte in data:
        crc ^= byte << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) if crc & 0x80000000 else (crc << 1)
            crc &= 0xFFFFFFFF
    return crc


def ogg_page(serial, seq, granule, body, flags=0):
    segs = []
    left = len(body)
    while left >= 255:
        segs.append(255)
        left -= 255
    segs.append(left)
    head = b"OggS" + bytes([0, flags]) + struct.pack("<qII", granule, serial, seq) + b"\0\0\0\0" + bytes([len(segs)])
    page = bytearray(head + bytes(segs) + body)
    struct.pack_into("<I", page, 22, ogg_crc(page))
    return bytes(page)


def write_ogg(path, granule, codec="vorbis", rate=44100, preskip=0, fake_oggs=False, other_serial=None, tail_junk=0,
              last_unset=False):
    """첫 페이지 = 코덱 식별 헤더, 마지막 페이지 granule = granule 인 Ogg 파일."""
    serial = 0x1234ABCD
    if codec == "vorbis":
        ident = b"\x01vorbis" + struct.pack("<IBIiiiBB", 0, 2, rate, 0, 128000, 0, 0xB8, 1)
    elif codec == "opus":
        ident = b"OpusHead" + struct.pack("<BBHIhB", 1, 2, preskip, rate, 0, 0)
    elif codec == "flac":
        info = bytearray(34)
        struct.pack_into(">HH", info, 0, 4096, 4096)
        v = (rate << 44) | (1 << 41) | (15 << 36) | granule
        info[10:18] = v.to_bytes(8, "big")
        ident = b"\x7fFLAC" + bytes([1, 0]) + struct.pack(">H", 1) + b"fLaC" + bytes([0, 0, 0, 34]) + bytes(info)
    else:
        raise ValueError(codec)
    pages = [ogg_page(serial, 0, 0, ident, flags=2), ogg_page(serial, 1, 0, b"\x03vorbis" + bytes(40))]
    audio = bytearray((i * 131 + granule) & 0xFF for i in range(700))
    if fake_oggs:
        audio[100:104] = b"OggS"
        audio[104] = 0
        audio[500:504] = b"OggS"
    pages.append(ogg_page(serial, 2, granule // 2, bytes(audio)))
    pages.append(ogg_page(serial, 3, granule, bytes(audio[:300]), flags=0 if last_unset else 4))
    if last_unset:
        pages.append(ogg_page(serial, 4, -1, bytes(500), flags=4))
    if other_serial is not None:
        pages.append(ogg_page(serial + 1, 0, other_serial, bytes(100), flags=6))
    data = b"".join(pages)
    if tail_junk:
        junk = bytearray(tail_junk)
        for pos in range(1000, tail_junk - 100, 50000):
            junk[pos:pos + 4] = b"OggS"  # CRC 가 맞지 않는 가짜
            junk[pos + 4] = 0
            junk[pos + 26] = 1
        data += bytes(junk)
    with open(path, "wb") as f:
        f.write(data)


# =============================================================================================
# 확인 맵 소리
# =============================================================================================

INGAME_SND = "bgm_ingame_snd"
EXAMPLE_SND = "bgm_example_snd"
SWEEP_COUNT = 24
SYNC_COUNT = 20
LOAD_COUNT = 300
BEEPS = 8

# 에뮬레이터 기대값 (tests/t_bgm.py ingame_emulate): 사이클 42ms, 이 PC(P1) 소리만 센다
INGAME_FRAMES_RANGE = range(1000)
INGAME_LAST_STEP = 12
INGAME_EXPECT = [
    ("d16_a", 4), ("d16_b", 2), ("d16_c", 3), ("d16_sweep", 144), ("d16_nofile", 2), ("d16_missing", 2),
    ("d16_ogg_as", 2), ("d16_beep", 8),
]


def summarize_ingame(timeline):
    """[(프레임, 파일 이름)] → [(이름 앞머리, 횟수)] (처음 나온 순서)."""
    order = []
    counts = {}
    for _f, name in timeline:
        base = os.path.splitext(name)[0]
        key = base.rstrip("0123456789").rstrip("_")
        if key not in counts:
            order.append(key)
            counts[key] = 0
        counts[key] += 1
    return [(k, counts[k]) for k in order]


def make_ingame_sounds(folder, ogg=None):
    os.makedirs(folder, exist_ok=True)
    w = lambda n, **kw: write_tone(os.path.join(folder, n), rate=22050, bits=16, fade=0.01, **kw)  # noqa: E731
    w("d16_a.wav", ms=1200, freq=440)
    w("d16_b.wav", ms=1200, freq=660)
    w("d16_c.wav", ms=1200, freq=880)
    w("d16_skip.wav", ms=80, freq=1500)
    write_sweep_chunks(folder, "d16_sweep_{:02d}.wav", SWEEP_COUNT, 250, 300.0, 900.0)
    notes = [262, 294, 330, 349, 392, 440, 494, 523, 494, 440, 392, 349, 330, 294, 262, 330, 392, 523, 392, 262]
    for k in range(SYNC_COUNT):
        w("d16_sync_%02d.wav" % (k + 1), ms=500, freq=notes[k % len(notes)])
    for k in range(BEEPS):
        w("d16_beep_%d.wav" % (k + 1), ms=600, freq=500 + 150 * k, amp=0.15)
    for k in range(LOAD_COUNT):
        write_tone(os.path.join(folder, "d16_load_%03d.wav" % (k + 1)), 20, rate=8000, amp=0.0)
    dst = os.path.join(folder, "d16_ogg_as.wav")
    if ogg:
        shutil.copyfile(ogg, dst)
    else:
        w("d16_ogg_as.wav", ms=1000, freq=330)


def make_example_sounds(folder):
    os.makedirs(folder, exist_ok=True)
    w = lambda n, **kw: write_tone(os.path.join(folder, n), rate=22050, bits=16, fade=0.01, **kw)  # noqa: E731
    w("bgm_op.wav", ms=1000, freq=392)
    w("bgm_loop.wav", ms=510, freq=523)
    for k in range(3):
        w("bgm_piece_%02d.wav" % (k + 1), ms=300, freq=330 + 110 * k)
    w("bgm_rot1.wav", ms=400, freq=600)
    w("bgm_rot2.wav", ms=400, freq=700)


def expected_mpq(which):
    """빌드한 맵의 MPQ 에 있어야 할 이름."""
    if which == "example":
        names = ["bgm_op.wav", "bgm_loop.wav", "bgm_rot1.wav", "bgm_rot2.wav"] + ["bgm_piece_%02d.wav" % k for k in (1, 2, 3)]
    else:
        names = ["d16_a.wav", "d16_b.wav", "d16_c.wav", "d16_skip.wav", "d16_ogg_as.wav"]
        names += ["d16_sweep_%02d.wav" % (k + 1) for k in range(SWEEP_COUNT)]
        names += ["d16_sync_%02d.wav" % (k + 1) for k in range(SYNC_COUNT)]
        names += ["d16_beep_%d.wav" % (k + 1) for k in range(BEEPS)]
        names += ["d16_load_%03d.wav" % (k + 1) for k in range(LOAD_COUNT)]
    return [WAV_DIR + n for n in names]


# =============================================================================================
# 빌드
# =============================================================================================


def _names(which):
    if which == "example":
        return "bgm_example.eps", "bgm_example.eds", EXAMPLE_SND, BASE_MAP
    if which == "ingame":
        return "bgm_ingame.eps", "bgm_ingame.eds", INGAME_SND, BASE_MULTI
    raise ValueError("which 는 ingame 또는 example (%r)" % which)


def _read_msqc(eds):
    from eudext.tools import build

    for name, items in build.read_eds(eds):
        if name == "MSQC":
            return [(k, v) for k, v, _raw in items]
    return []


def verify_msqc(eds, source, base_map):
    """eds 의 [MSQC] 줄이 맵 소스의 선언(sync.collect)과 같은지. 다르면 RuntimeError."""
    from eudext import sync

    buses = sync.collect(source, map_path=base_map)
    want = []
    for b in buses:
        want += [tuple(x.split(" : ", 1)) for x in b.eds_lines()]
    got = [(k.strip(), v.strip()) for k, v in _read_msqc(eds)]
    want = [(k.replace("\\", ""), v.strip()) for k, v in want]
    got = [(k.replace("\\", ""), v) for k, v in got]
    if sorted(got) != sorted(want):
        raise RuntimeError("%s 의 [MSQC] 줄이 선언과 다릅니다 — 아래 줄로 고치세요:\n%s" % (
            eds, "\n".join(b.eds_fragment() for b in buses)))
    return buses


def generate(work, which="ingame", base_map=None, ogg=None, build_eds=True, run=False, verify=True, eds_src=None):
    """소리 합성 + (선택) eds 준비·euddraft.

    build_eds=False: `<work>` 에 맵 소스와 소리 폴더만 둔다(에뮬레이터 시험용). 반환: work
    build_eds=True: `<work>/src` → `<work>/build` 로 준비. 반환: (eds, 출력 맵) — run=True 면 tools.build.BuildResult
    """
    eps, eds, snd_dir, default_map = _names(which)
    base_map = os.path.abspath(base_map or default_map)
    work = os.path.abspath(work)
    src = work if not build_eds else os.path.join(work, "src")
    os.makedirs(src, exist_ok=True)
    shutil.copy2(os.path.join(HERE, eps), os.path.join(src, eps))
    if which == "ingame":
        make_ingame_sounds(os.path.join(src, snd_dir), ogg)
    else:
        make_example_sounds(os.path.join(src, snd_dir))
    if not build_eds:
        return work
    from eudext.tools import build

    shutil.copy2(os.path.join(HERE, "dbg_setup.py"), os.path.join(src, "dbg_setup.py"))  # 디버그 브리지 켜기
    _copy_eds(eds_src or os.path.join(HERE, eds), os.path.join(src, eds))
    if which == "ingame" and verify:
        verify_msqc(os.path.join(src, eds), os.path.join(src, eps), base_map)
    out_dir = os.path.join(work, "build")
    new_eds, out_map = build.prepare_eds(os.path.join(src, eds), out_dir)
    _rewrite_input(new_eds, base_map)
    shutil.rmtree(os.path.join(out_dir, snd_dir), ignore_errors=True)
    shutil.copytree(os.path.join(src, snd_dir), os.path.join(out_dir, snd_dir))
    if not run:
        return new_eds, out_map
    return build.run_euddraft(new_eds, out_map=out_map, log_path=os.path.join(out_dir, "euddraft.log"))


def _copy_eds(src_eds, dst_eds):
    """eds 를 다른 폴더로 옮기면서 원래 폴더 기준 상대 경로(부트 플러그인·EudextRoot·input)를 절대 경로로 바꾼다.

    맵 소스(.eps)처럼 eds 옆에 두는 플러그인 이름은 그대로 둔다(같이 복사한다)."""
    from eudext.tools import build

    base = os.path.dirname(os.path.abspath(src_eds))
    lines = [":: %s 에서 옮김 (bgm_ingame_build.py)" % src_eds]

    def absol(v):
        v = v.replace("\\", "/") if os.sep == "/" else v
        return os.path.normpath(os.path.join(base, v))

    for name, items in build.read_eds(src_eds):
        header = name
        is_plugin = name.lower().endswith((".py", ".eps"))
        if is_plugin and os.path.dirname(name.replace("\\", "/")):
            header = absol(name)
        lines.append("")
        lines.append("[%s]" % header)
        for key, val, raw in items:
            k = key.lower()
            if val is not None and ((name == "main" and k == "input") or k in ("eudextroot", "venvsite")):
                lines.append("%s : %s" % (key, absol(val.strip())))
            else:
                lines.append(raw)
    with open(dst_eds, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")


def _rewrite_input(eds_path, new_input):
    import re

    with open(eds_path, encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"(?mi)^(\s*input\s*:).*$", lambda m: "%s %s" % (m.group(1), new_input), text, count=1)
    with open(eds_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description="eudext.bgm 확인 맵 빌드")
    work0 = os.environ.get("EUDEXT_WORK") or os.path.join(tempfile.gettempdir(), "eudext_work")
    ap.add_argument("--work", default=None)
    ap.add_argument("--which", choices=("ingame", "example"), default="ingame")
    ap.add_argument("--example", action="store_true", help="= --which example")
    ap.add_argument("--map", default=None, help="입력 맵 (ingame 기본 testing/base_multi.scx)")
    ap.add_argument("--ogg", default=None, help="D16-6 에 쓸 진짜 Ogg Vorbis 파일 (d16_ogg_as.wav 이름으로 넣는다)")
    ap.add_argument("--no-run", action="store_true", help="eds 만 준비한다")
    ap.add_argument("--copy-to", default=None, help="빌드한 scx 를 이 경로로 복사")
    ap.add_argument("--eds", default=None, help="examples 의 eds 대신 쓸 eds (시험용)")
    args = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    which = "example" if args.example else args.which
    work = os.path.abspath(args.work or os.path.join(work0, "bgm_" + which))
    if args.no_run:
        eds, out_map = generate(work, which, base_map=args.map, ogg=args.ogg, eds_src=args.eds)
        print("eds:", eds)
        print("출력 맵:", out_map)
        return 0
    r = generate(work, which, base_map=args.map, ogg=args.ogg, run=True, eds_src=args.eds)
    if not r.ok:
        print(r.log)
    print(r.summary())
    if r.ok and args.copy_to:
        shutil.copyfile(r.out_map, args.copy_to)
        print("복사:", args.copy_to)
    if which == "ingame" and not args.ogg:
        print("참고: --ogg 를 주지 않아 D16-6(확장자만 .wav 인 Ogg)은 WAV 로 대신했습니다 — 그 항목은 건너뜁니다.")
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
