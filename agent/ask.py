"""CLI entry point: ask the streaming-rag agent a single question

Usage:
    python -m agent.ask 'QUESTION'"""

import argparse

from agent.loop import run_loop


def main():
    parser = argparse.ArgumentParser(description="Ask the streaming-rag agent a question")
    parser.add_argument("question", help="The question to ask, in quotes")
    args = parser.parse_args()

    answer = run_loop(args.question)
    print("\n=== answer ===")
    print(answer)


if __name__ == "__main__":
    main()
