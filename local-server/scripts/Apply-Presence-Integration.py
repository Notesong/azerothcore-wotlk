"""Apply reviewed staged files only if the original Presence files are unchanged."""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "presence-integration"
STAGE = INTEGRATION / "working"
DESTINATION = Path("C:/Files/Programs/Codex/Presence/working")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, help='Apply a later reviewed delta manifest only')
    args = parser.parse_args()
    entries = []
    for item in json.loads((args.manifest or INTEGRATION / "manifest.json").read_text(encoding="utf-8")):
        entries.append((Path(item["relative_path"]), item["source_sha256"], item["staged_sha256"]))
    if not args.manifest:
        for item in json.loads((INTEGRATION / "parent-manifest.json").read_text(encoding="utf-8")):
            relative = Path(item["path"])
            entries.append((relative, item["sha256"], digest(STAGE / relative)))
        for source in (ROOT / "harness/presence_acore").glob("*.py"):
            relative = Path("backend/tools/presence_acore") / source.name
            target = STAGE / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            entries.append((relative, None, digest(target)))
    # Validate every file before changing any source file.
    for relative, expected, staged in entries:
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("Manifest contains a path outside the selected project.")
        destination = DESTINATION / relative
        if digest(STAGE / relative) != staged:
            raise RuntimeError(f"Staged file changed after review: {relative}")
        actual = digest(destination) if destination.exists() else None
        if actual != expected:
            raise RuntimeError(f"Original changed since staging; merge required: {relative}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = INTEGRATION / "backups" / stamp
    applied = []
    for relative, expected, staged in entries:
        destination = DESTINATION / relative
        if expected is not None:
            original = backup / relative
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, original)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(STAGE / relative, destination)
        applied.append({"path": str(relative), "previous_sha256": expected, "sha256": staged})
    backup.mkdir(parents=True, exist_ok=True)
    (backup / "applied.json").write_text(json.dumps(applied, indent=2), encoding="utf-8")
    print(f"Applied {len(applied)} reviewed files. Backups: {backup}")


if __name__ == "__main__":
    main()
