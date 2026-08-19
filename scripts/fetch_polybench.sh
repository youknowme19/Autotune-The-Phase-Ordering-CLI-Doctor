#!/usr/bin/env bash
set -e

POLYBENCH_DIR="polybench"

echo "=== Setting up PolyBench/C kernels in ${POLYBENCH_DIR}/ ==="
mkdir -p "${POLYBENCH_DIR}"

# 1. 2mm (Two Matrix Multiplications: D = A.B.C)
cat << 'EOF' > "${POLYBENCH_DIR}/2mm.c"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>

#define NI 128
#define NJ 128
#define NK 128
#define NL 128

static double A[NI][NK];
static double B[NK][NJ];
static double C[NJ][NL];
static double D[NI][NL];
static double tmp[NI][NJ];

static inline uint64_t get_monotonic_time_ns(void) {
#if defined(__APPLE__)
    return clock_gettime_nsec_np(CLOCK_MONOTONIC_RAW);
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
#endif
}

void kernel_2mm(void) {
    for (int i = 0; i < NI; i++) {
        for (int j = 0; j < NJ; j++) {
            tmp[i][j] = 0.0;
            for (int k = 0; k < NK; ++k)
                tmp[i][j] += A[i][k] * B[k][j];
        }
    }
    for (int i = 0; i < NI; i++) {
        for (int j = 0; j < NL; j++) {
            D[i][j] = 0.0;
            for (int k = 0; k < NJ; ++k)
                D[i][j] += tmp[i][k] * C[k][j];
        }
    }
}

int main(void) {
    int iterations = 10;
    if (scanf("%d", &iterations) != 1) iterations = 10;

    for (int i = 0; i < NI; i++)
        for (int j = 0; j < NK; j++) A[i][j] = (double)((i*j+1) % NI) / NI;
    for (int i = 0; i < NK; i++)
        for (int j = 0; j < NJ; j++) B[i][j] = (double)((i*(j+1)+2) % NJ) / NJ;
    for (int i = 0; i < NJ; i++)
        for (int j = 0; j < NL; j++) C[i][j] = (double)((i*(j+3)+4) % NL) / NL;

    uint64_t start = get_monotonic_time_ns();
    for (int it = 0; it < iterations; it++) {
        kernel_2mm();
        __asm__ __volatile__("" ::: "memory");
    }
    uint64_t elapsed = get_monotonic_time_ns() - start;

    printf("2mm Check D[64][64]: %.4f\n", D[64][64]);
    printf("__AUTOTUNE_TIME_NS__:%llu\n", (unsigned long long)elapsed);
    return 0;
}
EOF

# 2. cholesky (Cholesky Decomposition)
cat << 'EOF' > "${POLYBENCH_DIR}/cholesky.c"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>
#include <time.h>

#define N 128

static double A[N][N];

static inline uint64_t get_monotonic_time_ns(void) {
#if defined(__APPLE__)
    return clock_gettime_nsec_np(CLOCK_MONOTONIC_RAW);
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
#endif
}

void kernel_cholesky(void) {
    for (int i = 0; i < N; i++) {
        for (int j = 0; j < i; j++) {
            for (int k = 0; k < j; k++) {
                A[i][j] -= A[i][k] * A[j][k];
            }
            A[i][j] /= A[j][j];
        }
        for (int k = 0; k < i; k++) {
            A[i][i] -= A[i][k] * A[i][k];
        }
        A[i][i] = sqrt(fabs(A[i][i]));
    }
}

int main(void) {
    int iterations = 10;
    if (scanf("%d", &iterations) != 1) iterations = 10;

    for (int i = 0; i < N; i++) {
        for (int j = 0; j <= i; j++)
            A[i][j] = (double)(-j % N) / N + 1.0;
        for (int j = i+1; j < N; j++)
            A[i][j] = 0.0;
        A[i][i] += 10.0;
    }

    uint64_t start = get_monotonic_time_ns();
    for (int it = 0; it < iterations; it++) {
        kernel_cholesky();
        __asm__ __volatile__("" ::: "memory");
    }
    uint64_t elapsed = get_monotonic_time_ns() - start;

    printf("Cholesky Check A[64][64]: %.4f\n", A[64][64]);
    printf("__AUTOTUNE_TIME_NS__:%llu\n", (unsigned long long)elapsed);
    return 0;
}
EOF

# 3. atax (Matrix Transpose and Vector Multiplication: y = A^T . (A . x))
cat << 'EOF' > "${POLYBENCH_DIR}/atax.c"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>

#define NX 256
#define NY 256

static double A[NX][NY];
static double x[NY];
static double y[NY];
static double tmp[NX];

static inline uint64_t get_monotonic_time_ns(void) {
#if defined(__APPLE__)
    return clock_gettime_nsec_np(CLOCK_MONOTONIC_RAW);
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
#endif
}

void kernel_atax(void) {
    for (int i = 0; i < NY; i++) y[i] = 0.0;
    for (int i = 0; i < NX; i++) {
        tmp[i] = 0.0;
        for (int j = 0; j < NY; j++)
            tmp[i] += A[i][j] * x[j];
        for (int j = 0; j < NY; j++)
            y[j] += A[i][j] * tmp[i];
    }
}

int main(void) {
    int iterations = 20;
    if (scanf("%d", &iterations) != 1) iterations = 20;

    for (int i = 0; i < NY; i++) x[i] = 1.0 + (i / (double)NY);
    for (int i = 0; i < NX; i++)
        for (int j = 0; j < NY; j++)
            A[i][j] = (double)((i+j) % NY) / (5.0 * NX);

    uint64_t start = get_monotonic_time_ns();
    for (int it = 0; it < iterations; it++) {
        kernel_atax();
        __asm__ __volatile__("" ::: "memory");
    }
    uint64_t elapsed = get_monotonic_time_ns() - start;

    printf("Atax Check y[128]: %.4f\n", y[128]);
    printf("__AUTOTUNE_TIME_NS__:%llu\n", (unsigned long long)elapsed);
    return 0;
}
EOF

# 4. gemm (Matrix Multiply: C = alpha*A*B + beta*C)
cat << 'EOF' > "${POLYBENCH_DIR}/gemm.c"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>

#define NI 128
#define NJ 128
#define NK 128

static double A[NI][NK];
static double B[NK][NJ];
static double C[NI][NJ];
static double alpha = 1.5;
static double beta = 1.2;

static inline uint64_t get_monotonic_time_ns(void) {
#if defined(__APPLE__)
    return clock_gettime_nsec_np(CLOCK_MONOTONIC_RAW);
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
#endif
}

void kernel_gemm(void) {
    for (int i = 0; i < NI; i++) {
        for (int j = 0; j < NJ; j++) {
            C[i][j] *= beta;
        }
        for (int k = 0; k < NK; k++) {
            for (int j = 0; j < NJ; j++) {
                C[i][j] += alpha * A[i][k] * B[k][j];
            }
        }
    }
}

int main(void) {
    int iterations = 20;
    if (scanf("%d", &iterations) != 1) iterations = 20;

    for (int i = 0; i < NI; i++) {
        for (int j = 0; j < NK; j++) A[i][j] = (double)((i*j+1) % NI) / NI;
        for (int j = 0; j < NJ; j++) C[i][j] = (double)((i*j+2) % NJ) / NJ;
    }
    for (int i = 0; i < NK; i++)
        for (int j = 0; j < NJ; j++) B[i][j] = (double)((i*j+3) % NK) / NK;

    uint64_t start = get_monotonic_time_ns();
    for (int it = 0; it < iterations; it++) {
        kernel_gemm();
        __asm__ __volatile__("" ::: "memory");
    }
    uint64_t elapsed = get_monotonic_time_ns() - start;

    printf("GEMM Check C[64][64]: %.4f\n", C[64][64]);
    printf("__AUTOTUNE_TIME_NS__:%llu\n", (unsigned long long)elapsed);
    return 0;
}
EOF

# 5. bicg (BiCGStab Subkernel: s = A.p, q = A^T.r)
cat << 'EOF' > "${POLYBENCH_DIR}/bicg.c"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>

#define NX 256
#define NY 256

static double A[NX][NY];
static double p[NY];
static double r[NX];
static double s[NY];
static double q[NX];

static inline uint64_t get_monotonic_time_ns(void) {
#if defined(__APPLE__)
    return clock_gettime_nsec_np(CLOCK_MONOTONIC_RAW);
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
#endif
}

void kernel_bicg(void) {
    for (int i = 0; i < NY; i++) s[i] = 0.0;
    for (int i = 0; i < NX; i++) {
        q[i] = 0.0;
        for (int j = 0; j < NY; j++) {
            s[j] += A[i][j] * r[i];
            q[i] += A[i][j] * p[j];
        }
    }
}

int main(void) {
    int iterations = 20;
    if (scanf("%d", &iterations) != 1) iterations = 20;

    for (int i = 0; i < NY; i++) p[i] = (double)(i % NY) / NY;
    for (int i = 0; i < NX; i++) {
        r[i] = (double)(i % NX) / NX;
        for (int j = 0; j < NY; j++)
            A[i][j] = (double)((i*(j+1)) % NX) / NX;
    }

    uint64_t start = get_monotonic_time_ns();
    for (int it = 0; it < iterations; it++) {
        kernel_bicg();
        __asm__ __volatile__("" ::: "memory");
    }
    uint64_t elapsed = get_monotonic_time_ns() - start;

    printf("BiCG Check s[128]: %.4f, q[128]: %.4f\n", s[128], q[128]);
    printf("__AUTOTUNE_TIME_NS__:%llu\n", (unsigned long long)elapsed);
    return 0;
}
EOF

# Input files for workloads
echo "10" > "${POLYBENCH_DIR}/2mm_input.txt"
echo "10" > "${POLYBENCH_DIR}/cholesky_input.txt"
echo "20" > "${POLYBENCH_DIR}/atax_input.txt"
echo "20" > "${POLYBENCH_DIR}/gemm_input.txt"
echo "20" > "${POLYBENCH_DIR}/bicg_input.txt"

echo "=== PolyBench/C kernels created in ${POLYBENCH_DIR}/ ==="
