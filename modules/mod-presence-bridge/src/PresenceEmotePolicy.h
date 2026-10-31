/*
 * Local ordinary-emote protocol policy, released under the GNU GPL v2 or later.
 */
#ifndef PRESENCE_EMOTE_POLICY_H
#define PRESENCE_EMOTE_POLICY_H

#include <algorithm>
#include <array>
#include <cstdint>
#include <deque>
#include <optional>
#include <span>
#include <string>
#include <string_view>

namespace Presence
{
inline bool IsOwnedEmoteObserver(bool headless, bool sessionOwned, std::uint64_t player, std::uint64_t sessionPlayer)
{
    return headless && sessionOwned && player && player == sessionPlayer;
}

// IDs are the installed core's SharedDefines.h TextEmotes values. The bridge
// also checks these bindings against the actual enum and EmotesText DBC.
enum class OrdinaryTextEmote : std::uint32_t
{
    Bow = 17,
    Cheer = 21,
    Clap = 24,
    Dance = 34,
    Hug = 56,
    Kiss = 58,
    Laugh = 60,
    Nod = 67,
    Point = 72,
    Salute = 78,
    Shrug = 83,
    Thank = 97,
    Wave = 101,
    Slap = 130,
    Smile = 163
};

struct OrdinaryEmoteName
{
    std::string_view Name;
    OrdinaryTextEmote Id;
};

inline constexpr std::array<OrdinaryEmoteName, 15> OrdinaryEmotes{{
    {"bow", OrdinaryTextEmote::Bow}, {"cheer", OrdinaryTextEmote::Cheer},
    {"clap", OrdinaryTextEmote::Clap}, {"dance", OrdinaryTextEmote::Dance}, {"hug", OrdinaryTextEmote::Hug},
    {"kiss", OrdinaryTextEmote::Kiss}, {"laugh", OrdinaryTextEmote::Laugh}, {"nod", OrdinaryTextEmote::Nod},
    {"point", OrdinaryTextEmote::Point}, {"salute", OrdinaryTextEmote::Salute}, {"shrug", OrdinaryTextEmote::Shrug},
    {"slap", OrdinaryTextEmote::Slap}, {"smile", OrdinaryTextEmote::Smile}, {"thank", OrdinaryTextEmote::Thank},
    {"wave", OrdinaryTextEmote::Wave}}};

inline std::string_view OrdinaryEmoteNameById(std::uint32_t id)
{
    for (auto const& emote : OrdinaryEmotes)
        if (std::uint32_t(emote.Id) == id)
            return emote.Name;
    return {};
}

inline std::uint32_t OrdinaryEmoteIdByName(std::string_view input)
{
    if (input.starts_with('/'))
        input.remove_prefix(1);
    if (input.empty() || input.size() > 16)
        return 0;
    std::string name(input);
    for (char& value : name)
        if (value >= 'A' && value <= 'Z')
            value = char(value - 'A' + 'a');
    for (auto const& emote : OrdinaryEmotes)
        if (name == emote.Name)
            return std::uint32_t(emote.Id);
    return 0;
}

struct TextEmoteFrame
{
    std::uint64_t Sender = 0;
    std::uint32_t Emote = 0;
    std::uint32_t Variant = 0;
    std::string TargetName;
};

inline std::optional<TextEmoteFrame> DecodeTextEmote(std::span<std::uint8_t const> bytes)
{
    if (bytes.size() < 21)
        return {};
    auto read = [&bytes](std::size_t offset, std::size_t count)
    {
        std::uint64_t value = 0;
        for (std::size_t index = 0; index < count; ++index)
            value |= std::uint64_t(bytes[offset + index]) << (index * 8);
        return value;
    };
    TextEmoteFrame frame;
    frame.Sender = read(0, 8);
    frame.Emote = std::uint32_t(read(8, 4));
    frame.Variant = std::uint32_t(read(12, 4));
    std::uint32_t const length = std::uint32_t(read(16, 4));
    if (!frame.Sender || !frame.Emote || length > 255)
        return {};
    std::size_t const wireLength = length > 1 ? length : 0;
    if (bytes.size() != 21 + wireLength || bytes.back() != 0)
        return {};
    for (std::size_t index = 0; index < wireLength; ++index)
        if (!bytes[20 + index])
            return {};
    frame.TargetName.assign(reinterpret_cast<char const*>(bytes.data() + 20), wireLength);
    return frame;
}

struct TextEmoteCorrelation
{
    std::uint64_t Observer = 0;
    std::uint64_t Sender = 0;
    std::uint64_t Target = 0;
    std::uint32_t Emote = 0;
    std::uint32_t Variant = 0;
    std::uint64_t AtMilliseconds = 0;
    bool HasTarget = false;
    bool TargetKnown = false;
    bool TargetIsPlayer = false;
};

class TextEmoteCorrelations
{
public:
    static constexpr std::size_t Limit = 64;
    static constexpr std::uint64_t LifetimeMilliseconds = 1000;

    void Remember(TextEmoteCorrelation record, std::uint64_t now)
    {
        Prune(now);
        if (!record.Observer || !record.Sender || !record.Emote)
            return;
        Forget(record.Observer, record.Sender);
        record.AtMilliseconds = now;
        if (!record.TargetKnown)
            record.Target = 0;
        Records.push_back(record);
        while (Records.size() > Limit)
            Records.pop_front();
    }

    std::optional<TextEmoteCorrelation> Take(std::uint64_t observer, TextEmoteFrame const& frame, std::uint64_t now)
    {
        Prune(now);
        auto found = std::find_if(Records.begin(), Records.end(), [observer, &frame](auto const& row)
        {
            return row.Observer == observer && row.Sender == frame.Sender;
        });
        if (found == Records.end())
            return {};
        auto record = *found;
        Records.erase(found);
        if (record.Emote != frame.Emote || record.Variant != frame.Variant
            || record.HasTarget != !frame.TargetName.empty())
            return {};
        return record;
    }

    void Forget(std::uint64_t observer, std::uint64_t sender = 0)
    {
        std::erase_if(Records, [observer, sender](auto const& row)
        {
            return row.Observer == observer && (!sender || row.Sender == sender);
        });
    }

    void ForgetCharacter(std::uint64_t identity)
    {
        std::erase_if(Records, [identity](auto const& row)
        {
            return row.Observer == identity || row.Sender == identity || row.Target == identity;
        });
    }

    void ForgetSender(std::uint64_t sender)
    {
        std::erase_if(Records, [sender](auto const& row) { return row.Sender == sender; });
    }

    std::size_t Size() const { return Records.size(); }

private:
    void Prune(std::uint64_t now)
    {
        std::erase_if(Records, [now](auto const& row)
        {
            return row.AtMilliseconds > now || now - row.AtMilliseconds > LifetimeMilliseconds;
        });
    }

    std::deque<TextEmoteCorrelation> Records;
};
}

#endif
