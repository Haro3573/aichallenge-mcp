# 공개 ChatGPT Plugin 전환 체크리스트

## 이 저장소에서 완료된 준비

- Streamable HTTP MCP 서버를 컨테이너로 실행할 수 있다.
- `/healthz`와 `/readyz`가 프로세스와 production 설정을 각각 점검한다.
- `MCP_ALLOWED_HOSTS`로 공개 호스트를 명시하고, `PORT` 환경 변수를 지원한다.
- 모든 도구는 명시적으로 읽기 전용, 비파괴, 비공개-상태변경으로 표시된다.
- [chatgpt-app-submission.json](../chatgpt-app-submission.json)에 제출용 앱 정보와 5개 긍정·3개 부정 테스트가 있다.

## 실제 공개 전환에 필요한 운영자 작업

1. 고정 공개 HTTPS 도메인과 관리형 컨테이너 호스트를 준비한다.
2. 호스트의 secret manager에 Kaggle 서비스 자격증명을 등록한다. 저장소, 이미지, 대화, 로그에 넣지 않는다.
3. `MCP_PRODUCTION=true`, `MCP_ALLOWED_HOSTS=<공개-호스트>`, `REQUIRE_KAGGLE_CREDENTIALS=true`로 배포한다.
4. TLS proxy/CDN이 Streamable HTTP 응답을 버퍼링하지 않는지 확인하고, `/healthz`, `/readyz`, `/mcp`를 외부에서 검사한다.
5. Platform에서 Apps Management Write 권한과 게시자 신원 확인을 완료하고, 도메인 소유권 challenge와 서버 스캔을 공개 URL에서 수행한다.
6. 공개 지원·개인정보처리방침·이용약관 URL, 데모 동영상, 테스트 결과를 준비해 Plugins Directory 심사를 제출한다.

## 배포 후 수용 기준

- 새 ChatGPT 세션에서 로컬 프로세스나 Secure Tunnel 없이 도구를 발견하고 호출할 수 있다.
- `collect_all_sources`가 다른 source 실패와 무관하게 성공한 source의 현재 결과를 반환한다.
- Kaggle 자격증명이 누락되면 `/readyz`가 503을 반환하되 비밀값은 노출하지 않는다.
- 임의 URL, 과거 변경 비교, 자격증명 요청은 MCP 수집 도구를 호출하지 않는다.
