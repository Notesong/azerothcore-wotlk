#include "../src/PresenceCommercePolicy.h"
#include <cstdlib>
#include <iostream>

unsigned checks = 0;
void Check(bool condition)
{
    ++checks;
    if (!condition)
        std::exit(1);
}

int main()
{
    std::uint32_t units = 999;
    Check(Presence::CommercePurchaseUnits(5, 3, units) && units == 15);
    Check(Presence::CommercePurchaseUnits(1, 255, units) && units == 255);
    Check(!Presence::CommercePurchaseUnits(1, 256, units) && units == 0);
    Check(!Presence::CommercePurchaseUnits(1, 0, units) && units == 0);
    Check(!Presence::CommercePurchaseUnits(0, 1, units) && units == 0);
    Check(Presence::CommercePurchaseUnits(0xFFFFFFFF, 1, units) && units == 0xFFFFFFFF);
    Check(!Presence::CommercePurchaseUnits(0xFFFFFFFF, 2, units) && units == 0);
    Check(Presence::CommercePurchaseUnits(20, 200, units) && units == 4000);
    Check(!Presence::CommercePurchaseUnits(0x80000000, 2, units) && units == 0);
    std::cout << checks << " commerce quantity checks passed.\n";
}
