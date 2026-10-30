#include "../src/PresenceGuardTelemetry.h"
#include <cstdlib>
#include <iostream>

unsigned checks = 0;
void Check(bool value, char const* label)
{
    ++checks;
    if (!value)
    {
        std::cerr << "Failed: " << label << '\n';
        std::exit(1);
    }
}

int main()
{
    using Presence::GuardTelemetryWindow;
    using namespace std::chrono_literals;
    GuardTelemetryWindow telemetry;
    auto start = GuardTelemetryWindow::Clock::time_point{};
    Check(telemetry.Record("dot:owner:target:moon:spell", start, false), "first passive sample is visible");
    Check(!telemetry.Record("dot:owner:target:moon:spell", start + 1s, false), "repeated tick is suppressed");
    Check(!telemetry.Record("dot:owner:target:moon:spell", start + 1999ms, false), "cooldown covers subsecond boundary");
    Check(telemetry.Record("dot:owner:target:moon:spell", start + 2s, false), "cooldown ends at exact boundary");
    Check(telemetry.Record("dot:owner:new-target:moon:spell", start, false), "different victim remains visible");
    Check(telemetry.Record("dot:owner:target:new-moon:spell", start, false), "new protected binding remains visible");
    Check(telemetry.Record("heal:owner:target:moon:spell", start, false), "different intervention remains visible");
    Check(telemetry.Record("dot:owner:target:moon:spell", start + 1s, true), "action receipt bypasses passive cooldown");
    Check(telemetry.Record("dot:owner:target:moon:spell", start + 1s, true), "each action gets its own receipt");
    Check(telemetry.Total() == 9 && telemetry.Suppressed() == 2, "totals distinguish callbacks from emitted samples");

    GuardTelemetryWindow independent;
    Check(independent.Record("dot:owner:target:moon:spell", start + 1s, false), "another actor has independent samples");
    bool allSynchronous = true;
    for (unsigned index = 0; index < 1000; ++index)
        allSynchronous = independent.Record("sync:" + std::to_string(index), start, true) && allSynchronous;
    Check(allSynchronous, "one thousand synchronous samples remain individually visible");
    Check(independent.Keys() == 1, "synchronous actions cannot grow passive key cache");
    for (unsigned index = 0; index < 1000; ++index)
        telemetry.Record("passive:" + std::to_string(index), start, false);
    Check(telemetry.Keys() == 128, "passive key cache remains bounded");
    Check(telemetry.Total() == 1009 && telemetry.Suppressed() == 2, "bounded eviction preserves counters");
    std::cout << checks << " guard telemetry checks passed.\n";
}
