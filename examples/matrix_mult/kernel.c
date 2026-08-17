#include <stdio.h>
#include <stdlib.h>

#define N 256

void matmul(double A[N][N], double B[N][N], double C[N][N]) {
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

int main(void) {
    int scale = 1;
    if (scanf("%d", &scale) != 1) {
        scale = 1;
    }

    static double A[N][N];
    static double B[N][N];
    static double C[N][N];

    for (int i = 0; i < N; i++) {
        for (int j = 0; j < N; j++) {
            A[i][j] = (i + j) * 0.1 * scale;
            B[i][j] = (i - j) * 0.2 * scale;
            C[i][j] = 0.0;
        }
    }

    matmul(A, B, C);

    printf("Matrix mult check C[128][128]: %.4f\n", C[128][128]);
    return 0;
}
