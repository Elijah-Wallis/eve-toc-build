from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_TARGET = Path(__file__).resolve().parent / ".agents" / "skills" / "hologram_gen.py"
_SPEC = spec_from_file_location(__name__, _TARGET)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Failed to load module at {_TARGET}")
_MOD = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
globals().update(_MOD.__dict__)

