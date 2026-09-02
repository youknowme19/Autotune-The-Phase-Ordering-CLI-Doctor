/*
 * 2D Image Convolution / Gaussian Blur Kernel
 * High memory indexing, loop unrolling, and SIMD vectorization potential.
 */
#include <stdio.h>
#include <stdlib.h>

#define WIDTH 256
#define HEIGHT 256

static float image[HEIGHT][WIDTH];
static float output[HEIGHT][WIDTH];

static const float kernel[3][3] = {
    {0.0625f, 0.1250f, 0.0625f},
    {0.1250f, 0.2500f, 0.1250f},
    {0.0625f, 0.1250f, 0.0625f}
};

void init_image() {
    for (int y = 0; y < HEIGHT; y++) {
        for (int x = 0; x < WIDTH; x++) {
            image[y][x] = (float)((x * y) % 255) / 255.0f;
        }
    }
}

void conv2d_kernel(int iterations) {
    for (int iter = 0; iter < iterations; iter++) {
        for (int y = 1; y < HEIGHT - 1; y++) {
            for (int x = 1; x < WIDTH - 1; x++) {
                float sum = 0.0f;
                for (int ky = -1; ky <= 1; ky++) {
                    for (int kx = -1; kx <= 1; kx++) {
                        sum += image[y + ky][x + kx] * kernel[ky + 1][kx + 1];
                    }
                }
                output[y][x] = sum;
            }
        }
        image[HEIGHT / 2][WIDTH / 2] = output[HEIGHT / 2][WIDTH / 2];
    }
}

int main(int argc, char** argv) {
    int iters = 100;
    if (argc > 1) {
        iters = atoi(argv[1]);
    }
    init_image();
    conv2d_kernel(iters);
    printf("Conv2D Checksum: %.6f\n", output[HEIGHT / 2][WIDTH / 2]);
    return 0;
}
