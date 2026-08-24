/*
 * Autotune Example Workload: 2D Stencil
 * Memory-intensive 5-point 2D stencil computation.
 */

#include <stdio.h>

#define DIM 256

double grid[DIM][DIM];
double next_grid[DIM][DIM];

int main() {
    for (int i = 0; i < DIM; i++) {
        for (int j = 0; j < DIM; j++) {
            grid[i][j] = (double)(i * j);
        }
    }

    for (int i = 1; i < DIM - 1; i++) {
        for (int j = 1; j < DIM - 1; j++) {
            next_grid[i][j] = 0.25 * (grid[i-1][j] + grid[i+1][j] + grid[i][j-1] + grid[i][j+1]);
        }
    }

    printf("Stencil computation complete. next_grid[10][10] = %.2f\n", next_grid[10][10]);
    return 0;
}
