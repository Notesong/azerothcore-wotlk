/* Verified quest lifecycle facts, released under the GNU GPL v2 or later. */
#ifndef PRESENCE_QUEST_LIFECYCLE_POLICY_H
#define PRESENCE_QUEST_LIFECYCLE_POLICY_H

#include <cstdint>
#include <set>
#include <utility>

namespace Presence
{
inline bool QuestAcceptanceVerified(bool inLog, bool active, bool normalStatus)
{
    return inLog && active && normalStatus;
}

inline bool QuestRewardVerified(bool inLog, bool active, bool rewarded)
{
    return !inLog && !active && rewarded;
}

class QuestLifecycleEpisodes
{
public:
    void Baseline(std::set<std::uint32_t> held)
    {
        _held = std::move(held);
        _initialized = true;
    }

    bool Initialized() const { return _initialized; }

    bool Accepted(std::uint32_t quest, bool verified)
    {
        return _initialized && quest && verified && _held.insert(quest).second;
    }

    void Released(std::uint32_t quest) { _held.erase(quest); }

private:
    bool _initialized = false;
    std::set<std::uint32_t> _held;
};
}

#endif
