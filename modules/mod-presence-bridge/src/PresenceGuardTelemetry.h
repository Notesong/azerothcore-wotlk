/*
 * Local guard telemetry bounds, released under the GNU GPL v2 or later.
 */
#ifndef PRESENCE_GUARD_TELEMETRY_H
#define PRESENCE_GUARD_TELEMETRY_H

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <map>
#include <string>

namespace Presence
{
class GuardTelemetryWindow
{
public:
    using Clock = std::chrono::steady_clock;

    bool Record(std::string const& key, Clock::time_point now, bool synchronous)
    {
        ++_total;
        // Every proposed action needs its own receipt, even inside a passive-effect cooldown.
        if (synchronous)
            return true;
        auto found = _next.find(key);
        if (found != _next.end() && now < found->second)
        {
            ++_suppressed;
            return false;
        }
        if (found == _next.end() && _next.size() >= 128)
            _next.erase(_next.begin());
        _next[key] = now + std::chrono::seconds(2);
        return true;
    }

    std::uint64_t Total() const { return _total; }
    std::uint64_t Suppressed() const { return _suppressed; }
    std::size_t Keys() const { return _next.size(); }

private:
    std::map<std::string, Clock::time_point> _next;
    std::uint64_t _total = 0;
    std::uint64_t _suppressed = 0;
};
}

#endif
