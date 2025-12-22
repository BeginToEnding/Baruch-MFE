/**
 * PriceUtils.hpp
 * Utility functions for converting US Treasury fractional prices.
 *
 * Fractional format: AAA-xy z
 * - AAA is the integer price (e.g., 99, 100, 101)
 * - xy is 00..31 meaning xy/32
 * - z  is 0..7 meaning z/256; the special symbol '+' represents z = 4
 *
 * Example:
 *  - 100-001 => 100 + 0/32 + 1/256 = 100.00390625
 *  - 100-25+ => 100 + 25/32 + 4/256 = 100.796875
 *
 * @author Hao Wang
 */
#ifndef PRICE_UTILS_HPP
#define PRICE_UTILS_HPP

#include <string>
#include <stdexcept>
#include <cctype>
#include <cmath>
#include <cstdio>

 /**
  * Trim leading and trailing whitespace.
  * Useful because file/socket input may include spaces.
  */
inline std::string Trim(const std::string& s)
{
    size_t i = 0, j = s.size();
    while (i < j && std::isspace(static_cast<unsigned char>(s[i]))) ++i;
    while (j > i && std::isspace(static_cast<unsigned char>(s[j - 1]))) --j;
    return s.substr(i, j - i);
}

/**
 * Convert a fractional Treasury price string (AAA-xyz) to decimal.
 *
 * @param raw  Fractional price string, e.g., "100-25+"
 * @return     Decimal price, e.g., 100.796875
 *
 * @throws std::invalid_argument if the format is invalid.
 */
inline double FractionalToDecimal(const std::string& raw)
{
    const std::string px = Trim(raw);

    // Must contain a dash separating base and fractional part.
    const auto dash = px.find('-');
    if (dash == std::string::npos)
        throw std::invalid_argument("Bad fractional price: " + px);

    const int base = std::stoi(px.substr(0, dash));
    const std::string frac = px.substr(dash + 1);

    // frac must contain at least 3 chars: two digits xy + one char z or '+'
    if (frac.size() < 3)
        throw std::invalid_argument("Bad fractional price: " + px);

    const int xy = std::stoi(frac.substr(0, 2));
    const char zc = frac[2];

    int z = 0;
    if (zc == '+') z = 4;
    else if (zc >= '0' && zc <= '7') z = zc - '0';
    else throw std::invalid_argument("Bad fractional z: " + px);

    if (xy < 0 || xy > 31)
        throw std::invalid_argument("Bad fractional xy: " + px);

    // Base + xy/32 + z/256
    return static_cast<double>(base)
        + static_cast<double>(xy) / 32.0
        + static_cast<double>(z) / 256.0;
}

/**
 * Convert a decimal price to the Treasury fractional format AAA-xyz.
 * The price is rounded to the nearest 1/256 tick.
 *
 * @param px  Decimal price.
 * @return    Fractional string, e.g., "100-25+"
 */
inline std::string DecimalToFractional(double px)
{
    // Round to nearest 1/256 tick so we always output valid Treasury ticks.
    const double rounded = std::round(px * 256.0) / 256.0;

    // Base integer part. Small epsilon avoids cases like 100.0000000001.
    int base = static_cast<int>(std::floor(rounded + 1e-12));
    double rem = rounded - base;

    // Convert remainder to ticks in [0..256]
    int ticks = static_cast<int>(std::llround(rem * 256.0));
    if (ticks == 256)
    {
        // Example: rounding can push remainder to exactly 1.0
        base += 1;
        ticks = 0;
    }

    // Each 1/32 = 8 ticks (since 1/32 = 8/256)
    const int xy = ticks / 8;   // 0..31
    const int z = ticks % 8;   // 0..7

    const char zc = (z == 4 ? '+' : static_cast<char>('0' + z));

    char buf[32];
    std::snprintf(buf, sizeof(buf), "%d-%02d%c", base, xy, zc);
    return std::string(buf);
}

#endif
