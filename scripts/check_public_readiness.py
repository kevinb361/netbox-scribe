"""Mechanical checks for files that will be published from the Git tree."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = {
    ".github/workflows/ci.yml",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "docs/PUBLICATION.md",
}
FORBIDDEN_FILES = {".env", ".planning/.close-out-auditor.log"}
FORBIDDEN_PREFIXES = ("dist/", "snapshot/")
MARKDOWN_LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")


def main() -> int:
    tracked = _tracked_files()
    findings: list[str] = []

    for missing in sorted(REQUIRED - tracked):
        findings.append(f"required public artifact is not tracked: {missing}")
    for path in sorted(tracked):
        if path in FORBIDDEN_FILES or path.startswith(FORBIDDEN_PREFIXES):
            findings.append(f"sensitive/generated path is tracked: {path}")

    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    if "/home/" in design or ".agent-profile" in design:
        findings.append("DESIGN.md contains a local profile path")

    findings.extend(_broken_local_links(tracked))
    if findings:
        for finding in findings:
            print(f"public-readiness error: {finding}")
        return 1

    print(f"Public readiness checks passed ({len(tracked)} tracked files).")
    return 0


def _tracked_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return {path.decode() for path in result.stdout.split(b"\0") if path}


def _broken_local_links(tracked: set[str]) -> list[str]:
    findings: list[str] = []
    for relative in sorted(path for path in tracked if path.endswith(".md")):
        document = ROOT / relative
        for target in MARKDOWN_LINK.findall(document.read_text(encoding="utf-8")):
            if "://" in target or target.startswith(("#", "mailto:")) or "<" in target:
                continue
            path_part = target.split("#", 1)[0]
            candidate = (document.parent / path_part).resolve()
            try:
                published_path = candidate.relative_to(ROOT).as_posix().rstrip("/")
            except ValueError:
                published_path = ""
            is_tracked = published_path in tracked or any(
                path.startswith(f"{published_path}/") for path in tracked
            )
            if not candidate.exists() or not published_path or not is_tracked:
                findings.append(f"broken or untracked local link in {relative}: {target}")
    return findings


if __name__ == "__main__":
    raise SystemExit(main())
