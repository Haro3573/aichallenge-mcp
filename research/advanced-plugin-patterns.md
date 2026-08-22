# AI 대회 브리핑 고도화 사례 리서치

조사일: 2026-08-21  
범위: 공개 웹 데이터를 수집하고, 이전 결과와 비교해 사람이 읽는 브리핑으로 만드는 ChatGPT/MCP 플러그인의 다음 단계. 제품 홍보 글보다 각 제품의 공식 문서·공식 소스 저장소를 우선했다.

## 결론

현재 `aichallenge-mcp`는 이미 핵심 흐름(실수집 → SQLite 스냅샷 비교 → 한국어 브리핑)을 갖췄다. 고도화의 핵심은 **더 많은 도구를 붙이는 일**보다 다음 다섯 가지다.

1. 목록 스크래핑과 상세 페이지 검증을 분리해 데이터 품질을 높인다.
2. 원본 HTML/정규화 결과/차이를 버전으로 보존해 변경 이유를 설명 가능하게 만든다.
3. 변동성 높은 화면의 잡음은 선택자·규칙·의미 기반 비교로 줄인다.
4. 수집 실행, 재시도, 실패, 알림을 독립된 운영 파이프라인으로 만든다.
5. MCP에는 좁고 구조화된 읽기 도구와 `prompt`/`resource`를 함께 제공해 에이전트가 일관되게 사용하게 한다.

전용 “AI 대회만”을 완성형으로 제공하는 공개 ChatGPT 플러그인은 이번 1차 조사에서 확인하지 못했다. 대신 아래 제품들은 그 구성 요소를 훨씬 성숙하게 구현한 직접 비교 대상이다.

## 비교표

| 사례 | 공식적으로 확인된 성숙 기능 | 우리 프로젝트와의 차이 | 바로 적용할 업그레이드 |
| --- | --- | --- | --- |
| [Apify MCP Server](https://docs.apify.com/integrations/mcp) | Actor 검색·실행, 실행 로그, 데이터셋 조회, 페이지네이션·필드 필터, 원격 Streamable HTTP/OAuth, 필요한 도구만 선택 노출 | 현재는 네 개의 고정 도구와 로컬 SQLite 중심 | `get_run`, `get_changes`, `get_source_health`를 추가하고 모든 목록 결과에 `limit`/`cursor`/필드 선택을 둔다. 운영 배포 시 OAuth 또는 최소 권한 인증을 설계한다. |
| [Apify Actors/Schedules/Webhooks](https://docs.apify.com/actors) | 구조화 입력/출력, 서버리스 실행, 스케줄, 영속 스토리지, 모니터링·알림; [cron·시간대 스케줄](https://docs.apify.com/actors/running/schedules)과 실행 종료 webhook | 지금은 대화 호출 때만 실행하며 서버 프로세스·Quick Tunnel 생존에 의존 | human-invoke는 유지하되, 이후 별도 worker에서 수집 실행 이력·재시도·실패 알림을 갖춘 scheduler를 도입한다. ChatGPT는 최신 성공 스냅샷을 즉시 읽게 한다. |
| [Visualping](https://help.visualping.io/en/articles/4438913) | 전체/영역 감시, 텍스트·시각·코드 변화 비교, before/after 강조, 관심 변화만 필터링, AI 요약, 클라우드 모니터의 독립 실행 | 현재는 정규화된 대회 레코드 비교만 하며 증거(diff)와 변화 신뢰도가 약함 | 각 대회의 핵심 필드별 `before`/`after`, 변경 URL, 감지 시각, 변경 유형(상태·마감·요강·신규)을 저장·반환한다. 사용자 브리핑에는 이 증거 링크를 붙인다. |
| [changedetection.io](https://github.com/dgtlmoon/changedetection.io) | CSS/XPath/JSONPath/jq 선택자, 조건부 변화, 정기 점검, 브라우저 단계, 스크린샷, 다중 알림, REST/OpenAPI, JSON API 모니터링 | 사이트 템플릿 변경과 동적 페이지에 취약할 수 있고 원인 관측이 제한됨 | 소스별 extractor를 `URL + fetch 방식 + selector + 정규화 규칙` 구성으로 분리한다. 일시적 UI/광고/카운터를 제외하고, selector 테스트 fixture와 원본 스냅샷을 둔다. |
| [Browse AI Monitors](https://help.browse.ai/en/collections/11479089-monitors-alerts-change-detection) | 정기 모니터, 새 레코드만 추출, 일괄 URL 모니터, 스케줄과 변경 알림 | 현재는 ‘대회’ 엔터티는 있지만 레코드 단위 새 항목 추출 정책이 제한적 | `source_cursor`/목록 fingerprint를 도입해 목록의 새 항목과 기존 항목의 필드 변경을 명확히 구분한다. 사이트별 수집 성공률·최종 성공 시각도 함께 노출한다. |
| [MCP 공식 primitives](https://modelcontextprotocol.io/specification/2025-06-18/server/index) | 사용자 제어 `prompts`, 애플리케이션 제어 `resources`, 모델 제어 `tools`의 역할 분리; 도구에는 input/output schema·annotation 제공 가능 | 현재는 tools만 제공하고 지시는 ChatGPT Skill에 일부 분산 | MCP 서버에 `prompt`(“오늘 브리핑”, “신규·변경만”, “접수중만”)와 `resource`(최근 성공 수집, 소스 상태, 변경 피드)를 추가한다. 도구 결과에는 명시적 output schema를 제공한다. |
| [Firecrawl MCP](https://github.com/firecrawl/firecrawl-docs/blob/main/mcp-server.mdx) | hosted/local/self-hosted 선택, 대화형 OAuth와 서버용 API-key 경로, keyless 검색·스크랩 surface 분리 | 현재는 단일 No Auth Quick Tunnel이고 다중 사용자 운영 경계가 없음 | 공개 사이트 전용 No Auth는 유지하되, 장기 운영 전에는 rate limit, cache TTL, source allowlist, 운영자용 인증을 분리한다. |

## 사례별로 배울 점

### 1. Apify: ‘스크래퍼’가 아니라 실행·저장·관측 가능한 작업 단위

Apify의 Actor는 구조화 JSON 입력을 받아 수집/브라우저 자동화/처리를 하고 구조화 출력까지 내는 서버리스 프로그램이다. 수동, API/CLI, 스케줄 실행과 더 큰 자동화 조합을 지원하며 데이터·결과 파일 저장소도 제공한다. [공식 Actors 문서](https://docs.apify.com/actors)

MCP Server는 Actor 실행뿐 아니라 run, 로그, dataset을 별도 도구로 나눠서 제공한다. 특히 출력이 길 때 결과 미리보기와 전체 출력 조회를 분리하고, 결과 조회에 페이지네이션·필드 필터를 둔다. [공식 MCP 도구 문서](https://docs.apify.com/integrations/mcp)

우리 서버의 권장 형태는 다음과 같다.

```text
refresh_and_brief          # 최신 수집과 compact 브리핑
get_run(run_id)            # 수집 시각·성공/실패·소스별 결과
get_changes(since_run_id)  # 변경된 필드와 before/after 증거
get_source_health()        # URL별 최종 성공·연속 실패·레코드 수
list_competitions(...)     # status, tag, deadline, limit, cursor
fetch_competition(id)      # 현재 상세 + 최근 변경 이력
```

이렇게 하면 ChatGPT 브리핑에는 작은 결과만 주고, 추적이 필요할 때만 세부 증거를 가져온다. Apify가 production에서 필요한 도구만 `tools=`로 명시 노출하도록 권장하는 점도 참고할 만하다. 현재처럼 대회 도메인에 특화된 서버는 범용 `search/fetch`보다 의도가 분명한 적은 수의 도구가 유리하다. [Apify production guidance](https://docs.apify.com/integrations/mcp#production-best-practices)

### 2. Visualping·changedetection.io: ‘무엇이 바뀌었나’를 증명하고 잡음을 제거

Visualping은 특정 영역 또는 전체 페이지를 주기적으로 확인하고, 이전 버전과 비교해 변화 알림에 before/after 비교·추가/삭제 내용·AI 요약을 담는다. 로컬 브라우저 감시와 달리 cloud monitor는 사용자의 컴퓨터가 꺼져도 동작한다. [공식 도움말](https://help.visualping.io/en/articles/4438913)

changedetection.io는 더 구현 친화적인 참조다. CSS/XPath, JSONPath, jq로 관찰 대상을 좁히고, 조건에 맞을 때만 알림을 내며, JSON API와 브라우저 기반 fetch를 모두 지원한다. 변경을 단어·줄·문자 단위로 확인하고 URL별 스케줄도 둘 수 있다. [공식 README: 필터·스케줄](https://github.com/dgtlmoon/changedetection.io#key-features), [공식 README: API·알림](https://github.com/dgtlmoon/changedetection.io#api-support)

우리 프로젝트에는 다음 데이터 모델 보완이 우선이다.

```text
source_snapshot(id, source_id, fetched_at, http_status, content_hash, raw_location)
competition_revision(id, competition_id, run_id, field, before, after, evidence_url)
source_health(source_id, last_success_at, consecutive_failures, last_error)
```

이 구조면 “마감이 바뀌었다”가 아닌 “접수기간이 `8/31` → `9/7`로 바뀜(원문 링크)”이라는 신뢰 가능한 브리핑이 된다. 변경의 감지와 브리핑은 분리해야 하며, 수집 실패/파싱 실패/실제 빈 목록은 서로 다른 상태로 남겨야 한다. 현재 구현의 “전체 수집 실패 시 이전 결과 유지” 정책은 이 방향과 일치한다.

### 3. Browse AI: 새 레코드와 변경 레코드를 구분하는 모니터링 UX

Browse AI 공식 도움말은 모니터에서 “새 레코드만 추출”, 사용자 정의 스케줄, 다중 URL bulk monitor, 변경 알림을 독립 항목으로 제공한다. [Monitors, alerts & change detection](https://help.browse.ai/en/collections/11479089-monitors-alerts-change-detection)

대회 인덱스에는 다음 규칙이 적합하다.

- `new`: 안정적인 대회 식별자가 처음 보인 경우
- `changed`: 동일 식별자의 핵심 필드(제목, 상태, 접수기간, 상세 URL, 주최, 설명)가 달라진 경우
- `removed_from_source`: 목록에서 사라졌으나, **즉시 마감으로 해석하지 않는** 관측 상태
- `closed_confirmed`: 상세 페이지/명시 상태에서 종료가 확인된 경우
- `source_failed`: HTTP/렌더/파싱 실패로 이전 snapshot을 유지한 경우

이 네 상태를 프롬프트와 UI에서 구분하면 사용자는 ‘변화 없음’과 ‘수집이 불완전함’을 혼동하지 않는다.

### 4. MCP와 플러그인: 도구 호출만이 아니라 사용 경로를 제품화

MCP는 prompt/resource/tool을 각기 다른 제어 주체로 설계한다. prompt는 사용자가 고르는 템플릿, resource는 클라이언트가 관리하는 문맥, tool은 모델이 호출하는 실행 함수다. [공식 MCP server overview](https://modelcontextprotocol.io/specification/2025-06-18/server/index) 도구에는 `inputSchema`, 선택적 `outputSchema`, 그리고 읽기 전용·멱등성 같은 annotation을 제공할 수 있다. [공식 Tools 사양](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)

따라서 현재 ChatGPT Skill의 “먼저 `refresh_and_brief` 호출” 지침은 유지하되, 서버 차원에도 아래를 추가하는 편이 더 견고하다.

- `prompts/list`: `today_briefing`, `active_only`, `changes_since_last` 세 가지 템플릿
- `resources/list`: `aichallenge://latest-successful-run`, `aichallenge://source-health`, `aichallenge://changes/latest`
- 구조화 output schema: `counts`, `new_items`, `changed_items`, `active_items`, `warnings`, `sources`, `checked_at`의 타입을 명시
- 큰 목록은 cursor 기반 페이지네이션, 대화용 기본 `limit` 적용

MCP 명세상 도구는 모델 제어이므로 ‘항상 호출’은 클라이언트가 보장하는 강제 규칙이 아니다. 서버 instruction, 명시 Skill/Plugin, 도구 이름·설명, 작고 예측 가능한 schema를 함께 맞춰야 라우팅 성공률이 높아진다. 도구 실행에는 사람이 거부할 수 있는 흐름이 있어야 한다는 보안 원칙도 명세에 명시돼 있다. [MCP Tools user-interaction model](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)

또한 현재 `refresh_and_brief`는 외부 공개 웹을 읽지만 로컬 SQLite 캐시를 갱신한다. 따라서 화면상 위험도 표기를 단순히 read-only로 낮추기보다, 장기적으로는 `refresh`(새 snapshot을 쓰는 additive 작업)와 `brief_latest`(최근 성공 snapshot만 읽는 진짜 read-only 작업)를 분리하는 편이 정확하다. Tool annotation은 보안 보장이 아니라 클라이언트의 판단을 돕는 힌트다. [MCP tool annotations 안내](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/)

## 우선순위 제안

### P0 — 신뢰성·설명 가능성 (다음 구현 권장)

1. **필드 수준 revision 테이블과 diff API**: `changed_items`에 제목만이 아니라 어떤 필드가 어떻게 바뀌었는지, 증거 URL과 함께 반환한다.
2. **소스 health와 실패 분류**: 원본 URL별 최종 성공, HTTP 상태, 연속 실패, 파서 버전을 기록하고 `get_source_health`로 공개한다.
3. **목록/상세 2단계 수집**: 목록에서 후보를 찾고 상세를 재확인해 접수일/상태/요강을 정규화한다.
4. **fixture 기반 파서 회귀 테스트**: 실제 페이지 HTML/정규화 JSON fixture와 “템플릿 변경 시 실패해야 하는” 테스트를 추가한다.

### P1 — 사용자 경험

1. `today_briefing` 등 MCP prompt를 제공해 Skill/Plugin 유무와 무관하게 재사용 가능한 진입점을 만든다.
2. “마감 임박 7일”, 분야, 주최, 참가 자격, 온라인/오프라인, 상금 같은 정규화 필터와 정렬을 만든다.
3. `get_changes`를 통해 “지난 7일/지난 성공 수집 이후”를 정확히 비교하고, 후속 질문에서 전체 재수집을 피한다.
4. 브리핑 문장에 최신 성공 수집 시각, 성공 소스 수/전체 소스 수, 경고를 항상 표시한다.

### P2 — 운영 확장 (현재 human-invoke 범위 밖)

1. Docker/VM의 장기 실행 worker + Postgres 백업 + 안정적 HTTPS를 도입한다.
2. 수집은 cron/queue에서 실행하고, ChatGPT 호출은 저장된 최신 성공 snapshot을 읽되 “지금 새로고침”을 선택적으로 제공한다.
3. webhook/Slack/메일/RSS 발행은 사용자가 명시적으로 선택한 경우에만 추가한다. 이는 현재 제외된 자동 매일 발송과는 별도 범위다.

## 도입 시 주의점

- **스크래핑 정책**: 대상 사이트의 이용약관, robots.txt, 접근 정책을 준수해야 한다. changedetection.io도 사용자가 대상 서비스 정책과 법을 준수할 책임이 있다고 명시한다. [공식 README의 책임 고지](https://github.com/dgtlmoon/changedetection.io#disclaimer)
- **LLM 요약의 한계**: 원문 diff와 구조화된 상태를 보존하고, LLM 요약은 그 위의 표시 계층으로만 둔다. changedetection.io도 AI 요약의 누락·환각 가능성을 경고한다. [공식 README의 AI/LLM 고지](https://github.com/dgtlmoon/changedetection.io#ai--llm-features)
- **권한 최소화**: 수집형 MCP는 공개 데이터만 읽는다면 read-only 도구로 유지한다. 인증이 필요한 외부 연동이 생길 때에는 Apify MCP Connector처럼 자격증명을 실행 코드에 주입하지 않고, 권한·허용 도구 범위·실행 수명을 분리하는 모델이 안전하다. [Apify MCP Connectors security model](https://docs.apify.com/integrations/mcp-connectors#security-model)

## 참고한 1차 출처

- [Apify MCP Server 공식 문서](https://docs.apify.com/integrations/mcp)
- [Apify Actors 공식 문서](https://docs.apify.com/actors)
- [Apify Schedules 공식 문서](https://docs.apify.com/actors/running/schedules)
- [Apify Webhooks API 공식 문서](https://docs.apify.com/api/v2/webhooks-webhooks)
- [Visualping 공식 도움말](https://help.visualping.io/en/articles/4438913)
- [Browse AI 공식 도움말: monitors](https://help.browse.ai/en/collections/11479089-monitors-alerts-change-detection)
- [changedetection.io 공식 소스 저장소 README](https://github.com/dgtlmoon/changedetection.io)
- [Firecrawl MCP 공식 문서](https://github.com/firecrawl/firecrawl-docs/blob/main/mcp-server.mdx)
- [Model Context Protocol server primitives](https://modelcontextprotocol.io/specification/2025-06-18/server/index)
- [Model Context Protocol tools specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
