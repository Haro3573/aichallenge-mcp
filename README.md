# AI Challenge Briefing MCP (Codex Local)

Codex의 **AI 대회 브리핑 (로컬)** 플러그인이 운영자 등록 공개 source에서 AI 대회·해커톤·챌린지 정보를 매번 새로 수집하도록 하는 경량·무상태 MCP 서버입니다. 이 복제본은 Codex가 직접 실행하는 `stdio` 전송 방식을 기본으로 하므로 Secure MCP Tunnel, HTTP 포트, 상시 LaunchAgent가 필요 없습니다.

이 서버는 범용 URL 스크레이퍼가 아닙니다. 사용자는 URL을 입력하지 않으며, 운영자가 코드·테스트와 함께 등록한 source만 수집합니다. 서버는 현재 수집 데이터만 반환하고, 해석·추천·리포트·후속 대화는 Codex의 플러그인 Skill이 담당합니다.

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

이 MCP 서버는 문서·앱 카드·다운로드 UI를 만들지 않습니다. 서버는 상태나 데이터베이스를 사용하지 않습니다. Codex Skill은 현재 결과로 간결한 한국어 브리핑을 작성하고, 전체 JSON이나 읽기용 리포트는 사용자가 명시적으로 요청할 때만 만듭니다.

이 MCP는 이전 실행을 저장하지 않으므로 신규·변경·삭제 비교를 제공할 수 없습니다. source 수집 실패 역시 대회 종료나 삭제의 증거가 아닙니다.

## Codex 로컬 플러그인 실행

Python 3.11+과 [`uv`](https://docs.astral.sh/uv/)가 필요합니다. Codex가 플러그인을 처음 실행하면 `uv`가 `uv.lock`에 고정된 의존성을 설치합니다.

```bash
git clone <your-fork-url> aichallenge-briefing-stdio
cd aichallenge-briefing-stdio
uv run --locked --no-dev aichallenge-mcp-stdio
```

Kaggle source를 함께 수집하려면 Kaggle 계정의 API 토큰을 로컬 런타임 환경에 설정합니다. 토큰 값을 `.env`, 저장소, 로그, Codex 대화에 넣지 않습니다.

```bash
export KAGGLE_API_TOKEN='...'
```

레거시 키 쌍도 지원합니다.

```bash
export KAGGLE_USERNAME='...'
export KAGGLE_KEY='...'
```

Codex는 플러그인의 `.mcp.json`에 지정된 `uv run --locked --no-dev aichallenge-mcp-stdio` 명령을 실행하고 표준입력·표준출력으로 MCP 요청을 전달합니다. HTTP listener, `/healthz`, `/readyz`, OpenAI Secure MCP Tunnel, `tunnel-client`는 이 경로에서 사용하지 않습니다.

로컬 수집 검증:

```bash
python -m aichallenge_mcp.cli
pytest
python -m compileall src
```

## 기존 ChatGPT/Tunnel 복제본과의 차이

이 저장소는 원본 Secure Tunnel 프로젝트의 독립 복제본입니다. 기존 원본은 ChatGPT Developer Mode용 HTTP+Tunnel 경로로 그대로 보존됩니다. 이 복제본의 플러그인 manifest는 stdio 경로만 실행합니다.

```text
Codex Desktop → stdio → AI Challenge Briefing MCP → 공개 source
```

Kaggle이 필요한 경우 `.mcp.json`에는 Keychain 서비스명만 설정합니다. 실행 시 `aichallenge_mcp.stdio`가 해당 macOS Keychain password를 메모리의 `KAGGLE_API_TOKEN` 환경변수로만 전달하며, 토큰을 파일·로그·MCP 결과에 쓰지 않습니다.

원본을 비교·참조하기 쉽도록 `server.py`의 HTTP helper, `runtime.py`, `chatgpt-skills/`, Dockerfile은 이 복제본에도 남아 있습니다. 이 파일들은 Codex 플러그인 manifest에서 호출하지 않는 **레거시 참조물**이며, 공개 플러그인의 지원 경로는 stdio뿐입니다.

## Source 추가

새 source는 한 변경으로 다음을 포함해야 합니다.

1. 공개 접근 규칙과 필수 필드를 가진 source adapter
2. `server.py`의 공개 MCP source 도구와 source registry 등록
3. HTML/API fixture와 source 계약·orchestrator 테스트
4. 실제 공개 페이지/API initial live smoke test
5. 이 README와 `CONTEXT.md`의 source 목록 및 범위 갱신

로그인, CAPTCHA 우회, private data, 사용자 제공 URL은 지원하지 않습니다. 등록 source 수는 최대 20개를 목표로 유지합니다. source가 실패하면 다른 source의 성공 결과를 지우지 말고, 실패를 대회 마감으로 해석하지 않습니다.

## 운영 경계

이 프로젝트는 빠른 현재 정보 수집과 Codex 전달까지만 담당합니다. 결과를 이용한 일정 관리, 자동 발송, 데이터베이스 저장, 분석 보고서는 범위 밖입니다.

에이전트·운영자가 구현 구조, 데이터 계약, source 온보딩, 보안 불변 조건을 확인할 때는 [CONTEXT.md](CONTEXT.md)를 기준으로 합니다.
