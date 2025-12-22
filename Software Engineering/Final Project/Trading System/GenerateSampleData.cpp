/**
 * GenerateSmapleData.cpp
 * Generates sample input files (prices, market data, trades, inquiries) for the US Treasury trading system.
 * The generated files are newline-delimited CSV records intended to be fed into socket listeners via FileFeeder.
 *
 * Output files:
 * - prices.txt:      CUSIP,MidFrac,SpreadFrac
 * - marketdata.txt:  CUSIP,MidFrac,TopSpreadFrac
 * - trades.txt:      CUSIP,SIDE,QTY,PXFrac,TRADEID
 * - inquiries.txt:   INQID,CUSIP,SIDE,QTY,PXFrac
 *
 * Notes:
 * - All prices are written in Treasury fractional format with 1/256 tick granularity.
 * - Mid prices oscillate between 99.0 and 101.0 by 1/256 ticks.
 * - Pricing spread oscillates between 1/128 and 1/64 (in 1/256 tick steps).
 * - Market data top spread cycles among {1/128, 1/64, 3/128, 1/32, 3/128, 1/64}.
 *
 * @author Hao Wang
 */

// tools/GenerateSmapleData.cpp
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>
#include <cmath>
#include <stdexcept>

using namespace std;

/** Smallest tick size used for US Treasury pricing. */
static constexpr double TICK = 1.0 / 256.0;

/** Mid-price lower bound for generated pricing streams. */
static constexpr double MID_MIN = 99.0;

/** Mid-price upper bound for generated pricing streams. */
static constexpr double MID_MAX = 101.0;

#include <cctype>
#include <cstdio>

/**
 * Trim leading and trailing whitespace from a string.
 *
 * @param s  Input string.
 * @return   Trimmed string.
 */
inline std::string Trim(const std::string& s)
{
    size_t i = 0, j = s.size();
    while (i < j && std::isspace(static_cast<unsigned char>(s[i]))) ++i;
    while (j > i && std::isspace(static_cast<unsigned char>(s[j - 1]))) --j;
    return s.substr(i, j - i);
}

/**
 * Convert a decimal price into Treasury fractional format "AAA-xyz".
 *
 * - The smallest unit is 1/256.
 * - "xy" represents 32nds (00..31).
 * - "z" represents 1/8 of a 32nd (0..7).
 * - Special case: z=4 is represented as '+'.
 *
 * Example:
 *   100.0      -> "100-000"
 *   100 + 25/32 + 4/256 -> "100-25+"
 *
 * @param px  Decimal price.
 * @return    Fractional price string.
 */
inline std::string DecimalToFractional(double px)
{
    // Round to nearest 1/256 tick to avoid floating-point noise in output.
    const double rounded = std::round(px * 256.0) / 256.0;

    // Integer "handle" part of the price (the AAA portion).
    int base = static_cast<int>(std::floor(rounded + 1e-12));
    double rem = rounded - base;

    // Remaining part expressed as ticks in [0..256].
    int ticks = static_cast<int>(std::llround(rem * 256.0));
    if (ticks == 256)
    {
        // Carry overflow into base and reset remainder ticks.
        base += 1;
        ticks = 0;
    }

    // Split ticks into 32nds (xy) and 1/256 increments (z).
    const int xy = ticks / 8;   // 0..31
    const int z  = ticks % 8;   // 0..7

    // Represent z=4 as '+', otherwise use '0'..'7'.
    const char zc = (z == 4 ? '+' : static_cast<char>('0' + z));

    char buf[32];
    std::snprintf(buf, sizeof(buf), "%d-%02d%c", base, xy, zc);
    return std::string(buf);
}

/**
 * Generate an oscillating mid price between MID_MIN and MID_MAX.
 *
 * The mid price "bounces" at the endpoints to form a triangle wave:
 *   99.0 -> ... -> 101.0 -> ... -> 99.0 -> ...
 *
 * The step size is 1/256.
 *
 * @param i  Tick index (monotonically increasing).
 * @return   Mid price in decimal.
 */
static double OscillateMid(long long i)
{
    // Number of ticks from MID_MIN to MID_MAX (exclusive of endpoint handling).
    const int rangeTicks = static_cast<int>((MID_MAX - MID_MIN) / TICK); // 512
    const int period = 2 * rangeTicks;

    // Position in the triangle-wave period.
    int p = static_cast<int>(i % period);

    // Rising then falling segment.
    if (p <= rangeTicks) return MID_MIN + p * TICK;
    return MID_MAX - (p - rangeTicks) * TICK;
}

/**
 * Generate a pricing bid/offer spread oscillating between 1/128 and 1/64.
 *
 * Spread is expressed as a multiple of 1/256 ticks:
 *   1/128 = 2 ticks
 *   1/64  = 4 ticks
 *
 * The sequence cycles as: 2,3,4,3,2,...
 *
 * @param i  Tick index.
 * @return   Spread in decimal.
 */
static double OscillatePricingSpread(long long i)
{
    const int minTicks = 2; // 1/128
    const int maxTicks = 4; // 1/64
    const int steps = maxTicks - minTicks; // 2
    const int period = 2 * steps;

    // Build a "bounce" sequence in tick space.
    int p = static_cast<int>(i % period);
    int ticks = (p <= steps) ? (minTicks + p) : (maxTicks - (p - steps));
    return ticks * TICK;
}

/**
 * Generate the market data top-of-book spread sequence.
 *
 * Required cycle:
 *   1/128, 1/64, 3/128, 1/32, 3/128, 1/64, ...
 *
 * Implemented via multipliers in /128 units:
 *   1, 2, 3, 4, 3, 2
 *
 * @param i  Tick index.
 * @return   Top-of-book spread in decimal.
 */
static double MarketDataTopSpread(long long i)
{
    static const int mults[] = { 1, 2, 3, 4, 3, 2 };
    int idx = static_cast<int>(i % (sizeof(mults) / sizeof(mults[0])));
    return static_cast<double>(mults[idx]) / 128.0;
}

/**
 * Main generator entry point.
 *
 * Usage:
 *   GenerateSmapleData [--test]
 *
 * Defaults:
 * - pricesPerSec = 1,000,000 lines per CUSIP
 * - mdPerSec     = 1,000,000 lines per CUSIP
 * - tradesPerSec = 10 lines per CUSIP
 * - inqPerSec    = 10 lines per CUSIP
 *
 * With --test:
 * - pricesPerSec = 2,000 lines per CUSIP
 * - mdPerSec     = 2,000 lines per CUSIP
 *
 * @param argc  Argument count.
 * @param argv  Argument vector.
 * @return      Process exit code.
 */
int main(int argc, char** argv)
{
    // Default = full homework sizes (large files).
    long long pricesPerSec = 1'000'000;
    long long mdPerSec     = 1'000'000;
    int tradesPerSec       = 10;
    int inqPerSec          = 10;

    // Optional smaller generation size for quick end-to-end tests.
    if (argc >= 2 && std::string(argv[1]) == "--test")
    {
        pricesPerSec = 2000;
        mdPerSec     = 2000;
        tradesPerSec = 10;
        inqPerSec    = 10;
    }

    /**
     * Treasury universe: 7 representative CUSIPs.
     * These should match the ones in products/TreasuryProducts.cpp.
     */
    const std::vector<std::string> cusips = {
        "91282CGW5","91282CGZ8","91282CHA2","91282CHD6","91282CHE4","912810TF9","912810TG7"
    };

    // Output files consumed by FileFeeder (one line = one message).
    std::ofstream prices("prices.txt");
    std::ofstream market("marketdata.txt");
    std::ofstream trades("trades.txt");
    std::ofstream inqs("inquiries.txt");

    if (!prices || !market || !trades || !inqs)
    {
        std::cerr << "Failed to open output files.\n";
        return 1;
    }

    long long tradeId = 1;
    long long inqId = 1;

    // ---------- prices.txt & marketdata.txt (large streams) ----------
    // For each CUSIP, generate the required number of rows.
    for (const auto& c : cusips)
    {
        // Pricing feed: CUSIP, mid (frac), spread (frac)
        for (long long i = 0; i < pricesPerSec; ++i)
        {
            const double mid = OscillateMid(i);
            const double spr = OscillatePricingSpread(i);

            prices << c << ","
                   << DecimalToFractional(mid) << ","
                   << DecimalToFractional(spr) << "\n";
        }

        // Market data feed: CUSIP, mid (frac), topSpread (frac)
        for (long long i = 0; i < mdPerSec; ++i)
        {
            const double mid = OscillateMid(i);
            const double topSpr = MarketDataTopSpread(i);

            market << c << ","
                   << DecimalToFractional(mid) << ","
                   << DecimalToFractional(topSpr) << "\n";
        }
    }

    // ---------- trades.txt (70 lines total) ----------
    // Requirements:
    // - 10 trades per security
    // - alternate BUY/SELL
    // - qty cycles 1m..5m repeating
    // - BUY price 99.0, SELL price 100.0
    for (const auto& c : cusips)
    {
        for (int i = 0; i < tradesPerSec; ++i)
        {
            const bool buy = (i % 2 == 0);
            const std::string side = buy ? "BUY" : "SELL";

            // Cycle sizes: 1MM,2MM,3MM,4MM,5MM, then repeat.
            const long qty = static_cast<long>(((i % 5) + 1) * 1'000'000);

            // Fixed trade prices per requirement.
            const double px = buy ? 99.0 : 100.0;

            trades << c << ","
                   << side << ","
                   << qty << ","
                   << DecimalToFractional(px) << ","
                   << "TRD_" << std::setw(6) << std::setfill('0') << tradeId++
                   << "\n";
        }
    }

    // ---------- inquiries.txt (70 lines total) ----------
    // Generate 10 inquiries per security, alternating BUY/SELL and using the same size cycle.
    for (const auto& c : cusips)
    {
        for (int i = 0; i < inqPerSec; ++i)
        {
            const bool buy = (i % 2 == 0);
            const std::string side = buy ? "BUY" : "SELL";

            const long qty = static_cast<long>(((i % 5) + 1) * 1'000'000);

            // Initial inquiry price can be arbitrary; keep it fixed for reproducibility.
            const double px = 100.0;

            inqs << "INQ_" << std::setw(6) << std::setfill('0') << inqId++
                 << "," << c
                 << "," << side
                 << "," << qty
                 << "," << DecimalToFractional(px)
                 << "\n";
        }
    }

    // Summary report for the user.
    std::cout << "Generated:\n"
              << "  prices.txt      (" << (7LL * pricesPerSec) << " lines)\n"
              << "  marketdata.txt  (" << (7LL * mdPerSec) << " lines)\n"
              << "  trades.txt      (" << (7 * tradesPerSec) << " lines)\n"
              << "  inquiries.txt   (" << (7 * inqPerSec) << " lines)\n";
    return 0;
}
