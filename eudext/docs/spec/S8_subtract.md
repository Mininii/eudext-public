# S8 — 뺄셈 의미 전수 조사 (포화 vs wrap)

작성 2026-09-17. 대상: eudplib 0.76.14(설치본)·0.81.0(소스 + euddraft 0.11.0.1 번들로 실측), CtrigAsm v5.5, DPS 이식 명세, SC:R 액션.
DESIGN.md 3.5·4.3·4.4·7절 D3 를 확정하기 위한 조사다. 코드는 구현하지 않았고, 실험 스크립트와 인게임 시험 맵 소스만 만들었다.

**용어**
- **포화**: 0 에서 멈추는 뺄셈이다. `max(0, a − b)` (부호 없음)
- **wrap**: 한 바퀴 도는 뺄셈이다. `(a − b) mod 2^n`
- **Sub**: SC 액션 수정자 Subtract(9)
- **SubX**: 마스크(eudx `'SC'` 표식)가 붙은 Subtract
- **Add−**: 값이 0x80000000 이상인 Add, 곧 음수를 더하는 액션
- **AddX**: 마스크가 붙은 Add

**근거 약칭**

| 약칭 | 위치 |
|---|---|
| `E76:` | `C:\Users\whatd\.venvs\eud076\Lib\site-packages\eudplib\` (0.76.14) |
| `E81:` | `C:\Users\whatd\AppData\Local\Temp\claude\c--Users-whatd-Documents-MSF-Template\3ae10ce7-f379-40ba-95b4-2dbc6ccacb8c\scratchpad\upstream\eudplib\src\eudplib\` (0.81.0 소스) |
| `CL:` | 같은 스크래치패드의 `upstream\euddraft\CHANGELOG.md` |
| `CA:` / `LF:` / `GB:` | `MapSource\Library\CtrigAsm v5.5.lua` / `LibraryFor322.lua` / `Ctrig Assembler v5.4 Guide Book.txt` |
| `G1:` `G2:` `G3:` / `war:` `arith:` | `ScmDraft 2\DPS_eud\eud\spec\G?_*.md` / `DPS_eud\eud\ctrig\war.py`, `arith.py` |
| `X:` | 실험 폴더 `scratchpad\spec_s8\` (세션 임시 폴더라 핵심 수치는 이 문서에 옮겨 적었다) |
| `W1:` | llvm-bw 위키 "Instruction-Implementation" (https://github.com/heinermann/llvm-bw/wiki/Instruction-Implementation, 2020-02 수정). 사본 `X:llvmbw_instr.md` |
| `W2:` | "EUD Documentation" gist (https://gist.github.com/wdcqc/54df5ad49f7d5887a8f84c2ac0cd86ef, 2024-11). 사본 `X:gist_euddoc.md` |

**실험 방법**
- eudplib 경로마다 3에서 5를 빼는 코드를 만들었다. 이를 트리거 에뮬레이터(`X:emu.py`)로 돌리면서, **페이로드 바이트에서 실제로 실행된 SetDeaths 액션**(수정자·마스크·값·원래 값)을 사례별로 기록했다(`X:s8_paths.py`의 `TraceMachine`).
- 0.76.14는 venv 파이썬으로 돌렸다. 0.81.0은 euddraft 0.11.0.1 플러그인 안에서 같은 스크립트를 돌렸다(`X:s8_plugin.py`, `X:s8_081.eds`).
- 결과 파일은 `X:s8_paths_0.76.14.txt`와 `X:s8_paths_0.81.0.txt`다.
- 에뮬레이터의 Subtract 포화·마스크 식은 **가정**이다. 그래서 의미는 "어떤 액션이 나갔고, 0 에서 멈춘 Subtract(`Sub*`)가 결과를 정했는가"로 판정했다.

---

## 1. 한눈에

1. **eudplib의 규칙은 이름에 있다.** 연산자(`-=`, `-`, `--`, 단항 `-`)와 이름에 `sub`만 든 것(`isubitem`, `isubattr`)은 **wrap**이다(`Add−` 또는 `~x+1`로 뺀다). 이름에 `Subtract`가 든 것은 모두 SC Subtract 액션이라 **포화**다. 해당하는 것은 `SubtractNumber(X)`, `SeqCompute/SetVariables(…, Subtract, …)`, `f_dw/w/bsubtract_*`, `isubtractitem/attr`, `QueueSubtractTo`다.
2. **예외는 하나다.** `VariableBase.__isub__`만 연산자인데 포화다. 이것은 `EUDLightVariable -= x`로 드러난다(`E76 vbase.py:85-87`, `E81 vbase.py:89-91`). 0.81에서 새로 생긴 경로(scdata 멤버 `-=`, `TrgUnit`·`TrgPlayer` 값 `-=`, 0.81 `EUDVArray[i] -=`)는 모두 wrap이다. 0.76.14와 0.81.0의 뺄셈 의미는 **같다**(실측).
3. **eudplib 버그를 새로 찾았다.** 같은 변수끼리 `v -= v`를 하면 두 판 모두 **0xFFFFFFFF**가 나온다. `self += 1`을 먼저 한 뒤 `~self`를 더하기 때문이다(`E81 eudv.py:253-263`). eudext는 이 경로를 피해야 한다.
4. **CtrigAsm도 같은 규칙이다.**
   - 포화: `CSub`, `_Sub`, `V`의 이항 `-`, `SubV`, `SubCD`, `SubVX`, `f_LSub`
   - wrap: `CiSub`, `_iSub`, 단항 `-v`, `CNeg`, `f_LiSub`, `f_LNeg`

   **`f_LSub`는 64비트 전체 기준 포화**다(`S ≥ O ? S−O : 0`, 빌림 처리 포함, `CA:72945-73055`). 반면 `SetNWar(W, Subtract, …)`는 반쪽별 포화라서 다르다(`G1:273`).
5. **64비트 설계**
   - wrap: 상수는 트리거 1~2개, 변수는 인라인 6개 또는 공유 EUDFunc(본문 8, 호출 자리 1)다.
   - 포화(64비트 전체): 상수는 **분기 없이 트리거 2~4개**, 변수는 인라인 7개(실행 14) 또는 EUDFunc(본문 9)다.
   - 2,076쌍으로 검증했고 모두 통과했다. war.py `_subsat64`(본문 27, 실행 51)보다 싸다.
   - **마스크 Subtract의 세부 의미는 인게임 확인이 필요하다**(`S8_ingame\`, 8절).

---

## 2. eudplib 뺄셈 경로 표

"내는 액션" 칸은 3 − 5를 실행했을 때 페이로드에서 읽은 액션이다.
- `~`는 `0xFFFFFFFF`에서 빼는 Subtract다. 원래 값이 항상 더 크므로 포화가 일어나지 않는다.
- `Sub*`는 실제로 0 에서 멈춘 Subtract다.
- 결과 값은 두 판이 모두 같았다. 다른 곳만 칸을 나눠 적었다.

### 2.1 변수·연산자

| 경로 | 0.76.14 | 0.81.0 | 내는 액션(실측) | 의미 | 근거 |
|---|---|---|---|---|---|
| `EUDVariable -= 상수` (`a--`, `a -= 5`) | FFFFFFFE | 같음 | `Add−5` 1개 | **wrap** | E76 eudv.py:307-309 / E81 eudv.py:250-252 (`int`만. 다른 ConstExpr는 아래 변수 경로로 간다) |
| `EUDVariable -= 변수` | FFFFFFFE | 같음 | `self+=1`, `addor=~0`, `addor Sub other`(~), `self+=addor` | **wrap** | E76 eudv.py:310-323 / E81 eudv.py:253-263, evcommon.py:15 |
| `v -= v` (같은 변수) | **FFFFFFFF** | **FFFFFFFF** | 위와 같다. self가 먼저 +1 된 뒤 `~self`를 더해 −1이 된다 | **버그**(0이어야 함) | 같은 줄. X 사례 3 |
| `v - v` (lvalue 같은 변수) | 0 | 0 | `t=~0; t Sub v(~); t+=1; t+=v` | wrap(정상) | X 사례 4 |
| `a - b` (둘 다 lvalue) | FFFFFFFE | 같음 | `t=~0; t Sub b(~); t+=1; t+=a` | **wrap** | E76 eudv.py:343-375 / E81 eudv.py:286-325 |
| `a - 5` | FFFFFFFE | 같음 | `t=−5`(SetTo 음수) → `t+=a` | **wrap** | 같은 줄 |
| `3 - b` (`__rsub__`) | FFFFFFFE | 같음 | `t=~0; t Sub b(~); t+=4` | **wrap** | E76 eudv.py:377-405 / E81 eudv.py:327-357 |
| 임시값이 끼는 `x - b`, `a - y`, `-(v+0)` | FFFFFFFE / FFFFFFFB | 같음 | 0.76은 참조 수로 임시값을 판정한다(`E76 eudv.py:71-76`). 실험에서는 판정이 거짓이 되어 lvalue 경로를 탔다. 0.81은 `_is_rvalue`가 늘 False라 이 경로가 죽어 있다(`E81 eudv.py:57-58`) | **wrap** | 원래 경로는 `AddX(−1, 0x55555555)`·`AddX(−1, 0xAAAAAAAA)`·`+1` 부호 반전이다(E76 eudv.py:344-355) |
| 단항 `-v` | FFFFFFFB | 같음 | `0 - v` → `__rsub__` | **wrap** | E76 eudv.py:407-410 / E81 eudv.py:359-362 |
| `~v` | FFFFFFFA | 같음 | `t=~0; t Sub v`(~) | 비트 반전 | E76 eudv.py:412-417 / E81 eudv.py:364-369 |
| `v.ineg()` | FFFFFFFB | 같음 | `AddX(−1,0x55555555)`, `AddX(−1,0xAAAAAAAA)`, `Add 1` | **wrap**(마스크 Add에 의존) | E76 vbase.py:122-133 / E81 vbase.py:137-148 |
| `v.iabs()` (v=−5) | 5 | 같음 | 조건 `v ≥ 0x80000000` + ineg | wrap 부호 반전 | E76 vbase.py:135-140 / E81 vbase.py:150-155 |
| `EUDXVariable -= 5` | FFFFFFFE | 같음 | `Add−5` (EUDVariable 상속) | **wrap** | E76 eudxv.py:14 / E81 eudxv.py:35 |
| `v -= xv` (xv 마스크 0xFF, 값 0x1205) | FFFFFFFE | 같음 | `addor SubX(0x1205, m=FF)` (~) | wrap. **xv의 마스크가 적용**되어 `v − (xv & 0xFF)` | X 사례 27 |
| 비교 `a < b`, `a > b` (변수끼리) | 0.76: `AtMost(b−1)` 버그 | 0.81: `bitmask = b ⊖ a` 뒤 조건이 자기 첫 칸을 읽는다 | 포화 Sub **의도적 사용** | 포화에 기대어 비교 | E76 eudv.py:617-647 / E81 eudv.py:589-621, CL:302 |

### 2.2 VariableBase 액션 메서드·EUDLightVariable

| 경로 | 0.76.14 | 0.81.0 | 내는 액션(실측) | 의미 | 근거 |
|---|---|---|---|---|---|
| `DoActions(v.SubtractNumber(5))` | 0 | 0 | `Sub*` 1개 | **포화** | E76 vbase.py:48-49 / E81 vbase.py:51-52 |
| `v.SubtractNumberX(5, 0xFF)` (v=0x1203) | 1200 | 1200 | `SubX*` (필드 3 < 5) | **마스크 안 포화**(에뮬레이터 가정) → 인게임 S1 | E76 vbase.py:70-71 / E81 vbase.py:73-74 |
| `v.AddNumberX(−5, 0xFF)` (0x1203) | 12FE | 12FE | `AddX` | 바이트 안 wrap(모형 M) | 인게임 X1·X2 |
| `EUDLightVariable -= 5` | **0** | **0** | `Sub*` 1개 | **포화 ← 유일한 연산자 예외** | E76 vbase.py:85-87 / E81 vbase.py:89-91 |
| `EUDLightVariable -= 변수` | 컴파일 오류 | 컴파일 오류 | RawTrigger에 변수 amount | — | "invalid amount" (X 사례 22) |
| `EUDLightVariable.ineg()` | FFFFFFFB | 같음 | AddX 2 + Add | wrap | vbase 같은 줄 |
| `EUDLightVariable >>= n` | 정답 | 정답 | `SubX` 31번. 그중 29번이 필드 0에서 0으로 멈춤 | 마스크 Subtract 포화 **기법** | E76 vbase.py:152-159 / E81 vbase.py:167-174 (W1 "Shift right Method 2") |
| `EUDLightBool` | 뺄셈 없음 | 같음 | `Set/Clear/Toggle`만 | — | E76 eudlv.py:29-62 / E81 eudlv.py:30-75 |

### 2.3 SeqCompute·SetVariables

| 경로 | 0.76.14 | 0.81.0 | 내는 액션(실측) | 의미 | 근거 |
|---|---|---|---|---|---|
| `SeqCompute([(v, Subtract, 5)])` | 0 | 0 | `SetDeaths(dst, Subtract, 5)` 그대로 = `Sub*` | **포화** | E76 eudv.py:755 / E81 eudv.py:723 |
| `SeqCompute([(v, Subtract, w)])` | 0 | 0 | w의 변수 트리거가 수정자 Subtract로 실행된다 = `Sub*` | **포화** | E76 eudv.py:809 / E81 eudv.py:781 |
| `SetVariables([v],[w],[Subtract])` | 0 | 0 | 같음 | **포화** | E76 eudv.py:926 / E81 eudv.py:896 |
| `NonSeqCompute([(v, Subtract, w)])` | 0 | 0 | 같음 | **포화** | E76 eudv.py:885 / E81 eudv.py:855 |
| `SeqCompute([(v, Add, −5)])` | FFFFFFFE | 같음 | `Add−5` | **wrap** | 같은 곳 |
| `EUDVariable.QueueSubtractTo(dest)` | — | — | 변수 트리거 수정자 ← Subtract | **포화** | E76 eudv.py:290-291 / E81 eudv.py:233-234 |
| `SubtractDest(X)`, `SubtractMask(X)` | — | — | 변수 트리거의 dest·mask 칸에 Subtract | 포화(내부용) | E76 eudv.py:208-270 / E81 eudv.py:151-213 |

### 2.4 메모리 함수

| 경로 | 0.76.14 | 0.81.0 | 내는 액션(실측) | 의미 | 근거 |
|---|---|---|---|---|---|
| `f_dwsubtract_epd(epd, 5 또는 w)` | 0 | 0 | `Sub*` | **포화** | E76 memiof/dwepdio.py:163-164 / E81 memio/dwepdio.py:143-144 |
| `f_dwadd_epd(epd, −5)` | FFFFFFFE | 같음 | `Add−5` | **wrap** | E76 dwepdio.py:159 / E81 dwepdio.py:139 |
| `f_dwsubtract_cp(0, 5 또는 w)` | 0 | 0 | `Sub*` (w면 QueueSubtractTo) | **포화** | E76 memiof/cpmemio.py:153-161 / E81 memio/cpmemio.py:168-179 |
| `f_wsubtract_epd(epd, 1, 5 또는 w)` (0x11000322) | 11000022 | 같음 | `SubX*`(m=0xFFFF00) | **워드 안 포화**(에뮬레이터 가정) | E76 memiof/bwepdio.py:96-126 / E81 memio/bwepdio.py:93-121 |
| `f_bsubtract_epd(epd, 2, 5 또는 w)` (0x11030322) | 11000322 | 같음 | `SubX*`(m=0xFF0000) | **바이트 안 포화**(가정) | E76 bwepdio.py:190-214 / E81 bwepdio.py:232-253 |
| `f_badd_epd(epd, 2, −5)`, `f_wadd_epd(epd, 1, −5)` | 11FE0322 / 11FFFE22 | 같음 | `AddX` (값 = −5 ≪ 8·subp) | **필드 안 wrap**(모형 M) | E81 bwepdio.py:21-27(`_lshift`), 222-229 |
| `SetMemory/SetDeaths/SetMemoryEPD(…, Subtract, k)` | — | — | Subtract 그대로 | **포화** | E81 rawtrigger/stockact.py:677-687, 860-868 |
| `SetMemoryX/SetDeathsX/SetMemoryXEPD(…, Subtract, k, m)` | — | — | eudx=`0x4353`, 마스크는 첫 4바이트 | **마스크 포화**(세부는 3절) | E81 stockact.py:875-896 |
| 음수 상수를 넣을 때 (`Add, −5`) | — | — | eudplib은 **Add를 그대로 두고** 값만 2의 보수로 넣는다. 수정자를 바꾸는 코드는 없다. 실측 바이트 = 0xFFFFFFFB | wrap | X 사례 1·32·35 (`Add−` 판정은 바이트 값) |

### 2.5 배열·구조체·scdata

| 경로 | 0.76.14 | 0.81.0 | 내는 액션(실측) | 의미 | 근거 |
|---|---|---|---|---|---|
| `EUDArray.isubitem(i, v)` = epScript `arr[i] -= v` | FFFFFFFE | 같음 | 상수: `iset(Add, −v)` / 변수: 칸 부호 반전(AddX 2 + Add) → `+v` → 다시 반전 | **wrap** | E76 eudlib/eudarray.py:131-133, core/inplacecw.py:99-118 / E81 collections/eudarray.py:206-208, core/inplacecw.py:100-119 |
| `EUDArray.isubtractitem(i, v)` | 0 | 0 | `Sub*` | **포화** (주석 "FIXME: add operator for f_dwsubtract_epd") | E76 eudarray.py:126-129 / E81 eudarray.py:201-204 |
| 파이썬 `t = arr[i]; t -= 5; arr[i] = t` | FFFFFFFE | 같음 | 읽기 + `Add−` + 쓰기 | wrap | — |
| `EUDArray.irshiftitem(i, n)` | 정답 | 정답 | `SubX` 30번(28번 필드 0) | 마스크 포화 기법 | E76 inplacecw.py:297-310 / E81 inplacecw.py:298-311 |
| `EUDVArray` 원소 `-=` (epScript `va[i] -= v`) | `isubitem` 있음: `_set(i, Add, −v)` / 반전 기법 | **공개 `EUDVArray`에 `isubitem`이 없다.** `_ARRW`가 AttributeError를 받아 읽기·`-=`·쓰기로 대신한다 | wrap | **wrap**(두 판 모두) | E76 core/eudstruct/vararray.py:383-437 / E81 vararray.py:110-345(`_EUDVArray`: get·set만), epscript/helper.py:337-344 |
| `EUDVArray.isubtractitem` | 0 (포화) | **없음** | `Sub*` | 0.76만 포화 API | E76 vararray.py:378-381 / E81 내부 `_InternalVArray`에만(vararray.py:732-734) |
| `PVariable[i] -= v` | (EUDVArray) | `_EUDVArray` 상속 → 대체 경로 | | **wrap** | E81 collections/playerv.py:11 |
| `EUDStruct.isubattr` = epScript `s.f -= v` | FFFFFFFE | 같음 | `Add−` / 반전 기법 | **wrap** | E76 core/eudstruct/eudstruct.py:151-153 / E81 eudstruct.py:195-200 |
| `EUDStruct.isubtractattr` | 0 | 0 | `Sub*` | **포화** | E76 eudstruct.py:146-149 / E81 eudstruct.py:187-193 |
| scdata 멤버 `u.maxHp -= v` (dword) | 없음 | FFFFFFFB | `kind.add_epd(−v)` → `f_dwadd_epd(Add−)`. 변수면 `-v`(wrap 반전) 후 Add | **wrap** | E81 scdata/offsetmap/epdoffsetmap.py:239-243 |
| scdata 멤버 `u.armor -= v` (바이트) | 없음 | FB | `f_badd_epd(−v)` → `AddX` | **바이트 안 wrap** | E81 memberkind.py:72-75 |
| scdata `isubtractattr` | 없음 | 0 | `f_bsubtract_epd` → `SubX*` | **포화** (주석 "TODO: add operator for Subtract") | E81 epdoffsetmap.py:233-237, memberkind.py:78-81, 489-492 |
| `var u: TrgUnit; u -= 5`, `TrgPlayer` 값 `-=` | 없음 | FFFFFFFE (같은 객체 유지) | `ConstType.__isub__` → `_value.__isub__` | **wrap** | E81 core/rawtrigger/consttype.py:74-77, scdata/unit.py:126 |
| CUnit 멤버 `cu.hitPoints -= 256` | `_ATTW` → `isubattr` (0.76 CUnit) | scdata 규칙 | | wrap(0.81 소스 기준) | X eps 번역 `cunit` |

### 2.6 라이브러리 안의 Subtract 쓰임 (포화가 문제가 안 되는 곳)

| 종류 | 예 | 근거 |
|---|---|---|
| `0xFFFFFFFF − x` (반전, 포화 불가) | `-`, `__rsub__`, `~`, `&=`(변수), 로케이션 signed 경로 | E81 eudv.py:317-321, 383-393 / eudlib/locf/locf.py:30-47 |
| 앞 조건으로 보호됨 (`AtLeast(k)`이면 `Subtract k`) | `f_div`류, 상수 나눗셈, `EUDLoopN` 카운터, `f_lengthdir` 사분면, 이진 탐색 | E81 core/calcf/muldiv.py:286-291, 402-406, 488-493 / ctrlstru/loopblock.py:72-76 / eudlib/mathf/lengthdir.py:44-52 / eudlib/utilf/binsearch.py:43-89 |
| 포화를 **일부러** 씀 | 0.81 `<`·`>`, 0.76 `<=`·`>=` 대체 경로, 시프트 | 2.1·2.2 |

### 2.7 0.76.14 → 0.81.0 변경

| 항목 | 내용 | 근거 |
|---|---|---|
| 뺄셈 의미 | **바뀐 것 없다.** 2.1~2.5의 결과 값이 두 판에서 모두 같다(scdata 등 새 경로 제외) | X 두 결과 파일 |
| 변수끼리 `<`, `>` | 포화 Subtract 기법으로 고쳤다 (euddraft 0.10.0.0) | CL:302, E81 eudv.py:589-621 |
| epScript 타입 변수 | 값 타입은 `-=`를 지원한다. 참조 타입(`EUDArray` 등)은 `-=`를 막는다 (0.10.0.0) | CL:218-219 |
| `_is_rvalue` | 늘 False → 임시값 최적화 경로(VProc 반전)가 쓰이지 않는다 | E81 eudv.py:57-58 |
| 공개 `EUDVArray` 재작성 | `isubitem`·`isubtractitem`이 빠졌다 → `va[i] -=`는 대체 경로(wrap)로 가고, 포화 API는 없어졌다 | E81 vararray.py:110-345, 396-417 |
| scdata 추가 | 멤버 `-=`는 wrap, `isubtractattr`는 포화 | 2.5 |
| 더 오래된 이력 | `ineg`/`iabs` 추가(0.9.9.9, CL:847-851), `f_w/badd·subtract_epd` 추가(0.9.8.3, CL:1183), `PVariable[var] -= value` 수정(0.9.7.10, CL:1257), `SubtractNumberX` 추가(0.8.3.1, CL:3165) | CL |

---

## 3. SC 액션·마스크 의미와 근거 수준

| 항목 | 식 | 근거 | 수준 |
|---|---|---|---|
| 마스크 없는 Subtract | `max(0, d − v)` (**부호 없는** 비교) | W1:4 "Deaths subtraction is unsigned. If the result … below 0, then it is set to 0" / W2:4405-4410(`10 − 200000 → 0`), W2:7880 / CA:21850 주석 "(1 - 2 = 0)" / eudplib이 `-=`에서 Subtract를 피하고(E81 eudv.py:250-263) 0.81 비교가 포화에 기댄다(E81 eudv.py:589-621) | **확실**(여러 독립 근거와 라이브러리 의존). 인게임 P1·P2·F1로 한 번 더 본다 |
| Add에 음수 | `(d + v) mod 2^32` | W2:4397-4403 / 실측 바이트 | **확실** |
| 마스크 SetTo | `(d & ~m) \| (v & m)` | W2:1450, 1476 / 널리 쓰임 | 확실 |
| 마스크 Add | 모형 M: `(d & ~m) \| (((d&m) + (v&m)) & m)` | W2:1451, 1477 식이 같다 / eudplib `ineg`·`iinvert`·`^=`·`inplacecw.isub`가 `AddX(0xFFFFFFFF, 0x55555555)` 기법에 기댄다. 이 기법이 맞으려면 **v를 마스크하고**, **올림을 마스크 밖으로 내보내지 않고**, **d의 마스크 밖 비트를 더하지 않아야** 한다(d=4일 때 v를 마스크하지 않으면 0x55555551이 아니라 0x1이 된다. 직접 계산). 이 기법은 `-x`처럼 흔한 경로에 들어 있다 | **높음**. 인게임 X1~X3로 확정 |
| 마스크 Subtract | 후보 A: `(d & ~m) \| max(0, (d&m) − (v&m))` (G2:104) / 후보 A2: 위 식에 `& m`을 더함 (W2:1452, 1478 "the subtraction … can subtract to a minimum of 0", arith:87-103) | W1:129-136 "Abuse the property of never dipping below zero in subtraction" (오른쪽 시프트) / eudplib `>>=`(E81 vbase.py:167-174, inplacecw.py:298-311, vararray.py:908-929) / CtrigAsm CrShift·CEPD(CA:99122-99150, 98944-98976) / LF:983, 986 타이머 | **중간**. 아래 참고 |
| 마스크 조건 | `(d & m)` 과 비교 | W2:846, 871 | 확실 |

**마스크 Subtract에서 확인된 것과 확인되지 않은 것**

- **확인됨:** 시프트 기법(eudplib·CtrigAsm·llvm-bw)이 맞으려면 다음 두 가지가 필요하다.
  1. **필드 값이 0이고 빼는 값이 더 크면 필드가 0으로 남는다.** 마스크 안 wrap(모형 C)이나 전체 값에서 빌림(모형 B, Bw)은 배제된다.
  2. **마스크 밖 비트는 그대로다.**

  시프트 기법에서 필드 값은 늘 0이거나 정확히 `1 ≪ n`이다. 그래서 이 사용례들로는 모형 A, A2, Av, D를 가를 수 없다.
- **확인되지 않음:**
  - 필드 값이 0이 아닌데 모자랄 때, 0이 되는지(A 계열) 아니면 그대로인지(D)
  - v에 마스크 밖 비트가 있을 때 v를 마스크하는지(A/A2 대 Av)
  - 떨어진 마스크(예: 0x0F0F)에서 결과를 다시 마스크하는지(A 대 A2)

  `f_bsubtract_epd`/`f_wsubtract_epd`, CtrigAsm `SubVX`·3인자 `CSub`는 이 경계들에 기대지만, 인게임으로 검증했다는 기록은 찾지 못했다(추측: 검증하지 않았다).
- **원본 코드:** Blizzard SC:R 구현을 역공학한 자료는 찾지 못했다. W2는 식만 적었다. W1은 2020년 설계 문서다.
- → 8절 인게임 시험 S1~S5로 확정한다. 확정 전까지 eudext는 **마스크 Subtract를 "필드가 0이면 0으로 남는다"는 용도(시프트)로만** 쓰고, 부분 필드 포화 API(`isub_sat` 필드판)는 인게임 결과가 나온 뒤에 연다.

---

## 4. CtrigAsm 뺄셈 함수 표

TEP 수정자 번호는 `SetTo=7, Add=8, Subtract=9`다(CA:29-31). 변수 V는 `SetDeathsX(…, 0xFFFFFFFF)` 액션 하나로 된 트리거다(CA:5860). 변수가 피연산자면 그 액션의 수정자 바이트(+0x160)를 Subtract로 바꿔 호출한다. 그래서 이 경우는 "전체 마스크 Subtract"가 된다.

| 함수 | 형태 | 내는 액션 | 의미 | 근거 |
|---|---|---|---|---|
| `CSub` 2인자 (Dest 숫자/Cp/V/Mem, 상수) | `CSub(P, Dest, c)` | `SetMemory/SetDeaths(CP)/SetCtrig1X(…, Subtract, c)` | **포화** | CA:21850(주석 "1 - 2 = 0"), 21884-21888, 21916, 21946, 21976 |
| `CSub` 2인자, 변수 피연산자 | | 피연산자 V를 마스크 0xFFFFFFFF + Subtract로 호출 | **포화** | CA:21897-21900 등 |
| `CSub` 3인자 (`Dest ← S − O`, Mask) | | `Dest ← S`(SetTo, Mask) 뒤 `Subtract O`(Mask) | **포화**(Mask가 부분이면 마스크 Subtract) | CA:22055-22095 |
| `CiSub` 2인자 상수 | | `Add, 0 − c` | **wrap** | CA:22121(주석 "1 - 2 = -1"), 22155-22158, 22202, 22247, 22292 |
| `CiSub` 2인자 변수 | | `CRet ← 0xFFFFFFFF` → `Subtract O`(~) → `+1` → Dest에 Add | **wrap** | CA:22166-22186 |
| `CiSub` 3인자 | | `Dest ← S`(Mask) → `Add −O`(Mask) | wrap(마스크 Add) | CA:22386-22438 |
| `CNeg` | | `0xFFFFFFFF − X` → `+1` → SetTo | wrap | CA:22497-22575 |
| `_Sub` / `_iSub` / `_Neg` (임시식) | | 각각 CSub / CiSub / CNeg 3인자 | 포화 / wrap / wrap | CA:41850-41960 |
| `V` 메타테이블 `a - b` | `__sub = _Sub` | CSub | **포화**. `5 - v`(숫자가 왼쪽)는 오류 | LF:17, CA:41860 |
| `V` 단항 `-v` | `__unm = _Neg` | CNeg | wrap | LF:20 |
| `SubCD(Code, v)` | | `SetCDeaths/TSetCDeaths(FP, Subtract, …)` | **포화** | LF:596-605 |
| `SubV(V, v)` | | `SetCVar/TSetCVar(FP, …, Subtract, v)` (전체 마스크) | **포화** | LF:636-645, CA:7315-7317 |
| `SubVX(V, v, Mask)` | | 부분 마스크 Subtract | 마스크 안 포화(3절 미확인) | LF:668-677 |
| T 액션 `TSetMemoryX/TSetDeathsX/TSetCVar(…, Subtract, 변수)` | | 값 칸을 채운 뒤 Subtract 액션 | 포화(Mask가 있으면 마스크 Subtract) | CA:13550-13554, 13626-13636 |
| `MoveCp(Subtract, v)` | | `SetMemory(0x6509B0, Add, (0−v)/4)` | wrap | CA:5600-5603, GB:1321 |
| `SetNWar(W, Subtract, "…" 또는 {lo,hi})` | 64비트 T 액션 | 반쪽마다 따로 Subtract | **반쪽별 포화**(64비트 포화가 아니다) | G1:268-273 |
| `f_LSub` / `_LSub` | 64비트 | 2절 알고리즘(아래) | **64비트 전체 포화** `S ≥ O ? S − O : 0` | CA:66883, 72945-73055, G3:22, 131 |
| `f_LiSub` / `_LiSub` | 64비트 | `−O`(2의 보수)를 만든 뒤 f_LAdd와 같은 올림 처리 | **64비트 wrap** | CA:67760, 72829-72896, G3:132 |
| `f_LNeg` / `_LNeg` | 64비트 | `~S`, lo가 0xFFFFFFFF면 hi+1, lo+1 | wrap | CA:67398, 72898-72943 |
| `CNeg2` | | AddX 0x55555555/0xAAAAAAAA + Add 1 | wrap | CA:100233-100247 |
| `CrShift` / `CEPD` | 시프트 | `SetMemoryX(D, SetTo, 0, CBit)` + `Subtract CBit, 마스크 NBit`를 32−n번 | 마스크 포화 **기법** | CA:99122-99150, 98944-98976 |
| (없음) | `CSubX`, `SubCDX`, 이름에 `*Subtract*`가 든 도우미 | — | — | 검색 결과 없음 |

**f_LSub 본체 (직접 확인, CA:72945-73055)**

- **입력:** `WRet[2] = S`, `WRet[3] = O`. 결과는 `WRet[2]`에 남는다.
- **T0:** O.hi를 T(FA+3) 조건값에, O.lo를 T(FA+4) 조건값에 복사한다.
- **T(FA+3)** `S.hi ≥ O.hi`: 거짓이면 T(FA+7)로 가서 결과를 0으로 만든다.
- **T(FA+4)** `S.lo ≥ O.lo`: 참이면 두 반쪽을 Subtract하고 끝낸다(빌림 없음, 포화도 일어나지 않음).
- **T(FA+5)** 빌림이 있는 경우:
  - `CRet = 0xFFFFFFFF − O.lo`
  - `S.hi −= O.hi` (S.hi ≥ O.hi이므로 정확함)
- **T(FA+1)** `S.hi == 0`이면 결과를 0으로 만든다(hi가 같고 lo가 작은 경우).
- **T(FA+6):**
  - `S.hi −= 1`
  - `S.lo += 1 + CRet` (= `S.lo − O.lo` wrap)
- **예:** S = 2^32, O = 1이면 결과는 `0x00000000_FFFFFFFF`다. **반쪽별 포화가 아니다.**
- **실행 트리거 수**(호출·저장 제외, 코드를 세어 얻음): hi가 작으면 4, 빌림이 없으면 5, hi가 같고 lo가 작으면 7, 빌림이 있으면 9.
- **war.py 대응:** `_subsat64_inline`(war:420-433)이 같은 의미이고, 머리 주석은 "f_LSub 부호 없는 포화 (S < O → 0)"(war:4-7)이다.

**가이드북 (GB)**
- "0에서 멈춘다"는 직접적인 문장은 없다.
- CSub는 "(순환을 사용하지 않음)"(GB:1847), CiSub는 "(순환을 사용함)"(GB:1872)이다.
- `_Sub`는 "(순환X)", `_iSub`는 "(순환O)"다(GB:2626, 2631).
- 예시 "2 - 1 = 0 / −1"(GB:1860, 1884)은 "1 − 2"의 오타로 보인다(코드 주석 CA:21850, 22121).
- f_LSub 설명은 "Dest << Source - Operand"(GB:5489)뿐이고 포화 언급이 없다.

---

## 5. epScript 번역 표

두 판 모두 `epsCompile`로 번역했다(`X:eps_s8.py`, 결과는 `X:eps_s8_0.76.14.txt`와 `X:eps_s8_0.81.0.txt`). 0.81.0 결과는 euddraft 0.11.0.1 번들로 얻었다.

| epScript | 0.76.14 번역 | 0.81.0 번역 | 결과 의미 |
|---|---|---|---|
| `a -= b;` / `a -= 5;` | `a.__isub__(b)` / `a.__isub__(5)` | 같음 | var(EUDVariable)이면 **wrap** |
| `a--;` / `--a;` | `a.__isub__(1)` | 같음 | **wrap** |
| `const z = a--;` | 문법 오류 | 문법 오류 | — |
| `a = a - b;` | `a << (a - b)` | 같음 | wrap |
| `const z = a - b; var w = 5 - a;` | `z = a - b`, `w = _LVAR([5 - a])` | `w = _TYLV([None], [5 - a])` | wrap |
| `a = -a;` | `a << (-a)` | 같음 | wrap |
| 전역 `var g; g -= b; g--;` | `g.__isub__(b)`, `g.__isub__(1)` | 같음 | wrap |
| `static var s = 3; s -= b;` | `s = EUDVariable(3)`, `s.__isub__(b)` | `s = _TYSV([None],[3])` | wrap |
| `for (…; i--)` | `i.__isub__(1)` | 같음 | wrap |
| `p.x -= b; p.x--;` (object) | `_ATTW(p,'x').__isub__(b)` → `isubattr` | 같음 | wrap (2.5) |
| `arr[i] -= b; arr[i]--;` | `_ARRW(arr,i).__isub__(b)` → `isubitem` | 같음 | wrap |
| `va[i] -= b;` (EUDVArray) | `_ARRW` → `isubitem` | `_ARRW` → 대체 경로(읽기·`-=`·쓰기) | wrap |
| `foo.x -= b;` (모듈 변수) | `_ATTW(foo,'x').__isub__(b)` | 같음 | 모듈 객체라 AttributeError → `ov -= b` → EUDVariable이면 wrap |
| `var u: TrgUnit = 3; u -= 1; u.maxHp -= b; u.armor--;` | 문법 오류(타입 변수 없음) | `u.__isub__(1)`, `_ATTW(u,'maxHp').__isub__(b)`, `_ATTW(u,'armor').__isub__(1)` | wrap (2.5) |
| `cu.hitPoints -= 256;` | `_ATTW(cu,'hitPoints').__isub__(256)` | 같음 | wrap(0.81) |
| `const lv = EUDLightVariable(); lv -= 1; lv--;` | **컴파일 오류** "Undefined variable lv_1" | 같음 | const에 묶인 이름에는 `-=`를 못 쓴다 |
| `lv.__isub__(1); DoActions(lv.SubtractNumber(1));` | (0.76에서는 시험하지 않음) | 그대로 번역 | 둘 다 **포화** |
| `const cv = EUDVariable(); cv -= 1;` | (시험하지 않음) | 컴파일 오류 | 위와 같음 |
| `DoActions(a.SubtractNumber(1));` | 그대로 | 같음 | **포화** |
| `dwsubtract_epd(e, 1);` | `f_dwsubtract_epd(e, 1)` | 같음 | **포화** |
| `SetMemory(0x58A364, Subtract, 1);` | `DoActions(SetMemory(…, Subtract, 1))` | 같음 | **포화** |
| `x.v -= b; x.v--;` (const 값 타입) | `_ATTW(x,'v').__isub__(b)` → `x.isubattr('v', b)` | 같음 | eudext가 정한다(→ wrap) |
| `const A = EUDArray(1); A -= b;` | 오류 "Undefined variable A_1" | 같음 | — |

epScript에서 **포화를 쓰는 방법은 이름 있는 호출뿐**이다(`SubtractNumber`, `dwsubtract_epd`, `SeqCompute`, 모듈 함수). 연산자는 var에 대해 늘 wrap이다. 모듈 함수 `m.foo()`는 `m.f_foo()`로 번역되지만, const 객체의 메서드 `x.foo()`는 이름이 바뀌지 않는다(R3 2.2, `docs\proto\eps_probe_out.txt:500-511`).

---

## 6. 64비트 뺄셈 설계 (알고리즘·비용)

### 6.1 의미

| 이름 | 식 | CtrigAsm 대응 |
|---|---|---|
| wrap | `(a − b) mod 2^64` | f_LiSub, f_LNeg(`0 − a`) |
| 포화 (부호 없음) | `a ≥ b ? a − b : 0`, **64비트 전체 기준** | f_LSub |
| 반쪽별 포화 | `(max(0, ah−bh), max(0, al−bl))` | SetNWar(Subtract). **제공하지 않는다.** 예: 2^32 − 1이 2^32가 되어 틀린다 |
| 부호 있는 포화 (선택) | `clamp(a − b, −2^63, 2^63−1)` | 없음(G3 1.5에도 없음) |

게임 값(체력·자원·쿨타임)은 음수를 쓰지 않으므로 **부호 없는 포화**로 충분하다. "부호 있는 값인데 0 아래로만 막는 뺄셈"(`max(0, s64(a) − s64(b))`)은 위 두 포화와 또 다른 연산이다. 요청이 있을 때만 만든다(추측: 쓰임이 없다).

### 6.2 알고리즘 (검증 완료)

- **검증 방법:** 경계값 24개끼리의 모든 쌍에 무작위 1,500쌍을 더한 **2,076쌍** × 후보 전부를 에뮬레이터로 돌렸다(`X:s8_i64sub.py`, 결과는 `X:s8_i64sub_result.txt`).
- **결과:** 아래 알고리즘은 모두 통과했다. 실패는 "WVa로 `x -= x`" 하나였다(eudplib `v -= v` 버그 때문).
- **기호:** `⊖`는 SC Subtract(포화), `~y`는 `0xFFFFFFFF ⊖ y`(포화가 일어나지 않음)다.

**WK — 상수 wrap** `x −= K` (K = kh:kl)
```
kl≠0 : T1 [x.lo ≤ kl−1]  → x.hi += −1          # 빌림
       T2                → x.lo += −kl, x.hi += −kh
```

**SK — 상수 포화** `x = max(x − K, 0)`. 분기가 없고, 액션은 모두 상수다.
```
kl≠0 : T1 [x.hi ≤ kh, x.lo ≤ kl−1] → x.hi = 0, x.lo = kl   # x < K (hi가 같거나 작고 빌림): 뒤 단계가 0을 만들게 맞춘다
kh≠0 : T2 [x.hi ≤ kh−1]            → x.hi = 0, x.lo = kl   # hi가 작음
kl≠0 : T3 [x.lo ≤ kl−1]            → x.hi ⊖ 1              # 여기까지 오면 hi > kh라 정확한 뺄셈
       T4                          → x.lo += −kl, x.hi ⊖ kh # hi ≥ kh이거나 0. 0 에서 멈추는 것이 곧 정답
```

**WVb — 변수 wrap** `x −= y` (인라인, 같은 객체끼리여도 안전)
```
SeqCompute: t = y.lo ⊖ x.lo      # t>0 ⇔ 빌림 (x.lo를 바꾸기 전에)
            n = ~y.lo, m = ~y.hi
            x.lo += n, x.hi += m
T1          → x.lo += 1, x.hi += 1   # x + ~y + 1 = x − y (반쪽마다)
T2 [t ≥ 1]  → x.hi += −1
```
WVa는 `x.lo -= y.lo; x.hi -= y.hi`(eudplib 연산자)를 쓰는 판이다. 비용은 같다. 그러나 `x -= x`에서 eudplib 버그를 물려받으므로 **쓰지 않는다**.

**SVa — 변수 포화** `x = sat(x − y)` (인라인, 분기 없음, 같은 객체끼리여도 안전)
```
SeqCompute: t1 = y.lo ⊖ x.lo     # 빌림
            t2 = y.hi ⊖ x.hi     # x.hi < y.hi
            n = ~y.lo, x.lo += n
            x.hi ⊖= y.hi          # 반쪽 포화 (x.hi ≤ y.hi면 0)
T1                   → x.lo += 1            # x.lo = x.lo − y.lo (wrap)
T2 [t1 ≥ 1, x.hi==0] → x.lo = 0             # hi가 같고 빌림 → 0
T3 [t2 ≥ 1]          → x.lo = 0             # hi가 작음 → 0 (x.hi는 이미 0)
T4 [t1 ≥ 1]          → x.hi ⊖ 1             # 빌림. x.hi가 0이면 0 유지(이미 0 결과)
```

**SVf — SVa의 EUDFunc 판.** 인자가 사본이므로 `alo -= blo`를 써도 별칭 문제가 없다.

**SS — 부호 있는 포화.**
1. 부호 비트를 담은 `x.hi`, `y.hi`를 먼저 복사한다.
2. WV로 뺀다.
3. `x ≥ 0, y < 0, r < 0`이면 `0x7FFF…FFFF`로 둔다.
4. `x < 0, y ≥ 0, r ≥ 0`이면 `0x8000…0000`으로 둔다.

조건은 모두 `AtLeast(0x80000000)`/`AtMost(0x7FFFFFFF)`다.

### 6.3 비용 (0.76.14 에뮬레이터 실측)

- **생성:** 호출 자리에서 새로 생긴 트리거 수다(첫 호출이면 함수 본문 포함).
- **실행:** 한 번 연산할 때 실행된 트리거 수다. 변수 트리거 실행도 1로 셌다.
- 입력 복사 1개(실행 3)는 뺀 값이다.

| 후보 | 생성 | 실행 | 비고 |
|---|---|---|---|
| WK 상수 wrap | 1~2 | 1~2 | kl=0이면 1 |
| SK 상수 포화 | 2~4 | 2~4 | kl=0이면 2, kh=0이면 3, 둘 다 0이 아니면 4 |
| WVb 변수 wrap 인라인 | 6 | 12 | |
| WVf 변수 wrap EUDFunc | 본문 8 (1벌) + 호출 자리 1 | 23 | |
| SVa 변수 포화 인라인 | 7 | 14 | |
| SVf 변수 포화 EUDFunc | 본문 9 (1벌) + 호출 자리 1 | 25 | |
| SVw war.py `_subsat64_inline` 옮김 | 14 | 14~18 | 분기 있음 |
| SS 부호 있는 포화 인라인 | 9 | 17 | |
| (비교) war.py `_subsat64` EUDFunc | 본문 27 | 51 | R2 1.6·4.4 |
| (비교) war.py `_subwrap64` / `_neg64` | 본문 12 / 12 | — | R2 4.4 |
| (비교) 시제품 `_sub64` (`D << A - B`) | 11 (본문 8 포함) | — | R3 1.2 |
| (비교) CtrigAsm f_LSub / f_LiSub / f_LNeg | 본체 8 / 4 / 3 | 4~9 / 7 / 4 | 코드를 세어 얻음, 호출 제외 |

DESIGN 3.3·3.8 규칙에 맞추면 다음과 같다.
- **상수 쪽:** WK·SK를 인라인으로 쓴다. SK는 최대 4개라 "3개 이하 인라인" 기준을 1개 넘는다. 그래도 상수별 EUDFunc 호출 비용(실행 약 11)보다 싸므로 **SK는 인라인을 허용**하자고 제안한다.
- **변수끼리:** 공유 EUDFunc(WVf/SVf)가 기본이다. 호출 자리 1개라 "wrap 뺄셈 호출 자리 ≤ 3"을 만족한다. 루프 안처럼 실행 비용이 중요한 곳에는 `inline=True`로 WVb/SVa를 고를 수 있게 한다.
- **같은 객체끼리**(`x -= x`, `sub_sat(x, x)`): 컴파일 시점에 `x << 0`으로 접는다.

### 6.4 32비트 반쪽에 SC Subtract를 쓸 수 있는 곳 / 안 되는 곳

**쓸 수 있는 곳** (포화가 일어나지 않거나, 포화가 곧 원하는 값인 곳)
1. `0xFFFFFFFF ⊖ y` (비트 반전 `~y`)
2. **판정용 임시값**: `t = b ⊖ a` (t>0 ⇔ a<b). 빌림·비교·64비트 사전식 비교에 쓴다.
3. 앞 조건이나 앞 단계가 `원래 값 ≥ 빼는 값`을 보장하는 곳: SK의 T3, SVa의 T4, f_LSub의 `S.hi −= O.hi`
4. **64비트 포화의 hi 반쪽**. 0 에서 멈추는 것이 정답과 같은 경우이며, lo 보정 트리거가 함께 있어야 한다(SK T4, SVa).
5. 32비트 포화 헬퍼: `sub_sat(a, b)`, `isub_sat(v, b)`

**쓰면 안 되는 곳**
1. wrap 뺄셈의 lo 반쪽 (빌림이 생기면 0에서 멈춰 틀린다)
2. wrap 뺄셈의 hi 반쪽 (`a.hi < b.hi`일 수 있다)
3. **반쪽마다 따로 포화시켜 64비트 포화를 흉내 내기** (SetNWar 방식. 2^32 − 1에서 틀린다)
4. 부호 있는 값(음수 표현)의 뺄셈
5. 부분 마스크 Subtract로 필드 값 빼기. 인게임 결과가 나오기 전까지는 시프트 기법(필드가 0이거나 정확히 2^k)에만 쓴다.
6. 같은 EUDVariable을 양쪽에 둔 eudplib `v -= v` (Subtract 문제는 아니지만 결과가 −1이다)

---

## 7. eudext 이름 규칙 제안

### 7.1 규칙

1. **연산자는 모든 eudext 타입에서 wrap이다.** 해당하는 것은 `-`, `-=`, epScript `--`, `neg()`, `x.v -= y`, `isub()`, `isubitem()`, `isubattr()`이다. `Int64`, `Cell`, `Int64Array` 원소, 필드 뷰가 모두 같다. eudplib EUDVariable과도 같다.
2. **포화는 이름에 `_sat`를 붙인다.**
   - 32비트: `sub_sat(a, b)`(새 값), `isub_sat(v, b)`(제자리). 모듈 함수는 `f_sub_sat`/`f_isub_sat`로 정의하고 별칭을 둔다(3.1).
   - `Int64`: `x.isub_sat(y)`, `i64.sub_sat(x, y)`
   - `Cell`: `c.isub_sat(v)`
   - 배열: `arr.isub_sat(i, v)` (eudplib `isubtractitem`과 같은 뜻)
3. **이름에 `Subtract`/`subtract`가 든 것은 포화만 뜻한다.** eudplib 관례(`SubtractNumber(X)`, `f_*subtract_*`, `isubtractitem/attr`, `QueueSubtractTo`, `SeqCompute(…, Subtract, …)`)를 그대로 따르는 것이다. eudplib에서 이 규칙을 깨는 것은 `VariableBase.__isub__`(EUDLightVariable `-=`) 하나뿐이다.
   - eudext 타입은 포화 별칭으로 `isubtractitem`/`isubtractattr`를 가질 수 있다(`_ATTW`/`_ARRW` 호환).
   - `Int64.SubtractNumber(k)`는 **두지 않는다**. eudplib의 `*Number` 메서드는 `DoActions`에 넣는 **액션 하나**를 돌려주는데, 64비트 포화는 조건 트리거가 필요해 그렇게 만들 수 없다(6.2 SK). 같은 이유로 `Int64.AddNumber`도 두지 않는다.
4. **이름에 `sub`만 들고 `_sat`가 없는 것은 wrap이다.** 해당하는 것은 `sub`, `isub`, `isubitem`, `isubattr`, `f_badd_epd(−v)` 형태의 `field.isub`다. 따로 `_wrap` 접미사를 붙일 필요는 없다. 다만 문서 표에는 "wrap"이라고 적는다.
5. **CtrigAsm 이름 별칭은 원래 의미를 따른다.**
   - 포화: `SubCD`, `SubV`, `CSub`, `_Sub`, `f_LSub`
   - wrap: `CiSub`, `_iSub`, `f_LiSub`, `f_LNeg`

   `SetNWar(Subtract)`식 반쪽별 포화는 별칭으로도 만들지 않는다(호환 계층 몫).
6. **eudplib의 불일치를 막는 방법**
   - `Cell`은 `VariableBase.__isub__`를 **wrap으로 덮어쓴다**. `Cell.SubtractNumber(k)`는 eudplib 이름 그대로 포화 액션이다(규칙 3).
   - 문서에 "`EUDLightVariable -= x`는 포화, eudext `Cell -= x`는 wrap"이라는 경고를 둔다.
   - `tools/`에 날(raw) `EUDLightVariable`의 `-=`와 같은 변수끼리 `v -= v`를 찾는 검사를 두자고 제안한다(선택).
   - eudext 내부는 32비트 뺄셈을 `_parts.isub32(a, b)` 하나로 거치게 한다. 이 함수가 `a is b`면 `a << 0`으로 바꿔 eudplib 버그를 피한다.
7. **epScript에서 두 의미를 구분하는 방법**
   - wrap: `a -= b;`, `a--;`, `x.v -= b;`, `x.isub(b);`
   - 포화: `x.isub_sat(b);` (메서드는 이름이 바뀌지 않는다), `m.isub_sat(a, b);` (→ `m.f_isub_sat`, 파이썬 함수라 호출 자리에서 a를 직접 고친다), `const r = m.sub_sat(a, b);`
   - 32비트 상수 포화는 eudplib `DoActions(a.SubtractNumber(k));`를 그대로 써도 된다.
8. **마스크(필드) 뺄셈:** wrap판 `field.isub(v)`(= 마스크 Add −v)만 먼저 연다. `field.isub_sat(v)`(마스크 Subtract)는 8절 인게임 결과가 모형 A2(또는 A)로 나온 뒤에 연다.

### 7.2 DESIGN.md 수정 제안 (문장)

- **3.5 표**: "0.81 은 S8 에서 확인" 문구를 "0.76.14·0.81.0 모두 같음(S8 실측)"으로 바꾼다. 다음 행을 추가한다.
  - `SeqCompute/SetVariables/NonSeqCompute (…, Subtract, …)` → 포화
  - `f_dwsubtract_epd`/`f_dwsubtract_cp`/`f_w·bsubtract_epd` → 포화(바이트·워드는 마스크 포화)
  - `isubtractitem`/`isubtractattr` → 포화
  - `isubitem`/`isubattr`(epScript `arr[i] -=`, `s.f -=`) → wrap
  - 0.81 scdata 멤버 `-=`, `TrgUnit`·`TrgPlayer` 값 `-=`, 공개 `EUDVArray[i] -=` → wrap
  - `v -= v` → 0xFFFFFFFF(eudplib 버그)
- **3.5 잠정 규칙**: 7.1의 1~8을 "확정 규칙"으로 옮긴다. `Int64.SubtractNumber(k)`를 두겠다는 문장은 지운다(7.1-3). "변수끼리 비교에서만 포화 기법을 쓴다"는 문장은 6.4의 "쓸 수 있는 곳" 목록으로 바꾼다.
- **3.5**: "마스크 Subtract 의 세부 의미는 인게임 확인 전까지 시프트 기법에만 쓴다"와 "같은 변수끼리 `v -= v` 금지, `_parts.isub32` 경유" 두 줄을 넣는다.
- **4.3 Cell 표**: `-=` 행의 "포화 → wrap 으로 고정" 옆에 "(`VariableBase.__isub__` 덮어쓰기)"를 적는다. `c.isub(v)`/`c.v -= v`(epScript const 통로)와 `c.isub_sat(v)` 행을 추가한다. `SubCD`는 포화이고 `c.SubtractNumber(k)`도 포화 액션이라고 적는다.
- **4.4 API**:
  - `x.isub_sat(y); i64.sub_sat(x, y)` 줄의 "이름은 S8 결과로 확정"을 지운다. "**64비트 전체 포화**(f_LSub 와 같음, 반쪽별 아님)"를 덧붙인다.
  - `x.neg()`는 wrap이다.
  - `i64.ssub_sat`(부호 있는 포화)는 3단계 선택으로 추가한다.
  - `Int64Array`에 `isub_sat(i, v)`와 별칭 `isubtractitem`을 추가한다.
- **4.4 알고리즘**:
  - "sub_sat: war.py `_subsat64_inline`" 대신 "상수 = SK(분기 없음 2~4), 변수 = SVf 공유 EUDFunc(본문 9), `inline=True` 이면 SVa(생성 7·실행 14)"로 적는다.
  - wrap 뺄셈은 "상수 = WK(1~2), 변수 = WVf(본문 8), 인라인 WVb(6)"로 적는다.
  - `x -= x`는 컴파일 시점에 0으로 접는다고 적는다.
  - 시험 항목에 "같은 객체끼리"와 "2^32 − 1 빌림 경계"를 추가한다.
- **3.8 비용 표**: "Int64 덧셈·wrap 뺄셈 호출 자리 ≤ 3"은 유지한다(WVf 호출 자리 1). "Int64 포화 뺄셈: 상수 ≤ 4 인라인, 변수 호출 자리 ≤ 3, 실행 ≤ 30" 행을 추가한다.
- **7절 D3**: "결정(2026-09-17 S8): 연산자 = wrap, `_sat` 접미사 = 포화, `Subtract` 단어 = 포화(eudplib 관례), CtrigAsm 별칭 = 원래 의미"로 바꾼다. 영향 칸에 "마스크 필드 포화는 인게임 확인 뒤(S8 8절)"를 적는다.
- **0.1 핵심 결정 표 '뺄셈 의미' 행**: "S8 확정" 근거와 7.1 요약 한 줄을 넣는다.

---

## 8. 인게임 시험 방법 (`S8_ingame\`)

### 파일

| 파일 | 내용 |
|---|---|
| `S8_ingame\s8_ingame.py` | euddraft 플러그인. 첫 프레임에 시험을 한 번 실행하고, 이후 약 1초마다 결과를 한 줄씩 돌아가며 출력한다. 모형 정의와 기대값이 파일 머리 설명에 있다. `python s8_ingame.py`로 돌리면 기대값 표만 출력한다 |
| `S8_ingame\s8_ingame.eds` | 입력 `build\base.scx`, 출력 `build\S8_SubtractTest.scx` |
| `S8_ingame\build.bat` | `C:\euddraft0.9.2.0\CBTest.scx`를 `build\base.scx`로 **복사**한 뒤 euddraft 0.11.0.1로 빌드한다. `build.bat old`로 실행하면 0.9.2.0 폴더의 euddraft(eudplib 0.76.14)로 빌드한다. `C:\Program Files (x86)\StarCraft\Maps`가 있으면 그곳에도 복사한다 |

### 실행 순서

1. `S8_ingame\build.bat`을 실행한다.
2. 스타크래프트 리마스터에서 `S8_SubtractTest.scx`를 혼자 연다(사용자 지정 게임).
3. 화면에 "S8 subtract/mask test ready (19 lines)"가 뜬다. 이후 19줄이 약 1초 간격으로 반복해서 출력된다. 한 바퀴(약 19초)를 캡처하거나 옮겨 적는다.
4. 알려 줄 것은 두 줄이면 충분하다.
   - `SUBX …` 줄: 5/5인 모형이 마스크 Subtract의 답이다.
   - `ADDX …` 줄: 3/3인 모형이 마스크 Add의 답이다.

   답인 모형이 없으면 `S1~S5`, `X1~X3` 줄의 `got` 값을 알려 준다.

### 줄별 뜻

| 줄 | 액션 (d = 원래 값) | 모형별 기대값 |
|---|---|---|
| S1 | d=0x1203, `SetMemoryX(Subtract, 5, 0xFF)` | A/A2/Av = 00001200, C/B/Bw = 000012FE, D = 00001203 |
| S2 | d=0x0007, `Subtract 0x105, m=0xFF` (v에 마스크 밖 비트) | Av/B = 00000000, 나머지 = 00000002 |
| S3 | d=0x0102, `Subtract 3, m=0x0F0F` (떨어진 마스크) | A = 000000FF, 나머지 = 0000000F |
| S4 | d=0x80000001, `Subtract 2, m=6` (시프트 기법) | A/A2/Av/D = 80000001, C/B/Bw = 80000007 |
| S5 | d=0x1234, `Subtract 0x100, m=0xFF00` (대조) | 모두 00001134 |
| X1 | d=0x12FF, `Add 1, m=0xFF` | M/Mu = 00001200, Mn = 00001300 |
| X2 | d=0x00FF, `Add 1, m=0xFF00` | M/Mn = 000000FF, Mu = 000001FF |
| X3 | d=0xF0F0, `Add 0xFF00FF00` 두 번 (m=0x55555555, 0xAAAAAAAA; XOR 기법) | M = FF000FF0, Mu = 5503E5F0, Mn = FF014FF0 |
| P1 | d=3, 마스크 없는 `Subtract 5` | U/S = 0, W = FFFFFFFE |
| P2 | d=5, `Subtract 0xFFFFFFFF` | U = 0, S/W = 00000006 (부호 있는 해석이면 6) |
| P3 | d=3, `Add 0xFFFFFFFB` | W = FFFFFFFE |
| F1 | d=3, `SetMemoryX(Subtract, 5, 0xFFFFFFFF)` | U = 0 |
| E1 | eudplib `v -= v` (v=7) | emu = FFFFFFFF (버그 재현), zero = 0 |
| E2 | eudplib `f_bsubtract_epd(…, 1, 5)` (0x11000322) | A = 11000022, C = 1100FE22 |
| E3 | `EUDLightVariable(0x80000003) >>= 1` | ok = 40000001 |
| E4 | `EUDVariable 3 -= 5` | W = FFFFFFFE |
| E5 | `EUDLightVariable 3 -= 5` | U = 0 |
| SUBX / ADDX | 모형별로 맞은 수 | — |

- S1~S4의 값 조합은 모형 7개마다 모두 다르다. 그래서 SUBX 줄 하나로 답이 정해진다. X1~X3도 마찬가지다.
- 모형 식은 `s8_ingame.py`의 머리 설명과 `sub_models`/`add_models`에 있다.

### 빌드·논리 확인 (이번 작업에서 한 것)

- **빌드:** 스크래치패드 복사본(`X:ingame_build\`)으로 euddraft 0.11.0.1(chk 0.579MB)과 0.9.2.0(0.598MB)에서 모두 빌드했다. 출력은 스크래치패드에만 있다.
- **논리 확인:** `run_tests()`를 에뮬레이터로 돌렸다(`X:t_ingame_emu.py`). 에뮬레이터의 가정 모형대로 `SUBX A2=5/5`, `ADDX M=3/3`, `E1=FFFFFFFF`, `E2=11000022`, `E3=40000001`이 나왔다.
- 인게임 실행은 하지 않았다.

### 결과가 나오면

| 결과 | 조치 |
|---|---|
| A2 | 3절 표의 마스크 Subtract 행을 "확실(인게임)"으로 올리고, G2 1.3 식에 `& m`을 추가하라고 DPS에 알린다 |
| A | arith.py·emu.py의 `& m`을 뺀다 |
| D 또는 Av | `f_bsubtract_epd`·`SubVX`·3인자 `CSub`의 부분 포화 의미가 문서와 다르다. eudext `field.isub_sat`은 두 단계(판정 + SetTo)로 구현한다 |
| 공통 | 에뮬레이터(`docs\proto\emu.py`, eudext `testing` 모듈)의 모형을 결과에 맞춘다 |

---

## 9. 미확인 목록

1. **마스크 Subtract의 세부 식**(A / A2 / Av / D). 인게임 S1~S4로 확인한다. 떨어진 마스크, 마스크 밖 비트가 든 값, 모자라는 부분 필드가 대상이다. SC:R 원본 구현 자료는 찾지 못했다.
2. **마스크 Add에서 v를 마스크하는지, d의 마스크 밖 비트가 끼는지.** 라이브러리 의존으로 보아 모형 M이 거의 확실하다. 인게임 X1~X3로 확정한다.
3. **마스크 없는 Subtract가 부호 없는 비교인지.** W1이 "unsigned"라고 적었고 모든 라이브러리가 그렇게 가정한다. P2로 한 번 더 본다.
4. **`f_bsubtract_epd`·`f_wsubtract_epd`, CtrigAsm `SubVX`·`CrShift`·IBGM 타이머(LF:983)가 인게임에서 검증된 적이 있는지.** 기록을 찾지 못했다(추측: 검증하지 않았다).
5. **0.76.14에서 임시값 최적화 경로(VProc 부호 반전, `E76 eudv.py:344-355, 378-386`)를 실제로 타는 조건.** 참조 수 판정이라 이번 실험에서는 타지 않았다. 소스상 의미는 wrap이고, 0.81에서는 죽은 코드다.
6. **0.81.0 비용 수치.** 6.3의 비용은 0.76.14에서 쟀다. 0.81은 뺄셈 경로의 결과 값만 실측했다. `_seqcompute_sub` 구조가 같아(`E81 eudv.py:702-778`) 수치도 거의 같을 것이다(추측). WP0에서 다시 잰다.
7. **CtrigAsm f_LSub 실행 트리거 수(4~9).** 코드를 세어 얻은 값이고 실측하지 않았다. DPS `tests\t_war.py`의 빌림 사례(B1, C6, SS/SC)도 이번에 돌리지 않았다(DPS 폴더 읽기 전용).
8. **eudplib `v -= v` 버그가 업스트림에 보고되었는지.** 확인하지 못했다. 보고할지는 사용자가 정한다.
9. **부호 있는 포화 `ssub_sat`와 "부호 있는 값의 0 바닥 뺄셈"의 수요.** 맵 사용례 조사(R1)에는 없다(추측: 필요 없다).
