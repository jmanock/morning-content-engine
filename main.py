from __future__ import annotations

import argparse

from content_engine.engine import (
    brand_lines,
    clean,
    generate,
    history_lines,
    import_signal_lines,
    morning,
    platform_report,
    preview_path,
    queue_lines,
    signal_lines,
    stats_text,
    top,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Morning Content Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("morning", help="Run the reusable multi-brand morning content pipeline")
    subparsers.add_parser("import-signals", help="Import pending JSON signal files from signals/inbox")
    subparsers.add_parser("signals", help="List recently imported signals")
    subparsers.add_parser("queue", help="Create or show today's signal-driven content queue")
    subparsers.add_parser("brands", help="List configured brands")
    subparsers.add_parser("history", help="Show recent archived generated posts")
    subparsers.add_parser("stats", help="Print latest content statistics")
    subparsers.add_parser("preview", help="Print the latest HTML preview path")
    subparsers.add_parser("generate", help="Generate today's social content package")
    subparsers.add_parser("report", help="Print the latest platform summary report path")
    subparsers.add_parser("top", help="Show the current top ranked sample deals")
    subparsers.add_parser("clean", help="Clear generated output files")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "morning":
        report_dir = morning()
        print(f"Generated morning content platform reports: {report_dir}")
    elif args.command == "import-signals":
        for line in import_signal_lines():
            print(line)
    elif args.command == "signals":
        for line in signal_lines():
            print(line)
    elif args.command == "queue":
        for line in queue_lines():
            print(line)
    elif args.command == "brands":
        for line in brand_lines():
            print(line)
    elif args.command == "history":
        for line in history_lines():
            print(line)
    elif args.command == "stats":
        print(stats_text())
    elif args.command == "preview":
        print(preview_path())
    elif args.command == "generate":
        output_dir = generate()
        print(f"Generated daily package: {output_dir}")
    elif args.command == "report":
        report_path = platform_report()
        print(report_path)
    elif args.command == "top":
        for line in top():
            print(line)
    elif args.command == "clean":
        clean()
        print("Output folder cleaned.")


if __name__ == "__main__":
    main()
