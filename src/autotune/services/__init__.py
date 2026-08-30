"""
Autotune Application Service Layer.
Encapsulates core application logic and optimization orchestration away from CLI presentation interfaces.
"""

from autotune.services.doctor import DoctorService, DoctorResult, DoctorPreset, PRESETS
from autotune.services.reproduce import ReproduceService, ReproductionResult, ReproductionVerdict
from autotune.services.guard import GuardService, GuardResult, GuardExitCode
from autotune.services.inspect import InspectService, InspectionResult
from autotune.services.history import HistoryManager, HistoryEntry
from autotune.services.compare import CompareService, ComparisonResult, LiveComparisonResult
from autotune.services.optimize import OptimizeService, OptimizeResult
from autotune.services.validate import ValidateService, ValidationResult
from autotune.services.report import ReportService

__all__ = [
    "DoctorService",
    "DoctorResult",
    "DoctorPreset",
    "PRESETS",
    "ReproduceService",
    "ReproductionResult",
    "ReproductionVerdict",
    "GuardService",
    "GuardResult",
    "GuardExitCode",
    "InspectService",
    "InspectionResult",
    "HistoryManager",
    "HistoryEntry",
    "CompareService",
    "ComparisonResult",
    "LiveComparisonResult",
    "OptimizeService",
    "OptimizeResult",
    "ValidateService",
    "ValidationResult",
    "ReportService",
]
