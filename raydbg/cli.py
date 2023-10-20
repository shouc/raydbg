import argparse
import os
import sys

from .codeql import analyze as static_analyze, llm_analysis_pretty, CodeQL
from .dynamic_analysis import analyze_pretty as dynamic_analyze_pretty
from .llm import LLM


def main():
    # run cli.py static --source xxx
    parser = argparse.ArgumentParser()
    parser.add_argument("command", help="subcommand to run", choices=["static", "dynamic", "init"])
    parser.add_argument("--model", help="model name", default="gpt-3.5-turbo")
    parser.add_argument("--cache", help="cache path", default="/tmp/llm")
    parser.add_argument("--target", nargs="+", help="argv to pass to the program")
    parser.add_argument("--no-llm", help="disable LLM", action="store_true")

    args = parser.parse_args()
    no_llm = args.no_llm
    target = args.target
    if (not target or len(target) == 0) and args.command != "init":
        print("[Failed] Please specify the target program in --target")
        sys.exit(1)
    if args.command == "static":
        print("Running static analysis...")
        if not no_llm and "OPENAI_KEY" not in os.environ:
            print("[Failed] Please specify OpenAI API (or Anyscale Endpoint) key in OPENAI_KEY environment variable")
            sys.exit(1)
        absolute_path = os.path.abspath(target[0])
        absolute_dir = os.path.dirname(absolute_path)
        llm_analysis_pretty(absolute_dir, None if no_llm else LLM(
            os.environ["OPENAI_KEY"],
            model=args.model,
            cache_path=args.cache
        ))
        return
    elif args.command == "dynamic":
        print("Running dynamic analysis...")
        absolute_path = os.path.abspath(target[0])
        dynamic_analyze_pretty(absolute_path, argv=target)
        return
    elif args.command == "init":
        print("Initializing...")
        CodeQL()
        print("Done")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
