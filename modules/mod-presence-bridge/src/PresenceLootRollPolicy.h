/* Local ordinary loot-roll validation, released under the GNU GPL v2 or later. */
#ifndef PRESENCE_LOOT_ROLL_POLICY_H
#define PRESENCE_LOOT_ROLL_POLICY_H

#include <cstdint>
#include <string_view>

namespace Presence
{
enum class LootRollChoice : std::uint8_t
{
    Pass = 0,
    Need = 1,
    Greed = 2,
    Invalid = 255
};

inline LootRollChoice ParseLootRollChoice(std::string_view choice)
{
    if (choice == "pass")
        return LootRollChoice::Pass;
    if (choice == "need")
        return LootRollChoice::Need;
    if (choice == "greed")
        return LootRollChoice::Greed;
    return LootRollChoice::Invalid;
}

inline LootRollChoice LootRollAcknowledgement(std::uint8_t number, std::uint8_t type)
{
    // This core advertises a chosen Need as number=0,type=0. Actual dice
    // results use numbers 1..100 and must never acknowledge a new vote.
    if (number == 0 && type == 0)
        return LootRollChoice::Need;
    if (number == 128 && type == 0)
        return LootRollChoice::Pass;
    if (number == 128 && type == 2)
        return LootRollChoice::Greed;
    return LootRollChoice::Invalid;
}

struct LootRollAffixes
{
    std::int32_t property;
    std::uint32_t suffix;
};

inline LootRollAffixes DecodeLootRollResultAffixes(bool won, std::uint32_t first, std::uint32_t second)
{
    // The ordinary ALL_PASSED and WON packets have opposite affix orders.
    return won ? LootRollAffixes{static_cast<std::int32_t>(second), first}
        : LootRollAffixes{static_cast<std::int32_t>(first), second};
}

inline bool LootRollNeedEligible(bool needBeforeGreed, bool lfgGroup, bool sourceAvailable,
    bool currentAllowed, bool advertised, bool advertisedAllowed)
{
    if (!needBeforeGreed || !lfgGroup)
        return true;
    if (sourceAvailable)
        return currentAllowed;
    // A lost/unloaded source does not revoke the player's actual advertised
    // Need permission. Without either source or packet facts, it is unknown.
    return advertised && advertisedAllowed;
}

inline bool LootRollIdentityMatches(std::string_view supplied, std::string_view observed,
    std::uint64_t observedGroup, std::uint64_t currentGroup, std::uint64_t observedItem,
    std::uint64_t currentItem, std::uint32_t observedSlot, std::uint32_t currentSlot,
    std::uint32_t observedEntry, std::uint32_t currentEntry)
{
    return !supplied.empty() && supplied == observed && observedGroup && observedGroup == currentGroup
        && observedItem && observedItem == currentItem && observedSlot == currentSlot
        && observedEntry && observedEntry == currentEntry;
}

inline char const* LootRollVoteError(LootRollChoice choice, bool identityMatches, bool member,
    bool pending, bool expired, std::uint8_t mask, bool canNeed)
{
    if (choice == LootRollChoice::Invalid)
        return "invalid_roll_choice";
    if (!identityMatches)
        return "stale_loot_roll";
    if (!member)
        return "roll_not_eligible";
    if (!pending)
        return "roll_already_voted";
    if (expired)
        return "roll_expired";
    auto value = static_cast<std::uint8_t>(choice);
    if (!(mask & (1u << value)) || (choice == LootRollChoice::Need && !canNeed))
        return "roll_choice_unavailable";
    return nullptr;
}
}

#endif
