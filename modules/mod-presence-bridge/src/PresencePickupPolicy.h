/* Local pickup execution checks, released under the GNU GPL v2 or later. */
#ifndef PRESENCE_PICKUP_POLICY_H
#define PRESENCE_PICKUP_POLICY_H

#include <cstdint>
#include <string_view>

namespace Presence
{
inline bool PickupCastMatches(std::uint64_t target, std::uint32_t spell, std::uint8_t count,
    std::uint64_t observedTarget, std::uint32_t observedSpell, std::uint8_t observedCount)
{
    return target && spell && count && target == observedTarget && spell == observedSpell && count == observedCount;
}

inline bool PickupReceiptMatches(std::string_view request, std::uint64_t target, bool valid,
    std::string_view receiptRequest, std::uint64_t receiptTarget, std::uint64_t currentLoot)
{
    return !request.empty() && target && valid && request == receiptRequest
        && target == receiptTarget && target == currentLoot;
}

inline std::uint32_t StoredPickupCount(std::uint32_t before, std::uint32_t after)
{
    return after > before ? after - before : 0;
}

enum class PickupProgress
{
    Waiting,
    Store,
    Failed
};

inline PickupProgress ChestPickupProgress(bool alive, bool sourceUsable, bool expired,
    bool matchingReceipt, bool matchingCast)
{
    if (!alive || !sourceUsable || expired)
        return PickupProgress::Failed;
    if (matchingReceipt)
        return PickupProgress::Store;
    return matchingCast ? PickupProgress::Waiting : PickupProgress::Failed;
}

inline bool SupersedesPickup(std::string_view action)
{
    return action == "stop" || action == "move_to" || action == "follow"
        || action == "attack" || action == "cast" || action == "loot" || action == "interact";
}
}

#endif
