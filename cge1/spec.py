"""ObjectiveSpec: declarative definition of what "better" means."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MetricThreshold:
    """A metric that must meet a threshold (fail-closed gate)."""
    name: str
    floor: float
    direction: str = "max"  # "max" = must be >= floor; "min" = must be <= floor


@dataclass(frozen=True)
class GateSet:
    """Hard gates that must ALL pass before a candidate is eligible."""
    gates: tuple[MetricThreshold, ...]
    # Replace-if-wins: candidate must not regress on ANY gate metric vs incumbent.
    replace_if_wins: bool = True

    def check(self, metrics: dict[str, float]) -> tuple[bool, list[str]]:
        failures = []
        for g in self.gates:
            v = metrics.get(g.name)
            if v is None:
                failures.append(f"{g.name}: missing")
            elif g.direction == "max" and v < g.floor:
                failures.append(f"{g.name}: {v:.4f} < {g.floor}")
            elif g.direction == "min" and v > g.floor:
                failures.append(f"{g.name}: {v:.4f} > {g.floor}")
        return len(failures) == 0, failures

    def beats(self, challenger: dict[str, float], incumbent: dict[str, float]) -> bool:
        """True if challenger meets or beats incumbent on every gate metric."""
        for g in self.gates:
            cv, iv = challenger.get(g.name), incumbent.get(g.name)
            if cv is None or iv is None:
                continue
            if g.direction == "max" and cv < iv:
                return False
            if g.direction == "min" and cv > iv:
                return False
        return True


@dataclass(frozen=True)
class ObjectiveSpec:
    """Complete declarative definition of an evolution objective.

    This is configuration, not code. Adding a new optimization target means
    writing one of these dicts, not modifying the loop.
    """
    name: str
    primary_metric: str
    secondary_metrics: tuple[str, ...] = ()
    gates: GateSet | None = None
    search_space: dict[str, list] = field(default_factory=dict)
    prior_mean: float = 0.45
    prior_weight: float = 6.0
    max_auto_attempts: int = 6
    family: str = "generic"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "primary_metric": self.primary_metric,
            "secondary_metrics": list(self.secondary_metrics),
            "gate_floors": {g.name: g.floor for g in (self.gates.gates if self.gates else [])},
            "family": self.family,
        }
