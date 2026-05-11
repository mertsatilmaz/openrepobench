from __future__ import annotations

from collections import Counter
from pathlib import Path
from statistics import NormalDist
from typing import Iterable
import glob
import json
import time

import yaml

from .runner import run_task, safe_name
from .schemas import RunResult, load_task


def load_metadata(path: str | Path | None) -> dict:
    if path is None:
        return {}
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    if source.suffix.lower() == ".json":
        return json.loads(text)
    loaded = yaml.safe_load(text) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Metadata file must contain an object: {source}")
    return loaded


def expand_task_paths(patterns: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    seen = set()
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if not matches:
            candidate = Path(pattern)
            if candidate.exists():
                matches = [str(candidate)]
        for match in matches:
            path = Path(match)
            if path.is_file() and path not in seen:
                paths.append(path)
                seen.add(path)
    return sorted(paths)


def wilson_interval(successes: int, total: int, confidence: float = 0.95) -> dict[str, float]:
    if total == 0:
        return {"low": 0.0, "high": 0.0, "confidence": confidence}
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    phat = successes / total
    denominator = 1 + z**2 / total
    center = (phat + z**2 / (2 * total)) / denominator
    spread = z * ((phat * (1 - phat) + z**2 / (4 * total)) / total) ** 0.5 / denominator
    return {
        "low": max(0.0, center - spread),
        "high": min(1.0, center + spread),
        "confidence": confidence,
    }


def summarize_results(results: list[RunResult], suite_dir: Path) -> dict:
    resolved = sum(1 for result in results if result.resolved)
    total = len(results)
    failure_counts = Counter(result.failure_kind or "resolved" for result in results)
    harness_errors = failure_counts.get("harness_error", 0)
    interval = wilson_interval(resolved, total)
    return {
        "schema_version": "0.1",
        "suite_dir": str(suite_dir),
        "total_tasks": total,
        "resolved_tasks": resolved,
        "pass_rate": resolved / total if total else 0.0,
        "confidence_interval": interval,
        "failure_counts": dict(sorted(failure_counts.items())),
        "harness_errors": harness_errors,
        "results": [
            {
                "task_id": result.task_id,
                "agent": result.agent,
                "resolved": result.resolved,
                "failure_kind": result.failure_kind,
                "result_path": result.result_path,
                "bundle_path": result.bundle_path,
            }
            for result in results
        ],
    }


def run_suite(task_paths: list[Path], agent, output_root: Path, run_metadata: dict | None = None) -> dict:
    started = int(time.time())
    suite_dir = output_root / f"suite__{safe_name(agent.name)}__{started}"
    suite_dir.mkdir(parents=True, exist_ok=True)
    results: list[RunResult] = []

    for task_path in task_paths:
        task = load_task(task_path)
        metadata = dict(run_metadata or {})
        metadata["task_source"] = str(task_path)
        results.append(run_task(task, agent, suite_dir, metadata))

    summary = summarize_results(results, suite_dir)
    summary_path = suite_dir / "suite_summary.json"
    summary["summary_path"] = str(summary_path)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
