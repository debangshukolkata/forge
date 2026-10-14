"""D-363: commands DebCraft runs let Node trust the Windows certificate store (company HTTPS inspection broke `npx shadcn`)."""

from __future__ import annotations

import pytest

from forge import doctor
from forge.net import node_supports_system_ca


@pytest.mark.parametrize(
    ("version", "supported"),
    [
        ("v24.0.0", True),
        ("v25.1.0", True),
        ("v23.8.0", True),
        ("v23.7.9", False),
        ("v22.15.0", True),
        ("v22.14.9", False),
        ("v20.11.1", False),
        ("", False),
        ("none", False),
    ],
)
def test_node_versions_that_can_read_the_system_store(version: str, supported: bool) -> None:
    assert node_supports_system_ca(version) is supported


def test_doctor_explains_an_old_node(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FORGE_SYSTEM_CERTS", raising=False)
    monkeypatch.setattr("forge.net.installed_node_version", lambda: "v20.11.1")
    result = doctor.check_node_certificates()
    assert result is not None and result.status == "warn" and "NODE_EXTRA_CA_CERTS" in result.detail
    monkeypatch.setattr("forge.net.installed_node_version", lambda: "v24.1.0")
    result = doctor.check_node_certificates()
    assert result is not None and result.status == "ok"
    monkeypatch.setattr("forge.net.installed_node_version", lambda: None)
    assert doctor.check_node_certificates() is None
