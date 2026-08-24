/*
 * Autotune Example Workload: Matrix Multiplication
 * Dense floating-point matrix multiplication kernel.
 */

#include <stdio.h>
#include <stdlib.h>

#define N 128

double A[N][N];
double B[N][N];
double C[N][N];

void init_matrices() {
    for (int i = 0; i < N; i++) {
        for (int j = 0; j < N; j++) {
            A[i][j] = (double)(i + j);
            B[i][j] = (double)(i - j);
            C[i][j] = 0.0;
        }
    }
}

void multiply() {
    for (int i = 0; i < N; i++) {
        for (int j = 0; j < N; j++) {
            double sum = 0.0;
            for (int k = 0; k < N; k++) {
                sum += A[i][k] * B[k][j];
            }
            C[i][j] = sum;
        }
    }
}

int main() {
    init_matrices();
    multiply();
    printf("Matrix multiplication complete. C[0][0] = %.2f\n", C[0][0]);
    return 0;
}
