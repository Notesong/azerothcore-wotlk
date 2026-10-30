#ifndef PRESENCE_PROTECTION_POLICY_H
#define PRESENCE_PROTECTION_POLICY_H

#include <cstdint>

namespace Presence
{
// No health, visibility, death, group membership or clock input can release an established binding.
struct StickyProtection
{
    std::uint64_t protector = 0;
    std::uint64_t target = 0;
    std::uint64_t ignoredMoon = 0;

    bool ObserveExistingMoon(std::uint64_t human, std::uint64_t moon)
    {
        if (target || !human || !moon || moon == ignoredMoon)
            return false;
        protector = human;
        target = moon;
        ignoredMoon = 0;
        return true;
    }

    bool ExplicitMarker(std::uint64_t human, std::uint8_t icon, std::uint64_t marked,
        std::uint64_t currentMoon)
    {
        if (!human || icon >= 8 || (protector && human != protector))
            return false;
        if (icon == 4 && marked == currentMoon)
        {
            if (target == marked && (!marked || protector == human))
                return false;
            protector = human;
            target = marked;
            ignoredMoon = 0;
            return true;
        }
        if (icon != 4 && target && marked == target && currentMoon != target)
        {
            ignoredMoon = 0;
            target = 0;
            return true;
        }
        return false;
    }

    bool ExplicitClear(std::uint64_t human, std::uint64_t currentMoon)
    {
        if (!target || !human || human != protector)
            return false;
        ignoredMoon = currentMoon;
        target = 0;
        return true;
    }
};
}

#endif
