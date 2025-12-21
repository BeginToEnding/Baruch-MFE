#ifndef PRODUCT_LOOKUP_HPP
#define PRODUCT_LOOKUP_HPP

#include <string>
#include <vector>
#include <map>
#include "../products/TreasuryProducts.hpp"

using namespace std;

/**
 * ProductLookup
 * Provides easy access to the global Treasury bond universe.
 * All returned objects are references to the unique TreasuryBond instances.
 */
class ProductLookup
{
public:
    static const Treasury& GetBond(const std::string& cusip)
    {
        return ::GetBond(cusip);
    }

    static const Treasury& GetBondByTicker(const std::string& ticker)
    {
        return ::GetBondByTicker(ticker);
    }

    static std::vector<const Treasury*> GetAllBonds()
    {
        std::vector<const Treasury*> v;
        for (auto& kv : TreasuryUniverse())
            v.push_back(&kv.second);
        return v;
    }

    static const std::map<std::string, Treasury>& Universe()
    {
        return TreasuryUniverse();
    }
};

#endif
