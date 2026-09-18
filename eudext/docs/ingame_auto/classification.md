> 출처: 분류 에이전트가 2026-09-18 01:47 세션 임시 폴더(`scratchpad\dbg_plan\`)에 만든 `classification.md`·`classification.json`·`gen\` 를
> 그대로 옮겼다(feat/debugbridge). 다시 만들려면 `python gen/gen.py` (이 폴더에 쓴다).
> 판정 명세·도구: `eudext/tools/ingame_auto.py`, 블록 모듈: `eudext/dbg.py` (DESIGN 4.21·5.5).
> **2026-09-18 1차 인게임 뒤 고침**: E6-3·E6-4·E6-4b 를 `CRASH_RISK` 로 옮기고 통합 맵에서 뺐다 (display 단계에서 게임이 EUD ERROR 0xFF9BE98B 로 멈췄다) — 25_display_check·25b_display_bisect 전용.

# 인게임 확인 항목 분류 — 디버그 브리지 자동 판정 명세

만든 날 2026-09-18. 읽기·분석만 했고 저장소는 고치지 않았다.
원본은 `MapSource\EUDPLIB_PORT_CHECKLIST.md`(1~5절)과 eudext `fix/shape-crmath:eudext/docs/INGAME_CHECKLIST.md`(160항목)이다.
맵 소스는 eudext main 89c9539 `eudext/examples/*`, 이식판 문서(`ue_eud`, `theSeed_eud`, `MSF_Respect_V_eud`, `mem2_eud`, `mem1_eud` 의 `eud\*.md`)를 봤다.
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

| 묶음 | 항목 수 | AUTO | AUTO_ASSIST | VISUAL | MULTI | CRASH_RISK | EXTERNAL |
|---|---|---|---|---|---|---|---|
| eudext 전체 | 160 | 61 | 10 | 32 | 25 | 20 | 12 |
| └ eudext 필수 47 | 47 | 20 | 2 | 5 | 5 | 11 | 4 |
| 이식판 전체 | 126 | 26 | 19 | 40 | 19 | 17 | 5 |
| └ UE_RE | 19 | 2 | 2 | 7 | 1 | 3 | 4 |
| └ theSeed | 19 | 5 | 4 | 1 | 5 | 4 | 0 |
| └ Respect V | 51 | 15 | 11 | 12 | 8 | 5 | 0 |
| └ Memory 2 | 17 | 2 | 1 | 8 | 3 | 3 | 0 |
| └ Memory 1 | 20 | 2 | 1 | 12 | 2 | 2 | 1 |
| 합계 | 286 | 87 | 29 | 72 | 44 | 37 | 17 |

| 묶음 | 주 분류 AUTO | AUTO + AUTO_ASSIST | 자동 판정이 일부라도 있음(보조 포함) | 튕김 위험 표시(주·보조) |
|---|---|---|---|---|
| eudext (160) | 61 (38%) | 71 (44%) | 128 (80%) | 26 |
| eudext 필수 (47) | 20 (43%) | 22 (47%) | 46 (98%) | 13 |
| 이식판 (126) | 26 (21%) | 45 (36%) | 101 (80%) | 25 |
| 합계 (286) | 87 (30%) | 116 (41%) | 229 (80%) | 51 |

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

| ID | 주 분류 | 맵 | 왜 위험한가 |
|---|---|---|---|
| B10-1 | AUTO | 03 units_ingame | (b) 유닛 한도까지 채우기 — 한 프레임 약 5만 트리거 + 유닛 1,600여 마리 생성. 멈춤·긴 렉 가능 |
| B10-8 | AUTO | 03 units_ingame | limit=40 확인은 t9 채우기 뒤라 X_limit 맵 |
| B10-9 | CRASH_RISK | 03 units_ingame | 유닛 한도 채우기와 같은 프레임 |
| B13-9 | AUTO | 21 sync_check | 장시간 진행 안정성(낮음) |
| B15-8 | CRASH_RISK | 04 datpatch_check (변형) | 읽기 전용 표기 칸(그림 포인터 계열) 쓰기 — 그릴 때 튕길 수 있음 |
| D14-2 | AUTO | 10 bullet_check | 출발 = 목표 탄(0 벡터) 한 발 — 튕길 가능성은 낮지만 '튕기지 않는가' 가 질문이라 X_limit 로 옮기기를 권장 |
| D14-3 | CRASH_RISK | 10 bullet_check | 유닛 칸 1,700 가득 + 탄 생성 시도 |
| D14-10 | CRASH_RISK | (대량 패턴 맵) | 총알·스프라이트 표 한도 넘김 |
| D14-11 | CRASH_RISK | (대량 패턴 맵) | 언리미터 끔 + 대량 탄 |
| D16-5 | CRASH_RISK | 11 bgm_check | MPQ 에 없는 파일 재생 — SC:R 동작 미확인 |
| D16-6 | VISUAL | 11 bgm_check (--ogg 빌드) | 형식이 다른 파일 해독(낮음) |
| E6-3 | CRASH_RISK | 25 display_check + 25b display_bisect | 2026-09-18 인게임에서 게임이 EUD ERROR 로 멈췄다 (통합 맵에서 뺌) |
| E6-4 | CRASH_RISK | 25 display_check + 25b display_bisect | E6-3 과 같은 구간 — 통합 맵에서 뺌 (자체 점검 E6-8 에서는 같은 쓰기가 통과했다) |
| E6-4b | CRASH_RISK | 25 display_check + 25b display_bisect | E6-3 과 같은 구간 — 통합 맵에서 뺌 |
| F19-4 | CRASH_RISK | 17 exit_trap_check | 실험 기능 — 로컬 트리거 목록을 자기 순환으로 바꿈. 목록 주인을 잘못 고르면 전원 멈춤, 강제 종료 필요 |
| F21-1 | CRASH_RISK | 18 sprite_check | 18 맵 전체가 [unlimiter] + 영구 스프라이트 + (53초) 유닛 칸 가득 채우기 |
| F21-2 | CRASH_RISK | 18 sprite_check | 18 맵 전체가 [unlimiter] + 영구 스프라이트 + (53초) 유닛 칸 가득 채우기 |
| F21-3 | CRASH_RISK | 18 sprite_check | 18 맵 전체가 [unlimiter] + 영구 스프라이트 + (53초) 유닛 칸 가득 채우기 |
| F21-4 | CRASH_RISK | 18 sprite_check | 18 맵 전체가 [unlimiter] + 영구 스프라이트 + (53초) 유닛 칸 가득 채우기 |
| F21-5 | CRASH_RISK | 18 sprite_check | 18 맵 전체가 [unlimiter] + 영구 스프라이트 + (53초) 유닛 칸 가득 채우기 |
| F21-6 | CRASH_RISK | 18 sprite_check | 18 맵 전체가 [unlimiter] + 영구 스프라이트 + (53초) 유닛 칸 가득 채우기 |
| F21-7 | CRASH_RISK | 18 sprite_check | 18 맵 전체가 [unlimiter] + 영구 스프라이트 + (53초) 유닛 칸 가득 채우기 |
| F21-8 | CRASH_RISK | (28장 함수를 쓰는 맵) | 이미지 256 iscript 86·스캐너 크기 0 영구 부작용 |
| F21-9 | CRASH_RISK | 18 sprite_check | 유닛 칸 가득 + 스프라이트 생성(언리미터 맵) |
| F21-10 | CRASH_RISK | (언리미터 뺀 변형) | 가이드북상 CGRP 는 언리미터 필수 — 튕길 가능성 높음 |
| F21-11 | MULTI | (멀티 맵) | 언리미터 맵 |
| S0-1 | CRASH_RISK | UE_RE_S0.scx (①) | STRCtrig 런타임 재배치가 0.81 페이로드에서 맞는지 미확인(가장 큰 미확인) — 틀리면 시작 직후 멈춤·튕김 |
| S0-16 | CRASH_RISK | UE_RE_S0_cplp_out.scx (②) | CPLP 보호 검사가 0.11 출력(가짜 scenario.chk 두 벌)에서 오작동하면 시작 직후 멈춤 |
| S0-19 | CRASH_RISK | UE_RE_S0_eudext.scx (③) | eudext 부트를 얹은 하이브리드의 첫 시작(STRCtrig 재배치 + eudext 페이로드) |
| T0-1 | AUTO | theSeed_eud_S0_t1 (승인 닉네임) | EUD 오류면 멈춤(새로 짠 코드 — STRCtrig 없음, 낮음) |
| T0-2 | CRASH_RISK | theSeed_eud_S0_t1 (다른 닉네임) | 일부러 멈추기(unsafe_halt) — 강제 종료가 필요할 수 있음 |
| T0-4 | CRASH_RISK | theSeed_eud_S0_t1 (방 배속 옵션) | 일부러 멈추기 |
| T0-5 | CRASH_RISK | theSeed_eud_S0_t1 (슬롯 변경) | 일부러 멈추기(3판) |
| T0-13 | AUTO | theSeed_eud_S0_t1 | 장시간(낮음) |
| T0-19 | CRASH_RISK | theSeed_eud_S0_t1 (2인, 닉네임 없음) | 일부러 멈추기(두 PC) |
| S1-3-1 | CRASH_RISK | Respect_V_eud_S1.scx (LAN 방) (방 제목 배속 옵션) | 일부러 튕기기(실행 방지) — 원본의 ExitDrop 은 없지만 패배 뒤 튕김 |
| S1-3-2 | CRASH_RISK | Respect_V_eud_S1.scx (LAN 방) (사람 슬롯에 컴퓨터) | 일부러 튕기기(실행 방지) — 원본의 ExitDrop 은 없지만 패배 뒤 튕김 |
| S1-3-3 | CRASH_RISK | Respect_V_eud_S1.scx (LAN 방) (컴퓨터 슬롯·종족 변경) | 일부러 튕기기(실행 방지) — 원본의 ExitDrop 은 없지만 패배 뒤 튕김 |
| S1-3-4 | CRASH_RISK | Respect_V_eud_S1.scx (LAN 방) (싱글플레이) | 일부러 튕기기(실행 방지) — 원본의 ExitDrop 은 없지만 패배 뒤 튕김 |
| S1-3-6 | CRASH_RISK | Respect_V_eud_S1_T1.scx (허용 닉네임 없음) | 일부러 튕기기(실행 방지) — 원본의 ExitDrop 은 없지만 패배 뒤 튕김 |
| S1-3-7 | AUTO | Respect_V_eud_S1_T1.scx (GALAXY_BURST / Natori_sana) | 닉네임 판정이 틀리면 튕김(패배) |
| S1-3-8 | AUTO_ASSIST | Respect_V_eud_S1_T2.scx | 허용 닉네임 필요(없으면 튕김) |
| M2-S0-1 | CRASH_RISK | Mem2_S0_eudext.scx | STRCtrig 런타임 재배치(0.81) 미확인 — 틀리면 시작 직후 멈춤·튕김 |
| M2-S0-11 | CRASH_RISK | Mem2_S0_eudext.scx | 0.81 에서 고친 NSQC 키 기억 칸 — 틀리면 배열 밖 쓰기(메모리 오염·디싱크·멈춤) |
| M2-S0-14 | CRASH_RISK | Mem2_S0_eudext_cplp_out.scx | CPLP 검사 + STRCtrig 재배치 첫 시작 |
| M1-S0-1 | CRASH_RISK | Mem1_S0_A.scx | STRCtrig 런타임 재배치(0.81) 미확인 — 틀리면 시작 직후 멈춤·튕김 |
| M1-S0-9 | VISUAL | Mem1_S0_A.scx | 건작 대량 소환(유닛 한도 근처) |
| M1-S0-14 | MULTI | Mem1_S0_A.scx (2인) | 0.9 NSQC 는 F12(0x7B)에서 배열 밖에 썼다 — 고친 사본 확인 |
| M1-S0-16 | VISUAL | Mem1_S0_B.scx | B 판 첫 시작(STRCtrig 재배치) |
| M1-S0-18 | AUTO | Mem1_S0_C.scx | C 판(eudext + CPLP) 첫 시작 |
| M1-S0-19 | CRASH_RISK | Mem1_S0_C.scx | CPLP 검사가 0.11 출력(가짜 scenario.chk)에서 오작동하면 멈춤 |

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

| phase | 이름 | 프레임 창 | 원래 맵 | 항목 | 주 분류(수) | 비고 |
|---|---|---|---|---|---|---|
| 1 | `units` | 1~55 (+56 정리) | 03 (t9 뺌) | B10-1, B10-2, B10-3, B10-4, B10-5, B10-6, B10-7, B10-8, B10-10, B15-3 | AUTO 10 | 빈 유닛 표에서 시작해야 함 — 맨 앞, 이 창에서는 다른 phase 가 유닛을 만들지 않음 |
| 2 | `pool` | 1~60 판정, 끝까지 조용히 돎 | 08 | C11-1, C11-2, C11-3, C11-4, C11-5, C11-6, C11-7 | AUTO 7 | 유닛·문자열 없음(ERROR 두 줄·Buzz 만) |
| 3 | `switch` | 1 켜기, 48~100 판정 | 26 | A-2 | AUTO 1 | 스위치 1·3·32·33·40 — 다른 phase 는 스위치를 안 씀 |
| 4 | `s8` | 2 실행, 3 판정 | 01 | A-1, B15-5 | AUTO 2 | 메모리 칸만 |
| 5 | `datpatch` | 시작 목록, 24 덤프, 18 에서 B15-4 판정 | 04 (선언을 바꾼 판) | B15-1, B15-4, B15-10 | AUTO 2, VISUAL 1 | 탄 관련 dat(208·flingy 106·무기 127/128)은 건드리지 않게 선언을 바꿈 |
| 6 | `i64` | 60 | 02 | C3-1, C3-2, C3-3 | AUTO 3 | run_tests 한 프레임 |
| 7 | `i64_ops` | 90 | 15 | D4-1 | AUTO 1 |  |
| 8 | `i128` | 120 | 24 | F20-1 | AUTO 1 |  |
| 9 | `numfmt` | 150 | 16 | D5-1, D5-9, D5-10 | AUTO 3 | 약 31,000 트리거 프레임 — 단독 프레임에 |
| 10 | `cmp_cell` | 180 | 05·06 | B1-1, C2-1 | AUTO 2 |  |
| 11 | `mathx` | 200~212 | 07 | C9-2 | AUTO 1 | 그룹마다 2프레임 간격 |
| 12 | `players` | 230 | (새 코드) | B8-4 | AUTO 1 | B8-4, host_player |
| 13 | `plot` | 300~845 (+850 정리) | 12 | D7-1, D7-2, D7-3, D7-4, D7-5 | AUTO 5 | 로케이션 26, P1 공중 유닛 |
| 14 | `spawn` | 900~1905 (+1910 정리) | 19 | A-3, C11-9, E12-1, E12-2, E12-3, E12-4, E12-5, E12-6, E12-7, E12-8, E12-9 | AUTO 9, VISUAL 2 | 로케이션 26·27, P2 유닛, P1 리빌러 121 남김 |
| 15 | `bullet` | 1950~2640 (+2645 정리) | 10 (d3·출발=목표 뺌) + D14-4·9 | D14-1, D14-2, D14-4, D14-5, D14-6, D14-7, D14-8, D14-9, D14-13 | AUTO 5, AUTO_ASSIST 1, VISUAL 3 | 로케이션 26·27, 탄 dat 설치 |
| 16 | `display` | 2800~3258 (+3255 정리) | 22 (E6-1·3·4·4b 뺌) | E6-8, E6-5, E6-9, E6-10 | AUTO 3, VISUAL 1 | 고정 줄·이름·긴 줄·every — 13번째 줄·TBL 은 2026-09-18 EUD ERROR 로 25·25b 맵으로 옮겼다 |
| 17 | `chat` | 3400~4900 | 13 (D17-6 은 19 로) | D17-1, D17-2, D17-3, D17-4, D17-5, D17-7, D17-8, D17-9 | AUTO 4, VISUAL 4 | 타자기는 이 창에서만 켬, 다른 phase 출력 끔 |
| 18 | `final` | 4950 | - |  |  | 늦게 판정하는 값(B15-4, pool 계속 판정) + aa.done |
| 19 | `assist (선택)` | 4950~6390 (60초, 시간 지나면 건너뜀) | 13·25 | D17-6, E6-2 | AUTO_ASSIST 2 | 사람 조작: 채팅 '!H안녕 éè 가나다', 채팅 몇 줄 |
| 20 | `visual (선택)` | 6400~ | 16·09·25 | D5-2, D5-3, D5-4, D5-5, D5-6, D5-7, D5-8, D6-1, D6-2, D6-3, D6-4, D6-5, E6-7, E6-6 | VISUAL 14 | 화면만 보는 쪽 — numfmt 줄, strdesign 5쪽, E6-7·E6-6 |

통합 맵에 들어간 eudext 항목 88개 (필수 25) — 기다리기만 하는 구간(phase 1~18) 72개, 선택 구간(19 assist, 20 visual) 16개. 주 분류: AUTO 60, AUTO_ASSIST 3, VISUAL 25. 이 가운데 주 분류 VISUAL 인 25개는 '값은 자동, 화면은 사람' 으로 나눈 것.

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

| 넣지 않는 곳(bundle) | 항목 | 주 분류 |
|---|---|---|
| M1_multi | B8-1, B8-2, B8-3, B8-5, B8-6, B8-7, B8-8, C11-8, E6-1*, F19-1*, F19-5, F19-6 | MULTI |
| X_limit | B10-9, D14-3* | CRASH_RISK |
| 21 sync | B13-1*, B13-2*, B13-7 | MULTI |
| 21 sync (싱글 가능, 키 조작) | B13-3, B13-4, B13-5, B13-6, B13-8, B13-9 | AUTO, AUTO_ASSIST |
| 21 sync (배틀넷) | B13-10 | MULTI |
| 별도 멀티 맵(NSQC) | B13-11 | MULTI |
| 별도 멀티 맵(로케이션) | B13-12 | MULTI |
| 별도: SCMDraft 로 CHK 를 바꾼 맵 2개 | B15-2 | EXTERNAL |
| 별도: 저장·불러오기·리플레이 변형 맵 | B15-6 | AUTO_ASSIST |
| 별도: 두 변형 맵(소리) | B15-7 | VISUAL |
| R_risk (별도) | B15-8, D14-10, D14-11, F21-8, F21-10 | CRASH_RISK |
| 별도 빌드(M2 from_eud_editor) | B15-9 | EXTERNAL |
| EXT (게임 없음) | C9-1 | EXTERNAL |
| EXT (SCMDraft + 한 줄 보기) | D7-6 | EXTERNAL |
| 별도 멀티 맵 | D14-12 | MULTI |
| 11 bgm | D16-1*, D16-2, D16-3*, D16-5, D16-6, D16-8, D16-9 | CRASH_RISK, VISUAL |
| 11 bgm (멀티) | D16-4, D16-7 | MULTI |
| 14 scrdb | D18-1*, D18-2*, D18-3*, D18-5, D18-7, D18-8 | EXTERNAL |
| 14 scrdb (다시 열기) | D18-4* | EXTERNAL |
| 14b scrdb 2인 | D18-6* | MULTI |
| EXT (빌드 로그) | D18-9 | EXTERNAL |
| 25 display_check + 25b display_bisect (EUD ERROR 좁히기) | E6-3* | CRASH_RISK |
| 25 display_check + 25b display_bisect (마린 선택) | E6-4* | CRASH_RISK |
| 25 display_check + 25b display_bisect | E6-4b | CRASH_RISK |
| M1_multi (확인 코드 추가) | F19-2 | MULTI |
| M1_multi (싱글 값은 auto_all phase 12 에서 참고로 기록) | F19-1b | MULTI |
| 별도: 해상도 두 가지로 여는 맵 | F19-3 | AUTO_ASSIST |
| 17 exit_trap (위험, 2인) | F19-4* | CRASH_RISK |
| 18 sprite (위험) | F21-1*, F21-2*, F21-3*, F21-4*, F21-5*, F21-6*, F21-7*, F21-9 | CRASH_RISK |
| (별도 멀티) | F21-11 | MULTI |

(* = 필수) 통합 맵 밖 eudext 항목 72개.

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

### AUTO (87)

| ID | 절 | 맵 | 보조 | 판정(기대) | 완료 표식 | bundle | phase |
|---|---|---|---|---|---|---|---|
| A-1 **[필수]** | 1.2 (필수) | 01 S8_SubtractTest |  | SUBX 에서 5/5 인 모형 하나, ADDX 에서 3/3 인 모형 하나(에뮬레이터 가정은 A2·M). 리더가 S8_subtract.md 8절 표로 got 값에서 모형을 다시 계산해 이름을 기록. 둘 다 없으면 got 17개를 그대로 기록 | 통합 맵: aa.s8.end > 0 (phase 4 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m01.done = run_tests 를 마친 프레임(첫 프레임) | auto_all | 4 |
| A-2 | 1.3 (권장) | 26 switch_check |  | 0x58DC40 = 0x80000005(2147483653), 0x58DC44 = 0x00000081(129), cond1 = cond2 = 1 | 통합 맵: aa.switch.end > 0 (phase 3 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m26.tick >= 48 (첫 판정 뒤) | auto_all | 3 |
| A-3 **[필수]** | 1.2 (필수) | 19 spawn_check | VISUAL | 17번: 워프 유닛 명령 목표 = 로케이션 14 중심 (2731, 2048) — (2048, 2048)=13 이면 오프바이원. 18번: 보스 위치 ≈ (2731, 2048) (±32). 19번(E12-4): 마커 5기 x 평균 ≈ 3413(로케이션 15) | 통합 맵: aa.spawn.end > 0 (phase 14 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m19.frame >= PH3 + 20 (= 620) | auto_all (값) + 화면: 통합 맵을 지켜보거나 19 | 14 |
| B1-1 | 1.3 (권장) | 05 cmp_check |  | 15 / 15 | 통합 맵: aa.cmp_cell.end > 0 (phase 10 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m05.done (tick == 24 이후) | auto_all | 10 |
| B8-4 | 1.3 (권장) | 20 players_check (계측 추가 → auto_all) |  | setcurpl(P3) → run_as(Everyone, …) 뒤 SetResources(CurrentPlayer, Add, 1, Ore) 가 P3 광물 +1, foreach(pl.each(Humans)) 뒤에도 +1 (합 +2) | 통합 맵: aa.players.end > 0 (phase 12 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m20b.done | auto_all | 12 |
| B10-1 **[필수]** | 1.2 (필수) | 03 units_ingame | CRASH_RISK | (a) T4 첫 CC ok=1, 겹친 CC ok=0, 머리 전 = 후. (b) T9 마지막 ok=0 ptr=0 idx=1700 머리=1700, 채운 수 기록(한도가 1700 이 아니면 그 수) | 통합 맵: aa.units.end > 0 (phase 1 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): (a) frame >= 4, (b) frame >= 31 | auto_all (a) + X_limit (b 한도) | 1 |
| B10-2 **[필수]** | 1.2 (필수) | 03 units_ingame |  | ok=1, idx = index(머리 전), 종류=0, 주인=0, 주문≠0, 머리 후 = 전 + 1(보통 — 다르면 기록) | 통합 맵: aa.units.end > 0 (phase 1 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 1 | auto_all | 1 |
| B10-3 | 1.3 (권장) | 03 units_ingame |  | 종류=3, 서브 종류=4, 서브 칸 = idx+1(아니면 기록), 머리 = idx+2 | 통합 맵: aa.units.end > 0 (phase 1 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 2 | auto_all | 1 |
| B10-4 | 1.3 (권장) | 03 units_ingame |  | ok=1, 머리 = 첫 칸 + 3 | 통합 맵: aa.units.end > 0 (phase 1 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 3 | auto_all | 1 |
| B10-5 **[필수]** | 1.2 (필수) | 03 units_ingame |  | F1 = 64(리빌러) + 시작 위치 유닛(0 또는 2, 기록) + 1(T1), F2 = 2(골리앗 + 터렛 — 1 이면 터렛이 새 유닛으로 안 나옴, 기록), F3 = 3, F4 = 1, F5 = 0, F6 = 1, F7 = 1, F8~F12 = 0 | 통합 맵: aa.units.end > 0 (phase 1 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 12 | auto_all | 1 |
| B10-6 | 1.3 (권장) | 03 units_ingame |  | 판정 아님 — 사실 기록: 주문이 0 이 되는 프레임, 스프라이트가 0 이 되는 프레임, 새 칸(T8)이 죽은 칸이면 '앞으로 돌려줌', 아니면 '끝'. CC(RemoveUnitAt) 죽음 알림 1회 | 통합 맵: aa.units.end > 0 (phase 1 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 45 | auto_all | 1 |
| B10-7 | 1.3 (권장) | 03 units_ingame |  | 새 유닛이 죽은 칸에 들어갔을 때만 고유 바이트 +1 (사실 기록) | 통합 맵: aa.units.end > 0 (phase 1 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 24 | auto_all | 1 |
| B10-8 | 1.3 (권장) | 03 units_ingame | CRASH_RISK | F8 에 마린 6마리 죽음 알림 6줄(한 번씩), CC 알림 1회, mark=0 tag=0. (한도 부분) F32 뒤 합계가 프레임마다 40씩 늘다 멈춤 | 통합 맵: aa.units.end > 0 (phase 1 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 45 (한도 부분은 X_limit 에서 frame >= 80) | auto_all + X_limit (limit=40 부분) | 1 |
| B10-10 | 1.3 (권장) | 03 units_ingame |  | removeTimer 쓰기 뒤 읽은 값 0 | 통합 맵: aa.units.end > 0 (phase 1 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 50 | auto_all | 1 |
| B13-9 | 1.3 (권장) | 21 sync_check | MULTI, EXTERNAL, CRASH_RISK | 10분 이상 멈춤 없음. (빌드 쪽) 유닛 49 를 놓은 사본은 sync.verify 로 빌드가 멈춤 — 게임 불필요 | 게임 프레임 >= 14400 | 21 sync (싱글 가능, 키 조작) |  |
| B15-1 **[필수]** | 1.2 (필수) | 04 datpatch_check |  | 128·192·256(폭발형 × 소형·중형·대형)이 0x515BA0 에서 시작하면 0x515B88 이 맞음, 0x515B9C 에서 시작하면 0x515B84(eudplib 주석)가 맞음. 시작 주소를 기록 | 통합 맵: aa.datpatch.end > 0 (phase 5 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m04.done (frame >= 24, 시작 목록 적용 뒤) | auto_all | 5 |
| B15-3 | 1.3 (권장) | 04 datpatch_check | EXTERNAL | 사실 기록: 시작 직후 40/80(현재 HP 그대로) 인지 80/80 인지 | 통합 맵: aa.units.end > 0 (phase 1 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 30 | auto_all (기준 맵에 파이어뱃 한 기) | 1 |
| B15-4 | 1.3 (권장) | 04 datpatch_check | AUTO_ASSIST | 시작 목록으로 바꾼 값이 몇 분 뒤에도 그대로(게임이 되돌리면 기록). 저장·불러오기 뒤 값은 사람이 저장/불러오기를 한 뒤 자동 비교 | 통합 맵: aa.datpatch.end > 0 (phase 5 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): 게임 프레임 >= 2880 (2분) | auto_all (시간 부분; 저장·불러오기 부분은 별도) | 5 |
| B15-5 | 1.3 (권장) | 01 S8 (A-1 결과) |  | A-1 에서 정한 마스크 Add/Subtract 식이 에뮬레이터 식과 같은가(게임 불필요) | 통합 맵: aa.s8.end > 0 (phase 4 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): A-1 판정 뒤 | auto_all | 4 |
| C2-1 | 1.3 (권장) | 06 cell_check |  | 18 / 18 | 통합 맵: aa.cmp_cell.end > 0 (phase 10 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m06.done (tick == 24 이후) | auto_all | 10 |
| C3-1 **[필수]** | 1.2 (필수) | 02 i64_check |  | 0, 0, 2147483647 (5−0xFFFFFFFF 가 6 이면 부호 있는 비교 — 값 그대로 기록) | 통합 맵: aa.i64.end > 0 (phase 6 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m02.done (run_tests 끝) | auto_all | 6 |
| C3-2 **[필수]** | 1.2 (필수) | 02 i64_check |  | res 3~8 = 4294967295, 0, 2, 0, 0, 9800000000 / 9~12 = 4294967295, 0, 2, 0 / 13~15 = 4294967295, 0, 2 → 비트 3~15 모두 1 | 통합 맵: aa.i64.end > 0 (phase 6 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m02.done | auto_all | 6 |
| C3-3 | 1.3 (권장) | 02 i64_check | VISUAL | 23 / 23, 10진 출력 18446744073709551615·-1 등 기대 문자열과 같음 | 통합 맵: aa.i64.end > 0 (phase 6 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m02.done | auto_all | 6 |
| C9-2 | 1.3 (권장) | 07 mathx_check |  | 110 / 110, 그룹별 19·8·4·15·6·16·9·9·10·7·7, 표본 (70,70) 46 9 (FFFFFFAA,FFFFFFCF) | 통합 맵: aa.mathx.end > 0 (phase 11 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m07.frame >= 20 | auto_all | 11 |
| C11-1 **[필수]** | 1.2 (필수) | 08 pool_check |  | t1ok = 1, visits1 = frame × 5, bad1 = 0 (여러 프레임 동안 유지). 맵이 멈추면 멈춤으로 기록 | 통합 맵: aa.pool.end > 0 (phase 2 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m08.frame >= 60 (1초 넘게 유지) | auto_all | 2 |
| C11-2 | 1.3 (권장) | 08 pool_check | VISUAL | count 36, dropped 1, t2ok 1, 버퍼에 'ERROR : Over…' 한 줄. Buzz 3번은 귀로 | 통합 맵: aa.pool.end > 0 (phase 2 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 12 | auto_all | 2 |
| C11-3 | 1.3 (권장) | 08 pool_check |  | 1234, 1234, 1345, 345 / t3bad 0 / t3ok 1 | 통합 맵: aa.pool.end > 0 (phase 2 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 12 | auto_all | 2 |
| C11-4 | 1.3 (권장) | 08 pool_check |  | 99, 11, 1, 0, 1, 132, 판정 1 | 통합 맵: aa.pool.end > 0 (phase 2 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 12 | auto_all | 2 |
| C11-5 | 1.3 (권장) | 08 pool_check | VISUAL | count 10, 판정 1. 끊김 체감(원본 건작 맵 대비)은 사람 — 브리지는 프레임/초만 기록 | 통합 맵: aa.pool.end > 0 (phase 2 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 12 | auto_all | 2 |
| C11-6 | 1.3 (권장) | 08 pool_check |  | visits6 ≥ 1, t6bad 0, 판정 1 | 통합 맵: aa.pool.end > 0 (phase 2 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 12 | auto_all | 2 |
| C11-7 | 1.3 (권장) | 08 pool_check | VISUAL | 방문 1, count 0, 판정 1, 'ERROR : Kind…' 한 줄. Buzz 2번은 귀로 | 통합 맵: aa.pool.end > 0 (phase 2 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 12 | auto_all | 2 |
| C11-9 | 1.3 (권장) | 19 spawn_check (E12-1 로 대신) |  | 건작 본문 spawn 호출 → 중심 = 레코드 x, y (E12-1 anchor 와 같은 방식) | 통합 맵: aa.spawn.end > 0 (phase 14 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): E12-1 판정 뒤 | auto_all | 14 |
| D4-1 | 1.3 (권장) | 15 i64_ops_check |  | 56 / 56 (+ fmt 문자열 자체 점검 통과) | 통합 맵: aa.i64_ops.end > 0 (phase 7 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m15.done (run_tests 끝) | auto_all | 7 |
| D5-1 **[필수]** | 1.2 (필수) | 16 numfmt_check |  | 23 / 23, 틀린 번호 0, 셀 왕복 1 | 통합 맵: aa.numfmt.end > 0 (phase 9 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m16.done (run_tests 끝) | auto_all | 9 |
| D5-9 | 1.3 (권장) | 16 numfmt_check | VISUAL | 색 코드를 뗀 두 이름 바이트가 같음(16바이트까지), 첫 바이트 색 0x08, 셀 왕복 1. 빨간색은 눈 | 통합 맵: aa.numfmt.end > 0 (phase 9 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m16.done | auto_all | 9 |
| D5-10 | 1.3 (권장) | 16 numfmt_check | VISUAL | 약 31,000 트리거 프레임의 시간 기록(묶음에서는 frame 150 으로 옮김). 체감은 사람 | 통합 맵: aa.numfmt.end > 0 (phase 9 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m16.done | auto_all (단독 첫 프레임 수치가 필요하면 16) | 9 |
| D7-1 **[필수]** | 1.2 (필수) | 12 plot_check | VISUAL | ①원 19·②별 31·③④⑤막대 5씩: 만든 유닛 위치가 중심 + 도형 좌표(shapes.point_at)와 순서까지 같음(posbad 0, orderbad 0). 원 두 번째 점이 (0, −32)=12시, ⑤ = ④ 좌표. 사진 한 장은 선택 | 통합 맵: aa.plot.end > 0 (phase 13 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m12.frame >= 121 | auto_all (값) + 화면: 통합 맵을 지켜보거나 12 | 13 |
| D7-2 | 1.3 (권장) | 12 plot_check | VISUAL | 왼쪽(pF) 6,6,6,1 개가 4프레임에 끝, 오른쪽(pG) 8프레임마다 6개씩 25프레임에 끝 — 자체 점검 busy/done 과 함께 | 통합 맵: aa.plot.end > 0 (phase 13 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= PH2 + 24 | auto_all (값) + 화면: 통합 맵을 지켜보거나 12 | 13 |
| D7-3 | 1.3 (권장) | 12 plot_check | VISUAL | 4프레임마다 열 하나: 1,1,1,3,3,3,5,5,7,5,5,3,3,3,1,1,1 (가운데 열도 같은 박자) | 통합 맵: aa.plot.end > 0 (phase 13 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= PH3 + 64 | auto_all (값) + 화면: 통합 맵을 지켜보거나 12 | 13 |
| D7-4 | 1.3 (권장) | 12 plot_check |  | 원 3번, 만든 점 211 | 통합 맵: aa.plot.end > 0 (phase 13 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= PH5 | auto_all | 13 |
| D7-5 | 1.3 (권장) | 12 plot_check |  | 15 / 15 | 통합 맵: aa.plot.end > 0 (phase 13 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= PH5 (540) | auto_all | 13 |
| D14-1 **[필수]** | 1.2 (필수) | 10 bullet_check | VISUAL | 8방향 모두 facing = 기대, 진행 방향 = heading(h) (facing + 128 쪽, ±8), 표적 죽음 1. 방향이 facing 쪽이면 반대로 기록 | 통합 맵: aa.bullet.end > 0 (phase 15 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m10.frame >= 216 | auto_all (값) + 화면: 통합 맵을 지켜보거나 10 | 15 |
| D14-2 **[필수]** | 1.2 (필수) | 10 bullet_check | VISUAL, CRASH_RISK | 8발 facing = 기대·진행 방향이 표적 쪽·표적 죽음 1, 가까운 목표 facing = to_dir256(atan2(2,1)), 먼 목표 192, 출발=목표 128. 먼 표적 죽음은 사거리에 따라 0 가능(기록) | 통합 맵: aa.bullet.end > 0 (phase 15 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m10.frame >= 480 | auto_all (값) + 화면: 통합 맵을 지켜보거나 10 / 출발=목표 한 발은 X_limit | 15 |
| D14-4 | 1.3 (권장) | (10 에 없음) |  | 같은 프레임 같은 flingy 두 발이 모두 마지막 속도(4000)로 나가는지 기록(문서화용) | 통합 맵: aa.bullet.end > 0 (phase 15 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): - | auto_all | 15 |
| D14-5 | 1.3 (권장) | 10 bullet_check | VISUAL | (1000, 3400), (1200, 3410) | 통합 맵: aa.bullet.end > 0 (phase 15 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 492 | auto_all | 15 |
| D14-7 | 1.3 (권장) | 10 bullet_check | VISUAL | 사실 기록: 수명 안 씀 쪽이 남는지(주문·스프라이트 ≠ 0), 수명 12 쪽은 사라짐(0) | 통합 맵: aa.bullet.end > 0 (phase 15 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 576 | auto_all | 15 |
| D17-2 **[필수]** | 1.2 (필수) | 13 chat_check | VISUAL | 세 줄 모두 표식이 변환되어 같은 프레임부터 동시에 한 셀씩 드러남(짝·홀 slot 섞임, 홀수는 +2 바이트부터) | 통합 맵: aa.chat.end > 0 (phase 17 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 170 | auto_all | 17 |
| D17-4 **[필수]** | 1.2 (필수) | 13 chat_check | VISUAL | 짝수 slot 은 212바이트, 홀수 slot 은 214바이트 자리에 NUL → 콜론 뒤 남는 글자 12 / 14 개(16개면 NUL 안 먹음). 줄 꺾임은 눈 | 통합 맵: aa.chat.end > 0 (phase 17 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 300 | auto_all | 17 |
| D17-5 | 1.3 (권장) | 13 chat_check |  | 드러난 셀이 52칸(지운 !H 2칸 포함)에서 멈추고 숫자가 …890123 에서 끝남 | 통합 맵: aa.chat.end > 0 (phase 17 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 450 | auto_all | 17 |
| D17-9 | 1.3 (권장) | 13 chat_check |  | 타자기 A 가 1프레임 1글자(드러난 셀 수 증가 = 프레임 증가), D17-5 50자에 걸린 벽시계 초(가장 빠름 약 2초) | 통합 맵: aa.chat.end > 0 (phase 17 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 450 | auto_all | 17 |
| E6-8 **[필수]** | 1.2 (필수) | 25 display_check |  | 7 / 7, 틀린 번호 0 | 통합 맵: aa.display.end > 0 (phase 16 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 1 | auto_all | 16 |
| E6-5 **[필수]** | 1.2 (필수) | 25 display_check | VISUAL | 네 이름 바이트가 같음(색 코드 제외, name20 은 16바이트까지). P1 색(빨강)은 눈 | 통합 맵: aa.display.end > 0 (phase 16 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): page 4 | auto_all | 16 |
| E6-10 | 1.3 (권장) | 25 display_check | VISUAL | every=24 줄이 같은 slot 에 머물고 숫자가 24프레임마다 한 번 바뀜 | 통합 맵: aa.display.end > 0 (phase 16 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): page 7 | auto_all | 16 |
| E12-1 **[필수]** | 1.2 (필수) | 19 spawn_check | VISUAL | 만든 저글링 = N1 + N2(각 32, 합 64), 넘침 0, 생성 순간 위치 불일치 0, 명령 목표 (2048, 3413). 가장자리에서 밀려남은 몇 프레임 뒤 위치로 기록(눈 확인은 선택) | 통합 맵: aa.spawn.end > 0 (phase 14 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m19.frame >= 27 | auto_all (값) + 화면: 통합 맵을 지켜보거나 19 | 14 |
| E12-2 **[필수]** | 1.2 (필수) | 19 spawn_check | VISUAL | 히드라가 한 프레임에 한 열씩 18프레임(빈 6열 포함 끊김 없음), 옵저버 같은 박자 세 번(0·18·36), parked 73, vis 219, 풀리기 전 무적 비트 1 → PH2+150 뒤 0. 원본과 페이드 속도 나란히 비교는 사람 | 통합 맵: aa.spawn.end > 0 (phase 14 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m19.frame >= PH2 + 160 | auto_all (값) + 화면: 통합 맵을 지켜보거나 19 (원본과 페이드 비교) | 14 |
| E12-3 **[필수]** | 1.2 (필수) | 19 spawn_check | VISUAL | 층 프레임 차 2·2·2, boss 1(로케이션 14), marks 5, 네 층 유닛 명령 목표 = 로케이션 14 (2731, 2048), 36점 위치 불일치 0 | 통합 맵: aa.spawn.end > 0 (phase 14 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m19.frame >= PH3 + 20 | auto_all (값) + 화면: 통합 맵을 지켜보거나 19 | 14 |
| E12-4 | 1.3 (권장) | 19 spawn_check (화면 줄 [A-3]) |  | 피닉스 5기 가로줄 중심 (3413, 2048) = 로케이션 15 (14 나 16 이면 다름) | 통합 맵: aa.spawn.end > 0 (phase 14 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= PH3 + 20 | auto_all | 14 |
| E12-5 | 1.3 (권장) | 19 spawn_check (화면 줄 [E12-4]) | VISUAL | 스커지 10기 위치의 각도가 12시에서 시작해 시계 방향으로 늘어남(각 차 부호 일정) | 통합 맵: aa.spawn.end > 0 (phase 14 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= PH5 | auto_all (값) + 화면: 통합 맵을 지켜보거나 19 | 14 |
| E12-6 | 1.3 (권장) | 19 spawn_check (화면 줄 [E12-5]) | VISUAL | 브루들링 19마리가 로케이션 8 에 생기고 목표 로케이션 18 순찰, 약 15프레임 뒤 수 0 | 통합 맵: aa.spawn.end > 0 (phase 14 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= PH5 + 30 | auto_all (값) + 화면: 통합 맵을 지켜보거나 19 | 14 |
| E12-8 | 1.3 (권장) | 19 spawn_check (화면 줄 [E12-7]) |  | 11 / 11, 남은 작업 0 | 통합 맵: aa.spawn.end > 0 (phase 14 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= PH7 | auto_all | 14 |
| F20-1 | 1.3 (권장) | 24 i128_check |  | 46 / 46 (+ 39자리 10진 fmt 자체 점검) | 통합 맵: aa.i128.end > 0 (phase 8 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): m24.done (run_tests 끝) | auto_all | 8 |
| S0-2 | 3 (UE_RE S0) | UE_RE_S0_eudext.scx (③) (①은 눈) | VISUAL | 13번째 줄 '[LV.xxx - 00h 00m 00s]' 의 초가 벽시계 1초에 1씩(±5%) 바뀜 — 리더가 글에서 숫자를 뽑아 비교 | 게임 시작 뒤 90초 | port:UE_RE ③ |  |
| S0-18 | 3 (UE_RE S0) | UE_RE_S0_eudext.scx (③) | MULTI | 약 4초(96 사이클)에 '[eudext S0] … 하이브리드 빌드' 줄이 버퍼에 정확히 한 번, s0.shown = 1. 관전자 확인은 멀티 | s0_cycles >= 97 | port:UE_RE ③ |  |
| T0-1 | 4 (theSeed S0) | theSeed_eud_S0_t1 (승인 닉네임) | CRASH_RISK | 60초 동안 seq 계속, 패배 발동 0, LimitC = 1, GameStartDone = 1 (10초 뒤) | 게임 시각 60초 | port:theSeed t1 |  |
| T0-3 | 4 (theSeed S0) | theSeed_eud_S0_t0_noprobe | AUTO_ASSIST | 아무 닉네임으로 패배 없이 계속, Y 를 눌러도 버퍼에 [S0] 줄 없음 | 게임 시각 30초 | port:theSeed t0 |  |
| T0-6 | 4 (theSeed S0) | theSeed_eud_S0_t1 | VISUAL | 10초 전 P8→P1 시야 비트 1·지도탐색기 72, 10초 뒤 비트 0·지도탐색기 0. 미니맵 어두워짐은 눈 | 게임 시각 15초 | port:theSeed t1 |  |
| T0-7 | 4 (theSeed S0) | theSeed_eud_S0_t2 |  | 10초가 지나도 P8→P1 시야 비트 1 유지 | 게임 시각 15초 | port:theSeed t2 |  |
| T0-13 | 4 (theSeed S0) | theSeed_eud_S0_t1 | CRASH_RISK | 10분 동안 멈춤 없음, GameTimeSec 증가 = 게임 시간(프레임 기준)과 일치 | 게임 시각 600초 | port:theSeed t1 |  |
| S1-1-2 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | VISUAL | 300사이클에 유닛 96 이 방장에게 1기(로케이션 10), 안내 두 줄. scanr 소리는 귀 | 사이클 310 | port:RV S1 |  |
| S1-1-7 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) |  | 아무것도 안 고르면 2000사이클에 NM(난이도 값) 으로 시작 | 사이클 2010 | port:RV S1 |  |
| S1-3-5 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | MULTI | 평범한 설정(1인 LAN)에서 60초 동안 튕기지 않음, 버퍼에 '경고: '/'WARNING: ' 줄 없음 | 게임 시각 60초 | port:RV S1 |  |
| S1-3-7 | 5.1 (Respect V 1단계) | Respect_V_eud_S1_T1.scx (GALAXY_BURST / Natori_sana) | CRASH_RISK | 튕기지 않음, 소개 글에 'TESTMODE OP : 0 Shapes Initiated' | 사이클 300 | port:RV T1 |  |
| S1-4-1 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | VISUAL, EXTERNAL | 이름 바이트가 '[Creator] GALAXY_BURST' / '[Creator] 名取さな' 형식(색 코드 포함 — 원본 문자열과 바이트 대조) | 사이클 100 | port:RV S1 |  |
| S1-5-2 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | MULTI | GS 뒤 각 사람 +(1억 ÷ p + 5000), 공유 켜짐, 모든 사람 광물 = 팀 합계. 1인 판이면 시작 광물 + 100,005,000 | gs 뒤 2초 | port:RV S1 |  |
| S1-5-4 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | AUTO_ASSIST | GS 뒤 첫 고정 줄 '『 CreateUnitQueue : 0 ‖ Penalty Timer : 0 / 4800 』' + 인원별 줄, 채팅을 쳐도 slot 불변 | gs 뒤 5초 | port:RV S1 |  |
| S1-5-5 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | VISUAL | 공유 줄의 이름 = 칭호가 붙은 실시간 이름(바이트 일치). 원본과 같은지는 눈 | gs 뒤 5초 | port:RV S1 |  |
| S1-5-6 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | VISUAL | 공유 중 유닛 51 생산 불가(매 프레임) | gs 뒤 | port:RV S1 |  |
| S1-6-2 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | VISUAL | 곡 길이 타이머가 음원 실측 길이만큼 흐른 뒤 요청 가능 상태(1단계는 다음 요청이 없어 조용) | 곡 길이 + 5초 | port:RV S1 |  |
| S1-7-1 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) |  | 시작 속도 0x1D, GS 에 SpeedVar 4 + '#X2.0' 문구, 속도 칸은 0x1D 그대로 | gs 뒤 2초 | port:RV S1 |  |
| S1-7-5 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | MULTI | 최대 인구(내부값) = 1800 ÷ 사람 수 — 1인이면 1800, GS·퇴장 때 다시 계산(퇴장은 멀티) | gs 뒤 | port:RV S1 |  |
| S1-7-6 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) |  | 프로토스 최대 1200(내부), 저그 사용 칸 = 맵의 유닛 수 | gs 뒤 | port:RV S1 |  |
| S1-7-7 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) |  | 사람 유닛 에너지가 늘 최대 | gs 뒤 10초 | port:RV S1 |  |
| S1-8-2 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | MULTI | 사람끼리 동맹·시야, P6~P8 서로 시야(표 자동). 나간 사람(P12) 마린 죽음은 멀티 | gs 뒤 | port:RV S1 |  |
| M2-S0-2 | 5.2 (Memory 2 S0) | Mem2_S0_eudext.scx | VISUAL | 데스 181 누적이 방장 PC 실시간과 같은 빠르기(벽시계 대비 ±5%). 오프닝 빠르기 원본 비교는 눈 | 게임 시작 뒤 60초 | port:Mem2 eudext |  |
| M2-S0-9 | 5.2 (Memory 2 S0) | Mem2_S0_eudext.scx | MULTI | 약 4초에 '[eudext S0] Memory 2 …' 줄이 정확히 한 번(eudext 판만) | 사이클 97 | port:Mem2 eudext |  |
| M1-S0-4 | 5.3 (Memory 1 S0) | Mem1_S0_A.scx | VISUAL | 데스 180 누적이 실시간과 같은 빠르기, 10분에 Switch 2 켜짐. 13번째 줄 표시는 눈 | 게임 시각 610초 | port:Mem1 |  |
| M1-S0-18 | 5.3 (Memory 1 S0) | Mem1_S0_C.scx | CRASH_RISK, MULTI | 약 4초(96 사이클)에 '[eudext S0] Memory 1 …' 줄이 정확히 한 번 | 사이클 97 | port:Mem1 C |  |

### AUTO_ASSIST (29)

| ID | 절 | 맵 | 보조 | 판정(기대) | 완료 표식 | bundle | phase |
|---|---|---|---|---|---|---|---|
| B13-3 | 1.3 (권장) | 21 sync_check | MULTI | 누르는 동안만 held 증가, 떼면 멈춤. 톡 치기(한 턴 안)에서는 held 불변, 점수 +1 이 빠지는 빈도 기록. SPACE 누른 채 채팅창 열고 떼기 → held 멈춤 | 사용자 조작 끝(리더에 표시) | 21 sync (싱글 가능, 키 조작) |  |
| B13-4 | 1.3 (권장) | 21 sync_check | MULTI | 동기 값이 로컬 좌표를 몇 프레임 늦게 따라오는지(지연 프레임 수 기록), 마우스를 멈춘 동안 값이 흔들리거나 0 으로 튀지 않음 | 조작 뒤 | 21 sync (싱글 가능, 키 조작) |  |
| B13-5 | 1.3 (권장) | 21 sync_check |  | 채팅창 열린 동안 SPACE·LCTRL+좌클릭 → 점수 불변, TAB → panel 불변, F5 는 출력됨 | 조작 뒤 | 21 sync (싱글 가능, 키 조작) |  |
| B13-6 | 1.3 (권장) | 21 sync_check | MULTI | F5 를 오래 눌러도 출력 1회(누름 1회당), 우클릭 1회당 1줄. 두 PC 는 각자 화면에만 | 조작 뒤 | 21 sync (싱글 가능, 키 조작) |  |
| B13-8 | 1.3 (권장) | 21 sync_check | MULTI | 유닛 여러 기 선택 → SPACE·좌클릭 뒤에도 선택 표가 같고 QC 유닛(49) 포인터가 섞이지 않음. 부대 지정 뒤에도 | 조작 뒤 | 21 sync (싱글 가능, 키 조작) |  |
| B15-6 | 1.3 (권장) | 04 datpatch_check (변형) | VISUAL | restore=False 로 프레임을 넘긴 temporary 뒤 unpatch_all 로 되돌아가고, 그 사이 저장·불러오기·리플레이 재생에서 값·진행이 정상 | 조작 뒤 | 별도: 저장·불러오기·리플레이 변형 맵 |  |
| D14-6 **[필수]** | 1.2 (필수) | 10 bullet_check | VISUAL, AUTO | ①~⑤ 각각: 클릭 선택됨/드래그 선택됨(선택 표에 epd 포인터가 있나), 서로 밀림(위치 변화 px), 칸 값(만든 직후·ue_re 뒤). 안개 속 보임은 눈 | 통합 맵: aa.bullet.end > 0 (phase 15 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame 516 ~ 756 (10초) | auto_all (값·위치) + 사람 클릭·드래그(선택, 10초) | 15 |
| D17-6 **[필수]** | 1.2 (필수) | 13 chat_check | VISUAL | ① 그 줄이 이름 없이 '안녕 éè 가나다' 로 한 셀씩 다시 드러남(스냅숏) ② 원문 앞 12바이트 3개·표식 위치 N 기록(chatmodel 수정용) ③ 보통 채팅 줄은 그대로 | 통합 맵: aa.assist.end > 0 (phase 19 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): relayed >= 1 뒤 60프레임 | auto_all assist 구간(선택) / 13 | 19 |
| E6-2 | 1.3 (권장) | 25 display_check | VISUAL | 고정 줄 두 개가 같은 slot 에 머물고 숫자만 바뀜 — 사람이 채팅을 몇 번 친 뒤에도(자동: slot 번호 불변) | 통합 맵: aa.assist.end > 0 (phase 19 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): 채팅 뒤 5초 | auto_all assist 구간(선택) / 25 | 19 |
| F19-3 | 1.3 (권장) | (확인 맵 없음) | EXTERNAL | 4:3 에서 0, 와이드에서 1, 판정 뒤 화면 위치가 원래대로 | - | 별도: 해상도 두 가지로 여는 맵 |  |
| S0-5 | 3 (UE_RE S0) | UE_RE_S0.scx (①) | VISUAL | ESC·F9·F12·TAB·Z·Shift+←/→·백틱·1~7·Q/E 누를 때마다 해당 채널 받은 수 +1 (빠뜨림 0, 두 번 0). 상점 구매·콘솔 선택 결과는 눈 | 사용자 조작 끝 | port:UE_RE ① |  |
| S0-7 | 3 (UE_RE S0) | UE_RE_S0.scx (①) | VISUAL | @칭호 1~4 채팅 뒤 chatEvent 칸 값 2~5, 숫자 채팅 뒤 기부 금액만큼 광물 이동. 문구·이름 앞 칭호는 눈 | 채팅 뒤 3초 | port:UE_RE ① |  |
| T0-8 | 4 (theSeed S0) | theSeed_eud_S0_t1 |  | Y 누름 엣지마다 yCount[P1] +1, 스위치 199 뒤집힘, [S0] 줄 1개 (누락 0·두 번 0) | 사용자 조작 끝 | port:theSeed t1 |  |
| T0-9 | 4 (theSeed S0) | theSeed_eud_S0_t1 |  | 채팅창이 열린 동안 Y 를 쳐도 yCount 불변, [S0] 줄 없음 | 사용자 조작 끝 | port:theSeed t1 |  |
| T0-10 | 4 (theSeed S0) | theSeed_eud_S0_t1 |  | 값 줄 켜진 동안 lastX[P1] 이 로컬 X 를 따라가고 recvCount 증가, 꺼진 동안 불변 | 사용자 조작 끝 | port:theSeed t1 |  |
| T0-11 | 4 (theSeed S0) | theSeed_eud_S0_t1 | VISUAL | 5초 안 8번 → 소리 5번에서 멈춤(budget 5), 쉬고 나면 0부터. 소리는 귀 | 사용자 조작 끝 | port:theSeed t1 |  |
| S1-1-4 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | VISUAL | 선택 유닛을 로케이션 11 로 → EVF 유닛 0, evf=1, 전체 문구. ADEnd 는 귀 | 이동 뒤 2초 | port:RV S1 |  |
| S1-1-5 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) |  | 로케이션 48 → OM 유닛 0, om=1, 문구 | 이동 뒤 2초 | port:RV S1 |  |
| S1-1-6 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | VISUAL | 비콘 → 난이도 값, gs=1, 선택·난이도·옵션 유닛 0, 광물 증가(1억모드 식 — S1-5-2). bnetclick 은 귀 | gs == 1 | port:RV S1 |  |
| S1-1-8 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | VISUAL | SC 선택 → P6·P7·P8 색 188·160·173, 컴퓨터 업그레이드 단계 SC 6·3·3 (HD 2·1·1, MX 4·2·2 는 각 판에서). 원본과 나란히는 눈 | gs == 1 | port:RV S1 |  |
| S1-3-8 | 5.1 (Respect V 1단계) | Respect_V_eud_S1_T2.scx | VISUAL, CRASH_RISK | 방장만 62·63 생산 가능(표), 난이도 뒤 BGM 요청 없음(TestStart). 들리지 않는지는 귀 | gs 뒤 | port:RV T2 |  |
| S1-4-2 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | VISUAL, MULTI | 3·7 한 번씩 → 인식 1, 그 PC 에만 문구, 소리 2번(귀), 다시 눌러도 안 나옴. 칭호 없는 사람은 멀티 | 조작 뒤 | port:RV S1 |  |
| S1-6-3 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | VISUAL | 유닛 3 생산 → 끔 비트 1 + 'BGM 을 듣지 않습니다.', 다시 → 0 + '듣습니다.' | 조작 뒤 | port:RV S1 |  |
| S1-6-4 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | VISUAL | 끈 동안에도 곡 시간이 흐르고, 켠 뒤 그 곡이 끝나야 다음 요청(X13), 끄기는 다음 프레임부터(X14) | 조작 뒤 | port:RV S1 |  |
| S1-6-6 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | VISUAL | F10 일시정지 수 초 뒤 재개: 2.5초 넘는 경과는 0(X15) — 곡 시간이 일시정지만큼 건너뛰지 않음. 겹침은 귀 | 조작 뒤 | port:RV S1 |  |
| S1-7-2 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | VISUAL | 비콘 43~46 → SpeedVar 4·6·8·10 + 문구. 체감 속도가 원본과 같은지는 사람(브리지 프레임/초는 보조) | 조작 뒤 | port:RV S1 |  |
| S1-7-3 | 5.1 (Respect V 1단계) | Respect_V_eud_S1_T2.scx | MULTI | 방장이 62/63 생산 → +1/−1(1~11 안) + 문구. 방장 아닌 사람 불가는 멀티, 정식판은 모두 불가 | 조작 뒤 | port:RV T2 |  |
| M2-S0-3 | 5.2 (Memory 2 S0) | Mem2_S0_eudext.scx | VISUAL, AUTO | 방장 유닛(60·23)으로 난이도·모드·배속 선택(사람), 60초 뒤 모드 유닛 수 0(자동). 표시·배속은 눈 | 게임 시각 70초 | port:Mem2 eudext |  |
| M1-S0-3 | 5.3 (Memory 1 S0) | Mem1_S0_A.scx | VISUAL | TAB/ESC 누름 엣지마다 데스 206/205 처리 한 번(두 번·빠뜨림 없음), 첫 사람만. 선택 글·색·소리는 눈 | 조작 뒤 | port:Mem1 |  |

### VISUAL (72)

| ID | 절 | 맵 | 보조 | 판정(기대) | 완료 표식 | bundle | phase |
|---|---|---|---|---|---|---|---|
| B15-7 | 1.3 (권장) | 04 datpatch_check (두 변형) | EXTERNAL | 유닛 선택 음성이 기존 TEP 맵과 같은 쪽(SetUnitsDatX 판 / set 판) | - | 별도: 두 변형 맵(소리) |  |
| B15-10 | 1.3 (권장) | 04 datpatch_check | AUTO | 버튼 활성 동작이 기존 맵과 같음(눈). 칸 값이 매 프레임 0 인지는 자동 | 통합 맵: aa.datpatch.end > 0 (phase 5 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 24 | auto_all | 5 |
| D5-2 | 1.3 (권장) | 16 numfmt_check | AUTO | [00042] [-1,234,567] [+0,001,234] 가 기대 줄과 같게 보임 (바이트는 D5-1 이 판정) | 통합 맵: aa.visual.end > 0 (phase 20 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): - | auto_all visual 구간(선택) / 16 | 20 |
| D5-3 | 1.3 (권장) | 16 numfmt_check |  | 전각 숫자 사이 빈틈 없음, 앞 0x0D×4 가 자리를 차지하지 않음 | 통합 맵: aa.visual.end > 0 (phase 20 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): - | auto_all visual 구간(선택) / 16 | 20 |
| D5-4 | 1.3 (권장) | 16 numfmt_check |  | 자리마다 색 P6 갈색 … P1 빨강 | 통합 맵: aa.visual.end > 0 (phase 20 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): - | auto_all visual 구간(선택) / 16 | 20 |
| D5-5 | 1.3 (권장) | 16 numfmt_check |  | 만 단위 색이 옛 DPS 화면과 같음 | 통합 맵: aa.visual.end > 0 (phase 20 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): - | auto_all visual 구간(선택) / 16 | 20 |
| D5-6 | 1.3 (권장) | 16 numfmt_check |  | [12.5] [1234.567] [막대 앞 3개 초록] [05] | 통합 맵: aa.visual.end > 0 (phase 20 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): - | auto_all visual 구간(선택) / 16 | 20 |
| D5-7 | 1.3 (권장) | 16 numfmt_check |  | 한자 글자·16진 표시 | 통합 맵: aa.visual.end > 0 (phase 20 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): - | auto_all visual 구간(선택) / 16 | 20 |
| D5-8 | 1.3 (권장) | 16 numfmt_check |  | 0x0D 채움 고정 폭이 옛 DisplayPrint 와 같은 간격(옛 맵과 나란히) | 통합 맵: aa.visual.end > 0 (phase 20 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): - | auto_all visual 구간(선택) / 16 | 20 |
| D6-1 | 1.3 (권장) | 09 strdesign_check |  | mcf 판 장식이 DPS강화하기·UE_RE 화면과 같음 | 통합 맵: aa.visual.end > 0 (phase 20 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): - | auto_all visual 구간(선택) / 09 | 20 |
| D6-2 | 1.3 (권장) | 09 strdesign_check |  | seed 판 장식이 theSeed·Stella_II 와 같음 | 통합 맵: aa.visual.end > 0 (phase 20 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): - | auto_all visual 구간(선택) / 09 | 20 |
| D6-3 | 1.3 (권장) | 09 strdesign_check |  | respect 판, \x13 줄 가운데 정렬 | 통합 맵: aa.visual.end > 0 (phase 20 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): - | auto_all visual 구간(선택) / 09 | 20 |
| D6-4 | 1.3 (권장) | 09 strdesign_check |  | memory 판, \r\r 뒤 \x13 가운데 정렬 | 통합 맵: aa.visual.end > 0 (phase 20 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): - | auto_all visual 구간(선택) / 09 | 20 |
| D6-5 | 1.3 (권장) | 09 strdesign_check |  | \x13 두 번·오른쪽 정렬·줄바꿈 장식 | 통합 맵: aa.visual.end > 0 (phase 20 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): - | auto_all visual 구간(선택) / 09 | 20 |
| D14-8 **[필수]** | 1.2 (필수) | 10 bullet_check | AUTO | 종류=210 (자동). 왼쪽 탄이 가운데(야마토)와 같은 모양인지는 눈 — 총알 표(CBullet weaponType +0x5C 추정, sourceUnit +0x60 추정) 스캔이 확인되면 자동 | 통합 맵: aa.bullet.end > 0 (phase 15 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 610 | auto_all (값) + 화면: 통합 맵을 지켜보거나 10 | 15 |
| D14-9 | 1.3 (권장) | (bullet_example) | AUTO | height_actions 로 높이·그리기 층이 바뀜, 생성 전에 써야 하는지 | 통합 맵: aa.bullet.end > 0 (phase 15 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): - | auto_all (값) + 화면: 통합 맵을 지켜보거나 10 | 15 |
| D14-13 | 1.3 (권장) | 10 bullet_check | AUTO | BulletDat 만으로 설정한 208 탄 모양이 UE_RE 와 같음(dat 값은 시험이 이미 대조) | 통합 맵: aa.bullet.end > 0 (phase 15 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): - | auto_all (값) + 화면: 통합 맵을 지켜보거나 10 | 15 |
| D16-1 **[필수]** | 1.2 (필수) | 11 bgm_check | AUTO | ② 660Hz 가 ① 440Hz 와 다른(높은) 음으로 들림 — 귀. 문자열 칸에 d16_b.wav 이름이 들어갔는지는 자동 | frame >= 120 | 11 bgm |  |
| D16-2 | 1.3 (권장) | 11 bgm_check |  | ③(1번) ④(2번) 크기 차이·빠짐 | - | 11 bgm |  |
| D16-3 **[필수]** | 1.2 (필수) | 11 bgm_check | AUTO_ASSIST | ⑤⑥ 틈·딸깍·겹침은 귀. F10 일시정지 뒤 last_dt(>2500 이면 0)·조각 번호 건너뜀은 자동 기록 | frame >= 620 | 11 bgm |  |
| D16-6 | 1.3 (권장) | 11 bgm_check (--ogg 빌드) | EXTERNAL, CRASH_RISK | ⑨ 확장자만 .wav 인 Ogg 곡이 들림 | frame >= 800 | 11 bgm |  |
| D16-8 | 1.3 (권장) | 11 bgm_check |  | ⑩ 효과음이 몇 개 들리는지, 스윕 끊김 | - | 11 bgm |  |
| D16-9 | 1.3 (권장) | 11 bgm_check |  | 방 만들기~게임 시작 시간(초), units_ingame 과의 차이 | - | 11 bgm |  |
| D17-1 **[필수]** | 1.2 (필수) | 13 chat_check | AUTO | 표식 줄이 찍힌 프레임에 빈 줄 → 다음 프레임부터 셀 하나씩 드러남, 드러난 셀에 '!H'·U+200B 바이트 없음(자동). 네모·물음표가 안 보이는지, 가운데 정렬 움직임이 원본과 같은지(눈) | 통합 맵: aa.chat.end > 0 (phase 17 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 90 | auto_all (값) + 화면: 통합 맵을 지켜보거나 13 | 17 |
| D17-3 | 1.3 (권장) | 13 chat_check | AUTO | é ñ ü ß ç ø Ω 가 깨지지 않게 보임(눈). 드러나는 경계가 UTF-8 2바이트를 자르지 않는지는 자동 | 통합 맵: aa.chat.end > 0 (phase 17 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 260 | auto_all (값) + 화면: 통합 맵을 지켜보거나 13 | 17 |
| D17-7 | 1.3 (권장) | 13 chat_check | AUTO | 2프레임에 한 글자·글자마다 딸깍·공백은 조용(귀). 드러난 비공백 셀 수 = PlayWAV 횟수는 자동 | 통합 맵: aa.chat.end > 0 (phase 17 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 1080 | auto_all (값) + 화면: 통합 맵을 지켜보거나 13 (딸깍 소리) | 17 |
| D17-8 | 1.3 (권장) | 13 chat_check | AUTO | 끝난 줄이 시간이 지나 사라짐, 사라지기까지 초, 채팅창을 열면 다시 보이는지 | 통합 맵: aa.chat.end > 0 (phase 17 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= 1500 | auto_all (값) + 화면: 통합 맵을 지켜보거나 13 | 17 |
| E6-7 **[필수]** | 1.2 (필수) | 25 display_check |  | '\|-10\|1234만5678\|12.5\|42\|42\|' 대괄호 사이에 빈틈 없음(0x0D 가 폭을 차지하지 않음) | 통합 맵: aa.visual.end > 0 (phase 20 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): page 5 | auto_all visual 구간(선택) / 25 | 20 |
| E6-6 | 1.3 (권장) | 25 display_check |  | 임무 목표 창을 연 채로 카운터가 바뀌는지, 다시 열 때만 바뀌는지 | 통합 맵: aa.visual.end > 0 (phase 20 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): page 8 | auto_all visual 구간(선택) / 25 | 20 |
| E6-9 | 1.3 (권장) | 25 display_check | AUTO | 긴 줄 끝 '끝(…)' 이 보임(눈). 버퍼에서 그 줄 길이·NUL 위치(218 넘는지)는 자동 | 통합 맵: aa.display.end > 0 (phase 16 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): page 6 | auto_all (값) + 화면: 통합 맵을 지켜보거나 25 | 16 |
| E12-7 | 1.3 (권장) | 19 spawn_check (화면 줄 [E12-6]) | AUTO | 이미지 429 원이 번쩍임·모양(눈). 스캐너 유닛 남지 않음(수 0)·이미지 칸 546 복원은 자동 | 통합 맵: aa.spawn.end > 0 (phase 14 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): frame >= PH6 + 30 | auto_all (값) + 화면: 통합 맵을 지켜보거나 19 | 14 |
| E12-9 | 1.3 (권장) | 19 spawn_check | AUTO | 끊김 체감 — 브리지는 E12-1·E12-2 구간 프레임 시간 기록 | 통합 맵: aa.spawn.end > 0 (phase 14 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): - | auto_all (프레임 시간) + 체감은 사람 | 14 |
| S0-4 | 3 (UE_RE S0) | UE_RE_S0.scx (①) | AUTO_ASSIST | ←/→·B·Y 반응이 배포판과 같음(눈). 키 누름마다 채널 수신 1회인지는 자동 보조 | - | port:UE_RE ① |  |
| S0-6 | 3 (UE_RE S0) | UE_RE_S0.scx (①) | AUTO_ASSIST | 멀티 커맨드로 마린이 마우스 위치로 이동·공격, 연 채 우클릭 이동 | - | port:UE_RE ① |  |
| S0-8 | 3 (UE_RE S0) | UE_RE_S0.scx (①) | MULTI | 구간별 곡·보스곡, 관전자면 소리 꺼짐 | - | port:UE_RE ① |  |
| S0-9 | 3 (UE_RE S0) | UE_RE_S0.scx (①) | AUTO | 레벨 1→2 클리어 문구·포인트·사망 알림(눈). 건물 147 수 0 → 다음 레벨 전환 시각은 자동 기록 | - | port:UE_RE ① |  |
| S0-10 | 3 (UE_RE S0) | UE_RE_S0.scx (①) |  | 시작 레벨 2 에서 Identity 패턴·처치·보스곡 | - | port:UE_RE ① |  |
| S0-11 | 3 (UE_RE S0) | UE_RE_S0.scx (①) |  | 다른 보스 등장·패턴·클리어가 배포판과 같음 | - | port:UE_RE ① |  |
| S0-15 | 3 (UE_RE S0) | UE_RE_S0.scx (①) | AUTO | 30분(레벨 여러 개) 프레임 하락·멈춤이 배포판보다 심하지 않음 — 배포판에도 같은 표지 시그니처가 있어 같은 리더로 두 판 프레임/초를 잴 수 있음 | 30분 | port:UE_RE ① |  |
| T0-12 | 4 (theSeed S0) | theSeed_eud_S0_t1 | AUTO | (4,4) 타일 커맨드센터가 안 보이고 드래그로 안 잡힘(눈), 경고 문구 없음·이동 상태 6(자동) | 게임 시각 60초 | port:theSeed t1 |  |
| S1-1-1 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | AUTO | 첫 프레임 속도 0x1D, 화면 로케이션 64 중심, 150사이클 늘고 149사이클 줄어듦(자동). scan.wav·줄 구성은 원본과 나란히(눈·귀) | 사이클 300 | port:RV S1 |  |
| S1-1-3 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | AUTO_ASSIST, MULTI | 클릭한 PC 에만 화면 비움 + CTEnd + 설명(눈·귀). 다른 PC 에 안 보이는지는 멀티 | - | port:RV S1 |  |
| S1-2-1 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | AUTO | 상태창 수치가 원본과 같음, 레나마린 72·118·무기 127·128 은 HEAD 편집분 | gs 뒤 | port:RV S1 |  |
| S1-2-2 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | AUTO | 버튼·위치·아이콘이 원본과 같음 | - | port:RV S1 |  |
| S1-2-3 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | AUTO | 생산 가능/불가·요구조건 문구가 원본과 같음, 62·63 은 정식판에서 아무도 불가 | - | port:RV S1 |  |
| S1-2-4 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) |  | 상태창 특수 표시 14종·와이어프레임 40종 | - | port:RV S1 |  |
| S1-2-5 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | AUTO | 이름·툴팁·색이 원본과 같음 | - | port:RV S1 |  |
| S1-2-6 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | AUTO | Z·X·Q·W 업그레이드 툴팁 네 줄(시작값) | - | port:RV S1 |  |
| S1-2-7 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | AUTO | 난이도 뒤 영웅·보스 체력 dat(2단계에서 다시) | gs 뒤 | port:RV S1 |  |
| S1-6-1 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | AUTO, MULTI | NM·HD → 1번 곡(MX 28, SC 29) 요청(자동), 들림(귀) | gs 뒤 | port:RV S1 |  |
| S1-6-7 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) |  | 스캔·ADEnd·CTEnd 등 소리가 원본처럼 들림 | - | port:RV S1 |  |
| S1-8-1 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | AUTO | (상황이 있으면) '경고: '/'WARNING:' 채팅 줄이 곧 지워짐 — 버퍼에서 자동 확인 | - | port:RV S1 |  |
| M2-S0-4 | 5.2 (Memory 2 S0) | Mem2_S0_eudext.scx | AUTO | 스탯·버튼·요구사항·와이어프레임·한글 툴팁이 0.ZI_Fix 와 같음 | - | port:Mem2 eudext |  |
| M2-S0-5 | 5.2 (Memory 2 S0) | Mem2_S0_eudext.scx |  | 조각 BGM 끊김·겹침 없음, 구간·보스곡, 효과음 | - | port:Mem2 eudext |  |
| M2-S0-6 | 5.2 (Memory 2 S0) | Mem2_S0_eudext.scx | AUTO_ASSIST | 생산·조합·환전·자동환전·기부·업그레이드·컬러·메딕·보호막의 동작·가격·문구가 같음(금액 변화는 자동 보조) | - | port:Mem2 eudext |  |
| M2-S0-7 | 5.2 (Memory 2 S0) | Mem2_S0_eudext.scx | AUTO | 소환 도형·위치·주기가 같음, 한쪽 쏠림·엉뚱한 위치면 즉시 알림(NSQC 로케이션 복구 관련) | - | port:Mem2 eudext |  |
| M2-S0-8 | 5.2 (Memory 2 S0) | Mem2_S0_eudext.scx | AUTO | 킬 점수·EXP·사망 알림이 같음 | - | port:Mem2 eudext |  |
| M2-S0-10 | 5.2 (Memory 2 S0) | Mem2_S0_eudext.scx | AUTO_ASSIST | 평소 빠른 조작에서 BanCode 오탐 없음(값 0 유지 — 자동), 0.ZI_Fix 에서 처벌되던 조작은 처벌(사람 비교) | - | port:Mem2 eudext |  |
| M2-S0-12 | 5.2 (Memory 2 S0) | Mem2_S0_eudext.scx |  | RedNumber·해금·중간보스 등장·패턴이 같음 | - | port:Mem2 eudext |  |
| M2-S0-13 | 5.2 (Memory 2 S0) | Mem2_S0_eudext.scx | AUTO | 프레임이 0.ZI_Fix 와 비슷, 느린 장면 기록 | - | port:Mem2 eudext |  |
| M1-S0-2 | 5.3 (Memory 1 S0) | Mem1_S0_A.scx |  | 시작 위치·건물 배치가 출시판과 같음, 이상한 유닛 없음 | - | port:Mem1 |  |
| M1-S0-5 | 5.3 (Memory 1 S0) | Mem1_S0_A.scx | AUTO | 마린·영웅·적 수치가 출시판과 같음, P1·P2·P4·P5 마린 그림 = P3 마린(16) | - | port:Mem1 |  |
| M1-S0-6 | 5.3 (Memory 1 S0) | Mem1_S0_A.scx |  | 버튼 자리·아이콘·툴팁·단축키가 출시판과 같음 | - | port:Mem1 |  |
| M1-S0-7 | 5.3 (Memory 1 S0) | Mem1_S0_A.scx | AUTO | 업그레이드·스팀팩 활성/비활성이 출시판과 같음 | - | port:Mem1 |  |
| M1-S0-8 | 5.3 (Memory 1 S0) | Mem1_S0_A.scx | AUTO | 비용 숫자가 든 글이 깨지지 않음(줄 길이 그대로) | - | port:Mem1 |  |
| M1-S0-9 | 5.3 (Memory 1 S0) | Mem1_S0_A.scx | CRASH_RISK, AUTO | 건작 모양·주기·안내 글·BGM 전환이 같음, 유닛이 몰려도 튕기지 않음 | - | port:Mem1 |  |
| M1-S0-10 | 5.3 (Memory 1 S0) | Mem1_S0_A.scx | AUTO_ASSIST | 환전·조합·기부·메딕 반응·금액이 출시판과 같음 | - | port:Mem1 |  |
| M1-S0-11 | 5.3 (Memory 1 S0) | Mem1_S0_A.scx | AUTO | BYD 건작이 원본처럼, 비욘드 보스 조각 BGM 끊김 없음(귀) | - | port:Mem1 |  |
| M1-S0-12 | 5.3 (Memory 1 S0) | Mem1_S0_A.scx |  | Core of Depth 연출·조각 BGM(ikasu, H_Boss) | - | port:Mem1 |  |
| M1-S0-13 | 5.3 (Memory 1 S0) | Mem1_S0_A.scx |  | 승리 연출·엔딩·점수·패배가 같음 | - | port:Mem1 |  |
| M1-S0-15 | 5.3 (Memory 1 S0) | Mem1_S0_A.scx | AUTO | 30분 프레임 하락·멈춤이 출시판보다 심하지 않음 | - | port:Mem1 |  |
| M1-S0-16 | 5.3 (Memory 1 S0) | Mem1_S0_B.scx | CRASH_RISK, AUTO | ① 과 같은 조작 결과(특히 센터·SP/CERE/NEX 건작, BYD 도형) | - | port:Mem1 B |  |

### MULTI (44)

| ID | 절 | 맵 | 보조 | 판정(기대) | 완료 표식 | bundle | phase |
|---|---|---|---|---|---|---|---|
| B8-1 | 1.3 (권장) | 20 players_check | AUTO | 관전자 PC local_player ∈ 128~131(슬롯마다 다름), 플레이어 PC 0~7, contains_obs 는 관전자 PC 에서만 1 | frame >= 48 | M1_multi |  |
| B8-2 | 1.3 (권장) | 20 players_check | VISUAL, AUTO | run_as(Observers, DisplayText) 줄이 관전자 버퍼에만 있음. 소리(play_wav)는 귀로 | frame >= 24 | M1_multi |  |
| B8-3 | 1.3 (권장) | 20 players_check | AUTO | run_as(list(P1,P2), DisplayText('A')) 줄이 각 PC 버퍼에 정확히 한 번 | frame >= 24 | M1_multi |  |
| B8-5 | 1.3 (권장) | 20 players_check | AUTO | 한 명이 나간 뒤 is_human(1)=0, human_mask 에서 비트 빠짐, 나간 플레이어 광물 증가 없음 | 사람이 나간 뒤 5초 | M1_multi |  |
| B8-6 | 1.3 (권장) | 20 players_check | AUTO | 동맹 창·SetAllianceStatus 와 표가 같게 바뀜, run_as(Allies(P1)) 줄은 동맹 PC 에만 | 조작 뒤 | M1_multi |  |
| B8-7 | 1.3 (권장) | 20 players_check | VISUAL | 관전자 CP 로 CenterView·MinimapPing·SetMissionObjectives 해도 오류·튕김 없음, 관전자 화면에만 적용 | frame >= 24 | M1_multi |  |
| B8-8 | 1.3 (권장) | 20 players_check | AUTO | 사람 슬롯 0·2·3 처럼 띄운 방에서 모든 PC·관전자에서 contains_user(Everyone)=1 | frame >= 48 | M1_multi |  |
| B13-1 **[필수]** | 1.2 (필수) | 21 sync_check | AUTO | 5분 동안 드롭·동기화 오류 없음. 각 PC 리더의 score/held 표가 같은 게임 프레임에서 같음 | 게임 프레임 >= 7200 | 21 sync |  |
| B13-2 **[필수]** | 1.2 (필수) | 21 sync_check | AUTO | 두 PC 점수가 같다. 로컬 SPACE 누름 엣지 수 대비 점수 증가 수(빠진 횟수)를 기록 | 조작 뒤 | 21 sync |  |
| B13-7 | 1.3 (권장) | 21 sync_check | AUTO | 관전자 PC 멈춤·디싱크 없음, 관전자 F5 출력 없음 | 5분 | 21 sync |  |
| B13-10 | 1.3 (권장) | 21 sync_check |  | 배틀넷(턴이 여러 프레임)에서 B13-2~4 의 소실·지연이 LAN 과 어떻게 다른지 | - | 21 sync (배틀넷) |  |
| B13-11 | 1.3 (권장) | 21 sync_check (NSQC 변형) | EXTERNAL | 값이 오고 못 받은 사이클은 에러코드 | - | 별도 멀티 맵(NSQC) |  |
| B13-12 | 1.3 (권장) | 21 sync_check (별도 맵) | AUTO | bus.mouse_location 로케이션이 각 PC 마우스를 따라감, 번호 규칙(첫 로케이션 + p − 가장 작은 사람 번호) | - | 별도 멀티 맵(로케이션) |  |
| C11-8 | 1.3 (권장) | 22 pool_multi | AUTO | 모든 PC 에서 t1ok~t7ok 가 같고 디싱크 없음 | frame >= 12 | M1_multi |  |
| D14-12 | 1.3 (권장) | (멀티 맵) | AUTO | 매 프레임 bullet 2인 이상 디싱크 없음 | - | 별도 멀티 맵 |  |
| D16-4 | 1.3 (권장) | 11 bgm_check | VISUAL, AUTO | 관전자 PC 번호 128~131, 소리 들림(귀), DELETE 로 끄고 켜짐(끔 비트 자동) | - | 11 bgm (멀티) |  |
| D16-7 | 1.3 (권장) | 11 bgm_check | AUTO | N 뒤 모든 PC 조각 번호가 같은 게임 프레임에 같음, 방장이 나가도 계속 오름, M 은 누른 PC 만 | - | 11 bgm (멀티) |  |
| D18-6 **[필수]** | 1.2 (필수) | 14b scrdb_check_2p | EXTERNAL, AUTO | 두 런처 로그의 플레이어 P1/P2, 한 PC 에만 런처를 켠 판에서도 디싱크 없음, 런처 없는 PC 는 loaded=0 | - | 14b scrdb 2인 |  |
| E6-1 **[필수]** | 1.2 (필수) | 25 display_check (관전자 PC) | AUTO | 관전자 버퍼에 '[E6-1] 모두…'·'관전자에게만…'·'LOCAL: 이 PC 번호 = 128~131' 세 줄, P1 버퍼에는 '관전자에게만' 줄 없음·번호 0 | page 0 (frame 1~72) | M1_multi |  |
| F19-1 **[필수]** | 1.2 (필수) | 23 misc_obs_check | AUTO | 관전자 2~4번 PC 에서 END/HOME/INSERT 로 모드가 두 번 이상 바뀜(0x68C144 값 변화 자동), 실제 채팅 수신 대상은 사람 | - | M1_multi |  |
| F19-5 | 1.3 (권장) | 23 misc_obs_check | VISUAL | 안내 문구가 보이고 button3.wav 소리 | - | M1_multi |  |
| F19-6 | 1.3 (권장) | 23 misc_obs_check |  | 0x68C144 = 2/3/5 일 때 실제 채팅이 가는 곳(특히 3 '대상없음') | - | M1_multi |  |
| F19-2 | 1.3 (권장) | (확인 맵 없음) | AUTO | 모든 PC·리플레이에서 HotkeyUnit 값이 같음 | - | M1_multi (확인 코드 추가) |  |
| F19-1b | 1.3 (권장) | (확인 맵 없음) | AUTO | 모든 PC·싱글·리플레이에서 같은 방장 번호 | - | M1_multi (싱글 값은 auto_all phase 12 에서 참고로 기록) |  |
| F21-11 | 1.3 (권장) | (멀티 맵) | AUTO, CRASH_RISK | perma_sprite·CGRPPainter 를 매 프레임 쓰는 2인 이상 맵에서 디싱크 없음 | - | (별도 멀티) |  |
| S0-14 | 3 (UE_RE S0) | UE_RE_S0.scx (①) | AUTO | LAN 2명 5~10분 디싱크 없음, 두 사람 모두 불러오기 | - | port:UE_RE ①(멀티) |  |
| T0-14 | 4 (theSeed S0) | theSeed_eud_S0_t1 (2인) | AUTO | 풀어도 곧바로 다시 동맹·시야 공유 | - | port:theSeed(멀티) |  |
| T0-15 | 4 (theSeed S0) | theSeed_eud_S0_t1 (2인) | AUTO | 두 화면 같은 줄, 동시 누름이면 한 줄·두 횟수 +1 | - | port:theSeed(멀티) |  |
| T0-16 | 4 (theSeed S0) | theSeed_eud_S0_t1 (2인) | AUTO | 두 PC 값이 같음 | - | port:theSeed(멀티) |  |
| T0-17 | 4 (theSeed S0) | theSeed_eud_S0_t1 (2인) | AUTO | 30분 드랍 없음, 끝에 두 화면 확인 줄 같음 | - | port:theSeed(멀티) |  |
| T0-18 | 4 (theSeed S0) | theSeed_eud_S0_t1 (2인+관전자) |  | 관전자 채팅이 전체로 감, 관전자에게도 확인 줄 | - | port:theSeed(멀티) |  |
| S1-4-3 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) (2인) | AUTO | P2 패배·강퇴 문구, P1 화면에 완료 문구, 디싱크 없음 | - | port:RV(멀티) |  |
| S1-4-4 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) (2인) |  | 인식 전·칭호 없는 사람의 @파랑나가 는 아무 일 없음 | - | port:RV(멀티) |  |
| S1-5-1 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) (2인) | AUTO | 120초 안·난이도 전 방장 유닛 → 로케이션 49: 공유 켜짐, 문구 한 번, TAdUpd05(귀) | - | port:RV(멀티) |  |
| S1-5-3 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) | AUTO_ASSIST, AUTO | 한 사람이 쓰면 모든 사람 광물이 같은 값으로 움직임, '벌었음/사용함' 고정 줄 | - | port:RV(멀티) |  |
| S1-6-5 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) (관전자) | VISUAL | 관전자 PC 에서도 곡이 들림, 끄기 버튼 없음 | - | port:RV(멀티) |  |
| S1-7-4 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) (2인) | AUTO | 방장이 나가면 다음 앞 슬롯 사람이 방장(선택 유닛·62·63 권한) | - | port:RV(멀티) |  |
| S1-8-3 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) (2인) |  | 사람이 모두 나가면 P6~P8 패배 | - | port:RV(멀티) |  |
| S1-8-4 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) (5인) | AUTO | 5인 5분 끊김·디싱크·튕김 없음, 무거우면 기록(프레임/초) | - | port:RV(멀티) |  |
| M2-S0-20 | 5.2 (Memory 2 S0) | Mem2_S0_eudext.scx (2인) | AUTO | 5~10분 동기화 오류 없음 | - | port:Mem2(멀티) |  |
| M2-S0-21 | 5.2 (Memory 2 S0) | Mem2_S0_eudext.scx (2인) | AUTO | 방장 아닌 PC 에서도 같은 빠르기(Dt 는 방장 값) | - | port:Mem2(멀티) |  |
| M2-S0-22 | 5.2 (Memory 2 S0) | Mem2_S0_eudext.scx (2인) | VISUAL, AUTO | QC 유닛(58) 이 보이지 않고 선택되지 않음, 선택·부대 지정 유지(선택 표에 QC 유닛 없음 — 자동) | - | port:Mem2(멀티) |  |
| M1-S0-14 | 5.3 (Memory 1 S0) | Mem1_S0_A.scx (2인) | CRASH_RISK, AUTO | 10분 동기화 오류 없음, 두 사람 F12 눌러 보기에도 이상 없음 | - | port:Mem1(멀티) |  |
| M1-S0-17 | 5.3 (Memory 1 S0) | Mem1_S0_B.scx (2인) | AUTO | 5분 디싱크 없음 | - | port:Mem1(멀티) |  |

### CRASH_RISK (37)

| ID | 절 | 맵 | 보조 | 판정(기대) | 완료 표식 | bundle | phase |
|---|---|---|---|---|---|---|---|
| B10-9 | 1.3 (권장) | 03 units_ingame | VISUAL, AUTO | 끊김 체감 — 브리지는 F30 프레임 시간(ms)·F30~F40 평균 프레임/초를 기록 | frame >= 40 | X_limit |  |
| B15-8 | 1.3 (권장) | 04 datpatch_check (변형) | VISUAL | images grpFile·overlay 쓰기 뒤 오버레이가 바뀌는지(눈), 오류·튕김 없음(브리지) | - | R_risk (별도) |  |
| D14-3 **[필수]** | 1.2 (필수) | 10 bullet_check | AUTO | bullet=0, bullet_to=0, bullet_at=0 (zeroShots 1), 그 뒤 seq 계속. 채운 수 기록(기준 맵이면 1634 근처) | m10.frame >= 10 + 2초 동안 seq 계속 | X_limit |  |
| D14-10 | 1.3 (권장) | (대량 패턴 맵) | VISUAL | 소유자 사람/컴퓨터별 시야·총알 약 4096 표시 한도 | - | R_risk (별도) |  |
| D14-11 | 1.3 (권장) | (대량 패턴 맵) | VISUAL | [unlimiter] 켬/끔에서 한 프레임 80발 이상 | - | R_risk (별도) |  |
| D16-5 | 1.3 (권장) | 11 bgm_check | VISUAL, AUTO | ⑦ 없는 파일 PlayWAV·⑧ 없는 알림 뒤 게임이 멈추지 않음(seq 계속), 오류 창 없음, ① 음이 끝까지(귀) | frame >= 700 | 11 bgm |  |
| E6-3 **[필수]** | 1.2 (필수) | 25 display_check + 25b display_bisect | AUTO, VISUAL | 13번째 줄 바이트 = 우리 글(자동), 머리 값 복원(자동). SC 오류 문구가 보이는지·오류 소리가 나는지는 눈·귀 | page 1 (25) / bx.ok = 8~10 (25b) | 25 display_check + 25b display_bisect (EUD ERROR 좁히기) |  |
| E6-4 **[필수]** | 1.2 (필수) | 25 display_check + 25b display_bisect | AUTO_ASSIST, AUTO | 이름 칸이 '[E6-4] 마린 <숫자>' 이고 뒤 잔재 없음(눈 — 마린 선택 필요). TBL 바이트 끝 NUL·숫자 갱신은 자동 | page 2 (25) / bx.ok = 15~17 (25b) | 25 display_check + 25b display_bisect (마린 선택) |  |
| E6-4b | 1.3 (권장) | 25 display_check + 25b display_bisect | AUTO | NUL 없이 짧게 쓰면 앞 쪽 글자가 뒤에 남아 보임(눈), 바이트 잔재는 자동 | page 3 (25) / bx.ok = 17 (25b) | 25 display_check + 25b display_bisect |  |
| F19-4 **[필수]** | 1.2 (필수) | 17 exit_trap_check | MULTI, AUTO | P1 이 나갈 때 P1 의 스타가 멈춤(사람), P2 PC 는 seq 계속(자동) | P1 퇴장 뒤 30초 | 17 exit_trap (위험, 2인) |  |
| F21-1 **[필수]** | 1.2 (필수) | 18 sprite_check | VISUAL, AUTO | 만듦 16 실패 0, bounceE ≠ 0 (자동). 점이 보이고 안 움직이고 20초 뒤에도 남음, 높이별 겹침, 속도 1280 스프라이트 움직임은 눈 | frame >= 264 | 18 sprite (위험) |  |
| F21-2 **[필수]** | 1.2 (필수) | 18 sprite_check | VISUAL, AUTO | epd ≠ 0 둘 다(자동), 스톰 모양·수명 30/60 차이(눈) | frame >= 150 | 18 sprite (위험) |  |
| F21-3 **[필수]** | 1.2 (필수) | 18 sprite_check | VISUAL, AUTO_ASSIST, AUTO | +0xDC 0x100 켜짐·+0xE4 0, 약 96프레임 뒤 칸 비움, 드래그 선택에 안 잡힘(선택 표 자동), 2100 레이스는 잡힘, 움직이는 레이스 61번. 클로킹 소리·끊김 없는 움직임은 눈·귀 | frame >= 200 | 18 sprite (위험) |  |
| F21-4 **[필수]** | 1.2 (필수) | 18 sprite_check | VISUAL, AUTO | 남은 스캐너 유닛 1(마지막 remove=False 만) — 자동. 스캔 모양은 눈 | frame >= 180 | 18 sprite (위험) |  |
| F21-5 **[필수]** | 1.2 (필수) | 18 sprite_check | VISUAL, AUTO | epd ≠ 0, 마린이 (3413, 3413) 근처(±64)로 옮겨졌으면 '끌려옴' 기록(자동). 리콜 모양은 눈 | frame >= 228 | 18 sprite (위험) |  |
| F21-6 **[필수]** | 1.2 (필수) | 18 sprite_check | VISUAL, AUTO | 다 그림 1, 점 120/120, 실패 0 (자동). 색·모양은 눈(사진) | frame >= 360 | 18 sprite (위험) |  |
| F21-7 **[필수]** | 1.2 (필수) | 18 sprite_check | EXTERNAL, VISUAL, AUTO | 헤더 값 = CS_Photo 입력값(자동 대조 — 입력값을 사람이 알려 줘야 함), 다 그림 1·실패 0, 그림이 원본 BMP 와 같음(눈) | frame >= 600 | 18 sprite (위험) |  |
| F21-8 | 1.3 (권장) | (28장 함수를 쓰는 맵) | VISUAL | 진짜 벌처·스캐너가 있는 맵에서 모양·스캔 크기가 깨지는가(문서화용) | - | R_risk (별도) |  |
| F21-9 | 1.3 (권장) | 18 sprite_check | AUTO | storm·perma·unit_sprite·recall 모두 0, fullZero 1, 그 뒤 seq 계속 | frame >= 700 | 18 sprite (위험) |  |
| F21-10 | 1.3 (권장) | (언리미터 뺀 변형) | VISUAL | [unlimiter] 없이 28장 함수·CGRP 가 어떻게 되는지, 한 프레임 점 수 한도 | - | R_risk (별도) |  |
| S0-1 | 3 (UE_RE S0) | UE_RE_S0.scx (①) | AUTO, VISUAL | 시그니처가 나타나고 seq·게임 프레임이 계속 늘어남(자동 감시). 오프닝 글 스크롤·카운트다운은 눈 | 게임 시작 뒤 60초 | port 스모크(사람) |  |
| S0-16 | 3 (UE_RE S0) | UE_RE_S0_cplp_out.scx (②) | AUTO, EXTERNAL | 배포판 _out 처럼 열리고 S0-1~3 이 같음 | 게임 시작 뒤 60초 | port 스모크(사람) |  |
| S0-19 | 3 (UE_RE S0) | UE_RE_S0_eudext.scx (③) | AUTO, EXTERNAL, AUTO_ASSIST | S0-1·S0-3·S0-12 가 ①과 같음 | S0-12 절차 끝 | port 스모크(사람) |  |
| T0-2 | 4 (theSeed S0) | theSeed_eud_S0_t1 (다른 닉네임) | EXTERNAL, AUTO | 가운데 두 줄 + 패배 + EUD ERROR 로 멈춤(원본과 같음) — 멈춘 뒤 seq 정지로 기록 | 멈춤 | R_halt(사람) |  |
| T0-4 | 4 (theSeed S0) | theSeed_eud_S0_t1 (방 배속 옵션) | EXTERNAL | '방 제목에서 배속 옵션을 제거해 주십시오…' 세 줄 + 패배 + 멈춤 | 멈춤 | R_halt(사람) |  |
| T0-5 | 4 (theSeed S0) | theSeed_eud_S0_t1 (슬롯 변경) | EXTERNAL | 사람/컴퓨터 슬롯·종족 변경 각각의 문구 + 패배 + 멈춤 | 멈춤 | R_halt(사람) |  |
| T0-19 | 4 (theSeed S0) | theSeed_eud_S0_t1 (2인, 닉네임 없음) | MULTI | 두 PC 모두 같은 문구 + 패배 + 멈춤(디싱크 창 아님) | 멈춤 | R_halt(사람, 멀티) |  |
| S1-3-1 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) (방 제목 배속 옵션) | EXTERNAL | 실행 방지 문구 → 패배 → 튕김 | 튕김 | R_halt(사람) |  |
| S1-3-2 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) (사람 슬롯에 컴퓨터) | EXTERNAL | '사람 슬롯 변경…' → 튕김 | 튕김 | R_halt(사람) |  |
| S1-3-3 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) (컴퓨터 슬롯·종족 변경) | EXTERNAL | '컴퓨터 슬롯 변경…' / '컴퓨터 종족 변경…' → 튕김 | 튕김 | R_halt(사람) |  |
| S1-3-4 | 5.1 (Respect V 1단계) | Respect_V_eud_S1.scx (LAN 방) (싱글플레이) |  | '싱글플레이로는 플레이할 수 없습니다…' → 튕김 | 튕김 | R_halt(사람) |  |
| S1-3-6 | 5.1 (Respect V 1단계) | Respect_V_eud_S1_T1.scx (허용 닉네임 없음) | EXTERNAL | '테스트 전용 맵입니다…' → 패배 → 튕김 | 튕김 | R_halt(사람) |  |
| M2-S0-1 | 5.2 (Memory 2 S0) | Mem2_S0_eudext.scx | AUTO, VISUAL | 로딩·시작에서 튕기지 않음, seq 계속, freeze 문구 없음 | 게임 시작 뒤 60초 | port 스모크(사람) |  |
| M2-S0-11 | 5.2 (Memory 2 S0) | Mem2_S0_eudext.scx | AUTO_ASSIST, AUTO | O·P·F12·TAB·INSERT·DELETE·ESC 를 눌러도 멈춤 없음, 테스트 기능 관련 데스·스위치 변화 없음(출시판) | 조작 뒤 10초 | port 스모크(사람) |  |
| M2-S0-14 | 5.2 (Memory 2 S0) | Mem2_S0_eudext_cplp_out.scx | AUTO | 보호판이 똑같이 불러와지고 확인 줄 한 번 | 사이클 97 | port 스모크(사람) |  |
| M1-S0-1 | 5.3 (Memory 1 S0) | Mem1_S0_A.scx | AUTO, VISUAL | 제목 '마린키우기 Memory v.4.0R', 시작 직후 멈춤 없음, 약 3초 뒤 인트로 글·BGM | 게임 시작 뒤 60초 | port 스모크(사람) |  |
| M1-S0-19 | 5.3 (Memory 1 S0) | Mem1_S0_C.scx | AUTO | 출시판 _out 처럼 열리고 M1-S0-1·4 가 같음 | 게임 시작 뒤 60초 | port 스모크(사람) |  |

### EXTERNAL (17)

| ID | 절 | 맵 | 보조 | 판정(기대) | 완료 표식 | bundle | phase |
|---|---|---|---|---|---|---|---|
| B15-2 | 1.3 (권장) | 04 datpatch_check | AUTO | SCMDraft 로 CHK 를 바꾼 맵과 트리거 패치 맵의 두 칸 값이 같음 | frame >= 24 | 별도: SCMDraft 로 CHK 를 바꾼 맵 2개 |  |
| B15-9 | 1.3 (권장) | (M2 from_eud_editor 빌드) | AUTO | from_eud_editor 로 만든 M2 와 원래 DataEditor.py 맵의 dat 칸이 같음 — 덤프를 자동 대조 | frame >= 24 | 별도 빌드(M2 from_eud_editor) |  |
| C9-1 | 2 (SCMDraft) | (게임 없음) mathx_tep_check.py |  | 'C9-1 일치' | - | EXT (게임 없음) |  |
| D7-6 | 2 (SCMDraft) | (SCMDraft + TEP 맵) | VISUAL | 혼자 열면 'D7-6: 47 95 (eudext 와 같음)' | - | EXT (SCMDraft + 한 줄 보기) |  |
| D18-1 **[필수]** | 1.2 (필수) | 14 scrdb_check | AUTO, VISUAL | 표지 Seq 증가, LocalPlayer = 1, 로그 '연결되었습니다 … 빌드 N, P1' → '매니페스트 : …eudext_scrdb_check.json (빌드 일치, 항목 5개)'. 알림음은 귀 | 게임 시작 뒤 5초 | 14 scrdb |  |
| D18-2 **[필수]** | 1.2 (필수) | 14 scrdb_check | AUTO | loaded=1, Gold 0 Level 0 Big 0x12345678 Stat 7 Flags 0xABCDEF01, 받은 워드 P1 ≥ 1, 로그 '저장된 파일이 없습니다' | loaded[0] == 1 | 14 scrdb |  |
| D18-3 **[필수]** | 1.2 (필수) | 14 scrdb_check | AUTO_ASSIST, AUTO | F8 뒤 saves=1, Level 1, 로그 '저장 시작 … 저장 완료. (5개 항목)', 저장 완료 표식(0xFFFD) 처리 | save_done 처리 뒤 | 14 scrdb |  |
| D18-4 **[필수]** | 1.2 (필수) | 14 scrdb_check | AUTO_ASSIST, AUTO, VISUAL | 다시 연 판에서 저장했던 Gold·Level·Big 0x12345678·Stat 7·Flags 0xABCDEF01 (상위 16비트 포함), 로그 '불러오기 완료', '어긋난 항목' 없음. 알림음은 귀 | loaded[0] == 1 (두 번째 판) | 14 scrdb (다시 열기) |  |
| D18-5 | 1.3 (권장) | 14 scrdb_check | VISUAL | 런처 끄기 → 끊김 소리, 매니페스트 치우고 연결 → 오류 소리 (이 PC 만) | - | 14 scrdb |  |
| D18-7 | 1.3 (권장) | 14 scrdb_check (다시 빌드) | AUTO | 빌드 ID 가 바뀐 맵 + C:\Temp 매니페스트 삭제 → 로그 '매니페스트 : … (항목 지문 일치 …)' | - | 14 scrdb |  |
| D18-8 | 1.3 (권장) | 14 scrdb_check |  | 런처 --dev 'MSQC 채널 시험' 오류율·도착률이 DPS 맵과 비슷 | - | 14 scrdb |  |
| D18-9 | 1.3 (권장) | (빌드 로그) | AUTO | 'Sendable value range for val syntax: 0 to 4194303', 64×64 미만 맵은 빌드 오류 | - | EXT (빌드 로그) |  |
| S0-3 | 3 (UE_RE S0) | UE_RE_S0.scx (①) | AUTO, VISUAL | 표지 Seq 증가, 불러오기 완료 신호, 로그 '불러오기 완료'. 레벨·스탯·칭호 복원·GUEST 사라짐·소리는 눈·귀 | 게임 시작 뒤 30초 | port:UE_RE ① |  |
| S0-12 | 3 (UE_RE S0) | UE_RE_S0.scx (①) | AUTO_ASSIST, AUTO | HOME 뒤 로그 '저장 완료', 다시 들어가 불러오면 같은 값(표지·로그 자동), 문구는 눈 | HOME 뒤 10초 | port:UE_RE ① |  |
| S0-13 | 3 (UE_RE S0) | UE_RE_S0.scx (①) | AUTO_ASSIST, AUTO | 게임 시작 뒤 켠 런처로는 불러오기가 되지 않음(표지 상태·로그) | 런처 켠 뒤 30초 | port:UE_RE ① |  |
| S0-17 | 3 (UE_RE S0) | UE_RE_S0_cplp_out.scx (②) |  | SCMDraft 로 열리지 않음 | - | EXT |  |
| M1-S0-20 | 5.3 (Memory 1 S0) | Mem1_S0_C.scx |  | SCMDraft 로 열리지 않음 | - | EXT |  |

