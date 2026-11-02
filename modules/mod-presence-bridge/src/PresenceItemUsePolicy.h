/*
 * Local item-use eligibility and receipt identity policy.
 * Released under the GNU GPL v2, or (at your option) any later version.
 */
#ifndef PRESENCE_ITEM_USE_POLICY_H
#define PRESENCE_ITEM_USE_POLICY_H

#include <cstdint>
#include <string_view>

namespace Presence
{
struct SelfDrinkEffectFacts
{
    bool applyAura;
    bool manaRegen;
    bool periodicDummy;
    bool selfOnly;
    bool otherEffects;
    std::int32_t basePoints;
    std::int32_t dieSides;
    std::int32_t powerType;
    std::uint32_t amplitude;
};

constexpr bool ReviewedSelfDrink(std::string_view script, std::uint32_t scriptCount, bool foodDrink, bool genericFamily,
    SelfDrinkEffectFacts const& regen, SelfDrinkEffectFacts const& timing, bool extraEffects)
{
    // The stock arena-drink script only transfers effect 1's amount to effect
    // 0's mana regeneration, immediately outside arenas and with a ramp inside.
    // Permit that exact pair, including its initially zero (-1 + 1) regen.
    return script == "spell_gen_arena_drink" && scriptCount == 1 && foodDrink && genericFamily && !extraEffects
        && regen.applyAura && regen.manaRegen && !regen.periodicDummy && regen.selfOnly && !regen.otherEffects
        && regen.basePoints == -1 && regen.dieSides == 1 && regen.powerType == 0 && !regen.amplitude
        && timing.applyAura && !timing.manaRegen && timing.periodicDummy && timing.selfOnly && !timing.otherEffects
        && timing.basePoints >= 0 && timing.dieSides == 1 && timing.powerType == 0 && timing.amplitude == 2200;
}

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
