#ifndef TREASURY_PRODUCTS_HPP
#define TREASURY_PRODUCTS_HPP

#include <string>
#include <map>
#include <vector>
#include "../base/products.hpp"
#include "boost/date_time/gregorian/gregorian.hpp"

using namespace std;
using namespace boost::gregorian;

class Treasury: public Bond
{
public:
    Treasury(const string& _cusip,
        const string& _ticker,
        double _coupon,
        const date& _maturity)
        : Bond(_cusip, CUSIP(_cusip), _ticker, _coupon, _maturity)
    {
    }
};

// Return map<CUSIP, TreasuryBond>
const map<string, Treasury>& TreasuryUniverse();

// Lookup by CUSIP
const Treasury& GetBond(const string& cusip);

// Lookup by ticker (T2Y, T10Y)
const Treasury& GetBondByTicker(const string& ticker);

#endif
