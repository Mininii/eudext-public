#!/usr/bin/env python3
"""EUD 디버그 브리지 리더

출처(eudext 사본): DPS_Enhance eudplib-port `tools/debugbridge/dbg_reader.py`
(워크트리 ScmDraft 2\\DPS_eud e135dc7, 파일 판 021b77b 2026-09-14, blob 8237e4e — 사용자 작성).
eudext 에서 바꾼 것(최소, 원본 파일은 고치지 않음):
  - `eudext.dbg` 블록 읽기: 심볼의 `eudext` 확장(맵 이름·빌드 태그·판정·표식·글 스냅숏·64비트)을 화면 끝에 풀어 보인다.
  - `--symbols` 에 폴더를 줄 수 있다(찾은 블록의 빌드 ID 와 같은 JSON 을 고른다). 주지 않으면 EUDEXT_DBG_SYMBOLS →
    EUDEXT_DBG_DIR → EUDEXT_WORK/dbg → 저장소 work/dbg → <임시 폴더>/eudext_work/dbg → C:\\Temp\\DebugBridge_symbols.json
    순으로 찾는다.
  - Windows 가 아니어도 import 는 된다(파서·화면만 시험용으로 쓴다 — 게임 읽기는 Windows 전용).
  - `--judge 명세…`: 자동 판정(`eudext/tools/ingame_auto.py`)으로 넘긴다.
  - `--record 파일 [--record-keys] [--record-watch 이름…] [--record-seconds N]`: 시간순 기록(seq·프레임/초·멈춤·단계 사건,
    선택한 값 변화, 로컬 키 표 0x596A18 변화 — 키 표는 --diag 에서 그 구역이 직접 읽히는지 먼저 본다). 선택 표(0x6284B8)·
    채팅 상태(0x68C144) 같은 미러 밖 값은 맵이 dbg.watch 로 복사한 이름을 --record-watch 로 준다.
  - (설계만, 다음 작업) eudext 가 없는 판(UE_RE ①②, 14 scrdb)을 위해 SCR_DB 표지(SCRDB_MAGIC)·SNQC 디버그 칸
    (0x592100, `MSF_UE_RE\\tools\\snqc_probe.py` 의 DBG_MAGIC)으로 오프셋을 잡는 찾기. DESIGN 5.5 참고.

맵의 DebugBridge.lua(또는 eudext.dbg)가 게임 중에 쓰는 디버그 블록을 StarCraft.exe 메모리에서
찾아 읽는다. 찾는 방법은 SCA 런처와 같다.

  찾기    VirtualQueryEx 로 쓰기 가능한 메모리를 훑어 dword 8개짜리 시그니처를 찾는다.
  읽기    블록 시작 주소 기준 오프셋만 쓴다. SC:R 이 1.16.1 주소를 어디에 두는지 몰라도 된다.
  일관성  블록 앞뒤의 seq 가 같을 때만 스냅샷을 채택한다 (seqlock).

사용
  python dbg_reader.py              실시간 보기 (Ctrl+C 로 종료)
  python dbg_reader.py --once       한 번만 출력
  python dbg_reader.py --vars "Setup*" Gun
                                    변수 모드: CreateVar 변수를 이름으로 골라 실시간으로 본다 (VarStack 빌드 전용).
                                    * ? 가 있으면 이름 전체와, 없으면 이름의 일부와 비교한다. 대소문자는 가리지 않는다.
                                    V(98981) 처럼 번호로도 고른다. 패턴 없이 --vars 만 주면 전체 목록을 한 번 출력.
  python dbg_reader.py --diag       스캔 결과 + "블록 밖 1.16.1 주소 / 변수 메모리도 읽히나" 진단
  python dbg_reader.py --peek 0x58A364:4 0x57F23C
                                    EUD 주소를 블록과 같은 오프셋으로 직접 읽는다 (주소[:dword 수]).
                                    --diag 가 "직접 읽히는 영역" 이라고 한 범위에서만 믿을 수 있다.
  python dbg_reader.py --peek 0x19D13624 --raw
                                    오프셋 없이 실제 주소 그대로 읽는다
  python dbg_reader.py --pid N      특정 프로세스 (fake_game.py 로 자체 테스트할 때)

32비트 StarCraft(x86 클라이언트: "x86\\StarCraft.exe -launch")도 읽는다. 붙은 대상의 비트 수는 화면 첫 줄에 나온다.
64비트 SC:R 은 64비트 Python 으로만 읽힌다 (32비트 Python 은 4GB 위 주소에 못 닿는다).

심볼 파일(--symbols, 파일 또는 폴더)은 맵을 컴파일할 때 DebugBridge.lua(C:\\Temp\\DebugBridge_symbols.json)나
eudext.dbg(작업 폴더의 dbg\\DebugBridge_<맵>_<빌드>.json)가 쓴다. 없어도 동작하지만 이름 대신 슬롯 번호가 보인다.

변수 모드의 원리
  VarStack tepc 가 컴파일 때 쓰는 VARSTACK.txt(--varstack)에 변수마다 오프셋이 있고, 게임 중 실제 주소는
  "기준 + 오프셋" 이다. 기준은 판마다 달라서, DBG_Watch 로 블록에 복사되는 변수(theSeed 는 1초에 1씩 느는
  GameTimeSec)를 치트엔진의 '다음 스캔' 식으로 따라가 판마다 한 번 찾는다 (10~20초). 찾은 기준은
  임시 폴더에 저장해 두고 같은 판이면 다시 쓴다. 변수 이름은 심볼 파일의 이름표에서 온다.

읽기만 하고 게임 메모리에 쓰지 않는다. 그래도 외부 프로세스 메모리 접근이므로
배틀넷 멀티 게임이 아니라 싱글/로컬 테스트에서만 쓸 것.
"""
from __future__ import annotations

import argparse
import ctypes
import fnmatch
import glob
import json
import os
import shutil
import struct
import sys
import tempfile
import time

WIN32 = sys.platform == "win32"    # eudext: 다른 OS 에서도 import 는 된다 (main 이 막는다)
try:
    import ctypes.wintypes as wt
except (ImportError, ValueError):  # eudext: 옛 파이썬의 비 Windows 에서는 형 이름만 흉내
    import types as _types
    wt = _types.SimpleNamespace(DWORD=ctypes.c_uint32, WORD=ctypes.c_uint16, BOOL=ctypes.c_long,
                                HANDLE=ctypes.c_void_p)

DEFAULT_SIGNATURE = (0x44445545, 0x52424742, 0x9E3779B9, 0x7F4A7C15,
                     0xF39CC060, 0x5CEDC834, 0xB5297A4D, 0x1B873593)
LEGACY_SYMBOLS = r"C:\Temp\DebugBridge_symbols.json"
DEFAULT_SYMBOLS = None             # eudext: 한 경로 대신 symbol_candidates() 를 차례로 찾는다
REPO_WORK = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                         "work")
DEFAULT_VARSTACK = r"C:\euddraft0.9.2.0\Ctemp\VARSTACK.txt"
VARBASE_CACHE = os.path.join(tempfile.gettempdir(), "DebugBridge_varbase.json")
LAYOUT_VERSION = 1

# 헤더 dword 인덱스 - DebugBridge.lua 의 DBG_I 와 같아야 한다
H_VERSION, H_BUILD, H_SELF, H_CAPS, H_SEQ_BEGIN, H_GAME_FRAME, H_LOCAL_PLAYER, H_USED = range(8, 16)
HDR = 24
# 게임 시작 때 맵이 한 번 복사해 두는 정적 값: (이름, EUD 주소, 블록 인덱스, dword 수)
STATIC_COPIES = (("local_player", 0x512684, 14, 1),
                 ("player_info[0]", 0x57EEE8, 16, 4),
                 ("map_path", 0x57FD3C, 20, 4))
GAME_FRAME_EUD = 0x57F23C
# CtrigAsm 변수의 값 칸은 변수 트리거 첫 액션(SetDeaths)의 값 필드다. 값 칸 +6 바이트가 액션 번호
# (theSeed 인게임에서 P8 변수 1107개 전부 확인)
ACT_SETDEATHS = 0x2D

# --- Win32 ------------------------------------------------------------------

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
# 쓰기는 Process(pid, write=True) 로 명시할 때만 딸려온다. 디버그 브리지는 읽기 전용이 원칙이고
# (배틀넷 멀티에서 쓰면 안 된다), 쓰기가 필요한 쪽은 세이브를 되돌려 넣는 SCR_DB 런처뿐이다.
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
TH32CS_SNAPPROCESS = 0x02
TH32CS_SNAPMODULE = 0x08
TH32CS_SNAPMODULE32 = 0x10
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100
WRITABLE = 0x04 | 0x08 | 0x40 | 0x80   # READWRITE, WRITECOPY, EXECUTE_READWRITE, EXECUTE_WRITECOPY
READABLE = 0x02 | 0x20 | WRITABLE      # + READONLY, EXECUTE_READ
MEM_TYPES = {0x20000: "PRIVATE", 0x40000: "MAPPED", 0x1000000: "IMAGE"}
USER_SPACE_END = 0x7FFFFFFF0000        # 64비트 대상의 사용자 주소 끝
USER_SPACE_END_32 = 0x100000000        # 32비트 대상(WOW64 포함)의 맵 메모리는 4GB 안에만 있다
READER_64 = struct.calcsize("P") == 8

k32 = ctypes.WinDLL("kernel32", use_last_error=True) if WIN32 else None


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    # VirtualQueryEx 는 대상이 아니라 리더 자신의 비트 수 레이아웃으로 채운다. PartitionId 는 64비트에만 있다.
    # 주소는 c_size_t 로 받는다 (c_void_p 는 0 을 None 으로 돌려준다)
    _fields_ = ([("BaseAddress", ctypes.c_size_t),
                 ("AllocationBase", ctypes.c_size_t),
                 ("AllocationProtect", wt.DWORD)]
                + ([("PartitionId", wt.WORD)] if READER_64 else [])
                + [("RegionSize", ctypes.c_size_t),
                   ("State", wt.DWORD),
                   ("Protect", wt.DWORD),
                   ("Type", wt.DWORD)])


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("th32ModuleID", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("GlblcntUsage", wt.DWORD), ("ProccntUsage", wt.DWORD),
                ("modBaseAddr", ctypes.c_void_p), ("modBaseSize", wt.DWORD),
                ("hModule", ctypes.c_void_p), ("szModule", ctypes.c_wchar * 256),
                ("szExePath", ctypes.c_wchar * 260)]


if WIN32:
    k32.OpenProcess.argtypes = (wt.DWORD, wt.BOOL, wt.DWORD)
    k32.OpenProcess.restype = wt.HANDLE
    k32.CloseHandle.argtypes = (wt.HANDLE,)
    k32.VirtualQueryEx.argtypes = (wt.HANDLE, ctypes.c_void_p,
                                   ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t)
    k32.VirtualQueryEx.restype = ctypes.c_size_t
    k32.ReadProcessMemory.argtypes = (wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))
    k32.ReadProcessMemory.restype = wt.BOOL
    k32.WriteProcessMemory.argtypes = (wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))
    k32.WriteProcessMemory.restype = wt.BOOL
    k32.CreateToolhelp32Snapshot.argtypes = (wt.DWORD, wt.DWORD)
    k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
    k32.IsWow64Process.argtypes = (wt.HANDLE, ctypes.POINTER(wt.BOOL))
    k32.IsWow64Process.restype = wt.BOOL
    k32.GetCurrentProcess.restype = wt.HANDLE
    for _name, _entry in (("Process32FirstW", PROCESSENTRY32W), ("Process32NextW", PROCESSENTRY32W),
                          ("Module32FirstW", MODULEENTRY32W), ("Module32NextW", MODULEENTRY32W)):
        getattr(k32, _name).argtypes = (wt.HANDLE, ctypes.POINTER(_entry))
        getattr(k32, _name).restype = wt.BOOL
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


def is_wow64(handle):
    """64비트 윈도우에서 도는 32비트 프로세스인가"""
    flag = wt.BOOL(0)
    return bool(k32.IsWow64Process(handle, ctypes.byref(flag)) and flag.value)


READER_BITS = 64 if READER_64 else 32
OS_64 = READER_64 or (WIN32 and is_wow64(k32.GetCurrentProcess()))  # 32비트 리더는 자기가 WOW64 인지로 윈도우 비트 수를 안다


def _toolhelp(flags, pid, entry_type, first, next_):
    snap = k32.CreateToolhelp32Snapshot(flags, pid)
    if snap in (None, INVALID_HANDLE_VALUE):
        return
    try:
        entry = entry_type()
        entry.dwSize = ctypes.sizeof(entry)
        ok = first(snap, ctypes.byref(entry))
        while ok:
            yield entry
            ok = next_(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)


def find_pids(name):
    name = name.lower()
    return [e.th32ProcessID
            for e in _toolhelp(TH32CS_SNAPPROCESS, 0, PROCESSENTRY32W, k32.Process32FirstW, k32.Process32NextW)
            if e.szExeFile.lower() == name]


class Process:
    def __init__(self, pid, write=False):
        self.pid = pid
        self.writable = write
        access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        if write:
            access |= PROCESS_VM_WRITE | PROCESS_VM_OPERATION
        self.handle = k32.OpenProcess(access, False, pid)
        if not self.handle:
            err = ctypes.get_last_error()
            if err == 5:
                raise PermissionError(f"PID {pid} 를 열 수 없습니다 (접근 거부). 관리자 권한 터미널에서 다시 실행해 보세요.")
            raise OSError(f"PID {pid} 를 열 수 없습니다 (오류 {err}).")
        # 32비트 대상 = 32비트 윈도우의 모든 프로세스, 또는 64비트 윈도우의 WOW64 프로세스 (x86 클라이언트)
        self.bits = 32 if not OS_64 or is_wow64(self.handle) else 64
        if self.bits > READER_BITS:
            self.close()
            raise OSError(f"PID {pid} 는 64비트 프로세스라 32비트 Python 으로는 읽을 수 없습니다. 64비트 Python 으로 실행하세요.")
        self.space_end = USER_SPACE_END if self.bits == 64 else USER_SPACE_END_32

    def close(self):
        if self.handle:
            k32.CloseHandle(self.handle)
            self.handle = None

    def read(self, addr, size):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t(0)
        k32.ReadProcessMemory(self.handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
        return buf.raw[:got.value]

    def write(self, addr, data):
        """실제로 쓴 바이트 수. Process(pid, write=True) 로 연 핸들에서만 된다."""
        if not self.writable:
            raise PermissionError("읽기 전용으로 연 프로세스입니다 (Process(pid, write=True) 로 열 것).")
        buf = ctypes.create_string_buffer(bytes(data), len(data))
        put = ctypes.c_size_t(0)
        k32.WriteProcessMemory(self.handle, ctypes.c_void_p(addr), buf, len(data), ctypes.byref(put))
        return put.value

    def write_dwords(self, addr, values):
        """연속된 dword 들을 한 번에 쓴다. 다 못 쓰면 False."""
        raw = struct.pack(f"<{len(values)}I", *[v & 0xFFFFFFFF for v in values])
        return self.write(addr, raw) == len(raw)

    def dwords(self, addr, count):
        raw = self.read(addr, count * 4)
        if len(raw) < count * 4:
            return None
        return struct.unpack(f"<{count}I", raw)

    def read_many(self, addrs, span=0x10000):
        """{주소: dword 또는 None}. 가까운 주소끼리 묶어 한 번에 읽는다 (후보 수십만 개를 빠르게 다시 읽을 때).
        묶음이 메모리 영역 사이의 빈 곳에 걸쳐 한 번에 안 읽히면 그 묶음만 하나씩 다시 읽는다."""
        out = {}
        addrs = sorted(set(addrs))
        i = 0
        while i < len(addrs):
            start = addrs[i]
            j = i
            while j + 1 < len(addrs) and addrs[j + 1] - start < span:
                j += 1
            size = addrs[j] - start + 4
            data = self.read(start, size)
            if len(data) < size:
                for a in addrs[i:j + 1]:
                    got = self.dwords(a, 1)
                    out[a] = got[0] if got else None
            else:
                for a in addrs[i:j + 1]:
                    out[a] = struct.unpack_from("<I", data, a - start)[0]
            i = j + 1
        return out

    def query(self, addr):
        mbi = MEMORY_BASIC_INFORMATION()
        if not k32.VirtualQueryEx(self.handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            return None
        return mbi

    def region_of(self, addr):
        """addr 가 든 커밋 영역의 (시작, 끝). VirtualQueryEx 는 addr 가 든 페이지부터 알려주므로
        할당 시작점부터 다시 걸어서 영역의 진짜 시작을 찾는다."""
        mbi = self.query(addr)
        if mbi is None or mbi.State != MEM_COMMIT:
            return None
        cur = mbi.AllocationBase
        while True:
            q = self.query(cur)
            if q is None:
                return None
            start, end = q.BaseAddress, q.BaseAddress + q.RegionSize
            if start <= addr < end:
                return (start, end) if q.State == MEM_COMMIT else None
            if end <= cur:
                return None
            cur = end

    def regions(self, mask):
        addr = 0
        while addr < self.space_end:
            mbi = self.query(addr)
            if mbi is None:
                break
            base, size = mbi.BaseAddress, mbi.RegionSize
            if (mbi.State == MEM_COMMIT and (mbi.Protect & mask)
                    and not (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS))):
                yield base, size
            if base + size <= addr:
                break
            addr = base + size

    def scan(self, pattern, mask, chunk=32 << 20):
        """pattern 이 4바이트 정렬 위치에 나타나는 주소를 모두 돌려준다."""
        hits = []
        overlap = len(pattern) - 1
        for base, size in self.regions(mask):
            off = 0
            while off < size:
                n = min(chunk, size - off)
                data = self.read(base + off, min(n + overlap, size - off))
                i = data.find(pattern)
                while 0 <= i < n:
                    if (base + off + i) % 4 == 0:
                        hits.append(base + off + i)
                    i = data.find(pattern, i + 1)
                off += n
        return hits

    def modules(self):
        return [(e.szModule, e.modBaseAddr or 0, e.modBaseSize)
                for e in _toolhelp(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, self.pid, MODULEENTRY32W,
                                   k32.Module32FirstW, k32.Module32NextW)]


# --- 블록 -------------------------------------------------------------------

class Layout:
    def __init__(self, caps, used):
        self.watch_cap = caps & 0xFFFF
        self.probe_cap = caps >> 16
        self.watch_start = HDR
        self.seq_end = HDR + self.watch_cap
        self.probe_start = self.seq_end + 1
        self.total = self.probe_start + self.probe_cap
        self.watch_used = min(used & 0xFFFF, self.watch_cap)
        self.probe_used = min(used >> 16, self.probe_cap)


class Block:
    def __init__(self, proc, addr, header):
        self.proc = proc
        self.addr = addr
        self.build = header[H_BUILD]
        self.eud = header[H_SELF]
        self.delta = addr - header[H_SELF]      # 실제 주소 = EUD 주소 + delta (블록 기준)
        self.layout = Layout(header[H_CAPS], header[H_USED])

    def seq(self):
        d = self.proc.dwords(self.addr + 4 * H_SEQ_BEGIN, 1)
        return None if d is None else d[0]

    def snapshot(self, tries=20):
        """(dword 튜플, 일관성 여부). seq 시작 == seq 끝 인 읽기가 나올 때까지 몇 번 다시 읽는다."""
        d = None
        for _ in range(tries):
            d = self.proc.dwords(self.addr, self.layout.total)
            if d is None:
                return None, False
            if d[H_SEQ_BEGIN] == d[self.layout.seq_end]:
                return d, True
            time.sleep(0.0005)
        return d, False

    def direct(self, eud, count=1):
        """EUD 주소를 블록과 같은 오프셋으로 직접 읽는다. 그 자리에 메모리가 없으면 None."""
        return self.proc.dwords(eud + self.delta, count)


def read_symbol_doc(path):
    """심볼 JSON 한 개 (UTF-8 또는 CP949). 못 읽으면 {}."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return {}
    for encoding in ("utf-8", "cp949"):
        try:
            doc = json.loads(raw.decode(encoding))
            return doc if isinstance(doc, dict) else {}
        except (UnicodeDecodeError, ValueError):
            continue
    return {}


class Symbols:
    def __init__(self, path, doc=None):
        self.path = path
        self.doc = {}
        if doc is not None:                     # eudext: 폴더에서 고른 문서
            self.doc = doc
        elif path and os.path.isfile(path):
            self.doc = read_symbol_doc(path)
        self.loaded = bool(self.doc)
        self.mtime = os.path.getmtime(path) if self.loaded and path and os.path.isfile(path) else None
        # eudext: 확장 필드 (eudext.dbg 가 쓴 심볼에만 있다)
        ext = self.doc.get("eudext")
        self.ext = ext if isinstance(ext, dict) and ext.get("format") == "eudext-dbg" else None
        self.build_id = self.doc.get("build_id")
        self.signature = tuple(self.doc.get("signature") or DEFAULT_SIGNATURE)
        self.watches = {w["slot"]: w for w in self.doc.get("watches", [])}
        self.probes = {p["index"]: p for p in self.doc.get("probes", [])}
        self.has_vars = "vars" in self.doc
        self.vars = {v["i"]: v for v in self.doc.get("vars", []) if isinstance(v, dict) and "i" in v}
        # Ccode {k:"ccode", b:뱅크, l:줄} / CreateVoid {k:"void", a:EUD 주소} - 이름 n, 만든 자리 s
        self.mems = [m for m in self.doc.get("mems", []) if isinstance(m, dict) and m.get("k") in ("ccode", "void")]


# --- eudext: 심볼 찾기 (파일·폴더·기본 후보) ----------------------------------------

def symbol_candidates(spec=None):
    """심볼을 찾을 곳(파일 또는 폴더) 목록. spec 을 주면 그것만."""
    if spec:
        return [spec]
    out = []
    for key in ("EUDEXT_DBG_SYMBOLS", "EUDEXT_DBG_DIR"):
        if os.environ.get(key):
            out.append(os.environ[key])
    if os.environ.get("EUDEXT_WORK"):
        out.append(os.path.join(os.environ["EUDEXT_WORK"], "dbg"))
    out.append(os.path.join(REPO_WORK, "dbg"))
    out.append(os.path.join(tempfile.gettempdir(), "eudext_work", "dbg"))
    out.append(LEGACY_SYMBOLS)
    return out


def symbol_files(spec=None):
    """후보에서 심볼 JSON 파일들 (새것 먼저)."""
    files = []
    for cand in symbol_candidates(spec):
        if os.path.isdir(cand):
            files.extend(glob.glob(os.path.join(cand, "*.json")))
        elif os.path.isfile(cand):
            files.append(cand)
    seen, out = set(), []
    for f in sorted(files, key=lambda p: os.path.getmtime(p), reverse=True):
        key = os.path.normcase(os.path.abspath(f))
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def load_symbols(spec=None, build=None):
    """spec(파일·폴더·None=기본 후보)에서 심볼을 고른다. build 를 주면 build_id 가 같은 것(가장 새것).
    build 가 없거나 맞는 것이 없으면: spec 이 파일이면 그 파일, 아니면 가장 새 심볼. 아무것도 없으면 빈 Symbols."""
    if spec and os.path.isfile(spec) and build is None:
        return Symbols(spec)
    files = symbol_files(spec)
    docs = []
    for f in files:
        doc = read_symbol_doc(f)
        if doc.get("format", "eud-debug-bridge") == "eud-debug-bridge" and "build_id" in doc:
            docs.append((f, doc))
    if build is not None:
        for f, doc in docs:
            if doc.get("build_id") == build:
                return Symbols(f, doc)
        if spec and os.path.isfile(spec):
            return Symbols(spec)
        return Symbols(None)
    if docs:
        return Symbols(docs[0][0], docs[0][1])
    return Symbols(None)


def find_blocks(proc, signature, full_scan=False):
    pattern = struct.pack("<8I", *signature)
    hits = proc.scan(pattern, WRITABLE)
    if not hits and full_scan:
        hits = proc.scan(pattern, READABLE)
    blocks = []
    for addr in hits:
        header = proc.dwords(addr, HDR)
        if header is None or header[H_VERSION] != LAYOUT_VERSION:
            continue
        block = Block(proc, addr, header)
        if 0 < block.layout.total <= 0x4000:
            blocks.append(block)
    return hits, blocks


def choose(blocks, build_id=None, wait=0.3):
    """seq 가 움직이는(=게임이 돌고 있는) 블록을 고른다. 심볼의 빌드 ID 와 맞는 것을 먼저."""
    if not blocks:
        return None, []
    before = [b.seq() for b in blocks]
    time.sleep(wait)
    after = [b.seq() for b in blocks]
    live = [b for b, x, y in zip(blocks, before, after) if x is not None and y is not None and x != y]
    pool = sorted(live or blocks, key=lambda b: (b.build == build_id, b.seq() or 0), reverse=True)
    return pool[0], live


def locate(args, sym, errors=None):
    """(proc, 시그니처 위치들, 유효 블록들, 고른 블록, 살아 있는 블록들). 프로세스가 없으면 None.
    프로세스를 못 연 까닭(접근 거부, 비트 수)은 errors 목록이 있으면 거기에 넣고, 없으면 출력한다."""
    pids = [args.pid] if args.pid else find_pids(args.name)
    fallback = None
    for pid in pids:
        try:
            proc = Process(pid)
        except OSError as e:
            if errors is None:
                print(e)
            else:
                errors.append(str(e))
            continue
        hits, blocks = find_blocks(proc, sym.signature, args.full_scan)
        block, live = choose(blocks, sym.build_id)
        if block is not None:
            if fallback:
                fallback[0].close()
            return proc, hits, blocks, block, live
        if fallback is None:
            fallback = (proc, hits, blocks, None, [])
        else:
            proc.close()
    return fallback


# --- 출력 -------------------------------------------------------------------

def s32(value):
    return value - (1 << 32) if value & 0x80000000 else value


def build_tag(sym, block):
    if sym.build_id is None:
        return "심볼 없음"
    if sym.build_id == block.build:
        return "심볼 일치"
    return f"심볼 불일치 (심볼 {sym.build_id}) - 맵을 다시 컴파일했는지 확인"


class Viewer:
    """실시간 화면 한 장을 만든다. 초당 비율은 최근 1초 창으로 계산한다."""

    def __init__(self, sym):
        self.sym = sym
        self.history = []          # (시각, seq, 프로브 값 튜플)
        self.torn = 0
        self.last_seq = None
        self.last_change = time.perf_counter()

    def _rates(self, now, seq, probes):
        if self.history and seq < self.history[-1][1]:
            self.history.clear()   # seq 가 줄었다 = 새 게임
        self.history.append((now, seq, probes))
        while len(self.history) > 2 and now - self.history[1][0] >= 1.0:
            self.history.pop(0)
        t0, s0, p0 = self.history[0]
        dt = now - t0
        if dt <= 0:
            return None, None
        return (seq - s0) / dt, [(c - p) / dt for c, p in zip(probes, p0)]

    def render(self, block, d, consistent):
        lay = block.layout
        sym = self.sym
        now = time.perf_counter()
        seq = d[H_SEQ_BEGIN]
        if not consistent:
            self.torn += 1
        if seq != self.last_seq:
            self.last_seq, self.last_change = seq, now
        probes = tuple(d[lay.probe_start:lay.probe_start + lay.probe_used])
        fps, rates = self._rates(now, seq, probes)

        status = [f"seq {seq}", f"게임 프레임 {d[H_GAME_FRAME]}", f"로컬 P{d[H_LOCAL_PLAYER] + 1}"]
        if fps is not None:
            status.append(f"{fps:.1f} 프레임/초")
        if now - self.last_change > 2.0:
            status.append("멈춤")
        if self.torn:
            status.append(f"찢어진 읽기 {self.torn}")

        lines = [f"EUD 디버그 브리지  PID {block.proc.pid} ({block.proc.bits}비트)  블록 0x{block.addr:X} (EUD 0x{block.eud:X})",
                 f"빌드 {block.build} [{build_tag(sym, block)}]",
                 "  ".join(status),
                 "",
                 f"-- 감시 {lay.watch_used}/{lay.watch_cap} --"]
        for i in range(lay.watch_used):
            slot = lay.watch_start + i
            value = d[slot]
            info = sym.watches.get(slot, {})
            name = info.get("name", f"watch[{i}]")
            if sym.ext and info.get("kind") in ("text", "dwords", "const"):
                continue                            # eudext: 아래 eudext 칸에서 묶어 보인다
            if info.get("kind") == "ref":
                # 변수가 저장된 EUD 주소. 그 자리를 같은 오프셋으로 직접 읽은 값을 옆에 보인다
                got = block.direct(value) if value else None
                shown = f"직접 {s32(got[0])}" if got else "직접 읽기 불가"
                lines.append(f"  {name:<28} 주소 0x{value:08X}  {shown}  {info.get('site', '')}")
            elif info.get("kind") == "ptr":
                lines.append(f"  {name:<28} 주소 0x{value:08X}  (Ccode 위치 계산용, 자동)  {info.get('site', '')}")
            else:
                lines.append(f"  {name:<28} {s32(value):>12}  0x{value:08X}  {info.get('site', '')}")
        lines += ["", f"-- 프로브 {lay.probe_used}/{lay.probe_cap}  (누적 / 초당) --"]
        for i in range(lay.probe_used):
            index = lay.probe_start + i
            info = sym.probes.get(index, {})
            name = info.get("name", f"probe[{i}]")
            rate = f"{rates[i]:9.1f}/s" if rates and i < len(rates) else ""
            sites = ", ".join(info.get("sites", [])[:3])
            lines.append(f"  {name:<28} {d[index]:>10} {rate:>11}  {sites}")
        if sym.ext:
            lines += [""] + ext_lines(sym, d, block)
        return "\n".join(lines)


# --- eudext: 확장 필드 풀기 --------------------------------------------------------

def words_bytes(words):
    return struct.pack(f"<{len(words)}I", *[w & 0xFFFFFFFF for w in words])


def decode_text(words, plain=True):
    """dword 들 → 글 (NUL 앞까지, UTF-8). plain 이면 SC 색·제어 글자(0x01~0x1F, 줄바꿈 제외)를 뺀다."""
    raw = words_bytes(words).split(b"\0", 1)[0]
    if plain:
        raw = bytes(b for b in raw if b >= 0x20 or b == 0x0A)
    return raw.decode("utf-8", errors="replace")


def ext_values(sym, d):
    """eudext 확장 → {"checks": {이름: (통과, 전체)}, "results": {이름: (통과, 전체, 보고)}, "marks": {이름: 값},
    "hits": {이름: 값}, "watches": {이름: 값(64·128비트는 합친 정수, signed 면 부호 있게)}, "texts": {이름: (글, 원문 dword)},
    "marker": 표지 칸 값}"""
    ext = sym.ext or {}
    out = {"checks": {}, "results": {}, "marks": {}, "hits": {}, "watches": {}, "texts": {}, "suites": {},
           "suite_now": None, "marker": d[HDR] if len(d) > HDR else None}

    def at(i):
        return d[i] if isinstance(i, int) and 0 <= i < len(d) else None

    for c in ext.get("checks", []):
        out["checks"][c["name"]] = (at(c["pass"]), at(c["total"]))
    for r in ext.get("results", []):
        out["results"][r["name"]] = (at(r["pass"]), at(r["total"]), at(r["reports"]))
    for m in ext.get("marks", []):
        out["marks"][m["name"]] = at(m["index"])
    for h in ext.get("hits", []):
        out["hits"][h["name"]] = at(h["index"])
    for w in ext.get("watches", []):
        parts = [at(w["slot"] + k) for k in range(w.get("count", 1))]
        if None in parts:
            out["watches"][w["name"]] = None
            continue
        value = sum(p << (32 * k) for k, p in enumerate(parts))
        bits = 32 * len(parts)
        if w.get("signed") and value >> (bits - 1):
            value -= 1 << bits
        out["watches"][w["name"]] = value
    for t in ext.get("texts", []):
        words = [at(t["slot"] + k) for k in range(t["count"])]
        if None in words:
            continue
        text = decode_text(words) if t.get("kind") == "text" else None
        out["texts"][t["name"]] = (text, tuple(words))
    by_no = {}
    for s in ext.get("suites", []):
        # (상태 0 미실행·1 도는 중·2 끝, 시작 프레임, 끝 프레임, 판정 0 없음·1 통과·2 실패)
        out["suites"][s["name"]] = (at(s["state"]), at(s["begin"]), at(s["end"]), at(s["verdict"]))
        by_no[s.get("no")] = s["name"]
    slots = ext.get("suite_slots")
    if slots:
        cur, last, frame = at(slots["current"]), at(slots["last"]), at(slots["frame"])
        out["suite_now"] = {"current": by_no.get(cur) if cur else None, "last": by_no.get(last) if last else None,
                            "frame": frame}
    return out


def ext_lines(sym, d, block=None):
    ext = sym.ext
    v = ext_values(sym, d)
    marker_ok = v["marker"] == ext.get("marker")
    lines = [f"-- eudext: 맵 {ext.get('map_name')}  ({ext.get('build_tag', '')}, 블록 {ext.get('where')})"
             + ("" if marker_ok else f"  표지 불일치 0x{(v['marker'] or 0):08X}") + " --"]
    now = v["suite_now"]
    if now is not None:
        lines.append(f"  단계 지금 {now['current'] or '-'}  (마지막으로 시작한 단계 {now['last'] or '-'}, 사건 프레임 {now['frame']})")
    for name, (state, begin, end, verdict) in v["suites"].items():
        what = {0: "미실행", 1: "도는 중", 2: "끝"}.get(state, f"상태 {state}")
        judged = {1: "  맵 판정 통과", 2: "  맵 판정 실패"}.get(verdict, "")
        span = f"프레임 {begin}~{end}" if state == 2 else (f"프레임 {begin}~" if state == 1 else "")
        lines.append(f"  단계 {name:<24} {what} {span}{judged}")
    for name, (p, t) in v["checks"].items():
        state = "통과" if t and p == t else ("실패 있음" if t else "아직 없음")
        lines.append(f"  판정 {name:<24} {p} / {t}  {state}")
    for name, (p, t, n) in v["results"].items():
        state = "보고 없음" if not n else ("통과" if p == t else "다름")
        lines.append(f"  결과 {name:<24} {p} / {t}  (보고 {n}회)  {state}")
    for name, value in v["marks"].items():
        lines.append(f"  표식 {name:<24} {value}")
    for name, value in v["watches"].items():
        if value is not None and (value > 0xFFFFFFFF or value < -0x80000000):
            lines.append(f"  값   {name:<24} {value}")
    for name, (text, words) in v["texts"].items():
        if text is None:
            lines.append(f"  칸   {name:<24} " + " ".join(f"{w:08X}" for w in words[:8]) + (" …" if len(words) > 8 else ""))
        else:
            lines.append(f"  글   {name:<24} {text!r}")
    return lines


def region_text(proc, addr):
    mbi = proc.query(addr)
    if mbi is None:
        return "영역 정보 없음"
    kind = MEM_TYPES.get(mbi.Type, hex(mbi.Type))
    span = proc.region_of(addr)
    start, end = span if span else (mbi.BaseAddress, mbi.BaseAddress + mbi.RegionSize)
    text = f"영역 0x{start:X}~0x{end:X} (0x{end - start:X}) {kind} 보호 0x{mbi.Protect:X}"
    for name, base, size in proc.modules():
        if base <= addr < base + size:
            text += f"  ({name}+0x{addr - base:X})"
            break
    return text


def same_value(got, before, after):
    """직접 읽은 값이 블록 사본(읽기 전/후 스냅숏)과 같은지. 그사이 한두 사이클 증가는 봐준다."""
    if got in (before, after):
        return True
    lo, hi = min(before, after), max(before, after)
    return lo <= got <= hi + 2


def wait_change(block, slots, timeout):
    """slots 중 블록 사본 값이 먼저 바뀐 슬롯을 돌려준다 (timeout 안에 안 바뀌면 None)."""
    d, _ = block.snapshot()
    if d is None:
        return None
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(0.05)
        cur, _ = block.snapshot()
        if cur is None:
            continue
        for slot in slots:
            if cur[slot] != d[slot]:
                return slot
    return None


def locate_var_memory(block, failed, log, shape=False, min_rounds=0, dist_label="EUD 거리"):
    """변수 값이 실제 메모리의 어디에 사는지 치트엔진의 '다음 스캔' 식으로 찾는다.

    failed: [(이름, 좌표, 같은 변수를 복사해 둔 블록 슬롯)]. 좌표는 맵이 적어 준 EUD 주소(DBG_Ref) 또는
      VARSTACK 오프셋 - 같은 구역 안에서 좌표 차이가 실제 주소 차이와 같으면 된다.
      1) 값이 바뀌는 변수를 기준으로 삼는다 (없으면 좌표가 가장 낮은 것).
      2) 기준 값과 같은 4바이트 정렬 자리를 쓰기 가능한 메모리에서 모두 모은다 (조각마다 그때의 값 ±1).
         블록 안의 사본 자리는 뺀다. shape 이면 SetDeaths 값 칸 모양(+6 바이트가 0x2D)인 자리만 모은다.
      3) 기준 값이 바뀔 때마다 "사본과 정확히 같은 값이고, 지난번에 본 값에서 바뀐" 자리만 남긴다 (최대 6번,
         적어도 min_rounds 번). 가만히 있는 자리는 첫 번째 변화에서 떨어진다. 값이 안 바뀌는 변수뿐이면
         대신 다른 변수까지의 좌표 거리만큼 떨어진 곳에 그 값이 있는 자리만 남긴다.
    돌려주는 값: (기준 항목, [(실제 주소, 오프셋 = 실제 주소 - 좌표, [(다른 변수 이름, 같은 오프셋에서 맞는지)])])
    """
    proc = block.proc
    moving_slot = wait_change(block, [slot for _n, _e, slot in failed], 2.0)
    if moving_slot is not None:
        anchor = next(f for f in failed if f[2] == moving_slot)
    else:
        anchor = min(failed, key=lambda f: f[1])
    name0, eud0, slot0 = anchor
    others = [f for f in failed if f is not anchor]
    d, _ = block.snapshot()
    v0 = d[slot0]
    lo_ex, hi_ex = block.addr, block.addr + 4 * block.layout.total
    cands = {}                           # 실제 주소 -> 마지막으로 본 값

    def expected():
        # 스캔 도중에도 값이 바뀌므로 조각을 읽을 때마다 사본의 '지금 값' 을 다시 본다. 예전엔 시작 때 값 근처만
        # 찾아서, 메모리 전체를 훑는 십몇 초 사이에 값이 올라가 버리면 진짜 자리를 놓쳤다
        if moving_slot is None:
            return {v0}
        snap, _ = block.snapshot()
        v = snap[slot0] if snap else v0
        return {(v + k) & 0xFFFFFFFF for k in (-1, 0, 1)}

    for base, size in proc.regions(WRITABLE):
        off = 0
        while off < size and len(cands) < 3_000_000:
            n = min(8 << 20, size - off)
            values = expected()
            data = proc.read(base + off, n)
            values |= expected()
            for value in values:
                pat = struct.pack("<I", value)
                i = data.find(pat)
                while i != -1:
                    a = base + off + i
                    if (a % 4 == 0 and not lo_ex <= a < hi_ex
                            and (not shape or i + 6 >= len(data) or data[i + 6] == ACT_SETDEATHS)):
                        cands[a] = value
                    i = data.find(pat, i + 1)
            off += n
    near = " (조각마다 그때의 값으로)" if moving_slot is not None else ""
    kind = ", 값 칸 모양만" if shape else ""
    log(f"기준 {name0}: 값 {s32(v0)}{near}{kind} 찾은 자리 {len(cands)}곳")

    if moving_slot is not None:
        for r in range(6):
            if not cands or (r >= min_rounds and len(cands) <= 3):
                break
            if wait_change(block, [slot0], 3.0) is None:
                log("  기준 값이 3초 동안 안 바뀌어 여기서 멈춤")
                break
            before, _ = block.snapshot()
            got = proc.read_many(cands)
            after, _ = block.snapshot()
            now = (before[slot0], after[slot0])
            cands = {a: got[a] for a in cands
                     if got.get(a) is not None and got[a] in now and got[a] != cands[a]}
            log(f"  값이 바뀐 뒤 {r + 1}회: 사본과 같이 움직인 자리 {len(cands)}곳")
    else:
        for name, eud, slot in others:
            dist = eud - eud0
            got = proc.read_many([a + dist for a in cands])
            cands = {a: v for a, v in cands.items() if got.get(a + dist) == d[slot]}
            log(f"  {name} 까지 {dist_label} 0x{dist:X} 에 그 값이 있는 자리 {len(cands)}곳")

    results = []
    for a in sorted(cands)[:10]:
        delta = a - eud0
        checks = []
        d2, _ = block.snapshot()
        for name, eud, slot in others:
            got = proc.dwords(eud + delta, 1)
            checks.append((name, got is not None and same_value(got[0], d[slot], d2[slot])))
        results.append((a, delta, checks))
    return anchor, results


def diag(proc, hits, blocks, block, live, sym):
    print(f"[프로세스] PID {proc.pid}  {proc.bits}비트 (리더 {READER_BITS}비트 Python)")
    print(f"[스캔] 시그니처 {len(hits)}곳, 유효한 블록 {len(blocks)}개")
    for b in blocks:
        tag = "살아 있음" if b in live else "멈춤"
        print(f"  0x{b.addr:X}  빌드 {b.build}  seq {b.seq()}  {tag}")
        print(f"      {region_text(proc, b.addr)}")
    if block is None:
        return

    # 비교 대상: (이름, EUD 주소, 블록 인덱스, dword 수, 계속 바뀌는 값인가)
    rows = [(name, eud, index, count, False) for name, eud, index, count in STATIC_COPIES]
    rows.append(("game_frame", GAME_FRAME_EUD, H_GAME_FRAME, 1, True))
    for slot, w in sorted(sym.watches.items()):
        if w.get("kind") == "mem":
            rows.append((w["name"], int(w["src"], 16), slot, 1, True))
    refs = [(slot, w) for slot, w in sorted(sym.watches.items()) if w.get("kind") == "ref"]

    d0, _ = block.snapshot()
    if d0 is None:
        print("블록을 읽지 못했습니다.")
        return
    direct = [block.direct(eud, count) for _name, eud, _index, count, _dyn in rows]
    ref_ptr = [d0[slot] for slot, _w in refs]
    ref_same = [proc.dwords(ptr, 1) if ptr else None for ptr in ref_ptr]          # (a) EUD 주소 그대로
    ref_delta = [block.direct(ptr) if ptr else None for ptr in ref_ptr]           # (b) 블록 오프셋
    d1, _ = block.snapshot()
    if d1 is None:
        print("블록을 읽지 못했습니다.")
        return

    print(f"\n[선형 매핑 진단] 실제 주소 = EUD 주소 + 0x{block.delta:X}. 맵이 블록에 복사해 둔 값과 그 주소를 직접 읽은 값을 비교한다")
    ok, bad, gone = [], [], []
    for (name, eud, index, count, dynamic), got in zip(rows, direct):
        want0, want1 = tuple(d0[index:index + count]), tuple(d1[index:index + count])
        if got is None:
            state = "읽기 불가"
            gone.append(name)
        elif tuple(got) in (want0, want1) or (count == 1 and same_value(got[0], want0[0], want1[0])):
            state = "일치" if any(want1) or dynamic else "판단 보류 (둘 다 0)"
            if state == "일치":
                ok.append((name, eud))
        elif not dynamic and not any(want1):
            state = "판단 보류 (사본이 0)"
        else:
            state = "불일치"
            bad.append(name)
        copy = " ".join(f"{x:08X}" for x in want1)
        now = " ".join(f"{x:08X}" for x in got) if got else "-"
        print(f"  {name:<18} EUD 0x{eud:06X}  {state:<16} 사본 {copy}  직접 {now}")

    spans = {}
    for name, eud in ok + [("디버그 블록", block.eud)]:
        span = proc.region_of(eud + block.delta)
        if span:
            spans.setdefault(span, []).append(name)
    if spans:
        print("\n  직접 읽히는 영역 (실제 메모리 영역 하나가 한 줄 = 그 안의 EUD 주소는 모두 같은 오프셋):")
        for (start, end), names in sorted(spans.items()):
            print(f"    EUD 0x{start - block.delta:06X} ~ 0x{end - block.delta:06X}  (0x{end - start:X} 바이트)  <- {', '.join(names)}")

    ref_notes = []
    if refs:
        var_slot = {w["src"]: slot for slot, w in sym.watches.items() if w.get("kind") == "var"}
        print("\n[변수 메모리 진단] 맵이 적어 둔 '변수 값이 저장된 EUD 주소' 를 실제 메모리에서 읽어 본다")
        print("  (a) EUD 주소 그대로 읽기   (b) 블록과 같은 오프셋으로 읽기")
        way = {"a": [], "b": []}
        failed = []
        for (slot, w), ptr, got_a, got_b in zip(refs, ref_ptr, ref_same, ref_delta):
            vslot = var_slot.get(w["src"])
            if not ptr:
                print(f"  {w['name']:<18} 주소 0 (아직 안 적힘)")
                continue
            if vslot is None:
                print(f"  {w['name']:<18} 비교할 사본 없음 - 같은 변수를 DBG_Watch 로도 등록할 것")
                continue
            parts = []
            hit = False
            for label, got in (("a", got_a), ("b", got_b)):
                if got is None:
                    parts.append(f"({label}) 읽기 불가")
                elif same_value(got[0], d0[vslot], d1[vslot]):
                    parts.append(f"({label}) 일치")
                    if not hit:
                        way[label].append(w["name"])
                    hit = True
                else:
                    parts.append(f"({label}) 불일치 {s32(got[0])}")
            if not hit:
                failed.append((w["name"], ptr, vslot))
            print(f"  {w['name']:<18} {w['src']:<10} 주소 EUD 0x{ptr:08X}  사본 {s32(d1[vslot])}  " + "  ".join(parts))

        if way["a"]:
            ref_notes.append(f"{', '.join(way['a'])}: EUD 주소가 곧 실제 주소 -> 복사 없이 읽힙니다.")
        if way["b"]:
            ref_notes.append(f"{', '.join(way['b'])}: 블록과 같은 오프셋 -> 복사 없이 읽힙니다.")
        if failed:
            print("\n  (c) 치트엔진의 '다음 스캔' 식으로 변수 값이 실제로 사는 자리를 찾는다 (10초쯤 걸림)...")
            started = time.perf_counter()
            anchor, results = locate_var_memory(block, failed, lambda text: print("      " + text, flush=True))
            print(f"      ({time.perf_counter() - started:.1f}초)")
            name0, eud0, _slot0 = anchor
            names = ", ".join(n for n, _e, _s in failed)
            linear = []
            for real, delta, checks in results:
                span = proc.region_of(real)
                where = f"영역 0x{span[0]:X}~0x{span[1]:X}" if span else "영역 ?"
                same_page = "페이지 안 위치 같음" if (real & 0xFFF) == (eud0 & 0xFFF) else "페이지 안 위치 다름"
                verdict = ", ".join(f"{n} {'일치' if good else '불일치'}" for n, good in checks) or "검증할 다른 변수 없음"
                print(f"      찾은 자리 0x{real:X} ({where}, {same_page})  오프셋 0x{delta:X}  -> 같은 오프셋에서 {verdict}")
                if checks and all(good for _n, good in checks):
                    linear.append(delta)
            if linear:
                ref_notes.append(f"{names}: 별도 오프셋 0x{linear[0]:X} 로 선형 (변수 {len(failed)}개로 확인) "
                                 "-> 이 오프셋만 알면 복사 없이 읽힙니다.")
            elif results and not any(checks for _r, _d, checks in results):
                ref_notes.append(f"{name0}: 실제 자리 후보는 찾았지만 검증할 다른 변수가 없습니다 "
                                 "-> 서로 떨어진 변수를 DBG_Ref + DBG_Watch 로 하나 더 등록할 것.")
            elif results:
                ref_notes.append(f"{name0}: 실제 자리는 찾았지만 다른 변수는 같은 오프셋이 아닙니다 "
                                 "-> 변수 메모리는 한 오프셋으로 안 이어집니다 (변수마다 따로 놓임). DBG_Watch 복사로 봅니다.")
            else:
                ref_notes.append(f"{names}: 실제 자리를 못 찾았습니다 -> DBG_Watch 복사로 봅니다.")

    print()
    if not gone and not bad:
        print("결론: 확인한 주소가 전부 같은 오프셋으로 읽힙니다.")
    elif ok:
        print("결론: 부분 선형. 위 '직접 읽히는 영역' 안의 1.16.1 주소는 맵이 복사하지 않아도 --peek 로 직접 읽을 수 있습니다.")
        if gone:
            print(f"      읽기 불가({', '.join(gone)})는 SC:R 이 다른 곳에서 처리하는 주소라 DBG_Watch 로 복사해야 합니다.")
        if bad:
            print(f"      불일치({', '.join(bad)})는 직접 읽히는 영역 밖이라 그 자리가 다른 메모리이거나, 값이 빨리 바뀌는 중입니다.")
    else:
        print("결론: 블록 밖은 같은 오프셋으로 읽히지 않습니다. 필요한 값은 DBG_Watch 로 복사해야 합니다.")
    if ref_notes:
        print("      변수 메모리:")
        for note in ref_notes:
            print("        " + note)


def peek(block, specs, raw=False):
    if raw:
        print("실제 주소 그대로 읽는다 (오프셋 없음)")
    else:
        print(f"실제 주소 = EUD 주소 + 0x{block.delta:X} (블록 기준). --diag 의 '직접 읽히는 영역' 밖이면 값을 믿지 말 것")
    for spec in specs:
        addr_text, _, count_text = spec.partition(":")
        addr = int(addr_text, 0)
        count = int(count_text, 0) if count_text else 1
        got = block.proc.dwords(addr, count) if raw else block.direct(addr, count)
        label = "주소" if raw else "EUD"
        if got is None:
            print(f"  {label} 0x{addr:06X}  읽기 불가 (그 자리에 메모리가 없음)")
            continue
        for i, value in enumerate(got):
            print(f"  {label} 0x{addr + 4 * i:06X}  {value:>10}  {s32(value):>11}  0x{value:08X}")


# --- 변수 모드 (VarStack 빌드) ------------------------------------------------

class VarStack:
    """VarStack tepc 가 컴파일할 때 쓰는 VARSTACK.txt.
    줄 형식: "BASE P8 78F7FA0 N 1107 NREC 34" 다음에 "P8 <변수 번호 16진> <칸> <오프셋 16진>".
    같은 스택(트리거 플레이어) 안에서는 실제 주소 = 기준 + 오프셋 이고, 기준은 판마다 달라 리더가 찾는다.
    AllPlayers 변수는 P1~P7 스택마다 같은 번호로 따로 있고 스택마다 기준도 따로다."""

    def __init__(self, path):
        self.path = path
        self.stacks = {}         # 스택 이름 -> {변수 번호: 오프셋}
        self.mtime = None
        if path and os.path.isfile(path):
            self.mtime = os.path.getmtime(path)
            with open(path, encoding="ascii", errors="replace") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) < 4 or parts[0] == "BASE":
                        continue
                    try:
                        index, off = int(parts[1], 16), int(parts[3], 16)
                    except ValueError:
                        continue
                    self.stacks.setdefault(parts[0], {})[index] = off
        self.loaded = bool(self.stacks)


class VarBase:
    """찾은 변수 구역: 실제 주소 = base + VARSTACK 오프셋 (stack 스택 안에서만)."""

    def __init__(self, base, stack, anchors, how, shape=True):
        self.base, self.stack, self.anchors, self.how, self.shape = base, stack, anchors, how, shape


def var_anchors(sym, vs):
    """DBG_Watch 로 블록에 복사되는 변수 중 VARSTACK 에 있는 것: {스택: [(이름, 오프셋, 슬롯)]}"""
    out = {}
    for slot, w in sorted(sym.watches.items()):
        src = w.get("src", "")
        if w.get("kind") != "var" or not src.startswith("V("):
            continue
        try:
            index = int(src[2:-1])
        except ValueError:
            continue
        for stack, offs in vs.stacks.items():
            if index in offs:
                out.setdefault(stack, []).append((w["name"], offs[index], slot))
    return out


def check_base(block, base, anchors, shape=True):
    """기준이 맞는지: 기준 변수들을 base + 오프셋에서 읽어 블록 사본과 정확히 같고, 값 칸 모양인지."""
    proc = block.proc
    d0, _ = block.snapshot()
    raw = {off: proc.read(base + off, 8) for _n, off, _s in anchors}
    d1, _ = block.snapshot()
    if d0 is None or d1 is None or not anchors:
        return False
    for _name, off, slot in anchors:
        data = raw[off]
        if len(data) < 8 or (shape and data[6] != ACT_SETDEATHS):
            return False
        if struct.unpack_from("<I", data)[0] not in (d0[slot], d1[slot]):
            return False
    return True


CCODE_DATA = 0x1C8          # Ccode 뱅크(CtrigAsm CVariable 트리거)의 480칸이 시작하는 자리 (트리거 머리 기준)
CCODE_LINES = 480


def bank_bases(block, sym, vs, vb, d):
    """Ccode 뱅크(FP 사본) 첫 칸의 실제 주소 {뱅크 번호: 주소} 와 한 줄 설명.
    맵이 매 프레임 적는 EUD 주소(감시 변수 값 칸 "V(n)", 뱅크 "bank(b)")를, VARSTACK 으로 찾은 감시 변수의 실제 주소와의
    차이만큼 옮긴다. 감시 변수가 여럿이면 차이가 모두 같아야 하고, 뱅크 트리거는 첫 두 액션이 SetDeaths 여야 한다."""
    ptrs = {w.get("src", ""): d[slot] for slot, w in sym.watches.items() if w.get("kind") == "ptr" and d[slot]}
    offs = vs.stacks.get(vb.stack, {})
    deltas = {vb.base + offs[int(src[2:-1])] - ptr for src, ptr in ptrs.items()
              if src.startswith("V(") and src[2:-1].isdigit() and int(src[2:-1]) in offs}
    banks = sorted(int(src[5:-1]) for src in ptrs if src.startswith("bank(") and src[5:-1].isdigit())
    if not banks:
        return {}, "Ccode 뱅크 주소가 블록에 없음 (Ccode 를 안 쓰거나 옛 DebugBridge)"
    if len(deltas) != 1:
        return {}, f"감시 변수의 EUD 주소 -> 실제 주소 차이가 {len(deltas)}가지라 Ccode 위치를 계산할 수 없음"
    delta = deltas.pop()
    out, bad = {}, []
    for b in banks:
        real = ptrs[f"bank({b})"] + delta
        raw = block.proc.read(real - CCODE_DATA + 0x148, 0x40)      # 트리거 머리 +0x148 = 첫 액션
        if len(raw) == 0x40 and raw[0x1A] == ACT_SETDEATHS and raw[0x3A] == ACT_SETDEATHS:
            out[b] = real
        else:
            bad.append(b)
    return out, f"Ccode 뱅크 {len(out)}개" + (f" (모양이 안 맞아 뺀 뱅크 {bad})" if bad else "")


def load_cached_base(block):
    try:
        with open(VARBASE_CACHE, encoding="utf-8") as f:
            c = json.load(f)
    except (OSError, ValueError):
        return None
    if c.get("pid") == block.proc.pid and c.get("block") == block.addr and c.get("build") == block.build:
        return c.get("base")
    return None


def save_cached_base(block, vb):
    try:
        with open(VARBASE_CACHE, "w", encoding="utf-8") as f:
            json.dump({"pid": block.proc.pid, "block": block.addr, "build": block.build, "base": vb.base,
                       "stack": vb.stack, "saved": time.strftime("%Y-%m-%d %H:%M:%S")}, f)
    except OSError:
        pass


def find_var_base(block, sym, vs, log, use_cache=True):
    """판마다 한 번: 변수 구역의 기준(실제 주소 = 기준 + VARSTACK 오프셋)을 찾는다. (VarBase 또는 None, 이유)"""
    by_stack = var_anchors(sym, vs)
    if not by_stack:
        return None, ("기준으로 쓸 변수가 없습니다. DBG_Watch 로 블록에 복사하는 변수 중 VARSTACK 에 있는 것이 "
                      "하나 이상 필요합니다 (theSeed: GameTimeSec). 심볼과 VARSTACK 이 같은 빌드인지도 확인할 것.")
    stack = max(by_stack, key=lambda s: (len(by_stack[s]), s == "P8"))
    anchors = by_stack[stack]
    if use_cache:
        base = load_cached_base(block)
        if base is not None and check_base(block, base, anchors):
            return VarBase(base, stack, anchors, "저장해 둔 기준"), ""
    for shape in (True, False):
        anchor, results = locate_var_memory(block, anchors, log, shape=shape, min_rounds=1,
                                            dist_label="VARSTACK 오프셋 거리")
        good = [base for _real, base, checks in results
                if all(ok for _n, ok in checks) and check_base(block, base, anchors, shape)]
        if good:
            if len(good) > 1:
                log(f"  맞는 기준이 {len(good)}개 - 첫 번째를 쓴다: " + ", ".join(f"0x{b:X}" for b in good[:4]))
            vb = VarBase(good[0], stack, anchors, f"기준 변수 {anchor[0]} 로 찾음", shape)
            save_cached_base(block, vb)
            return vb, ""
        if shape:
            log("  값 칸 모양(SetDeaths)인 자리에서는 못 찾음 - 모양을 안 따지고 다시 찾는다")
    return None, "변수 구역을 찾지 못했습니다. 게임이 진행 중인지(기준 변수가 움직이는지) 확인할 것."


def var_rows(sym, vs, stack):
    """[(이름, 변수 번호, 오프셋, 만든 자리)] - 그 스택의 VARSTACK 변수 전부, 이름순"""
    rows = []
    for index, off in vs.stacks.get(stack, {}).items():
        info = sym.vars.get(index, {})
        rows.append((info.get("n") or f"V({index})", index, off, info.get("s", "")))
    rows.sort(key=lambda r: (r[0].lower(), r[1]))
    return rows


def match_vars(rows, patterns):
    """패턴에 맞는 행. * ? 가 있으면 이름 전체와(대괄호는 글자 그대로), 없으면 이름의 일부와 비교한다.
    V(98981) 이나 98981 처럼 변수 번호로도 고른다. 대소문자는 가리지 않는다."""
    if not patterns:
        return rows
    out = []
    for row in rows:
        name = row[0].lower()
        for p in patterns:
            q = p.lower()
            number = q[2:-1] if q.startswith("v(") and q.endswith(")") else q
            if number.isdigit() and int(number) == row[1]:
                hit = True
            elif "*" in q or "?" in q:
                hit = fnmatch.fnmatchcase(name, q.replace("[", "[[]"))
            else:
                hit = q in name
            if hit:
                out.append(row)
                break
    return out


def read_vars(proc, base, offs, span=0x10000):
    """{오프셋: (값, 값 칸 모양인지) 또는 None}. 가까운 변수끼리 묶어 한 번에 읽는다."""
    out = {}
    offs = sorted(set(offs))
    i = 0
    while i < len(offs):
        start = offs[i]
        j = i
        while j + 1 < len(offs) and offs[j + 1] - start < span:
            j += 1
        data = proc.read(base + start, offs[j] - start + 8)
        for off in offs[i:j + 1]:
            k = off - start
            chunk = data[k:k + 8] if len(data) >= k + 8 else proc.read(base + off, 8)
            out[off] = (struct.unpack_from("<I", chunk)[0], chunk[6] == ACT_SETDEATHS) if len(chunk) == 8 else None
        i = j + 1
    return out


def var_notes(sym, vs, vb):
    notes = []
    if not sym.loaded:
        notes.append("심볼 파일이 없어 이름 대신 V(번호)로 보입니다.")
    elif not sym.has_vars:
        notes.append("심볼에 변수 이름표가 없습니다 (이름표 전의 DebugBridge 로 컴파일) - V(번호)로 보입니다.")
    elif sym.doc.get("vars_error"):
        notes.append(f"이름표를 만들다 오류: {sym.doc['vars_error']}")
    if sym.mtime and vs.mtime and vs.mtime < sym.mtime - 5:
        notes.append("VARSTACK.txt 가 심볼 파일보다 먼저 쓰였습니다 - 다른 빌드의 VARSTACK 일 수 있습니다.")
    others = sorted(s for s in vs.stacks if s != vb.stack)
    if others:
        count = sum(len(vs.stacks[s]) for s in others)
        notes.append(f"다른 스택({', '.join(others)}, 변수 {count}개)은 기준이 따로라 여기엔 안 나옵니다.")
    if not vb.shape:
        notes.append("값 칸 모양(SetDeaths)이 아닌 자리에서 찾은 기준입니다 - 값이 이상하면 --rescan.")
    return notes


class VarView:
    """변수 모드 화면 한 장. 값이 바뀐 지 1초가 안 된 행 앞에 * 를 붙인다."""

    def __init__(self, sym, vs, vb, patterns):
        self.sym, self.vs, self.vb = sym, vs, vb
        self.patterns = patterns
        self.notes = var_notes(sym, vs, vb)
        self.seen = {}             # 오프셋 -> (마지막 값, 바뀐 시각)

    def render(self, block, d, rows, values, limit=None):
        now = time.perf_counter()
        vb = self.vb
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.vs.mtime)) if self.vs.mtime else "?"
        total = len(self.vs.stacks.get(vb.stack, {}))
        picked = " ".join(self.patterns) if self.patterns else "(전체)"
        where = f"  seq {d[H_SEQ_BEGIN]}  게임 프레임 {d[H_GAME_FRAME]}" if d else ""
        lines = [f"EUD 디버그 브리지 - 변수  PID {block.proc.pid} ({block.proc.bits}비트)  빌드 {block.build} [{build_tag(self.sym, block)}]",
                 f"{vb.stack} 변수 구역 기준 0x{vb.base:X} ({vb.how}){where}",
                 f"VARSTACK {stamp} ({vb.stack} {total}개)  패턴 {picked} -> {len(rows)}개"]
        lines += ["  ! " + note for note in self.notes]
        lines += ["", f"  {'이름':<32} {'값':>10}  {'16진':<9}  {'V번호':>4}  만든 자리"]  # 한글은 두 칸이라 그만큼 덜 채운다
        shown = rows if limit is None or len(rows) <= limit else rows[:max(limit, 1)]
        for name, index, off, site in shown:
            got = values.get(off)
            if got is None:
                lines.append(f"  {name:<34} {'읽기 불가':>9}")
                continue
            value, shape_ok = got
            prev = self.seen.get(off)
            if prev is None:
                self.seen[off] = (value, float("-inf"))
            elif prev[0] != value:
                self.seen[off] = (value, now)
            mark = "*" if now - self.seen[off][1] < 1.0 else " "
            flag = "  (값 칸 모양 아님 - 위치 의심)" if vb.shape and not shape_ok else ""
            lines.append(f"{mark} {name:<34} {s32(value):>11}  0x{value:08X}  {index:>6}  {site}{flag}")
        if len(shown) < len(rows):
            lines.append(f"  ... 외 {len(rows) - len(shown)}개 - 패턴을 좁히거나 창을 키울 것")
        return "\n".join(lines)


def locate_vars(block, sym, vs, rescan=False):
    print("변수 구역 찾는 중 (저장해 둔 기준이 없으면 10~20초)...", flush=True)
    started = time.perf_counter()
    vb, why = find_var_base(block, sym, vs, lambda text: print("  " + text, flush=True), use_cache=not rescan)
    if vb is None:
        print(why)
        return None
    print(f"기준 0x{vb.base:X} ({vb.how}, {time.perf_counter() - started:.1f}초)", flush=True)
    return vb


def vars_mode(args, sym, proc, block):
    vs = VarStack(args.varstack)
    if not vs.loaded:
        print(f"VARSTACK 파일이 없거나 비었습니다: {args.varstack}")
        print("  변수 모드는 VarStack 을 켠 tepc 로 컴파일한 맵(theSeed)에서만 됩니다. 그 밖의 맵은 DBG_Watch 로 복사해서 봅니다.")
        proc.close()
        return 1
    vb = locate_vars(block, sym, vs, args.rescan)
    if vb is None:
        proc.close()
        return 1
    if args.once or not args.vars:
        rows = match_vars(var_rows(sym, vs, vb.stack), args.vars)
        d, _ = block.snapshot()
        print(VarView(sym, vs, vb, args.vars).render(block, d, rows, read_vars(proc, vb.base, [r[2] for r in rows])))
        proc.close()
        return 0 if rows else 1
    return vars_loop(args, sym, vs, proc, block, vb)


def vars_loop(args, sym, vs, proc, block, vb):
    os.system("")                  # Windows 콘솔에서 ANSI 이스케이프 켜기
    view = rows = None
    last_seq, last_check, misses = None, time.perf_counter(), 0
    try:
        while True:
            d, _ok = block.snapshot()
            if d is None or tuple(d[:8]) != sym.signature:
                proc.close()
                proc = None
                sym, proc, block = wait_for_block(args)
                vb = None
            elif last_seq is not None and d[H_SEQ_BEGIN] < last_seq:
                vb = None                                   # seq 가 줄었다 = 새 게임
            elif vb is not None and time.perf_counter() - last_check > 2.0:
                last_check = time.perf_counter()
                misses = 0 if check_base(block, vb.base, vb.anchors, vb.shape) else misses + 1
                if misses >= 3:                             # 기준 변수가 계속 안 맞으면 다시 찾는다
                    vb = None
            if vb is None:
                sys.stdout.write("\x1b[H\x1b[J")
                vs = VarStack(args.varstack)
                vb = locate_vars(block, sym, vs)
                if vb is None:
                    time.sleep(5)
                    continue
                view, last_seq, misses = None, None, 0
                continue
            if view is None:
                rows = match_vars(var_rows(sym, vs, vb.stack), args.vars)
                view = VarView(sym, vs, vb, args.vars)
            last_seq = d[H_SEQ_BEGIN]
            values = read_vars(proc, vb.base, [r[2] for r in rows])
            limit = shutil.get_terminal_size((120, 40)).lines - 9 - len(view.notes)
            sys.stdout.write("\x1b[H\x1b[J" + view.render(block, d, rows, values, limit) + "\n")
            sys.stdout.flush()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        if proc:
            proc.close()
    return 0


# --- 메인 -------------------------------------------------------------------

def wait_for_block(args):
    """블록을 다시 찾을 때까지 2초마다 스캔한다. 다시 컴파일했을 수 있으니 심볼도 새로 읽는다. (sym, proc, block)"""
    sys.stdout.write("\x1b[H\x1b[J블록을 잃었습니다 (게임 종료/재시작?). 다시 찾는 중...\n")
    sys.stdout.flush()
    while True:
        time.sleep(2)
        sym = load_symbols(args.symbols)
        found = locate(args, sym)
        if found and found[3] is not None:
            return load_symbols(args.symbols, found[3].build), found[0], found[3]
        if found:
            found[0].close()


def live_loop(args, sym, proc, block):
    os.system("")                  # Windows 콘솔에서 ANSI 이스케이프 켜기
    viewer = Viewer(sym)
    try:
        while True:
            d, ok = block.snapshot()
            if d is None or tuple(d[:8]) != sym.signature:
                proc.close()
                proc = None
                sym, proc, block = wait_for_block(args)
                viewer = Viewer(sym)
                continue
            sys.stdout.write("\x1b[H\x1b[J" + viewer.render(block, d, ok) + "\n")
            sys.stdout.flush()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        if proc:
            proc.close()
    return 0


KEY_TABLE_EUD, KEY_TABLE_BYTES = 0x596A18, 256    # eudext: 로컬 키 상태 표 (1.16.1, 미러 구역)


def record_loop(args, sym, proc, block):
    """eudext: 시간순 기록 — seq·게임 프레임·초당 프레임·멈춤·단계 사건, 선택한 값·키 표 변화 (탭으로 나눈 줄).

    CRASH_RISK 세션의 증거용이다. 게임이 튕기면 마지막 줄이 마지막으로 본 상태다(줄마다 바로 파일에 쓴다)."""
    out = open(args.record, "a", encoding="utf-8")
    names = set(args.record_watch or [])

    def put(*cols):
        out.write("\t".join([time.strftime("%H:%M:%S") + ".%03d" % (time.time() % 1 * 1000)] + [str(c) for c in cols]) + "\n")
        out.flush()

    put("시작", f"PID {proc.pid}", f"블록 0x{block.addr:X}", f"빌드 {block.build}",
        f"맵 {(sym.ext or {}).get('map_name', '?')}", f"키 표 {'켬' if args.record_keys else '끔'}")
    last_seq, last_change, stalled = None, time.perf_counter(), False
    prev_vals, prev_keys = None, None
    beat = 0.0
    t_end = time.perf_counter() + args.record_seconds if args.record_seconds else None
    rate = []
    try:
        while t_end is None or time.perf_counter() < t_end:
            now = time.perf_counter()
            d, ok = block.snapshot()
            if d is None or tuple(d[:8]) != sym.signature:
                put("블록 잃음", "게임 종료·튕김·재시작?", f"마지막 seq {last_seq}")
                if args.record_seconds:
                    break
                proc.close()
                proc = None
                sym, proc, block = wait_for_block(args)
                put("블록 다시 찾음", f"0x{block.addr:X}", f"빌드 {block.build}")
                last_seq, prev_vals, prev_keys = None, None, None
                continue
            seq = d[H_SEQ_BEGIN]
            if seq != last_seq:
                if stalled:
                    put("다시 움직임", f"seq {seq}", f"{now - last_change:.2f}초 멈춤")
                    stalled = False
                last_seq, last_change = seq, now
                rate.append((now, seq))
                rate = [x for x in rate if now - x[0] <= 1.0]
            elif not stalled and now - last_change >= args.stall_seconds:
                stalled = True
                vals = ext_values(sym, d) if sym.ext else None
                where = (vals or {}).get("suite_now") or {}
                put("멈춤", f"seq {seq}", f"{args.stall_seconds:g}초 넘게 정지", f"단계 {where.get('current') or '-'}",
                    f"사건 프레임 {where.get('frame')}")
            if sym.ext and ok:
                vals = ext_values(sym, d)
                if prev_vals is not None:
                    for name, st in vals["suites"].items():
                        if prev_vals["suites"].get(name, (0,))[0] != st[0]:
                            put("단계", name, {1: "시작", 2: "끝"}.get(st[0], st[0]), f"프레임 {st[1] if st[0] == 1 else st[2]}")
                    for group in ("watches", "marks", "hits", "checks", "results", "texts"):
                        for name, v in vals[group].items():
                            if name in names and prev_vals[group].get(name) != v:
                                shown = v[0] if group == "texts" and v[0] is not None else v
                                put("값", name, prev_vals[group].get(name) if group != "texts" else "", shown)
                prev_vals = vals
            if args.record_keys:
                raw = block.proc.read(KEY_TABLE_EUD + block.delta, KEY_TABLE_BYTES)
                if len(raw) == KEY_TABLE_BYTES:
                    if prev_keys is not None and raw != prev_keys:
                        for vk in range(KEY_TABLE_BYTES):
                            if raw[vk] != prev_keys[vk]:
                                put("키", f"0x{vk:02X}", "누름" if raw[vk] else "뗌", f"seq {seq}")
                    prev_keys = raw
            if now - beat >= 1.0:
                beat = now
                fps = (rate[-1][1] - rate[0][1]) / (rate[-1][0] - rate[0][0]) if len(rate) > 1 and rate[-1][0] > rate[0][0] else 0
                put("박동", f"seq {seq}", f"게임 프레임 {d[H_GAME_FRAME]}", f"{fps:.1f} 프레임/초", "일관" if ok else "찢어짐")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        put("끝", f"마지막 seq {last_seq}")
        out.close()
        if proc:
            proc.close()
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="EUD 디버그 브리지 리더 (DebugBridge.lua 의 짝)")
    ap.add_argument("--symbols", default=DEFAULT_SYMBOLS,
                    help="심볼 JSON 또는 폴더 (기본: EUDEXT_DBG_SYMBOLS·EUDEXT_DBG_DIR·작업 폴더 dbg·C:\\Temp 순으로 찾음)")
    ap.add_argument("--name", default="StarCraft.exe", help="대상 프로세스 이름 (기본 %(default)s)")
    ap.add_argument("--pid", type=int, help="대상 PID. 주면 --name 은 무시")
    ap.add_argument("--once", action="store_true", help="한 번만 출력하고 끝낸다")
    ap.add_argument("--vars", nargs="*", metavar="PATTERN",
                    help="변수 모드: CreateVar 변수를 이름/패턴으로 골라 본다 (VarStack 빌드). 패턴 없으면 전체 목록 한 번")
    ap.add_argument("--varstack", default=DEFAULT_VARSTACK, help="VARSTACK.txt (기본 %(default)s)")
    ap.add_argument("--rescan", action="store_true", help="--vars 에서 저장해 둔 기준을 쓰지 않고 새로 찾는다")
    ap.add_argument("--diag", action="store_true", help="스캔 결과와 선형 매핑 / 변수 메모리 진단만 출력")
    ap.add_argument("--peek", nargs="+", metavar="ADDR[:N]", help="EUD 주소를 블록 기준 오프셋으로 직접 읽는다")
    ap.add_argument("--raw", action="store_true", help="--peek 에서 오프셋 없이 실제 주소 그대로 읽는다")
    ap.add_argument("--interval", type=float, default=0.25, help="갱신 간격 초 (기본 %(default)s)")
    ap.add_argument("--full-scan", action="store_true", help="쓰기 가능 영역에서 못 찾으면 읽기 전용 영역까지 스캔")
    # eudext 추가
    ap.add_argument("--judge", nargs="+", metavar="SPEC",
                    help="eudext: 자동 판정 (명세 파일·폴더 → tools/ingame_auto.py). 다른 옵션은 ingame_auto 를 직접 실행")
    ap.add_argument("--record", metavar="FILE", help="eudext: 시간순 기록 파일 (seq·프레임/초·멈춤·단계, 탭 구분, 덧붙임)")
    ap.add_argument("--record-keys", action="store_true", help="eudext: --record 에 로컬 키 표(0x596A18) 변화도 적는다")
    ap.add_argument("--record-watch", nargs="*", metavar="NAME", help="eudext: --record 에 이 이름의 값 변화를 적는다")
    ap.add_argument("--record-seconds", type=float, default=0, help="eudext: --record 를 이만큼만 (0 = Ctrl+C 까지)")
    ap.add_argument("--stall-seconds", type=float, default=2.0, help="eudext: --record 에서 멈춤으로 볼 seq 정지 시간")
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if not WIN32:
        print("Windows 전용 도구입니다.")
        return 1
    if args.judge:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        if root not in sys.path:
            sys.path.insert(0, root)
        from eudext.tools import ingame_auto
        judge_argv = ["--specs", *args.judge]
        if args.symbols:
            judge_argv += ["--symbols", args.symbols]
        judge_argv += ["--pid", str(args.pid)] if args.pid else ["--name", args.name]
        return ingame_auto.main(judge_argv)
    sym = load_symbols(args.symbols)
    print("메모리 스캔 중...", flush=True)
    started = time.perf_counter()
    found = locate(args, sym)
    if found is None:
        print(f"{args.pid or args.name} 프로세스를 찾지 못했습니다.")
        return 1
    proc, hits, blocks, block, live = found
    if block is not None:                   # eudext: 찾은 블록의 빌드 ID 와 짝인 심볼
        sym = load_symbols(args.symbols, block.build)
    print(f"심볼: {sym.path if sym.loaded else '없음 - 이름 대신 번호로 표시'}")
    print(f"스캔 {time.perf_counter() - started:.1f}초")

    if args.diag:
        diag(proc, hits, blocks, block, live, sym)
        proc.close()
        return 0 if block else 1
    if block is None:
        print("디버그 블록을 찾지 못했습니다. 맵이 DBG_Init(true) 로 컴파일됐고 게임이 시작됐는지 확인하세요.")
        proc.close()
        return 1
    if args.vars is not None:
        return vars_mode(args, sym, proc, block)
    if args.record:
        return record_loop(args, sym, proc, block)
    if args.peek:
        peek(block, args.peek, args.raw)
        proc.close()
        return 0
    if args.once:
        d, ok = block.snapshot()
        print(Viewer(sym).render(block, d, ok) if d else "블록을 읽지 못했습니다.")
        proc.close()
        return 0
    return live_loop(args, sym, proc, block)


if __name__ == "__main__":
    sys.exit(main())
