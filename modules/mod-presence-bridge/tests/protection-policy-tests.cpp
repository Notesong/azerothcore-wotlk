#include "../src/PresenceProtectionPolicy.h"
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
    using Presence::StickyProtection;
    StickyProtection state;
    Check(!state.ObserveExistingMoon(0, 100), "missing protector cannot bind");
    Check(!state.ObserveExistingMoon(10, 0), "missing moon cannot bind");
    Check(state.ObserveExistingMoon(10, 100), "existing moon binds");
    Check(state.protector == 10 && state.target == 100, "binding retains exact identities");
    bool retained = true;
    for (unsigned tick = 0; tick < 10000; ++tick)
        retained = retained && !state.ObserveExistingMoon(0, 0) && state.target == 100;
    Check(retained, "ten thousand absent observations cannot release");
    Check(!state.ObserveExistingMoon(10, 200) && state.target == 100, "new observed icon cannot replace binding");
    Check(!state.ObserveExistingMoon(11, 200) && state.protector == 10, "other observer cannot replace protector");
    Check(!state.ExplicitMarker(0, 4, 0, 0) && state.target == 100, "automatic empty setter cannot clear");
    Check(!state.ExplicitClear(11, 100) && state.target == 100, "other human cannot clear");
    Check(!state.ExplicitMarker(11, 4, 200, 200) && state.target == 100, "other human cannot move binding");
    Check(!state.ExplicitMarker(10, 4, 100, 200) && state.target == 100, "unverified moon state cannot release");
    Check(!state.ExplicitMarker(10, 255, 100, 0) && state.target == 100, "invalid icon cannot release");

    StickyProtection reloaded{state.protector, state.target, state.ignoredMoon};
    Check(!reloaded.ObserveExistingMoon(0, 0) && reloaded.target == 100, "serialized binding survives empty world");
    Check(reloaded.ExplicitClear(10, 100), "protector may explicitly clear");
    Check(reloaded.target == 0 && reloaded.ignoredMoon == 100, "clear tombstones unchanged marker");
    Check(!reloaded.ObserveExistingMoon(10, 100) && !reloaded.target, "unchanged marker cannot rebind after clear");
    Check(reloaded.ExplicitMarker(10, 4, 100, 100) && reloaded.target == 100 && !reloaded.ignoredMoon,
          "protector explicit reapply restores binding");
    Check(reloaded.ExplicitMarker(10, 4, 200, 200) && reloaded.target == 200, "protector may explicitly move moon");
    Check(!reloaded.ExplicitMarker(11, 2, 200, 0) && reloaded.target == 200, "other human cannot remove via other icon");
    Check(reloaded.ExplicitMarker(10, 2, 200, 0) && !reloaded.target, "protector may explicitly replace moon with another icon");
    Check(reloaded.ObserveExistingMoon(10, 300) && reloaded.target == 300, "new marker can bind after explicit removal");
    Check(reloaded.ExplicitMarker(10, 4, 0, 0) && !reloaded.target, "protector may explicitly remove moon");
    Check(!reloaded.ExplicitClear(10, 0), "repeated clear has no new effect");
    std::cout << checks << " protection-policy checks passed.\n";
}
