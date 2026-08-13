"""Tests unitaires des options SSL/TLS du connecteur."""

from __future__ import annotations

from pathlib import Path

import pytest

from database import connector as connector_module
from database.connector import DatabaseConnector, DatabaseSSLConfig


class _FakeEngine:
    def dispose(self) -> None:
        pass


def test_postgresql_ssl_uses_ca_and_verify_full(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ca_file = tmp_path / "ca.pem"
    ca_file.write_text("-----BEGIN CERTIFICATE-----\nCA\n-----END CERTIFICATE-----\n")
    captured: dict = {}

    def fake_create_engine(url: str, **kwargs: object) -> _FakeEngine:
        captured["url"] = url
        captured.update(kwargs)
        return _FakeEngine()

    monkeypatch.setattr(connector_module, "create_engine", fake_create_engine)
    connector = DatabaseConnector(
        "postgresql+psycopg2://user:password@db.example.com:5432/app",
        ssl_config=DatabaseSSLConfig(enabled=True, ca_cert_path=str(ca_file)),
    )

    connector.connect()

    assert captured["connect_args"] == {
        "sslmode": "verify-full",
        "sslrootcert": str(ca_file),
    }


def test_mysql_ssl_uses_ca_and_hostname_verification(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ca_file = tmp_path / "ca.pem"
    ca_file.write_text("-----BEGIN CERTIFICATE-----\nCA\n-----END CERTIFICATE-----\n")
    captured: dict = {}

    monkeypatch.setattr(
        connector_module,
        "create_engine",
        lambda url, **kwargs: captured.update(kwargs) or _FakeEngine(),
    )
    connector = DatabaseConnector(
        "mysql+pymysql://user:password@db.example.com:3306/app",
        ssl_config=DatabaseSSLConfig(
            enabled=True,
            ca_cert_path=str(ca_file),
            verify_identity=True,
        ),
    )

    connector.connect()

    assert captured["connect_args"] == {
        "ssl": {"ca": str(ca_file), "check_hostname": True}
    }


def test_pem_content_is_written_to_private_temporary_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        connector_module,
        "create_engine",
        lambda url, **kwargs: captured.update(kwargs) or _FakeEngine(),
    )
    connector = DatabaseConnector(
        "postgresql://user:password@db.example.com:5432/app",
        ssl_config=DatabaseSSLConfig(
            enabled=True,
            ca_cert_content="\ufeff-----BEGIN CERTIFICATE-----\r\nCA\r\n-----END CERTIFICATE-----",
        ),
    )

    connector.connect()
    temporary_path = Path(captured["connect_args"]["sslrootcert"])

    assert temporary_path.is_file()
    assert temporary_path.stat().st_mode & 0o777 == 0o600
    assert temporary_path.read_bytes() == (
        b"-----BEGIN CERTIFICATE-----\nCA\n-----END CERTIFICATE-----\n"
    )

    connector.disconnect()

    assert not temporary_path.exists()


def test_ssl_requires_a_ca_certificate() -> None:
    connector = DatabaseConnector(
        "postgresql://user:password@db.example.com:5432/app",
        ssl_config=DatabaseSSLConfig(enabled=True),
    )

    with pytest.raises(ValueError, match="certificat CA est requis"):
        connector.connect()


def test_ssl_rejects_missing_ca_path(tmp_path: Path) -> None:
    connector = DatabaseConnector(
        "postgresql://user:password@db.example.com:5432/app",
        ssl_config=DatabaseSSLConfig(
            enabled=True,
            ca_cert_path=str(tmp_path / "missing.pem"),
        ),
    )

    with pytest.raises(ValueError, match="Certificat CA introuvable"):
        connector.connect()