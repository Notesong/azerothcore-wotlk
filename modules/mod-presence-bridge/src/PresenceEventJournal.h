#ifndef PRESENCE_EVENT_JOURNAL_H
#define PRESENCE_EVENT_JOURNAL_H

#include <algorithm>
#include <charconv>
#include <cstdint>
#include <deque>
#include <limits>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace Presence
{
struct JournalCursor
{
    std::string epoch;
    std::uint64_t sequence;
};

inline bool ValidJournalEpoch(std::string_view epoch)
{
    return epoch.size() == 32 && std::all_of(epoch.begin(), epoch.end(), [](char value)
    {
        return (value >= '0' && value <= '9') || (value >= 'a' && value <= 'f');
    });
}

inline std::optional<JournalCursor> ParseJournalCursor(std::string_view cursor)
{
    if (cursor.size() < 34 || cursor[32] != ':' || !ValidJournalEpoch(cursor.substr(0, 32)))
        return std::nullopt;
    std::string_view number = cursor.substr(33);
    if (number.size() > 1 && number.front() == '0')
        return std::nullopt;
    if (!std::all_of(number.begin(), number.end(), [](char value) { return value >= '0' && value <= '9'; }))
        return std::nullopt;
    std::uint64_t sequence = 0;
    auto result = std::from_chars(number.data(), number.data() + number.size(), sequence);
    if (result.ec != std::errc{} || result.ptr != number.data() + number.size())
        return std::nullopt;
    return JournalCursor{std::string(cursor.substr(0, 32)), sequence};
}

struct JournalActorState
{
    bool alive;
    bool combat;
    std::uint64_t health;
};

struct JournalActorDelta
{
    bool combatStarted;
    bool combatEnded;
    bool died;
    bool resurrected;
    std::uint64_t healthLoss;
};

inline JournalActorDelta CompareJournalActorStates(JournalActorState before, JournalActorState after)
{
    return {!before.combat && after.combat, before.combat && !after.combat,
        before.alive && !after.alive, !before.alive && after.alive,
        before.health > after.health ? before.health - after.health : 0};
}

template<class Value, std::size_t Capacity = 512>
class JournalBuffer
{
public:
    static_assert(Capacity > 0);
    struct Entry
    {
        std::uint64_t sequence;
        Value value;
    };
    struct Page
    {
        std::vector<Entry> events;
        std::uint64_t cursor;
        std::uint64_t lost = 0;
        bool hasMore = false;
        bool gap = false;
    };

    std::optional<std::uint64_t> Push(Value value)
    {
        if (_sequence == std::numeric_limits<std::uint64_t>::max())
            return std::nullopt;
        _events.push_back(Entry{++_sequence, std::move(value)});
        if (_events.size() > Capacity)
        {
            _events.pop_front();
            ++_dropped;
        }
        return _sequence;
    }

    std::uint64_t Oldest() const { return _events.empty() ? 0 : _events.front().sequence; }
    std::uint64_t Newest() const { return _sequence; }
    std::uint64_t Dropped() const { return _dropped; }

    template<class Predicate>
    Page Read(std::uint64_t since, std::size_t maximum, Predicate matches) const
    {
        Page result{{}, since};
        maximum = std::clamp<std::size_t>(maximum, 1, Capacity);
        if (!_events.empty() && since < Oldest() - 1)
        {
            result.gap = true;
            result.lost = Oldest() - 1 - since;
            result.cursor = Oldest() - 1;
        }
        for (Entry const& entry : _events)
            if (entry.sequence > result.cursor)
            {
                result.cursor = entry.sequence;
                if (matches(entry.value))
                    result.events.push_back(entry);
                if (result.events.size() >= maximum)
                    break;
            }
        result.hasMore = result.cursor < Newest();
        return result;
    }

private:
    std::deque<Entry> _events;
    std::uint64_t _sequence = 0;
    std::uint64_t _dropped = 0;
};
}
#endif
