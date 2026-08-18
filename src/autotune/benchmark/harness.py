"""
In-process benchmark harness wrapping C/C++ kernels with tight loop execution, compiler clobbers, and high-precision monotonic timing.
"""

import re
from typing import Optional


HARNESS_WRAPPER_TEMPLATE = """#include <stdio.h>
#include <stdint.h>
#include <time.h>

static inline uint64_t autotune_get_time_ns(void) {
#if defined(__APPLE__)
    return clock_gettime_nsec_np(CLOCK_MONOTONIC_RAW);
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
#endif
}

{kernel_source}

void autotune_run_harness(int iterations) {
    uint64_t start = autotune_get_time_ns();
    for (int i = 0; i < iterations; ++i) {
        // Clobber memory to prevent compiler dead-code elimination across iterations
        __asm__ __volatile__("" ::: "memory");
    }
    uint64_t elapsed = autotune_get_time_ns() - start;
    printf("__AUTOTUNE_TIME_NS__:%llu\\n", (unsigned long long)elapsed);
}
"""


class InProcessHarness:
    """Manages in-process timing harness parsing and kernel wrapping."""

    TIME_MARKER_REGEX = re.compile(r"__AUTOTUNE_TIME_NS__:(\d+)")

    @classmethod
    def parse_time_ns(cls, stdout: str) -> Optional[float]:
        """Extract high-precision in-process kernel execution time in nanoseconds from stdout."""
        match = cls.TIME_MARKER_REGEX.search(stdout)
        if match:
            return float(match.group(1))
        return None

    @classmethod
    def wrap_kernel_source(cls, kernel_code: str) -> str:
        """Inject in-process benchmark harness wrapper into C source code."""
        return HARNESS_WRAPPER_TEMPLATE.format(kernel_source=kernel_code)
