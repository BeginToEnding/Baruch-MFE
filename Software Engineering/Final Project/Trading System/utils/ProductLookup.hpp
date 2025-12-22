/**
 * ProductLookup.hpp
 * A thin wrapper providing global access to the Treasury product universe.
 *
 * This class delegates to functions defined in TreasuryProducts.hpp:
 *   - ::GetBond(cusip)
 *   - ::GetBondByTicker(ticker)
 *   - ::TreasuryUniverse()
 *
 * @author Hao Wang
 */
#ifndef PRODUCT_LOOKUP_HPP
#define PRODUCT_LOOKUP_HPP

#include <string>
#include <vector>
#include <map>

#include "../products/TreasuryProducts.hpp"

 /**
  * ProductLookup
  * Central access point for Treasury products (Bond universe).
  *
  * Notes:
  * - Returned references remain valid for the lifetime of the program because the universe
  *   is stored in a global container.
  * - The "::" prefix forces lookup in the global namespace (not ProductLookup::GetBond itself).
  */
class ProductLookup
{
public:
    /**
     * Lookup Treasury(Bond) by CUSIP.
     */
    static const Treasury& GetBond(const std::string& cusip)
    {
        return ::GetBond(cusip);
    }

    /**
     * Lookup Treasury(Bond) by ticker (e.g., "T").
     * Depending on your TreasuryProducts implementation, this may return one or multiple bonds.
     * Here it delegates to your global function.
     */
    static const Treasury& GetBondByTicker(const std::string& ticker)
    {
        return ::GetBondByTicker(ticker);
    }

    /**
     * Return all bonds as pointers.
     * Useful for iterating without copying the objects.
     */
    static std::vector<const Treasury*> GetAllBonds()
    {
        std::vector<const Treasury*> v;
        for (auto& kv : TreasuryUniverse())
            v.push_back(&kv.second);
        return v;
    }

    /**
     * Expose the full universe map (CUSIP -> Treasury).
     */
    static const std::map<std::string, Treasury>& Universe()
    {
        return TreasuryUniverse();
    }
};

#endif
