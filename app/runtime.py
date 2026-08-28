from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping


class RuntimeConfigurationError(ValueError):
    """Raised when runtime settings would create an unsafe or invalid server."""


def _parse_positive_int(raw: str, name: str, *, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeConfigurationError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise RuntimeConfigurationError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return value


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class RuntimeSettings:
    environment: str
    access_key: str
    allowed_hosts: tuple[str, ...]
    max_request_bytes: int
    sqlite_busy_timeout_ms: int
    seed_demo: bool

    @property
    def production(self) -> bool:
        return self.environment in {"prod", "production"}

    @property
    def interactive_docs_enabled(self) -> bool:
        return not self.production


def _validate_production_settings(
    access_key: str,
    allowed_hosts: tuple[str, ...],
) -> None:
    normalized_key = access_key.lower()
    placeholder = (
        not access_key
        or len(access_key) < 32
        or "change-this" in normalized_key
        or "replace-with" in normalized_key
    )
    if placeholder:
        raise RuntimeConfigurationError(
            "Production requires APP_ACCESS_KEY with at least 32 non-placeholder characters"
        )
    if not allowed_hosts or "*" in allowed_hosts:
        raise RuntimeConfigurationError(
            "Production requires an explicit PROJECT_OS_ALLOWED_HOSTS allowlist"
        )


def load_runtime_settings(
    environ: Mapping[str, str] | None = None,
) -> RuntimeSettings:
    """Load and validate environment-backed settings without side effects."""

    env = os.environ if environ is None else environ
    environment = env.get("PROJECT_OS_ENV", "development").strip().lower()
    if environment not in {"development", "test", "prod", "production"}:
        raise RuntimeConfigurationError(
            "PROJECT_OS_ENV must be development, test, prod, or production"
        )

    production = environment in {"prod", "production"}
    access_key = env.get("APP_ACCESS_KEY", "").strip()
    hosts = tuple(
        host.strip()
        for host in env.get(
            "PROJECT_OS_ALLOWED_HOSTS", "localhost,127.0.0.1"
        ).split(",")
        if host.strip()
    )
    max_request_bytes = _parse_positive_int(
        env.get("PROJECT_OS_MAX_REQUEST_BYTES", "2000000"),
        "PROJECT_OS_MAX_REQUEST_BYTES",
        minimum=65_536,
        maximum=50_000_000,
    )
    sqlite_busy_timeout_ms = _parse_positive_int(
        env.get("PROJECT_OS_SQLITE_BUSY_TIMEOUT_MS", "5000"),
        "PROJECT_OS_SQLITE_BUSY_TIMEOUT_MS",
        minimum=100,
        maximum=60_000,
    )
    seed_default = "0" if production else "1"
    seed_demo = _parse_bool(env.get("PROJECT_OS_SEED_DEMO", seed_default))

    if production:
        _validate_production_settings(access_key, hosts)

    return RuntimeSettings(
        environment=environment,
        access_key=access_key,
        allowed_hosts=hosts,
        max_request_bytes=max_request_bytes,
        sqlite_busy_timeout_ms=sqlite_busy_timeout_ms,
        seed_demo=seed_demo,
    )
