from __future__ import annotations

import os

from learning_problem_factory.env_utils import load_env_file


def test_load_env_file_without_overwriting_process_environment(tmp_path, monkeypatch) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "# ignored\nEXISTING=from-file\nNEW_VALUE='loaded value'\nINVALID-LINE=x\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EXISTING", "from-process")
    monkeypatch.delenv("NEW_VALUE", raising=False)

    assert load_env_file(path)
    assert os.environ["EXISTING"] == "from-process"
    assert os.environ["NEW_VALUE"] == "loaded value"
    assert "INVALID-LINE" not in os.environ


def test_missing_env_file_is_a_safe_noop(tmp_path) -> None:
    assert not load_env_file(tmp_path / "missing.env")
