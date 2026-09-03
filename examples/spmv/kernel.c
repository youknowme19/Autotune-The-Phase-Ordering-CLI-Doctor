/*
 * Sparse Matrix-Vector Multiplication (SpMV) in Compressed Sparse Row (CSR) format.
 * Irregular memory access, pointer indirection, and sparse loop computation.
 */
#include <stdio.h>
#include <stdlib.h>

#define ROWS 512
#define NNZ_PER_ROW 16
#define NNZ (ROWS * NNZ_PER_ROW)

static double values[NNZ];
static int col_indices[NNZ];
static int row_ptrs[ROWS + 1];
static double x_vec[ROWS];
static double y_vec[ROWS];

void init_sparse_matrix() {
    int idx = 0;
    for (int i = 0; i < ROWS; i++) {
        row_ptrs[i] = idx;
        x_vec[i] = (double)(i % 50) / 10.0;
        y_vec[i] = 0.0;
        for (int j = 0; j < NNZ_PER_ROW; j++) {
            col_indices[idx] = (i + j * 17) % ROWS;
            values[idx] = 1.0 + (double)((i + j) % 10);
            idx++;
        }
    }
    row_ptrs[ROWS] = idx;
}

void spmv_csr_kernel(int iterations) {
    for (int iter = 0; iter < iterations; iter++) {
        for (int r = 0; r < ROWS; r++) {
            double sum = 0.0;
            int start = row_ptrs[r];
            int end = row_ptrs[r + 1];
            for (int k = start; k < end; k++) {
                sum += values[k] * x_vec[col_indices[k]];
            }
            y_vec[r] = sum;
        }
        x_vec[iter % ROWS] = y_vec[iter % ROWS] * 0.0001;
    }
}

int main(int argc, char** argv) {
    int iters = 100;
    if (argc > 1) {
        iters = atoi(argv[1]);
    }
    init_sparse_matrix();
    spmv_csr_kernel(iters);
    printf("SpMV CSR Checksum: y[256]=%.6f\n", y_vec[256]);
    return 0;
}
