#include <stdio.h>
#include <stdlib.h>

#define SIZE 200000

int main(void) {
    int scale = 1;
    if (scanf("%d", &scale) != 1) {
        scale = 1;
    }

    double *a = (double *)malloc(SIZE * sizeof(double));
    double *b = (double *)malloc(SIZE * sizeof(double));
    double *c = (double *)malloc(SIZE * sizeof(double));

    if (!a || !b || !c) return 1;

    for (int i = 0; i < SIZE; i++) {
        a[i] = i * 0.5 * scale;
        b[i] = i * 1.5 * scale;
    }

    // Vector reduction loop candidate
    for (int i = 0; i < SIZE; i++) {
        c[i] = a[i] * b[i] + (a[i] - b[i]);
    }

    double total = 0.0;
    for (int i = 0; i < SIZE; i++) {
        total += c[i];
    }

    printf("Vector sum total: %.2f\n", total);

    free(a);
    free(b);
    free(c);
    return 0;
}
