from pathlib import Path

import pytest
from cmp.apps.worker import _worker_token
from cmp.bootstrap.rotating_secret import RotatingTextFile
from cmp.bootstrap.settings import Settings


def test_rotating_text_file_reads_an_atomically_replaced_token_without_restart(
    tmp_path: Path,
) -> None:
    path = tmp_path / "worker.token"
    path.write_text("first.header.signature\n", encoding="ascii")
    provider = RotatingTextFile(path)

    assert provider() == "first.header.signature"
    replacement = tmp_path / "replacement.token"
    replacement.write_text("second.header.signature\n", encoding="ascii")
    replacement.replace(path)
    assert provider() == "second.header.signature"


def test_rotating_text_file_rejects_whitespace_oversize_and_symlink(
    tmp_path: Path,
) -> None:
    path = tmp_path / "worker.token"
    provider = RotatingTextFile(path, maximum_bytes=64)
    path.write_text("two tokens", encoding="ascii")
    with pytest.raises(RuntimeError, match="one non-empty token"):
        provider()
    path.write_bytes(b"x" * 65)
    with pytest.raises(RuntimeError, match="size"):
        provider()

    target = tmp_path / "target.token"
    target.write_text("valid.token.value", encoding="ascii")
    link = tmp_path / "link.token"
    try:
        link.symlink_to(target)
    except OSError:
        return
    with pytest.raises(RuntimeError, match="non-symlink"):
        RotatingTextFile(link)()


def test_worker_token_file_setting_is_separate_from_inline_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CMP_WORKER_ACCESS_TOKEN", "inline-secret")
    monkeypatch.setenv("CMP_WORKER_ACCESS_TOKEN_FILE", "C:/run/secrets/worker.token")

    settings = Settings.from_environment()

    assert settings.worker_access_token == "inline-secret"
    assert settings.worker_access_token_file == "C:/run/secrets/worker.token"


def test_production_worker_rejects_inline_token_and_reloads_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="rotate identity"):
        _worker_token(
            Settings(environment="production", worker_access_token="inline"),
            None,
        )

    path = tmp_path / "worker.token"
    path.write_text("first.worker.token", encoding="ascii")
    provider = _worker_token(
        Settings(
            environment="production",
            worker_access_token_file=str(path),
        ),
        None,
    )
    assert provider is not None
    assert provider() == "first.worker.token"
    path.write_text("rotated.worker.token", encoding="ascii")
    assert provider() == "rotated.worker.token"
