#!/usr/bin/env python3
"""Static audit of an enforcement check and its tests — can this gate say no?

Four findings, each earned by a control that ran, stayed green, and protected
nothing:

  rubber-stamp      a test module where no test asserts a REFUSAL. A gate that
                    only says GO is a rubber stamp, and a freshly written gate
                    passing on today's data feels like evidence that it works.
  never-passes      ...and the mirror: no test asserts a PASS, so the gate is
                    stuck in the other position and cannot distinguish anything.
  swallowed-failure a broad `except` whose handler neither re-raises nor records
                    a failing verdict. One unhashable value raised inside a gate
                    wrapped in a blanket except, and the caller reported all
                    four of its checks clean.
  unwired-verdict   a gate with a CLI that can never exit non-zero. It reports;
                    it does not refuse.
  stranded-tests    `if __name__ == "__main__"` above later test classes. One
                    such file ran 12 tests, printed OK, and skipped 13.

This checks the MECHANICAL half of "prove it can say no". The other half is not
static and cannot be: mutate the enforcement line, and watch the decisive test
go red. A test that survives that mutation was testing something else.

Standard library only. No network. Python sources only.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

# Vocabulary that reads as "this run was refused". Extend with --blocking for a
# project whose verdicts have their own names.
BLOCKING_WORDS = {
    "FAIL", "FAILED", "FAILING", "FAILURE", "BLOCK", "BLOCKED", "BLOCKING",
    "REFUSE", "REFUSED", "REJECT", "REJECTED", "DENY", "DENIED", "INVALID",
    "VIOLATION", "BROKEN", "OWED", "DEBT", "STALE", "ERROR", "UNSAFE",
}
PASSING_WORDS = {
    "OK", "PASS", "PASSED", "PASSING", "GO", "CLEAN", "GREEN", "ALLOW",
    "ALLOWED", "VALID", "SUCCESS", "SATISFIED", "READY",
}
# Numeric evidence (a 0 or a 1) only counts where the call also names something
# exit-code-shaped; otherwise `assertEqual(len(rows), 1)` would read as a proof
# of refusal.
EXIT_HINT = re.compile(r"return_?code|exit_?code|exit_?status|\bstatus\b|verdict",
                       re.IGNORECASE)
RAISES = {"assertRaises", "assertRaisesRegex", "raises"}
WORD = re.compile(r"[^A-Za-z0-9]+")


def _words(value: str) -> set[str]:
    return {w for w in WORD.split(value.upper()) if w} | {value.upper()}


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _names_in(node: ast.AST) -> str:
    """Flat text of every identifier under `node`, for the exit-code hint."""
    parts = []
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            parts.append(child.id)
        elif isinstance(child, ast.Attribute):
            parts.append(child.attr)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            parts.append(child.value)
    return " ".join(parts)


def _assertion_nodes(func: ast.AST):
    """Only assertion contexts, never docstrings or prose.

    A test whose docstring says "must not fail" would otherwise count as proof
    that the gate can refuse, which is the exact confusion this tool exists to
    remove.
    """
    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            yield node
        elif isinstance(node, ast.Call) and (
                _call_name(node).startswith("assert") or _call_name(node) in RAISES):
            yield node
        elif isinstance(node, ast.With):
            for item in node.items:
                if isinstance(item.context_expr, ast.Call) and \
                        _call_name(item.context_expr) in RAISES:
                    yield item.context_expr


def classify_test(func: ast.AST, blocking: set[str], passing: set[str]) -> set[str]:
    """{'blocking'} / {'passing'} / both / neither, for one test function."""
    found: set[str] = set()
    for node in _assertion_nodes(func):
        name = _call_name(node)
        if name in RAISES or name in ("assertFalse", "assertNotEqual", "assertNotIn"):
            found.add("blocking")
        elif name == "assertTrue":
            found.add("passing")
        exit_shaped = bool(EXIT_HINT.search(_names_in(node)))
        for child in ast.walk(node):
            if not isinstance(child, ast.Constant):
                continue
            value = child.value
            if isinstance(value, str):
                words = _words(value)
                if words & blocking:
                    found.add("blocking")
                if words & passing:
                    found.add("passing")
            elif isinstance(value, int) and not isinstance(value, bool) and exit_shaped:
                found.add("passing" if value == 0 else "blocking")
    return found


def audit_tests(path: Path, tree: ast.Module, blocking: set[str],
                passing: set[str], min_blocking: int) -> list[dict]:
    tests = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and n.name.startswith("test")]
    findings = []
    if not tests:
        return findings
    verdicts = [classify_test(t, blocking, passing) for t in tests]
    n_blocking = sum(1 for v in verdicts if "blocking" in v)
    n_passing = sum(1 for v in verdicts if "passing" in v)
    if n_blocking < min_blocking:
        findings.append({
            "check": "rubber-stamp", "file": str(path), "line": tests[0].lineno,
            "message": (f"{len(tests)} test(s), {n_blocking} of which assert a "
                        f"refusal (want {min_blocking}). A gate that only says "
                        f"GO is a rubber stamp — write the blocking cases and "
                        f"count them."),
        })
    if n_passing == 0:
        findings.append({
            "check": "never-passes", "file": str(path), "line": tests[0].lineno,
            "message": (f"{len(tests)} test(s), none of which assert a pass. A "
                        f"gate stuck in the refusing position is decoration in "
                        f"the other direction, and gets switched off wholesale."),
        })
    findings += _stranded(path, tree)
    return findings


def _stranded(path: Path, tree: ast.Module) -> list[dict]:
    """Definitions below `if __name__ == "__main__"` never exist when the file
    is run directly — the runner has already finished."""
    for index, node in enumerate(tree.body):
        if not (isinstance(node, ast.If) and "__main__" in _names_in(node.test)):
            continue
        later = [n for n in tree.body[index + 1:]
                 if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
        if later:
            return [{
                "check": "stranded-tests", "file": str(path), "line": node.lineno,
                "message": (f"the __main__ entrypoint sits above "
                            f"{len(later)} later definition(s) (first: "
                            f"{later[0].name!r}, line {later[0].lineno}). Running "
                            f"this file directly executes the tests defined so "
                            f"far, prints OK, and silently skips the rest."),
            }]
    return []


def _broad(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(isinstance(t, ast.Name) and t.id in ("Exception", "BaseException")
               for t in types)


def _swallow_shape(handler: ast.ExceptHandler) -> str:
    """What the handler does instead, in the reader's terms."""
    last = handler.body[-1] if handler.body else None
    if isinstance(last, (ast.Pass, ast.Continue)):
        return ("it drops this input from the result, and a source that errored "
                "is not a source that returned nothing")
    if isinstance(last, ast.Return):
        return "it returns a value the caller cannot tell from a clean result"
    return "the failure leaves no trace the caller can act on"


def audit_gate(path: Path, tree: ast.Module, blocking: set[str]) -> list[dict]:
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if not _broad(handler):
                continue
            body = ast.Module(body=handler.body, type_ignores=[])
            if any(isinstance(n, ast.Raise) for n in ast.walk(body)):
                continue
            if any(isinstance(n, ast.Constant) and isinstance(n.value, str)
                   and _words(n.value) & blocking for n in ast.walk(body)):
                continue
            findings.append({
                "check": "swallowed-failure", "file": str(path),
                "line": handler.lineno,
                "message": (f"broad `except` that neither re-raises nor records a "
                            f"failing verdict — {_swallow_shape(handler)}. One "
                            f"raise inside a gate wrapped like this reported "
                            f"every check clean. Fail open only on purpose, "
                            f"per-probe, with the reason stated."),
            })
    findings += _unwired(path, tree)
    return findings


def _nonzero_int(node: ast.AST | None) -> bool:
    """A non-zero integer literal anywhere under `node`.

    Covers `return 1`, `sys.exit(2)`, `return 1 if broken else 0`, and the
    dispatch form `sys.exit({"GO": 0, "HOLD": 1}[verdict])` — all the ways a
    refusal actually reaches an exit code.
    """
    return node is not None and any(
        isinstance(n, ast.Constant) and isinstance(n.value, int)
        and not isinstance(n.value, bool) and n.value != 0
        for n in ast.walk(node))


def _unwired(path: Path, tree: ast.Module) -> list[dict]:
    """A verdict not wired to a non-zero exit reports; it does not refuse."""
    has_entrypoint = any(isinstance(n, ast.If) and "__main__" in _names_in(n.test)
                         for n in tree.body)
    if not has_entrypoint:
        return []
    defined = {n.name for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and _nonzero_int(node.value):
            return []
        if isinstance(node, ast.Raise) and _call_name(node.exc or node) == "SystemExit":
            return []
        if not (isinstance(node, ast.Call) and _call_name(node) in ("exit", "_exit")):
            continue
        if any(_nonzero_int(a) for a in node.args):
            return []
        # `sys.exit(main())` where `main` is imported: the verdicts live in
        # another file, so this one cannot be judged. Stay quiet rather than
        # invent a finding — a checker that cries wolf gets switched off.
        if any(isinstance(a, ast.Call) and _call_name(a) not in defined
               for a in node.args):
            return []
    return [{
        "check": "unwired-verdict", "file": str(path), "line": 1,
        "message": ("a command-line entrypoint with no path to a non-zero exit. "
                    "Whatever this computes, nothing downstream can refuse on "
                    "it — wire the broken verdicts to the exit code."),
    }]


def run(gates: list[Path], tests: list[Path], *, blocking: set[str],
        passing: set[str], min_blocking: int) -> list[dict]:
    findings = []
    for path, is_test in [(p, False) for p in gates] + [(p, True) for p in tests]:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, ValueError) as exc:
            findings.append({"check": "unreadable", "file": str(path), "line": 1,
                             "message": f"could not parse: {exc}"})
            continue
        findings += (audit_tests(path, tree, blocking, passing, min_blocking)
                     if is_test else audit_gate(path, tree, blocking))
    return findings


def render(findings: list[dict]) -> str:
    if not findings:
        return "GATE SELFTEST — clean"
    lines = [f"GATE SELFTEST — {len(findings)} finding(s)"]
    for f in findings:
        lines.append(f"  {f['file']}:{f['line']}  [{f['check']}]")
        lines.append(f"      {f['message']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Can this gate say no? A static audit of a check and its tests.")
    parser.add_argument("--gate", type=Path, nargs="*", default=[],
                        metavar="FILE", help="gate implementation source")
    parser.add_argument("--tests", type=Path, nargs="*", default=[],
                        metavar="FILE", help="the gate's test module(s)")
    parser.add_argument("--blocking", default="",
                        help="comma-separated extra words that read as a refusal")
    parser.add_argument("--passing", default="",
                        help="comma-separated extra words that read as a pass")
    parser.add_argument("--min-blocking", type=int, default=1,
                        help="tests that must assert a refusal (default: 1)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not args.gate and not args.tests:
        parser.error("give --gate and/or --tests")

    def extra(raw: str) -> set[str]:
        return {w.strip().upper() for w in raw.split(",") if w.strip()}

    findings = run(args.gate, args.tests,
                   blocking=BLOCKING_WORDS | extra(args.blocking),
                   passing=PASSING_WORDS | extra(args.passing),
                   min_blocking=args.min_blocking)
    print(json.dumps(findings, indent=2) if args.json else render(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
