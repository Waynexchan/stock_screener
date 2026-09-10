"""Stable hashes and manifests for research runs."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_state(project_root: str | Path) -> tuple[str, bool | None]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return "unavailable", None


def build_manifest(
    *,
    project_root: str | Path,
    config_path: str | Path,
    experiment_id: str,
    data_period: dict[str, Any],
    universe_definition: str,
    execution_assumptions: dict[str, Any],
    feature_configuration: dict[str, Any],
    known_limitations: list[str],
    random_seed: int,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    timestamp = timestamp.astimezone(timezone.utc)
    commit, dirty = git_state(project_root)
    return {
        "run_id": timestamp.strftime("%Y%m%dT%H%M%S%fZ"),
        "timestamp": timestamp.isoformat(),
        "git_commit": commit,
        "git_dirty": dirty,
        "config_hash": sha256_file(config_path),
        "experiment_id": experiment_id,
        "data_period": data_period,
        "universe_definition": universe_definition,
        "execution_assumptions": execution_assumptions,
        "feature_configuration": feature_configuration,
        "random_seed": random_seed,
        "known_data_limitations": known_limitations,
    }


def stable_payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
