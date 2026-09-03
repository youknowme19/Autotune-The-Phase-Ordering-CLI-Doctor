/*
 * Dense Matrix-Vector Multiplication (GEMV) Kernel: y = alpha * A * x + beta * y
 * Standard BLAS Level-2 benchmark kernel for cache reuse and SIMD vectorization.
 */
#include <stdio.h>
#include <stdlib.h>

#define N 1024

static double A[N][N];
static double x[N];
static double y[N];

void init_data() {
    for (int i = 0; i < N; i++) {
        x[i] = (double)(i % 100) / 10.0;
        y[i] = 1.0;
        for (int j = 0; j < N; j++) {
            A[i][j] = (double)((i + j) % 100) / 100.0;
        }
    }
}

void gemv_kernel(int iterations, double alpha, double beta) {
    for (int iter = 0; iter < iterations; iter++) {
        for (int i = 0; i < N; i++) {
            double sum = 0.0;
            for (int j = 0; j < N; j++) {
                sum += A[i][j] * x[j];
            }
            y[i] = alpha * sum + beta * y[i];
        }
        x[iter % N] = y[iter % N] * 0.001;
    }
}

int main(int argc, char** argv) {
    int iters = 20;
    if (argc > 1) {
        iters = atoi(argv[1]);
    }
    init_data();
    gemv_kernel(iters, 1.5, 0.5);
    printf("GEMV Checksum: y[512]=%.6f\n", y[512]);
    return 0;
}
