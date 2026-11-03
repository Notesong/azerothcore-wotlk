#include "../src/PresenceTaxiPolicy.h"
#include <cstdlib>
#include <iostream>

namespace
{
void Check(bool condition, char const* message)
{
    if (!condition)
    {
        std::cerr << message << '\n';
        std::exit(1);
    }
}
}

int main()
{
    using namespace Presence;
    std::vector<TaxiEdge> edges{{1, 2, 101}, {2, 3, 101}, {1, 3, 400}, {1, 4, 1}, {4, 3, 1},
        {3, 5, 1}, {2, 1, 0}, {1, 6, 0}};
    auto routes = KnownTaxiRoutes(1, {1, 2, 3, 5, 6, 7}, edges, 0.95f);
    Check(routes.at(3).nodes == std::vector<std::uint32_t>({1, 2, 3}), "unknown shortcut must be excluded");
    Check(routes.at(3).price == 192, "quote must include each normal leg's rounded reputation fare");
    Check(routes.at(5).nodes.size() == 4, "known connected multi-hop destination must be exposed");
    Check(!routes.contains(1) && !routes.contains(4) && !routes.contains(7), "no self/unknown/disconnected route");
    Check(routes.at(6).price == 0, "ordinary free routes remain usable");
    Check(KnownTaxiRoutes(4, {1, 2, 3}, edges, 1.0f).empty(), "unknown source cannot expose routes");
    Check(!TaxiLegPrice(1, -1) && !TaxiLegPrice(UINT32_MAX, 1), "invalid or overflowing fares fail closed");
    Check(!TaxiSplineAckReady(true, false, false, true, 3, 2), "do not acknowledge unfinished spline");
    Check(!TaxiSplineAckReady(true, true, true, true, 3, 2), "world transfer must finish before next ack");
    Check(!TaxiSplineAckReady(true, false, true, true, 3, 3), "do not acknowledge a spline twice");
    Check(TaxiSplineAckReady(true, false, true, true, 4, 3), "completed next native spline permits one ack");
    Check(!TaxiLandedAtDestination(false, false, false, true, true, false, true, 0), "acceptance is not arrival");
    Check(!TaxiLandedAtDestination(true, true, false, true, true, false, true, 0), "flight flag bars arrival");
    Check(!TaxiLandedAtDestination(true, false, true, true, true, false, true, 0), "transfer bars arrival");
    Check(!TaxiLandedAtDestination(true, false, false, true, true, false, false, 0), "wrong map bars arrival");
    Check(!TaxiLandedAtDestination(true, false, false, false, true, false, true, 0), "death is not landing");
    Check(!TaxiLandedAtDestination(true, false, false, true, false, false, true, 0), "unconsumed route bars arrival");
    Check(!TaxiLandedAtDestination(true, false, false, true, true, true, true, 0), "active generator bars arrival");
    Check(!TaxiLandedAtDestination(true, false, false, true, true, false, true, 50), "wrong endpoint bars arrival");
    Check(TaxiLandedAtDestination(true, false, false, true, true, false, true, 3), "actual endpoint permits arrival");
    std::cout << "Taxi policy checks passed\n";
}
