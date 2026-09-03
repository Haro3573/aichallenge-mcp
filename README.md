# AI Challenge Briefing MCP

ChatGPT의 **AI 대회 브리핑** 앱이 운영자 등록 공개 source에서 AI 대회·해커톤·챌린지 정보를 매번 새로 수집하도록 하는 경량·무상태 MCP 서버입니다.

이 서버는 범용 URL 스크레이퍼가 아닙니다. 사용자는 URL을 입력하지 않으며, 운영자가 코드·테스트와 함께 등록한 source만 수집합니다. 서버는 현재 수집 데이터만 반환하고, 해석·추천·읽기용 리포트·후속 대화는 ChatGPT Skill이 담당합니다.

## 제공 도구

| MCP 도구 | 용도 |
| --- | --- |
| `collect_all_sources` | 기본 오케스트레이터. 모든 등록 source를 동시에 수집하고, source별 20초 timeout·1회 재시도·부분 실패 격리를 적용한다. 대화에는 압축 요약을, 모델에는 완전한 현재 데이터를 반환한다. |
| `collect_aichallenge4all` | `aichallenge4all.or.kr`의 현재 공개 결과를 source-native 형태로 반환한다. |
| `collect_dacon_competitions` | DACON의 `참가신청중`·`진행중`·`연습` 공식 대회와 공개 상세 정보를 반환한다. |
| `collect_kaggle_competitions` | Kaggle 공식 인증 API의 활성 대회 중 온라인 참여 정책을 만족하는 항목을 반환한다. 런타임 Kaggle 자격증명이 필요하다. |
| `collect_devpost_hackathons` | Devpost 공개 목록 API의 현재 제출 가능한 해커톤을 반환한다. 위치는 필터링하지 않고 원본 공개 필드를 보존한다. |

수집 결과는 상태가 없습니다. SQLite, 이전 실행 결과, 신규·변경 비교, stale fallback, 아카이브는 사용하지 않습니다.

`collect_all_sources`의 전체 데이터는 `structuredContent.collection`에 `aichallenge-mcp.columnar.v1` 형식으로 제공됩니다. source마다 `item_columns`와 `item_rows`가 있고, row의 값은 같은 index의 column에 대응합니다. 파서 진단용 `raw` payload는 공개 결과에서 제외됩니다.

이 MCP 서버는 문서·앱 카드·다운로드 UI를 만들지 않습니다. 문서화와 파일 보관은 ChatGPT 클라이언트가 담당합니다. 서버는 상태나 데이터베이스를 사용하지 않습니다.

## ChatGPT에서의 사용자 경험

사용자는 ChatGPT에서 **@AI 대회 브리핑**을 명시해 실행합니다. 설치된 Skill은 자동으로 `collect_all_sources`를 호출하고 다음을 제공합니다.

1. 최대 10개 기회를 담은 간결한 한국어 최신 브리핑
2. 전체 정규화 collection과 정확히 동일한 UTF-8 JSON 첨부 파일: `ai-contest-data-YYYY-MM-DD.json`

같은 대화 안의 후속 질문은 기존 수집 결과와 첨부 JSON을 재사용합니다. 사용자가 명시적으로 새로고침/재수집을 요청하기 전에는 전체 수집을 다시 실행하거나 JSON을 다시 만들지 않습니다. 전체 읽기용 Markdown 리포트는 사용자가 명시적으로 요청할 때만 ChatGPT가 작성합니다.

이 MCP는 이전 실행을 저장하지 않으므로 신규·변경·삭제 비교를 제공할 수 없습니다. source 수집 실패 역시 대회 종료나 삭제의 증거가 아닙니다.

## 로컬 실행

Python 3.11+이 필요합니다.

```bash
cd aichallenge-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m aichallenge_mcp.server
```

Kaggle source를 함께 수집하려면 Kaggle 계정의 API 토큰을 로컬 런타임 환경에 설정합니다. 토큰 값을 `.env`, 저장소, 로그, ChatGPT 대화에 넣지 않습니다.

```bash
export KAGGLE_API_TOKEN='...'
```

레거시 키 쌍도 지원합니다.

```bash
export KAGGLE_USERNAME='...'
export KAGGLE_KEY='...'
```

서버는 기본적으로 `http://127.0.0.1:8000/mcp`에서 Streamable HTTP MCP를 제공합니다.
의존성은 MCP Python SDK 2.x(`mcp>=2.0.0,<3`)이며 최신 Discovery 프로토콜을 네이티브로 지원합니다.

운영 상태는 다음 엔드포인트로 점검합니다.

- `GET /healthz`: 프로세스 liveness
- `GET /readyz`: production host 설정과 필수 source 자격증명 readiness

공개 HTTPS reverse proxy 또는 터널을 쓰면, MCP SDK Host 검증에 해당 공개 호스트를 명시합니다.

```bash
MCP_ALLOWED_HOSTS=example.com python -m aichallenge_mcp.server
```

로컬 수집 검증:

```bash
python -m aichallenge_mcp.cli
pytest
python -m compileall src
```

## ChatGPT 연결

1. 로컬 서버를 실행한다.
2. OpenAI Secure MCP Tunnel 또는 개발용 HTTPS reverse tunnel을 `http://127.0.0.1:8000/mcp`에 연결한다.
3. ChatGPT Developer mode에서 **AI 대회 브리핑** 앱의 연결 방식을 Tunnel, 인증을 No Auth로 설정한다.
4. 앱의 도구 목록에 `collect_all_sources`와 등록 source 도구가 표시되는지 확인하고 앱 연결을 Refresh한다.
5. `chatgpt-skills/ai-contest-briefing-chatgpt.skill.zip`을 ChatGPT Skill로 설치 또는 업데이트한다.
6. 새 ChatGPT 대화에서 `@AI 대회 브리핑`을 선택해 실행한다. Skill이 `collect_all_sources`를 호출하고 간결한 브리핑과 전체 JSON 첨부 파일을 반환해야 한다.

로컬 서버와 tunnel-client는 모두 실행 중이어야 ChatGPT가 도구를 검색·호출할 수 있습니다. ChatGPT 앱이나 Skill은 Mac의 중단된 로컬 프로세스를 직접 복구할 수 없습니다. Codex 세션이 종료되면 이 로컬 프로세스와 임시 터널도 종료될 수 있으므로, 연결 실패 시 아래 runtime 진단을 먼저 실행합니다.

### Skill 변경 배포

`chatgpt-skills/ai-contest-briefing/SKILL.md`를 변경한 경우, 두 ZIP을 다시 만들고 ChatGPT의 설치된 Skill을 업데이트합니다.

```bash
cd chatgpt-skills
zip -q -r -FS ai-contest-briefing-chatgpt.skill.zip ai-contest-briefing
zip -q -r -FS ai-contest-briefing.skill.zip ai-contest-briefing
```

### 개인용 연결 자동 복구

`aichallenge-mcp-runtime`는 개인용 Secure MCP Tunnel 환경을 진단하고
로컬 서버·터널을 재기동합니다. 이 명령은 비밀값을 출력하거나 파일에 저장하지
않습니다.

```bash
source .venv/bin/activate
aichallenge-mcp-runtime doctor
aichallenge-mcp-runtime up
```

Mac 로그인 후에도 자동으로 복구하려면, OpenAI Secure Tunnel의 **runtime
control-plane credential**이 기존 Secure Tunnel 앱이 설정한 user `launchd`
환경에 있어야 합니다. 복구기는 기존 profile의 `env:CONTROL_PLANE_API_KEY`
참조 방식을 그대로 사용하며, 값을 출력·복사·저장하지 않습니다. 이 값은 대회
수집용 Kaggle 키나 모델 API 키와 다른 tunnel-client 런타임 자격증명입니다.
기존 앱을 이미 사용했다면 별도 Keychain 등록 없이 다음 명령만 한 번 실행합니다.

기존 OpenAI 키가 Keychain에만 있다면 서비스 이름을 지정해 같은 항목을
런타임에만 참조할 수 있습니다. 서비스 이름은 비밀값이 아닙니다.

```bash
aichallenge-mcp-runtime --keychain-service '<기존-Keychain-서비스-이름>' install-launchd
```

Kaggle API는 별도 Keychain generic-password 항목으로 연결할 수 있습니다.
Kaggle API Token을 해당 항목의 password로 저장한 뒤, 서비스 이름만 지정해
LaunchAgent를 재설치합니다. 토큰은 plist, 로그, `.env`, Git에 저장되지 않고
서버 자식 프로세스에만 `KAGGLE_API_TOKEN`으로 전달됩니다.

```bash
aichallenge-mcp-runtime \
  --keychain-service 'aichallenge-mcp-control-plane' \
  --kaggle-keychain-service 'aichallenge-mcp-kaggle' \
  install-launchd
```

설치되면 두 개의 user LaunchAgent가 로그인 시 시작되고, 서버 또는
`tunnel-client`가 비정상 종료되면 재시작합니다. `doctor`는 로컬 `/readyz`,
tunnel-client의 loopback `/readyz`, Keychain 자격증명 유무, 설정 권한, 그리고
LaunchAgent 상태를 확인합니다. 연결이 실패해도 ChatGPT가 로컬 프로세스를 직접
복구할 수는 없으므로, 이 Mac 측 감시자가 복구를 담당합니다.

이미 8000 포트를 쓰는 이전 서버가 새 `/readyz` 점검에 응답하지 않으면 복구기는
중복 실행하지 않고 안전하게 중단합니다. 그 경우 이전 로컬 서버를 종료한 뒤
`aichallenge-mcp-runtime up`을 다시 실행합니다.

```bash
aichallenge-mcp-runtime status
aichallenge-mcp-runtime uninstall-launchd
```

## Source 추가

새 source는 한 변경으로 다음을 포함해야 합니다.

1. 공개 접근 규칙과 필수 필드를 가진 source adapter
2. `server.py`의 공개 MCP source 도구와 source registry 등록
3. HTML/API fixture와 source 계약·orchestrator 테스트
4. 실제 공개 페이지/API initial live smoke test
5. 이 README와 `CONTEXT.md`의 source 목록 및 범위 갱신

로그인, CAPTCHA 우회, private data, 사용자 제공 URL은 지원하지 않습니다. 등록 source 수는 최대 20개를 목표로 유지합니다. source가 실패하면 다른 source의 성공 결과를 지우지 말고, 실패를 대회 마감으로 해석하지 않습니다.

## 운영 경계

이 프로젝트는 빠른 현재 정보 수집과 ChatGPT 전달까지만 담당합니다. 결과를 이용한 일정 관리, 자동 발송, 데이터베이스 저장, 분석 보고서는 범위 밖입니다.

에이전트·운영자가 구현 구조, 데이터 계약, source 온보딩, 보안 불변 조건을 확인할 때는 [CONTEXT.md](CONTEXT.md)를 기준으로 합니다.
