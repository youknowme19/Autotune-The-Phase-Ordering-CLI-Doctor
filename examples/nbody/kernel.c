/*
 * N-Body Gravitational Physics Particle Simulation Kernel
 * All-pairs O(N^2) pairwise force interaction with vector velocity Verlet integration.
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

#define BODIES 256
#define SOFTENING 1e-9

typedef struct {
    double x, y, z;
    double vx, vy, vz;
    double mass;
} Body;

static Body bodies[BODIES];

void init_bodies() {
    for (int i = 0; i < BODIES; i++) {
        bodies[i].x = (double)(i % 50) - 25.0;
        bodies[i].y = (double)((i * 3) % 50) - 25.0;
        bodies[i].z = (double)((i * 7) % 50) - 25.0;
        bodies[i].vx = 0.0;
        bodies[i].vy = 0.0;
        bodies[i].vz = 0.0;
        bodies[i].mass = 1.0 + (double)(i % 10);
    }
}

void nbody_kernel(int steps, double dt) {
    for (int step = 0; step < steps; step++) {
        for (int i = 0; i < BODIES; i++) {
            double Fx = 0.0, Fy = 0.0, Fz = 0.0;
            for (int j = 0; j < BODIES; j++) {
                if (i == j) continue;
                double dx = bodies[j].x - bodies[i].x;
                double dy = bodies[j].y - bodies[i].y;
                double dz = bodies[j].z - bodies[i].z;
                double dist_sq = dx * dx + dy * dy + dz * dz + SOFTENING;
                double inv_dist = 1.0 / sqrt(dist_sq);
                double inv_dist3 = inv_dist * inv_dist * inv_dist;
                double f = bodies[j].mass * inv_dist3;
                Fx += dx * f;
                Fy += dy * f;
                Fz += dz * f;
            }
            bodies[i].vx += dt * Fx;
            bodies[i].vy += dt * Fy;
            bodies[i].vz += dt * Fz;
        }

        for (int i = 0; i < BODIES; i++) {
            bodies[i].x += dt * bodies[i].vx;
            bodies[i].y += dt * bodies[i].vy;
            bodies[i].z += dt * bodies[i].vz;
        }
    }
}

int main(int argc, char** argv) {
    int steps = 100;
    if (argc > 1) {
        steps = atoi(argv[1]);
    }
    init_bodies();
    nbody_kernel(steps, 0.01);
    printf("NBody Checksum: Body[0] pos=(%.4f, %.4f, %.4f)\n", bodies[0].x, bodies[0].y, bodies[0].z);
    return 0;
}
