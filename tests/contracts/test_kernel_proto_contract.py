from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTO = ROOT / "services" / "ontology-kernel" / "proto" / "kernel.proto"


def test_kernel_proto_has_required_batch_apis() -> None:
    assert PROTO.exists(), f"missing proto: {PROTO}"
    text = PROTO.read_text(encoding="utf-8")
    assert "rpc BatchResolvePredicates" in text
    assert "rpc BatchLookupEdges" in text
    assert "rpc BatchTriplePatterns" in text
    assert "rpc ExecutePlan" in text
    assert "message SubjectPredicatePair" in text
