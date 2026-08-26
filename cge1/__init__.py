"""cge1 — Objective evolution kernel.

A declarative framework for evolving solutions against live evaluators
with noisy small-sample feedback. Domain-agnostic: works for model weights,
scoring functions, rule programs, prompts, or anything with measurable quality.

Five phases per cycle:
    INGEST → PROPOSE → VALIDATE → EMIT → SUBMIT
"""
__version__ = "0.1.0"

from .spec import ObjectiveSpec, GateSet, MetricThreshold
from .feedback import FeedbackAdapter, Observation
from .scorer import ShrinkageScorer, FitnessResult
from .constraints import ConstraintLedger
from .pipeline import ArtifactPipeline, PipelineStage, BuildResult
from .loop import EvolutionLoop, LoopResult

__all__ = [
    "ObjectiveSpec", "GateSet", "MetricThreshold",
    "FeedbackAdapter", "Observation",
    "ShrinkageScorer", "FitnessResult",
    "ConstraintLedger",
    "ArtifactPipeline", "PipelineStage", "BuildResult",
    "EvolutionLoop", "LoopResult",
]
