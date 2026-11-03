#include "../src/PresenceQuestLifecyclePolicy.h"
#include <cstdlib>
#include <iostream>

namespace
{
void Check(bool value, char const* label)
{
    if (!value)
    {
        std::cerr << label << '\n';
        std::exit(1);
    }
}
}

int main()
{
    using namespace Presence;
    Check(!QuestAcceptanceVerified(false, false, true), "a full-log failed AddQuest hook is not acceptance");
    Check(!QuestAcceptanceVerified(true, false, true), "a slot alone is not an active quest");
    Check(!QuestAcceptanceVerified(true, true, false), "failed/invalid status is not acceptance");
    Check(QuestAcceptanceVerified(true, true, true), "normal newly held quest verifies acceptance");
    Check(!QuestRewardVerified(true, false, true), "a rewarded history bit with a held repeatable is not turn-in");
    Check(!QuestRewardVerified(false, true, true), "active status bars turn-in confirmation");
    Check(!QuestRewardVerified(false, false, false), "abandonment is never a reward");
    Check(QuestRewardVerified(false, false, true), "post-RewardQuest proof confirms turn-in");
    QuestLifecycleEpisodes episodes;
    Check(!episodes.Accepted(10, true), "uninitialized login state cannot backfill a notice");
    episodes.Baseline({10});
    Check(!episodes.Accepted(10, true), "an already held baseline quest is not a fresh acceptance");
    Check(!episodes.Accepted(11, false), "a rejected acceptance cannot occupy a generation");
    Check(episodes.Accepted(11, true), "a later successful normal acceptance gets its own episode");
    Check(!episodes.Accepted(11, true), "duplicate acceptance hook cannot duplicate the episode");
    episodes.Released(11);
    Check(episodes.Accepted(11, true), "abandon then reaccept creates a fresh acceptance episode");
    episodes.Released(11);
    Check(episodes.Accepted(11, true), "reward then repeatable reaccept creates a fresh episode");
    Check(!episodes.Accepted(0, true), "missing identity cannot emit a lifecycle fact");
    episodes.Baseline({10, 11});
    Check(!episodes.Accepted(11, true), "reattach baseline cannot rediscover historical acceptance");
    episodes.Baseline({});
    Check(episodes.Accepted(11, true), "a subsequent new acceptance remains observable");
    std::cout << "18 quest lifecycle policy checks passed\n";
}
