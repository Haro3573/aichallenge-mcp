"""A dependency-free MCP Apps view for downloading one briefing document."""

from __future__ import annotations


BRIEFING_DOCUMENT_UI_URI = "ui://ai-contest-briefing/briefing-document-v2.html"


BRIEFING_DOCUMENT_UI_HTML = """<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>AI 대회 브리핑 문서</title>
    <style>
      :root { color-scheme: light dark; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
      body { margin: 0; padding: 16px; }
      main { display: grid; gap: 12px; }
      h1 { font-size: 16px; margin: 0; }
      p { color: CanvasText; font-size: 13px; line-height: 1.5; margin: 0; }
      button { border: 0; border-radius: 8px; cursor: pointer; font: inherit; font-weight: 600; padding: 10px 12px; width: fit-content; }
      button:disabled { cursor: not-allowed; opacity: .55; }
    </style>
  </head>
  <body>
    <main>
      <h1>AI 대회 브리핑 문서</h1>
      <p id="status">수집 결과를 준비하는 중입니다.</p>
      <button id="download" type="button" disabled>Markdown 문서 다운로드</button>
    </main>
    <script>
      (() => {
        const status = document.getElementById("status");
        const button = document.getElementById("download");
        let documentPayload = null;

        function setResult(params) {
          const summary = params && params.structuredContent;
          const meta = params && params._meta;
          const candidate = meta && meta.briefing_document;
          if (!candidate || typeof candidate.content !== "string") {
            status.textContent = "다운로드할 문서를 받지 못했습니다.";
            return;
          }
          documentPayload = candidate;
          const counts = (summary && summary.counts) || {};
          const itemCount = summary && typeof summary.item_count === "number" ? summary.item_count : 0;
          status.textContent = `수집 완료: source ${counts.succeeded || 0}/${counts.total || 0} 성공, ${itemCount}건. 아래에서 전체 결과를 받을 수 있습니다.`;
          button.disabled = false;
        }

        window.addEventListener("message", (event) => {
          if (event.source !== window.parent) return;
          const message = event.data;
          if (!message || message.jsonrpc !== "2.0") return;
          if (message.method === "ui/notifications/tool-result") setResult(message.params);
        }, { passive: true });

        button.addEventListener("click", () => {
          if (!documentPayload) return;
          const blob = new Blob([documentPayload.content], {
            type: documentPayload.mime_type || "text/markdown;charset=utf-8",
          });
          const url = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = url;
          link.download = documentPayload.file_name || "ai-contest-briefing.md";
          link.hidden = true;
          document.body.appendChild(link);
          link.click();
          link.remove();
          window.setTimeout(() => URL.revokeObjectURL(url), 0);
        });
      })();
    </script>
  </body>
</html>
"""
