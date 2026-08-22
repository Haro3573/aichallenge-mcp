# AI Challenge Briefing MCP

ChatGPT Workspace Agent가 `aichallenge4all.or.kr`의 공개 대회 정보를 호출할 때마다 확인하고, 이전 실행과 비교해 신규·변경 항목과 접수중·진행중 현황을 반환하는 read-only MCP 서버입니다.

앱 유형: `tool-only`

## 제공 도구

- `refresh_and_brief`: 사이트와 연결된 공개 상세 페이지를 수집하고 DB에 스냅샷을 저장합니다. 신규·변경·접수중·진행중·마감 임박 항목을 JSON으로 반환합니다.
- `get_active_overview`: DB에 저장된 접수중·진행중 대회를 조회합니다.
- `search`: 표준 MCP 검색 도구입니다. DB에 저장된 대회를 검색합니다.
- `fetch`: 표준 MCP 가져오기 도구입니다. 대회 ID의 상세 내용을 반환합니다.

## 로컬 실행

Python 3.11+이 필요합니다.

```bash
cd aichallenge-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m aichallenge_mcp.server
```

서버는 기본적으로 `http://localhost:8000/mcp`에서 Streamable HTTP MCP를 제공합니다.

공개 HTTPS reverse proxy 또는 터널을 사용하는 경우, FastMCP의 Host 검증에 해당 공개 호스트를 명시합니다. 예를 들어 `MCP_ALLOWED_HOSTS=example.com`을 설정한 뒤 서버를 재시작합니다. 이 값은 쉼표로 구분해 여러 호스트를 허용할 수 있으며, 와일드카드 대신 실제 공개 호스트만 넣으세요.

간단한 수집 테스트:

```bash
python -m aichallenge_mcp.cli refresh
python -m aichallenge_mcp.cli overview
```

## ChatGPT Developer Mode 연결 (Secure MCP Tunnel)

Secure MCP Tunnel은 로컬 MCP 서버를 공개 인터넷에 노출하지 않고 ChatGPT Developer Mode에 연결합니다. 최신 `tunnel-client` 릴리스와 Platform의 터널 설정을 사용하세요.

1. `python -m aichallenge_mcp.server`로 `http://127.0.0.1:8000/mcp`를 실행합니다.
2. Platform tunnel settings에서 터널을 만들고, 대상 ChatGPT workspace와 연결합니다. 터널 생성·수정에는 **Tunnels Read + Manage**, 실행과 앱에서 선택에는 **Tunnels Read + Use** 권한이 필요합니다.
3. 최신 `tunnel-client`로 HTTP MCP 서버 URL을 `http://127.0.0.1:8000/mcp`로 지정하고 실행합니다. API 키는 환경변수 또는 공식 credential flow로만 제공하고 저장소에 기록하지 않습니다.
4. `tunnel-client`의 health/ready 상태와 `tunnel_id`를 확인합니다. 클라이언트가 실행 중이지 않으면 ChatGPT의 도구 검색과 호출이 실패합니다.
5. ChatGPT **Settings → Security and login → Developer mode**를 켭니다.
6. ChatGPT Plugins에서 새 앱을 만들고, 이름은 `AI 대회 브리핑`, 설명은 `aichallenge4all.or.kr의 접수중·진행중 대회를 최신 수집하고 변경사항을 브리핑합니다.`로 입력합니다.
7. Connection은 **Tunnel**을 선택해 `tunnel_id`를 연결하고, 인증은 공개 데이터 서버이므로 **No Auth**를 선택합니다. 도구 네 개가 모두 검색되는지 확인한 후 생성합니다.

공식 안내: [Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels), [ChatGPT 연결 및 테스트](https://developers.openai.com/plugins/deploy/connect-chatgpt).

### API 키 없이 개발 환경에서 확인하기

Platform tunnel client는 런타임 API 키가 필요합니다. API 키를 사용하지 않는 개발 확인에는 임시 HTTPS reverse tunnel을 사용할 수 있습니다. 예를 들어 Cloudflare Quick Tunnel을 쓸 경우:

```bash
# 1) cloudflared가 출력한 공개 호스트만 허용하고 로컬 서버 실행
MCP_ALLOWED_HOSTS=<quick-tunnel-host> python -m aichallenge_mcp.server

# 2) 별도 터미널에서 로컬 HTTP MCP를 공개 HTTPS로 전달
cloudflared tunnel --url http://127.0.0.1:8000
```

출력된 `https://<quick-tunnel-host>/mcp`를 ChatGPT 앱의 **URL** 연결 방식과 **No Auth**로 등록합니다. Quick Tunnel 주소와 두 프로세스는 세션에 종속되므로, 개발 검증용으로만 사용하세요. 서버 또는 터널 클라이언트가 멈추면 ChatGPT 도구 검색과 호출도 실패합니다.

앱 생성 후 새 대화에서 다음과 같이 호출합니다.

```text
오늘 AI 대회 브리핑해줘.
```

운영 배포 시에는 터널 대신 고정 HTTPS 엔드포인트와 영속 DB를 사용하세요. SQLite는 단일 인스턴스 MVP에 적합하고, 다중 인스턴스나 팀 공유에는 PostgreSQL로 교체하는 편이 안전합니다.

## Workspace Agent 지침

`agent-instructions.md`를 Workspace Agent의 지침 또는 Skill 내용으로 사용하세요. Agent는 매번 `refresh_and_brief`를 먼저 호출한 뒤 결과를 한국어 브리핑으로 변환해야 합니다.

## 데이터 주의사항

- 공개 페이지와 공개 공고문만 수집합니다.
- CAPTCHA, 로그인, 개인정보, 참가자 제출물은 수집하지 않습니다.
- 수집 실패를 마감으로 해석하지 않고 `확인 필요`로 표시합니다.
- 사이트의 동적 영역이 비어 있으면 기존 데이터를 보존하고 `stale` 상태를 남기는 것이 운영 보강 포인트입니다.
