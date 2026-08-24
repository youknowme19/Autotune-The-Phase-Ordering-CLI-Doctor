/*
 * Autotune Example Workload: Loop Reduction
 * Arithmetic sum reduction kernel.
 */

#include <stdio.h>

#define N 500000

int main() {
    volatile long long sum = 0;
    for (int i = 0; i < N; i++) {
        sum += (i * 3) - (i / 2);
    }
    printf("Reduction complete. Sum = %lld\n", sum);
    return 0;
}
