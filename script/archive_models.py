"""Archive explicitly selected model directories with SHA256 verification and path links."""

import argparse, hashlib, json, os, shutil
from pathlib import Path

# Functions ===============================================
def manifest(root: Path) -> dict:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Refusing nested symlink: {path}")
        if path.is_file():
            with path.open("rb") as stream:
                result[path.relative_to(root).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def archive(source: Path, archive_root: Path, log: Path) -> None:
    if source.is_symlink():
        print(f"Already linked: {source}", flush=True)
        return
    source = source.resolve(strict=True)
    target = archive_root.resolve() / source.name
    if source == target or source in target.parents or not source.is_dir():
        raise ValueError("Invalid archive path")
    initial = manifest(source)
    print(f"Hashed {source.name}: {len(initial)} files", flush=True)
    if not target.exists():
        total = sum(p.stat().st_size for p in source.rglob("*") if p.is_file())
        if shutil.disk_usage(archive_root).free < total + 20 * 1024**3:
            raise RuntimeError("Insufficient destination space")
        shutil.copytree(source, target, copy_function=shutil.copyfile)
    if manifest(target) != initial:
        raise RuntimeError(f"Archive mismatch: {target}; source preserved")
    if manifest(source) != initial:
        raise RuntimeError("Source changed during verification; source preserved")
    record = {"source": str(source), "destination": str(target), "sha256": initial, "status": "verified"}
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as stream:
        stream.write(json.dumps(record) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    backup = source.with_name(source.name + ".archive-verified")
    if backup.exists():
        raise FileExistsError(backup)
    source.rename(backup)
    try:
        source.symlink_to(target, target_is_directory=True)
    except OSError:
        backup.rename(source)
        raise
    shutil.rmtree(backup)
    print(f"Archived and linked: {source.name}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("source", type=Path, nargs="+")
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    for source in args.source:
        archive(source, args.destination, args.log)

# Run =====================================================
if __name__ == "__main__":
    main()
