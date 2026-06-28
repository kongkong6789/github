#!/usr/bin/env python3
"""Run LangGraph dev server with a stable child stdin.

`langgraph dev` can exit when launched as a detached background process if its
standard input reaches EOF. This wrapper keeps a pipe open for the child and
forwards termination signals so the existing stop script can still manage it.
"""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.a2a_ecommerce_demo.checkpoint_tools import prepare_langgraph_checkpoint_dir  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--langgraph-bin", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True)
    args = parser.parse_args()

    langgraph_bin = Path(args.langgraph_bin)
    prepare_langgraph_checkpoint_dir()
    child = subprocess.Popen(
        [
            str(langgraph_bin),
            "dev",
            "--host",
            args.host,
            "--port",
            args.port,
            "--no-browser",
            "--no-reload",
            "--n-jobs-per-worker",
            "1",
        ],
        stdin=subprocess.PIPE,
    )

    def terminate(signum: int, _frame: object) -> None:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    return child.wait()


if __name__ == "__main__":
    sys.exit(main())
