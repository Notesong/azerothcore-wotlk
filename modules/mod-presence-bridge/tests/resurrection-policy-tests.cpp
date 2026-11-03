#include "../src/PresenceResurrectionPolicy.h"
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
    Check(ParseResurrectionChoice("accept") == ResurrectionChoice::Accept, "normal accept byte");
    Check(ParseResurrectionChoice("decline") == ResurrectionChoice::Decline, "normal decline byte");
    Check(ParseResurrectionChoice("revive") == ResurrectionChoice::Invalid, "no forced restoration choice");
    Check(ParseResurrectionChoice("Accept") == ResurrectionChoice::Invalid, "exact closed choice");
    Check(ResurrectionOfferCurrent(10, 2, 10, 2, true, false, false), "actual dead player offer is current");
    Check(!ResurrectionOfferCurrent(0, 2, 0, 2, true, false, false), "missing caster cannot bind");
    Check(!ResurrectionOfferCurrent(10, 0, 10, 0, true, false, false), "unobserved generation cannot bind");
    Check(!ResurrectionOfferCurrent(10, 2, 11, 2, true, false, false), "replacement caster invalidates nonce");
    Check(!ResurrectionOfferCurrent(10, 2, 10, 4, true, false, false), "same caster clear/reoffer invalidates nonce");
    Check(!ResurrectionOfferCurrent(10, 2, 10, 2, false, false, false), "cleared request cannot be accepted");
    Check(!ResurrectionOfferCurrent(10, 2, 10, 2, true, true, false), "alive state removes offer applicability");
    Check(!ResurrectionOfferCurrent(10, 2, 10, 2, true, false, true), "dispatched nonce cannot be submitted twice");
    Check(!ResurrectionRecoveryComplete(false, true, false, false), "existing life is not this recovery");
    Check(!ResurrectionRecoveryComplete(true, false, true, false), "a ghost is not recovered");
    Check(!ResurrectionRecoveryComplete(true, true, true, false), "alive flag alone cannot prove recovery");
    Check(!ResurrectionRecoveryComplete(true, true, false, true), "near/far transfer acceptance is not settled life");
    Check(ResurrectionRecoveryComplete(true, true, false, false),
        "normal ack and actual living state complete recovery");
    std::cout << "17 resurrection policy checks passed\n";
}
