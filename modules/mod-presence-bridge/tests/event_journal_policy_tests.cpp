#include "../src/PresenceEventJournal.h"
#include <cassert>
#include <string>

int main()
{
    std::string epoch(32, 'a');
    assert(Presence::ValidJournalEpoch(epoch));
    assert(!Presence::ValidJournalEpoch(std::string(32, 'A')));
    assert(!Presence::ValidJournalEpoch(std::string(31, 'a')));
    auto maximum = Presence::ParseJournalCursor(epoch + ":18446744073709551615");
    assert(maximum && maximum->sequence == UINT64_MAX);
    assert(!Presence::ParseJournalCursor(epoch + ":18446744073709551616"));
    assert(!Presence::ParseJournalCursor(epoch + ":00"));
    assert(!Presence::ParseJournalCursor(epoch + ":01"));
    assert(!Presence::ParseJournalCursor(epoch + ":-1"));
    assert(!Presence::ParseJournalCursor(epoch + ":+1"));
    assert(!Presence::ParseJournalCursor(epoch + ":"));
    assert(!Presence::ParseJournalCursor(epoch + ":1:2"));
    // Shared self/visible-party state transitions: flags are facts, not attack intent.
    auto started = Presence::CompareJournalActorStates({true, false, 100}, {true, true, 90});
    assert(started.combatStarted && !started.combatEnded && started.healthLoss == 10);
    assert(!started.died && !started.resurrected);
    auto stopped = Presence::CompareJournalActorStates({true, true, 90}, {true, false, 95});
    assert(stopped.combatEnded && !stopped.combatStarted && stopped.healthLoss == 0);
    auto death = Presence::CompareJournalActorStates({true, true, 20}, {false, false, 0});
    assert(death.died && death.combatEnded && death.healthLoss == 20);
    auto revived = Presence::CompareJournalActorStates({false, false, 0}, {true, false, 10});
    assert(revived.resurrected && !revived.died && revived.healthLoss == 0);
    Presence::JournalBuffer<int, 3> journal;
    auto empty = journal.Read(0, 3, [](int) { return true; });
    assert(empty.events.empty() && !empty.gap && !empty.hasMore && empty.cursor == 0);
    for (int value = 1; value <= 5; ++value)
        assert(journal.Push(value).value() == std::uint64_t(value));
    assert(journal.Oldest() == 3 && journal.Newest() == 5 && journal.Dropped() == 2);
    auto lost = journal.Read(0, 3, [](int) { return true; });
    assert(lost.gap && lost.lost == 2 && lost.events.size() == 3 && lost.cursor == 5 && !lost.hasMore);
    auto filtered = journal.Read(2, 1, [](int value) { return value % 2 == 0; });
    assert(filtered.events.size() == 1 && filtered.events.front().value == 4);
    assert(filtered.cursor == 4 && filtered.hasMore && !filtered.gap);
    auto tail = journal.Read(filtered.cursor, 1, [](int value) { return value % 2 == 0; });
    assert(tail.events.empty() && tail.cursor == 5 && !tail.hasMore);
    auto noLoss = journal.Read(2, 512, [](int) { return true; });
    assert(!noLoss.gap && noLoss.lost == 0 && noLoss.events.size() == 3);
    auto baseline = journal.Read(journal.Newest(), 512, [](int) { return true; });
    assert(baseline.events.empty() && baseline.cursor == 5);
}
