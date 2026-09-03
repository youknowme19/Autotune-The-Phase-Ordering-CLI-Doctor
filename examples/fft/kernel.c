/*
 * Cooley-Tukey Radix-2 Fast Fourier Transform (FFT) 1D Kernel
 * Bit-reversal permutation and complex trigonometric butterfly stages.
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

#define N 1024
#define PI 3.14159265358979323846

static double real[N];
static double imag[N];

void init_signal() {
    for (int i = 0; i < N; i++) {
        real[i] = sin(2.0 * PI * 5.0 * i / N) + 0.5 * cos(2.0 * PI * 20.0 * i / N);
        imag[i] = 0.0;
    }
}

void fft_kernel(int iterations) {
    for (int iter = 0; iter < iterations; iter++) {
        // Bit-reversal permutation
        int j = 0;
        for (int i = 0; i < N - 1; i++) {
            if (i < j) {
                double tr = real[i]; real[i] = real[j]; real[j] = tr;
                double ti = imag[i]; imag[i] = imag[j]; imag[j] = ti;
            }
            int k = N / 2;
            while (k <= j) {
                j -= k;
                k /= 2;
            }
            j += k;
        }

        // Butterfly stages
        for (int len = 2; len <= N; len <<= 1) {
            double ang = -2.0 * PI / len;
            double wlen_r = cos(ang);
            double wlen_i = sin(ang);
            for (int i = 0; i < N; i += len) {
                double w_r = 1.0;
                double w_i = 0.0;
                for (int j_step = 0; j_step < len / 2; j_step++) {
                    double u_r = real[i + j_step];
                    double u_i = imag[i + j_step];
                    double v_r = real[i + j_step + len / 2] * w_r - imag[i + j_step + len / 2] * w_i;
                    double v_i = real[i + j_step + len / 2] * w_i + imag[i + j_step + len / 2] * w_r;
                    real[i + j_step] = u_r + v_r;
                    imag[i + j_step] = u_i + v_i;
                    real[i + j_step + len / 2] = u_r - v_r;
                    imag[i + j_step + len / 2] = u_i - v_i;
                    double next_w_r = w_r * wlen_r - w_i * wlen_i;
                    double next_w_i = w_r * wlen_i + w_i * wlen_r;
                    w_r = next_w_r;
                    w_i = next_w_i;
                }
            }
        }
        real[0] += 0.0001;
    }
}

int main(int argc, char** argv) {
    int iters = 50;
    if (argc > 1) {
        iters = atoi(argv[1]);
    }
    init_signal();
    fft_kernel(iters);
    printf("FFT Energy Checksum: %.6f\n", real[5] * real[5] + imag[5] * imag[5]);
    return 0;
}
