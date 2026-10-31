/*
 * Local character catch-up XP hooks, released under the GNU GPL v2 or later.
 */
#include "CharacterCache.h"
#include "Config.h"
#include "Log.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "PlayerScript.h"
#include "PresenceCatchupXpPolicy.h"
#include "WorldScript.h"
#include "WorldSession.h"
#include <atomic>
#include <memory>
#include <string>

namespace Presence
{
namespace
{
struct CatchupXpSettings
{
    bool Enabled = false;
    std::string Character;
    std::string LeadCharacter;
    double Multiplier = 2.0;
};

std::atomic<std::shared_ptr<CatchupXpSettings const>> Settings{std::make_shared<CatchupXpSettings>()};

CatchupXpSource SourceFromCore(uint8 source)
{
    switch (source)
    {
        case XPSOURCE_KILL:
            return CatchupXpSource::Kill;
        case XPSOURCE_QUEST:
            return CatchupXpSource::Quest;
        case XPSOURCE_QUEST_DF:
            return CatchupXpSource::QuestDungeonFinder;
        case XPSOURCE_EXPLORE:
            return CatchupXpSource::Explore;
        case XPSOURCE_BATTLEGROUND:
            return CatchupXpSource::Battleground;
        default:
            return CatchupXpSource::Other;
    }
}

class CatchupXpWorld : public WorldScript
{
public:
    CatchupXpWorld() : WorldScript("presence_catchup_xp_world", {WORLDHOOK_ON_AFTER_CONFIG_LOAD}) { }

    void OnAfterConfigLoad(bool /*reload*/) override
    {
        auto settings = std::make_shared<CatchupXpSettings>();
        settings->Enabled = sConfigMgr->GetOption<bool>("PresenceBridge.CatchupXP.Enable", false);
        settings->Character = sConfigMgr->GetOption<std::string>("PresenceBridge.CatchupXP.Character", "Vesper");
        settings->LeadCharacter =
            sConfigMgr->GetOption<std::string>("PresenceBridge.CatchupXP.LeadCharacter", "Aurenne");
        settings->Multiplier = sConfigMgr->GetOption<float>("PresenceBridge.CatchupXP.Multiplier", 2.0f);
        bool const valid = normalizePlayerName(settings->Character)
            && normalizePlayerName(settings->LeadCharacter) && settings->Character != settings->LeadCharacter
            && std::isfinite(settings->Multiplier) && settings->Multiplier > 1.0;
        if (settings->Enabled && !valid)
        {
            LOG_ERROR("module.presence", "Catch-up XP disabled: invalid character pair or multiplier");
            settings->Enabled = false;
        }
        if (settings->Enabled)
            LOG_INFO("module.presence", "Catch-up XP enabled for {} below {}: multiplier {}",
                settings->Character, settings->LeadCharacter, settings->Multiplier);
        Settings.store(std::shared_ptr<CatchupXpSettings const>(settings), std::memory_order_release);
    }
};

class CatchupXpPlayer : public PlayerScript
{
public:
    CatchupXpPlayer() : PlayerScript("presence_catchup_xp_player", {PLAYERHOOK_ON_GIVE_EXP}) { }

    void OnPlayerGiveXP(Player* player, uint32& amount, Unit* /*victim*/, uint8 xpSource) override
    {
        auto const settings = Settings.load(std::memory_order_acquire);
        if (!player || !amount || !settings->Enabled || player->GetName() != settings->Character
            || !player->GetSession())
            return;

        // Cache lookup is local and current: SetLevel updates it immediately,
        // and startup loads offline character levels. No SQL or Player* is retained.
        auto const* receiver = sCharacterCache->GetCharacterCacheByName(settings->Character);
        auto const* lead = sCharacterCache->GetCharacterCacheByName(settings->LeadCharacter);
        if (!receiver || !lead)
            return;

        CatchupXpContext context;
        context.Enabled = settings->Enabled;
        context.ReceiverGuid = player->GetGUID().GetRawValue();
        context.ReceiverAccount = player->GetSession()->GetAccountId();
        context.ConfiguredReceiverGuid = receiver->Guid.GetRawValue();
        context.ConfiguredReceiverAccount = receiver->AccountId;
        context.LeadGuid = lead->Guid.GetRawValue();
        context.ReceiverLevel = player->GetLevel();
        context.ReceiverXp = player->GetUInt32Value(PLAYER_XP);
        context.LeadLevel = lead->Level;
        context.Multiplier = settings->Multiplier;
        context.Source = SourceFromCore(xpSource);
        amount = CatchupXpAmount(amount, context);
    }
};
}
}

void AddPresenceCatchupXpScripts()
{
    new Presence::CatchupXpWorld();
    new Presence::CatchupXpPlayer();
}
