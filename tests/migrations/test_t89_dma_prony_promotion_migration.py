from __future__ import annotations

from pathlib import Path


def test_dma_prony_promotion_migration_extends_exact_method_allowlist() -> None:
    path = (
        Path(__file__).parents[2]
        / "backend"
        / "migrations"
        / "versions"
        / "20260918_083_T89_dma_prony_promotion.py"
    )
    text = path.read_text(encoding="utf-8")

    assert "polymer.prony_fit_compare" in text
    assert "polymer.dma_prony_fit_compare" in text
    assert "output_sha256" in text
    assert "mapping_profile_revision_id" in text
    assert "immutable DMA Prony evidence" in text


def test_dma_neutral_migration_allows_explicit_joint_selected_series() -> None:
    path = (
        Path(__file__).parents[2]
        / "backend"
        / "migrations"
        / "versions"
        / "20260919_084_T89_dma_neutral_selection.py"
    )
    text = path.read_text(encoding="utf-8")

    assert "modulus.storage.prony.selected+modulus.loss.prony.selected" in text
    assert "ck_modeling_neutral_material_selection_kind" in text
    assert "immutable DMA Neutral evidence" in text


def test_dma_neutral_source_migration_allows_explicit_frequency_mode() -> None:
    path = (
        Path(__file__).parents[2]
        / "backend"
        / "migrations"
        / "versions"
        / "20260920_085_T89_dma_neutral_source.py"
    )
    text = path.read_text(encoding="utf-8")

    assert "dma_frequency" in text
    assert "ck_modeling_neutral_material_source_test_mode" in text
    assert "immutable DMA source evidence" in text
