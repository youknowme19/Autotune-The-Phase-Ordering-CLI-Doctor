/*
 * Autotune Example Workload: Vector Addition
 * SIMD vector accumulation kernel.
 */

#include <stdio.h>
#include <stdlib.h>

#define SIZE 100000

float a[SIZE];
float b[SIZE];
float c[SIZE];

int main() {
    for (int i = 0; i < SIZE; i++) {
        a[i] = (float)i * 1.5f;
        b[i] = (float)i * 2.5f;
    }

    for (int i = 0; i < SIZE; i++) {
        c[i] = a[i] + b[i];
    }

    printf("Vector addition complete. c[100] = %.2f\n", c[100]);
    return 0;
}
