"""Shared helpers for the skill-script tests.

The scripts are standalone files, not an installed package, so they are loaded by
path. Keeping that in one place means a moved script breaks one line, not six
test modules.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"


def load_script(skill: str, filename: str) -> ModuleType:
    path = SKILLS / skill / "scripts" / filename
    if not path.is_file():
        raise FileNotFoundError(f"no such script: {path}")
    spec = importlib.util.spec_from_file_location(f"skillscript_{skill}_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_script(skill: str, filename: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a script as a subprocess — the way an agent actually invokes it."""
    path = SKILLS / skill / "scripts" / filename
    return subprocess.run(
        [sys.executable, str(path), *args], capture_output=True, text=True, cwd=cwd
    )


def git_repo(root: Path) -> None:
    """Initialize a throwaway repository with deterministic identity."""
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    for key, value in (("user.email", "t@example.com"), ("user.name", "Test")):
        subprocess.run(["git", "-C", str(root), "config", key, value], check=True)


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    )
    return proc.stdout


def commit_all(root: Path, message: str) -> None:
    git(root, "add", "-A")
    git(root, "commit", "-qm", message)
