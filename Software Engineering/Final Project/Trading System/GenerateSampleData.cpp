// tools/GenerateHomeworkData.cpp
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>
#include <cmath>
#include <string>
#include <stdexcept>
using namespace std;

static constexpr double TICK = 1.0 / 256.0;
static constexpr double MID_MIN = 99.0;
static constexpr double MID_MAX = 101.0;

#include <string>
#include <stdexcept>
#include <cctype>
#include <cmath>
#include <cstdio>

inline std::string Trim(const std::string& s)
{
    size_t i = 0, j = s.size();
    while (i < j && std::isspace(static_cast<unsigned char>(s[i]))) ++i;
    while (j > i && std::isspace(static_cast<unsigned char>(s[j - 1]))) --j;
    return s.substr(i, j - i);
}

// Convert decimal back to FRAC "AAA-xyz" (z=4 becomes '+'), rounded to nearest 1/256.
inline std::string DecimalToFractional(double px)
{
    // round to nearest 1/256 tick
    const double rounded = std::round(px * 256.0) / 256.0;

    int base = static_cast<int>(std::floor(rounded + 1e-12));
    double rem = rounded - base;

    // total ticks in [0..256]
    int ticks = static_cast<int>(std::llround(rem * 256.0));
    if (ticks == 256) { base += 1; ticks = 0; }

    const int xy = ticks / 8;   // 0..31
    const int z  = ticks % 8;   // 0..7

    const char zc = (z == 4 ? '+' : static_cast<char>('0' + z));

    char buf[32];
    std::snprintf(buf, sizeof(buf), "%d-%02d%c", base, xy, zc);
    return std::string(buf);
}



static double OscillateMid(long long i)
{
    const int rangeTicks = static_cast<int>((MID_MAX - MID_MIN) / TICK); // 512
    const int period = 2 * rangeTicks;

    int p = static_cast<int>(i % period);
    if (p <= rangeTicks) return MID_MIN + p * TICK;
    return MID_MAX - (p - rangeTicks) * TICK;
}

static double OscillatePricingSpread(long long i)
{
    // between 1/128 and 1/64, step 1/256 ticks: 2,3,4,3,2...
    const int minTicks = 2; // 1/128
    const int maxTicks = 4; // 1/64
    const int steps = maxTicks - minTicks; // 2
    const int period = 2 * steps;

    int p = static_cast<int>(i % period);
    int ticks = (p <= steps) ? (minTicks + p) : (maxTicks - (p - steps));
    return ticks * TICK;
}

static double MarketDataTopSpread(long long i)
{
    // 1/128, 1/64, 3/128, 1/32, 3/128, 1/64 repeat
    // expressed in /128 units: 1,2,3,4,3,2
    static const int mults[] = {1,2,3,4,3,2};
    int idx = static_cast<int>(i % (sizeof(mults)/sizeof(mults[0])));
    return static_cast<double>(mults[idx]) / 128.0;
}

int main(int argc, char** argv)
{
    // Default = full homework sizes
    long long pricesPerSec = 1'000'000;
    long long mdPerSec     = 1'000'000;
    int tradesPerSec       = 10;
    int inqPerSec          = 10;

    if (argc >= 2 && std::string(argv[1]) == "--test")
    {
        // small for quick end-to-end testing
        pricesPerSec = 2000;
        mdPerSec     = 2000;
        tradesPerSec = 10;
        inqPerSec    = 10;
    }

    const std::vector<std::string> cusips = {
        "91282CGW5","91282CGZ8","91282CHA2","91282CHD6","91282CHE4","912810TF9","912810TG7"
    };

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

    // ---------- prices.txt & marketdata.txt (huge) ----------
    for (const auto& c : cusips)
    {
        for (long long i = 0; i < pricesPerSec; ++i)
        {
            const double mid = OscillateMid(i);
            const double spr = OscillatePricingSpread(i);

            prices << c << ","
                   << DecimalToFractional(mid) << ","
                   << DecimalToFractional(spr) << "\n";
        }

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

            const long qty = static_cast<long>(((i % 5) + 1) * 1'000'000);

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
    for (const auto& c : cusips)
    {
        for (int i = 0; i < inqPerSec; ++i)
        {
            const bool buy = (i % 2 == 0);
            const std::string side = buy ? "BUY" : "SELL";

            const long qty = static_cast<long>(((i % 5) + 1) * 1'000'000);

            // initial price can be anything; keep it simple
            const double px = 100.0;

            inqs << "INQ_" << std::setw(6) << std::setfill('0') << inqId++
                 << "," << c
                 << "," << side
                 << "," << qty
                 << "," << DecimalToFractional(px)
                 << "\n";
        }
    }

    std::cout << "Generated:\n"
              << "  prices.txt      (" << (7LL * pricesPerSec) << " lines)\n"
              << "  marketdata.txt  (" << (7LL * mdPerSec) << " lines)\n"
              << "  trades.txt      (" << (7 * tradesPerSec) << " lines)\n"
              << "  inquiries.txt   (" << (7 * inqPerSec) << " lines)\n";
    return 0;
}
