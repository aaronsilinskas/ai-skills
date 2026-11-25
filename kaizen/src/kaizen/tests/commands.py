"""Every ``kaizen`` command's parser, for the tests that check a rule across all of them."""

import argparse

from kaizen.shared.cli import GROUPS


def command_parsers() -> dict[str, argparse.ArgumentParser]:
    """Every command's parser, keyed by its group and name, such as ``"ticket start"``."""
    parsers: dict[str, argparse.ArgumentParser] = {}
    for group, (_, commands) in GROUPS.items():
        subparsers = argparse.ArgumentParser().add_subparsers()
        for module in commands:
            module.add_parser(subparsers)
        parsers |= {f"{group} {name}": command for name, command in subparsers.choices.items()}
    return parsers


def has_dry_run(parser: argparse.ArgumentParser) -> bool:
    return any("--dry-run" in action.option_strings for action in parser._actions)
