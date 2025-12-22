/**
 * Books.hpp
 * Utility functions and constants for cycling through trading books.
 *
 * @author Hao Wang
 */
#ifndef BOOKS_HPP
#define BOOKS_HPP

#include <string>

 /**
  * List of supported books.
  * Note: "static" gives internal linkage, so each translation unit gets its own copy.
  * This avoids multiple-definition linker errors in pre-C++17.
  */
static const std::string BOOKS[3] = { "TRSY1", "TRSY2", "TRSY3" };

/**
 * Return the next book name in round-robin order.
 *
 * @param idx  Input/output index used to track where we are in the cycle.
 *             This value is updated in-place.
 * @return     The selected book name.
 */
inline std::string NextBook(int& idx)
{
    // Defensive: keep idx in range even if caller passes a weird value.
    idx = (idx % 3 + 3) % 3;

    const std::string b = BOOKS[idx];
    idx = (idx + 1) % 3;
    return b;
}

#endif
