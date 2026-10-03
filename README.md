# AI Challenge Briefing Codex Plugin

이 저장소는 Git marketplace로 설치하는 Codex용 로컬 플러그인입니다. Codex Desktop이 이 Mac에서 stdio MCP를 직접 실행하므로 Secure Tunnel, HTTP 포트, 상시 프로세스가 필요 없습니다.

## 설치

macOS, Codex Desktop, Python 3.11+, [`uv`](https://docs.astral.sh/uv/), Git이 필요합니다. 저장소를 공개 GitHub에 올린 뒤에는 아래의 `<repository-url>`을 해당 복제 URL로 바꿉니다.

```bash
git clone <repository-url> aichallenge-briefing-stdio
cd aichallenge-briefing-stdio
codex plugin marketplace add .
codex plugin add aichallenge-briefing-stdio@aichallenge-briefing
```

설치 후 새 Codex 대화에서 “현재 AI 대회와 해커톤을 브리핑해줘”라고 요청하면 됩니다. 공개 source는 별도 계정 설정 없이 수집합니다.

## 선택 사항: Kaggle

Kaggle도 수집하려면 **토큰을 Codex 대화나 파일에 붙여 넣지 마세요.** macOS의 **Keychain Access**에서 Generic Password 항목을 만들고 다음처럼 로컬에만 보관합니다.

- Name/Service: `aichallenge-mcp-kaggle`
- Account: 본인이 알아볼 임의의 로컬 라벨
- Password: Kaggle API token

이 플러그인은 실행 시 그 password를 자식 프로세스의 메모리에만 전달합니다. 토큰은 저장소, 환경 파일, 로그, MCP 결과로 쓰지 않습니다. Keychain 항목이 없으면 Kaggle source만 경고와 함께 건너뛰며, 다른 공개 source 브리핑은 계속 사용할 수 있습니다.

Codex Skill은 Kaggle 설정이 없다는 결과를 받으면 설정 여부를 물어보고 이 절차를 안내해야 합니다. 토큰 값 자체를 요청하거나 표시해서는 안 됩니다.

## 저장소 구조

`.agents/plugins/marketplace.json`은 Git marketplace 선언이고, 실제 설치되는 플러그인은 `plugins/aichallenge-briefing-stdio/`입니다. 해당 폴더의 [README](plugins/aichallenge-briefing-stdio/README.md)에는 MCP 도구, 테스트, source 추가 규칙이 있습니다.
