/*
 * Local character catch-up XP policy, released under the GNU GPL v2 or later.
 */
#ifndef PRESENCE_CATCHUP_XP_POLICY_H
#define PRESENCE_CATCHUP_XP_POLICY_H

#include <cmath>
#include <cstdint>
#include <limits>

namespace Presence
{
enum class CatchupXpSource
{
    Other,
    Kill,
    Quest,
    QuestDungeonFinder,
    Explore,
    Battleground
};

struct CatchupXpContext
{
    bool Enabled = false;
    std::uint64_t ReceiverGuid = 0;
    std::uint32_t ReceiverAccount = 0;
    std::uint64_t ConfiguredReceiverGuid = 0;
    std::uint32_t ConfiguredReceiverAccount = 0;
    std::uint64_t LeadGuid = 0;
    std::uint8_t ReceiverLevel = 0;
    std::uint32_t ReceiverXp = 0;
    std::uint8_t LeadLevel = 0;
    double Multiplier = 2.0;
    CatchupXpSource Source = CatchupXpSource::Other;
};

inline bool IsCatchupXpSource(CatchupXpSource source)
{
    switch (source)
    {
        case CatchupXpSource::Kill:
        case CatchupXpSource::Quest:
        case CatchupXpSource::QuestDungeonFinder:
        case CatchupXpSource::Explore:
        case CatchupXpSource::Battleground:
            return true;
        default:
            return false;
    }
}

inline std::uint32_t CatchupXpAmount(std::uint32_t amount, CatchupXpContext const& context)
{
    if (!amount || !context.Enabled || !IsCatchupXpSource(context.Source)
        || !context.ReceiverGuid || context.ReceiverGuid != context.ConfiguredReceiverGuid
        || !context.ReceiverAccount || context.ReceiverAccount != context.ConfiguredReceiverAccount
        || !context.LeadGuid || context.LeadGuid == context.ReceiverGuid
        || !context.ReceiverLevel || !context.LeadLevel || context.ReceiverLevel >= context.LeadLevel
        || !std::isfinite(context.Multiplier) || context.Multiplier <= 1.0)
        return amount;

    double const scaled = double(amount) * context.Multiplier;
    // Preserve the normal award if scaling cannot be represented. Saturating to
    // UINT32_MAX would risk wrapping GiveXP's later current/rested/RaF addition.
    if (!std::isfinite(scaled) || scaled > std::numeric_limits<std::uint32_t>::max())
        return amount;

    std::uint32_t const boosted = std::uint32_t(scaled);
    // GiveXP may apply favored-area XP (1.05), then RaF (3) or rested (at
    // most 2), before adding current XP in uint32. Four is a conservative
    // bound for those existing combinations, not a change to their rules.
    if (std::uint64_t(context.ReceiverXp) + std::uint64_t(boosted) * 4
        > std::numeric_limits<std::uint32_t>::max())
        return amount;

    return boosted;
}
}

#endif
