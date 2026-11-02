/*
 * Local item-use receipt identity policy.
 * Released under the GNU GPL v2, or (at your option) any later version.
 */
#ifndef PRESENCE_ITEM_USE_POLICY_H
#define PRESENCE_ITEM_USE_POLICY_H

#include <cstdint>

namespace Presence
{
enum class ItemUseProgress
{
    Waiting,
    Emitted,
    Rejected,
    Unknown
};

constexpr bool ItemUseCastMatches(std::uint64_t owner, std::uint64_t item, std::uint32_t spell,
    std::uint8_t count, std::uint64_t observedOwner, std::uint64_t observedItem,
    std::uint32_t observedSpell, std::uint8_t observedCount, bool hasOwner, bool hasItem)
{
    return owner && item && spell && count && spell == observedSpell && count == observedCount
        && (!hasOwner || owner == observedOwner) && (!hasItem || item == observedItem);
}

constexpr ItemUseProgress ItemUseReceiptProgress(bool emitted, bool rejected, bool expired)
{
    // Emission proves an attempted cast, even if a later interruption occurs.
    // No diagnostic is never evidence that a consumable can be retried.
    return emitted ? ItemUseProgress::Emitted : rejected ? ItemUseProgress::Rejected
        : expired ? ItemUseProgress::Unknown : ItemUseProgress::Waiting;
}
}

#endif
