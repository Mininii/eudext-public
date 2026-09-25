# 인게임 확인 항목 분류 — 디버그 브리지 자동 판정 명세

만든 날 2026-09-18. 읽기·분석만 했고 저장소는 고치지 않았다.
원본은 `MapSource\EUDPLIB_PORT_CHECKLIST.md`(1~5절)과 eudext `fix/shape-crmath:eudext/docs/INGAME_CHECKLIST.md`(160항목)이다.
맵 소스는 eudext main d6b12b0 `eudext/examples/*`, 이식판 문서(`ue_eud`, `theSeed_eud`, `MSF_Respect_V_eud`, `mem2_eud`, `mem1_eud` 의 `eud\*.md`)를 봤다.
항목마다 적은 내용(읽을 값·기대값·완료 표식·계측·위험)은 `classification.json` 에 있다. 이 문서는 그 요약이다.

분류

- `AUTO`: 맵을 열고 기다리기만 하면 브리지가 판정한다.
- `AUTO_ASSIST`: 사람이 정해진 조작(키·클릭·채팅)만 하고, 판정은 브리지가 한다.
- `VISUAL`: 눈이나 귀로만 판단할 수 있다.
- `MULTI`: 2인 이상·관전자·LAN 이 필요하다.
- `CRASH_RISK`: 맵이나 게임이 멈출 수 있어 사용자가 따로 본다.
- `EXTERNAL`: SCMDraft·런처·CS_Photo·빌드 로그 같은 다른 프로그램이 필요하다.

주 분류는 하나다. 보조 표시(`extra`)에는 그 항목의 다른 성격을 적었다.
예: `VISUAL` + 보조 `AUTO` 는 "모양은 사람이 보지만 수·바이트는 브리지가 판정한다" 는 뜻이다.
JSON 에는 스키마 밖 키 세 개를 더 넣었다. `required` 는 필수 항목 여부다. `bundle` 은 `auto_all`(5절 통합 맵)이거나 따로 여는 맵·세션 이름이다. `phase` 는 통합 맵 안 순서이고, 통합 맵 밖이면 null 이다.

## 1. 개수

{{COUNTS}}

- "자동 판정이 일부라도 있음" 은 주 분류가 AUTO·AUTO_ASSIST 이거나, 보조 표시에 AUTO·AUTO_ASSIST 가 있는 항목이다.
  사람이 보는 항목이라도 수·바이트·멈춤 여부는 브리지가 기록한다는 뜻이다.
- 이식판은 대부분 "배포판과 같게 도는가" 를 사람이 게임하며 보는 항목이다. 그래서 주 분류 AUTO 비율이 낮다.
  그래도 시작 감시·시간 흐름·확인 문구·자원·스위치·데스 값은 자동으로 판정한다.
- 준비 항목 P-1~P-3 은 확인 항목이 아니라서 세지 않았다.

## 2. 브리지로 읽는 방법 (명세의 전제)

| 표기 | 뜻 | 맵 쪽 할 일 |
|---|---|---|
| `peek 주소` | 1.16.1 미러 구역(EUD 0x57F0E0~0x59F0E0)을 블록과 같은 오프셋으로 직접 읽는다. 데스 표 0x58A364, 자원 0x57F0F0, 유닛 수 0x582324, 스위치 0x58DC40, 동맹 0x58D634, 로케이션 0x58DC60, 생산 가능 0x57F27C, 업그레이드 0x58D2B0·0x58F32C, 공유 시야 0x57F1EC, 키 표 0x596A18, SCR_DB 칸 0x58F678~0x594198, Void 0x594000~, GunPtr 0x590300 | 계측은 필요 없다. 다만 오프셋을 잡을 블록(또는 시그니처)이 있어야 한다 |
| `watch 이름` / `watch_mem 주소:n` | eudplib 변수·식이나 미러 밖 주소(0x515B80, 0x57EEEB, 0x6284B8, 0x68C144, 0x641598, 0x51CE8C, 0x5124F0, 0x62848C, CUnit 칸, dat 표)를 맵이 매 프레임(또는 한 번) 감시 슬롯으로 복사한다 | `eudext.dbg` 호출을 넣는다 |
| `result 이름` | 결과 카운터(통과 수 / 전체 수 / 틀린 번호) | 자체 점검이 끝나는 자리에서 호출한다 |
| `chat` | 채팅 버퍼 0x640B58(11줄 × 218B) 스냅숏. 줄이 떴는지, 셀이 드러나는 진행, NUL 위치, slot 고정 여부를 본다 | 스냅숏 호출(매 프레임 또는 지정 프레임). 복사량이 크니 필요한 맵에서만 |
| `hdr` | 블록 헤더: seq, 게임 프레임 사본, 로컬 플레이어(관전자 128~131) | 없음 |
| `wall` | 리더 벽시계. seq 증가율(프레임/초), 멈춤(2초 이상 seq 정지), 프레임 시간(ms), 게임 시간 대 실시간 비율 | 없음 |

주의

- 미러 주소 가운데 SC:R 이 실제로 선형 매핑하는 것은 `dbg_reader.py --diag` 의 "직접 읽히는 영역" 에서 한 번 확인해야 한다.
  특히 0x596A18 키 표, 0x57F1EC 시야, 인구 표 칸이 그렇다.
  인구·색 표의 정확한 칸 주소는 구현 때 eudplib 정의로 맞춘다. 이 문서의 주소는 그 전제의 후보다.
- 키 입력·클릭은 브리지가 하지 않는다. AUTO_ASSIST 에서는 사람이 조작하고, 리더가 로컬 키 표·선택 표·채팅 상태의 시간순 기록과 결과 값을 맞대 본다.
- 소리는 알 수 없다. `PlayWAV` 호출 횟수(프로브)까지만 센다.
- 배틀넷에서는 쓰지 않는다. B13-10 은 사람만 본다.

### 2.1 맵 쪽 표준 슬롯 규약 (제안)

모든 확인 맵이 같은 이름 규칙을 쓰면 리더 하나로 판정할 수 있다.

- `<맵>.done`: 판정할 값이 다 준비된 게임 프레임. 0 이면 아직이다.
- `<맵>.pass`, `<맵>.total`, `<맵>.lastbad`, `<맵>.passbits`: 자체 점검 결과와 번호별 통과 비트.
- `<맵>.<항목 값>`: 항목별 원시 값. 이름은 `classification.json` 의 `read` 를 따른다.
- 판정 기대값은 맵에 넣지 않는다. 리더 쪽 기대 파일(JSON)에 두고, 기대 파일은 `classification.json` 의 `expect` 에서 만든다.

### 2.2 리더 쪽 추가 작업 (제안)

1. `--judge <기대 파일>`: done 표식을 기다렸다가 항목별 PASS/FAIL/기록값을 JSON 으로 쓴다. 그러면 Claude 가 체크리스트 결과 칸으로 옮길 수 있다.
2. 다른 시그니처로 블록 찾기: SCR_DB 표지(SCRDB_MAGIC)와 SNQC 디버그 칸(0x592100, `MSF_UE_RE\tools\snqc_probe.py` 의 DBG_MAGIC)으로도 오프셋을 잡는다.
   eudext 가 없는 UE_RE ①②·14 scrdb 맵을 계측 없이 `peek` 하기 위해서다.
3. 감시 모드 기록: seq·프레임 시간·멈춤을 시간순으로 파일에 남긴다(CRASH_RISK 세션의 증거).
4. AUTO_ASSIST 용 로컬 입력 기록: 키 표·선택 표·0x68C144 를 시간순으로 남겨 결과 값의 증가와 짝을 맞춘다.
5. 채팅 스냅숏 해독: 줄별 바이트, 0x0D 셀, 표식, NUL 위치를 보여 주고 13번째 줄 글에서 시간 숫자를 뽑는다(UE_RE S0-2).

## 3. 튕길 위험 목록 (사용자가 따로 보는 것)

주 분류가 CRASH_RISK 인 항목, 또는 보조 표시에 CRASH_RISK 가 있는 항목이다.

{{RISKTABLE}}

판단

- 이식판의 "시작 직후 멈춤 확인(STRCtrig 재배치)" 은 CRASH_RISK 로 넣었다.
  대상은 UE_RE S0-1·S0-16·S0-19, Memory 2 M2-S0-1·14, Memory 1 M1-S0-1·19 이다.
  확인 방법 자체는 "열고 기다리기" 뿐이다. 하지만 0.81 페이로드에서 재배치가 맞는지가 이식판 전체의 가장 큰 미확인이고, 틀리면 스타가 멈춰 강제 종료가 필요할 수 있다.
  그래서 사용자가 직접 보고, 브리지는 감시 기록만 남긴다(시그니처가 나타나는지, seq 가 흐르는지).
  theSeed 이식판은 STRCtrig 가 없어 T0-1 을 AUTO(보조 CRASH_RISK)로 두었다.
- "일부러 멈추기·튕기기"(theSeed T0-2·4·5·19, Respect V S1-3-1~4·6)는 모두 CRASH_RISK 다. 한 번에 한 판씩, 멈춘 스타를 끄고 다시 연다.
- 유닛 한도 채우기(B10-1 (b)·B10-9·D14-3·F21-9)와 언리미터 맵(18 전체, D14-11, F21-10)도 CRASH_RISK 다.

사용자가 따로 여는 위험 세션

| 세션 | 내용 | 항목 |
|---|---|---|
| X_limit (새 맵) | 03 의 t9(1,600여 마리 채우기, dying limit 40) → 10 의 d3(칸 가득 탄 0 반환) → 출발=목표 탄 한 발 | B10-1(b), B10-8(한도 부분), B10-9, D14-3, D14-2(출발=목표) |
| 18 sprite (그대로) | 언리미터·영구 스프라이트·칸 가득(53초) — 모양도 사람이 봐야 함 | F21-1~7, F21-9 |
| 17 exit_trap (그대로, 2인) | 실험 기능 exit_trap | F19-4 |
| 11 bgm (그대로) | 없는 파일 재생 D16-5(소리 확인 맵이라 어차피 사람이 봄) | D16-5, D16-6 |
| R_halt (이식판) | 일부러 멈추기·튕기기 판들 | T0-2·4·5·19, S1-3-1~4·6 |
| port 스모크 | 이식판 첫 시작 감시: UE_RE ①②③, Mem2 eudext·cplp, Mem1 A·C, M2-S0-11 테스트 키 | S0-1·16·19, M2-S0-1·11·14, M1-S0-1·19 |
| R_risk (맵 없음) | 앞으로 만들 확인 맵 | B15-8, D14-10, D14-11, F21-8, F21-10 |

## 4. 발견 사항 (분석 중 확인한 것)

1. **04 `datpatch_check` 는 화면에 아무 줄도 띄우지 않는다.** `examples/datpatch_example.eps`·`.py` 에 표시 코드가 없다.
   B15-1 방법의 "두 주소의 dword 를 표시" 가 맵에 빠져 있어서, 지금 04 맵으로는 사람이 봐도 B15-1 결과가 안 나온다.
   `0x515B80:32` 덤프 계측이 필요하다(미러 밖).
2. 19 `spawn_check` 는 화면 줄머리와 체크리스트 번호가 다르다.
   체크리스트 E12-4 가 화면에서는 `[A-3]` 줄이다. 마찬가지로 E12-5 는 `[E12-4]`, E12-6 은 `[E12-5]`, E12-7 은 `[E12-6]`, E12-8 은 `[E12-7]` 줄이다. 사람이 볼 때 헷갈린다.
3. 01 `S8_SubtractTest` 는 eudext 부트가 없는 순수 euddraft 플러그인이고 입력 맵이 `CBTest.scx` 다.
   `eudext.dbg` 가 eudplib 만으로 import 되거나, 부트를 얹어 `testing/base.scx` 로 옮겨야 통합 맵에 들어간다. 메모리 칸만 쓰니 옮겨도 될 것으로 본다.
4. 03 `units_ingame`(t9)과 10 `bullet_check`(d3)는 맵 안에 유닛 한도 채우기가 섞여 있다.
   이 부분을 떼어야 나머지 항목(B10-2~8·10, D14-1·2·5~8)을 통합 맵에 넣을 수 있다.
5. eudext 가 없는 이식판(UE_RE ①②, Mem2_S0, Mem1 A·B)에는 dbg 블록이 없다.
   UE_RE 는 SCR_DB 표지·SNQC 디버그 칸 시그니처로 오프셋을 잡을 수 있다. Memory 1·2 의 eudext 없는 판은 최소 블록 플러그인(순수 eudplib)을 넣지 않으면 감시할 수 없다.
6. i64·i64_ops·i128 의 10진 출력(`fmt()`)은 화면 글로만 확인된다.
   자체 점검 카운터(okCount)는 값 비교만 센다. 출력 문자열도 자동 판정하려면 strcmp 자체 점검을 더해야 한다.
7. 16 `numfmt` 의 D5-9 이름 비교와 25 `display` 의 E6-5 는 사용자 두 이름이 ASCII 라서 클랜 태그·한글·16바이트 초과 경우를 못 본다. 결과에 그 한계를 적어 둔다.
8. 체크리스트 원문의 `E6-4b`·`F19-1b` 는 번호 머리만 보면 E6-4·F19-1 과 겹친다. JSON 에서는 `E6-4b`·`F19-1b` 로 나눴다.

## 5. 자동 점검 통합 맵 (`auto_all`) 설계

목표는 안전한 자동 점검을 **한 맵에서 한 번에** 도는 것이다. 사용자는 맵을 혼자 열고 약 3분 30초(가장 빠름 기준, phase 1~18) 기다린다.
그 뒤 원하면 선택 구간 두 개(사람 조작 60초, 화면 보기)를 이어서 본다.
CRASH_RISK·MULTI 항목은 넣지 않았다.

### 5.1 기준 맵 요구

- `testing/base.scx` 사본(`auto_all_base.scx`): 128×128, P1 사람, P2 컴퓨터, P1 맵 리빌러 64, 시작 위치 2.
  - P2 가 있어야 하는 이유: 표적 마린(bullet)과 소환 주인(spawn)이 P2 이다.
  - base_multi(P1~P4 사람)는 필요 없다. display 의 관전자 항목(E6-1)만 base_multi 가 필요한데, 그 항목은 멀티 세션으로 뺐다.
- 로케이션(기준 맵 그대로): 1, 3(점 2048,683), 8, 12, 13(가운데), 14, 15, 16, 18, 23(본진), 25(3413,3413), 26 "Location 0"(찍기·탄), 27 "CLoc"(표적).
- 추가 유닛 하나: **P1 파이어뱃 한 기를 (160, 160)** 에 미리 놓는다(B15-3 — 시작 목록 체력 패치가 미리 놓인 유닛에 어떻게 먹는가).
  units 가 KillUnit 하는 마린이 아니고, 다른 phase 가 만드는 종류도 아니다. B10-5 의 F1 기대값은 "미리 놓인 유닛 수 + 1" 로 계산하므로 한 기가 늘어도 된다.
- eds: `[eudext boot]`, `[s8_ingame.py]`, `[auto_all.eps]`(phase 진행기), 프레임 로직이 있는 플러그인들(units·pool·switch·datpatch 판), `[freeze] freeze : 0`.
  unlimiter·MSQC·음원은 넣지 않는다. 그래서 bgm·sync·scrdb·sprite 는 밖에 둔다.

### 5.2 phase 표 (프레임은 게임 시작부터, 24프레임 = 1초)

{{PHASETABLE}}

### 5.3 진행기(`auto_all.eps`)와 표식 이름

- 각 원래 맵의 `afterTriggerExec` 본문을 `step(f)` 함수로 바꾼다. `f` 는 phase 시작부터 센 프레임이다.
  진행기가 창 안에서만 `step` 을 부른다. 원래 맵의 `frame == N` 조건은 그대로 두고, 들어가는 값만 phase 안 프레임으로 바뀐다.
- run_tests 형(i64·i64_ops·i128·numfmt·cmp·cell·mathx)은 모듈로 import 해 한 프레임에 호출한다.
  import 한 eps 의 `afterTriggerExec` 는 돌지 않으므로, 그 맵의 화면 줄 반복(show)도 저절로 빠진다.
- 표식(브리지 감시 슬롯):
  - `aa.frame`: 진행기가 매 프레임 쓰는 박동.
  - `aa.phase`: 지금 phase 번호.
  - `aa.<이름>.start` / `aa.<이름>.end`: 그 phase 의 시작·끝 게임 프레임. 0 이면 아직이다.
  - `aa.cpbad`: phase 끝에서 CP 가 캐시와 다르면 +1.
  - `aa.cleanbad`: 정리 뒤 남은 유닛 수가 기대와 다르면 +1.
  - `aa.done`: phase 18 까지 끝난 프레임.
  - `aa.assist.skipped`: 선택 구간을 시간 초과로 건너뛰었으면 1.
- 도중에 멈추면 리더가 마지막 `aa.phase`, 그 phase 의 start(end 없음), 마지막 `aa.frame`, seq 정지 시각을 기록한다.
  그러면 "어느 점검에서 멈췄는지" 가 남는다. 그 phase 는 다음 판에서 진행기 설정(`skip` 목록)으로 빼고 다시 돌릴 수 있게 한다.

### 5.4 phase 사이 정리

| 끝나는 phase | 정리 | 확인 |
|---|---|---|
| 1 units | RemoveUnit P1 마린·골리앗(터렛은 함께)·CC 남은 것. units 순회(new_units·dying·clear_on_death)는 이 창에서만 부른다 | P1 유닛 수 = 리빌러 64 + 파이어뱃 1 (peek 유닛 수 표) |
| 3 switch | 판정(프레임 100) 뒤 스위치 1·3·32·33·40 Clear | peek 0x58DC40 = 0 |
| 13 plot | RemoveUnit P1 스커지·뮤탈·레이스·스카우트·커세어. 로케이션 26 을 (0,0,0,0) 으로 | 해당 종류 수 0 |
| 14 spawn | RemoveUnit P2 전부(남는 노라드 II·피닉스 5·기타). P1 리빌러 121 은 남긴다(시야). 로케이션 26·27 되돌림 | P2 유닛 수 0 |
| 15 bullet | RemoveUnit P1 208·210·204(수명 안 쓴 탄막 유닛 포함), P2 마린. 로케이션 26·27 되돌림. 탄 dat 설치는 그대로 둔다(뒤 phase 는 208/210/204 를 안 씀) | 해당 수 0 |
| 16 display | end_pinned, RemoveUnit P1 마린(E6-4 용), 마린 이름 TBL 을 원래 글로 되돌림, 임무 목표 비움 | 채팅 스냅숏에 고정 줄 없음 |
| 17 chat | 타자기 enable 둘 다 0, relay 끔 | - |

- **문자열**: 모든 phase 의 printAll/DisplayText 는 `aa.quiet`(기본 1)일 때 내지 않는다. 판정은 슬롯으로 하기 때문이다.
  예외는 사람이 봐야 하는 phase(13~17)의 안내 줄과, pool 의 ERROR 두 줄(프레임 2·10, chat phase 훨씬 앞)이다.
  chat phase(17)는 다른 줄이 끼면 D17-4·5 판정이 흔들리므로 그 창에서는 진행기 안내 줄도 끈다.
- **CP**: phase 마다 끝에서 `getcurpl()` 과 CP 캐시를 비교해 `aa.cpbad` 를 센다.
- **dat**: datpatch phase 는 원래 예제의 선언 가운데 탄과 겹치는 것을 뺀 판으로 쓴다.
  원래 예제는 `datpatch_example.py` 에서 flingy 106 최고속도를 +8000 으로 바꾸는데, bullet 은 같은 flingy 를 −8001(음수 관례)로 쓴다. 섞이면 D14-1 방향이 뒤집힌다.
  예제의 unit 208 Flyer/Invincible 도 bullet 의 탄막 유닛과 같은 번호다. 대신 파이어뱃 maxHp·Valkyrie timeCost·supplyUsed 처럼 아무 phase 도 쓰지 않는 칸을 쓴다.
- **유닛 표**: 동시에 유닛을 만드는 phase 가 없다. 새 유닛 순회를 쓰는 곳은 units(1)와 plot(13, 좌표 대조) 두 곳이다.
  `units.new_units()` 의 첫 호출이 이전 유닛을 한꺼번에 돌려주는지는 구현 때 확인한다. 돌려준다면 plot 창 한 프레임 전에 한 번 비우는 호출을 둔다.

### 5.5 통합 맵에 넣지 않는 것과 이유

{{OUTSIDE}}

이유

- **X_limit**(B10-1(b)·B10-8 한도 부분·B10-9·D14-3·D14-2 출발=목표): 유닛 한도 채우기와 0 벡터 탄은 CRASH_RISK 다.
  통합 맵 도중에 멈추면 뒤 phase 결과를 모두 잃으므로 뺐다. X_limit 은 03 의 t9 + 10 의 d3 + 한 발짜리 작은 맵이다.
- **빈 유닛 표 가정(units B10)** 검토 결과
  - B10-5 의 F1(미리 놓인 유닛이 첫 프레임에 나오는가)은 질문 자체가 "게임 첫 프레임" 이다. 상대값으로 바꿀 수 없어 **맨 앞(phase 1)** 에 둔다.
  - 나머지(B10-1(a)·2·3·4·6·7)는 머리 전/후·칸 번호의 **상대값** 판정이라 어디서든 되지만, 같은 프레임에 다른 유닛 생성·죽음이 끼면 안 된다. 그래서 phase 1 을 "유닛을 만드는 다른 phase 없음" 창으로 잡았다.
  - B10-8 의 F8 알림 수(6)도 그 창의 마린 수 기준이다(미리 놓인 파이어뱃은 마린이 아니라 죽지 않음).
- **R_sprite(18)**: F21-* 는 `[unlimiter]` 가 필요하다(CGRP 필수). 언리미터를 통합 맵 전체에 켜면 모든 점검의 조건이 바뀌고, 영구 스프라이트가 남는다.
- **11 bgm**: 소리가 판정 대상이다. MSQC(QC 49)·음원 약 370개를 싣고, D16-5(없는 파일 재생)가 위험하다.
  값 판정(조각 번호·dt·patch 칸)은 11 맵에서 자동으로 한다.
- **14 scrdb**: SCR_DB 런처·MSQC·다시 열기가 필요하다.
- **21 sync**: MSQC 입력과 사람 키 조작이 필요하다. 싱글 가능 항목(B13-3~6·8·9)도 21 맵 하나에서 사람이 조작한다.
- **멀티·관전자**(B8-1~3·5~8, C11-8, E6-1, F19-1·5·6·2, D16-4·7, D18-6, B13-1·2·7·10): base_multi 와 여러 PC 가 필요하다.
- **다른 맵·빌드가 필요**(B15-2·6·7·9, F19-3, B13-11·12, D14-12): 확인 코드나 변형 맵부터 만들어야 한다.
- **게임 없음**(C9-1, D7-6, D18-9): SCMDraft·파이썬·빌드 로그로 끝난다.
- **한 프레임 부담**: numfmt(약 31,000 트리거)·i128·i64_ops 는 통합 맵 안에서 서로 다른 프레임(90·120·150)에 둔다.
  원래 01~26 맵 가운데 한 프레임 부담 때문에 뺄 것은 t9(약 5만 트리거 + 유닛 1,600) 하나뿐이다.
  D5-10 의 "첫 프레임 체감" 은 통합 맵에서는 150프레임 프레임 시간으로 판정한다. 첫 프레임 수치가 따로 필요하면 16 을 단독으로 연다.

### 5.6 화면 확인이 섞인 점검의 나눔

- 값은 통합 맵에서 자동으로 판정하고, 화면은 "통합 맵을 지켜보거나 원래 맵을 따로" 연다.
  대상: D7-1~3(12), A-3·E12-1~3·5~7(19), D14-1·2·8·9·13(10), E6-3·4·4b·9(25), D17-1·3·7·8(13). `bundle` 에 적었다.
- 통합 맵은 phase 13~17 시작마다 CenterView 와 안내 줄 한 줄을 띄운다. 지켜보는 사람이 어디를 볼지 알게 하기 위해서다.
- 화면만 보는 항목(D5-2~8, D6-1~5, E6-6·7)은 phase 20(선택)에서 돈다. 보지 않으면 원래 맵 16·09·25 를 연다.
- 사람 조작 항목 가운데 통합 맵에 넣은 것은 두 곳이다.
  - D17-6·E6-2 는 phase 19(선택, 60초, 시간 초과 시 건너뜀)에 넣었다.
  - D14-6 의 클릭·드래그는 phase 15 안 10초 창에 넣었다. 하지 않으면 선택 부분만 '건너뜀' 으로 기록한다.

### 5.7 여는 횟수 (eudext)

| | 싱글 | 멀티·관전 | 합계 |
|---|---|---|---|
| 지금 | 21맵(01~16·18·19·24·25·26) + 14 다시 열기 = 22 | 17·20·21·22·23·14b + 11 멀티 + 25 관전자 = 8 | **30** |
| 통합 맵안 | **auto_all** 1 + 사람이 따로 보는 X_limit·18(위험)·11(소리)·14(+다시 열기)·21(키 조작) = 6 (+1) | M1_multi(20+22+23+E6-1), 21 멀티, 11 멀티, 14b, 17 = 5 | **11 (+1)** |

- 화면 항목을 통합 맵에서 지켜보지 않으면 원래 맵(09·10·12·13·16·19·25)을 필요한 만큼 더 연다(최대 7).
- 이식판은 맵 자체가 달라 통합 맵에 넣을 수 없다. 판마다 "스모크 1분"(열고 기다리기)으로 AUTO 항목을 한꺼번에 판정한다.
  대상: S0-18, T0-1·3·6·7·13, S1-1-7·S1-3-5·S1-5-2·S1-7-1·5·6·7·S1-8-2, M2-S0-2·9, M1-S0-4·18.
  STRCtrig 첫 시작 판은 3절의 port 스모크(사람)로 본다.
- 멀티 세션 M1_multi: 20 players + 22 pool(C11-8) + 23 misc 관전자 채팅 + 25 의 E6-1 세 줄(display 모듈만, 고정 줄 없이). 사람 2 + 관전자 2.
  players 의 자원·표시, pool 의 공유 상태, misc 의 관전자 키 처리는 칸이 겹치지 않는다.
  관전자 PC 에도 리더를 켜면 B8-1·E6-1·F19-1 의 번호·줄 판정이 자동이다.

## 6. 맵별 계측 명세 (AUTO 로 만들기 위해 고칠 곳)

`dbg.*` 이름은 제안이다. 실제 이름은 만들고 있는 `eudext.dbg` 에 맞춘다.
`watch`·`result`·`done` 이름은 `classification.json` 의 `read` 와 같다.

| 맵 / 파일 | 고칠 곳 | 내보낼 값 | 완료 표식 |
|---|---|---|---|
| 01 `docs/spec/S8_ingame/s8_ingame.py` | `beforeTriggerExec` 에서 run_tests 직후 | 시험 칸 17개 원시 값(S1~S5, X1~X3, P1~P3, F1, E1~E5), 모형별 맞은 수 | `m01.done` |
| 02 `i64_ingame.eps` | `keep()` 에 passbits, run_tests 끝 | raw1~3, passbits(23), okCount/total, fmt strcmp 결과 | run_tests 끝 |
| 03 `units_ingame.eps` | t1~t4·t8·t11 의 지역 값을 전역으로, 새 유닛 순회 뒤 `nu[frame]`, dying 순회 뒤 `dead[frame]`. t9 를 `units_limit_ingame.eps` 로 분리 | T1~T11 값, nu[1..12], dead[1..45], t6 표(F8~F20) | frame 50 |
| 04 `datpatch_example.eps` | afterTriggerExec 24프레임에 덤프 | 0x515B80:32, (추가) timeCost·supplyUsed·requirementOffset 칸 | frame 24 |
| 05 `cmp_example.eps` / 06 `cell_example.eps` | tick == 24 | n (/15, /18), 번호별 비트 | tick 24 |
| 07 `mathx_ingame.eps` | `tally()`·`g_samples()` | good/total, 그룹 11개, 표본 6개 | frame 20 |
| 08 `pool_ingame.eps` | afterTriggerExec 끝 | t1ok~t7ok, visits1·bad1·overCount·overDropped·code3[F3..F6]·t3bad·last3·g1·g0·al1·al2·ix4·sum4·perfCount·visits6·t6bad·visits7·kinds.count | frame 60 |
| 10 `bullet_ingame.eps` | d1/d2 에 탄 epd·기대 보관, `k % 24 == 3` 에서 위치 변화 → `atan2`/`to_dir256`. d5·d6·d7·d8 값, d6 은 10초 위치·선택 표(0x6284B8, 로컬). d3·출발=목표를 X_limit 로 | facing/want/dir/dead ×16, 가까운·먼·같은 점, 위치, 칸 값, shellType, (선택) 총알 표 weaponType | frame 610 |
| 11 `bgm_ingame.eps` | 상태 줄 자리 | step, pd/pe chunk·last_dt, player_s 상태·끔 비트, patch 문자열 칸 | frame 1000 |
| 12 `plot_ingame.eps` | 매 프레임 `units.new_units()` 로 새 유닛 (종류, +0x28 좌표) → plotter 별 기대 좌표열(`shapes.point_at` + 중심)과 대조. 프레임별 made 증가량 배열 | posbad, orderbad, made_per_frame, rounds, made, good/checks | frame 540 |
| 13 `chat_ingame.eps` | `relayLine()` 의 dwread 3개·i, relayed, LONG 줄 nx, slow 타자기 PlayWAV 에 프로브, 채팅 스냅숏 | raw0/4/8, marker_pos, relayed, nx, wav_count | frame 1500 |
| 14 `scrdb_ingame.eps` | (선택) loaded·saves 감시. 값 칸은 미러 | loaded[p], saves[p] | loaded == 1 |
| 16 `numfmt_ingame.eps` | run_tests 끝 | okCount/total, lastBad, cellsOk, nameBuf:8, 0x57EEEB:7 | run_tests 끝 |
| 18 `sprite_ingame.eps` | f1~f9 값 | dotMade·dotZero·bounceE·stormE·stormE2·usE(+0xDC·+0xE4·주문)·usMoving·recE·recE2·marine xy·paintDone·drawn·dropped·userDone·헤더 값·fillMade·fullZero, 선택 표 | frame 700 |
| 19 `spawn_ingame.eps` | 콜백(CountHome·Park·CountVis·WarpSeen·CountMark·CountBoss)에서 epd 의 +0x28 위치·+0x58 목표를 콜백 x,y·기대 로케이션과 비교. 프레임별 생성 수 배열, 나선 좌표 10개, PH7 에 남은 보스·피닉스 제거 | posbad, order_bad, homes, overflow, hydra/obs_per_frame, parked, vis, live_at_gap, inv_flag, w8~w3, boss·mark 좌표, spiral_xy, brood, 0x666458 | frame 1005 |
| 20 `players_example.eps` | contains_user 결과(로컬), is_human·human_mask, CenterView 등 관전자 CP 액션 추가 | contains_obs, contains_all, is_human1, human_mask | frame 48 |
| 21 `sync_example.eps` | score·held·level, F5·우클릭 출력 카운터, mouse.x/y, mx/my, panel, 선택 표 | 좌동 | 조작 끝(리더) |
| 23 `misc_ingame.eps` | 0x68C144 감시, (추가) host_player·HotkeyUnit·is_widescreen | 좌동 | - |
| 24 `i128_ingame.eps` | run_tests 끝 | okCount/total, passbits(46), fmt strcmp | run_tests 끝 |
| 25 `display_ingame.eps` | self_check 뒤, 쪽 4 에서 이름 버퍼 네 개, 13번째 줄 0x641598, TBL 칸, 채팅 스냅숏 | okCount/total/lastBad, 이름 ×4, line13, TBL | page 8 |
| 26 `switch_ingame.py` | 조건 두 개 결과를 변수로 | cond1, cond2 (+ peek 0x58DC40:2) | tick 48 |
| UE_RE `eud/src/s0_probe.eps` (③) | `import eudext.dbg`, 표시 여부·s0_cycles, 채팅·13번째 줄 스냅숏. ①② 는 리더의 SCR_DB·SNQC 시그니처 찾기로(계측 없음) | s0.shown, line13 | cycle 97 |
| theSeed `eud/frame/probe.eps` + `seed_main` + `build_eud.py --dbg` | probe 와 따로 켜는 dbg 블록(t0 에도). yCount·recvCount·lastX·pressedBy·budget.count·GameTimeSec·LimitX·LimitC·TestMode·GameStartDone·패배 발동, play_wav 프로브 | 좌동 | GameTimeSec |
| Respect V `eud/src/rv_main.eps` + `rv_state.py` + `build.py --dbg` | 난이도·GS·EVF/OM·SpeedVar·방장·시작 인원·사람 수·공유·BGM(곡·남은 시간·끔 비트·last_dt)·칭호 인식·강퇴·유닛 수·표본 에너지, 채팅 스냅숏, (선택) dat 덤프 | 좌동 | gs 뒤 |
| Memory 2 `eud/src/s0_probe.eps` | eudext 판에 dbg 블록·표시 표식·채팅·13번째 줄. 나머지는 미러(데스 180/181, 0x58F450~, 0x58F500, 0x590300) | s0.shown | cycle 97 |
| Memory 1 `eud/src/s0_probe.eps` (C판) | 위와 같음. A·B 판은 최소 블록 플러그인 변형이 있어야 감시 가능 | s0.shown | cycle 97 |

계측이 가장 많이 필요한 곳은 다음 순서다.

1. **19 spawn**: 콜백 6개에서 위치·명령 목표 대조와 프레임별 배열.
2. **10 bullet**: 탄 진행 방향 계산, 선택 표, 분리.
3. **12 plot**: 새 유닛 좌표 대조기.
4. **Respect V rv_main**: 상태 변수 약 20개와 채팅 스냅숏.
5. **03 units**: 값 약 40개와 t9 분리.

## 7. 분류별 표

{{CATTABLES}}
