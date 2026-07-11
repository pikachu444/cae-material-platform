from pathlib import Path

from cmp.tools.architecture import find_violations

PROJECT_ROOT = Path(__file__).parents[2]


def test_repository_has_no_architecture_violations() -> None:
    assert find_violations(PROJECT_ROOT / "backend/src") == []


def test_domain_framework_import_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "cmp/modules/catalog/domain/entity.py"
    source.parent.mkdir(parents=True)
    source.write_text("from fastapi import FastAPI\n", encoding="utf-8")

    violations = find_violations(tmp_path)

    assert [item.rule for item in violations] == ["ARCH-001"]


def test_cross_module_private_adapter_import_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "cmp/modules/catalog/application/service.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from cmp.modules.testing.adapters import repository\n", encoding="utf-8"
    )

    violations = find_violations(tmp_path)

    assert [item.rule for item in violations] == ["ARCH-002"]


def test_production_plugin_import_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "cmp/apps/api.py"
    source.parent.mkdir(parents=True)
    source.write_text("import plugins.production.secret_model\n", encoding="utf-8")

    violations = find_violations(tmp_path)

    assert [item.rule for item in violations] == ["ARCH-003"]

