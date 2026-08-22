from __future__ import annotations

import argparse
import json

from .service import BriefingService


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Challenge Briefing CLI")
    parser.add_argument("command", choices=("refresh", "overview"))
    args = parser.parse_args()
    service = BriefingService()
    result = service.refresh() if args.command == "refresh" else service.active_overview()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
