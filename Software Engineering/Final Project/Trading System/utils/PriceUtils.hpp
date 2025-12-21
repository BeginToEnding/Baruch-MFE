// ====================== PriceUtils.hpp ======================
#ifndef PRICE_UTILS_HPP
#define PRICE_UTILS_HPP

#include <string>
#include <stdexcept>
using namespace std;

/**
 * Convert FRAC like ¡°100-255¡± or ¡°100-25+¡± to decimal.
 * xy = 0..31   z = 0..7 (z=4 represented as '+')
 */
inline double FractionalToDecimal(const string& px) {
    // Format: AAA-XYZ
    int dash = px.find('-');
    if (dash < 0) throw invalid_argument("Bad fractional price");

    double base = stod(px.substr(0, dash));
    string frac = px.substr(dash + 1);

    int xy = stoi(frac.substr(0, 2));
    char zc = frac[2];
    int z = (zc == '+') ? 4 : (zc - '0');

    return base + xy / 32.0 + z / 256.0;
}

/**
 * Convert decimal back to FRAC AAA-XYZ (z=4 becomes '+').
 */
inline string DecimalToFractional(double px) {
    int base = int(px);
    double rem = px - base;

    int xy = int(rem * 32);
    int z = int((rem * 256)) % 8;

    char zc = (z == 4 ? '+' : char('0' + z));

    char buf[16];
    sprintf(buf, "%d-%02d%c", base, xy, zc);
    return string(buf);
}

#endif
