#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>

#define N 512

static double A[N][N];
static double B[N][N];

void transpose_kernel(int iterations) {
    for (int it = 0; it < iterations; it++) {
        for (int i = 0; i < N; i++) {
            for (int j = 0; j < N; j++) {
                B[j][i] = A[i][j] + (double)it * 0.0001;
            }
        }
    }
}

int main(void) {
    int iterations = 50;
    if (scanf("%d", &iterations) != 1) {
        iterations = 50;
    }

    for (int i = 0; i < N; i++) {
        for (int j = 0; j < N; j++) {
            A[i][j] = (double)(i * N + j) * 0.01;
            B[i][j] = 0.0;
        }
    }

    transpose_kernel(iterations);

    printf("Matrix Transpose Check B[256][256]: %.4f\n", B[256][256]);
    return 0;
}
