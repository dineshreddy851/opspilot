from __future__ import annotations

import argparse
import shlex
import shutil
from collections.abc import Sequence

from opspilot.agent import DevOpsAgent
from opspilot.executor import CommandExecutor
from opspilot.models import Operation, Risk
from opspilot.policy import ALLOWED_EXECUTABLES, PolicyViolation
from opspilot.tools import catalog


def _command_text(operation: Operation) -> str:
    return shlex.join(operation.command)


def _print_operation(operation: Operation) -> None:
    print(f"Plan: {operation.description}")
    print(f"Risk: {operation.risk.value}")
    print(f"Command: {_command_text(operation)}")


def _confirm(operation: Operation) -> bool:
    expected = operation.name
    response = input(f"Type {expected!r} to confirm: ").strip()
    return response == expected


def _ask(args: argparse.Namespace) -> int:
    operation = DevOpsAgent().plan(args.request)
    if operation is None:
        print("I could not map that request to a safe built-in operation.")
        print("Run `opspilot tools` to see supported operations.")
        return 2

    _print_operation(operation)

    if args.plan_only:
        return 0

    if operation.risk is Risk.MUTATING and args.apply and not args.yes:
        if not _confirm(operation):
            print("Operation cancelled.")
            return 3

    try:
        result = CommandExecutor().execute(operation, apply=args.apply)
    except PolicyViolation as error:
        print(f"Policy refused operation: {error}")
        return 4

    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())
    return result.return_code


def _tools(_: argparse.Namespace) -> int:
    print("Built-in read-only operations:")
    for operation in catalog():
        print(f"  {operation.name:24} {_command_text(operation)}")
    print("Built-in controlled operation:")
    print("  restart-deployment       kubectl rollout restart deployment/<name>")
    return 0


def _doctor(_: argparse.Namespace) -> int:
    print("OpsPilot dependency check:")
    missing = []
    for executable in sorted(ALLOWED_EXECUTABLES):
        location = shutil.which(executable)
        if location:
            print(f"  OK      {executable}: {location}")
        else:
            print(f"  MISSING {executable}")
            missing.append(executable)
    print("Missing tools only affect operations that require them.")
    return 1 if missing else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opspilot",
        description="A safety-first DevOps agent bot.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask = subparsers.add_parser("ask", help="Plan and run a DevOps request.")
    ask.add_argument("request", help="Natural-language DevOps request.")
    ask.add_argument(
        "--plan-only",
        action="store_true",
        help="Show the selected operation without running it.",
    )
    ask.add_argument(
        "--apply",
        action="store_true",
        help="Authorize a built-in mutating operation.",
    )
    ask.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation; requires --apply for mutating operations.",
    )
    ask.set_defaults(handler=_ask)

    tools = subparsers.add_parser("tools", help="List built-in operations.")
    tools.set_defaults(handler=_tools)

    doctor = subparsers.add_parser("doctor", help="Check local DevOps dependencies.")
    doctor.set_defaults(handler=_doctor)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)

