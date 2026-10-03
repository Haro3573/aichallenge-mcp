from __future__ import annotations

import argparse
import asyncio
import json

from .server import orchestrator


def main() -> None:
    argparse.ArgumentParser(description="AI Challenge source collection CLI").parse_args()
    result = asyncio.run(orchestrator.collect())
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
