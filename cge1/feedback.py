"""FeedbackAdapter protocol: external evaluator payloads → typed Observations.

Implement poll() for any source: REST API, benchmark runner, human review,
game scores, CI results, A/B test outcomes.
"""
from __future__ import annotations
import json
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Observation:
    subject_id: str              # unique identifier for this evaluation attempt
    genome_hash: str | None      # attribution to the emitting genome
    intent: str                  # which objective this belongs to
    metrics: dict                # {"accuracy": …, "margin": …, "score": …}
    accepted: bool               # did the evaluator promote/accept?
    source: str = "unknown"
    meta: dict = field(default_factory=dict)


class FeedbackAdapter(Protocol):
    """Any class that implements poll() returning Observations."""

    def poll(self) -> list[Observation]: ...


class RestFeedbackAdapter:
    """Polls a JSON REST endpoint for evaluation results.

    Expects response to be a list of objects with at minimum:
      {"id": str, "metrics": {...}, "accepted": bool}
    Optional fields: "genome_hash", "intent", "reason".
    Configure `field_map` if your API uses different key names.
    """

    def __init__(self, url: str, intents: list[str],
                 headers: dict | None = None,
                 field_map: dict | None = None):
        self.url = url
        self.tracked = set(intents)
        self.headers = headers or {"User-Agent": "cge1"}
        self.field_map = field_map or {}

    def poll(self) -> list[Observation]:
        req = urllib.request.Request(self.url, headers=self.headers)
        d = json.loads(urllib.request.urlopen(req, timeout=60).read())
        stack, seen, out = [d], set(), []
        while stack:
            x = stack.pop()
            if isinstance(x, dict) and x.get("id") is not None:
                iid = x.get("intent", "")
                if iid in self.tracked and x.get("status") in ("active", "rejected", "superseded"):
                    metrics_src = x.get("eval") or x.get("metrics") or {}
                    m = {self.field_map.get(k, k): self._num(v)
                         for k, v in metrics_src.items()
                         if isinstance(v, (int, float))}
                    out.append(Observation(
                        subject_id=str(x["id"]),
                        genome_hash=x.get("genome_hash"),
                        intent=iid,
                        metrics=m,
                        accepted=(x.get("status") == "active"),
                        source="rest",
                        meta={"reason": x.get("reason", "")}))
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)
        return out

    @staticmethod
    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0


class StaticBenchmarkAdapter:
    """Wraps local bench results as Observations (pre-deployment validation)."""

    def __init__(self, intent: str, bench_fn):
        self.intent = intent
        self.bench_fn = bench_fn
        self.counter = 0

    def observe(self, genome_hash: str, genome: dict) -> Observation:
        self.counter += 1
        metrics = self.bench_fn(genome)
        return Observation(
            subject_id=f"local_{self.counter}",
            genome_hash=genome_hash,
            intent=self.intent,
            metrics=metrics,
            accepted=True,
            source="local_bench")
