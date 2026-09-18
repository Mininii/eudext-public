#!/usr/bin/env python3
"""euddraft 0.9 플러그인 원본 → euddraft 0.11(eudplib 0.81) 사본을 만든다. 결과는 hybrid/plugins/ (커밋한다).

    python hybrid/make_plugins.py --orig <원본 폴더>            # 만들기 (원본 md5 가 다르면 멈춤)
    python hybrid/make_plugins.py --orig <원본 폴더> --check    # 사본이 지금 규칙으로 만든 것과 같은지만 본다

원본 폴더 = euddraft 0.9.10.11 의 plugins 폴더(예: C:\\euddraft0.9.2.0\\plugins). `--orig` 가 없으면 환경 변수
EUDEXT_PLUGINS09, 그다음 작업 저장소 자리(reference/euddraft-0.9.10.11-plugins/)를 본다. 고치는 규칙은 하이브리드 이식판
(MSF_Memory_2·MSF_Memory 의 eud/tools/make_plugins.py)과 같다. 그 판으로 만든 사본이 인게임에서 돌았다.

사본과 고친 곳
  STRCtrig_v55_eud081.py  `from eudx import *` 한 줄을 주석으로. eudx.py 는 0.81 에 없는
                          `EncodePlayer(…, issueError=True)` 인자를 써서 불러오기부터 실패한다. 이 플러그인이 쓰는
                          DeathsX·SetDeathsX·f_maskread_epd 는 0.81 에 있다.
  CPLP_eud081.py          같은 한 줄.
  NSQC_eud081.py          (1) 키·마우스 눌림 기억 칸 (MapSource SNQC 1.3 과 같은 수정).
                          0.9 판은 `KeyArray = EUDArray(8)` 에 `KeyArray + 키 // 8` 로 주소를 만든다. eudplib 0.76 은
                          EUDArray 값이 주소라 조건·액션이 EPD 로 내림하여 (키 // 32) 번째 dword 의 (키 % 32) 번째 비트 =
                          256비트 비트필드가 됐다. 0.81 은 EUDArray 값이 EPD 라 `+ 키 // 8` 이 (키 // 8) 번째 dword 가 되어
                          키 0x40 이상(O·P·F12 …)에서 8칸 배열 밖(다른 트리거·변수)에 쓴다 → 로컬 키 상태로 공유 메모리를
                          덮어 디싱크·오동작. 고침: KeyArray = Db(32), MouseArray = Db(4), 칸 = KeyArray + 4*(키//32)
                          (두 판에서 같은 비트필드).
                          (2) Respawn 의 QC 로케이션 임시 저장 `SetMemory(LOC_TEMP + 4k, …)` (LOC_TEMP = EUDArray(5)):
                          0.81 에서 원소 4k 에 써서 원소 8·12·16 이 배열 밖(다른 페이로드)을 덮고, 복구 때 로케이션 좌표가
                          틀린 값이 된다 → `SetMemoryEPD(LOC_TEMP._epd + k, …)`. 빌드 로그의 "EPD on EPD value" 경고 5건이 이 자리.
                          나머지(배열 결과 줄의 isinstance 등)는 고치지 않았다 — 그 기능은 0.81 에서 쓰지 않는다(hybrid/README.md).

사본을 만들지 않은 것
  STRCtrig Assembler v5.5 Stack.py (적층 포크): 같은 `from eudx import *` 줄이 있지만 0.81 에서 돌려 본 적이 없다.
  APMCounter.py: 고칠 것이 없어 원본을 그대로 쓴다(MSF_Memory_2 하이브리드에서 확인).
  unlimiter.py·dataDumper.py·noAirCollision.py 등 euddraft 0.11 번들에 있는 것은 번들 판을 쓴다.

md5 는 줄 끝을 LF 로 맞춘 뒤 잰다(git 이 체크아웃 때 줄 끝을 바꿀 수 있다). 사본은 LF 로 쓴다.
"""
import argparse
import hashlib
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ORIG_DEFAULT = os.path.join(ROOT, "reference", "euddraft-0.9.10.11-plugins")
OUT = os.path.join(HERE, "plugins")


def to_lf(data):
    return data.replace(b"\r\n", b"\n")


def md5_lf(data):
    return hashlib.md5(to_lf(data)).hexdigest()


EUDX_OLD = "from eudx import *\n"
EUDX_NEW = "# from eudx import *  # eudplib 0.81: eudx.py 는 0.76 전용 인자를 써서 실패. 쓰는 함수는 eudplib 에 있다 (eudext hybrid)\n"

NSQC_PATCHES = [
    ("KeyArray, KeyOffset = EUDArray(8), set()\nMouseArray, MouseOffset = EUDArray(1), set()\n",
     "# [eudext hybrid, eudplib 0.81] 눌림 기억 칸을 바이트 배열로 (MapSource SNQC 1.3 과 같은 수정).\n"
     "# 0.9 판의 EUDArray(8) + 키 // 8 은 0.81 에서 (키 // 8) 번째 dword = 배열 밖이 된다. 0.76 과 같은 비트필드:\n"
     "# 키 k 의 칸 = KeyArray 의 (k // 32) 번째 dword, (k % 32) 번째 비트.\n"
     "KeyArray, KeyOffset = Db(32), set()\n"
     "MouseArray, MouseOffset = Db(4), set()\n"
     "\n"
     "\n"
     "def _keybit(offset):\n"
     "    return KeyArray + 4 * (offset // 32), 2 ** (offset % 32)\n"),
    # KeyUpdate
    ("    for offset in KeyOffset:\n"
     "        r = offset % 4\n"
     "        m = 256 ** r\n"
     "        n = 2 ** (offset % 32)\n"
     "        RawTrigger(\n"
     "            conditions=[  # KeyDown\n"
     "                MemoryX(0x596A18 + offset - r, Exactly, m, m),\n"
     "                MemoryX(KeyArray + offset // 8, Exactly, 0, n),\n"
     "            ],\n"
     "            actions=SetMemoryX(KeyArray + offset // 8, SetTo, n, n),\n"
     "        )\n"
     "        RawTrigger(\n"
     "            conditions=[  # KeyUp\n"
     "                MemoryX(0x596A18 + offset - r, Exactly, 0, m),\n"
     "                MemoryX(KeyArray + offset // 8, Exactly, n, n),\n"
     "            ],\n"
     "            actions=SetMemoryX(KeyArray + offset // 8, SetTo, 0, n),\n"
     "        )\n",
     "    for offset in sorted(KeyOffset):\n"
     "        r = offset % 4\n"
     "        m = 256 ** r\n"
     "        ka, n = _keybit(offset)\n"
     "        RawTrigger(\n"
     "            conditions=[  # KeyDown\n"
     "                MemoryX(0x596A18 + offset - r, Exactly, m, m),\n"
     "                MemoryX(ka, Exactly, 0, n),\n"
     "            ],\n"
     "            actions=SetMemoryX(ka, SetTo, n, n),\n"
     "        )\n"
     "        RawTrigger(\n"
     "            conditions=[  # KeyUp\n"
     "                MemoryX(0x596A18 + offset - r, Exactly, 0, m),\n"
     "                MemoryX(ka, Exactly, n, n),\n"
     "            ],\n"
     "            actions=SetMemoryX(ka, SetTo, 0, n),\n"
     "        )\n"),
    # KeyDown
    ("        KeyOffset.add(offset)\n"
     "        r = offset % 4\n"
     "        m = 256 ** r\n"
     "        n = 2 ** (offset % 32)\n"
     "        return [  # KeyDown\n"
     "            MemoryX(0x596A18 + offset - r, Exactly, m, m),\n"
     "            MemoryX(KeyArray + offset // 8, Exactly, 0, n),\n"
     "        ]\n",
     "        KeyOffset.add(offset)\n"
     "        r = offset % 4\n"
     "        m = 256 ** r\n"
     "        ka, n = _keybit(offset)\n"
     "        return [  # KeyDown\n"
     "            MemoryX(0x596A18 + offset - r, Exactly, m, m),\n"
     "            MemoryX(ka, Exactly, 0, n),\n"
     "        ]\n"),
    # KeyUp
    ("        KeyOffset.add(offset)\n"
     "        r = offset % 4\n"
     "        m = 256 ** r\n"
     "        n = 2 ** (offset % 32)\n"
     "        return [  # KeyUp\n"
     "            MemoryX(0x596A18 + offset - r, Exactly, 0, m),\n"
     "            MemoryX(KeyArray + offset // 8, Exactly, n, n),\n"
     "        ]\n",
     "        KeyOffset.add(offset)\n"
     "        r = offset % 4\n"
     "        m = 256 ** r\n"
     "        ka, n = _keybit(offset)\n"
     "        return [  # KeyUp\n"
     "            MemoryX(0x596A18 + offset - r, Exactly, 0, m),\n"
     "            MemoryX(ka, Exactly, n, n),\n"
     "        ]\n"),
    # Respawn: QC 로케이션 임시 저장 (LOC_TEMP = EUDArray(5)). 0.81 에서 `LOC_TEMP + 4k` 는 EPD + 4k 라
    # 원소 0·4·8·12·16 에 쓴다 (8·12·16 은 배열 밖 = 다른 페이로드). 빌드 로그의 "EPD on EPD value" 경고 5건이 이 자리.
    # 복구(`LOC_TEMP[k]`)는 0.81 에서도 원소 k 라 저장만 원소 k 의 EPD 로 고친다 (_epd 는 두 판 모두 있다 — SNQC 1.3 _arr_epd).
    ("            SetMemory(LOC_TEMP, SetTo, f_dwread_epd(LocEPD)),\n"
     "            SetMemory(LOC_TEMP + 4, SetTo, f_dwread_epd(LocEPD + 1)),\n"
     "            SetMemory(LOC_TEMP + 8, SetTo, f_dwread_epd(LocEPD + 2)),\n"
     "            SetMemory(LOC_TEMP + 12, SetTo, f_dwread_epd(LocEPD + 3)),\n"
     "            SetMemory(LOC_TEMP + 16, SetTo, f_dwread_epd(LocEPD + 4)),\n",
     "            # [eudext hybrid, eudplib 0.81] LOC_TEMP + 4k 는 0.81 에서 원소 4k (배열 밖) -> 원소 k 의 EPD 로 쓴다\n"
     "            SetMemoryEPD(LOC_TEMP._epd, SetTo, f_dwread_epd(LocEPD)),\n"
     "            SetMemoryEPD(LOC_TEMP._epd + 1, SetTo, f_dwread_epd(LocEPD + 1)),\n"
     "            SetMemoryEPD(LOC_TEMP._epd + 2, SetTo, f_dwread_epd(LocEPD + 2)),\n"
     "            SetMemoryEPD(LOC_TEMP._epd + 3, SetTo, f_dwread_epd(LocEPD + 3)),\n"
     "            SetMemoryEPD(LOC_TEMP._epd + 4, SetTo, f_dwread_epd(LocEPD + 4)),\n"),
]

COPIES = {
    # 사본 이름: (원본, 원본 md5 (LF 기준), [(찾을 글, 바꿀 글)])
    "STRCtrig_v55_eud081.py": ("STRCtrig Assembler v5.5.py", "2ba1ef42ab42a587d40803df85f3e816", [(EUDX_OLD, EUDX_NEW)]),
    "CPLP_eud081.py": ("CPLP.py", "01ee95cbed7b420effd2e13184887c7e", [(EUDX_OLD, EUDX_NEW)]),
    "NSQC_eud081.py": ("NSQC.py", "35ce5e53173aca18e20593f9f9c0704e", NSQC_PATCHES),
}


def find_orig(arg):
    for d in (arg, os.environ.get("EUDEXT_PLUGINS09"), ORIG_DEFAULT):
        if d and os.path.isdir(d):
            return d
    raise SystemExit("원본 0.9 플러그인 폴더를 찾지 못했다 — --orig <euddraft 0.9.10.11 의 plugins 폴더> 로 알려 줄 것")


def render(name, orig):
    src_name, want_md5, patches = COPIES[name]
    src = os.path.join(orig, src_name)
    raw = open(src, "rb").read()
    got_md5 = md5_lf(raw)
    if got_md5 != want_md5:
        raise SystemExit("원본 %s 의 md5 가 %s (사본을 만들 때 %s) — 원본이 바뀌었다. 고칠 곳을 다시 확인할 것" % (src, got_md5, want_md5))
    text = to_lf(raw).decode("utf-8")
    for old, new in patches:
        n = text.count(old)
        if n != 1:
            raise SystemExit("%s: 고칠 글이 %d번 나온다 (1번이어야 한다): %r" % (name, n, old[:80]))
        text = text.replace(old, new)
    head = ("# [eudext hybrid] euddraft 0.11 / eudplib 0.81 사본 — 원본 %s (md5 %s, 줄 끝 LF 기준).\n"
            "# hybrid/make_plugins.py 가 만든다. 손으로 고치지 말 것 (규칙은 그 파일의 머리 주석).\n"
            % (src_name, want_md5))
    lines = text.split("\n", 2)
    # 원본 첫 줄이 shebang/인코딩이면 그 뒤에 머리 주석을 둔다
    if lines[0].startswith("#!") and len(lines) > 2 and "coding" in lines[1]:
        text = lines[0] + "\n" + lines[1] + "\n" + head + lines[2]
    elif lines[0].startswith("#!"):
        text = lines[0] + "\n" + head + "\n".join(lines[1:])
    else:
        text = head + text
    return text.encode("utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--orig", default=None, help="euddraft 0.9.10.11 의 plugins 폴더")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    orig = find_orig(args.orig)
    os.makedirs(OUT, exist_ok=True)
    bad = 0
    for name in COPIES:
        data = render(name, orig)
        dst = os.path.join(OUT, name)
        if args.check:
            same = os.path.isfile(dst) and to_lf(open(dst, "rb").read()) == data
            print("%-26s %s" % (name, "같음" if same else "다름/없음"))
            bad += not same
        else:
            with open(dst, "wb") as f:
                f.write(data)
            print("%-26s %d B, md5 %s" % (name, len(data), hashlib.md5(data).hexdigest()))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
