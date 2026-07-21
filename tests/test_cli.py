from __future__ import annotations

import re

import pytest

from netbox_scribe.cli import main


def test_help_does_not_require_netbox_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("NETBOX_URL", raising=False)
    monkeypatch.delenv("NETBOX_TOKEN", raising=False)

    exit_code = main(["--help"])

    assert exit_code == 0
    assert "Versioned, AI-ready infrastructure context" in capsys.readouterr().out


def test_version_does_not_require_netbox_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("NETBOX_URL", raising=False)
    monkeypatch.delenv("NETBOX_TOKEN", raising=False)

    exit_code = main(["--version"])

    assert exit_code == 0
    assert re.fullmatch(r"nbscribe \d+\.\d+\.\d+(?:\.dev\d+)?\n", capsys.readouterr().out)
