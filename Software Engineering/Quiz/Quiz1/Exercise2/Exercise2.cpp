#include <iostream>
#include <vector>
using namespace std;

class MaxHeap {
private:
    vector<int> h;

    // Move child upwards if larger than parent
    void bubbleUp(int i) {
        while (i > 0) {
            int p = (i - 1) / 2;   // parent index
            if (h[p] < h[i]) {
                swap(h[p], h[i]);
                i = p;
            }
            else break;
        }
    }

public:
    void Add(int x) {
        h.push_back(x);
        bubbleUp(h.size() - 1);
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
    heap.Print();
}
