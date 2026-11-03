/* Ordinary resurrection response validation, released under the GNU GPL v2 or later. */
#ifndef PRESENCE_RESURRECTION_POLICY_H
#define PRESENCE_RESURRECTION_POLICY_H

#include <cstdint>
#include <string_view>

namespace Presence
{
enum class ResurrectionChoice : std::uint8_t
{
    Decline = 0,
    Accept = 1,
    Invalid = 255
};

inline ResurrectionChoice ParseResurrectionChoice(std::string_view value)
{
    if (value == "accept")
        return ResurrectionChoice::Accept;
    if (value == "decline")
        return ResurrectionChoice::Decline;
    return ResurrectionChoice::Invalid;
}

inline bool ResurrectionOfferCurrent(std::uint64_t caster, std::uint64_t revision,
    std::uint64_t currentCaster, std::uint64_t currentRevision, bool requested, bool alive, bool consumed)
{
    return caster && revision && caster == currentCaster && revision == currentRevision
        && requested && !alive && !consumed;
}

inline bool ResurrectionRecoveryComplete(bool wasDead, bool alive, bool ghost, bool teleporting)
{
    return wasDead && alive && !ghost && !teleporting;
}
}

#endif
