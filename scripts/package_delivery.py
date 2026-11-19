"""Create the private hand-in ZIP from source files and the course manuals.

Run from any directory: python3 scripts/package_delivery.py
Only the person preparing the submission needs Python and Git.
"""

import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist-delivery" / "arol-fleet-management.zip"
SOURCE_DIRS = {"agents", "backend", "frontend", "mock-backoffice", "shared", "tests", "scripts", "langfuse-local"}
ROOT_FILES = {
    "README.md", "SETUP.md", ".dockerignore", ".gitignore", ".env.example",
    "compose.delivery.yml", "compose.delivery.gpu.yml", "docker-compose.yml",
    "avvia.sh", "avvia.bat", "avvia-gpu.sh", "avvia-gpu.bat",
}
SERIALS = {"15610", "17203", "17478", "17579", "A2055", "A2064", "A2132", "A4344"}


def main():
    manuals = [ROOT / "data/manuals" / f"{serial}_manual_EN.pdf" for serial in sorted(SERIALS)]
    missing = [path.name for path in manuals if not path.is_file()]
    if missing:
        raise SystemExit("Missing course manuals: " + ", ".join(missing))

    # Include current working files, including new source not yet committed.
    # Git's exclusions omit databases, environments, caches and node_modules.
    listed = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT,
    ).decode().split("\0")
    files = set(manuals)
    for name in listed:
        if not name:
            continue
        relative = Path(name)
        if relative.parts[0] not in SOURCE_DIRS and name not in ROOT_FILES:
            continue
        if any(part.startswith(".env") and part != ".env.example" for part in relative.parts):
            continue
        path = ROOT / relative
        if path.is_file() and not path.is_symlink():
            files.add(path)
    OUTPUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, Path("arol-fleet-management") / path.relative_to(ROOT))
    print(f"Created {OUTPUT} ({OUTPUT.stat().st_size / 1024**2:.1f} MiB, {len(files)} files)")
    print("Contains the proprietary course manuals: distribute only with the course submission.")


if __name__ == "__main__":
    main()
