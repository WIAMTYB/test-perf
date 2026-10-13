"""Campaign configuration for the harness.

Resolution order, highest first: command-line overrides, PERF_* environment variables, the
project .env file (parsed here, never sourced: the DB password contains '$'), then the
committed profile src/test/resources/profiles/<env>.properties. Secrets never reach a log.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
ALLOWED_HOST_SUFFIXES = (".apps.ocpdev.attijariwafa.net", ".apps.ocppprd.attijariwafa.net")
CAMPAIGN_ID = re.compile(r"^[A-Z0-9-]{4,24}$")
MASK = re.compile(r"(PASSWORD|SECRET|CREDENTIALS|SIGNKEY|API_KEY|TOKEN)", re.IGNORECASE)


def read_properties(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


@dataclass
class Config:
    env: str
    profile: dict[str, str]
    secrets: dict[str, str]
    project_dir: Path = PROJECT_DIR

    # --- profile values ---------------------------------------------------------
    @property
    def base_url(self) -> str:
        return self.profile["selfcare.baseUrl"].rstrip("/")

    @property
    def oc_context(self) -> str | None:
        return self.secrets.get("PERF_OC_CONTEXT") or self.profile.get("oc.context") or None

    @property
    def ns_services(self) -> str:
        return self.profile["oc.namespace.services"]

    @property
    def ns_datas(self) -> str:
        return self.profile["oc.namespace.datas"]

    @property
    def selector_api(self) -> str:
        return self.profile["oc.selector.api"]

    @property
    def selector_worker(self) -> str:
        return self.profile["oc.selector.worker"]

    @property
    def db_dsn(self) -> str:
        return self.profile["db.dsn"]

    @property
    def sample_seconds(self) -> int:
        return int(self.profile.get("metrics.sampleSeconds", "15"))

    @property
    def source(self) -> str:
        return self.profile.get("orders.source", "PERF")

    @property
    def abort_5xx_percent(self) -> float:
        return float(self.profile.get("limits.abort5xxPercent", "5"))

    @property
    def abort_window_seconds(self) -> int:
        return int(self.profile.get("limits.abortWindowSeconds", "60"))

    # --- secrets ---------------------------------------------------------------------
    @property
    def api_key(self) -> str:
        return self._secret("PERF_API_KEY")

    @property
    def metrics_api_key(self) -> str:
        return self._secret("PERF_METRICS_API_KEY")

    @property
    def db_user(self) -> str:
        return self._secret("PERF_DB_USER")

    @property
    def db_password(self) -> str:
        return self._secret("PERF_DB_PASSWORD")

    def has_db(self) -> bool:
        return bool(self.secrets.get("PERF_DB_USER") and self.secrets.get("PERF_DB_PASSWORD"))

    def has_metrics_key(self) -> bool:
        return bool(self.secrets.get("PERF_METRICS_API_KEY"))

    def has_api_key(self) -> bool:
        return bool(self.secrets.get("PERF_API_KEY"))

    def _secret(self, name: str) -> str:
        value = self.secrets.get(name)
        if not value:
            raise SystemExit(f"{name} is not set (environment or {self.project_dir / '.env'})")
        return value

    @property
    def mvn(self) -> str:
        return self.secrets.get("PERF_MVN") or "mvn"

    # --- paths -----------------------------------------------------------------------
    @property
    def campaigns_dir(self) -> Path:
        return self.project_dir / "campaigns" / self.env

    def new_run_dir(self, scenario: str, stamp: datetime | None = None) -> Path:
        stamp = stamp or datetime.now()
        return self.campaigns_dir / f"{stamp:%Y%m%d-%H%M}-{scenario}"

    @property
    def sql_dir(self) -> Path:
        return self.project_dir / "harness" / "sql"

    def masked_profile(self) -> dict[str, str]:
        return {k: ("***" if MASK.search(k) else v) for k, v in self.profile.items()}


def load(env: str | None = None, overrides: dict[str, str] | None = None) -> Config:
    dot_env = read_properties(PROJECT_DIR / ".env")
    env = env or os.environ.get("PERF_ENV") or dot_env.get("PERF_ENV") or "recette"
    profile_file = PROJECT_DIR / "src" / "test" / "resources" / "profiles" / f"{env}.properties"
    if not profile_file.exists():
        raise SystemExit(f"Unknown environment '{env}': {profile_file} does not exist")
    profile = read_properties(profile_file)
    profile.update(overrides or {})

    secrets = {k: v for k, v in dot_env.items() if k.startswith("PERF_")}
    secrets.update({k: v for k, v in os.environ.items() if k.startswith("PERF_") and v})

    config = Config(env=env, profile=profile, secrets=secrets)
    verify(config)
    return config


def verify(config: Config) -> None:
    host = re.sub(r"^https?://", "", config.base_url).split("/")[0].split(":")[0]
    if not host.endswith(ALLOWED_HOST_SUFFIXES):
        raise SystemExit(f"Refusing to target {config.base_url}: not a recette or preprod route")
    if config.source != "PERF":
        raise SystemExit(f"Refusing orders.source={config.source}: campaigns must use PERF")


def check_campaign_id(campaign_id: str) -> str:
    if not CAMPAIGN_ID.match(campaign_id or ""):
        raise SystemExit(f"Campaign id '{campaign_id}' must match {CAMPAIGN_ID.pattern}")
    return campaign_id
