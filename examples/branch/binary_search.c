/*
 * Autotune Example Workload: Binary Search
 * Branch-heavy search kernel.
 */

#include <stdio.h>

#define SIZE 10000

int arr[SIZE];

int binary_search(int target) {
    int low = 0, high = SIZE - 1;
    while (low <= high) {
        int mid = low + (high - low) / 2;
        if (arr[mid] == target) return mid;
        if (arr[mid] < target) low = mid + 1;
        else high = mid - 1;
    }
    return -1;
}

int main() {
    for (int i = 0; i < SIZE; i++) arr[i] = i * 2;

    int matches = 0;
    for (int i = 0; i < 5000; i++) {
        if (binary_search(i * 2) != -1) matches++;
    }

    printf("Binary search complete. Matches = %d\n", matches);
    return 0;
}
