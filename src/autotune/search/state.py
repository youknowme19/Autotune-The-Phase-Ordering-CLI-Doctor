"""
Search Engine State Machine and Stagnation Recovery Tracker.
Tracks explicit search phases: EXPLORING, EXPLOITING, REFINING, CONFIRMING, STOPPED, FAILED.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SearchState(str, Enum):
    EXPLORING = "EXPLORING"
    EXPLOITING = "EXPLOITING"
    REFINING = "REFINING"
    CONFIRMING = "CONFIRMING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class StateTransition(BaseModel):
    from_state: SearchState
    to_state: SearchState
    evaluation_index: int
    reason: str


class SearchStateMachine(BaseModel):
    """Tracks search phase state transitions and stagnation counts."""

    current_state: SearchState = SearchState.EXPLORING
    evaluations_count: int = 0
    evaluations_without_improvement: int = 0
    stagnation_threshold: int = 15
    transitions: List[StateTransition] = Field(default_factory=list)

    def transition_to(self, new_state: SearchState, reason: str) -> None:
        t = StateTransition(
            from_state=self.current_state,
            to_state=new_state,
            evaluation_index=self.evaluations_count,
            reason=reason,
        )
        self.transitions.append(t)
        self.current_state = new_state

    def record_evaluation(self, improved: bool) -> bool:
        """Record candidate evaluation; returns True if search is stagnating."""
        self.evaluations_count += 1
        if improved:
            self.evaluations_without_improvement = 0
            if self.current_state == SearchState.EXPLORING:
                self.transition_to(SearchState.EXPLOITING, "Discovered promising speedup candidate.")
            elif self.current_state == SearchState.EXPLOITING:
                self.transition_to(SearchState.REFINING, "Applying local search refinement.")
            return False
        else:
            self.evaluations_without_improvement += 1
            if self.evaluations_without_improvement >= self.stagnation_threshold:
                self.transition_to(SearchState.EXPLORING, f"Stagnated for {self.evaluations_without_improvement} evaluations; restarting exploration.")
                self.evaluations_without_improvement = 0
                return True
            return False
