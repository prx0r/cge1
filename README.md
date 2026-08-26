# cge1 — Objective Evolution Kernel

A declarative framework for evolving solutions against live evaluators
with noisy small-sample feedback. Domain-agnostic.

## The problem it solves

When optimizing against a hidden evaluator that resamples between rounds,
you hit the same wall every time: raw mean margins swing wildly at small n,
one lucky draw dominates selection, bad candidates burn expensive attempts,
and there's no principled way to decide "is this variant actually better?"

cge1 formalizes the answers:
- **Shrinkage fitness** — honest estimates under tiny noisy draws
- **Replace-if-wins gates** — never ship a regression on any metric
- **Constraint ledger** — burned identifiers, slot caps, attempt budgets as state
- **Local pre-validation gate** — kill bad genomes before spending real resources
- **Declarative spec** — adding a new objective means writing config, not code

## The five-phase cycle

```
INGEST → PROPOSE → VALIDATE → EMIT → SUBMIT
   ↑                                      │
   └────────── feedback loop ─────────────┘
```

## Quick start

```python
from cge1 import (ObjectiveSpec, GateSet, MetricThreshold,
                  ShrinkageScorer, ConstraintLedger, EvolutionLoop)

spec = ObjectiveSpec(
    name="my_model",
    primary_metric="accuracy",
    gates=GateSet(gates=(MetricThreshold("accuracy", 0.75),)),
    search_space={"learning_rate": [0.001, 0.01, 0.1]},
)

scorer = ShrinkageScorer(prior_mean=0.45)
ledger = ConstraintLedger("./state.json")

loop = EvolutionLoop(spec=spec, source=my_feedback_source,
                     scorer=scorer, ledger=ledger,
                     local_bench_fn=my_bench_fn,
                     emit_fn=my_emit_fn)

result = loop.run_cycle()
print(result.action)  # "proposed" | "null" | "capped" | ...
```

## Design principles

| Principle | Why |
|---|---|
| Replace-if-wins | Never ship a regression on any gate metric |
| Shrinkage fitness | Raw means mislead when hidden benches resample |
| Honest nulls | Failed candidates are recorded, never deleted |
| Local gates first | Kill bad genomes pre-submission |
| Declarative spec | Adding a new objective = config, not code |
| Domain-agnostic | No assumptions about what you're evolving |

## Modules

- `cge1.spec` — ObjectiveSpec, GateSet, MetricThreshold
- `cge1.feedback` — FeedbackAdapter protocol + adapters
- `cge1.scorer` — ShrinkageScorer for tiny noisy draws
- `cge1.constraints` — ConstraintLedger
- `cge1.pipeline` — ArtifactPipeline (composable build stages)
- `cge1.loop` — EvolutionLoop (autonomous cycle)
