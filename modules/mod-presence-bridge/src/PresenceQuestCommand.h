#ifndef PRESENCE_QUEST_COMMAND_H
#define PRESENCE_QUEST_COMMAND_H

#include <cstdint>
#include <limits>
#include <string_view>

namespace Presence
{
struct QuestAbandonInput
{
    bool addressed = false;
    std::uint32_t quest = 0;
};

constexpr bool CommandSpace(char value)
{
    return value == ' ' || value == '\t';
}

constexpr std::string_view TrimCommand(std::string_view text)
{
    while (!text.empty() && CommandSpace(text.front()))
        text.remove_prefix(1);
    while (!text.empty() && CommandSpace(text.back()))
        text.remove_suffix(1);
    return text;
}

constexpr bool CommandEqual(std::string_view first, std::string_view second)
{
    if (first.size() != second.size())
        return false;
    for (std::size_t index = 0; index < first.size(); ++index)
    {
        char left = first[index] >= 'A' && first[index] <= 'Z' ? char(first[index] + ('a' - 'A')) : first[index];
        char right = second[index] >= 'A' && second[index] <= 'Z' ? char(second[index] + ('a' - 'A')) : second[index];
        if (left != right)
            return false;
    }
    return true;
}

constexpr std::string_view CommandWord(std::string_view& text)
{
    text = TrimCommand(text);
    std::size_t end = 0;
    while (end < text.size() && !CommandSpace(text[end]))
        ++end;
    std::string_view word = text.substr(0, end);
    text.remove_prefix(end);
    return word;
}

constexpr std::uint32_t CommandQuestId(std::string_view text)
{
    if (text.empty())
        return 0;
    std::uint32_t quest = 0;
    for (char value : text)
    {
        if (value < '0' || value > '9'
            || quest > (std::numeric_limits<std::uint32_t>::max() - (value - '0')) / 10)
            return 0;
        quest = quest * 10 + (value - '0');
    }
    return quest;
}

constexpr QuestAbandonInput ParseQuestAbandonCommand(std::string_view text, std::string_view character)
{
    if (!CommandEqual(CommandWord(text), character) || !CommandEqual(CommandWord(text), "drop")
        || !CommandEqual(CommandWord(text), "quest"))
        return {};
    QuestAbandonInput result{true, 0};
    text = TrimCommand(text);
    if (!text.starts_with("|"))
    {
        result.quest = CommandQuestId(text);
        return result;
    }
    if (text.starts_with("|c"))
    {
        if (text.size() < 12 || !text.ends_with("|r"))
            return result;
        for (char value : text.substr(2, 8))
            if (!((value >= '0' && value <= '9') || (value >= 'a' && value <= 'f')
                || (value >= 'A' && value <= 'F')))
                return result;
        text.remove_prefix(10);
        text.remove_suffix(2);
    }
    if (!text.starts_with("|Hquest:") || !text.ends_with("]|h"))
        return result;
    text.remove_prefix(8);
    std::size_t separator = text.find(':');
    std::size_t label = text.find("|h[");
    if (separator == std::string_view::npos || label == std::string_view::npos || separator >= label)
        return result;
    std::string_view level = text.substr(separator + 1, label - separator - 1);
    if (level.starts_with("-"))
        level.remove_prefix(1);
    if (level.empty() || level.find_first_not_of("0123456789") != std::string_view::npos
        || text.substr(label + 3, text.size() - label - 6).find('|') != std::string_view::npos)
        return result;
    result.quest = CommandQuestId(text.substr(0, separator));
    return result;
}
}

#endif
