#include "../src/PresenceEmotePolicy.h"
#include <cstdlib>
#include <iostream>
#include <set>
#include <vector>

namespace
{
unsigned Checks = 0;

void Check(bool condition)
{
    ++Checks;
    if (!condition)
        std::exit(1);
}

std::vector<std::uint8_t> Wire(std::uint64_t sender, std::uint32_t emote, std::uint32_t variant,
    std::string const& name)
{
    std::vector<std::uint8_t> data;
    auto append = [&data](std::uint64_t value, unsigned bytes)
    {
        for (unsigned index = 0; index < bytes; ++index)
            data.push_back(std::uint8_t(value >> (index * 8)));
    };
    append(sender, 8);
    append(emote, 4);
    append(variant, 4);
    append(name.size(), 4);
    data.insert(data.end(), name.begin(), name.end());
    data.push_back(0);
    return data;
}

Presence::TextEmoteCorrelation Record()
{
    Presence::TextEmoteCorrelation result;
    result.Observer = 1001;
    result.Sender = 2001;
    result.Target = 1001;
    result.Emote = std::uint32_t(Presence::OrdinaryTextEmote::Wave);
    result.Variant = 1;
    result.HasTarget = true;
    result.TargetKnown = true;
    result.TargetIsPlayer = true;
    return result;
}
}

int main()
{
    using namespace Presence;
    // Each advertised bridge character can observe emotes; Moon's protected
    // character name is not part of this independent session/GUID boundary.
    Check(IsOwnedEmoteObserver(true, true, 1001, 1001));
    Check(IsOwnedEmoteObserver(true, true, 2001, 2001));
    Check(!IsOwnedEmoteObserver(false, true, 1001, 1001));
    Check(!IsOwnedEmoteObserver(true, false, 1001, 1001));
    Check(!IsOwnedEmoteObserver(true, true, 0, 0));
    Check(!IsOwnedEmoteObserver(true, true, 1001, 2001));
    Check(!IsOwnedEmoteObserver(true, true, 1001, 0));
    std::set<std::uint32_t> ids;
    for (auto const& named : OrdinaryEmotes)
    {
        auto id = std::uint32_t(named.Id);
        Check(OrdinaryEmoteIdByName(named.Name) == id);
        Check(OrdinaryEmoteNameById(id) == named.Name);
        Check(OrdinaryEmoteIdByName("/" + std::string(named.Name)) == id);
        Check(ids.insert(id).second);
    }
    Check(ids.size() == 15);
    Check(OrdinaryEmoteIdByName("/WaVe") == std::uint32_t(OrdinaryTextEmote::Wave));
    for (auto name : {"", "/", "//wave", "wave ", " wave", "waving at you", "101", "unknown"})
        Check(OrdinaryEmoteIdByName(name) == 0);
    Check(OrdinaryEmoteNameById(999999).empty());

    auto bytes = Wire(2001, 101, 1, "Companion");
    auto frame = DecodeTextEmote(bytes);
    Check(frame && frame->Sender == 2001 && frame->Emote == 101 && frame->Variant == 1);
    Check(frame && frame->TargetName == "Companion");
    auto untargeted = DecodeTextEmote(Wire(2001, 101, 1, ""));
    Check(untargeted && untargeted->TargetName.empty());
    Check(DecodeTextEmote(Wire(2001, 999999, 0, "Companion"))->Emote == 999999);
    Check(DecodeTextEmote(Wire(2001, 101, 1, std::string(255, 'N')))->TargetName.size() == 255);
    Check(!DecodeTextEmote(Wire(2001, 101, 1, std::string(256, 'N'))));
    Check(!DecodeTextEmote(Wire(0, 101, 1, "Companion")));
    Check(!DecodeTextEmote(Wire(2001, 0, 1, "Companion")));
    for (std::size_t length = 0; length < bytes.size(); ++length)
        Check(!DecodeTextEmote(std::span<std::uint8_t const>(bytes.data(), length)));
    auto malformed = bytes;
    malformed.back() = 'N';
    Check(!DecodeTextEmote(malformed));
    malformed = bytes;
    malformed[21] = 0;
    Check(!DecodeTextEmote(malformed));
    malformed = bytes;
    malformed.push_back(0);
    Check(!DecodeTextEmote(malformed));

    TextEmoteCorrelations pending;
    // A packet name by itself never supplies a GUID, even if it matches self.
    Check(!pending.Take(1001, *frame, 100));
    pending.Remember(Record(), 100);
    auto match = pending.Take(1001, *frame, 100);
    Check(match && match->TargetKnown && match->Target == 1001 && match->TargetIsPlayer);
    Check(pending.Size() == 0 && !pending.Take(1001, *frame, 101));
    pending.Remember(Record(), 100);
    Check(!pending.Take(9999, *frame, 101));
    Check(pending.Take(1001, *frame, 102).has_value());
    pending.Remember(Record(), 100);
    auto different = *frame;
    different.Emote = std::uint32_t(OrdinaryTextEmote::Slap);
    Check(!pending.Take(1001, different, 101) && pending.Size() == 0);
    pending.Remember(Record(), 100);
    different = *frame;
    different.Variant = 2;
    Check(!pending.Take(1001, different, 101) && pending.Size() == 0);
    pending.Remember(Record(), 100);
    Check(!pending.Take(1001, *untargeted, 101));

    auto record = Record();
    record.HasTarget = false;
    record.Target = 0;
    record.TargetIsPlayer = false;
    pending.Remember(record, 100);
    match = pending.Take(1001, *untargeted, 101);
    Check(match && match->TargetKnown && !match->HasTarget && match->Target == 0);
    record = Record();
    record.TargetKnown = false;
    pending.Remember(record, 100);
    match = pending.Take(1001, *frame, 101);
    Check(match && match->HasTarget && !match->TargetKnown && match->Target == 0);
    pending.Remember(record, 100); // Nonzero hook target failed lookup; core emitted no name.
    Check(!pending.Take(1001, *untargeted, 101)); // Unknown, never authoritative target zero.

    pending.Remember(Record(), 100);
    Check(pending.Take(1001, *frame, 1100).has_value());
    pending.Remember(Record(), 100);
    Check(!pending.Take(1001, *frame, 1101));
    pending.Remember(Record(), 100);
    Check(!pending.Take(1001, *frame, 99));

    pending.Remember(Record(), 100);
    record = Record();
    record.Target = 3001; // Different entity with an identical displayed name.
    pending.Remember(record, 101);
    Check(pending.Size() == 1);
    match = pending.Take(1001, *frame, 102);
    Check(match && match->Target == 3001);
    for (unsigned index = 0; index < 65; ++index)
    {
        record = Record();
        record.Sender += index;
        pending.Remember(record, 100);
    }
    Check(pending.Size() == TextEmoteCorrelations::Limit);
    Check(!pending.Take(1001, *frame, 101));
    pending.ForgetCharacter(1001);
    Check(pending.Size() == 0);
    record = Record();
    record.Observer = 3001;
    pending.Remember(record, 100);
    pending.ForgetCharacter(2001);
    Check(pending.Size() == 0);
    pending.Remember(Record(), 100);
    pending.ForgetSender(2001); // A newer hook that fails visibility cannot reuse an old target.
    Check(pending.Size() == 0 && !pending.Take(1001, *frame, 101));
    record = Record();
    record.Observer = 0;
    pending.Remember(record, 100);
    Check(pending.Size() == 0);
    std::cout << Checks << " emote protocol/correlation checks passed.\n";
}
