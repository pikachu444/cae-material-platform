import importlib

from cmp.modules import MODULE_NAMES


def test_all_bounded_module_namespaces_are_importable() -> None:
    imported = [importlib.import_module(f"cmp.modules.{name}") for name in MODULE_NAMES]

    assert len(imported) == len(MODULE_NAMES)

