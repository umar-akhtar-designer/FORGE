"""Unified-diff utilities shared by PR shipping and skill learning."""

from __future__ import annotations


def apply_unified_diff(source: str, diff: str) -> str:
    """Apply a single-file unified diff (difflib output) to ``source``."""
    out: list[str] = []
    for raw in diff.splitlines(keepends=True):
        if raw == "\n":
            continue
        if raw.startswith(("@", "---", "+++", "\\")):
            continue
        if raw[0] == "+":
            out.append(raw[1:])
        elif raw[0] == " ":
            out.append(raw[1:])
        elif raw[0] == "-":
            # A removal and its replacement can be glued onto one line when the
            # file has no trailing newline: "-old+new".
            plus = raw.find("+", 1)
            if plus != -1:
                out.append(raw[plus + 1:])
    return "".join(out)