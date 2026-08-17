#include <stdio.h>
#include <stdlib.h>

#define N 500000

int main(void) {
    long long multiplier = 1;
    if (scanf("%lld", &multiplier) != 1) {
        multiplier = 1;
    }

    long long sum = 0;
    for (int i = 0; i < N; i++) {
        sum += (i * multiplier) ^ (i % 7);
    }

    printf("Result: %lld\n", sum);
    return 0;
}
