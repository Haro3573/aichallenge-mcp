# aichallenge-mcp 프로젝트 컨텍스트

이 문서는 이 저장소를 처음 맡은 에이전트·운영자를 위한 현재 기준 문서다. 구현·테스트·ChatGPT Skill의 동작이 충돌할 때는 **코드와 테스트를 우선**하고, 이 문서를 함께 갱신한다.

## 한 줄 정의

`aichallenge-mcp`는 운영자가 코드로 등록한 공개 AI 대회·해커톤·챌린지 source를 매 호출마다 수집해 ChatGPT에 구조화된 현재 데이터를 제공하는, **무상태 Streamable HTTP MCP 서버**다.

사용자는 URL을 주지 않는다. 범용 웹 스크레이퍼도, 대회 일정관리 서비스도, 변화 추적 데이터베이스도 아니다.

## 제품 경계

### 하는 일

- 운영자가 등록한 고정 source의 공개 정보를 수집한다.
- 전체 source를 병렬 수집하고, source별 성공·실패·경고를 분리해 반환한다.
- ChatGPT가 읽을 수 있는 손실 없는 정규화 결과와 간결한 수집 요약을 제공한다.
- 나머지 대화, 참가 적합성 인터뷰, 브리핑·리포트 작성은 ChatGPT Skill이 담당한다.

### 하지 않는 일

- 사용자 제공 URL, 임의 도메인, 로그인·CAPTCHA 우회, 비공개 데이터 수집
- SQLite, 스냅샷, 캐시, 아카이브, 이전 결과와의 신규·변경·삭제 비교
- 서버 측 문서 파일·다운로드 UI·자동 발송·일정 관리
- source 간 중복 제거·우선순위 판단·자격요건 추정

수집 실패는 대회 종료나 목록 비어 있음을 의미하지 않는다. 실패한 source는 실패로만 보고한다.

## 현재 구조

| 경로 | 책임 |
| --- | --- |
| `src/aichallenge_mcp/server.py` | MCP 도구, `/healthz`, `/readyz`, Streamable HTTP 앱, source registry |
| `src/aichallenge_mcp/orchestrator.py` | 모든 등록 source의 병렬 실행, timeout·재시도·부분 실패 격리 |
| `src/aichallenge_mcp/sources/` | source별 adapter, 공개 접근 정책, 정규화, registry/result 계약 |
| `src/aichallenge_mcp/briefing_document.py` | `raw` 제거, 요약 생성, 손실 없는 columnar 변환·복원 |
| `src/aichallenge_mcp/runtime.py` | 로컬 서버·Secure MCP Tunnel·LaunchAgent·Keychain 참조의 안전한 운영 |
| `chatgpt-skills/ai-contest-briefing/SKILL.md` | ChatGPT에서의 초기 호출·JSON 첨부·후속 대화 규칙 |
| `tests/` | source fixture/계약, orchestrator, runtime, ChatGPT surface 회귀 테스트 |
| `docs/adr/` | 무상태 설계, Kaggle API, 과거 설계 결정 기록 |

## 핵심 용어

| 용어 | 뜻 |
| --- | --- |
| **source** | `source_id`로 식별되는 운영자 등록 사이트 또는 페이지군 |
| **source adapter** | 한 source의 접근 규칙, 파싱, required fields, 검증을 소유한 구현 |
| **source tool** | adapter 하나의 완전한 source-native 결과를 반환하는 공개 MCP 도구 |
| **orchestrator** | 모든 등록 source를 병렬 실행하는 `collect_all_sources` |
| **collection run** | 한 번의 새 수집 실행. 과거 상태를 읽거나 쓰지 않는다. |
| **operator** | source를 코드·테스트와 함께 등록/수정하는 유지보수자. 최종 사용자가 아니다. |

## 현재 등록 source와 공개 도구

| source ID | MCP 도구 | 포함 범위 | 인증 |
| --- | --- | --- | --- |
| `aichallenge4all` | `collect_aichallenge4all` | AI Challenge for All의 현재 공개 목록 | 없음 |
| `dacon` | `collect_dacon_competitions` | DACON의 `참가신청중`·`진행중`·`연습` 공식 대회와 공개 상세 정보 | 없음 |
| `kaggle` | `collect_kaggle_competitions` | Kaggle 공식 API의 활성 대회 중 공개 메타데이터가 온라인 참여 정책을 만족하는 항목 | 런타임 Kaggle API 자격증명 |
| `devpost` | `collect_devpost_hackathons` | Devpost 공개 목록 API의 현재 제출 가능한 해커톤 | 없음 |

Kaggle은 `KAGGLE_API_TOKEN` 또는 `KAGGLE_USERNAME`과 `KAGGLE_KEY` 쌍을 런타임에만 받는다. 자격증명과 계정 개인화 필드는 MCP 결과, 파일, 로그에 절대 넣지 않는다.

## MCP 계약과 데이터 흐름

```text
@AI 대회 브리핑 Skill
        │
        ▼
collect_all_sources
        │  병렬 실행 · source당 20초 timeout · 실패 시 1회 재시도
        ▼
source별 정규화 결과 ──► compact summary (대화용)
        │
        └──────────────► lossless columnar collection (모델/JSON 파일용)
```

### 도구 사용 규칙

1. 현재 전체 브리핑의 첫 요청에는 반드시 `collect_all_sources`를 먼저 호출한다.
2. 전체 수집 뒤 같은 첫 턴에 source 도구를 추가 호출하지 않는다. 전체 도구가 필요한 현재 데이터를 이미 반환한다.
3. 이후 사용자가 특정 source의 source-native 필드를 명시적으로 필요로 할 때만 `collect_<source>` 도구를 호출한다.
4. 이전 수집과의 변경 비교 요청에는 도구를 호출하거나 결론을 추측하지 않는다. 이 MCP는 무상태다.

`collect_all_sources`는 다음 두 결과를 반환한다.

- 대화 content: 성공 source 수와 총 항목 수를 담은 작은 한국어 상태 메시지
- `structuredContent.summary`: source별 상태·건수·경고·오류만 담은 요약
- `structuredContent.collection`: 완전한 현재 수집 데이터

`collection`의 canonical format은 `aichallenge-mcp.columnar.v1`이다. source마다 `item_columns`와 `item_rows`가 있고, 각 row의 값은 같은 index의 column에 대응한다. `briefing_document.expand_compact_collection()`은 테스트·내부 소비자를 위한 복원 함수다. item의 파서 진단용 `raw` 필드는 공개 계약에 포함하지 않는다.

source 결과는 공통적으로 source 정체성, source URL, 수집 시각, `success`, `items`, `source_pages`, `warnings`, `error`, `attempts`를 가진다. 성공 결과가 required-field/shape 계약을 위반하거나 유효 항목이 0건이면 성공으로 처리하지 않는다.

## ChatGPT Skill 동작

ChatGPT에 배포하는 실제 지시는 `chatgpt-skills/ai-contest-briefing/SKILL.md`가 기준이다. 이를 수정하면 두 ZIP을 갱신하고 ChatGPT Skill도 업데이트해야 한다.

초기 `@AI 대회 브리핑` 실행은 다음을 반드시 수행한다.

1. 앱의 `collect_all_sources`를 인자 없이 호출한다.
2. columnar collection을 해석해 최대 10개 기회만 포함한 간결한 한국어 브리핑을 쓴다.
3. 같은 응답에 전체 `structuredContent.collection`과 **완전히 동일한** UTF-8 JSON을 `ai-contest-data-YYYY-MM-DD.json`으로 첨부한다.

그 뒤의 대화는 일반 ChatGPT 후속 대화다. 현재 대화의 수집 결과와 JSON을 재사용하고, 사용자가 명시적으로 새로고침/재수집을 요청하기 전에는 다시 수집하거나 JSON을 재생성하지 않는다. 참가 대회 추천 또는 인터뷰 요청이면 도구 호출 없이 목표·기술/역할·시간/팀/온라인 제약의 세 질문으로 한국어 인터뷰를 시작한다. 답변은 항상 가시적인 한국어 문장으로 끝나야 하며, 단지 작업 시간 표시만 남겨서는 안 된다.

완전한 읽기용 Markdown 리포트는 사용자가 명시적으로 전체 리포트/모든 대회를 요청할 때만 만든다. 서버가 문서를 만들지는 않는다.

## source 추가 또는 수정 규칙

새 URL은 사용자가 런타임에 전달하는 방식이 아니라 운영자가 코드로 도입한다. 한 source 변경에는 반드시 다음이 함께 들어간다.

1. `sources/`의 전용 adapter: canonical URL, 공개 접근 규칙, 포함/제외 정책, required fields, 정규화
2. `server.py`의 adapter 인스턴스·`SourceRegistry` 등록·읽기 전용 공개 MCP 도구
3. HTML/API fixture와 source 계약 테스트
4. orchestrator 통합 영향 테스트
5. 실제 공개 페이지/API live smoke test
6. README와 이 문서의 source 표 갱신

등록 source는 최대 20개를 목표로 유지한다. source별 직접 도구를 공개하므로, 이름·설명·반환 shape는 운영 계약이다. 기존 결과를 깨는 변경은 fixture와 회귀 테스트를 먼저 수정해 의도적으로 수행한다.

## 로컬 운영과 비밀값

- 기본 MCP 주소: `http://127.0.0.1:8000/mcp`
- `GET /healthz`: 프로세스 liveness
- `GET /readyz`: production host와 선택적 Kaggle 자격증명 readiness
- 현재 개인용 연결: 로컬 서버 + OpenAI Secure MCP Tunnel + ChatGPT의 Tunnel/No Auth 앱 연결
- `aichallenge-mcp-runtime doctor`: 서버·터널·설정·LaunchAgent 상태 확인
- `aichallenge-mcp-runtime up`: 로컬 서버와 터널을 재기동

비밀값은 `.env`, Git, 로그, ChatGPT 대화에 기록하지 않는다. 개인용 런타임은 macOS Keychain을 참조하고, LaunchAgent는 해당 참조만 사용한다. Keychain 서비스명은 비밀값이 아니지만 password/token 값은 읽거나 출력하지 않는다.

`.venv`는 현재 LaunchAgent가 사용하는 Python 환경이므로 단순 정리 대상으로 삭제하면 안 된다. tunnel-client는 런타임이 관리하는 경로를 사용한다. Codex 세션 종료 또는 Mac 재시작 뒤에도 LaunchAgent와 터널 상태는 `doctor`로 확인한다.

## 개발·검증 명령

```bash
source .venv/bin/activate
pytest
python -m compileall src
python -m aichallenge_mcp.cli
aichallenge-mcp-runtime doctor
```

ChatGPT Skill을 변경했을 때는 ZIP을 다시 만든 뒤 ChatGPT의 설치된 Skill을 업데이트한다.

```bash
cd chatgpt-skills
zip -q -r -FS ai-contest-briefing-chatgpt.skill.zip ai-contest-briefing
zip -q -r -FS ai-contest-briefing.skill.zip ai-contest-briefing
```

## 변경 시 지켜야 할 불변 조건

- MCP는 읽기 전용·비파괴·operator-curated public source만 다룬다.
- collection은 항상 새 결과이며 과거와 비교하지 않는다.
- source 하나가 실패해도 다른 source의 성공 데이터를 버리지 않는다.
- source 실패를 마감·삭제·0건으로 해석하지 않는다.
- 공개 결과에서 자격증명, 세션 값, 사용자 개인화 필드, parser `raw` payload를 제외한다.
- collection의 columnar format과 ChatGPT Skill의 초기 JSON 첨부 계약을 바꿀 때는 서버·Skill·테스트·README·이 문서를 한 변경에서 함께 갱신한다.
