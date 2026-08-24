"""
Multi-Armed Bandit (UCB1) for Adaptive Pass Family and Search Direction Allocation.
"""

import math
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from autotune.llvm.taxonomy import PassFamily


class BanditArmStats(BaseModel):
    arm_name: str
    pulls: int = 0
    total_reward: float = 0.0
    mean_reward: float = 0.0
    ucb1_score: float = float("inf")


class UCB1PassFamilyBandit:
    """Lightweight UCB1 Multi-Armed Bandit allocating search budget to promising pass families."""

    def __init__(self, exploration_constant: float = 0.5):
        self.c = exploration_constant
        self.arms: Dict[str, BanditArmStats] = {
            f.value: BanditArmStats(arm_name=f.value) for f in PassFamily
        }
        self.total_pulls: int = 0

    def select_arm(self) -> str:
        """Select arm with highest UCB1 score."""
        self.total_pulls += 1
        
        # If any arm has 0 pulls, select it for exploration first
        for name, arm in self.arms.items():
            if arm.pulls == 0:
                return name

        # Compute UCB1 score for all arms
        best_arm = None
        best_score = float("-inf")

        for name, arm in self.arms.items():
            score = arm.mean_reward + self.c * math.sqrt(math.log(self.total_pulls) / arm.pulls)
            arm.ucb1_score = round(score, 4)
            if score > best_score:
                best_score = score
                best_arm = name

        return best_arm or PassFamily.SSA_SCALAR.value

    def update(self, arm_name: str, speedup: float) -> None:
        """Update arm statistics with observed candidate speedup reward."""
        if arm_name not in self.arms:
            return

        arm = self.arms[arm_name]
        arm.pulls += 1
        reward = max(0.0, speedup - 1.0)  # Reward is speedup gain above baseline 1.0x
        arm.total_reward += reward
        arm.mean_reward = arm.total_reward / arm.pulls
