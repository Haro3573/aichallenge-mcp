# AI Challenge Briefing MCP

ChatGPT의 **AI 대회 브리핑** 앱이 운영자 등록 공개 소스에서 AI 대회·해커톤·챌린지 정보를 매번 새로 수집하도록 하는 경량 MCP 서버입니다.

이 서버는 범용 URL 스크레이퍼가 아닙니다. 사용자는 URL을 입력하지 않으며, 운영자가 코드·테스트와 함께 등록한 source만 수집합니다.

## 제공 도구

- `collect_all_sources`: 모든 등록 source를 동시에 수집하는 기본 오케스트레이터입니다. source별 전체 결과, 원본 URL, 수집 시각, 성공/실패와 경고를 반환합니다. source마다 20초 제한과 1회 재시도를 적용하며, 한 source 실패가 다른 결과를 지우지 않습니다.
- `collect_aichallenge4all`: `aichallenge4all.or.kr`의 현재 전체 결과를 반환하는 공개 source 도구입니다. ChatGPT가 후속 질문에서 직접 사용할 수 있습니다.
- `collect_dacon_competitions`: `dacon.io/competitions`에서 현재 참여 가능한 공식 대회(`참가신청중`·`진행중`·`연습`)와 공개 상세 정보를 반환하는 source 도구입니다.
- `collect_kaggle_competitions`: Kaggle 공식 인증 API에서 활성 대회를 읽고, 원격 참여 정책을 만족하는 `location: Online` 항목만 반환하는 source 도구입니다. 런타임 환경에 `KAGGLE_API_TOKEN` 또는 `KAGGLE_USERNAME`·`KAGGLE_KEY`가 필요하며, 자격증명과 개인화 필드는 반환하지 않습니다.
- `collect_devpost_hackathons`: Devpost 공개 목록 API에서 현재 접수 중인 해커톤을 반환하는 source 도구입니다. 온라인·오프라인 위치는 필터링하지 않고 원본 `location` 필드로 제공합니다. Devpost 계정이나 API 키는 사용하지 않습니다.

수집 결과는 상태가 없습니다. SQLite, 이전 실행 결과, 신규·변경 비교, stale fallback, 아카이브는 사용하지 않습니다.

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
4. 앱의 도구 목록에 `collect_all_sources`와 등록 source 도구가 표시되는지 확인한다.
5. `chatgpt-skills/ai-contest-briefing-chatgpt.skill.zip`을 ChatGPT Skill로 설치 또는 업데이트한다.
6. `@AI 대회 브리핑`을 선택하면 Skill이 `collect_all_sources`를 호출한다.

로컬 서버와 tunnel-client는 모두 실행 중이어야 ChatGPT가 도구를 검색·호출할 수 있습니다. Codex 세션이 종료되면 이 로컬 프로세스와 임시 터널도 종료될 수 있습니다.

## Source 추가

새 source는 한 변경으로 다음을 포함해야 합니다.

1. 공개 접근 규칙과 필수 필드를 가진 source adapter
2. 공개 MCP source 도구
3. source registry 등록
4. HTML fixture와 계약 테스트
5. 실제 공개 페이지 초기 수집 검증

로그인, CAPTCHA 우회, private data, 사용자 제공 URL은 지원하지 않습니다. 등록 source 수는 최대 20개로 유지합니다.

## 운영 경계

이 프로젝트는 빠른 현재 정보 수집과 ChatGPT 전달까지만 담당합니다. 결과를 이용한 일정 관리, 자동 발송, 데이터베이스 저장, 분석 보고서는 범위 밖입니다.
