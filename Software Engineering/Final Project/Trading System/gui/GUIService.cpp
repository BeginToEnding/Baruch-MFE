// ====================== GUIService.cpp ======================
#include "GUIService.hpp"

GUIService::GUIService()
    : count(0), fout("gui.txt", std::ios::app)
{
    if (!fout.is_open())
    {
        std::cerr << "[GUIService] Failed to open gui.txt for append.\n";
    }
}

GUIService::~GUIService()
{
    if (fout.is_open())
        fout.close();
}

void GUIService::OnMessage(Price<Bond>& data)
{
    // Only log the first 100 updates to keep output small.
    if (count >= kMaxUpdates) return;

    const string cusip = data.GetProduct().GetProductId();

    priceMap.erase(cusip);
    auto it = priceMap.emplace(cusip, data).first;
    Price<Bond>& stored = it->second;

    if (fout.is_open())
    {
        fout << NowTimestampMS() << "  "
            << cusip
            << "  Mid=" << stored.GetMid()
            << "  Spread=" << stored.GetBidOfferSpread()
            << "\n";
        // Optional: flush so we can watch file update in real time
        fout.flush();
    }

    ++count;
}
