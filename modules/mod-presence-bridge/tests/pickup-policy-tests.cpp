#include "../src/PresencePickupPolicy.h"
#include <array>
#include <cstdlib>
#include <iostream>

namespace
{
unsigned Checks = 0;

void Check(bool condition)
{
    ++Checks;
    if (!condition)
        std::exit(1);
}
}

int main()
{
    using namespace Presence;
    Check(PickupCastMatches(3001, 4001, 7, 3001, 4001, 7));
    Check(!PickupCastMatches(3001, 4001, 7, 3002, 4001, 7));
    Check(!PickupCastMatches(3001, 4001, 7, 3001, 4002, 7));
    Check(!PickupCastMatches(3001, 4001, 7, 3001, 4001, 8));
    Check(!PickupCastMatches(0, 4001, 7, 0, 4001, 7));
    Check(!PickupCastMatches(3001, 0, 7, 3001, 0, 7));
    Check(!PickupCastMatches(3001, 4001, 0, 3001, 4001, 0));

    Check(PickupReceiptMatches("original", 3001, true, "original", 3001, 3001));
    Check(!PickupReceiptMatches("original", 3001, false, "original", 3001, 3001));
    Check(!PickupReceiptMatches("original", 3001, true, "earlier", 3001, 3001));
    Check(!PickupReceiptMatches("original", 3001, true, "original", 3002, 3001));
    Check(!PickupReceiptMatches("original", 3001, true, "original", 3001, 3002));
    Check(!PickupReceiptMatches("", 3001, true, "", 3001, 3001));
    Check(!PickupReceiptMatches("original", 0, true, "original", 0, 0));

    // Opening spans map ticks without a new cast. Its source-bound normal
    // receipt is the sole path to storage after the original cast finishes.
    for (unsigned tick = 0; tick < 20; ++tick)
        Check(ChestPickupProgress(true, true, false, false, true) == PickupProgress::Waiting);
    Check(ChestPickupProgress(true, true, false, true, false) == PickupProgress::Store);
    Check(ChestPickupProgress(true, true, false, false, false) == PickupProgress::Failed);
    Check(ChestPickupProgress(false, true, false, true, false) == PickupProgress::Failed);
    Check(ChestPickupProgress(true, false, false, true, false) == PickupProgress::Failed);
    Check(ChestPickupProgress(true, true, true, true, true) == PickupProgress::Failed);
    Check(ChestPickupProgress(true, true, true, false, true) == PickupProgress::Failed);
    // A stale or different source window cannot rescue an interrupted cast.
    bool stale = PickupReceiptMatches("new", 3001, true, "old", 3001, 3001);
    Check(ChestPickupProgress(true, true, false, stale, false) == PickupProgress::Failed);

    for (auto action : {"stop", "move_to", "follow", "attack", "cast", "loot", "interact"})
        Check(SupersedesPickup(action));
    for (auto action : {"target", "say", "emote", "inspect_item", "observe", "action_result", ""})
        Check(!SupersedesPickup(action));

    Check(StoredPickupCount(0, 1) == 1);
    Check(StoredPickupCount(3, 5) == 2);
    Check(StoredPickupCount(0, 0) == 0); // Full bag or quest-ineligible: no invented receipt.
    Check(StoredPickupCount(1, 1) == 0); // Unique quest item already owned, no duplicate claimed.
    Check(StoredPickupCount(2, 1) == 0);
    Check(StoredPickupCount(0xFFFFFFFE, 0xFFFFFFFF) == 1);
    std::cout << Checks << " pickup source/cast/receipt/interrupt/storage checks passed.\n";
}
