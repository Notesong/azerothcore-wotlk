#include "../src/PresenceCatchupXpPolicy.h"
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

Presence::CatchupXpContext Eligible()
{
    Presence::CatchupXpContext context;
    context.Enabled = true;
    context.ReceiverGuid = context.ConfiguredReceiverGuid = 1001;
    context.ReceiverAccount = context.ConfiguredReceiverAccount = 77;
    context.LeadGuid = 2001;
    context.ReceiverLevel = 4;
    context.LeadLevel = 5; // A cached offline lead level works without an online Player object.
    context.Source = Presence::CatchupXpSource::Kill;
    return context;
}
}

int main()
{
    using Presence::CatchupXpAmount;
    using Presence::CatchupXpSource;
    auto context = Eligible();
    Check(CatchupXpAmount(101, context) == 202);
    Check(CatchupXpAmount(0, context) == 0);
    Check(CatchupXpAmount(101, {}) == 101);
    context.Enabled = false;
    Check(CatchupXpAmount(101, context) == 101);

    for (auto source : std::array{CatchupXpSource::Kill, CatchupXpSource::Quest,
        CatchupXpSource::QuestDungeonFinder, CatchupXpSource::Explore, CatchupXpSource::Battleground})
    {
        context = Eligible();
        context.Source = source;
        Check(CatchupXpAmount(101, context) == 202);
    }
    context.Source = CatchupXpSource::Other;
    Check(CatchupXpAmount(101, context) == 101);
    context.Source = static_cast<CatchupXpSource>(999);
    Check(CatchupXpAmount(101, context) == 101);

    context = Eligible();
    context.ReceiverGuid = 1002; // An ordinary bot on the same account remains unchanged.
    Check(CatchupXpAmount(101, context) == 101);
    context = Eligible();
    context.ReceiverAccount = 78;
    Check(CatchupXpAmount(101, context) == 101);
    context = Eligible();
    context.ConfiguredReceiverGuid = 0;
    Check(CatchupXpAmount(101, context) == 101);
    context = Eligible();
    context.ConfiguredReceiverAccount = 0;
    Check(CatchupXpAmount(101, context) == 101);
    context = Eligible();
    context.LeadGuid = 0;
    Check(CatchupXpAmount(101, context) == 101);
    context.LeadGuid = context.ReceiverGuid;
    Check(CatchupXpAmount(101, context) == 101);

    for (auto levels : std::array<std::array<std::uint8_t, 2>, 4>{{{0, 5}, {4, 0}, {5, 5}, {6, 5}}})
    {
        context = Eligible();
        context.ReceiverLevel = levels[0];
        context.LeadLevel = levels[1];
        Check(CatchupXpAmount(101, context) == 101);
    }
    context = Eligible();
    context.ReceiverLevel = 5; // Reached parity: the next award is normal.
    Check(CatchupXpAmount(101, context) == 101);
    context.LeadLevel = 6; // The cache observes the lead's later level-up: catch-up resumes.
    Check(CatchupXpAmount(101, context) == 202);

    for (double rate : std::array{0.0, -2.0, 1.0, std::numeric_limits<double>::infinity(),
        std::numeric_limits<double>::quiet_NaN()})
    {
        context = Eligible();
        context.Multiplier = rate;
        Check(CatchupXpAmount(101, context) == 101);
    }
    context = Eligible();
    context.Multiplier = 1.5;
    Check(CatchupXpAmount(101, context) == 151);
    context.Multiplier = std::numeric_limits<double>::max();
    Check(CatchupXpAmount(101, context) == 101);
    context = Eligible();
    Check(CatchupXpAmount(0xFFFFFFFF, context) == 0xFFFFFFFF);
    Check(CatchupXpAmount(0x80000000, context) == 0x80000000);
    Check(CatchupXpAmount(0x7FFFFFFF, context) == 0x7FFFFFFF);
    Check(CatchupXpAmount(0x1FFFFFFF, context) == 0x3FFFFFFE);
    Check(CatchupXpAmount(0x20000000, context) == 0x20000000);
    context.ReceiverXp = 7;
    Check(CatchupXpAmount(0x1FFFFFFF, context) == 0x3FFFFFFE);
    context.ReceiverXp = 8;
    Check(CatchupXpAmount(0x1FFFFFFF, context) == 0x1FFFFFFF);
    context.ReceiverXp = 0xFFFFFFFF - 800;
    Check(CatchupXpAmount(100, context) == 200);
    context.ReceiverXp = 0xFFFFFFFF - 799;
    Check(CatchupXpAmount(100, context) == 100);
    std::cout << Checks << " catch-up XP policy checks passed.\n";
}
