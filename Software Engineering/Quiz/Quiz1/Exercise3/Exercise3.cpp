#include <iostream>
#include <vector>
using namespace std;

class MaxHeap {
private:
    vector<int> h;

    void bubbleUp(int i) {
        while (i > 0) {
            int p = (i - 1) / 2;
            if (h[p] < h[i]) {
                swap(h[p], h[i]);
                i = p;
            }
            else break;
        }
    }

    void bubbleDown(int i) {
        int n = h.size();
        while (true) {
            int left = 2 * i + 1;
            int right = 2 * i + 2;
            int largest = i;

            if (left < n && h[left] > h[largest]) largest = left;
            if (right < n && h[right] > h[largest]) largest = right;

            if (largest != i) {
                swap(h[i], h[largest]);
                i = largest;
            }
            else break;
        }
    }

public:
    void Add(int x) {
        h.push_back(x);
        bubbleUp(h.size() - 1);
    }

    int RemoveMax() {
        if (h.empty()) throw runtime_error("heap empty");

        int maxValue = h[0];
        h[0] = h.back();
        h.pop_back();
        if (!h.empty()) bubbleDown(0);

        return maxValue;
    }

    void Print() {
        for (int x : h) cout << x << " ";
        cout << endl;
    }
};

int main() {
    MaxHeap heap;
    heap.Add(10);
    heap.Add(4);
    heap.Add(15);
    heap.Add(20);
    heap.Add(17);

    heap.Print();

    cout << "Removed: " << heap.RemoveMax() << endl;
    heap.Print();
}
