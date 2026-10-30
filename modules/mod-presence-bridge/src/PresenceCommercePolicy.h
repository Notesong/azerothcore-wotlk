/*
 * Local commerce protocol bounds, released under the GNU GPL v2 or later.
 */
#ifndef PRESENCE_COMMERCE_POLICY_H
#define PRESENCE_COMMERCE_POLICY_H

#include <cstdint>
#include <limits>

namespace Presence
{
inline bool CommercePurchaseUnits(std::uint32_t bundleSize, std::uint32_t bundles, std::uint32_t& units)
{
    units = 0;
    if (!bundleSize || !bundles || bundles > 255)
        return false;
    std::uint64_t total = std::uint64_t(bundleSize) * bundles;
    if (total > std::numeric_limits<std::uint32_t>::max())
        return false;
    units = std::uint32_t(total);
    return true;
}
}

#endif
