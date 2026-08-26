"""EvolutionLoop: orchestrates the five-phase cycle autonomously.

    INGEST (poll feedback) → PROPOSE (evolve genome) →
    VALIDATE (local gates + constraints) → EMIT (pipeline) → SUBMIT

Subclass and override `propose` or `local_validate` for custom behavior,
or just configure it via ObjectiveSpec and callback functions.
"""
from __future__ import annotations
import hashlib
import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .spec import ObjectiveSpec, GateSet, MetricThreshold
from .feedback import FeedbackAdapter, Observation
from .scorer import ShrinkageScorer, FitnessResult
from .constraints import ConstraintLedger


@dataclass
class LoopResult:
    action: str  # "proposed" | "null" | "capped" | "gate_fail" | "constraint_blocked" | "emit_fail"
    intent: str
    genome_hash: str | None = None
    fitness: float | None = None
    detail: dict = field(default_factory=dict)


class EvolutionLoop:
    def __init__(
        self,
        spec: ObjectiveSpec,
        source: FeedbackAdapter,
        scorer: Optional[ShrinkageScorer] = None,
        ledger: Optional[ConstraintLedger] = None,
        state_path: str = "cge1-state.json",
        local_bench_fn: Callable | None = None,
        emit_fn: Callable | None = None,
        seed: int = 42,
    ):
        self.spec = spec
        self.source = source
        self.scorer = scorer or ShrinkageScorer(spec.prior_mean, spec.prior_weight)
        self.ledger = ledger or ConstraintLedger("cge1-constraints.json")
        self.state_path = state_path
        self.bench_fn = local_bench_fn
        self.emit_fn = emit_fn
        self.rng = random.Random(seed)
        self.state: dict = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.state_path):
            return json.load(open(self.state_path))
        return {"population": [], "used": [], "auto_attempts": 0,
                "nulls": 0, "processed": []}

    def _save(self):
        os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
        json.dump(self.state, open(self.state_path, "w"), indent=1, sort_keys=True)

    # ── Phase 1: INGEST ──────────────────────────────────────────────────

    def poll_and_ingest(self) -> int:
        """Poll assessor for new observations, attach to known genomes."""
        observations = self.source.poll()
        count = 0
        for obs in observations:
            if obs.subject_id in self.state["processed"]:
                continue
            self.state["processed"].append(obs.subject_id)

            gh = obs.genome_hash or (
                self.state["used"][-1] if self.state["used"] else None)
            entry = next(
                (p for p in self.state["population"] if p["hash"] == gh), None)
            if entry is None:
                entry = {"hash": gh or "unknown", "genome": {}, "obs": []}
                self.state["population"].append(entry)

            margin = obs.metrics.get(self.spec.primary_metric, 0.0)
            entry.setdefault("obs", []).append({
                "margin": margin,
                "metrics": {k: v for k, v in obs.metrics.items()},
                "accepted": obs.accepted,
                "source": obs.source,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ")})
            fit = self.scorer.evaluate([o["margin"] for o in entry["obs"]])
            entry["fitness"] = fit.score
            count += 1

        if count:
            self._save()
        return count

    # ── Phase 2: PROPOSE ─────────────────────────────────────────────────

    def propose(self) -> tuple[dict, str] | tuple[None, str]:
        space = self.spec.search_space
        population = sorted(
            self.state["population"],
            key=lambda p: p.get("fitness", 0),
            reverse=True)
        elites = [p["genome"] for p in population[:4] if p.get("genome")]

        candidates = []
        if elites:
            # elitist mutation around top performers
            base = self.rng.choice(elites)
            cand = dict(base)
            for k in space:
                if self.rng.random() < 0.3:
                    cand[k] = self.rng.choice(space[k])
            candidates.append(cand)
            for _ in range(2):
                c2 = dict(candidates[-1])
                for k in space:
                    if self.rng.random() < 0.15:
                        c2[k] = self.rng.choice(space[k])
                candidates.append(c2)
        else:
            for _ in range(3):
                candidates.append({k: self.rng.choice(v)
                                   for k, v in space.items()})

        used = set(self.state["used"])
        for cand in candidates:
            h = hashlib.sha256(json.dumps(cand, sort_keys=True).encode()).hexdigest()[:16]
            if h not in used:
                return cand, h
        return None, ""

    # ── Phase 3: VALIDATE ────────────────────────────────────────────────

    def local_validate(self, genome: dict) -> tuple[bool, dict]:
        if self.bench_fn is None:
            return True, {}
        try:
            metrics = self.bench_fn(genome)
            if not self.spec.gates:
                return True, metrics
            ok = True
            failures = []
            for g in self.spec.gates.gates:
                v = metrics.get(g.name)
                if v is not None and v < g.floor:
                    ok = False
                    failures.append(f"{g.name}={v:.4f} < {g.floor}")
            return ok, metrics | {"gate_failures": failures}
        except Exception as e:
            return False, {"error": str(e)[:120]}

    # ── Phase 4: EMIT ────────────────────────────────────────────────────

    def emit_and_submit(self, genome: dict, gh: str) -> str | None:
        if self.emit_fn is None:
            return None
        return self.emit_fn(intent=self.spec.name, genome=genome, gh=gh)

    # ── MAIN CYCLE ───────────────────────────────────────────────────────

    def run_cycle(self) -> LoopResult:
        ingested = self.poll_and_ingest()
        st = self.state

        if st["auto_attempts"] >= self.spec.max_auto_attempts:
            return LoopResult(action="capped", intent=self.spec.name)

        genome, gh = self.propose()
        if genome is None:
            st["nulls"] += 1
            self._save()
            return LoopResult(action="null", intent=self.spec.name)

        can, reason = self.ledger.can_attempt("default", gh)
        if not can:
            st["used"].append(gh)
            self._save()
            return LoopResult(action="constraint_blocked",
                              intent=self.spec.name, genome_hash=gh,
                              detail={"reason": reason})

        ok, validation = self.local_validate(genome)
        if not ok:
            st["used"].append(gh)
            st["nulls"] += 1
            self._save()
            return LoopResult(action="local_gate_fail",
                              intent=self.spec.name, genome_hash=gh,
                              detail=validation)

        err = self.emit_and_submit(genome, gh)
        if err:
            st["used"].append(gh)
            self._save()
            return LoopResult(action="emit_fail", intent=self.spec.name,
                              genome_hash=gh, detail={"error": err})

        st["used"].append(gh)
        st["auto_attempts"] += 1
        self.ledger.register_attempt("default", gh)
        self._save()
        return LoopResult(action="proposed", intent=self.spec.name,
                          genome_hash=gh)

    def status(self) -> dict:
        st = self.state
        pop_fits = []
        for p in st.get("population", []):
            margins = [o["margin"] for o in p.get("obs", [])]
            fit = self.scorer.evaluate(margins) if margins else \
                  FitnessResult(score=self.spec.prior_mean, n=0,
                                raw_mean=self.prior_mean)
            pop_fits.append({"hash": p.get("hash"), "fitness": fit.score,
                             "n_obs": len(p.get("obs", []))})
        return {
            "intent": self.spec.name,
            "attempts": st.get("auto_attempts", 0),
            "nulls": st.get("nulls", 0),
            "population_size": len(st.get("population", [])),
            "top_fitness": max((f["fitness"] for f in pop_fits), default=0),
            "constraints": self.ledger.stats(),
        }
