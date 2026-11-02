#include "../src/PresenceItemUsePolicy.h"
#include <cassert>
#include <initializer_list>
#include <iostream>

int main()
{
    using namespace Presence;
    unsigned checks = 0;
    auto check = [&checks](bool condition)
    {
        assert(condition);
        ++checks;
    };
    // A nearby unit's packet, another item stack, another spell and a prior
    // cast of this same spell cannot complete the owned item request.
    for (bool hasOwner : {false, true})
        for (bool hasItem : {false, true})
        {
            check(ItemUseCastMatches(11, 22, 439, 3, 11, 22, 439, 3, hasOwner, hasItem));
            check(!ItemUseCastMatches(11, 22, 439, 3, 11, 22, 430, 3, hasOwner, hasItem));
            check(!ItemUseCastMatches(11, 22, 439, 3, 11, 22, 439, 2, hasOwner, hasItem));
            check(!ItemUseCastMatches(0, 22, 439, 3, 11, 22, 439, 3, hasOwner, hasItem));
            check(!ItemUseCastMatches(11, 0, 439, 3, 11, 22, 439, 3, hasOwner, hasItem));
            check(!ItemUseCastMatches(11, 22, 0, 3, 11, 22, 439, 3, hasOwner, hasItem));
            check(!ItemUseCastMatches(11, 22, 439, 0, 11, 22, 439, 3, hasOwner, hasItem));
            check(ItemUseCastMatches(11, 22, 439, 3, 12, 22, 439, 3, hasOwner, hasItem) == !hasOwner);
            check(ItemUseCastMatches(11, 22, 439, 3, 11, 23, 439, 3, hasOwner, hasItem) == !hasItem);
        }
    check(ItemUseReceiptProgress(false, false, false) == ItemUseProgress::Waiting);
    check(ItemUseReceiptProgress(false, false, true) == ItemUseProgress::Unknown);
    check(ItemUseReceiptProgress(false, true, false) == ItemUseProgress::Rejected);
    check(ItemUseReceiptProgress(false, true, true) == ItemUseProgress::Rejected);
    check(ItemUseReceiptProgress(true, false, false) == ItemUseProgress::Emitted);
    check(ItemUseReceiptProgress(true, false, true) == ItemUseProgress::Emitted);
    check(ItemUseReceiptProgress(true, true, false) == ItemUseProgress::Emitted);
    check(ItemUseReceiptProgress(true, true, true) == ItemUseProgress::Emitted);

    // Actual Spell.dbc 430: zero initial mana regen (-1 + 1), followed by
    // the stock script's self-only timing dummy (41 + 1 mana regeneration).
    SelfDrinkEffectFacts regen{true, true, false, true, false, -1, 1, 0, 0};
    SelfDrinkEffectFacts timing{true, false, true, true, false, 41, 1, 0, 2200};
    auto drink = [](SelfDrinkEffectFacts const& first, SelfDrinkEffectFacts const& second)
    {
        return ReviewedSelfDrink("spell_gen_arena_drink", 1, true, true, first, second, false);
    };
    check(drink(regen, timing));
    check(!ReviewedSelfDrink("", 1, true, true, regen, timing, false));
    check(!ReviewedSelfDrink("other_script", 1, true, true, regen, timing, false));
    check(!ReviewedSelfDrink("spell_gen_arena_drink", 0, true, true, regen, timing, false));
    check(!ReviewedSelfDrink("spell_gen_arena_drink", 2, true, true, regen, timing, false));
    check(!ReviewedSelfDrink("spell_gen_arena_drink", 1, false, true, regen, timing, false));
    check(!ReviewedSelfDrink("spell_gen_arena_drink", 1, true, false, regen, timing, false));
    check(!ReviewedSelfDrink("spell_gen_arena_drink", 1, true, true, regen, timing, true));
    for (auto member : {&SelfDrinkEffectFacts::applyAura, &SelfDrinkEffectFacts::manaRegen,
        &SelfDrinkEffectFacts::periodicDummy, &SelfDrinkEffectFacts::selfOnly, &SelfDrinkEffectFacts::otherEffects})
    {
        auto changedRegen = regen;
        changedRegen.*member = !(regen.*member);
        check(!drink(changedRegen, timing));
        auto changedTiming = timing;
        changedTiming.*member = !(timing.*member);
        check(!drink(regen, changedTiming));
    }
    for (int value : {-2, 0, 1})
    {
        auto changed = regen;
        changed.basePoints = value;
        check(!drink(changed, timing));
    }
    for (int value : {0, 2})
    {
        auto changedRegen = regen;
        changedRegen.dieSides = value;
        check(!drink(changedRegen, timing));
        auto changedTiming = timing;
        changedTiming.dieSides = value;
        check(!drink(regen, changedTiming));
    }
    auto changedRegen = regen;
    changedRegen.powerType = 1;
    check(!drink(changedRegen, timing));
    changedRegen = regen;
    changedRegen.amplitude = 2200;
    check(!drink(changedRegen, timing));
    auto changedTiming = timing;
    changedTiming.powerType = 1;
    check(!drink(regen, changedTiming));
    changedTiming = timing;
    changedTiming.amplitude = 2000;
    check(!drink(regen, changedTiming));
    changedTiming = timing;
    changedTiming.basePoints = -1;
    check(!drink(regen, changedTiming));
    changedTiming = timing;
    changedTiming.basePoints = 248; // Spell.dbc 1133 shares the same reviewed family.
    check(drink(regen, changedTiming));
    std::cout << checks << " item-use policy checks passed\n";
}
