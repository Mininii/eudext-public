#!/usr/bin/env python3
"""dbg_reader.py / dbg_gui.py 자체 테스트용 가짜 게임

출처(eudext 사본): DPS_Enhance eudplib-port `tools/debugbridge/fake_game.py`
(워크트리 ScmDraft 2\\DPS_eud e135dc7, 파일 판 021b77b 2026-09-14, blob b1724f9 — 사용자 작성).
eudext 에서 더한 것: `--replay 시나리오.json` — eudext 에뮬레이터(testing/emu)가 돌린 맵의 블록 스냅숏을
프레임마다 이 프로세스 메모리에 다시 써서, 리더·자동 판정(tools/ingame_auto.py)이 실제 Win32 읽기 경로로 시험되게 한다
(아래 "재생 모드"). 원래의 자체 테스트 모드는 그대로다.

재생 모드 (eudext)
  python fake_game.py --replay scen.json
  시나리오: {"maps": [{"name", "where": "mirror"|"payload", "block_eud", "frames": [[dword …] …],
                       "mirror": [[EUD 주소, 값] …], "fps": 24, "hold": 1.0, "gap": 0.002}], "tail": 5.0}
  - mirror 맵은 EUD 0x57F0E0~0x59F0E0 를 흉내 내는 버퍼 하나에 블록을 놓는다(맵이 바뀌어도 같은 자리 — SC 처럼 덮어씀).
    그래서 리더 --peek 가 블록과 같은 오프셋으로 다른 미러 주소(게임 프레임 0x57F23C 등)를 읽는다.
  - payload 맵은 맵마다 새 버퍼(SC:R 의 페이로드처럼 미러 구역과 다른 곳). 끝난 맵의 버퍼는 멈춘 채 남는다.
  - 프레임마다 seq 시작 → 나머지 칸 → (gap 초) → seq 끝 순서로 쓴다(찢어진 읽기 시험). 서명은 첫 프레임 뒤에 쓴다.
    시나리오의 서명 칸은 0 이어야 한다(이 프로세스 메모리에 연속 서명 사본이 생기지 않게).
  - 표준 출력: "READY <pid>", 맵마다 "MAP <번호> <이름> 0x<블록 주소>" 와 "END <번호>", 끝에 "DONE".

스타 없이 리더를 확인한다. 이 프로세스의 힙에 DebugBridge.lua 와 같은 배치의 블록을 만들고
초당 24프레임으로 갱신한다. 시그니처는 맵처럼 실행 중에 dword 하나씩 써서 조립한다.
갱신 도중에 일부러 틈을 둬서 리더의 seqlock(찢어진 읽기 거르기)도 시험한다.

--diag 경로를 시험하려고 감시 슬롯에 mem/ref 종류도 넣었다. 가짜 게임에서는 블록 자신만
"1.16.1 주소가 같은 오프셋으로 읽히는 영역" 이다:
  self.frame : 블록 안의 게임 프레임 칸을 가리키는 mem 감시  -> 직접 읽기 '일치' 여야 한다
  outside    : 가짜 게임에는 없는 EUD 주소(데스값 표)          -> '일치' 가 아니어야 한다 (그 자리의 힙 배치에 따라
               '읽기 불가' 또는 '불일치')
  frame@     : frame 감시 슬롯의 EUD 주소를 담은 ref           -> (b) 블록 오프셋 '일치' 여야 한다
  far@/far2@ : SC:R 의 CreateVar 처럼 블록과 다른 곳(별도 버퍼 far_mem)에 사는 변수 흉내.
               sec 는 GameTimeSec 처럼 1초에 1씩, phase 는 SetupPhase 처럼 3 고정.
               (a)/(b) 는 안 맞고, (c) 가 sec 를 따라가 far_mem 을 찾은 뒤 phase 로 오프셋을 확정해야 한다.

--vars 경로(VARSTACK.txt 로 변수 위치 계산)를 시험하려고 가짜 VARSTACK 파일과 변수 이름표도 쓴다.
  far_mem 이 P8 변수 구역이다. 실제처럼 값 칸마다 +6 바이트에 SetDeaths(0x2D) 가 있다.
  FakeSec=sec, FakePhase=3, FakeCounter=매 프레임 +1, FakeConst=1234, 이름표에 없는 V(8)=0xDEADBEEF.
  미끼: far_mem[40] 도 sec 와 같이 움직이지만 값 칸 모양이 아니다 (--vars 는 걸러야 하고 --diag 의 (c) 는
  '다른 변수 불일치' 로 떨궈야 한다). P1 스택 변수 하나는 기준이 따로라 '다른 스택' 으로만 나와야 한다.

GUI(Ccode / CreateVoid) 경로:
  Ccode 뱅크 0 = far_mem 바이트 0x100 에 놓은 가짜 CVariable 트리거 (첫 두 액션 번호 0x2D, 칸은 +0x1C8 부터).
  자동 ptr 슬롯 sec@(FakeSec 값 칸의 EUD 주소)과 ccode.bank0(뱅크 첫 칸의 EUD 주소)으로 리더가 위치를 계산한다.
  FakeTimer(줄 0)=프레임%100, FakeFlag(줄 1)=2초마다 0/1, 이름 없는 줄 5=4242.
  void 는 블록 뒤에 붙인 dword 들 (블록과 같은 오프셋으로 읽힘): FakeVoidA=프레임*2, FakeVoidB=77.

    python fake_game.py                 # PID 와 리더 실행 명령을 출력하고 --seconds 동안 돈다

32비트 Python 으로 돌리면 32비트 대상(x86 클라이언트 흉내)이 된다.
"""
import argparse
import ctypes
import json
import os
import random
import tempfile
import time

from dbg_reader import (ACT_SETDEATHS, DEFAULT_SIGNATURE, H_BUILD, H_CAPS, H_GAME_FRAME, H_LOCAL_PLAYER,
                        H_SELF, H_SEQ_BEGIN, H_USED, H_VERSION, HDR, LAYOUT_VERSION)

WATCH_CAP, PROBE_CAP = 12, 16
FAKE_EUD = 0x596280
FAR_EUD, FAR_EUD2 = 0x19D13624, 0x19D1729C
# 가짜 VARSTACK: (변수 번호, 이름, 변수 구역 안 오프셋). far_mem[0] 이 오프셋 0x1000
VAR_BASE_OFF = 0x1000
FAKE_VARS = ((4, "FakeSec", 0x1000), (5, "FakePhase", 0x1000 + (FAR_EUD2 - FAR_EUD)),
             (6, "FakeCounter", 0x1020), (7, "FakeConst", 0x1040), (8, None, 0x1060))
DECOY = 40
BANK_TRIG = 0x100                  # far_mem 안 바이트 위치 = 가짜 Ccode 뱅크 트리거 머리
BANK_DATA = BANK_TRIG + 0x1C8      # 뱅크 첫 칸
VOIDS = 4                          # 블록 뒤에 붙이는 void dword 수
WATCHES = (("frame", "var", "V(1)"),
           ("minus_frame", "var", "V(2)"),
           ("random", "var", "V(3)"),
           ("self.frame", "mem", "0x%X" % (FAKE_EUD + 4 * H_GAME_FRAME)),
           ("outside", "mem", "0x58A364"),
           ("frame@", "ref", "V(1)"),
           ("sec", "var", "V(4)"),
           ("phase", "var", "V(5)"),
           ("far@", "ref", "V(4)"),
           ("far2@", "ref", "V(5)"),
           ("sec@", "ptr", "V(4)"),
           ("ccode.bank0", "ptr", "bank(0)"))
PROBES = ("every_frame", "every_3rd_frame", "random_burst")


def slot_of(off):
    return (off - VAR_BASE_OFF) // 4


MIRROR_LO, MIRROR_HI = 0x57F0E0, 0x59F0E0          # eudext 재생 모드: 1.16.1 미러 구역
GAME_FRAME_EUD = 0x57F23C


def replay(path):
    """eudext: 에뮬레이터 블록 스냅숏을 프레임마다 다시 쓴다 (모듈 설명 "재생 모드")."""
    with open(path, encoding="utf-8") as f:
        scen = json.load(f)
    mirror = (ctypes.c_uint32 * ((MIRROR_HI - MIRROR_LO) // 4))()
    keep = []                                        # 끝난 페이로드 버퍼를 살려 둔다 (멈춘 옛 블록)
    print(f"READY {os.getpid()}", flush=True)
    time.sleep(float(scen.get("start_delay", 0.0)))
    for n, mp in enumerate(scen["maps"]):
        frames = mp["frames"]
        total = len(frames[0])
        seq_end = HDR + (frames[0][H_CAPS] & 0xFFFF)
        if mp["where"] == "mirror":
            buf, base = mirror, (mp["block_eud"] - MIRROR_LO) // 4
            for j in range(total):                   # 맵의 시작 코드처럼 먼저 0 으로
                buf[base + j] = 0
        else:
            buf, base = (ctypes.c_uint32 * total)(), 0
            keep.append(buf)
        for eud, value in mp.get("mirror", []):
            mirror[(eud - MIRROR_LO) // 4] = value & 0xFFFFFFFF
        print(f"MAP {n} {mp.get('name', '?')} 0x{ctypes.addressof(buf) + 4 * base:X}", flush=True)
        fps = float(mp.get("fps", 24))
        gap = float(mp.get("gap", 0.002))
        for k, words in enumerate(frames):
            if any(words[:8]):
                raise SystemExit("시나리오의 서명 칸은 0 이어야 합니다")
            buf[base + H_SEQ_BEGIN] = words[H_SEQ_BEGIN] & 0xFFFFFFFF
            for j in range(8, total):
                if j not in (H_SEQ_BEGIN, seq_end):
                    buf[base + j] = words[j] & 0xFFFFFFFF
            if mp["where"] == "mirror":
                mirror[(GAME_FRAME_EUD - MIRROR_LO) // 4] = words[H_GAME_FRAME] & 0xFFFFFFFF
            if k == 0:
                for i, magic in enumerate(DEFAULT_SIGNATURE):
                    buf[base + i] = magic
            time.sleep(gap)                          # 갱신 도중의 틈
            buf[base + seq_end] = words[seq_end] & 0xFFFFFFFF
            time.sleep(max(0.0, 1 / fps - gap))
        time.sleep(float(mp.get("hold", 1.0)))       # 게임이 끝나 멈춘 블록
        print(f"END {n}", flush=True)
    print("DONE", flush=True)
    time.sleep(float(scen.get("tail", 5.0)))


def main():
    ap = argparse.ArgumentParser(description="dbg_reader.py 자체 테스트용 가짜 게임")
    ap.add_argument("--symbols", default=os.path.join(tempfile.gettempdir(), "DebugBridge_fake_symbols.json"))
    ap.add_argument("--varstack", default=os.path.join(tempfile.gettempdir(), "DebugBridge_fake_VARSTACK.txt"))
    ap.add_argument("--seconds", type=float, default=120)
    ap.add_argument("--replay", help="eudext: 에뮬레이터 스냅숏 시나리오 JSON 을 재생한다")
    args = ap.parse_args()
    if args.replay:
        return replay(args.replay)

    seq_end = HDR + WATCH_CAP
    probe_start = seq_end + 1
    total = probe_start + PROBE_CAP
    block = (ctypes.c_uint32 * (total + VOIDS))()
    void_eud = [FAKE_EUD + 4 * (total + i) for i in range(VOIDS)]
    # SC:R 의 변수 메모리 흉내: EUD 0x19D13624 = far_mem[0], 0x19D1729C = far_mem[far2]
    far2 = (FAR_EUD2 - FAR_EUD) // 4
    far_mem = (ctypes.c_uint32 * (far2 + 8))()
    for _i, _n, off in FAKE_VARS:
        far_mem[slot_of(off) + 1] = ACT_SETDEATHS << 16     # 값 칸 +6 바이트 = 액션 번호
    far_mem[far2] = 3
    far_mem[slot_of(0x1040)] = 1234
    far_mem[slot_of(0x1060)] = 0xDEADBEEF
    for act in (0x162, 0x182):                            # 뱅크 트리거 첫 두 액션의 번호 칸 (머리 +0x148 + 0x1A, +0x20)
        far_mem[(BANK_TRIG + act) // 4] = ACT_SETDEATHS << 8 * ((BANK_TRIG + act) % 4)
    ccode = BANK_DATA // 4                                # 뱅크 줄 L = far_mem[ccode + L]
    far_mem[ccode + 5] = 4242
    build = int(time.time()) % 0x7FFFFFFF

    def put(index, value):
        block[index] = value & 0xFFFFFFFF

    put(H_VERSION, LAYOUT_VERSION)
    put(H_BUILD, build)
    put(H_SELF, FAKE_EUD)
    put(H_CAPS, WATCH_CAP | PROBE_CAP << 16)
    put(H_USED, len(WATCHES) | len(PROBES) << 16)
    put(H_LOCAL_PLAYER, 0)
    put(HDR + 5, FAKE_EUD + 4 * HDR)                 # frame@ = frame 감시 슬롯의 EUD 주소
    put(HDR + 7, 3)                                  # phase 사본
    put(HDR + 8, FAR_EUD)                            # far@  = sec 가 사는 가짜 EUD 주소
    put(HDR + 9, FAR_EUD2)                           # far2@ = phase 가 사는 가짜 EUD 주소
    put(HDR + 10, FAR_EUD)                           # sec@ (자동 ptr)
    put(HDR + 11, FAR_EUD + BANK_DATA)               # ccode.bank0 (자동 ptr) = 뱅크 첫 칸의 EUD 주소
    put(total + 1, 77)                               # FakeVoidB
    for i, magic in enumerate(DEFAULT_SIGNATURE):    # 시그니처는 맨 마지막에
        put(i, magic)

    mems = [{"k": "ccode", "b": 0, "l": 0, "n": "FakeTimer", "s": "fake_game.py"},
            {"k": "ccode", "b": 0, "l": 1, "n": "FakeFlag", "s": "fake_game.py"},
            {"k": "ccode", "b": 0, "l": 5, "n": "", "s": ""},
            {"k": "void", "a": void_eud[0], "n": "FakeVoidA", "s": "fake_game.py"},
            {"k": "void", "a": void_eud[1], "n": "FakeVoidB", "s": "fake_game.py"}]
    doc = {
        "format": "eud-debug-bridge", "layout_version": LAYOUT_VERSION, "build_id": build,
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "signature": list(DEFAULT_SIGNATURE), "block_eud": FAKE_EUD, "total_dwords": total,
        "watch_start": HDR, "watch_cap": WATCH_CAP, "seq_end": seq_end,
        "probe_start": probe_start, "probe_cap": PROBE_CAP,
        "watches": [{"name": n, "slot": HDR + i, "kind": k, "src": s, "site": "fake_game.py"}
                    for i, (n, k, s) in enumerate(WATCHES)],
        "probes": [{"name": n, "index": probe_start + i, "sites": ["fake_game.py"]}
                   for i, n in enumerate(PROBES)],
        "vars": [{"i": i, "n": n, "s": "fake_game.py"} for i, n, _off in FAKE_VARS if n],
        "mems": mems,
    }
    with open(args.symbols, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    with open(args.varstack, "w", encoding="ascii") as f:
        f.write("BASE P1 200 N 1 NREC 1\nP1 9 0 200\n")
        f.write(f"BASE P8 {VAR_BASE_OFF:X} N {len(FAKE_VARS)} NREC 1\n")
        for slot, (i, _n, off) in enumerate(FAKE_VARS):
            f.write(f"P8 {i:X} {slot} {off:X}\n")

    reader = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dbg_reader.py")
    print(f"PID {os.getpid()}  블록 0x{ctypes.addressof(block):X}  변수 0x{ctypes.addressof(far_mem):X}", flush=True)
    print(f'python "{reader}" --pid {os.getpid()} --symbols "{args.symbols}" --varstack "{args.varstack}" --vars Fake',
          flush=True)

    frame = 0
    start = time.time()
    end = start + args.seconds
    while time.time() < end:
        frame += 1
        sec = 100 + int(time.time() - start)         # GameTimeSec 흉내: 1초에 1씩
        far_mem[0] = sec
        far_mem[DECOY] = sec
        far_mem[slot_of(0x1020)] = frame             # FakeCounter
        far_mem[ccode + 0] = frame % 100             # FakeTimer
        far_mem[ccode + 1] = (sec // 2) % 2          # FakeFlag
        put(total + 0, frame * 2)                    # FakeVoidA
        put(H_SEQ_BEGIN, block[H_SEQ_BEGIN] + 1)
        put(H_GAME_FRAME, frame)
        put(HDR + 0, frame)
        put(HDR + 1, -frame)
        put(HDR + 2, random.randrange(1 << 32))
        put(HDR + 3, block[H_GAME_FRAME])            # self.frame: 게임 프레임 칸의 사본
        put(HDR + 4, 1)                              # outside: 맵이라면 데스값을 복사했을 자리
        put(HDR + 6, sec)                            # sec 사본
        time.sleep(0.003)            # 갱신 도중의 틈: 이때 읽으면 seq 시작 != seq 끝
        put(seq_end, block[seq_end] + 1)
        put(probe_start + 0, block[probe_start + 0] + 1)
        if frame % 3 == 0:
            put(probe_start + 1, block[probe_start + 1] + 1)
        put(probe_start + 2, block[probe_start + 2] + random.choice((0, 0, 0, 5)))
        time.sleep(1 / 24)


if __name__ == "__main__":
    main()
