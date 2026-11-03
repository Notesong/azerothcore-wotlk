/* Ordinary known-network taxi routing, released under the GNU GPL v2 or later. */
#ifndef PRESENCE_TAXI_POLICY_H
#define PRESENCE_TAXI_POLICY_H

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <vector>

namespace Presence
{
struct TaxiEdge
{
    std::uint32_t source;
    std::uint32_t destination;
    std::uint32_t basePrice;
};

struct TaxiRoute
{
    std::vector<std::uint32_t> nodes;
    std::uint32_t price = 0;

    bool operator==(TaxiRoute const&) const = default;
};

inline std::optional<std::uint32_t> TaxiLegPrice(std::uint32_t price, float discount)
{
    // Match FlightPathMovementGenerator's per-leg rounding, including free legs.
    float rounded = std::ceil(price * discount);
    if (!std::isfinite(rounded) || rounded < 0 || rounded >= float(std::numeric_limits<std::int32_t>::max()))
        return std::nullopt;
    return static_cast<std::uint32_t>(rounded);
}

inline std::map<std::uint32_t, TaxiRoute> KnownTaxiRoutes(std::uint32_t source,
    std::set<std::uint32_t> const& known, std::vector<TaxiEdge> const& edges, float discount)
{
    std::map<std::uint32_t, TaxiRoute> result;
    if (!known.contains(source))
        return result;
    result[source] = {{source}, 0};
    std::set<std::pair<std::uint32_t, std::uint32_t>> frontier{{0, source}};
    while (!frontier.empty())
    {
        auto [price, node] = *frontier.begin();
        frontier.erase(frontier.begin());
        if (result.at(node).price != price)
            continue;
        for (TaxiEdge const& edge : edges)
        {
            if (edge.source != node || !known.contains(edge.destination))
                continue;
            auto leg = TaxiLegPrice(edge.basePrice, discount);
            if (!leg || *leg > std::numeric_limits<std::int32_t>::max() - price)
                continue;
            std::uint32_t total = price + *leg;
            auto previous = result.find(edge.destination);
            if (previous != result.end() && previous->second.price <= total)
                continue;
            TaxiRoute route = result.at(node);
            route.nodes.push_back(edge.destination);
            route.price = total;
            result[edge.destination] = std::move(route);
            frontier.emplace(total, edge.destination);
        }
    }
    result.erase(source); // Remaining at the origin is not a paid destination.
    return result;
}

inline bool TaxiSplineAckReady(bool inFlight, bool teleporting, bool finalized,
    bool flightGenerator, std::uint32_t spline, std::uint32_t acknowledged)
{
    return inFlight && !teleporting && finalized && flightGenerator && spline != acknowledged;
}

inline bool TaxiLandedAtDestination(bool everInFlight, bool inFlight, bool teleporting,
    bool alive, bool pathEmpty, bool flightGenerator, bool destinationMap, float distance)
{
    return everInFlight && !inFlight && !teleporting && alive && pathEmpty && !flightGenerator
        && destinationMap && std::isfinite(distance) && distance <= 40.0f;
}
}

#endif
