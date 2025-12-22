/**
 * TreasuryProducts.hpp
 * Defines the US Treasury product universe used by the trading system.
 *
 * This file provides:
 *  - A Treasury product type (derives from Bond)
 *  - Global lookup functions to access a shared in-memory universe of Treasuries
 *
 * @author Hao Wang
 */

#ifndef TREASURY_PRODUCTS_HPP
#define TREASURY_PRODUCTS_HPP

#include <string>
#include <map>
#include <vector>

#include "../base/products.hpp"
#include "boost/date_time/gregorian/gregorian.hpp"

using namespace std;
using namespace boost::gregorian;

/**
 * Treasury
 * Concrete treasury bond product type used in this project.
 *
 * Note:
 *  - The base Bond class is provided by the course code.
 *  - We reuse CUSIP as the product identifier.
 */
class Treasury : public Bond
{
public:
    /**
     * Construct a Treasury bond.
     *
     * @param _cusip     Treasury CUSIP string (used as productId)
     * @param _ticker    Short ticker symbol (e.g., T2Y, T10Y)
     * @param _coupon    Annual coupon rate (e.g., 0.045)
     * @param _maturity  Maturity date
     */
    Treasury(const string& _cusip,
        const string& _ticker,
        double _coupon,
        const date& _maturity)
        : Bond(_cusip, CUSIP(_cusip), _ticker, _coupon, _maturity)
    {
        // Bond constructor takes:
        //   productId, CUSIP, ticker, coupon, maturity
    }
};

/**
 * Return the global treasury universe.
 *
 * This is a shared map:
 *   key   = CUSIP string
 *   value = Treasury object
 *
 * @return Const reference to the global universe map.
 */
const map<string, Treasury>& TreasuryUniverse();

/**
 * Lookup a Treasury by CUSIP.
 *
 * @param cusip  The CUSIP string key.
 * @return       Const reference to the Treasury in the universe.
 * @throws       std::out_of_range if CUSIP not found.
 */
const Treasury& GetBond(const string& cusip);

/**
 * Lookup a Treasury by ticker.
 *
 * @param ticker  Ticker string (e.g., "T2Y", "T10Y")
 * @return        Const reference to the Treasury in the universe.
 * @throws        std::runtime_error if ticker not found.
 */
const Treasury& GetBondByTicker(const string& ticker);

#endif
