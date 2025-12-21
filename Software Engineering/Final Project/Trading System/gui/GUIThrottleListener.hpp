// ====================== GUIThrottleListener.hpp ======================
#ifndef GUI_THROTTLE_LISTENER_HPP
#define GUI_THROTTLE_LISTENER_HPP

#include "GUIService.hpp"
#include <chrono>

class GUIThrottleListener : public ServiceListener< Price<Bond> >
{
public:
    GUIThrottleListener(GUIService* g)
        : gui(g),
        lastTime(std::chrono::steady_clock::now()) {}

    virtual void ProcessAdd(Price<Bond>& p) override {
        auto now = std::chrono::steady_clock::now();
        auto diff = std::chrono::duration_cast<std::chrono::milliseconds>(now - lastTime);

        if (diff.count() >= 300 && !gui->Finished()) {
            gui->OnMessage(p);
            lastTime = now;
        }
    }

    virtual void ProcessRemove(Price<Bond>& p) override {}
    virtual void ProcessUpdate(Price<Bond>& p) override {}

private:
    GUIService* gui;
    std::chrono::time_point<std::chrono::steady_clock> lastTime;
};

#endif
