/**
 * GUIThrottleListener.hpp
 * A throttle listener for GUIService: only forward Price updates every 300ms.
 *
 * Registered on BondPricingService so that the GUI output is throttled.
 *
 * @author Hao Wang
 */

#ifndef GUI_THROTTLE_LISTENER_HPP
#define GUI_THROTTLE_LISTENER_HPP

#include "GUIService.hpp"
#include <chrono>

using namespace std;

/**
 * GUIThrottleListener
 * Applies a 300ms throttle on incoming Price<Bond> events.
 */
class GUIThrottleListener : public ServiceListener< Price<Bond> >
{
public:
    /**
     * @param g Target GUIService sink.
     */
    GUIThrottleListener(GUIService* g)
        : gui(g),
        lastTime(std::chrono::steady_clock::now())
    {}

    /**
     * Called when PricingService publishes a new price.
     * Only forward to GUIService when 300ms have elapsed since last forward.
     */
    virtual void ProcessAdd(Price<Bond>& p) override
    {
        // Use steady_clock to avoid issues if system time changes.
        auto now = std::chrono::steady_clock::now();
        auto diff = std::chrono::duration_cast<std::chrono::milliseconds>(now - lastTime);

        // 300ms throttle + stop after GUI wrote enough lines.
        if (diff.count() >= 300 && !gui->Finished())
        {
            gui->OnMessage(p);
            lastTime = now;
        }
    }

    virtual void ProcessRemove(Price<Bond>& /*p*/) override {}
    virtual void ProcessUpdate(Price<Bond>& /*p*/) override {}

private:
    GUIService* gui;

    // Timestamp of last forwarded update
    std::chrono::time_point<std::chrono::steady_clock> lastTime;
};

#endif
