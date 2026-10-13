#!/usr/bin/env python3
"""Normalise notebooks so commits stay readable - without dropping outputs.

Outputs, figures and images are kept, because the notebooks are meant to be read
on GitHub with their results. What is removed is the bookkeeping that changes on
every run and carries no information: execution counts.

    python3 tools/clean_notebooks.py                 # clean every tracked notebook
    python3 tools/clean_notebooks.py nb.ipynb        # clean specific files
    python3 tools/clean_notebooks.py --check         # report, change nothing (exit 1 if dirty)
    python3 tools/clean_notebooks.py --install-hook  # run --check-and-clean before each commit

Standard library only.
"""

import argparse
import glob
import json
import os
import stat
import subprocess
import sys

HOOK = """#!/usr/bin/env bash
# Installed by tools/clean_notebooks.py --install-hook
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
mapfile -t staged < <(git diff --cached --name-only --diff-filter=ACM -- '*.ipynb')
[ ${#staged[@]} -eq 0 ] && exit 0
python3 "$root/tools/clean_notebooks.py" "${staged[@]}"
git add -- "${staged[@]}"
"""


def clean(path, check=False):
    with open(path, encoding="utf-8") as handle:
        original = handle.read()
    nb = json.loads(original)

    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        cell["execution_count"] = None
        for output in cell.get("outputs", []):
            if "execution_count" in output:
                output["execution_count"] = None

    # Jupyter's own on-disk format, so this introduces no whitespace churn.
    cleaned = json.dumps(nb, indent=1, ensure_ascii=False) + "\n"
    if cleaned == original:
        return False
    if not check:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(cleaned)
    return True


def tracked_notebooks():
    try:
        out = subprocess.run(
            ["git", "ls-files", "*.ipynb"], capture_output=True, text=True, check=True
        ).stdout
        return [p for p in out.splitlines() if p]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return sorted(glob.glob("*.ipynb"))


def install_hook():
    hook_dir = subprocess.run(
        ["git", "rev-parse", "--git-path", "hooks"], capture_output=True, text=True, check=True
    ).stdout.strip()
    os.makedirs(hook_dir, exist_ok=True)
    target = os.path.join(hook_dir, "pre-commit")
    if os.path.exists(target):
        sys.exit(f"{target} already exists - merge the snippet in by hand:\n\n{HOOK}")
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(HOOK)
    os.chmod(target, os.stat(target).st_mode | stat.S_IEXEC)
    print(f"installed {target}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="notebooks (default: every tracked .ipynb)")
    parser.add_argument("--check", action="store_true", help="report only, change nothing")
    parser.add_argument("--install-hook", action="store_true", help="install a pre-commit hook")
    args = parser.parse_args()

    if args.install_hook:
        install_hook()
        return

    paths = args.paths or tracked_notebooks()
    changed = [p for p in paths if clean(p, check=args.check)]

    for path in changed:
        print(("would clean " if args.check else "cleaned ") + path)
    print(f"{len(changed)} of {len(paths)} notebook(s) {'need cleaning' if args.check else 'cleaned'}")
    if args.check and changed:
        sys.exit(1)


if __name__ == "__main__":
    main()
