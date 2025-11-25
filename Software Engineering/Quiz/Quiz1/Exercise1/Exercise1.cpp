#include <iostream>
#include <vector>
using namespace std;

// Partition using Lomuto partition scheme
int partition(vector<int>& a, int l, int r) {
    int pivot = a[r];
    int i = l - 1;
    for (int j = l; j < r; j++) {
        if (a[j] <= pivot) {
            ++i;
            swap(a[i], a[j]);
        }
    }
    swap(a[i + 1], a[r]);
    return i + 1;
}

void quicksort(vector<int>& a, int l, int r) {
    if (l >= r) return;
    int p = partition(a, l, r);
    quicksort(a, l, p - 1);
    quicksort(a, p + 1, r);
}

int main() {
    vector<int> arr = { 5, 3, 8, 4, 2, 7, 1 };
    quicksort(arr, 0, arr.size() - 1);

    for (int x : arr) cout << x << " ";
    cout << endl;
}
