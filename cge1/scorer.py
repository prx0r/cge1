"""ShrinkageScorer: honest fitness estimation under tiny noisy draws.

When hidden evaluations resample between rounds (n=4..15), raw mean margins
swing ±0.15. Shrinkage pulls small-n means toward a prior so one lucky draw
doesn't dominate selection.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class FitnessResult:
    score: float       # shrunk fitness value used for ranking
    n: int             # number of observations backing this estimate
    raw_mean: float    # unadjusted mean for comparison
    prior_used: float
    k_used: float


class ShrinkageScorer:
    def __init__(self, prior_mean: float = 0.45, prior_weight: float = 6.0):
        self.prior_mean = prior_mean
        self.k = prior_weight

    def evaluate(self, margins: Sequence[float]) -> FitnessResult:
        if not margins:
            return FitnessResult(score=self.prior_mean, n=0,
                                 raw_mean=self.prior_mean,
                                 prior_used=self.prior_mean, k_used=self.k)
        n = len(margins)
        raw = sum(margins) / n
        score = (n * raw + self.k * self.prior_mean) / (n + self.k)
        return FitnessResult(score=round(score, 6), n=n, raw_mean=round(raw, 6), prior_used=self.prior_mean, k_used=self.k)

    def best(self, results: list[tuple[str, FitnessResult]]) -> str | None:
        if not results:
            return None
        return max(results, key=lambda x: x[1].score)[0]
