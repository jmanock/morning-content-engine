from __future__ import annotations

import argparse

from content_engine.engine import clean, generate, report, top


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Morning Content Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("generate", help="Generate today's social content package")
    subparsers.add_parser("report", help="Print the latest report path, generating one if needed")
    subparsers.add_parser("top", help="Show the current top ranked sample deals")
    subparsers.add_parser("clean", help="Clear generated output files")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "generate":
        output_dir = generate()
        print(f"Generated daily package: {output_dir}")
    elif args.command == "report":
        report_path = report()
        print(report_path)
    elif args.command == "top":
        for line in top():
            print(line)
    elif args.command == "clean":
        clean()
        print("Output folder cleaned.")


if __name__ == "__main__":
    main()

