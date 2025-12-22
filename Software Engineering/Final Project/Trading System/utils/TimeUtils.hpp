/**
 * TimeUtils.hpp
 * Timestamp helper utilities.
 *
 * @author Hao Wang
 */
#ifndef TIME_UTILS_HPP
#define TIME_UTILS_HPP

#include <chrono>
#include <ctime>
#include <string>
#include <iomanip>
#include <sstream>

 /**
  * Get a local timestamp string with millisecond precision.
  *
  * Format: YYYY-MM-DD HH:MM:SS.mmm
  */
inline std::string NowTimestampMS()
{
    using namespace std::chrono;

    const auto now = system_clock::now();
    const auto ms = duration_cast<milliseconds>(now.time_since_epoch()) % 1000;

    const time_t t = system_clock::to_time_t(now);
    tm buf{};

#ifdef _WIN32
    // Thread-safe local time conversion on Windows
    localtime_s(&buf, &t);
#else
    // Thread-safe local time conversion on POSIX
    localtime_r(&t, &buf);
#endif

    std::stringstream ss;
    ss << std::put_time(&buf, "%Y-%m-%d %H:%M:%S");
    ss << "." << std::setfill('0') << std::setw(3) << ms.count();

    return ss.str();
}

#endif
