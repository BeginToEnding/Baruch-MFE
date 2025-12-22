/**
 * GUIService.cpp
 * Implements GUIService: throttled price logging to gui.txt.
 *
 * Output format example:
 *   2025-12-21 18:12:34.123  91282CGW5  Mid=100-01+  Spread=0-00?
 *
 * Note:
 * - We convert decimal mid/spread into Treasury fractional string via DecimalToFractional
 *   right before writing (assignment requirement for file output).
 *
 * @author Hao Wang
 */

#include "GUIService.hpp"

using namespace std;

GUIService::GUIService()
    : count(0),
    fout("gui.txt", ios::app)
{
    // gui.txt is created automatically when opening the ofstream.
    if (!fout.is_open())
    {
        cerr << "[GUIService] Failed to open gui.txt for append.\n";
    }
}

GUIService::~GUIService()
{
    if (fout.is_open())
    {
        fout.close();
    }
}

void GUIService::OnMessage(Price<Bond>& data)
{
    // Only log the first 100 updates to keep output small.
    if (count >= kMaxUpdates) return;

    const string cusip = data.GetProduct().GetProductId();

    // Store the latest Price by CUSIP. Use erase+emplace to avoid operator= issues.
    priceMap.erase(cusip);
    map<string, Price<Bond> >::iterator it = priceMap.emplace(cusip, data).first;

    // Stored reference has stable lifetime for this scope.
    Price<Bond>& stored = it->second;

    if (fout.is_open())
    {
        // Timestamp with millisecond precision.
        fout << NowTimestampMS() << "  "
            << cusip
            << "  Mid=" << DecimalToFractional(stored.GetMid())
            << "  Spread=" << DecimalToFractional(stored.GetBidOfferSpread())
            << "\n";

        // Optional: flush so you can watch file update in real time.
        // This hurts performance if you write very frequently, but GUI is throttled.
        fout.flush();
    }

    ++count;
}
