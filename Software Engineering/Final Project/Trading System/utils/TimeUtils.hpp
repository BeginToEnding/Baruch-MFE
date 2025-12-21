// ====================== TimeUtils.hpp ======================
#ifndef TIME_UTILS_HPP
#define TIME_UTILS_HPP

#include <chrono>
#include <string>
#include <iomanip>
#include <sstream>

inline string NowTimestampMS() {
    using namespace std::chrono;
    auto now = system_clock::now();
    auto ms = duration_cast<milliseconds>(now.time_since_epoch()) % 1000;

    time_t t = system_clock::to_time_t(now);
    tm buf;
#ifdef _WIN32
    localtime_s(&buf, &t);
#else
    localtime_r(&t, &buf);
#endif

    stringstream ss;
    ss << put_time(&buf, "%Y-%m-%d %H:%M:%S");
    ss << "." << setfill('0') << setw(3) << ms.count();

    return ss.str();
}

#endif
