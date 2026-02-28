from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import fcntl  # type: ignore
except Exception:  # pragma: no cover
    fcntl = None


LEDGER_FIELDS = {
    "ledger_seq",
    "ledger_prev_hash",
    "ledger_hash",
    "ledger_algo",
    "ledger_version",
}


def compute_ledger_hash(*, seq: int, prev_hash: str, event: Dict[str, Any], algo: str = "sha256") -> str:
    payload = {
        "ledger_seq": int(seq),
        "ledger_prev_hash": str(prev_hash),
        "event": event,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.new(algo, encoded).hexdigest()


def verify_log_chain(
    path: Path,
    *,
    max_errors: int = 20,
    allow_legacy_prefix: bool = True,
    allow_legacy_interleaving: bool = False,
    require_signed: bool = False,
) -> Dict[str, Any]:
    path = Path(path).expanduser()
    if not path.exists():
        return {"ok": False, "reason": "missing_file", "record_count": 0, "errors": [{"reason": "missing_file"}]}

    errors: List[Dict[str, Any]] = []
    record_count = 0
    legacy_count = 0
    legacy_interleaved_count = 0
    signed_count = 0
    prev_hash: Optional[str] = None
    prev_seq: Optional[int] = None

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                errors.append({"line": line_no, "reason": "invalid_json"})
                if len(errors) >= max_errors:
                    break
                continue
            if not isinstance(row, dict):
                errors.append({"line": line_no, "reason": "non_object"})
                if len(errors) >= max_errors:
                    break
                continue

            record_count += 1
            has_any_ledger = any(field in row for field in LEDGER_FIELDS)
            has_all_ledger = all(field in row for field in LEDGER_FIELDS)

            if not has_any_ledger:
                if signed_count > 0:
                    if allow_legacy_interleaving:
                        legacy_count += 1
                        legacy_interleaved_count += 1
                        continue
                    errors.append({"line": line_no, "reason": "legacy_after_signed"})
                elif allow_legacy_prefix:
                    legacy_count += 1
                    continue
                else:
                    errors.append({"line": line_no, "reason": "legacy_not_allowed"})
                if len(errors) >= max_errors:
                    break
                continue

            if not has_all_ledger:
                errors.append({"line": line_no, "reason": "partial_ledger_fields"})
                if len(errors) >= max_errors:
                    break
                continue

            signed_count += 1
            seq = row.get("ledger_seq")
            row_prev_hash = row.get("ledger_prev_hash")
            row_hash = row.get("ledger_hash")
            algo = str(row.get("ledger_algo") or "sha256").lower()

            if not isinstance(seq, int) or seq <= 0:
                errors.append({"line": line_no, "reason": "invalid_seq", "value": seq})
                if len(errors) >= max_errors:
                    break
                continue
            if not isinstance(row_prev_hash, str) or not row_prev_hash:
                errors.append({"line": line_no, "reason": "invalid_prev_hash"})
                if len(errors) >= max_errors:
                    break
                continue
            if not isinstance(row_hash, str) or not row_hash:
                errors.append({"line": line_no, "reason": "invalid_hash"})
                if len(errors) >= max_errors:
                    break
                continue

            if prev_seq is not None and seq != prev_seq + 1:
                errors.append({"line": line_no, "reason": "seq_gap", "expected": prev_seq + 1, "actual": seq})
            if prev_hash is not None and row_prev_hash != prev_hash:
                errors.append({"line": line_no, "reason": "prev_hash_mismatch"})

            unsigned_event = {k: v for k, v in row.items() if k not in LEDGER_FIELDS}
            expected_hash = compute_ledger_hash(seq=seq, prev_hash=row_prev_hash, event=unsigned_event, algo=algo)
            if expected_hash != row_hash:
                errors.append({"line": line_no, "reason": "hash_mismatch"})

            prev_seq = seq
            prev_hash = row_hash
            if len(errors) >= max_errors:
                break

    if require_signed and signed_count == 0:
        errors.append({"reason": "no_signed_records"})

    report = {
        "ok": len(errors) == 0 and (signed_count > 0 or (legacy_count > 0 and not require_signed)),
        "record_count": record_count,
        "legacy_record_count": legacy_count,
        "legacy_interleaved_count": legacy_interleaved_count,
        "signed_record_count": signed_count,
        "errors": errors,
    }
    if prev_hash:
        report["head_hash"] = prev_hash
    if prev_seq is not None:
        report["last_seq"] = prev_seq
    return report


class ImmutableLogWriter:
    def __init__(self, path: str | Path, *, enabled: bool = True, algo: str = "sha256", fsync_every: int = 1) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.enabled = enabled
        self.algo = algo
        self.fsync_every = max(1, int(fsync_every))
        self._writes_since_sync = 0

    def append(self, event: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return dict(event)
        flags = os.O_APPEND | os.O_CREAT | os.O_RDWR
        fd = os.open(str(self.path), flags, 0o600)
        try:
            if fcntl is not None:
                fcntl.flock(fd, fcntl.LOCK_EX)

            seq, prev_hash = self._tail_state_from_fd(fd)
            next_seq = seq + 1
            event_copy = dict(event)
            digest = compute_ledger_hash(seq=next_seq, prev_hash=prev_hash, event=event_copy, algo=self.algo)
            signed = {
                **event_copy,
                "ledger_seq": next_seq,
                "ledger_prev_hash": prev_hash,
                "ledger_hash": digest,
                "ledger_algo": self.algo,
                "ledger_version": 1,
            }
            line = json.dumps(signed, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
            os.lseek(fd, 0, os.SEEK_END)
            os.write(fd, line.encode("utf-8"))
            self._writes_since_sync += 1
            if self._writes_since_sync >= self.fsync_every:
                os.fsync(fd)
                self._writes_since_sync = 0
            return signed
        finally:
            if fcntl is not None:
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _tail_state_from_fd(self, fd: int, *, max_bytes: int = 256 * 1024) -> tuple[int, str]:
        size = os.lseek(fd, 0, os.SEEK_END)
        if size <= 0:
            return 0, "GENESIS"
        read_size = min(max_bytes, size)
        os.lseek(fd, size - read_size, os.SEEK_SET)
        data = os.read(fd, read_size)
        text = data.decode("utf-8", errors="ignore")
        for line in reversed([ln for ln in text.splitlines() if ln.strip()]):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            seq = row.get("ledger_seq")
            digest = row.get("ledger_hash")
            if isinstance(seq, int) and seq > 0 and isinstance(digest, str) and digest:
                return seq, digest
        return 0, "GENESIS"
