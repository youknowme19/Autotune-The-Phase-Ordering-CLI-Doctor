"""
Robust Benchmark Stability Analyzer.
Calculates median, mean, stddev, IQR, MAD (Median Absolute Deviation), and stability classification.
"""

from enum import Enum
import math
import statistics
from typing import List, Optional
from pydantic import BaseModel


class StabilityClassification(str, Enum):
    STABLE = "STABLE"
    NOISY = "NOISY"
    UNSTABLE = "UNSTABLE"
    INCONCLUSIVE = "INCONCLUSIVE"


class StabilityReport(BaseModel):
    sample_count: int
    median_time_ns: float
    mean_time_ns: float
    stddev_time_ns: float
    iqr_time_ns: float
    mad_time_ns: float  # Median Absolute Deviation
    cv: float  # Coefficient of variation
    ci95_lower_ns: float
    ci95_upper_ns: float
    min_time_ns: float
    max_time_ns: float
    outliers_count: int
    classification: StabilityClassification


class StabilityAnalyzer:
    """Analyzes raw timing samples using robust non-parametric and parametric statistics."""

    @staticmethod
    def analyze(samples_ns: List[int]) -> StabilityReport:
        if not samples_ns or len(samples_ns) < 3:
            return StabilityReport(
                sample_count=len(samples_ns),
                median_time_ns=float(samples_ns[0]) if samples_ns else 0.0,
                mean_time_ns=float(samples_ns[0]) if samples_ns else 0.0,
                stddev_time_ns=0.0,
                iqr_time_ns=0.0,
                mad_time_ns=0.0,
                cv=0.0,
                ci95_lower_ns=0.0,
                ci95_upper_ns=0.0,
                min_time_ns=float(samples_ns[0]) if samples_ns else 0.0,
                max_time_ns=float(samples_ns[0]) if samples_ns else 0.0,
                outliers_count=0,
                classification=StabilityClassification.INCONCLUSIVE,
            )

        sorted_s = sorted(samples_ns)
        n = len(sorted_s)

        med = float(statistics.median(sorted_s))
        mean = float(statistics.mean(sorted_s))
        stddev = float(statistics.stdev(sorted_s)) if n > 1 else 0.0

        # Calculate MAD: median(|x_i - median|)
        devs = [abs(x - med) for x in sorted_s]
        mad = float(statistics.median(devs))

        # Calculate IQR
        q25 = float(statistics.quantiles(sorted_s, n=4)[0])
        q75 = float(statistics.quantiles(sorted_s, n=4)[2])
        iqr = q75 - q25

        cv = stddev / mean if mean > 0 else 0.0

        ci_margin = 1.96 * (stddev / math.sqrt(n)) if (n > 1 and stddev > 0) else 0.0
        ci_lower = max(0.0, mean - ci_margin)
        ci_upper = mean + ci_margin

        # Outliers detection using Tukey's fences (1.5 * IQR)
        lower_fence = q25 - 1.5 * iqr
        upper_fence = q75 + 1.5 * iqr
        outliers = sum(1 for x in sorted_s if x < lower_fence or x > upper_fence)

        if cv <= 0.10:
            cls = StabilityClassification.STABLE
        elif cv <= 0.20:
            cls = StabilityClassification.NOISY
        else:
            cls = StabilityClassification.UNSTABLE

        return StabilityReport(
            sample_count=n,
            median_time_ns=med,
            mean_time_ns=mean,
            stddev_time_ns=stddev,
            iqr_time_ns=iqr,
            mad_time_ns=mad,
            cv=cv,
            ci95_lower_ns=ci_lower,
            ci95_upper_ns=ci_upper,
            min_time_ns=float(sorted_s[0]),
            max_time_ns=float(sorted_s[-1]),
            outliers_count=outliers,
            classification=cls,
        )
