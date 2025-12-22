/**
 * TreasuryProducts.cpp
 * Implements the US Treasury product universe and lookup functions.
 *
 * Design:
 *  - The universe is stored as a single global static map.
 *  - InitBonds() lazily initializes the map on first access.
 *
 * Thread-safety note:
 *  - This lazy init is fine in single-threaded init order, but if multiple threads
 *    call GetBond/GetBondByTicker at the same time before initialization completes,
 *    it is not strictly thread-safe in C++11 without extra guards.
 *
 * @author Hao Wang
 */

#include "TreasuryProducts.hpp"

#include <stdexcept>   // runtime_error

 /**
  * Global treasury universe store.
  *
  * Key:   CUSIP string
  * Value: Treasury object
  *
  * We keep it in this .cpp to avoid multiple-definition issues.
  */
static map<string, Treasury> bondUniverse;

/**
 * Lazy-initialize the treasury universe.
 *
 * We only populate the map once, on first use.
 * Subsequent calls return immediately.
 */
static void InitBonds()
{
    // If already initialized, do nothing.
    if (!bondUniverse.empty()) return;

    // Populate 7 treasuries required by the assignment.
    bondUniverse.emplace("91282CGW5",
        Treasury("91282CGW5", "T2Y", 0.04625, date(2027, Feb, 28)));

    bondUniverse.emplace("91282CGZ8",
        Treasury("91282CGZ8", "T3Y", 0.04250, date(2028, Feb, 28)));

    bondUniverse.emplace("91282CHA2",
        Treasury("91282CHA2", "T5Y", 0.04000, date(2030, Feb, 28)));

    bondUniverse.emplace("91282CHD6",
        Treasury("91282CHD6", "T7Y", 0.04125, date(2032, Feb, 28)));

    bondUniverse.emplace("91282CHE4",
        Treasury("91282CHE4", "T10Y", 0.04500, date(2035, Feb, 15)));

    bondUniverse.emplace("912810TF9",
        Treasury("912810TF9", "T20Y", 0.04500, date(2045, Feb, 15)));

    bondUniverse.emplace("912810TG7",
        Treasury("912810TG7", "T30Y", 0.04500, date(2055, Feb, 15)));
}

/**
 * Return the global treasury universe.
 *
 * @return Const reference to the map so callers cannot modify the universe.
 */
const map<string, Treasury>& TreasuryUniverse()
{
    // Ensure initialization has happened before returning.
    InitBonds();
    return bondUniverse;
}

/**
 * Lookup by CUSIP.
 *
 * @param cusip  Treasury CUSIP.
 * @return       Const reference to Treasury object in universe.
 */
const Treasury& GetBond(const string& cusip)
{
    // Ensure universe exists before lookup.
    InitBonds();

    // at() throws if missing; that's OK (fail fast on bad input).
    return bondUniverse.at(cusip);
}

/**
 * Lookup by ticker.
 *
 * @param ticker  Treasury ticker such as "T2Y".
 * @return        Const reference to Treasury object.
 * @throws        runtime_error if ticker not found.
 */
const Treasury& GetBondByTicker(const string& ticker)
{
    // Ensure universe exists before scanning.
    InitBonds();

    // Linear scan is fine for only 7 products.
    for (auto& kv : bondUniverse)
    {
        if (kv.second.GetTicker() == ticker)
            return kv.second;
    }

    // Explicit error makes debugging wrong ticker inputs easier.
    throw runtime_error("Ticker not found: " + ticker);
}
