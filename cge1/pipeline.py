"""ArtifactPipeline: composable genome→build→verify→deploy stages.

Each stage takes (genome, context) → context updates. Any exception or
context["_error"] short-circuits the pipeline.
"""
from __future__ import annotations
import hashlib
import os
from typing import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class BuildResult:
    ok: bool
    artifact_path: str | None = None
    error: str | None = None


class PipelineStage:
    def __init__(self, name: str, fn: Callable):
        self.name = name
        self.fn = fn

    def __call__(self, genome: dict, ctx: dict) -> dict:
        result = self.fn(genome, ctx)
        if isinstance(result, dict):
            ctx.update(result)
        return ctx


class ArtifactPipeline:
    def __init__(self, stages: list[PipelineStage]):
        self.stages = stages

    def run(self, genome: dict) -> BuildResult:
        ctx: dict = {"genome": genome}
        for stage in self.stages:
            try:
                stage(genome, ctx)
            except Exception as e:
                return BuildResult(ok=False, error=f"{stage.name}: {e}")
            if ctx.get("_error"):
                return BuildResult(ok=False, error=ctx["_error"])
        path = ctx.get("artifact_path")
        if not path or not os.path.exists(path):
            return BuildResult(ok=False, error="no artifact produced")
        sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
        return BuildResult(ok=True, artifact_path=path)
