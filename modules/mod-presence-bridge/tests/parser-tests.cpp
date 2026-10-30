#include "../src/PresenceQuestCommand.h"
#include <iostream>
#include <string_view>

struct Case
{
    std::string_view text;
    bool addressed;
    std::uint32_t quest;
};

int main()
{
    Case const cases[] = {
        {"Vesper drop quest 8330", true, 8330},
        {"vEsPeR DrOp QuEsT 8330", true, 8330},
        {"  Vesper\tdrop  quest\t8330  ", true, 8330},
        {"Vesper drop quest 0008330", true, 8330},
        {"Vesper drop quest 4294967295", true, 4294967295U},
        {"Vesper drop quest 4294967296", true, 0},
        {"Vesper drop quest 999999999999999999999999999999999", true, 0},
        {"Vesper drop quest 0", true, 0},
        {"Vesper drop quest -8330", true, 0},
        {"Vesper drop quest +8330", true, 0},
        {"Vesper drop quest 8.330", true, 0},
        {"Vesper drop quest 8e3", true, 0},
        {"Vesper drop quest 8330junk", true, 0},
        {"Vesper drop quest 8330 8346", true, 0},
        {"Vesper drop quest 8330\n", true, 0},
        {"Vesper drop quest 8330\r", true, 0},
        {"Vesper drop quest", true, 0},
        {"Vesper drop quest   ", true, 0},
        {"Vesper drop quest all", true, 0},
        {"Vesper drop quest Thirst Unending", true, 0},
        {"Vesper2 drop quest 8330", false, 0},
        {"drop quest 8330", false, 0},
        {"Please Vesper drop quest 8330", false, 0},
        {"Vesper drop quests 8330", false, 0},
        {"Vesper stop quest 8330", false, 0},
        {"Vesperdrop quest 8330", false, 0},
        {"", false, 0},
        {"Vesper drop quest |Hquest:8330:1|h[Quest name]|h", true, 8330},
        {"Vesper drop quest |Hquest:8330:-1|h[Quest name]|h", true, 8330},
        {"Vesper drop quest |cffffff00|Hquest:8330:1|h[Quest name]|h|r", true, 8330},
        {"Vesper drop quest |cABCDEF12|Hquest:8330:1|h[Different display title]|h|r", true, 8330},
        {"Vesper drop quest |cggffff00|Hquest:8330:1|h[Quest name]|h|r", true, 0},
        {"Vesper drop quest |cffffff00|Hquest:8330:1|h[Quest name]|h", true, 0},
        {"Vesper drop quest |Hquest:8330:1|h[Quest name]|h|r", true, 0},
        {"Vesper drop quest |Hitem:8330:1|h[Quest name]|h", true, 0},
        {"Vesper drop quest |Hquest:4294967296:1|h[Quest name]|h", true, 0},
        {"Vesper drop quest |Hquest:0:1|h[Quest name]|h", true, 0},
        {"Vesper drop quest |Hquest:-8330:1|h[Quest name]|h", true, 0},
        {"Vesper drop quest |Hquest:8330:|h[Quest name]|h", true, 0},
        {"Vesper drop quest |Hquest:8330:-|h[Quest name]|h", true, 0},
        {"Vesper drop quest |Hquest:8330:+1|h[Quest name]|h", true, 0},
        {"Vesper drop quest |Hquest:8330:1:2|h[Quest name]|h", true, 0},
        {"Vesper drop quest |Hquest:8330:1|h[Quest name]|h extra", true, 0},
        {"Vesper drop quest |Hquest:8330:1|h[One]|h |Hquest:8346:1|h[Two]|h", true, 0},
        {"Vesper drop quest |Hquest:8330:1|h[One |Hquest:8346:1|h[Two]|h]|h", true, 0},
        {"Vesper drop quest |Hquest:8330:1|h[Quest name]", true, 0},
        {"Vesper drop quest |Hquest:8330:1|h", true, 0},
        {"Vesper drop quest |Hquest:8330", true, 0},
        {"Vesper drop quest |", true, 0}
    };
    unsigned count = 0;
    for (Case const& sample : cases)
    {
        ++count;
        auto result = Presence::ParseQuestAbandonCommand(sample.text, "Vesper");
        if (result.addressed != sample.addressed || result.quest != sample.quest)
        {
            std::cerr << "Case " << count << " failed: " << sample.text << '\n';
            return 1;
        }
    }
    std::cout << count << " quest-command parser cases passed.\n";
}
