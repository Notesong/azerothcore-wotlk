"""Page immutable, private HTTP request captures without altering their JSON."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

SCHEMA = "native-full-request/v1"
DIRECTORY = "runtime-game-player-full-requests"
REVISION = re.compile(r"[0-9a-f]{32}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _path(directory: Path, name: str) -> Path:
    path = directory / name
    if directory.is_symlink() or path.is_symlink() or path.resolve().parent != directory.resolve():
        raise ValueError("unsafe_capture_path")
    return path


def _json(path: Path, limit: int = 65536) -> dict[str, Any]:
    with path.open("rb") as stream:
        raw = stream.read(limit+1)
    if len(raw) > limit:
        raise ValueError("invalid_metadata")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("invalid_metadata")
    return obj


def read_full_context(data_dir: Path, *, lane: str = "body", revision: str | None = None,
                      sha256: str | None = None, offset: int = 0,
                      limit_bytes: int = 65536) -> dict[str, Any]:
    """Use revision+hash to pin subsequent pages; offsets are UTF-8 byte offsets."""
    base = {"schema": "wow-full-context/v1", "character": "Vesper", "lane": lane,
            "inspection_only": True, "available": False,
            "authentication_headers_captured": False}
    if (lane not in {"body", "social"} or type(offset) is not int or offset < 0
            or type(limit_bytes) is not int or not 1 <= limit_bytes <= 262144
            or bool(revision) != bool(sha256)
            or revision is not None and (not isinstance(revision, str) or not REVISION.fullmatch(revision))
            or sha256 is not None and (not isinstance(sha256, str) or not SHA256.fullmatch(sha256))
            or offset and not revision):
        return {**base, "error": {"code": "invalid_arguments"}}
    directory = Path(data_dir) / DIRECTORY
    pinned = revision is not None
    try:
        if revision is None:
            pointer = _json(_path(directory, "latest-"+lane+".json"))
            if (pointer.get("schema") != SCHEMA or pointer.get("character") != "Vesper"
                    or pointer.get("lane") != lane or not pointer.get("available")
                    or not isinstance(pointer.get("revision"), str)
                    or not REVISION.fullmatch(pointer["revision"])):
                raise ValueError("full_request_unavailable")
            revision, sha256 = pointer["revision"], pointer.get("body_sha256")
        meta = _json(_path(directory, revision+".meta.json"))
        if (meta.get("schema") != SCHEMA or meta.get("revision") != revision
                or meta.get("character") != "Vesper" or meta.get("lane") != lane
                or meta.get("available") is not True or meta.get("body_sha256") != sha256
                or not isinstance(sha256, str) or not SHA256.fullmatch(sha256)
                or type(meta.get("body_bytes")) is not int or meta["body_bytes"] < 0
                or meta.get("authentication_headers_captured") is not False
                or meta.get("encoding") != "utf-8"):
            raise ValueError("capture_metadata_mismatch")
        # A failed new capture must not silently fall back to an older successful one.
        if not pinned:
            preview_path = Path(data_dir) / ("runtime-game-player-context-"+lane+".json")
            try:
                preview = _json(preview_path, 262144)
            except FileNotFoundError:
                preview = {}
            except (OSError, ValueError):
                raise ValueError("latest_capture_freshness_unverified")
            preview_time = preview.get("prepared_at", "")
            if (preview.get("character") == "Vesper" and preview.get("lane") == lane
                    and preview.get("capture_id") and meta.get("capture_id")
                    and preview["capture_id"] != meta["capture_id"]
                    and isinstance(preview_time, str) and preview_time > str(meta.get("prepared_at", ""))):
                raise ValueError("latest_full_capture_stale")
        body_path = _path(directory, revision+".body.json")
        digest = hashlib.sha256()
        with body_path.open("rb") as stream:
            size = 0
            for chunk in iter(lambda: stream.read(1048576), b""):
                size += len(chunk)
                digest.update(chunk)
            if size != meta["body_bytes"] or digest.hexdigest() != sha256:
                raise ValueError("capture_body_mismatch")
            if offset > size:
                raise ValueError("invalid_offset")
            stream.seek(offset)
            raw = stream.read(limit_bytes)
            # Offset must be a codepoint boundary. A page ends at one too.
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                if exc.reason != "unexpected end of data" or exc.start == 0:
                    raise ValueError("invalid_utf8_offset") from exc
                raw = raw[:exc.start]
                text = raw.decode("utf-8")
            if not raw and offset < size:
                raise ValueError("page_limit_too_small")
        next_offset = offset + len(raw)
        return {**base, "available": True, "revision": revision, "sha256": sha256,
                "offset": offset, "next_offset": next_offset, "total_bytes": size,
                "complete": next_offset == size, "encoding": "utf-8", "text": text,
                "metadata": meta, "is_actual_recorded_request": True,
                "context_note": "Exact recorded request attempt; not hidden reasoning or proof of execution. Outcome metadata may update; body bytes are immutable."}
    except FileNotFoundError:
        code = "revision_unavailable" if pinned else "no_full_request_recorded"
    except ValueError as exc:
        code = str(exc) if str(exc) in {"unsafe_capture_path", "invalid_metadata", "full_request_unavailable",
            "capture_metadata_mismatch", "latest_full_capture_stale", "latest_capture_freshness_unverified", "capture_body_mismatch", "invalid_offset",
            "invalid_utf8_offset", "page_limit_too_small"} else "invalid_capture"
    except (OSError, TypeError, RecursionError):
        code = "capture_unavailable"
    return {**base, "error": {"code": code}, "context_note": "No reconstructed or older request is substituted."}
