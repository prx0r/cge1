"""ConstraintLedger: attempt budgets, burned identifiers, slot caps.

Formalizes hard-won constraints from adversarial systems where every attempt
has a cost and identifiers are consumed permanently on failure.
"""
from __future__ import annotations
import json
import os


class ConstraintLedger:
    def __init__(self, path: str, max_inflight_per_hash: int = 2):
        self.path = path
        self.cap = max_inflight_per_hash
        self.burned: set[tuple[str, str]] = set()
        self.inflight: dict[tuple[str, str], int] = {}
        self.attempts: int = 0
        self.nulls: int = 0
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        d = json.load(open(self.path))
        self.burned = set(tuple(x) for x in d.get("burned", []))
        self.inflight = {tuple(k.split("|")): v
                         for k, v in d.get("inflight", {}).items()}
        self.attempts = d.get("attempts", 0)
        self.nulls = d.get("nulls", 0)

    def _save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        json.dump({"burned": [list(x) for x in self.burned],
                   "inflight": {"|".join(k): v for k, v in self.inflight.items()},
                   "attempts": self.attempts, "nulls": self.nulls},
                  open(self.path, "w"), indent=1)

    def can_attempt(self, owner: str, artifact_hash: str) -> tuple[bool, str]:
        key = (owner, artifact_hash)
        if key in self.burned:
            return False, "hash burned (lifetime)"
        if self.inflight.get(key, 0) >= self.cap:
            return False, f"max inflight ({self.cap})"
        return True, ""

    def register_attempt(self, owner: str, h: str):
        key = (owner, h)
        self.inflight[key] = self.inflight.get(key, 0) + 1
        self.attempts += 1
        self._save()

    def burn(self, owner: str, h: str, reason: str = ""):
        key = (owner, h)
        self.inflight.pop(key, None)
        self.burned.add(key)
        self._save()

    def record_null(self):
        self.nulls += 1
        self._save()

    def stats(self) -> dict:
        return {"burned": len(self.burned),
                "inflight": sum(self.inflight.values()),
                "attempts": self.attempts, "nulls": self.nulls}
