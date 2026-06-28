from __future__ import annotations

import argparse

from src.a2a_ecommerce_demo.mock_graph import run_mock_demo
from src.a2a_ecommerce_demo.supervisor_app import build_supervisor_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the A2A ecommerce LangGraph demo.")
    parser.add_argument(
        "task",
        nargs="?",
        default="帮我优化一款跨境电商商品的 listing，并给出广告关键词建议",
        help="Task for the multi-agent system.",
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="Use real LLM supervisor mode. Requires OPENAI_API_KEY in .env or environment.",
    )
    args = parser.parse_args()

    if args.real:
        app = build_supervisor_app()
        result = app.invoke({"messages": [{"role": "user", "content": args.task}]})
        print(result["messages"][-1].content)
        return

    print(run_mock_demo(args.task))


if __name__ == "__main__":
    main()
