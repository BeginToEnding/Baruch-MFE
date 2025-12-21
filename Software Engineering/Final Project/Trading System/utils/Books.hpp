// ====================== Books.hpp ======================
#ifndef BOOKS_HPP
#define BOOKS_HPP

#include <string>
using namespace std;

static const string BOOKS[3] = { "TRSY1", "TRSY2", "TRSY3" };

/**
 * Returns next book in cycle.
 */
inline string NextBook(int& idx) {
    string b = BOOKS[idx];
    idx = (idx + 1) % 3;
    return b;
}

#endif
