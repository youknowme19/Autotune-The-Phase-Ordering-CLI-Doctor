"""
Experiment Design Engine and Centralized Measurement Policy.
Controls randomized trial sequences, A/B interleaving, and rigorous experiment planning.
"""

import random
from typing import List, Optional
from pydantic import BaseModel, Field


class MeasurementPolicy(BaseModel):
    """Centralized policy controlling benchmarking sample sizes, interleaving, and noise tolerances."""

    warmup_runs: int = 5
    screening_runs: int = 5
    confirmation_runs: int = 30
    interleave: bool = True
    randomize_order: bool = True
    cv_warning_threshold: float = 0.15
    min_effect_size: float = 0.5
    min_speedup_ratio: float = 1.02


class TrialSpec(BaseModel):
    trial_index: int
    candidate_type: str  # "baseline" or "candidate"


class ExperimentPlan(BaseModel):
    """Structured plan for randomized/interleaved A/B candidate benchmarking."""

    experiment_id: str
    seed: int
    policy: MeasurementPolicy = Field(default_factory=MeasurementPolicy)
    trial_sequence: List[TrialSpec] = Field(default_factory=list)

    @classmethod
    def create_interleaved_plan(
        self,
        experiment_id: str,
        seed: int = 42,
        policy: Optional[MeasurementPolicy] = None,
    ) -> "ExperimentPlan":
        pol = policy or MeasurementPolicy()
        rng = random.Random(seed)

        # Create balanced trial pairs (1 baseline + 1 candidate per pair)
        n_pairs = pol.confirmation_runs
        trials: List[TrialSpec] = []

        for i in range(n_pairs):
            pair = ["baseline", "candidate"]
            if pol.randomize_order:
                rng.shuffle(pair)
            trials.append(TrialSpec(trial_index=i * 2, candidate_type=pair[0]))
            trials.append(TrialSpec(trial_index=i * 2 + 1, candidate_type=pair[1]))

        return ExperimentPlan(
            experiment_id=experiment_id,
            seed=seed,
            policy=pol,
            trial_sequence=trials,
        )
