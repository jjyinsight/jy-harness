#!/usr/bin/env python3
"""Phase task runner for the phased-dev skill.

Two roles:

1. **Pipeline scaffolding** — ``init`` creates ``.phased-dev/artifacts/`` and
   ``plans/phases/`` in the current project, and self-copies this script to
   ``.phased-dev/run_phases.py`` so the project is self-contained.

2. **Task state tracking** — reads task markdown files under
   ``plans/phases/<NN-name>/*.md`` and parses YAML-ish frontmatter so the
   orchestrator can ask ``next``, mark ``start`` / ``done`` / ``block`` /
   ``reset``, and check status.

Frontmatter shape (only the fields below are read/written):

    ---
    phase: 1
    task: 1
    status: pending          # pending | in-progress | done | blocked
    depends_on: []           # optional, list of paths
    ---

The script is intentionally dependency-free (no PyYAML) and conservative when
rewriting frontmatter: only the ``status:`` line is changed.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

PLANS_ROOT = Path("plans/phases")
ARTIFACTS_ROOT = Path(".phased-dev/artifacts")
VALID_STATUSES = {"pending", "in-progress", "done", "blocked"}

ARTIFACT_FILES = {
    "clarify": ARTIFACTS_ROOT / "01-clarify.md",
    "context": ARTIFACTS_ROOT / "02-context.md",
    "plan": ARTIFACTS_ROOT / "03-plan.md",
    "generate": ARTIFACTS_ROOT / "04-generate.md",
    "evaluate": ARTIFACTS_ROOT / "05-evaluate.md",
}

# Minimum required headings per artifact phase. ``validate`` checks both file
# existence and that these substrings appear somewhere in the body.
ARTIFACT_REQUIRED = {
    "clarify": ["# Clarify", "## 결정"],
    "context": ["# Context", "## 코드베이스 상태"],
    "plan": ["# Plan", "## 페이즈"],
    "generate": ["# Generate Log"],
    "evaluate": ["# Evaluate", "## 실행한 명령"],
}


@dataclass(frozen=True)
class Task:
    path: Path
    phase_dir: str
    title: str
    status: str
    depends_on: tuple[str, ...]


# --------------------------------------------------------------------------- #
# Frontmatter helpers
# --------------------------------------------------------------------------- #

def _read_frontmatter(text: str) -> tuple[dict[str, str], int]:
    """Return (fields, end_index_after_closing_fence).

    end_index is 0 when no frontmatter is present.
    """
    if not text.startswith("---"):
        return {}, 0
    close = text.find("\n---", 3)
    if close == -1:
        return {}, 0
    block = text[3:close].strip("\n")
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    end = close + len("\n---")
    if end < len(text) and text[end] == "\n":
        end += 1
    return fields, end


def _parse_depends(raw: str) -> tuple[str, ...]:
    raw = raw.strip()
    if not raw or raw == "[]":
        return ()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
        items = [p.strip().strip("'\"") for p in inner.split(",") if p.strip()]
        return tuple(items)
    return tuple(p.strip().strip("'\"") for p in raw.split(",") if p.strip())


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def load_tasks(root: Path = PLANS_ROOT) -> list[Task]:
    if not root.exists():
        return []
    tasks: list[Task] = []
    for phase_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for f in sorted(phase_dir.glob("*.md")):
            if f.name.lower() == "readme.md":
                continue
            text = f.read_text(encoding="utf-8")
            fm, _ = _read_frontmatter(text)
            tasks.append(
                Task(
                    path=f,
                    phase_dir=phase_dir.name,
                    title=_first_heading(text) or f.stem,
                    status=fm.get("status", "pending"),
                    depends_on=_parse_depends(fm.get("depends_on", "")),
                )
            )
    return tasks


def _set_status(path: Path, new_status: str) -> None:
    if new_status not in VALID_STATUSES:
        raise SystemExit(
            f"invalid status '{new_status}'. valid: {sorted(VALID_STATUSES)}"
        )
    text = path.read_text(encoding="utf-8")
    fields, end = _read_frontmatter(text)
    body = text[end:] if end else text
    fields["status"] = new_status
    order = ["phase", "task", "status", "depends_on"]
    keys = [k for k in order if k in fields] + [k for k in fields if k not in order]
    rebuilt = "---\n" + "\n".join(f"{k}: {fields[k]}" for k in keys) + "\n---\n"
    path.write_text(rebuilt + body, encoding="utf-8")


def _deps_satisfied(task: Task, by_path: dict[str, Task]) -> bool:
    for dep in task.depends_on:
        dep_task = by_path.get(dep)
        if dep_task is None or dep_task.status != "done":
            return False
    return True


# --------------------------------------------------------------------------- #
# Pipeline state
# --------------------------------------------------------------------------- #

def _phase_state() -> list[tuple[str, str, Path]]:
    """Return [(phase_key, state, path), ...] for the 5 pipeline phases.

    state is one of: ``missing``, ``empty``, ``ok``.
    """
    out = []
    for key, path in ARTIFACT_FILES.items():
        if not path.exists():
            out.append((key, "missing", path))
            continue
        body = path.read_text(encoding="utf-8")
        required = ARTIFACT_REQUIRED.get(key, [])
        if all(s in body for s in required):
            out.append((key, "ok", path))
        else:
            out.append((key, "empty", path))
    return out


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #

def cmd_init(_args: argparse.Namespace) -> int:
    """Create directories and self-copy the runner into the project."""
    PLANS_ROOT.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)

    src = Path(__file__).resolve()
    dst = Path(".phased-dev/run_phases.py").resolve()
    if src != dst:
        shutil.copy2(src, dst)
        print(f"copied runner: {dst}")
    else:
        print(f"runner already in place: {dst}")
    print(f"ready: plans/phases/, .phased-dev/artifacts/")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    # Pipeline phases
    print("Pipeline:")
    for key, state, path in _phase_state():
        marker = {"ok": "[x]", "empty": "[~]", "missing": "[ ]"}[state]
        print(f"  {marker} {key:<8} → {path.as_posix()}")

    # Tasks
    tasks = load_tasks()
    if not tasks:
        print(f"\nTasks: (none under {PLANS_ROOT.as_posix()}/)")
        return 0
    print("\nTasks:")
    counts = {s: 0 for s in VALID_STATUSES}
    current_phase = None
    for t in tasks:
        if t.phase_dir != current_phase:
            current_phase = t.phase_dir
            print(f"\n  [{current_phase}]")
        marker = {
            "done": "[x]",
            "in-progress": "[~]",
            "blocked": "[!]",
        }.get(t.status, "[ ]")
        print(f"    {marker} {t.path.as_posix()}  —  {t.title}")
        counts[t.status] = counts.get(t.status, 0) + 1
    total = len(tasks)
    print(
        f"\n  {counts['done']}/{total} done · "
        f"{counts['in-progress']} in-progress · "
        f"{counts['pending']} pending · "
        f"{counts['blocked']} blocked"
    )
    return 0


def cmd_next(_args: argparse.Namespace) -> int:
    tasks = load_tasks()
    by_path = {t.path.as_posix(): t for t in tasks}
    for t in tasks:
        if t.status != "pending":
            continue
        if not _deps_satisfied(t, by_path):
            continue
        print(t.path.as_posix())
        return 0
    print("(no runnable pending task)", file=sys.stderr)
    return 1


def cmd_run(_args: argparse.Namespace) -> int:
    tasks = load_tasks()
    by_path = {t.path.as_posix(): t for t in tasks}
    runnable = [
        t for t in tasks
        if t.status == "pending" and _deps_satisfied(t, by_path)
    ]
    blocked_pending = [
        t for t in tasks
        if t.status == "pending" and not _deps_satisfied(t, by_path)
    ]
    if not runnable and not blocked_pending:
        print("(no pending tasks)")
        return 0
    if runnable:
        print(f"{len(runnable)} runnable pending task(s):")
        for t in runnable:
            print(f"  {t.path.as_posix()}  —  {t.title}")
    if blocked_pending:
        print(f"\n{len(blocked_pending)} pending task(s) waiting on dependencies:")
        for t in blocked_pending:
            unmet = [
                d for d in t.depends_on
                if (by_path.get(d) is None or by_path[d].status != "done")
            ]
            print(f"  {t.path.as_posix()}  ← needs: {', '.join(unmet)}")
    print(
        "\nExecute each runnable task one at a time, then mark it with:\n"
        "  python .phased-dev/run_phases.py done <path>"
    )
    return 0


def cmd_artifact(args: argparse.Namespace) -> int:
    if args.phase not in ARTIFACT_FILES:
        print(
            f"unknown phase '{args.phase}'. valid: {sorted(ARTIFACT_FILES)}",
            file=sys.stderr,
        )
        return 1
    print(ARTIFACT_FILES[args.phase].as_posix())
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    if args.phase not in ARTIFACT_FILES:
        print(
            f"unknown phase '{args.phase}'. valid: {sorted(ARTIFACT_FILES)}",
            file=sys.stderr,
        )
        return 2
    path = ARTIFACT_FILES[args.phase]
    if not path.exists():
        print(f"missing: {path.as_posix()}", file=sys.stderr)
        return 1
    body = path.read_text(encoding="utf-8")
    missing = [s for s in ARTIFACT_REQUIRED[args.phase] if s not in body]
    if missing:
        print(
            f"incomplete: {path.as_posix()} missing sections: {missing}",
            file=sys.stderr,
        )
        return 1
    print(f"ok: {path.as_posix()}")
    return 0


def _mutate(args: argparse.Namespace, status: str) -> int:
    p = Path(args.path)
    if not p.exists():
        print(f"not found: {p}", file=sys.stderr)
        return 1
    _set_status(p, status)
    print(f"{p.as_posix()} → {status}")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    return _mutate(args, "in-progress")


def cmd_done(args: argparse.Namespace) -> int:
    return _mutate(args, "done")


def cmd_block(args: argparse.Namespace) -> int:
    return _mutate(args, "blocked")


def cmd_reset(args: argparse.Namespace) -> int:
    return _mutate(args, "pending")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="run_phases",
        description=(
            "Pipeline scaffolding + task tracker for the phased-dev skill. "
            "Run `init` first; subsequent invocations use `.phased-dev/run_phases.py`."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser(
        "init",
        help="Create .phased-dev/ and plans/phases/, copy runner into project",
    ).set_defaults(func=cmd_init)

    sub.add_parser(
        "status", help="Show pipeline phase artifacts and task status"
    ).set_defaults(func=cmd_status)

    sub.add_parser(
        "next", help="Print path of next runnable pending task"
    ).set_defaults(func=cmd_next)

    sub.add_parser(
        "run", help="List runnable pending tasks (and what's blocked)"
    ).set_defaults(func=cmd_run)

    art = sub.add_parser("artifact", help="Print the path of a phase artifact")
    art.add_argument("phase", choices=sorted(ARTIFACT_FILES))
    art.set_defaults(func=cmd_artifact)

    val = sub.add_parser(
        "validate", help="Check a phase artifact exists and has required sections"
    )
    val.add_argument("phase", choices=sorted(ARTIFACT_FILES))
    val.set_defaults(func=cmd_validate)

    for name, fn, helptext in [
        ("start", cmd_start, "Mark a task as in-progress"),
        ("done", cmd_done, "Mark a task as done"),
        ("block", cmd_block, "Mark a task as blocked"),
        ("reset", cmd_reset, "Reset a task to pending"),
    ]:
        s = sub.add_parser(name, help=helptext)
        s.add_argument("path")
        s.set_defaults(func=fn)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
