from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

_SCRIPTS = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))


def _load_script(name: str) -> ModuleType:
    spec = spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_viscoelastic_helper_targets_current_polymer_seed_name() -> None:
    module = _load_script("seed_viscoelastic_master_demo")

    assert module.TARGET_MATERIAL_NAME == "Synthetic Polymer Prony"


def test_ogden_helper_targets_current_elastomer_seed_name() -> None:
    module = _load_script("seed_ogden_calibration_demo")

    assert module.TARGET_MATERIAL_NAME == "Synthetic Elastomer Ogden-Prony"
