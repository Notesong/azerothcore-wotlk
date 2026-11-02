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
    std::cout << checks << " item-use receipt checks passed\n";
}
