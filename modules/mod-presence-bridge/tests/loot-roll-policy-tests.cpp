#include "../src/PresenceLootRollPolicy.h"
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
    check(ParseLootRollChoice("need") == LootRollChoice::Need);
    check(ParseLootRollChoice("greed") == LootRollChoice::Greed);
    check(ParseLootRollChoice("pass") == LootRollChoice::Pass);
    for (char const* invalid : {"", "Need", "disenchant", "1", "greed\n", " roll"})
        check(ParseLootRollChoice(invalid) == LootRollChoice::Invalid);
    check(LootRollIdentityMatches("round-a", "round-a", 11, 11, 22, 22, 0, 0, 33, 33));
    check(!LootRollIdentityMatches("round-a", "round-b", 11, 11, 22, 22, 0, 0, 33, 33));
    check(!LootRollIdentityMatches("", "", 11, 11, 22, 22, 0, 0, 33, 33));
    check(!LootRollIdentityMatches("round-a", "round-a", 0, 0, 22, 22, 0, 0, 33, 33));
    check(!LootRollIdentityMatches("round-a", "round-a", 11, 12, 22, 22, 0, 0, 33, 33));
    check(!LootRollIdentityMatches("round-a", "round-a", 11, 11, 0, 0, 0, 0, 33, 33));
    check(!LootRollIdentityMatches("round-a", "round-a", 11, 11, 22, 23, 0, 0, 33, 33));
    check(!LootRollIdentityMatches("round-a", "round-a", 11, 11, 22, 22, 0, 1, 33, 33));
    check(!LootRollIdentityMatches("round-a", "round-a", 11, 11, 22, 22, 0, 0, 33, 34));
    check(!LootRollIdentityMatches("round-a", "round-a", 11, 11, 22, 22, 0, 0, 0, 0));

    for (auto choice : {LootRollChoice::Pass, LootRollChoice::Need, LootRollChoice::Greed})
    {
        check(!LootRollVoteError(choice, true, true, true, false, 7, true));
        check(LootRollVoteError(choice, false, true, true, false, 7, true) != nullptr);
        check(LootRollVoteError(choice, true, false, true, false, 7, true) != nullptr);
        check(LootRollVoteError(choice, true, true, false, false, 7, true) != nullptr);
        check(LootRollVoteError(choice, true, true, true, true, 7, true) != nullptr);
        check(LootRollVoteError(choice, true, true, true, false, 0, true) != nullptr);
    }
    // A legal Group Loot Need is separate from item usefulness. NBG may remove
    // Need even with the underlying roll mask set, without denying Greed/Pass.
    check(LootRollVoteError(LootRollChoice::Need, true, true, true, false, 7, false) != nullptr);
    check(!LootRollVoteError(LootRollChoice::Greed, true, true, true, false, 7, false));
    check(!LootRollVoteError(LootRollChoice::Pass, true, true, true, false, 7, false));
    check(LootRollVoteError(LootRollChoice::Need, true, true, true, false, 5, true) != nullptr);
    check(!LootRollVoteError(LootRollChoice::Greed, true, true, true, false, 5, true));
    check(!LootRollVoteError(LootRollChoice::Pass, true, true, true, false, 1, false));
    check(LootRollVoteError(LootRollChoice::Greed, true, true, true, false, 1, false) != nullptr);
    check(LootRollVoteError(LootRollChoice::Invalid, true, true, true, false, 7, true) != nullptr);

    check(LootRollNeedEligible(false, false, false, false, false, false));
    check(LootRollNeedEligible(false, true, false, false, false, false));
    check(LootRollNeedEligible(true, false, false, false, false, false));
    check(LootRollNeedEligible(true, false, true, false, false, false));
    check(LootRollNeedEligible(true, true, true, true, false, false));
    check(!LootRollNeedEligible(true, true, true, false, true, true));
    check(LootRollNeedEligible(true, true, false, false, true, true));
    check(!LootRollNeedEligible(true, true, false, true, false, true));
    check(!LootRollNeedEligible(true, true, false, true, true, false));
    check(!LootRollNeedEligible(true, true, false, true, false, false));

    check(LootRollAcknowledgement(0, 0) == LootRollChoice::Need);
    check(LootRollAcknowledgement(128, 0) == LootRollChoice::Pass);
    check(LootRollAcknowledgement(128, 2) == LootRollChoice::Greed);
    check(LootRollAcknowledgement(128, 3) == LootRollChoice::Invalid);
    auto won = DecodeLootRollResultAffixes(true, 9876, 0xFFFFFFFE);
    check(won.property == -2 && won.suffix == 9876);
    auto allPassed = DecodeLootRollResultAffixes(false, 0xFFFFFFFE, 9876);
    check(allPassed.property == -2 && allPassed.suffix == 9876);
    auto plain = DecodeLootRollResultAffixes(false, 0, 0);
    check(plain.property == 0 && plain.suffix == 0);
    for (std::uint8_t number = 1; number <= 100; ++number)
        for (std::uint8_t type = 0; type <= 3; ++type)
            check(LootRollAcknowledgement(number, type) == LootRollChoice::Invalid);
    std::cout << checks << " loot-roll policy checks passed\n";
}
