#include "TreasuryProducts.hpp"

static map<string, Treasury> bondUniverse;

static void InitBonds()
{
    if (!bondUniverse.empty()) return;

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

const map<string, Treasury>& TreasuryUniverse()
{
    InitBonds();
    return bondUniverse;
}

const Treasury& GetBond(const string& cusip)
{
    InitBonds();
    return bondUniverse.at(cusip);
}

const Treasury& GetBondByTicker(const string& ticker)
{
    InitBonds();
    for (auto& kv : bondUniverse)
        if (kv.second.GetTicker() == ticker)
            return kv.second;

    throw runtime_error("Ticker not found: " + ticker);
}
