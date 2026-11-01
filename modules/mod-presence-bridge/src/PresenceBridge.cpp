/*
 * Local structured gameplay bridge for AzerothCore.
 * Released under the GNU GPL v2, or (at your option) any later version.
 */

#include "AccountMgr.h"
#include "Bag.h"
#include "Base64.h"
#include "CellImpl.h"
#include "CharacterCache.h"
#include "Chat.h"
#include "Config.h"
#include "Creature.h"
#include "DatabaseEnv.h"
#include "DBCStores.h"
#include "GameObject.h"
#include "GossipDef.h"
#include "Group.h"
#include "GridNotifiers.h"
#include "GridNotifiersImpl.h"
#include "Item.h"
#include "ItemPackets.h"
#include "LootMgr.h"
#include "MotionMaster.h"
#include "MoveSplineInit.h"
#include "ObjectAccessor.h"
#include "ObjectMgr.h"
#include "NPCPackets.h"
#include "Opcodes.h"
#include "PathGenerator.h"
#include "Player.h"
#include "PlayerScript.h"
#include "PresenceCommercePolicy.h"
#include "PresenceEmotePolicy.h"
#include "PresenceEventJournal.h"
#include "Random.h"
#include "PresenceGuardTelemetry.h"
#include "PresenceQuestCommand.h"
#include "PresenceProtectionPolicy.h"
#include "PresencePickupPolicy.h"
#include "QuestDef.h"
#include "QuestPackets.h"
#include "ScriptMgr.h"
#include "Spell.h"
#include "SpellInfo.h"
#include "SpellMgr.h"
#include "SpellAuras.h"
#include "Trainer.h"
#include "Util.h"
#include "World.h"
#include "WorldPacket.h"
#include "WorldSession.h"
#include "WorldSessionMgr.h"
#define BOOST_JSON_NO_LIB
#define BOOST_CONTAINER_NO_LIB
#include <boost/json/src.hpp>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <ctime>
#include <deque>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace Presence
{
namespace Json = boost::json;

static_assert(uint32(OrdinaryTextEmote::Bow) == TEXT_EMOTE_BOW);
static_assert(uint32(OrdinaryTextEmote::Cheer) == TEXT_EMOTE_CHEER);
static_assert(uint32(OrdinaryTextEmote::Clap) == TEXT_EMOTE_CLAP);
static_assert(uint32(OrdinaryTextEmote::Dance) == TEXT_EMOTE_DANCE);
static_assert(uint32(OrdinaryTextEmote::Hug) == TEXT_EMOTE_HUG);
static_assert(uint32(OrdinaryTextEmote::Kiss) == TEXT_EMOTE_KISS);
static_assert(uint32(OrdinaryTextEmote::Laugh) == TEXT_EMOTE_LAUGH);
static_assert(uint32(OrdinaryTextEmote::Nod) == TEXT_EMOTE_NOD);
static_assert(uint32(OrdinaryTextEmote::Point) == TEXT_EMOTE_POINT);
static_assert(uint32(OrdinaryTextEmote::Salute) == TEXT_EMOTE_SALUTE);
static_assert(uint32(OrdinaryTextEmote::Shrug) == TEXT_EMOTE_SHRUG);
static_assert(uint32(OrdinaryTextEmote::Slap) == TEXT_EMOTE_SLAP);
static_assert(uint32(OrdinaryTextEmote::Smile) == TEXT_EMOTE_SMILE);
static_assert(uint32(OrdinaryTextEmote::Thank) == TEXT_EMOTE_THANK);
static_assert(uint32(OrdinaryTextEmote::Wave) == TEXT_EMOTE_WAVE);

uint64 EmoteMilliseconds()
{
    return uint64(std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}

std::string Text(Json::object const& object, char const* key, std::string fallback = "")
{
    auto value = object.if_contains(key);
    if (!value)
        return fallback;
    if (!value->is_string())
        throw std::runtime_error(std::string(key) + " must be a string");
    return std::string(value->as_string());
}

double Number(Json::object const& object, char const* key, double fallback = 0)
{
    auto value = object.if_contains(key);
    if (!value)
        return fallback;
    if (!value->is_number())
        throw std::runtime_error(std::string(key) + " must be a number");
    double number = value->to_number<double>();
    if (!std::isfinite(number))
        throw std::runtime_error("Numbers must be finite");
    return number;
}

uint32 Unsigned(Json::object const& object, char const* key, uint32 fallback = 0, uint32 maximum = 0xFFFFFFFF)
{
    double number = Number(object, key, fallback);
    if (number < 0 || number > maximum || std::floor(number) != number)
        throw std::runtime_error(std::string(key) + " is outside its unsigned integer range");
    return uint32(number);
}

uint64 GuidNumber(Json::object const& object, char const* key, std::string fallback = "0")
{
    std::string value = Text(object, key, std::move(fallback));
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
        throw std::runtime_error(std::string(key) + " must be an unsigned decimal GUID");
    return std::stoull(value);
}

std::string Timestamp()
{
    std::time_t now = std::time(nullptr);
    std::tm utc{};
#ifdef _WIN32
    gmtime_s(&utc, &now);
#else
    gmtime_r(&now, &utc);
#endif
    std::ostringstream output;
    output << std::put_time(&utc, "%Y-%m-%dT%H:%M:%SZ");
    return output.str();
}

Json::object PositionOf(WorldObject const* object)
{
    return {{"x", object->GetPositionX()}, {"y", object->GetPositionY()},
        {"z", object->GetPositionZ()}, {"orientation", object->GetOrientation()}};
}

bool IsReleasedGhost(Player const* player)
{
    return player->isDead() && player->HasPlayerFlag(PLAYER_FLAGS_GHOST);
}

enum class RecoverySpell : uint32
{
    ResurrectionSickness = 15007
};

char const* QuestStatusName(QuestStatus status)
{
    switch (status)
    {
        case QUEST_STATUS_NONE: return "none";
        case QUEST_STATUS_COMPLETE: return "complete";
        case QUEST_STATUS_INCOMPLETE: return "incomplete";
        case QUEST_STATUS_FAILED: return "failed";
        case QUEST_STATUS_REWARDED: return "rewarded";
        default: return "unknown";
    }
}

char const* QuestGiverStatusName(QuestGiverStatus status)
{
    switch (status)
    {
        case DIALOG_STATUS_NONE: return "none";
        case DIALOG_STATUS_UNAVAILABLE: return "unavailable";
        case DIALOG_STATUS_LOW_LEVEL_AVAILABLE: return "low_level_available";
        case DIALOG_STATUS_LOW_LEVEL_REWARD_REP: return "low_level_repeatable_reward";
        case DIALOG_STATUS_LOW_LEVEL_AVAILABLE_REP: return "low_level_repeatable_available";
        case DIALOG_STATUS_INCOMPLETE: return "incomplete";
        case DIALOG_STATUS_REWARD_REP: return "repeatable_reward";
        case DIALOG_STATUS_AVAILABLE_REP: return "repeatable_available";
        case DIALOG_STATUS_AVAILABLE: return "available";
        case DIALOG_STATUS_REWARD2: return "reward";
        case DIALOG_STATUS_REWARD: return "reward";
        default: return "unknown";
    }
}

std::string PerCasterBuffGroup(SpellInfo const* info)
{
    if (!info || info->SpellFamilyName != SPELLFAMILY_PALADIN
        || !info->IsAuraExclusiveBySpecificPerCasterWith(info))
        return "";
    switch (info->GetSpellSpecific())
    {
        case SPELL_SPECIFIC_SEAL:
            return "paladin_seal";
        case SPELL_SPECIFIC_AURA:
            return "paladin_aura";
        default:
            return "";
    }
}

Json::object UnitState(Unit const* unit, uint32 auraLimit = 24)
{
    Json::array services;
    bool vendor = unit->IsCreature() && unit->HasNpcFlag(UNIT_NPC_FLAG_VENDOR);
    bool trainer = unit->IsCreature() && unit->HasNpcFlag(UNIT_NPC_FLAG_TRAINER);
    bool repair = unit->IsCreature() && unit->HasNpcFlag(UNIT_NPC_FLAG_REPAIR);
    bool questgiver = unit->IsCreature() && unit->HasNpcFlag(UNIT_NPC_FLAG_QUESTGIVER);
    bool spiritHealer = unit->IsCreature() && unit->IsSpiritHealer();
    if (vendor)
        services.emplace_back("vendor");
    if (trainer)
        services.emplace_back("trainer");
    if (repair)
        services.emplace_back("repair");
    if (questgiver)
        services.emplace_back("questgiver");
    if (spiritHealer)
        services.emplace_back("spirit_healer");
    Json::array casts;
    for (uint32 slot = CURRENT_GENERIC_SPELL; slot < CURRENT_MAX_SPELL; ++slot)
        if (Spell* spell = unit->GetCurrentSpell(slot); spell && spell->getState() != SPELL_STATE_FINISHED)
        {
            SpellInfo const* info = spell->GetSpellInfo();
            Json::array effects;
            for (auto const& effect : info->Effects)
                if (effect.IsEffect())
                    effects.emplace_back(effect.Effect);
            casts.emplace_back(Json::object{{"spell_id", info->Id}, {"name", info->SpellName[0]},
                {"slot", slot}, {"state", spell->getState()}, {"remaining_ms", spell->GetCastTimeRemaining()},
                {"target_guid", std::to_string(spell->m_targets.GetUnitTargetGUID().GetRawValue())},
                {"semantic_tame", info->HasEffect(SPELL_EFFECT_TAMECREATURE)}, {"effect_ids", std::move(effects)}});
        }
    Json::object result{{"guid", std::to_string(unit->GetGUID().GetRawValue())}, {"name", unit->GetName()},
        {"entry", unit->GetEntry()}, {"position", PositionOf(unit)}, {"level", unit->GetLevel()},
        {"health", unit->GetHealth()}, {"max_health", unit->GetMaxHealth()},
        {"alive", unit->IsAlive()}, {"in_combat", unit->IsInCombat()},
        {"emote_state", unit->GetUInt32Value(UNIT_NPC_EMOTESTATE)}, {"stand_state", unit->getStandState()},
        {"is_player", unit->IsPlayer()}, {"npc_flags", uint32(unit->GetNpcFlags())},
        {"services", std::move(services)}, {"is_vendor", vendor}, {"is_trainer", trainer}, {"can_repair", repair},
        {"is_questgiver", questgiver}, {"is_spirit_healer", spiritHealer},
        {"moving", unit->isMoving()}, {"selected_target_guid", std::to_string(unit->GetTarget().GetRawValue())},
        {"attack_victim_guid", unit->GetVictim() ? std::to_string(unit->GetVictim()->GetGUID().GetRawValue()) : "0"},
        {"channel_spell_id", unit->GetUInt32Value(UNIT_CHANNEL_SPELL)},
        {"channel_target_guid", std::to_string(unit->GetGuidValue(UNIT_FIELD_CHANNEL_OBJECT).GetRawValue())},
        {"current_spells", std::move(casts)}};
    if (Creature const* creature = unit->ToCreature())
    {
        if (CreatureTemplate const* info = creature->GetCreatureTemplate())
        {
            std::string title = info->SubName;
            utf8truncate(title, 128);
            result["title"] = std::move(title);
        }
        if (trainer)
        {
            result["trainer_type"] = nullptr;
            result["trainer_requirement"] = nullptr;
            result["trainer_class"] = nullptr;
            result["trainer_metadata_source"] = nullptr;
            // These identify the normal default provider, not its current spell offers.
            if (Trainer::Trainer const* provider = sObjectMgr->GetTrainer(creature->GetEntry()))
            {
                Trainer::Type type = provider->GetTrainerType();
                uint32 requirement = provider->GetTrainerRequirement();
                result["trainer_type"] = static_cast<uint32>(type);
                result["trainer_requirement"] = requirement;
                result["trainer_metadata_source"] = "creature_default_trainer";
                if (type == Trainer::Type::Class && requirement > 0 && requirement < MAX_CLASSES)
                    result["trainer_class"] = requirement;
            }
        }
    }
    Json::array auras;
    uint32 totalAuras = 0;
    uint32 passiveAuras = 0;
    uint32 unavailableAuras = 0;
    for (auto const& [id, application] : unit->GetAppliedAuras())
    {
        Aura const* aura = application ? application->GetBase() : nullptr;
        SpellInfo const* info = aura ? aura->GetSpellInfo() : nullptr;
        if (!info)
        {
            ++totalAuras;
            ++unavailableAuras;
            continue;
        }
        if (info->IsPassive())
        {
            ++passiveAuras;
            continue;
        }
        ++totalAuras;
        if (auras.size() >= auraLimit)
            continue;
        std::string name = info->SpellName[0] ? info->SpellName[0] : "";
        utf8truncate(name, 96);
        Json::object facts{{"spell_id", info->Id}, {"name", std::move(name)},
            {"caster_guid", std::to_string(aura->GetCasterGUID().GetRawValue())},
            {"duration_ms", aura->GetDuration()}, {"max_duration_ms", aura->GetMaxDuration()},
            {"positive", application->IsPositive()}, {"stacks", aura->GetStackAmount()},
            {"effect_mask", application->GetEffectMask()},
            {"rank_chain_id", sSpellMgr->GetFirstSpellInChain(info->Id)},
            {"spell_specific", uint32(info->GetSpellSpecific())}};
        std::string group = PerCasterBuffGroup(info);
        if (!group.empty())
            facts["exclusive_group"] = std::move(group);
        auras.emplace_back(std::move(facts));
    }
    result["auras_coverage"] = Json::object{{"total", totalAuras}, {"included", auras.size()},
        {"omitted", totalAuras - auras.size()}, {"excluded_passive", passiveAuras},
        {"unavailable", unavailableAuras}, {"limit", auraLimit}};
    result["auras"] = std::move(auras);
    return result;
}

bool PositiveAreaAura(SpellInfo const* info)
{
    return info && info->IsPositive() && std::any_of(info->GetEffects().begin(), info->GetEffects().end(),
        [](SpellEffectInfo const& effect) { return effect.IsAreaAuraEffect(); });
}

std::optional<Json::object> BuffSpellFacts(Player* player, SpellInfo const* info)
{
    if (!info->IsPositive() || info->IsPassive())
        return std::nullopt;
    bool appliesAura = false;
    bool healing = false;
    bool areaAura = false;
    Json::array effects;
    for (auto const& effect : info->GetEffects())
    {
        if (!effect.IsEffect())
            continue;
        appliesAura = appliesAura || effect.IsAura();
        areaAura = areaAura || effect.IsAreaAuraEffect();
        healing = healing || effect.IsEffect(SPELL_EFFECT_HEAL) || effect.IsEffect(SPELL_EFFECT_HEAL_PCT)
            || effect.IsEffect(SPELL_EFFECT_HEAL_MAX_HEALTH) || effect.IsAura(SPELL_AURA_PERIODIC_HEAL)
            || effect.IsAura(SPELL_AURA_OBS_MOD_HEALTH);
        effects.emplace_back(Json::object{{"index", effect.EffectIndex}, {"effect_id", effect.Effect},
            {"aura_type", uint32(effect.ApplyAuraName)}, {"target_a", uint32(effect.TargetA.GetTarget())},
            {"target_b", uint32(effect.TargetB.GetTarget())}, {"area_aura", effect.IsAreaAuraEffect()}});
    }
    if (!appliesAura || healing)
        return std::nullopt;
    uint32 targetMask = info->GetExplicitTargetMask();
    uint32 friendlyMask = TARGET_FLAG_UNIT_ALLY | TARGET_FLAG_UNIT_PARTY | TARGET_FLAG_UNIT_RAID;
    std::string targetMode = "other";
    if (!targetMask)
        targetMode = "self";
    else if ((targetMask & friendlyMask) && !(targetMask & ~(friendlyMask | TARGET_FLAG_UNIT)))
        targetMode = "friendly_unit";
    Json::array reagents;
    for (uint32 index = 0; index < MAX_SPELL_REAGENTS; ++index)
        if (info->Reagent[index] > 0 && info->ReagentCount[index])
        {
            uint32 itemId = uint32(info->Reagent[index]);
            reagents.emplace_back(Json::object{{"item_id", itemId}, {"count", info->ReagentCount[index]},
                {"current", player->GetItemCount(itemId, false)}});
        }
    Json::object facts{{"rank_chain_id", sSpellMgr->GetFirstSpellInChain(info->Id)},
        {"rank", sSpellMgr->GetSpellRank(info->Id)}, {"positive", true}, {"applies_aura", true},
        {"spell_specific", uint32(info->GetSpellSpecific())},
        {"area_aura", areaAura}, {"target_mode", targetMode}, {"explicit_target_mask", targetMask},
        {"effects", std::move(effects)}, {"power_type", info->PowerType},
        {"power_cost", info->CalcPowerCost(player, info->GetSchoolMask())},
        {"range_min", info->GetMinRange(true)}, {"range_max", info->GetMaxRange(true, player)},
        {"duration_ms", info->GetDuration()}, {"reagents", std::move(reagents)},
        {"source", "known_spell_info"}};
    std::string group = PerCasterBuffGroup(info);
    if (!group.empty())
        facts["exclusive_group"] = std::move(group);
    return facts;
}

bool CarriedItem(Player const* player, Item const* item)
{
    if (!item || item->GetOwnerGUID() != player->GetGUID())
        return false;
    uint8 bag = item->GetBagSlot();
    uint8 slot = item->GetSlot();
    return (bag == INVENTORY_SLOT_BAG_0 && slot < INVENTORY_SLOT_ITEM_END)
        || (bag >= INVENTORY_SLOT_BAG_START && bag < INVENTORY_SLOT_BAG_END
            && player->GetBagByPos(bag) && slot < player->GetBagByPos(bag)->GetBagSize());
}

char const* EquipmentSlotName(uint8 slot)
{
    static char const* const names[] = {"head", "neck", "shoulder", "shirt", "chest", "waist", "legs", "feet",
        "wrists", "hands", "finger_1", "finger_2", "trinket_1", "trinket_2", "back", "main_hand", "off_hand",
        "ranged", "tabard", "bag_1", "bag_2", "bag_3", "bag_4"};
    return slot < INVENTORY_SLOT_BAG_END ? names[slot] : "";
}

bool CanAddQuestSilently(Player* player, Quest const* quest)
{
    // CanAddQuest(false) still sends item-capacity errors and a failure sound.
    // Keep observations pure while applying the same normal capacity checks.
    if (!quest || !player->SatisfyQuestLog(false))
        return false;
    if (!quest->GetSrcItemId())
        return true;
    ItemPosCountVec destination;
    InventoryResult result = player->CanStoreNewItem(NULL_BAG, NULL_SLOT, destination,
        quest->GetSrcItemId(), quest->GetSrcItemCount());
    return result == EQUIP_ERR_OK || result == EQUIP_ERR_CANT_CARRY_MORE_OF_THIS;
}

Json::object ItemFacts(Player* player, ItemTemplate const* info, Item* item = nullptr)
{
    Json::array stats;
    for (uint32 index = 0; index < std::min(info->StatsCount, uint32(MAX_ITEM_PROTO_STATS)); ++index)
        stats.emplace_back(Json::object{{"type", info->ItemStat[index].ItemStatType},
            {"value", info->ItemStat[index].ItemStatValue}});
    Json::array spells;
    for (auto const& spell : info->Spells)
        if (spell.SpellId > 0)
        {
            SpellInfo const* effect = sSpellMgr->GetSpellInfo(uint32(spell.SpellId));
            spells.emplace_back(Json::object{{"spell_id", spell.SpellId}, {"trigger", spell.SpellTrigger},
                {"name", effect ? effect->SpellName[0] : ""}});
        }
    Json::object result{{"entry", info->ItemId}, {"item_id", info->ItemId}, {"name", info->Name1},
        {"quality", info->Quality}, {"item_level", info->ItemLevel}, {"inventory_type", info->InventoryType},
        {"class", info->Class}, {"subclass", info->SubClass}, {"armor", info->Armor},
        {"damage_min", info->Damage[0].DamageMin}, {"damage_max", info->Damage[0].DamageMax},
        {"delay_ms", info->Delay}, {"stats", std::move(stats)}, {"stats_source", "item_template"},
        {"item_spells", std::move(spells)}, {"required_level", info->RequiredLevel},
        {"required_skill", info->RequiredSkill}, {"required_skill_rank", info->RequiredSkillRank},
        {"required_spell", info->RequiredSpell}, {"required_class_mask", info->AllowableClass},
        {"required_race_mask", info->AllowableRace}, {"container_slots", info->ContainerSlots},
        {"bag_family", info->BagFamily}, {"max_stack", info->GetMaxStackSize()},
        {"is_bag", info->Class == ITEM_CLASS_CONTAINER || info->Class == ITEM_CLASS_QUIVER},
        {"sell_price", info->SellPrice}, {"sell_price_is_estimate", true}, {"buy_count", info->BuyCount},
        {"equippable", info->InventoryType != INVTYPE_NON_EQUIP},
        {"is_quest", info->Class == ITEM_CLASS_QUEST || player->HasQuestForItem(info->ItemId)},
        {"bonding", info->Bonding}};
    InventoryResult usable = item ? player->CanUseItem(item) : player->CanUseItem(info);
    result["usable"] = usable == EQUIP_ERR_OK;
    result["use_error"] = uint32(usable);
    result["usability_error"] = uint32(usable);
    if (item)
    {
        result["guid"] = std::to_string(item->GetGUID().GetRawValue());
        result["count"] = item->GetCount();
        result["bag"] = item->GetBagSlot();
        result["slot"] = item->GetSlot();
        result["equipped"] = Player::IsEquipmentPos(item->GetPos());
        if (CarriedItem(player, item))
        {
            result["start_quest"] = nullptr;
            if (uint32 questId = info->StartQuest)
            {
                Quest const* quest = sObjectMgr->GetQuestTemplate(questId);
                Json::object start{{"id", questId}, {"source", "item_template.StartQuest"},
                    {"status", uint32(player->GetQuestStatus(questId))},
                    {"status_name", QuestStatusName(player->GetQuestStatus(questId))},
                    {"in_log", player->FindQuestSlot(questId) < MAX_QUEST_LOG_SIZE},
                    {"rewarded", player->IsQuestRewarded(questId)},
                    {"can_take", quest && player->CanTakeQuest(quest, false)},
                    {"can_add", CanAddQuestSilently(player, quest)},
                    {"template_available", quest != nullptr}};
                if (quest)
                {
                    std::string title = quest->GetTitle();
                    utf8truncate(title, 128);
                    start["title"] = std::move(title);
                }
                result["start_quest"] = std::move(start);
            }
        }
        if (Player::IsEquipmentPos(item->GetPos()))
        {
            result["equipment_slot"] = item->GetSlot();
            result["slot_name"] = EquipmentSlotName(item->GetSlot());
            result["empty"] = false;
        }
        result["soulbound"] = item->IsSoulBound();
        result["durability"] = item->GetUInt32Value(ITEM_FIELD_DURABILITY);
        result["max_durability"] = item->GetUInt32Value(ITEM_FIELD_MAXDURABILITY);
        uint16 destination = 0;
        InventoryResult equip = player->CanEquipItem(NULL_SLOT, destination, item, true);
        result["equip_error"] = uint32(equip);
        result["can_equip_now"] = equip == EQUIP_ERR_OK;
        if (equip == EQUIP_ERR_OK)
            result["candidate_equipment_slot"] = uint32(destination & 0xFF);
        Json::array enchantments;
        for (uint8 slot = 0; slot < MAX_ENCHANTMENT_SLOT; ++slot)
            if (uint32 enchantment = item->GetEnchantmentId(EnchantmentSlot(slot)))
            {
                Json::object row{{"slot", slot}, {"id", enchantment},
                    {"remaining_ms", item->GetEnchantmentDuration(EnchantmentSlot(slot))}};
                if (SpellItemEnchantmentEntry const* entry = sSpellItemEnchantmentStore.LookupEntry(enchantment))
                {
                    row["description"] = entry->description[0];
                    Json::array effects;
                    for (uint32 index = 0; index < MAX_SPELL_ITEM_ENCHANTMENT_EFFECTS; ++index)
                        if (entry->type[index])
                            effects.emplace_back(Json::object{{"type", entry->type[index]},
                                {"amount", entry->amount[index]}, {"argument", entry->spellid[index]}});
                    row["effects"] = std::move(effects);
                }
                enchantments.emplace_back(std::move(row));
            }
        result["enchantments"] = std::move(enchantments);
        result["random_property_id"] = item->GetItemRandomPropertyId();
        result["suffix_factor"] = item->GetItemSuffixFactor();
        result["modifiers_resolved"] = false;
        int32 property = item->GetItemRandomPropertyId();
        char const* suffix = nullptr;
        if (property > 0)
        {
            if (ItemRandomPropertiesEntry const* entry = sItemRandomPropertiesStore.LookupEntry(uint32(property)))
                suffix = entry->Name[0];
        }
        else if (property < 0)
            if (ItemRandomSuffixEntry const* entry = sItemRandomSuffixStore.LookupEntry(uint32(-int64(property))))
                suffix = entry->Name[0];
        if (suffix && *suffix)
        {
            result["random_property_name"] = suffix;
            result["name"] = info->Name1 + " " + suffix;
        }
    }
    return result;
}

Json::object BagCapacity(Player* player)
{
    uint32 backpackSlots = INVENTORY_SLOT_ITEM_END - INVENTORY_SLOT_ITEM_START;
    uint32 backpackUsed = 0;
    for (uint8 slot = INVENTORY_SLOT_ITEM_START; slot < INVENTORY_SLOT_ITEM_END; ++slot)
        if (player->GetItemByPos(INVENTORY_SLOT_BAG_0, slot))
            ++backpackUsed;
    uint32 total = backpackSlots;
    uint32 used = backpackUsed;
    uint32 generalFree = backpackSlots - backpackUsed;
    Json::array bags;
    for (uint8 slot = INVENTORY_SLOT_BAG_START; slot < INVENTORY_SLOT_BAG_END; ++slot)
    {
        Bag* bag = player->GetBagByPos(slot);
        uint32 slots = bag ? std::min(bag->GetBagSize(), uint32(MAX_BAG_SIZE)) : 0;
        uint32 occupied = 0;
        for (uint32 index = 0; index < slots; ++index)
            if (bag->GetItemByPos(uint8(index)))
                ++occupied;
        ItemTemplate const* info = bag ? bag->GetTemplate() : nullptr;
        bool general = info && info->Class == ITEM_CLASS_CONTAINER && info->SubClass == ITEM_SUBCLASS_CONTAINER;
        bags.emplace_back(Json::object{{"equipment_slot", slot}, {"slot_name", EquipmentSlotName(slot)},
            {"empty", !bag}, {"bag_guid", bag ? std::to_string(bag->GetGUID().GetRawValue()) : "0"},
            {"total_slots", slots}, {"used_slots", occupied}, {"free_slots", slots - occupied},
            {"general_purpose", general}, {"bag_family", info ? info->BagFamily : 0}});
        total += slots;
        used += occupied;
        if (general)
            generalFree += slots - occupied;
    }
    return {{"total_slots", total}, {"used_slots", used}, {"free_slots", total - used},
        {"general_free_slots", generalFree},
        {"backpack", Json::object{{"bag", INVENTORY_SLOT_BAG_0}, {"total_slots", backpackSlots},
            {"used_slots", backpackUsed}, {"free_slots", backpackSlots - backpackUsed}}},
        {"bags", std::move(bags)}};
}

struct CommerceMenu
{
    ObjectGuid source;
    Json::array rows;
    uint32 total = 0;
    uint32 page = 0;
    uint64 revision = 0;
    std::chrono::steady_clock::time_point opened;
};

struct QuestFrame
{
    ObjectGuid source;
    uint32 quest = 0;
    std::string phase;
    Json::object fields;
    Json::array rows;
    uint64 revision = 0;
    std::chrono::steady_clock::time_point opened;
};

struct SpiritHealerFrame
{
    ObjectGuid source;
    ObjectGuid character;
    uint32 map = 0;
    uint32 instance = 0;
    uint32 menu = 0;
    std::set<uint32> options;
    std::string receivedAt;
    std::chrono::steady_clock::time_point received;
};

struct CachedRequest
{
    std::string encoded;
    Json::object response;
    std::string actionType;
};

struct NativeJournal
{
    ObjectGuid observer;
    JournalBuffer<Json::object> buffer;
    uint64 excludedAddon = 0;
    uint64 excludedDecodeError = 0;
};

struct TradeFrame
{
    uint64 id = 0;
    uint32 revision = 0;
    ObjectGuid partner;
    bool active = false;
    bool open = false;
    uint32 lastStatus = 0;
    uint64 statusSequence = 0;
    uint32 inventoryResult = 0;
    bool targetResult = false;
    uint32 limitedItem = 0;
    std::string fingerprint;
    Json::object receipt;
    bool pendingConsent = false;
};

struct Actor
{
    std::unique_ptr<WorldSession> session;
    std::string pendingId;
    std::string phase;
    std::string motionId;
    bool motionAsGhost = false;
    bool loginCancelled = false;
    Position destination;
    std::chrono::steady_clock::time_point loginDeadline;
    std::chrono::steady_clock::time_point motionDeadline;
    ObjectGuid protectedGroup;
    ObjectGuid protectedTarget;
    std::string protectedName;
    std::string protectionMode = "inactive";
    std::string protectionReason;
    std::chrono::steady_clock::time_point nextEscape;
    Position escapeDestination;
    std::map<ObjectGuid, ReactStates> petReactions;
    ObjectGuid inspectedItem;
    std::string lootId;
    ObjectGuid lootTarget;
    uint32 lootSpell = 0;
    uint8 lootCastCount = 0;
    uint8 nextLootCastCount = 0;
    Json::object journalBasic;
    bool journalDetailsReady = false;
    std::chrono::steady_clock::time_point journalNextDetails;
    std::map<uint32, uint64> journalInventory;
    std::map<uint32, Json::object> journalQuests;
    std::map<ObjectGuid, bool> journalParty;
    std::map<ObjectGuid, Json::object> journalPartyUnits;
    std::chrono::steady_clock::time_point lootDeadline;
    std::chrono::steady_clock::time_point nextInteractionGesture;
};

struct OpeningLoot
{
    std::string request;
    ObjectGuid target;
    uint32 spell = 0;
    uint8 count = 0;
};

struct TameAttempt
{
    ObjectGuid group;
    ObjectGuid tamer;
    ObjectGuid target;
    uint32 spell = 0;
    std::chrono::steady_clock::time_point observed;
    uint32 attempts = 1;
    std::string phase = "attempt";
    std::deque<std::pair<std::string, std::chrono::steady_clock::time_point>> phases;
    uint8 castCount = 0;
};

struct ProtectionBinding
{
    ObjectGuid actor;
    StickyProtection policy;
    std::string protectorName;
    std::string targetName;
    uint32 map = 0;
    uint32 instance = 0;
    uint32 entry = 0;
    uint32 spawn = 0;
    bool recoveredDynamic = false;
};

struct MarkerChange
{
    ObjectGuid setter;
    ObjectGuid group;
    uint8 icon = 0;
    ObjectGuid target;
    ObjectGuid moon;
    bool clearCommand = false;
};

struct GuardActionContext
{
    ObjectGuid owner;
    std::string request;
    std::string action;
    uint64 observedSequence = 0;
    Json::array interventions;
    uint32 dropped = 0;
    uint32 quest = 0;
    bool questRewarded = false;
    bool interactionVisualObserved = false;
};

// Only synchronous hooks on this action's thread may claim its request identity.
// Delayed effects on map workers deliberately have no planner attribution.
thread_local GuardActionContext* CurrentGuardAction = nullptr;

class GuardActionScope
{
public:
    explicit GuardActionScope(GuardActionContext& context) : _previous(CurrentGuardAction)
    {
        CurrentGuardAction = &context;
    }

    ~GuardActionScope() { CurrentGuardAction = _previous; }

private:
    GuardActionContext* _previous;
};

struct GuardTelemetry
{
    GuardTelemetryWindow window;
    std::deque<Json::object> events;
};

struct LootSlot
{
    uint8 slot;
    uint32 item;
    uint32 count;
};

struct LootWindow
{
    ObjectGuid guid;
    uint32 gold = 0;
    uint8 visibleSlots = 0;
    bool valid = false;
    std::vector<LootSlot> allowed;
    std::string openingRequest;
};

struct PartyInvite
{
    ObjectGuid inviter;
    ObjectGuid leader;
    ObjectGuid group;
    std::string name;
};

struct SharedQuestOffer
{
    ObjectGuid sharer;
    uint32 quest = 0;
    bool confirmation = false;
    uint64 sequence = 0;
    std::chrono::steady_clock::time_point received;
};

struct QuestAbandonCommand
{
    ObjectGuid sender;
    ObjectGuid group;
    ObjectGuid character;
    std::string name;
    uint32 quest = 0;
    std::chrono::steady_clock::time_point received;
};

class Bridge
{
public:
    static Bridge& Instance()
    {
        // Explicit OnShutdown cleanup happens while the core is still alive.
        static Bridge* bridge = new Bridge();
        return *bridge;
    }

    void Configure()
    {
        _accountName = sConfigMgr->GetOption<std::string>("PresenceBridge.Account", "PRESENCE");
        std::string names = sConfigMgr->GetOption<std::string>(
            "PresenceBridge.AllowedCharacters", "Vesper,Acoreprobe");
        _allowed.clear();
        std::istringstream input(names);
        std::string name;
        while (std::getline(input, name, ','))
            if (normalizePlayerName(name))
                _allowed.insert(name);
        if (!_protectionLoaded)
        {
            _protectionLoaded = true;
            _protectedCharacter = sConfigMgr->GetOption<std::string>("PresenceBridge.ProtectedCharacter", "Vesper");
            _protectionFile = sConfigMgr->GetOption<std::string>(
                "PresenceBridge.ProtectionFile", "presence-bridge-protection.jsonl");
            LoadProtection();
        }
    }

    Json::object Response(Json::object const& request, bool ok, Json::object result = {})
    {
        return {{"v", 1}, {"id", Text(request, "id")}, {"op", Text(request, "op")},
            {"character", Text(request, "character")}, {"ok", ok}, {"result", std::move(result)}};
    }

    Json::object Error(Json::object const& request, char const* code, std::string const& message)
    {
        auto response = Response(request, false);
        response["error"] = Json::object{{"code", code}, {"message", message}};
        return response;
    }

    Json::object Request(std::string const& encoded)
    {
        Json::object request;
        try
        {
            if (encoded.empty() || encoded.size() > 32768)
                return Error(request, "invalid_request", "Encoded request must contain 1 to 32768 bytes");
            auto decoded = Acore::Encoding::Base64::Decode(encoded);
            if (!decoded)
                return Error(request, "invalid_request", "Invalid standard base64");
            auto parsed = Json::parse(std::string(decoded->begin(), decoded->end()));
            if (!parsed.is_object())
                return Error(request, "invalid_request", "Request must be a JSON object");
            request = parsed.as_object();
            // Validate envelope before constructing any error response from it.
            std::string id = Text(request, "id");
            std::string op = Text(request, "op");
            std::string name = Text(request, "character");
            if (Number(request, "v") != 1 || id.empty() || id.size() > 128 || op.empty())
                return Error(request, "invalid_request", "Expected v=1, id (1-128 characters), and op");
            if (op == "capabilities")
                return Response(request, true, {{"protocol", 1}, {"operations", Json::array{
                    "observe", "events", "action", "action_result", "capabilities", "attach", "detach"}},
                    {"actions", Json::array{"say", "emote", "move_to", "stop", "follow", "target",
                        "attack", "cast", "interact", "loot", "query_quest", "accept_quest", "complete_quest",
                        "request_reward", "reward_quest",
                        "party_accept", "party_decline", "vendor_list", "vendor_buy", "vendor_sell", "vendor_repair",
                        "trainer_list", "train_spell", "equip_item", "unequip_item", "inspect_item", "gossip_select",
                        "spirit_healer_activate",
                        "vendor_buyback", "trade_begin", "trade_accept", "trade_unaccept", "trade_cancel"}},
                    {"loot", Json::object{{"target_types", Json::array{"creature_corpse", "gameobject_chest"}},
                        {"operation", "open_loot"}, {"async_opening", true}}},
                    {"headless", true}, {"allowed_characters", AllowedNames()}});
            if (op == "action_result")
            {
                std::string original = Text(request, "request_id");
                auto found = _requests.find(original);
                if (found == _requests.end())
                    return Error(request, "unknown_request", "Request is not in the bounded result cache");
                return Response(request, true, {{"request_id", original}, {"response", found->second.response}});
            }
            if (!normalizePlayerName(name))
                return Error(request, "invalid_character", "Character name is invalid");
            request["character"] = name;
            if (op == "observe")
                return Observe(request, name);
            if (!_allowed.contains(name))
                return Error(request, "character_not_allowed", "Character is outside PresenceBridge.AllowedCharacters");
            if (op == "events")
                return JournalRead(request, name);
            auto duplicate = _requests.find(id);
            if (duplicate != _requests.end())
            {
                if (duplicate->second.encoded != encoded)
                    return Error(request, "id_conflict", "A request id cannot be reused for a different request");
                return duplicate->second.response;
            }
            Json::object response;
            if (op == "create" || op == "attach")
                response = Connect(request, name, op == "create");
            else if (op == "detach")
            {
                auto actor = _actors.find(name);
                if (actor != _actors.end())
                {
                    if (actor->second->phase == "creating" || actor->second->phase == "loading")
                        return Error(request, "busy", "Wait for the pending creation/login before detaching");
                    CancelOpeningLoot(*actor->second, "detached");
                    if (Player* player = actor->second->session->GetPlayer())
                        RestorePetReactions(*actor->second, player);
                    actor->second->session->LogoutPlayer(true);
                    RemoveCreationResult(actor->second->session.get());
                    _actors.erase(actor);
                }
                response = Response(request, true, {{"status", "completed"}, {"attached", false}});
            }
            else if (op == "action")
                response = Action(request, name);
            else
                response = Error(request, "unknown_operation", "Operation is not supported");
            std::string actionType;
            if (auto action = request.if_contains("action"); op == "action" && action && action->is_object())
                actionType = Text(action->as_object(), "type");
            Remember(id, encoded, response, actionType);
            if (op == "action")
                JournalAction(name, id, actionType, response);
            return response;
        }
        catch (std::exception const& exception)
        {
            // Malformed envelope fields must never make the error formatter throw again.
            Json::object envelope;
            for (char const* key : {"id", "op", "character"})
                if (auto value = request.if_contains(key); value && value->is_string())
                    envelope[key] = *value;
            return Error(envelope, "invalid_request", exception.what());
        }
    }

    static std::set<std::string> const& JournalTypes()
    {
        static std::set<std::string> const types{"chat", "text_emote", "combat_started", "combat_ended",
            "damage", "death", "resurrected", "area_changed", "quest_changed", "inventory_changed",
            "party_separation", "party_rejoined", "arrival", "action_result", "loot_result"};
        return types;
    }

    void JournalAppendLocked(Player* player, std::string const& type, Json::object payload, ObjectGuid actor = {})
    {
        auto& journal = _journals[player->GetName()];
        journal.observer = player->GetGUID();
        if (journal.buffer.Newest() == std::numeric_limits<uint64>::max())
            return;
        std::string sequence = std::to_string(journal.buffer.Newest() + 1);
        journal.buffer.Push(Json::object{{"type", type}, {"timestamp", Timestamp()},
            {"cursor", _journalEpoch + ":" + sequence}, {"sequence", sequence},
            {"observer_guid", std::to_string(player->GetGUID().GetRawValue())},
            {"actor_guid", std::to_string((actor ? actor : player->GetGUID()).GetRawValue())},
            {"payload", std::move(payload)}});
    }

    void JournalAppend(Player* player, std::string const& type, Json::object payload, ObjectGuid actor = {})
    {
        if (!player || !player->GetSession())
            return;
        std::lock_guard<std::mutex> lock(_eventMutex);
        if (_ownedSessions.contains(player->GetSession()))
            JournalAppendLocked(player, type, std::move(payload), actor);
    }

    Json::object JournalRead(Json::object const& request, std::string const& name)
    {
        std::set<std::string> selected;
        if (auto filters = request.if_contains("event_types"))
        {
            if (!filters->is_array() || filters->as_array().size() > JournalTypes().size())
                return Error(request, "invalid_filter", "event_types must be a bounded array of journal types");
            for (auto const& value : filters->as_array())
            {
                if (!value.is_string() || !JournalTypes().contains(std::string(value.as_string())))
                    return Error(request, "invalid_filter", "A journal event type is not supported");
                selected.insert(std::string(value.as_string()));
            }
        }
        if (auto maximum = request.if_contains("max_events"); maximum
            && !maximum->is_int64() && !maximum->is_uint64())
            return Error(request, "invalid_limit", "max_events must be an integer from 1 through 512");
        double maximum = Number(request, "max_events", 128);
        if (maximum < 1 || maximum > 512)
            return Error(request, "invalid_limit", "max_events must be an integer from 1 through 512");
        std::optional<JournalCursor> supplied;
        if (auto since = request.if_contains("since"))
        {
            if (!since->is_string() || !(supplied = ParseJournalCursor(std::string(since->as_string()))))
                return Error(request, "invalid_cursor", "since must be a 32-lowercase-hex epoch:decimal cursor");
        }
        std::lock_guard<std::mutex> lock(_eventMutex);
        auto found = _journals.find(name);
        if (found == _journals.end())
            return Error(request, "journal_unavailable", "No owned-character journal is available yet");
        NativeJournal const& journal = found->second;
        bool reset = supplied && supplied->epoch != _journalEpoch;
        uint64 since = supplied ? (reset ? 0 : supplied->sequence) : journal.buffer.Newest();
        if (supplied && !reset && since > journal.buffer.Newest())
            return Error(request, "cursor_ahead", "Cursor is ahead of this character's journal");
        auto page = journal.buffer.Read(since, std::size_t(maximum), [&selected](Json::object const& event)
        {
            return selected.empty() || selected.contains(Text(event, "type"));
        });
        Json::array events;
        for (auto const& entry : page.events)
            events.push_back(entry.value);
        return Response(request, true, {{"schema", "native-event-journal/v1"}, {"epoch", _journalEpoch},
            {"observer_guid", std::to_string(journal.observer.GetRawValue())},
            {"cursor", _journalEpoch + ":" + std::to_string(page.cursor)}, {"events", std::move(events)},
            {"oldest", _journalEpoch + ":" + std::to_string(journal.buffer.Oldest())},
            {"newest", _journalEpoch + ":" + std::to_string(journal.buffer.Newest())},
            {"has_more", page.hasMore}, {"gap", page.gap}, {"reset", reset}, {"baseline", !supplied},
            {"lost_events", std::to_string(page.lost)}, {"previous_epoch_loss_unknown", reset},
            {"dropped_total", std::to_string(journal.buffer.Dropped())},
            {"excluded_addon_total", std::to_string(journal.excludedAddon)},
            {"excluded_decode_error_total", std::to_string(journal.excludedDecodeError)},
            {"sampling", Json::object{{"basic", "owned_world_update"}, {"details_interval_ms", 250},
                {"damage", "net_health_drop_not_full_combat_log"}, {"scope", "owned_self_and_visible_party"},
                {"party_baseline", "cleared_when_invisible"}}}});
    }

    void JournalAction(std::string const& name, std::string const& id, std::string const& type,
        Json::object const& response)
    {
        auto actor = _actors.find(name);
        if (actor == _actors.end())
            return;
        Player* player = actor->second->session->GetPlayer();
        if (!player)
            return;
        bool ok = response.at("ok").as_bool();
        auto field = response.if_contains("result");
        Json::object result = field && field->is_object() ? field->as_object() : Json::object{};
        std::string status = ok ? Text(result, "status") : (Text(result, "status") == "unknown" ? "unknown" : "failed");
        if (status.empty())
            status = ok ? "completed" : "failed";
        Json::object facts{{"request_id", id}, {"action_type", type}, {"status", status}, {"ok", ok}};
        if (std::string reference = Text(result, "request_id"); !reference.empty() && reference != id)
            facts["referenced_request_id"] = reference;
        if (auto error = response.if_contains("error"); error && error->is_object())
            facts["error_code"] = Text(error->as_object(), "code");
        if (std::string reason = Text(result, "reason"); !reason.empty())
            facts["reason"] = reason.substr(0, 128);
        for (char const* key : {"target_guid", "quest_id", "arrived", "partial", "copper", "skipped_slots",
                               "reward_receipt", "tracking_quest_rewarded"})
            if (auto value = result.if_contains(key); value && !value->is_object() && !value->is_array())
                facts[key] = *value;
        JournalAppend(player, "action_result", facts);
        if (type == "loot" && ok && status == "completed")
        {
            if (auto items = result.if_contains("items"); items && items->is_array())
                facts["items"] = *items;
            JournalAppend(player, "loot_result", std::move(facts));
        }
    }

    void JournalStateTransitions(Player* observer, Json::object const& before, Json::object const& after,
        ObjectGuid actor, char const* source, uint32 interval)
    {
        if (before.empty())
            return;
        JournalActorDelta delta = CompareJournalActorStates(
            {before.at("alive").as_bool(), before.at("combat").as_bool(), before.at("health").to_number<uint64>()},
            {after.at("alive").as_bool(), after.at("combat").as_bool(), after.at("health").to_number<uint64>()});
        Json::object facts{{"source", source}, {"sample_interval_ms", interval}};
        if (delta.combatStarted || delta.combatEnded)
        {
            facts["in_combat"] = delta.combatStarted;
            JournalAppend(observer, delta.combatStarted ? "combat_started" : "combat_ended", facts, actor);
        }
        if (delta.died || delta.resurrected)
        {
            facts["alive"] = delta.resurrected;
            JournalAppend(observer, delta.died ? "death" : "resurrected", facts, actor);
        }
        if (delta.healthLoss)
        {
            facts["before_health"] = before.at("health");
            facts["health"] = after.at("health");
            facts["net_health_loss"] = delta.healthLoss;
            facts["damage_semantics"] = "net_health_drop_not_full_combat_log";
            JournalAppend(observer, "damage", std::move(facts), actor);
        }
    }

    void SampleJournal(Actor& actor, Player* player)
    {
        Json::object basic{{"health", player->GetHealth()}, {"alive", player->IsAlive()},
            {"combat", player->IsInCombat()}, {"map_id", player->GetMapId()},
            {"zone_id", player->GetZoneId()}, {"area_id", player->GetAreaId()}};
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            _journals[player->GetName()].observer = player->GetGUID();
        }
        if (!actor.journalBasic.empty())
        {
            JournalStateTransitions(player, actor.journalBasic, basic, player->GetGUID(),
                "owned_world_update", 0);
            if (actor.journalBasic.at("map_id") != basic.at("map_id")
                || actor.journalBasic.at("zone_id") != basic.at("zone_id")
                || actor.journalBasic.at("area_id") != basic.at("area_id"))
                JournalAppend(player, "area_changed", {{"before_map_id", actor.journalBasic.at("map_id")},
                    {"map_id", player->GetMapId()}, {"zone_id", player->GetZoneId()},
                    {"area_id", player->GetAreaId()}});
        }
        actor.journalBasic = std::move(basic);
        auto now = std::chrono::steady_clock::now();
        if (now < actor.journalNextDetails)
            return;
        actor.journalNextDetails = now + std::chrono::milliseconds(250);
        SampleJournalDetails(actor, player);
    }

    void SampleJournalDetails(Actor& actor, Player* player)
    {
        std::map<uint32, uint64> items;
        auto itemCount = [&items](Item* item)
        {
            if (item)
                items[item->GetEntry()] += item->GetCount();
        };
        for (uint8 slot = 0; slot < INVENTORY_SLOT_ITEM_END; ++slot)
            itemCount(player->GetItemByPos(INVENTORY_SLOT_BAG_0, slot));
        for (uint8 bag = INVENTORY_SLOT_BAG_START; bag < INVENTORY_SLOT_BAG_END; ++bag)
            if (Bag* container = player->GetBagByPos(bag))
                for (uint32 slot = 0; slot < std::min(container->GetBagSize(), uint32(MAX_BAG_SIZE)); ++slot)
                    itemCount(container->GetItemByPos(uint8(slot)));
        if (actor.journalDetailsReady && items != actor.journalInventory)
        {
            Json::array changes;
            std::set<uint32> identifiers;
            for (auto const& [id, count] : items)
                identifiers.insert(id);
            for (auto const& [id, count] : actor.journalInventory)
                identifiers.insert(id);
            for (uint32 id : identifiers)
            {
                uint64 before = actor.journalInventory.contains(id) ? actor.journalInventory.at(id) : 0;
                uint64 after = items.contains(id) ? items.at(id) : 0;
                if (before != after)
                    changes.emplace_back(Json::object{{"item_id", id}, {"before", before}, {"after", after}});
            }
            JournalAppend(player, "inventory_changed",
                {{"changes", std::move(changes)}, {"source", "carried_item_counts"}});
        }
        actor.journalInventory = std::move(items);
        std::map<uint32, Json::object> quests;
        for (uint16 slot = 0; slot < MAX_QUEST_LOG_SIZE; ++slot)
            if (uint32 id = player->GetQuestSlotQuestId(slot))
            {
                Json::array objectives;
                Json::array questItems;
                for (uint8 index = 0; index < QUEST_OBJECTIVES_COUNT; ++index)
                    objectives.push_back(player->GetQuestSlotCounter(slot, index));
                if (Quest const* quest = sObjectMgr->GetQuestTemplate(id))
                    for (uint8 index = 0; index < QUEST_ITEM_OBJECTIVES_COUNT; ++index)
                        if (quest->RequiredItemId[index])
                            questItems.emplace_back(Json::object{{"item_id", quest->RequiredItemId[index]},
                                {"current", player->GetItemCount(quest->RequiredItemId[index])},
                                {"required", quest->RequiredItemCount[index]}});
                quests[id] = {{"status", uint32(player->GetQuestStatus(id))},
                    {"objectives", std::move(objectives)}, {"item_objectives", std::move(questItems)}};
            }
        if (actor.journalDetailsReady)
        {
            for (auto const& [id, facts] : quests)
                if (!actor.journalQuests.contains(id) || actor.journalQuests.at(id) != facts)
                    JournalAppend(player, "quest_changed", {{"quest_id", id},
                        {"change", actor.journalQuests.contains(id) ? "updated" : "added"}, {"current", facts}});
            for (auto const& [id, facts] : actor.journalQuests)
                if (!quests.contains(id))
                    JournalAppend(player, "quest_changed", {{"quest_id", id}, {"change", "removed"}});
        }
        actor.journalQuests = std::move(quests);
        std::set<ObjectGuid> currentMembers;
        if (Group* group = player->GetGroup())
            for (auto const& member : group->GetMemberSlots())
            {
                if (member.guid == player->GetGUID() || currentMembers.size() == MAXRAIDSIZE)
                    continue;
                currentMembers.insert(member.guid);
                Player* other = ObjectAccessor::FindPlayer(member.guid);
                bool sameMap = other && other->IsInWorld() && other->GetMap() == player->GetMap();
                bool visible = sameMap && player->HaveAtClient(other) && player->CanSeeOrDetect(other);
                bool before = actor.journalParty.contains(member.guid) && actor.journalParty.at(member.guid);
                float distance = visible ? player->GetDistance(other) : 0;
                bool separated = !visible || (before ? distance > 25.0f : distance >= 30.0f);
                if (actor.journalDetailsReady && actor.journalParty.contains(member.guid) && separated != before)
                {
                    Json::object facts{{"member_guid", std::to_string(member.guid.GetRawValue())},
                        {"visible", visible}, {"same_map", sameMap}, {"separated", separated},
                        {"separation_yards", 30}, {"recovery_yards", 25},
                        {"reason", !sameMap ? "offline_or_different_map" : !visible ? "not_visible" : "distance"}};
                    facts["distance"] = visible ? Json::value(distance) : Json::value(nullptr);
                    JournalAppend(player, separated ? "party_separation" : "party_rejoined",
                        std::move(facts), member.guid);
                }
                actor.journalParty[member.guid] = separated;
                if (visible)
                {
                    Json::object state{{"health", other->GetHealth()}, {"alive", other->IsAlive()},
                        {"combat", other->IsInCombat()}};
                    if (auto previous = actor.journalPartyUnits.find(member.guid);
                        previous != actor.journalPartyUnits.end())
                        JournalStateTransitions(player, previous->second, state, member.guid,
                            "visible_party_sample", 250);
                    actor.journalPartyUnits[member.guid] = std::move(state);
                }
                else
                    actor.journalPartyUnits.erase(member.guid); // No invented damage across invisible intervals.
            }
        for (auto it = actor.journalParty.begin(); it != actor.journalParty.end();)
            if (!currentMembers.contains(it->first))
            {
                if (actor.journalDetailsReady && !it->second)
                    JournalAppend(player, "party_separation", {{"member_guid", std::to_string(it->first.GetRawValue())},
                        {"reason", "left_party"}, {"separated", true}}, it->first);
                actor.journalPartyUnits.erase(it->first);
                it = actor.journalParty.erase(it);
            }
            else
                ++it;
        actor.journalDetailsReady = true;
    }

    void Update()
    {
        // World::Update calls this after MapMgr::Update has joined its workers.
        for (auto const& [name, actor] : _actors)
        {
            actor->session->ProcessQueryCallbacks();
            if (actor->phase == "loading" && std::chrono::steady_clock::now() > actor->loginDeadline)
            {
                // The eventual callback checks this flag before loading a Player.
                actor->loginCancelled = true;
                actor->phase = "failed";
                Finish(actor->pendingId, false, {{"status", "failed"}, {"reason", "login_timeout"}});
            }
            if (actor->phase == "creating")
            {
                int code = CreationResult(actor->session.get());
                if (code >= 0)
                {
                    actor->phase = code == CHAR_CREATE_SUCCESS ? "created" : "failed";
                    Finish(actor->pendingId, code == CHAR_CREATE_SUCCESS, {
                        {"status", code == CHAR_CREATE_SUCCESS ? "completed" : "failed"},
                        {"creation_code", code}, {"character", name}});
                }
            }
            Player* player = actor->session->GetPlayer();
            if (!player)
                continue;
            if (player->IsBeingTeleportedFar())
                actor->session->HandleMoveWorldportAck();
            if (player->IsBeingTeleportedNear())
            {
                WorldPacket packet(MSG_MOVE_TELEPORT_ACK, 20);
                packet << player->GetPackGUID() << uint32(0) << uint32(0);
                actor->session->HandleMoveTeleportAck(packet);
            }
            if (actor->phase == "ready")
            {
                RefreshSpiritHealerFrames(player);
                if (player->isMoving() || player->IsInCombat() || player->IsNonMeleeSpellCast(false))
                    ClearCosmeticEmote(*actor, player);
                RefreshTrade(player);
                ProcessSharedQuest(*actor, player);
                ProcessQuestAbandonCommands(*actor, player);
                UpdateProtection(*actor, player);
                ProcessOpeningLoot(*actor, player);
                if (player->IsInWorld())
                    SampleJournal(*actor, player);
            }
            if (!actor->motionId.empty())
            {
                bool ghost = IsReleasedGhost(player);
                if ((!player->IsAlive() && !ghost) || ghost != actor->motionAsGhost
                    || std::chrono::steady_clock::now() > actor->motionDeadline)
                {
                    player->GetMotionMaster()->Clear();
                    player->StopMoving();
                    Finish(actor->motionId, false, {{"status", "failed"}, {"reason", "movement_timeout_or_death"}});
                    actor->motionId.clear();
                }
                else if (player->GetDistance(actor->destination) < 1.0f)
                {
                    Finish(actor->motionId, true, {{"status", "completed"}, {"arrived", true}});
                    JournalAppend(player, "arrival", {{"request_id", actor->motionId},
                        {"distance", player->GetDistance(actor->destination)}, {"source", "normal_motion_completion"}});
                    actor->motionId.clear();
                }
            }
        }
    }

    void Shutdown()
    {
        for (auto const& [name, actor] : _actors)
        {
            CancelOpeningLoot(*actor, "server_shutdown");
            if (Player* player = actor->session->GetPlayer())
                RestorePetReactions(*actor, player);
            actor->session->LogoutPlayer(true);
            RemoveCreationResult(actor->session.get());
        }
        _actors.clear();
    }

    Creature* SpiritHealerNpc(Player* player, ObjectGuid guid)
    {
        if (!player || !IsReleasedGhost(player) || !player->IsInWorld() || player->IsBeingTeleported())
            return nullptr;
        Creature* npc = player->GetNPCIfCanInteractWith(guid, UNIT_NPC_FLAG_SPIRITHEALER);
        return npc && player->CanSeeOrDetect(npc) && player->IsWithinLOSInMap(npc) ? npc : nullptr;
    }

    bool SpiritHealerFrameCurrent(Player* player, SpiritHealerFrame const& frame)
    {
        return frame.character == player->GetGUID() && frame.source == player->GetTarget()
            && frame.map == player->GetMapId() && frame.instance == player->GetInstanceId()
            && std::chrono::steady_clock::now() - frame.received < std::chrono::seconds(30)
            && SpiritHealerNpc(player, frame.source);
    }

    void ClearSpiritHealerFrames(WorldSession* session)
    {
        std::lock_guard<std::mutex> lock(_eventMutex);
        _spiritHealerMenus.erase(session);
        _spiritHealerConfirmations.erase(session);
    }

    void ClearSpiritRecovery(Player* player)
    {
        if (!player)
            return;
        std::lock_guard<std::mutex> lock(_eventMutex);
        _spiritHealerMenus.erase(player->GetSession());
        _spiritHealerConfirmations.erase(player->GetSession());
        _spiritRecoveryReceipts.erase(player->GetSession());
    }

    std::optional<SpiritHealerFrame> CurrentSpiritHealerFrame(WorldSession* session, bool menu)
    {
        std::lock_guard<std::mutex> lock(_eventMutex);
        auto const& frames = menu ? _spiritHealerMenus : _spiritHealerConfirmations;
        auto found = frames.find(session);
        return found == frames.end() ? std::nullopt : std::optional<SpiritHealerFrame>(found->second);
    }

    void RefreshSpiritHealerFrames(Player* player)
    {
        for (bool menu : {true, false})
            if (auto frame = CurrentSpiritHealerFrame(player->GetSession(), menu);
                frame && !SpiritHealerFrameCurrent(player, *frame))
            {
                std::lock_guard<std::mutex> lock(_eventMutex);
                auto& frames = menu ? _spiritHealerMenus : _spiritHealerConfirmations;
                auto found = frames.find(player->GetSession());
                if (found != frames.end() && found->second.received == frame->received)
                    frames.erase(found);
            }
    }

    void CaptureSpiritHealerFrame(WorldSession* session, WorldPacket const& packet, bool menu)
    {
        // A new menu supersedes any previous recovery dialog, including other NPCs.
        ClearSpiritHealerFrames(session);
        try
        {
            if (!menu && packet.size() != 8)
                return;
            Player* player = session->GetPlayer();
            WorldPacket copy(packet);
            SpiritHealerFrame frame;
            copy >> frame.source;
            if (!player || frame.source != player->GetTarget() || !SpiritHealerNpc(player, frame.source))
                return;
            frame.character = player->GetGUID();
            frame.map = player->GetMapId();
            frame.instance = player->GetInstanceId();
            frame.received = std::chrono::steady_clock::now();
            frame.receivedAt = Timestamp();
            if (menu)
            {
                uint32 textId, count;
                copy >> frame.menu >> textId >> count;
                if (count > 64)
                    return;
                for (uint32 index = 0; index < count; ++index)
                {
                    uint32 option, money;
                    uint8 icon, coded;
                    std::string text, confirmation;
                    copy >> option >> icon >> coded >> money >> text >> confirmation;
                    frame.options.insert(option);
                }
            }
            std::lock_guard<std::mutex> lock(_eventMutex);
            if (!_ownedSessions.contains(session))
                return;
            (menu ? _spiritHealerMenus : _spiritHealerConfirmations)[session] = std::move(frame);
        }
        catch (std::exception const&)
        {
            // Only an actual, decoded normal server dialog can authorize recovery.
        }
    }

    Json::object RecoverySnapshot(Player* player)
    {
        RefreshSpiritHealerFrames(player);
        Json::object result{{"is_ghost", IsReleasedGhost(player)},
            {"spirit_healer_confirmation", nullptr}, {"receipt", nullptr}};
        std::lock_guard<std::mutex> lock(_eventMutex);
        if (auto found = _spiritHealerConfirmations.find(player->GetSession());
            found != _spiritHealerConfirmations.end())
        {
            SpiritHealerFrame const& frame = found->second;
            auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(
                frame.received + std::chrono::seconds(30) - std::chrono::steady_clock::now()).count();
            std::string guid = std::to_string(frame.source.GetRawValue());
            result["spirit_healer_confirmation"] = Json::object{{"target_guid", guid}, {"available", true},
                {"received_at", frame.receivedAt}, {"remaining_ms", std::max<int64>(0, remaining)},
                {"next_action", Json::object{{"type", "spirit_healer_activate"}, {"target_guid", guid}}}};
        }
        if (auto found = _spiritRecoveryReceipts.find(player->GetSession()); found != _spiritRecoveryReceipts.end())
            result["receipt"] = found->second;
        return result;
    }

    Json::object SpiritHealerAction(Json::object const& request, Json::object const& action,
        Actor& actor, Player* player, std::string const& type)
    {
        ObjectGuid target(GuidNumber(action, "target_guid"));
        RefreshSpiritHealerFrames(player);
        Creature* npc = SpiritHealerNpc(player, target);
        if (!npc)
            return Error(request, "invalid_spirit_healer",
                "Recovery requires a released ghost and a visible Spirit Healer in normal range and line of sight");
        std::string guid = std::to_string(target.GetRawValue());
        if (type == "interact")
        {
            ClearSpiritHealerFrames(actor.session.get());
            player->SetSelection(target);
            WorldPacket packet(CMSG_GOSSIP_HELLO, 8);
            packet << target;
            actor.session->HandleGossipHelloOpcode(packet);
            return Response(request, true, {{"status", "accepted"}, {"request_id", Text(request, "id")},
                {"target_guid", guid}, {"recovery", RecoverySnapshot(player)}});
        }
        if (type == "gossip_select")
        {
            if (!player->PlayerTalkClass || !action.if_contains("menu_id") || !action.if_contains("option_id"))
                return Error(request, "invalid_gossip", "Choose an explicit advertised Spirit Healer menu option");
            uint32 menuId = Unsigned(action, "menu_id");
            uint32 optionId = Unsigned(action, "option_id");
            GossipMenu const& menu = player->PlayerTalkClass->GetGossipMenu();
            GossipMenuItem const* option = menu.GetItem(optionId);
            auto frame = CurrentSpiritHealerFrame(actor.session.get(), true);
            bool captured = frame && frame->source == target && frame->menu == menuId
                && frame->options.contains(optionId) && SpiritHealerFrameCurrent(player, *frame);
            if (!captured || menu.GetSenderGUID() != target || menu.GetMenuId() != menuId || !option
                || option->IsCoded || option->OptionType != GOSSIP_OPTION_SPIRITHEALER || !menu.GetItemData(optionId))
                return Error(request, "stale_gossip", "Choose the current normal Spirit Healer recovery option");
            ClearSpiritHealerFrames(actor.session.get());
            WorldPacket packet(CMSG_GOSSIP_SELECT_OPTION, 16);
            packet << target << menuId << optionId;
            actor.session->HandleGossipSelectOptionOpcode(packet);
            return Response(request, true, {{"status", "accepted"}, {"request_id", Text(request, "id")},
                {"target_guid", guid}, {"menu_id", menuId}, {"option_id", optionId},
                {"recovery", RecoverySnapshot(player)}});
        }
        auto frame = CurrentSpiritHealerFrame(actor.session.get(), false);
        bool confirmed = frame && frame->source == target && SpiritHealerFrameCurrent(player, *frame);
        if (!confirmed)
            return Error(request, "spirit_healer_confirmation_required",
                "First open and select the normal Spirit Healer dialog; its confirmation expires after 30 seconds");
        ClearSpiritHealerFrames(actor.session.get());
        std::map<ObjectGuid, std::pair<uint32, uint32>> durability;
        auto remember = [&durability, player](Item* item)
        {
            if (CarriedItem(player, item) && item->GetUInt32Value(ITEM_FIELD_MAXDURABILITY))
                durability[item->GetGUID()] = {item->GetUInt32Value(ITEM_FIELD_DURABILITY),
                    item->GetUInt32Value(ITEM_FIELD_MAXDURABILITY)};
        };
        for (uint8 slot = 0; slot < INVENTORY_SLOT_ITEM_END; ++slot)
            remember(player->GetItemByPos(INVENTORY_SLOT_BAG_0, slot));
        for (uint8 bag = INVENTORY_SLOT_BAG_START; bag < INVENTORY_SLOT_BAG_END; ++bag)
            if (Bag* container = player->GetBagByPos(bag))
                for (uint32 slot = 0; slot < std::min(container->GetBagSize(), uint32(MAX_BAG_SIZE)); ++slot)
                    remember(container->GetItemByPos(uint8(slot)));
        bool aliveBefore = player->IsAlive();
        bool ghostBefore = IsReleasedGhost(player);
        uint32 healthBefore = player->GetHealth();
        float lossRate = sWorld->getRate(RATE_DURABILITY_LOSS_ON_SPIRIT_RESURRECT);
        WorldPacket packet(CMSG_SPIRIT_HEALER_ACTIVATE, 8);
        packet << target;
        actor.session->HandleSpiritHealerActivateOpcode(packet);
        bool aliveAfter = player->IsAlive();
        bool ghostAfter = IsReleasedGhost(player);
        bool recovered = !aliveBefore && ghostBefore && aliveAfter && !ghostAfter;
        Json::array changes;
        for (auto const& [itemGuid, before] : durability)
            if (Item* item = player->GetItemByGuid(itemGuid); CarriedItem(player, item)
                && item->GetUInt32Value(ITEM_FIELD_DURABILITY) != before.first)
                changes.emplace_back(Json::object{{"item_guid", std::to_string(itemGuid.GetRawValue())},
                    {"before", before.first}, {"after", item->GetUInt32Value(ITEM_FIELD_DURABILITY)},
                    {"max_durability", before.second}});
        Json::object receipt{{"request_id", Text(request, "id")}, {"target_guid", guid},
            {"status", recovered ? "completed" : "failed"},
            {"reason", recovered ? "" : "normal_handler_did_not_restore_life"},
            {"life_changed", aliveBefore != aliveAfter}, {"alive_before", aliveBefore}, {"alive_after", aliveAfter},
            {"is_ghost_before", ghostBefore}, {"is_ghost_after", ghostAfter},
            {"health_before", healthBefore}, {"health_after", player->GetHealth()},
            {"durability_loss_rate_percent", lossRate}, {"durability_changes", std::move(changes)},
            {"resurrection_sickness", nullptr}};
        if (Aura* sickness = player->GetAura(uint32(RecoverySpell::ResurrectionSickness)))
            receipt["resurrection_sickness"] = Json::object{{"spell_id", uint32(RecoverySpell::ResurrectionSickness)},
                {"duration_ms", sickness->GetDuration()}, {"max_duration_ms", sickness->GetMaxDuration()}};
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            _spiritRecoveryReceipts[actor.session.get()] = receipt;
        }
        return Response(request, true, {{"status", recovered ? "completed" : "failed"},
            {"reason", recovered ? "" : "normal_handler_did_not_restore_life"},
            {"request_id", Text(request, "id")}, {"recovery_receipt", std::move(receipt)}});
    }

    void QuestRewarded(Player* player, Quest const* quest)
    {
        GuardActionContext* context = CurrentGuardAction;
        if (context && player && quest && context->owner == player->GetGUID()
            && context->quest == quest->GetQuestId())
        {
            context->questRewarded = true;
            std::lock_guard<std::mutex> lock(_eventMutex);
            for (auto* frames : {&_questMenus, &_questDialogs})
                if (auto found = frames->find(player->GetSession()); found != frames->end()
                    && found->second.quest == quest->GetQuestId())
                    frames->erase(found);
        }
    }

    void ClearQuestFrames(WorldSession* session)
    {
        std::lock_guard<std::mutex> lock(_eventMutex);
        _questMenus.erase(session);
        _questDialogs.erase(session);
    }

    Json::array ReadQuestItems(WorldPacket& packet, bool choices, uint32 maximum)
    {
        uint32 count;
        packet >> count;
        if (count > maximum)
            throw std::runtime_error("Quest item count exceeds the normal window limit");
        Json::array items;
        for (uint32 index = 0; index < count; ++index)
        {
            uint32 item, amount, display;
            packet >> item >> amount >> display;
            Json::object row{{"item_id", item}, {"count", amount}, {"display_id", display}};
            if (choices)
                row["reward_index"] = index;
            items.emplace_back(std::move(row));
        }
        return items;
    }

    bool CaptureQuestFrame(WorldSession* session, WorldPacket const& packet)
    {
        try
        {
            WorldPacket copy(packet);
            QuestFrame frame;
            copy >> frame.source;
            if (frame.source.IsPlayer())
            {
                ClearQuestFrames(session);
                return false; // Shared quests have their existing separate confirmation path.
            }
            frame.opened = std::chrono::steady_clock::now();
            bool menu = packet.GetOpcode() == SMSG_GOSSIP_MESSAGE
                || packet.GetOpcode() == SMSG_QUESTGIVER_QUEST_LIST;
            if (menu)
            {
                frame.phase = "menu";
                uint32 count;
                if (packet.GetOpcode() == SMSG_GOSSIP_MESSAGE)
                {
                    uint32 menuId, textId;
                    copy >> menuId >> textId >> count;
                    if (count > 64)
                        throw std::runtime_error("Gossip option count exceeds the bridge window limit");
                    for (uint32 index = 0; index < count; ++index)
                    {
                        uint32 option, cost;
                        uint8 icon, coded;
                        std::string text, confirmation;
                        copy >> option >> icon >> coded >> cost >> text >> confirmation;
                    }
                    copy >> count;
                }
                else
                {
                    std::string greeting;
                    uint32 delay, emote;
                    uint8 size;
                    copy >> greeting >> delay >> emote >> size;
                    count = size;
                }
                if (count > 64)
                    throw std::runtime_error("Quest menu exceeds the bridge window limit");
                for (uint32 index = 0; index < count; ++index)
                {
                    uint32 quest, icon, flags;
                    int32 level;
                    uint8 repeatable;
                    std::string title;
                    copy >> quest >> icon >> level >> flags >> repeatable >> title;
                    frame.rows.emplace_back(Json::object{{"id", quest}, {"icon", icon},
                        {"level", level}, {"flags", flags}, {"repeatable", repeatable != 0},
                        {"title", title.substr(0, 256)}});
                }
            }
            else
            {
                bool details = packet.GetOpcode() == SMSG_QUESTGIVER_QUEST_DETAILS;
                if (details)
                {
                    ObjectGuid divider;
                    copy >> divider;
                }
                std::string title, text, objectives;
                copy >> frame.quest >> title >> text;
                frame.fields["title"] = title.substr(0, 256);
                frame.fields["text"] = text.substr(0, 4096);
                frame.fields["text_truncated"] = text.size() > 4096;
                uint32 flags, suggested;
                if (details)
                {
                    frame.phase = "details";
                    uint8 accept, finished;
                    copy >> objectives >> accept >> flags >> suggested >> finished;
                    frame.fields["activate_accept"] = accept != 0;
                    frame.fields["objective_text"] = objectives.substr(0, 2048);
                    frame.fields["objective_text_truncated"] = objectives.size() > 2048;
                }
                else if (packet.GetOpcode() == SMSG_QUESTGIVER_OFFER_REWARD)
                {
                    frame.phase = "offer_reward";
                    uint8 next;
                    uint32 emotes;
                    copy >> next >> flags >> suggested >> emotes;
                    if (emotes > QUEST_EMOTE_COUNT)
                        throw std::runtime_error("Quest reward emote count exceeds the normal limit");
                    for (uint32 index = 0; index < emotes; ++index)
                    {
                        uint32 delay, emote;
                        copy >> delay >> emote;
                    }
                }
                else
                {
                    frame.phase = "request_items";
                    uint32 unknown, emote, close, money, complete;
                    copy >> unknown >> emote >> close >> flags >> suggested >> money;
                    frame.fields["money_required"] = money;
                    frame.fields["required_items"] = ReadQuestItems(copy, false, QUEST_ITEM_OBJECTIVES_COUNT);
                    copy >> complete;
                    frame.fields["can_complete"] = complete == 3;
                }
                frame.fields["flags"] = flags;
                frame.fields["rewards_hidden"] = details && (flags & QUEST_FLAGS_HIDDEN_REWARDS) != 0;
                frame.fields["rewards_visible"] = frame.phase != "request_items"
                    && !frame.fields.at("rewards_hidden").as_bool();
                frame.fields["suggested_players"] = suggested;
                if (frame.phase == "offer_reward")
                    frame.fields["can_complete"] = true;
                if (frame.phase != "request_items")
                {
                    frame.fields["choice_rewards"] = ReadQuestItems(copy, true, QUEST_REWARD_CHOICES_COUNT);
                    frame.fields["fixed_rewards"] = ReadQuestItems(copy, false, QUEST_REWARDS_COUNT);
                    int32 money;
                    uint32 xp;
                    copy >> money >> xp;
                    frame.fields["money_reward"] = money > 0 ? uint32(money) : 0;
                    frame.fields["money_required"] = money < 0 ? uint32(-int64(money)) : 0;
                    frame.fields["xp_reward"] = xp;
                }
                frame.rows.emplace_back(Json::object{{"id", frame.quest}, {"title", title.substr(0, 256)},
                    {"icon", details ? 2 : 4}});
            }
            std::lock_guard<std::mutex> lock(_eventMutex);
            if (!_ownedSessions.contains(session))
                return false;
            frame.revision = ++_questFrameSequence;
            _vendorMenus.erase(session);
            _trainerMenus.erase(session);
            _questMenus[session] = frame;
            if (menu)
                _questDialogs.erase(session);
            else
                _questDialogs[session] = std::move(frame);
            return true;
        }
        catch (std::exception const&)
        {
            ClearQuestFrames(session);
            return false;
        }
    }

    std::optional<QuestFrame> CurrentQuestFrame(WorldSession* session, bool dialog)
    {
        std::lock_guard<std::mutex> lock(_eventMutex);
        auto const& frames = dialog ? _questDialogs : _questMenus;
        auto found = frames.find(session);
        return found == frames.end() ? std::nullopt : std::optional<QuestFrame>(found->second);
    }

    Object* QuestSource(Player* player, ObjectGuid guid, uint32 questId = 0)
    {
        if (guid.IsItem())
        {
            Item* item = player->GetItemByGuid(guid);
            if (!CarriedItem(player, item) || !item->GetTemplate()->StartQuest
                || (questId && item->GetTemplate()->StartQuest != questId)
                || !player->CanInteractWithQuestGiver(item))
                return nullptr;
            return item;
        }
        WorldObject* source = ObjectAccessor::GetWorldObject(*player, guid);
        if (!source || (!source->IsCreature() && !source->IsGameObject()) || !player->CanSeeOrDetect(source)
            || !player->IsWithinDistInMap(source, INTERACTION_DISTANCE) || !player->IsWithinLOSInMap(source)
            || !player->CanInteractWithQuestGiver(source))
            return nullptr;
        return source;
    }

    bool QuestFrameAvailable(Player* player, QuestFrame const& frame)
    {
        return std::chrono::steady_clock::now() - frame.opened <= std::chrono::minutes(2)
            && QuestSource(player, frame.source, frame.quest);
    }

    Json::object QuestRelations(Player* player, WorldObject* source)
    {
        Json::array turnIns;
        for (uint16 slot = 0; slot < MAX_QUEST_LOG_SIZE; ++slot)
            if (uint32 quest = player->GetQuestSlotQuestId(slot); quest && source->hasInvolvedQuest(quest))
                turnIns.emplace_back(quest);
        QuestGiverStatus status = player->GetQuestDialogStatus(source);
        return {{"quest_status", uint32(status)}, {"quest_status_name", QuestGiverStatusName(status)},
            {"turn_in_quest_ids", std::move(turnIns)}};
    }

    Json::value QuestDialogSnapshot(Player* player)
    {
        auto frame = CurrentQuestFrame(player->GetSession(), true);
        if (!frame)
            return nullptr;
        Json::object result = frame->fields;
        bool available = QuestFrameAvailable(player, *frame);
        result["target_guid"] = std::to_string(frame->source.GetRawValue());
        result["quest_id"] = frame->quest;
        result["phase"] = frame->phase;
        result["available"] = available;
        result["stale"] = !available;
        result["revision"] = frame->revision;
        result["quest_status"] = uint32(player->GetQuestStatus(frame->quest));
        result["quest_status_name"] = QuestStatusName(player->GetQuestStatus(frame->quest));
        for (char const* key : {"choice_rewards", "fixed_rewards"})
        {
            Json::array enriched;
            if (auto rows = result.if_contains(key); rows && rows->is_array())
                for (auto const& value : rows->as_array())
                {
                    Json::object row = value.as_object();
                    if (ItemTemplate const* info = sObjectMgr->GetItemTemplate(Unsigned(row, "item_id")))
                    {
                        Json::object facts = ItemFacts(player, info);
                        for (auto const& field : row)
                            facts[field.key()] = field.value();
                        row = std::move(facts);
                    }
                    enriched.emplace_back(std::move(row));
                }
            result[key] = std::move(enriched);
        }
        if (auto required = result.if_contains("required_items"); required && required->is_array())
            for (auto& value : required->as_array())
            {
                value.as_object()["current"] = player->GetItemCount(Unsigned(value.as_object(), "item_id"), false);
                if (ItemTemplate const* info = sObjectMgr->GetItemTemplate(Unsigned(value.as_object(), "item_id")))
                    value.as_object()["name"] = info->Name1;
            }
        return result;
    }

    Json::array QuestMenuSnapshot(Player* player)
    {
        Json::array result;
        auto frame = CurrentQuestFrame(player->GetSession(), false);
        if (!frame)
            return result;
        bool available = QuestFrameAvailable(player, *frame);
        Object* source = available ? QuestSource(player, frame->source, frame->quest) : nullptr;
        for (auto const& value : frame->rows)
        {
            Json::object row = value.as_object();
            uint32 quest = Unsigned(row, "id");
            bool start = source && source->hasQuest(quest);
            bool turnIn = source && source->hasInvolvedQuest(quest);
            row["target_guid"] = std::to_string(frame->source.GetRawValue());
            row["quest_status"] = uint32(player->GetQuestStatus(quest));
            row["quest_status_name"] = QuestStatusName(player->GetQuestStatus(quest));
            row["relation"] = start ? (turnIn ? "both" : "start") : (turnIn ? "turn_in" : "none");
            row["available"] = available;
            result.emplace_back(std::move(row));
        }
        return result;
    }

    void CaptureCommerceMenu(WorldSession* session, WorldPacket const& packet, bool trainer)
    {
        try
        {
            WorldPacket copy(packet);
            CommerceMenu menu;
            copy >> menu.source;
            menu.opened = std::chrono::steady_clock::now();
            if (trainer)
            {
                uint32 type;
                copy >> type >> menu.total;
                if (menu.total > 4096)
                    return;
                for (uint32 index = 0; index < menu.total; ++index)
                {
                    uint32 spell, skill, rank;
                    uint8 state, level;
                    int32 cost, points, profession;
                    uint32 required[3];
                    copy >> spell >> state >> cost >> points >> profession >> level >> skill >> rank;
                    for (uint32& ability : required)
                        copy >> ability;
                    if (menu.rows.size() < 1024)
                    {
                        Json::array abilities;
                        for (uint32 ability : required)
                            if (ability)
                                abilities.emplace_back(ability);
                        menu.rows.emplace_back(Json::object{{"spell_id", spell}, {"state", state}, {"cost", cost},
                            {"required_level", level}, {"required_skill", skill}, {"required_skill_rank", rank},
                            {"required_spells", std::move(abilities)}, {"profession_points", profession}});
                    }
                }
            }
            else
            {
                uint8 count;
                copy >> count;
                menu.total = count;
                for (uint32 index = 0; index < count; ++index)
                {
                    uint32 slot, item, display, stock, price, durability, bundle, extended;
                    copy >> slot >> item >> display >> stock >> price >> durability >> bundle >> extended;
                    menu.rows.emplace_back(Json::object{{"vendor_slot", slot}, {"item_id", item},
                        {"price", price}, {"buy_count", bundle}, {"stock", stock == 0xFFFFFFFF ? -1 : int64(stock)},
                        {"extended_cost_id", extended}});
                }
            }
            std::lock_guard<std::mutex> lock(_eventMutex);
            auto& target = trainer ? _trainerMenus : _vendorMenus;
            if (!_ownedSessions.contains(session))
                return;
            auto found = target.find(session);
            menu.revision = ++_commerceSequence;
            if (found != target.end() && found->second.source == menu.source)
                menu.page = found->second.page;
            target[session] = std::move(menu);
            _questMenus.erase(session);
            _questDialogs.erase(session);
        }
        catch (std::exception const&)
        {
            // A malformed outgoing menu cannot authorize a purchase.
        }
    }

    CommerceMenu CommerceMenuFor(WorldSession* session, bool trainer)
    {
        std::lock_guard<std::mutex> lock(_eventMutex);
        auto& menus = trainer ? _trainerMenus : _vendorMenus;
        auto found = menus.find(session);
        return found != menus.end() ? found->second : CommerceMenu{};
    }

    bool CommerceMenuCurrent(Player* player, ObjectGuid source, bool trainer, CommerceMenu& menu)
    {
        menu = CommerceMenuFor(player->GetSession(), trainer);
        return menu.source == source && menu.revision
            && std::chrono::steady_clock::now() - menu.opened < std::chrono::minutes(2);
    }

    Creature* CommerceNpc(Player* player, ObjectGuid guid, NPCFlags flags)
    {
        Creature* npc = player->GetNPCIfCanInteractWith(guid, flags);
        return npc && player->CanSeeOrDetect(npc) && player->IsWithinLOSInMap(npc) ? npc : nullptr;
    }

    Json::value CommerceSnapshot(Player* player, bool trainer)
    {
        CommerceMenu menu = CommerceMenuFor(player->GetSession(), trainer);
        if (!menu.source)
            return nullptr;
        Creature* npc = CommerceNpc(player, menu.source, trainer ? UNIT_NPC_FLAG_TRAINER : UNIT_NPC_FLAG_VENDOR);
        bool current = npc && std::chrono::steady_clock::now() - menu.opened < std::chrono::minutes(2);
        Json::object result{{"target_guid", std::to_string(menu.source.GetRawValue())},
            {"name", npc ? npc->GetName() : ""}, {"available", current}, {"page", menu.page}, {"page_size", 24},
            {"revision", menu.revision}, {trainer ? "total_spells" : "total_items", menu.total},
            {"bounded_rows", menu.rows.size()}, {"has_more", (menu.page + 1) * 24 < menu.rows.size()}};
        Json::array rows;
        if (current)
            for (size_t index = size_t(menu.page) * 24; index < menu.rows.size() && rows.size() < 24; ++index)
            {
                Json::object row = menu.rows[index].as_object();
                if (trainer)
                {
                    SpellInfo const* info = sSpellMgr->GetSpellInfo(Unsigned(row, "spell_id"));
                    row["name"] = info ? info->SpellName[0] : "";
                    Json::array learned;
                    if (info)
                        for (auto const& effect : info->Effects)
                            if (effect.IsEffect(SPELL_EFFECT_LEARN_SPELL))
                                learned.emplace_back(effect.TriggerSpell);
                    row["learned_spells"] = std::move(learned);
                    row["affordable"] = player->GetMoney() >= Number(row, "cost");
                }
                else
                {
                    uint32 itemId = Unsigned(row, "item_id");
                    if (ItemTemplate const* info = sObjectMgr->GetItemTemplate(itemId))
                        for (auto const& member : ItemFacts(player, info))
                            if (!row.contains(member.key()))
                                row[member.key()] = member.value();
                    uint32 extended = Unsigned(row, "extended_cost_id");
                    Json::object cost{{"id", extended}, {"honor", 0}, {"arena", 0},
                        {"personal_rating", 0}, {"arena_slot", 0}, {"required_items", Json::array{}}};
                    if (ItemExtendedCostEntry const* entry = sItemExtendedCostStore.LookupEntry(extended))
                    {
                        cost["honor"] = entry->reqhonorpoints;
                        cost["arena"] = entry->reqarenapoints;
                        cost["personal_rating"] = entry->reqpersonalarenarating;
                        cost["arena_slot"] = entry->reqarenaslot;
                        Json::array required;
                        for (uint32 slot = 0; slot < MAX_ITEM_EXTENDED_COST_REQUIREMENTS; ++slot)
                            if (entry->reqitem[slot])
                                required.emplace_back(Json::object{{"item_id", entry->reqitem[slot]},
                                    {"count", entry->reqitemcount[slot]}});
                        cost["required_items"] = std::move(required);
                    }
                    row["extended_cost"] = std::move(cost);
                    row["gold_affordable"] = player->GetMoney() >= Number(row, "price");
                }
                rows.emplace_back(std::move(row));
            }
        result[trainer ? "spells" : "items"] = std::move(rows);
        return result;
    }

    bool OwnsEmoteObserver(Player const* player)
    {
        WorldSession* session = player ? player->GetSession() : nullptr;
        if (!session)
            return false;
        std::lock_guard<std::mutex> lock(_eventMutex);
        auto owned = _ownedCharacters.find(session);
        return IsOwnedEmoteObserver(session->IsHeadless(), _ownedSessions.contains(session),
            player->GetGUID().GetRawValue(), owned == _ownedCharacters.end() ? 0 : owned->second.GetRawValue());
    }

    void CaptureTextEmote(Player* sender, uint32 emote, uint32 variant, ObjectGuid target)
    {
        if (!sender || !sEmotesTextStore.LookupEntry(emote))
            return;
        std::vector<ObjectGuid> observers;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            _emoteCorrelations.ForgetSender(sender->GetGUID().GetRawValue());
            for (auto const& [session, identity] : _ownedCharacters)
            {
                observers.push_back(identity);
                if (observers.size() >= 32)
                    break;
            }
        }
        std::vector<TextEmoteCorrelation> records;
        for (auto identity : observers)
        {
            Player* observer = ObjectAccessor::GetPlayer(sender->GetMap(), identity);
            if (!observer || !OwnsEmoteObserver(observer) || !observer->HaveAtClient(sender)
                || !observer->CanSeeOrDetect(sender)
                || !observer->IsWithinDistInMap(sender, sWorld->getFloatConfig(CONFIG_LISTEN_RANGE_TEXTEMOTE)))
                continue;
            TextEmoteCorrelation record;
            record.Observer = identity.GetRawValue();
            record.Sender = sender->GetGUID().GetRawValue();
            record.Emote = emote;
            record.Variant = variant;
            Unit* unit = target ? ObjectAccessor::GetUnit(*sender, target) : nullptr;
            // The core can render an empty target name when a nonzero request
            // GUID fails lookup. Only an explicit zero is authoritative untargeted.
            record.HasTarget = bool(target);
            record.TargetKnown = !target;
            if (unit && observer->HaveAtClient(unit) && observer->CanSeeOrDetect(unit)
                && observer->IsWithinDistInMap(unit, 90))
            {
                record.TargetKnown = true;
                record.Target = unit->GetGUID().GetRawValue();
                record.TargetIsPlayer = unit->IsPlayer();
            }
            records.push_back(record);
        }
        // This transient hook context never emits events. Only a matching packet
        // actually delivered to an owned headless session can consume it.
        std::lock_guard<std::mutex> lock(_eventMutex);
        uint64 now = EmoteMilliseconds();
        for (auto const& record : records)
            _emoteCorrelations.Remember(record, now);
    }

    void Packet(WorldSession* session, WorldPacket const& packet)
    {
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            if (!_ownedSessions.contains(session))
                return;
        }
        if (packet.GetOpcode() == SMSG_CHAR_CREATE && packet.size())
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            _creationResults[session] = packet[0];
            return;
        }
        Player* player = session->GetPlayer();
        if (!player || !session->IsHeadless())
            return;
        if (CurrentGuardAction && CurrentGuardAction->owner == player->GetGUID())
        {
            // Preserve a normal spell or scripted player gesture instead of
            // overwriting it with the bridge's brief interaction feedback.
            if (packet.GetOpcode() == SMSG_SPELL_START || packet.GetOpcode() == SMSG_SPELL_GO)
                CurrentGuardAction->interactionVisualObserved = true;
            else if (packet.GetOpcode() == SMSG_EMOTE && packet.size() >= 12)
            {
                WorldPacket copy(packet);
                uint32 emote;
                ObjectGuid actor;
                copy >> emote >> actor;
                if (actor == player->GetGUID())
                    CurrentGuardAction->interactionVisualObserved = true;
            }
        }
        Json::object event;
        switch (packet.GetOpcode())
        {
            case SMSG_TRADE_STATUS:
                CaptureTradeStatus(session, packet);
                return;
            case SMSG_TRADE_STATUS_EXTENDED:
                // Read current TradeData at the next world-thread safe point.
                return;
            case SMSG_TEXT_EMOTE:
                event = TextEmoteEvent(session, packet);
                break;
            case SMSG_MESSAGECHAT:
            case SMSG_GM_MESSAGECHAT:
                event = ChatEvent(packet);
                CaptureQuestAbandonCommand(session, event);
                CaptureProtectionClear(session, event);
                break;
            case MSG_RAID_TARGET_UPDATE:
                CaptureMarkerChange(session, packet);
                return;
            case SMSG_GROUP_INVITE:
                event = CapturePartyInvite(session, packet);
                break;
            case SMSG_GOSSIP_MESSAGE:
                CaptureSpiritHealerFrame(session, packet, true);
                CaptureQuestFrame(session, packet);
                event["type"] = "gossip";
                break;
            case SMSG_SPIRIT_HEALER_CONFIRM:
                CaptureSpiritHealerFrame(session, packet, false);
                event["type"] = "spirit_healer_confirmation";
                break;
            case SMSG_GOSSIP_COMPLETE:
                ClearSpiritHealerFrames(session);
                ClearQuestFrames(session);
                return;
            case SMSG_QUESTGIVER_QUEST_LIST:
                ClearSpiritHealerFrames(session);
                CaptureQuestFrame(session, packet);
                event["type"] = "quest_menu";
                break;
            case SMSG_LIST_INVENTORY:
                ClearSpiritHealerFrames(session);
                CaptureCommerceMenu(session, packet, false);
                return;
            case SMSG_TRAINER_LIST:
                ClearSpiritHealerFrames(session);
                CaptureCommerceMenu(session, packet, true);
                return;
            case SMSG_QUESTGIVER_QUEST_DETAILS:
                ClearSpiritHealerFrames(session);
                CaptureQuestFrame(session, packet);
                event = CaptureSharedQuest(session, packet, false);
                break;
            case SMSG_QUEST_CONFIRM_ACCEPT:
                ClearSpiritHealerFrames(session);
                ClearQuestFrames(session);
                event = CaptureSharedQuest(session, packet, true);
                break;
            case SMSG_QUESTGIVER_OFFER_REWARD:
                ClearSpiritHealerFrames(session);
                CaptureQuestFrame(session, packet);
                event["type"] = "quest_reward";
                break;
            case SMSG_QUESTGIVER_REQUEST_ITEMS:
                ClearSpiritHealerFrames(session);
                CaptureQuestFrame(session, packet);
                event["type"] = "quest_request_items";
                break;
            case SMSG_QUESTGIVER_QUEST_COMPLETE:
                if (packet.size() >= 4)
                {
                    WorldPacket copy(packet);
                    uint32 quest;
                    copy >> quest;
                    {
                        std::lock_guard<std::mutex> lock(_eventMutex);
                        _rewardReceipts[session] = quest;
                        _questMenus.erase(session);
                        _questDialogs.erase(session);
                    }
                    event["type"] = "quest_rewarded";
                    event["quest_id"] = quest;
                }
                break;
            case SMSG_LOOT_RESPONSE:
                CaptureLoot(session, packet);
                event["type"] = "loot_window";
                break;
            case SMSG_INVENTORY_CHANGE_FAILURE:
                event["type"] = "inventory_error";
                break;
            case SMSG_CAST_FAILED:
                event["type"] = "cast_failed";
                break;
            case SMSG_SPELL_GO:
                event["type"] = "spell_go";
                break;
            case SMSG_LEVELUP_INFO:
                event["type"] = "level_up";
                break;
            default:
                return;
        }
        if (event.empty())
            return;
        event["opcode"] = uint32(packet.GetOpcode());
        RecordEvent(session, std::move(event));
    }

    void RecordEvent(WorldSession* session, Json::object event)
    {
        Player* player = session->GetPlayer();
        if (!player || !session->IsHeadless())
            return;
        Json::value recipient = nullptr;
        if (auto value = event.if_contains("journal_recipient_guid"))
        {
            recipient = *value;
            event.erase("journal_recipient_guid");
        }
        event["timestamp"] = Timestamp();
        std::lock_guard<std::mutex> lock(_eventMutex);
        if (!_ownedSessions.contains(session))
            return;
        event["id"] = ++_eventSequence;
        std::string type = Text(event, "type");
        if (type == "chat" || type == "text_emote")
        {
            bool addon = false;
            if (auto language = event.if_contains("language"); language && language->is_int64())
                addon = language->as_int64() == -1 || language->as_int64() == 4294967295LL;
            bool decodeError = false;
            if (auto value = event.if_contains("decode_error"); value && value->is_bool())
                decodeError = value->as_bool();
            auto& journal = _journals[player->GetName()];
            journal.observer = player->GetGUID();
            if (addon)
                ++journal.excludedAddon;
            if (decodeError)
                ++journal.excludedDecodeError;
            if (!addon && !decodeError)
            {
                Json::object payload = event;
                payload.erase("type");
                payload.erase("timestamp");
                payload.erase("id");
                ObjectGuid sender(GuidNumber(event, type == "chat" ? "sender_guid" : "actor_guid"));
                std::string observer = std::to_string(player->GetGUID().GetRawValue());
                payload["direction"] = sender == player->GetGUID() ? "outgoing" : "incoming";
                payload["actor_is_player"] = sender.IsPlayer();
                if (type == "chat")
                {
                    payload["speaker"] = Text(event, "sender");
                    payload["recipient_guid"] = recipient;
                    payload["directed_at_self"] = recipient.is_string()
                        ? Json::value(Text(payload, "recipient_guid") == observer)
                        : Json::value(nullptr);
                }
                else
                {
                    auto target = event.if_contains("target_guid");
                    payload["directed_at_self"] = target && target->is_string()
                        && Text(event, "target_guid_source") == "normal_text_emote_hook"
                        ? Json::value(Text(event, "target_guid") == observer)
                        : Json::value(nullptr);
                }
                JournalAppendLocked(player, type, std::move(payload), sender);
            }
        }
        auto& queue = _events[player->GetGUID()];
        queue.push_back(std::move(event));
        if (queue.size() > 128)
            queue.pop_front();
    }

    bool CanReceive(WorldSession* session, WorldPacket const& packet)
    {
        if (!session || packet.GetOpcode() != CMSG_PLAYER_LOGIN || packet.size() < 8)
            return true;
        WorldPacket copy(packet);
        ObjectGuid guid;
        copy >> guid;
        bool owned = false;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            for (auto const& [owner, character] : _ownedCharacters)
                if (owner != session && character == guid)
                {
                    owned = true;
                    break;
                }
        }
        if (!owned)
            return true;
        session->KickPlayer("Character controlled by Presence; detach before logging in");
        return false;
    }

    Player* OwnedPlayer(Unit const* source)
    {
        Player* player = source ? source->GetAffectingPlayer() : nullptr;
        if (!player || player->GetName() != _protectedCharacter || !player->GetSession()
            || !player->GetSession()->IsHeadless())
            return nullptr;
        std::lock_guard<std::mutex> lock(_eventMutex);
        auto owned = _ownedCharacters.find(player->GetSession());
        return owned != _ownedCharacters.end() && owned->second == player->GetGUID() ? player : nullptr;
    }

    ProtectionBinding BindingFor(Player const* owner)
    {
        std::lock_guard<std::mutex> lock(_eventMutex);
        auto found = owner ? _protections.find(owner->GetGUID()) : _protections.end();
        return found != _protections.end() ? found->second : ProtectionBinding{};
    }

    ObjectGuid ProtectedGuid(Player const* owner)
    {
        if (!owner || owner->GetName() != _protectedCharacter)
            return ObjectGuid::Empty;
        ProtectionBinding binding = BindingFor(owner);
        if (binding.policy.target)
            return ObjectGuid(binding.policy.target);
        if (binding.policy.protector)
            return ObjectGuid::Empty;
        // Protect immediately during the first map tick; Update durably binds it at the safe point.
        Group const* group = owner ? owner->GetGroup() : nullptr;
        ObjectGuid moon = group ? group->GetTargetIcon(4) : ObjectGuid::Empty;
        return TrustedProtector(owner) && moon.IsCreature() && moon.GetRawValue() != binding.policy.ignoredMoon
            ? moon : ObjectGuid::Empty;
    }

    bool ProtectionUncertain(Player const* owner)
    {
        if (!owner || owner->GetName() != _protectedCharacter)
            return false;
        ProtectionBinding binding = BindingFor(owner);
        return _protectionPersistenceError || (binding.policy.target && binding.recoveredDynamic);
    }

    Unit* ProtectedUnit(Player* owner)
    {
        ProtectionBinding binding = BindingFor(owner);
        if (binding.policy.target && binding.spawn)
        {
            if (owner->GetMapId() != binding.map || owner->GetInstanceId() != binding.instance)
                return nullptr;
            auto matches = owner->GetMap()->GetCreatureBySpawnIdStore().equal_range(binding.spawn);
            for (auto found = matches.first; found != matches.second; ++found)
                if (Creature* creature = found->second; creature && creature->GetEntry() == binding.entry)
                    return creature;
            return nullptr;
        }
        if (binding.recoveredDynamic)
            return nullptr;
        ObjectGuid guid = ProtectedGuid(owner);
        Unit* target = guid ? ObjectAccessor::GetUnit(*owner, guid) : nullptr;
        if (binding.entry && target && (target->GetMapId() != binding.map
            || target->GetInstanceId() != binding.instance || target->GetEntry() != binding.entry))
            return nullptr;
        return target;
    }

    bool BlocksDamage(Unit const* source, Unit const* target)
    {
        Player* owner = OwnedPlayer(source);
        if (!owner || !target)
            return false;
        ProtectionBinding binding = BindingFor(owner);
        if (ProtectionUncertain(owner))
            return true;
        if (binding.policy.target && binding.spawn)
            return target->IsCreature() && target->GetMapId() == binding.map
                && target->GetInstanceId() == binding.instance && target->GetEntry() == binding.entry
                && target->ToCreature()->GetSpawnId() == binding.spawn;
        return ProtectedGuid(owner) == target->GetGUID();
    }

    void CaptureTameAttempt(Spell* spell)
    {
        if (!spell || !spell->GetSpellInfo()->HasEffect(SPELL_EFFECT_TAMECREATURE))
            return;
        Player* tamer = spell->GetCaster()->ToPlayer();
        Group* group = tamer ? tamer->GetGroup() : nullptr;
        ObjectGuid target = spell->m_targets.GetUnitTargetGUID();
        if (!group || !target)
            return;
        bool watched = false;
        for (auto const& member : group->GetMemberSlots())
            if (Player* observer = ObjectAccessor::FindPlayer(member.guid); observer && OwnedPlayer(observer)
                && observer->IsWithinDistInMap(tamer, 90) && observer->CanSeeOrDetect(tamer))
            {
                watched = true;
                break;
            }
        if (!watched)
            return;
        std::lock_guard<std::mutex> lock(_eventMutex);
        if (_tameAttempts.size() >= MAXRAIDSIZE * 2 && !_tameAttempts.contains(tamer->GetGUID()))
            _tameAttempts.erase(_tameAttempts.begin());
        auto now = std::chrono::steady_clock::now();
        auto old = _tameAttempts.find(tamer->GetGUID());
        uint32 attempts = old != _tameAttempts.end() && old->second.group == group->GetGUID()
            && old->second.target == target && now - old->second.observed < std::chrono::seconds(60)
            ? std::min(old->second.attempts + 1, uint32(1000)) : 1;
        auto phases = old != _tameAttempts.end() && attempts > 1 ? old->second.phases
            : std::deque<std::pair<std::string, std::chrono::steady_clock::time_point>>{};
        phases.emplace_back("attempt", now);
        if (phases.size() > 8)
            phases.pop_front();
        _tameAttempts[tamer->GetGUID()] = {group->GetGUID(), tamer->GetGUID(), target,
            spell->GetSpellInfo()->Id, now, attempts, "attempt", std::move(phases), spell->m_cast_count};
    }

    void NoteTamePhase(Spell* spell, std::string const& phase)
    {
        if (!spell || !spell->GetSpellInfo()->HasEffect(SPELL_EFFECT_TAMECREATURE))
            return;
        auto now = std::chrono::steady_clock::now();
        std::lock_guard<std::mutex> lock(_eventMutex);
        auto found = _tameAttempts.find(spell->GetCaster()->GetGUID());
        if (found == _tameAttempts.end() || found->second.target != spell->m_targets.GetUnitTargetGUID()
            || found->second.spell != spell->GetSpellInfo()->Id || found->second.castCount != spell->m_cast_count
            || found->second.phase == phase)
            return;
        found->second.phase = phase;
        found->second.observed = now;
        found->second.phases.emplace_back(phase, now);
        if (found->second.phases.size() > 8)
            found->second.phases.pop_front();
    }

    bool AreaBenefitsWithheld(Player* owner)
    {
        if (!owner)
            return false;
        if (ProtectedGuid(owner) || ProtectionUncertain(owner))
            return true;
        TameAttempt attempt;
        bool active = false;
        return TameFor(owner, attempt, active);
    }

    bool BlocksBeneficial(Unit const* source, Unit const* target, SpellInfo const* info = nullptr)
    {
        Player* owner = OwnedPlayer(source);
        // A self-targeted persistent area aura can later assist the protected
        // human without passing through the original spell's target filter.
        if (owner && PositiveAreaAura(info) && AreaBenefitsWithheld(owner))
            return true;
        Player const* human = target ? target->ToPlayer() : nullptr;
        Group const* group = owner ? owner->GetGroup() : nullptr;
        ProtectionBinding binding = BindingFor(owner);
        if (owner && human && human != owner && (ProtectionUncertain(owner)
            || (binding.policy.target && binding.policy.protector == human->GetGUID().GetRawValue())))
            return true;
        if (!owner || !human || human == owner || !group || human->GetGroup() != group || OwnedPlayer(human))
            return false;
        if (ProtectedGuid(owner))
            return true;
        TameAttempt attempt;
        bool active = false;
        return TameFor(owner, attempt, active) && attempt.tamer == human->GetGUID();
    }

    bool BlocksSpell(Spell* spell, Unit const* target)
    {
        if (!spell)
            return false;
        SpellInfo const* info = spell->GetSpellInfo();
        Unit* actual = spell->GetCaster()->ToUnit();
        Unit* original = spell->GetOriginalCaster();
        if (PositiveAreaAura(info)
            && (BlocksBeneficial(actual, target, info) || BlocksBeneficial(original, target, info)))
            return true;
        if (!target)
            return false;
        bool reflection = info->HasAura(SPELL_AURA_REFLECT_SPELLS)
            || info->HasAura(SPELL_AURA_REFLECT_SPELLS_SCHOOL);
        Player* receiver = OwnedPlayer(target);
        // This is the protected character declining reflection on itself, not ownership of the buff caster.
        if (reflection && receiver && (ProtectedGuid(receiver) || ProtectionUncertain(receiver)))
            return true;
        if (BlocksDamage(actual, target) || BlocksDamage(original, target))
            return true;
        Player* owner = OwnedPlayer(actual);
        if (!owner)
            owner = OwnedPlayer(original);
        if (owner && ProtectedGuid(owner) && reflection)
            return true;
        return (info->IsPositive() || info->HasEffect(SPELL_EFFECT_HEAL)
            || info->HasEffect(SPELL_EFFECT_HEAL_PCT) || info->HasEffect(SPELL_EFFECT_HEAL_MAX_HEALTH))
            && (BlocksBeneficial(actual, target, info) || BlocksBeneficial(original, target, info));
    }

    void GuardIntervention(Unit const* source, Unit const* target, char const* hook, char const* reason,
        uint32 spell = 0, uint8 castCount = 0, Player* owner = nullptr)
    {
        try
        {
            if (!owner)
                owner = OwnedPlayer(source);
            if (!owner)
                return;
            ProtectionBinding binding = BindingFor(owner);
            ObjectGuid protectedTarget = ProtectedGuid(owner);
            uint64 protector = binding.policy.protector;
            if (!protector)
                protector = TrustedProtector(owner).GetRawValue();
            GuardActionContext* context = CurrentGuardAction;
            bool synchronous = context && context->owner == owner->GetGUID();
            Json::object event{{"type", "moon_guard_intervention"}, {"timestamp", Timestamp()},
                {"attribution", synchronous ? "synchronous_action" : "unattributed_execution"},
                {"owner_guid", std::to_string(owner->GetGUID().GetRawValue())},
                {"source_guid", std::to_string(source ? source->GetGUID().GetRawValue() : 0)},
                {"target_guid", std::to_string(target ? target->GetGUID().GetRawValue() : 0)},
                {"protected_target_guid", std::to_string(protectedTarget.GetRawValue())},
                {"protected_by_guid", std::to_string(protector)}, {"hook", hook},
                {"reason", ProtectionUncertain(owner) ? "protected_state_unavailable" : reason},
                {"spell_id", spell}, {"cast_count", castCount}};
            if (synchronous)
            {
                event["request_id"] = context->request;
                event["observed_sequence"] = context->observedSequence;
                event["action_type"] = context->action;
            }
            std::string key = std::string(hook) + ":" + Text(event, "source_guid") + ":" + Text(event, "target_guid")
                + ":" + Text(event, "protected_target_guid") + ":" + std::to_string(spell);
            std::lock_guard<std::mutex> lock(_eventMutex);
            if (!_ownedSessions.contains(owner->GetSession()))
                return;
            auto& telemetry = _guardTelemetry[owner->GetGUID()];
            if (!telemetry.window.Record(key, std::chrono::steady_clock::now(), synchronous))
                return;
            event["id"] = ++_guardEventSequence;
            event["guard_event_id"] = _guardEventSequence;
            if (synchronous)
            {
                if (context->interventions.size() < 16)
                    context->interventions.push_back(event);
                else
                    ++context->dropped;
            }
            telemetry.events.push_back(std::move(event));
            if (telemetry.events.size() > 64)
                telemetry.events.pop_front();
        }
        catch (std::exception const&)
        {
            // Diagnostics must never change the guard decision or interrupt its enforcement.
        }
    }

    void GuardSpellIntervention(Spell* spell, Unit const* target, char const* hook)
    {
        try
        {
            if (!spell)
                return;
            Unit* actual = spell->GetCaster()->ToUnit();
            Unit* original = spell->GetOriginalCaster();
            Player* owner = OwnedPlayer(actual);
            if (!owner)
                owner = OwnedPlayer(original);
            if (!owner)
                owner = OwnedPlayer(target);
            SpellInfo const* info = spell->GetSpellInfo();
            bool reflection = info->HasAura(SPELL_AURA_REFLECT_SPELLS)
                || info->HasAura(SPELL_AURA_REFLECT_SPELLS_SCHOOL);
            char const* reason = reflection ? "reflection_declined"
                : (BlocksBeneficial(actual, target, info) || BlocksBeneficial(original, target, info))
                    ? "beneficial_intervention_withheld" : "protected_target_effect";
            GuardIntervention(actual ? actual : original, target, hook, reason, info->Id, spell->m_cast_count, owner);
        }
        catch (std::exception const&)
        {
            // Diagnostics must never change the guard decision or interrupt its enforcement.
        }
    }

private:
    ObjectGuid TrustedProtector(Player const* player) const
    {
        Group const* group = player ? player->GetGroup() : nullptr;
        return group && CommandEqual(group->GetLeaderName(), "Aurenne")
            ? group->GetLeaderGUID() : ObjectGuid::Empty;
    }

    void LoadProtection()
    {
        try
        {
            if (!std::filesystem::exists(_protectionFile))
                return;
            if (std::filesystem::file_size(_protectionFile) > 2 * 1024 * 1024)
                throw std::runtime_error("Protection journal exceeds its bounded size");
            std::ifstream input(_protectionFile, std::ios::binary);
            if (!input)
                throw std::runtime_error("Cannot open protection journal");
            std::string line;
            while (std::getline(input, line))
            {
                if (line.empty() || line.size() > 4096)
                    throw std::runtime_error("Invalid protection journal record size");
                auto value = Json::parse(line);
                if (!value.is_object())
                    throw std::runtime_error("Invalid protection journal record");
                auto const& row = value.as_object();
                ProtectionBinding binding;
                if (Unsigned(row, "v") != 1)
                    throw std::runtime_error("Unsupported protection journal version");
                binding.actor = ObjectGuid(GuidNumber(row, "actor_guid"));
                binding.policy.protector = GuidNumber(row, "protected_by_guid");
                binding.policy.target = GuidNumber(row, "protected_target_guid");
                binding.policy.ignoredMoon = GuidNumber(row, "ignored_moon_guid");
                binding.protectorName = Text(row, "protected_by");
                binding.targetName = Text(row, "protected_target_name");
                binding.map = Unsigned(row, "map_id");
                binding.instance = Unsigned(row, "instance_id");
                binding.entry = Unsigned(row, "entry");
                binding.spawn = Unsigned(row, "spawn_id");
                binding.recoveredDynamic = binding.policy.target && !binding.spawn;
                if (!binding.actor.IsPlayer() || (binding.policy.target && (!binding.policy.protector
                    || !ObjectGuid(binding.policy.target).IsCreature()))
                    || (_protections.size() >= 64 && !_protections.contains(binding.actor)))
                    throw std::runtime_error("Invalid or excessive protection bindings");
                _protections[binding.actor] = std::move(binding);
            }
            if (!input.eof())
                throw std::runtime_error("Failed reading protection journal");
        }
        catch (std::exception const& exception)
        {
            _protectionPersistenceError = true;
            LOG_ERROR("module.presence", "Protection persistence unavailable: {}", exception.what());
        }
    }

    bool StoreProtection(ProtectionBinding const& binding)
    {
        if (_protectionPersistenceError)
            return false;
        Json::object row{{"v", 1}, {"actor_guid", std::to_string(binding.actor.GetRawValue())},
            {"protected_by_guid", std::to_string(binding.policy.protector)},
            {"protected_by", binding.protectorName}, {"protected_target_guid", std::to_string(binding.policy.target)},
            {"protected_target_name", binding.targetName},
            {"ignored_moon_guid", std::to_string(binding.policy.ignoredMoon)},
            {"map_id", binding.map}, {"instance_id", binding.instance}, {"entry", binding.entry},
            {"spawn_id", binding.spawn}};
        try
        {
            std::string line = Json::serialize(row) + "\n";
            if (std::filesystem::exists(_protectionFile)
                && std::filesystem::file_size(_protectionFile) + line.size() > 2 * 1024 * 1024)
                throw std::runtime_error("Protection journal is full");
            std::ofstream output(_protectionFile, std::ios::binary | std::ios::app);
            output << line;
            output.flush();
            if (!output)
                throw std::runtime_error("Cannot persist protection transition");
            std::lock_guard<std::mutex> lock(_eventMutex);
            _protections[binding.actor] = binding;
            return true;
        }
        catch (std::exception const& exception)
        {
            _protectionPersistenceError = true;
            LOG_ERROR("module.presence", "Protection persistence failed closed: {}", exception.what());
            return false;
        }
    }

    void DescribeProtectedTarget(Player* player, ProtectionBinding& binding)
    {
        if (!binding.policy.target)
            return;
        Unit* target = ObjectAccessor::GetUnit(*player, ObjectGuid(binding.policy.target));
        if (!target || !target->IsCreature())
            return;
        binding.targetName = target->GetName();
        binding.map = target->GetMapId();
        binding.instance = target->GetInstanceId();
        binding.entry = target->GetEntry();
        binding.spawn = target->ToCreature()->GetSpawnId();
        binding.recoveredDynamic = false;
    }

    void CaptureMarkerChange(WorldSession* session, WorldPacket const& source)
    {
        try
        {
            WorldPacket packet(source);
            uint8 list;
            packet >> list;
            if (list != 0)
                return;
            ObjectGuid setter;
            ObjectGuid target;
            uint8 icon;
            packet >> setter >> icon >> target;
            Player* player = session->GetPlayer();
            Group* group = player ? player->GetGroup() : nullptr;
            if (!setter || !group || icon >= TARGETICONCOUNT || group->GetTargetIcon(icon) != target)
                return;
            std::lock_guard<std::mutex> lock(_eventMutex);
            auto& pending = _markerChanges[session];
            if (pending.size() < 16)
                pending.push_back({setter, group->GetGUID(), icon, target, group->GetTargetIcon(4), false});
        }
        catch (std::exception const&)
        {
            // Malformed packets cannot authorize a release.
        }
    }

    void CaptureProtectionClear(WorldSession* session, Json::object& event)
    {
        if (Text(event, "type") != "chat" || event.if_contains("decode_error"))
            return;
        uint32 chat = Unsigned(event, "chat_type", MAX_CHAT_MSG_TYPE);
        if (chat != CHAT_MSG_PARTY && chat != CHAT_MSG_PARTY_LEADER)
            return;
        Player* player = session->GetPlayer();
        std::string text = Text(event, "text");
        std::string_view words(text);
        if (!CommandEqual(CommandWord(words), player->GetName()) || !CommandEqual(CommandWord(words), "clear")
            || !CommandEqual(CommandWord(words), "protection") || !TrimCommand(words).empty())
            return;
        event["type"] = "protection_clear_command";
        Group* group = player->GetGroup();
        ObjectGuid sender(std::stoull(Text(event, "sender_guid")));
        ProtectionBinding binding = BindingFor(player);
        Player* human = ObjectAccessor::FindPlayer(sender);
        if (!binding.policy.target || sender.GetRawValue() != binding.policy.protector
            || !group || !human || human->GetGroup() != group)
        {
            event["status"] = "denied";
            return;
        }
        std::lock_guard<std::mutex> lock(_eventMutex);
        auto& pending = _markerChanges[session];
        if (pending.size() < 16)
        {
            pending.push_back({sender, group->GetGUID(), 4, ObjectGuid::Empty, ObjectGuid::Empty, true});
            event["status"] = "queued";
        }
    }

    void ProcessProtectionChanges(Actor& actor, Player* player)
    {
        if (!OwnedPlayer(player))
            return;
        std::deque<MarkerChange> changes;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            changes.swap(_markerChanges[actor.session.get()]);
        }
        ProtectionBinding binding = BindingFor(player);
        binding.actor = player->GetGUID();
        Group* group = player->GetGroup();
        for (auto const& change : changes)
        {
            Player* human = ObjectAccessor::FindPlayer(change.setter);
            if (!group || group->GetGUID() != change.group || !human || human->GetGroup() != group
                || (binding.policy.protector ? change.setter.GetRawValue() != binding.policy.protector
                    : human->GetName() != "Aurenne"))
                continue;
            ObjectGuid moon = change.clearCommand ? group->GetTargetIcon(4) : change.moon;
            ProtectionBinding next = binding;
            bool movingMoonToPlayer = change.icon == 4 && change.target && !change.target.IsCreature();
            bool changed = change.clearCommand || movingMoonToPlayer
                ? next.policy.ExplicitClear(change.setter.GetRawValue(), moon.GetRawValue())
                : next.policy.ExplicitMarker(change.setter.GetRawValue(), change.icon,
                    change.target.GetRawValue(), moon.GetRawValue());
            if (!changed)
                continue;
            next.protectorName = human->GetName();
            if (next.policy.target != binding.policy.target)
            {
                next.targetName.clear();
                next.map = next.instance = next.entry = next.spawn = 0;
                next.recoveredDynamic = false;
            }
            DescribeProtectedTarget(player, next);
            if (!StoreProtection(next))
                break;
            binding = next;
            RecordEvent(actor.session.get(), {{"type", "protection_binding"}, {"active", bool(binding.policy.target)},
                {"protected_target_guid", std::to_string(binding.policy.target)}, {"explicit_human_change", true}});
            if (change.clearCommand)
            {
                std::string reply = "Cleared your protected-creature instruction. "
                    "Reapply Moon to protect a creature again.";
                Language language = player->GetTeamId() == TEAM_ALLIANCE ? LANG_COMMON : LANG_ORCISH;
                WorldPacket receipt(CMSG_MESSAGECHAT, reply.size() + 9);
                receipt << uint32(CHAT_MSG_PARTY) << uint32(language) << reply;
                actor.session->HandleMessagechatOpcode(receipt);
            }
        }
        if (!binding.policy.protector && !binding.policy.target && group && group->GetTargetIcon(4).IsCreature())
        {
            ProtectionBinding next = binding;
            if (next.policy.ObserveExistingMoon(TrustedProtector(player).GetRawValue(),
                group->GetTargetIcon(4).GetRawValue()))
            {
                next.protectorName = "Aurenne";
                DescribeProtectedTarget(player, next);
                StoreProtection(next);
            }
        }
        binding = BindingFor(player);
        if (binding.policy.target && binding.spawn && player->GetMapId() == binding.map
            && player->GetInstanceId() == binding.instance)
        {
            auto matches = player->GetMap()->GetCreatureBySpawnIdStore().equal_range(binding.spawn);
            for (auto found = matches.first; found != matches.second; ++found)
                if (Creature* creature = found->second; creature && creature->GetEntry() == binding.entry)
                {
                    if (binding.policy.target != creature->GetGUID().GetRawValue())
                    {
                        binding.policy.target = creature->GetGUID().GetRawValue();
                        StoreProtection(binding);
                    }
                    break;
                }
        }
    }

    Json::object ProtectionState(Player* player)
    {
        ProtectionBinding binding = BindingFor(player);
        ObjectGuid target = ProtectedGuid(player);
        Group* group = player->GetGroup();
        Unit* present = target ? ProtectedUnit(player) : nullptr;
        bool identityMatches = !binding.policy.target || (present && !binding.recoveredDynamic
            && present->GetMapId() == binding.map && present->GetInstanceId() == binding.instance
            && present->GetEntry() == binding.entry && (!binding.spawn
                || (present->IsCreature() && present->ToCreature()->GetSpawnId() == binding.spawn)));
        bool visible = present && identityMatches && player->CanSeeOrDetect(present)
            && player->IsWithinDistInMap(present, 90);
        auto actor = _actors.find(player->GetName());
        std::string name = visible ? present->GetName() : binding.targetName;
        std::string mode = target ? "avoid" : "inactive";
        std::string reason = target ? "party_moon_marker" : "";
        if (actor != _actors.end() && actor->second->protectedTarget == target)
        {
            if (name.empty())
                name = actor->second->protectedName;
            mode = actor->second->protectionMode;
            reason = actor->second->protectionReason;
        }
        TameAttempt attempt;
        bool active = false;
        bool recent = TameFor(player, attempt, active);
        uint64 age = recent ? uint64(std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - attempt.observed).count()) : 0;
        Json::array phases;
        for (auto const& [phase, observed] : attempt.phases)
            phases.emplace_back(Json::object{{"phase", phase}, {"age_ms", uint64(
                std::chrono::duration_cast<std::chrono::milliseconds>(
                    std::chrono::steady_clock::now() - observed).count())}});
        bool uncertain = ProtectionUncertain(player);
        return {{"active", bool(target)}, {"state", uncertain ? "unavailable" : target ? "active" : "inactive"},
            {"source", "persistent_moon_binding"}, {"marker", "moon"}, {"marker_index", 4},
            {"group_guid", group ? std::to_string(group->GetGUID().GetRawValue()) : "0"},
            {"protected_target_guid", std::to_string(target.GetRawValue())}, {"protected_target_name", name},
            {"protected_by_guid", std::to_string(binding.policy.protector)}, {"protected_by", binding.protectorName},
            {"policy", "evade_only"}, {"binding", "persistent"},
            {"persistence_ok", !_protectionPersistenceError.load()},
            {"persistence_error", _protectionPersistenceError ? "protection_journal_unavailable" : ""},
            {"map_id", binding.map}, {"instance_id", binding.instance},
            {"entry", binding.entry}, {"spawn_id", binding.spawn},
            {"identity_status", binding.recoveredDynamic ? "unresolved_dynamic" : binding.spawn ? "database_spawn"
                : binding.policy.target ? "current_session_guid" : "unbound"},
            {"target_present", visible}, {"mode", uncertain ? "blocked_unavailable" : mode},
            {"reason", uncertain ? "protected_state_unavailable" : reason},
            {"party_beneficial_blocked", bool(target) || uncertain},
            {"reflection_disabled", bool(target) || uncertain},
            {"tame_intent", Json::object{{"active", active}, {"recent", recent},
                {"tamer_guid", recent ? std::to_string(attempt.tamer.GetRawValue()) : "0"},
                {"target_guid", recent ? std::to_string(attempt.target.GetRawValue()) : "0"},
                {"spell_id", attempt.spell}, {"age_ms", age}, {"attempt_count", recent ? attempt.attempts : 0},
                {"recent_events", std::move(phases)}, {"phase", active ? "casting" : recent ? attempt.phase : ""}}}};
    }

    void RestorePetReactions(Actor& actor, Player* player)
    {
        for (Unit* controlled : player->m_Controlled)
            if (controlled && controlled->IsCreature() && OwnedPlayer(controlled) == player)
                if (auto found = actor.petReactions.find(controlled->GetGUID()); found != actor.petReactions.end())
                    controlled->ToCreature()->SetReactState(found->second);
        actor.petReactions.clear();
    }

    void StopProtectedActivity(Unit* unit, ObjectGuid protectedTarget)
    {
        Player* owner = OwnedPlayer(unit);
        if (protectedTarget || (owner && ProtectionUncertain(owner)))
        {
            // Cancel only this character's/controlled unit's reflection, never another player's aura or spell.
            bool reflecting = unit->HasAuraType(SPELL_AURA_REFLECT_SPELLS)
                || unit->HasAuraType(SPELL_AURA_REFLECT_SPELLS_SCHOOL);
            unit->RemoveAurasByType(SPELL_AURA_REFLECT_SPELLS);
            unit->RemoveAurasByType(SPELL_AURA_REFLECT_SPELLS_SCHOOL);
            if (reflecting)
                GuardIntervention(unit, unit, "local_reflection_cancel", "reflection_declined");
        }
        if (owner && AreaBenefitsWithheld(owner))
            unit->RemoveOwnedAuras([this, unit, owner](Aura const* aura)
            {
                Unit* caster = aura->GetCaster();
                bool ownedCaster = aura->GetCasterGUID() == owner->GetGUID()
                    || (caster && OwnedPlayer(caster) == owner);
                if (aura->GetOwner() != unit || !ownedCaster || !PositiveAreaAura(aura->GetSpellInfo()))
                    return false;
                GuardIntervention(caster ? caster : owner, unit, "local_party_aura_cancel",
                    "beneficial_intervention_withheld", aura->GetId());
                return true;
            });
        bool attacking = unit->GetVictim() && BlocksDamage(unit, unit->GetVictim());
        if (attacking)
        {
            Unit* victim = unit->GetVictim();
            unit->AttackStop();
            unit->GetMotionMaster()->Clear();
            unit->StopMoving();
            GuardIntervention(unit, victim, "ongoing_melee_cancel", "protected_damage");
        }
        for (uint32 slot = CURRENT_GENERIC_SPELL; slot < CURRENT_MAX_SPELL; ++slot)
            if (Spell* spell = unit->GetCurrentSpell(slot); spell && spell->getState() != SPELL_STATE_FINISHED)
            {
                Unit* target = spell->m_targets.GetUnitTarget();
                Unit* protectedUnit = protectedTarget && owner ? ProtectedUnit(owner) : nullptr;
                bool area = protectedUnit && unit->IsWithinDistInMap(protectedUnit, 90)
                    && !spell->GetSpellInfo()->IsPositive() && spell->GetSpellInfo()->IsTargetingArea();
                if (area || BlocksSpell(spell, target))
                {
                    GuardSpellIntervention(spell, target, "ongoing_cast_cancel");
                    unit->InterruptNonMeleeSpells(true);
                    break;
                }
            }
    }

    bool EscapePath(Player* player, Unit* protectedUnit, Position const& destination)
    {
        float currentDistance = player->GetDistance(protectedUnit);
        if (protectedUnit->GetDistance(destination) < currentDistance + 5 || player->GetDistance(destination) > 25)
            return false;
        PathGenerator path(player);
        path.SetPathLengthLimit(35);
        if (!path.CalculatePath(destination.GetPositionX(), destination.GetPositionY(),
                destination.GetPositionZ(), false)
            || path.GetPathType() != PATHFIND_NORMAL || path.GetPath().size() < 2)
            return false;
        float minimum = std::max(0.0f, currentDistance - 1.0f);
        bool checkedInitialProgress = false;
        for (size_t index = 1; index < path.GetPath().size(); ++index)
        {
            auto const& start = path.GetPath()[index - 1];
            auto const& end = path.GetPath()[index];
            float x = start.x - protectedUnit->GetPositionX();
            float y = start.y - protectedUnit->GetPositionY();
            float vx = end.x - start.x;
            float vy = end.y - start.y;
            float lengthSquared = vx * vx + vy * vy;
            if (lengthSquared < 0.0001f)
                continue;
            float outwardProgress = x * vx + y * vy;
            if (!checkedInitialProgress)
            {
                if (outwardProgress < 0)
                    return false;
                checkedInitialProgress = true;
            }
            // Navigation vertices can both be safe while the segment between them crosses the attacker.
            float fraction = std::clamp(-outwardProgress / lengthSquared, 0.0f, 1.0f);
            float dx = x + fraction * vx;
            float dy = y + fraction * vy;
            if (dx * dx + dy * dy < minimum * minimum)
                return false;
        }
        if (!checkedInitialProgress)
            return false;
        player->GetMotionMaster()->Clear();
        Movement::MoveSplineInit movement(player);
        movement.MovebyPath(path.GetPath());
        movement.SetWalk(false);
        return movement.Launch() > 0;
    }

    void UpdateProtection(Actor& actor, Player* player)
    {
        if (!OwnedPlayer(player))
            return;
        ProcessProtectionChanges(actor, player);
        ObjectGuid target = ProtectedGuid(player);
        Group* group = player->GetGroup();
        ObjectGuid groupGuid = group ? group->GetGUID() : ObjectGuid::Empty;
        if (actor.protectedTarget != target)
        {
            if (actor.protectionMode == "evading" || actor.protectionMode == "stopped_no_safe_path")
            {
                player->GetMotionMaster()->Clear();
                player->StopMoving();
            }
            actor.protectedTarget = target;
            actor.protectedGroup = groupGuid;
            actor.protectedName.clear();
            actor.protectionMode = target ? "avoid" : "inactive";
            actor.protectionReason = target ? "party_moon_marker" : "";
            actor.nextEscape = {};
            if (!target)
                RestorePetReactions(actor, player);
            RecordEvent(actor.session.get(), {{"type", "protection_changed"}, {"active", bool(target)},
                {"protected_target_guid", std::to_string(target.GetRawValue())}, {"marker", "moon"}});
        }
        StopProtectedActivity(player, target);
        std::set<ObjectGuid> controlledGuids;
        for (Unit* controlled : player->m_Controlled)
            if (controlled && OwnedPlayer(controlled) == player)
                controlledGuids.insert(controlled->GetGUID());
        std::erase_if(actor.petReactions, [&controlledGuids](auto const& entry)
        {
            return !controlledGuids.contains(entry.first);
        });
        for (Unit* controlled : player->m_Controlled)
            if (controlled && OwnedPlayer(controlled) == player)
            {
                if (target && controlled->IsCreature())
                {
                    actor.petReactions.try_emplace(controlled->GetGUID(), controlled->ToCreature()->GetReactState());
                    controlled->ToCreature()->SetReactState(REACT_PASSIVE);
                }
                StopProtectedActivity(controlled, target);
            }
        if (ProtectionUncertain(player))
        {
            player->AttackStop();
            player->InterruptNonMeleeSpells(true);
            player->GetMotionMaster()->Clear();
            player->StopMoving();
            actor.protectionMode = "blocked_unavailable";
            actor.protectionReason = "protected_state_unavailable";
            return;
        }
        Unit* protectedUnit = target ? ProtectedUnit(player) : nullptr;
        if (!protectedUnit || !protectedUnit->IsAlive() || !player->IsAlive())
        {
            if (actor.protectionMode == "evading" || actor.protectionMode == "stopped_no_safe_path")
            {
                player->GetMotionMaster()->Clear();
                player->StopMoving();
            }
            actor.protectionMode = target ? "avoid" : "inactive";
            actor.protectionReason = target ? "persistent_protected_target" : "";
            return;
        }
        if (player->CanSeeOrDetect(protectedUnit))
            actor.protectedName = protectedUnit->GetName();
        bool attacking = protectedUnit->GetVictim() == player || player->getAttackers().contains(protectedUnit);
        if (!attacking)
        {
            if (actor.protectionMode == "stopped_no_safe_path"
                || (actor.protectionMode == "evading" && !player->isMoving()))
                actor.protectionMode = "avoid";
            return;
        }
        auto now = std::chrono::steady_clock::now();
        if (now < actor.nextEscape)
            return;
        actor.nextEscape = now + std::chrono::seconds(2);
        if (!actor.motionId.empty())
        {
            Finish(actor.motionId, false, {{"status", "failed"}, {"reason", "protected_target_escape"}});
            actor.motionId.clear();
        }
        if (player->HasUnitState(UNIT_STATE_ROOT | UNIT_STATE_STUNNED) || player->IsInFlight())
        {
            actor.protectionMode = "stopped_no_safe_path";
            actor.protectionReason = "cannot_move";
            return;
        }
        if (actor.protectionMode == "evading" && player->isMoving()
            && player->GetDistance(actor.escapeDestination) > 2)
            return;
        bool escaped = false;
        Position destination;
        uint64 protector = BindingFor(player).policy.protector;
        // Prefer a living nearby human if the entire checked path moves away from the protected attacker.
        if (group)
            for (auto const& member : group->GetMemberSlots())
                if (Player* human = ObjectAccessor::FindPlayer(member.guid); human && human != player
                    && human->GetGUID().GetRawValue() == protector
                    && !OwnedPlayer(human) && human->IsAlive() && player->IsWithinDistInMap(human, 25))
                {
                    destination = human->GetPosition();
                    if (EscapePath(player, protectedUnit, destination))
                    {
                        escaped = true;
                        break;
                    }
                }
        if (!escaped)
        {
            float away = protectedUnit->GetAngle(player);
            for (float offset : {0.0f, 0.6f, -0.6f})
            {
                destination = player->GetFirstCollisionPosition(12.0f, away + offset - player->GetOrientation());
                if (EscapePath(player, protectedUnit, destination))
                {
                    escaped = true;
                    break;
                }
            }
        }
        if (escaped)
        {
            actor.escapeDestination = destination;
            actor.protectionMode = "evading";
            actor.protectionReason = "protected_attacker_normal_path";
        }
        else
        {
            player->GetMotionMaster()->Clear();
            player->StopMoving();
            actor.protectionMode = "stopped_no_safe_path";
            actor.protectionReason = "no_complete_path_away";
        }
    }

    bool TameFor(Player* owner, TameAttempt& result, bool& active)
    {
        Group* group = owner->GetGroup();
        if (!group)
            return false;
        auto now = std::chrono::steady_clock::now();
        for (auto const& member : group->GetMemberSlots())
            if (Player* human = ObjectAccessor::FindPlayer(member.guid); human && human != owner
                && human->GetGroup() == group && human->IsWithinDistInMap(owner, 90)
                && owner->CanSeeOrDetect(human))
                for (uint32 slot = CURRENT_GENERIC_SPELL; slot < CURRENT_MAX_SPELL; ++slot)
                    if (Spell* spell = human->GetCurrentSpell(slot); spell
                        && spell->getState() != SPELL_STATE_FINISHED
                        && spell->GetSpellInfo()->HasEffect(SPELL_EFFECT_TAMECREATURE))
                    {
                        {
                            std::lock_guard<std::mutex> lock(_eventMutex);
                            auto prior = _tameAttempts.find(human->GetGUID());
                            if (prior != _tameAttempts.end()
                                && prior->second.target == spell->m_targets.GetUnitTargetGUID()
                                && prior->second.group == group->GetGUID())
                                result = prior->second;
                        }
                        result.group = group->GetGUID();
                        result.tamer = human->GetGUID();
                        result.target = spell->m_targets.GetUnitTargetGUID();
                        result.spell = spell->GetSpellInfo()->Id;
                        result.observed = now;
                        active = true;
                        return true;
                    }
        std::lock_guard<std::mutex> lock(_eventMutex);
        bool found = false;
        for (auto const& [guid, attempt] : _tameAttempts)
            if (attempt.group == group->GetGUID() && group->IsMember(guid)
                && now - attempt.observed <= std::chrono::seconds(20)
                && (!found || attempt.observed > result.observed))
            {
                result = attempt;
                found = true;
            }
        return found;
    }

    Json::array AllowedNames() const
    {
        Json::array result;
        for (auto const& name : _allowed)
            result.emplace_back(name);
        return result;
    }

    void Remember(std::string const& id, std::string const& encoded, Json::object const& response,
        std::string const& actionType)
    {
        if (_requests.size() >= 512)
        {
            _requests.erase(_requestOrder.front());
            _requestOrder.pop_front();
        }
        _requests.emplace(id, CachedRequest{encoded, response, actionType});
        _requestOrder.push_back(id);
    }

    void Finish(std::string const& id, bool ok, Json::object result)
    {
        auto found = _requests.find(id);
        if (found == _requests.end())
            return;
        found->second.response["ok"] = ok;
        found->second.response["result"] = std::move(result);
        if (!ok)
            found->second.response["error"] = Json::object{
                {"code", "action_failed"}, {"message", "See result for the operation failure"}};
        if (Text(found->second.response, "op") == "action")
            JournalAction(Text(found->second.response, "character"), id,
                found->second.actionType, found->second.response);
    }

    int CreationResult(WorldSession* session)
    {
        std::lock_guard<std::mutex> lock(_eventMutex);
        auto found = _creationResults.find(session);
        return found == _creationResults.end() ? -1 : found->second;
    }

    void RemoveCreationResult(WorldSession* session)
    {
        std::lock_guard<std::mutex> lock(_eventMutex);
        _creationResults.erase(session);
        _ownedSessions.erase(session);
        if (auto owned = _ownedCharacters.find(session); owned != _ownedCharacters.end())
            _emoteCorrelations.ForgetCharacter(owned->second.GetRawValue());
        _ownedCharacters.erase(session);
        _lootWindows.erase(session);
        _openingLoot.erase(session);
        _rewardReceipts.erase(session);
        _partyInvites.erase(session);
        _tradeFrames.erase(session);
        _questShares.erase(session);
        _questAbandons.erase(session);
        _lastQuestAbandon.erase(session);
        _markerChanges.erase(session);
        _vendorMenus.erase(session);
        _trainerMenus.erase(session);
        _questMenus.erase(session);
        _questDialogs.erase(session);
        _spiritHealerMenus.erase(session);
        _spiritHealerConfirmations.erase(session);
        _spiritRecoveryReceipts.erase(session);
    }

    void ClearCosmeticEmote(Actor& actor, Player* player)
    {
        if (!player || !actor.session->IsHeadless() || actor.session->GetPlayer() != player
            || player->GetUInt32Value(UNIT_NPC_EMOTESTATE) != EMOTE_STATE_DANCE)
            return;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            if (!_ownedSessions.contains(actor.session.get()))
                return;
        }
        // Normal client movement clears this stored loop. Native MotionMaster
        // movement has no client movement packet, so complete that cosmetic step.
        player->ClearEmoteState();
    }

    Json::object TradeOffer(Player* viewer, TradeData* data)
    {
        Json::array items;
        Json::value service = nullptr;
        for (uint8 slot = 0; slot < TRADE_SLOT_COUNT; ++slot)
            if (Item* item = data->GetItem(TradeSlots(slot)))
            {
                Json::object facts = ItemFacts(viewer, item->GetTemplate(), item);
                facts["trade_slot"] = slot;
                facts["owner_guid"] = std::to_string(item->GetOwnerGUID().GetRawValue());
                facts["wrapped"] = item->IsWrapped();
                facts["tradeable_to_recipient"] = item->CanBeTraded(false, true) && !item->IsBindedNotWith(viewer);
                if (slot == TRADE_SLOT_NONTRADED)
                    service = std::move(facts);
                else
                    items.emplace_back(std::move(facts));
            }
        Item* castItem = data->GetSpellCastItem();
        return {{"items", std::move(items)}, {"money", data->GetMoney()}, {"spell_id", data->GetSpell()},
            {"spell_cast_item_guid", castItem ? std::to_string(castItem->GetGUID().GetRawValue()) : "0"},
            {"nontraded_item", std::move(service)}};
    }

    std::string TradeFingerprint(TradeData* mine, TradeData* theirs)
    {
        Json::array offers;
        for (TradeData* data : {mine, theirs})
        {
            Json::array slots;
            for (uint8 slot = 0; slot < TRADE_SLOT_COUNT; ++slot)
            {
                Json::value value = nullptr;
                if (Item* item = data->GetItem(TradeSlots(slot)))
                {
                    Json::array enchantments;
                    for (uint8 index = 0; index < MAX_ENCHANTMENT_SLOT; ++index)
                        enchantments.emplace_back(item->GetEnchantmentId(EnchantmentSlot(index)));
                    Json::array charges;
                    for (uint8 index = 0; index < MAX_ITEM_PROTO_SPELLS; ++index)
                        charges.emplace_back(item->GetSpellCharges(index));
                    value = Json::object{{"guid", std::to_string(item->GetGUID().GetRawValue())},
                        {"entry", item->GetEntry()}, {"count", item->GetCount()},
                        {"owner", std::to_string(item->GetOwnerGUID().GetRawValue())},
                        {"property", item->GetItemRandomPropertyId()}, {"suffix", item->GetItemSuffixFactor()},
                        {"wrapped", item->IsWrapped()}, {"soulbound", item->IsSoulBound()},
                        {"gift_creator", std::to_string(item->GetGuidValue(ITEM_FIELD_GIFTCREATOR).GetRawValue())},
                        {"creator", std::to_string(item->GetGuidValue(ITEM_FIELD_CREATOR).GetRawValue())},
                        {"charges", std::move(charges)}, {"enchantments", std::move(enchantments)}};
                }
                slots.emplace_back(std::move(value));
            }
            Item* castItem = data->GetSpellCastItem();
            offers.emplace_back(Json::object{{"items", std::move(slots)}, {"money", data->GetMoney()},
                {"spell", data->GetSpell()},
                {"cast_item", castItem ? std::to_string(castItem->GetGUID().GetRawValue()) : "0"}});
        }
        return Json::serialize(offers);
    }

    Json::object TradeInventoryState(Player* player, Player* partner, Json::object const& approved)
    {
        Json::array items;
        auto offer = approved.if_contains("partner_offer");
        auto rows = offer && offer->is_object() ? offer->as_object().if_contains("items") : nullptr;
        if (rows && rows->is_array())
            for (auto const& row : rows->as_array())
            {
                if (!row.is_object())
                    continue;
                auto const& item = row.as_object();
                ObjectGuid guid(GuidNumber(item, "guid"));
                uint32 entry = Unsigned(item, "item_id");
                Item* ownItem = player->GetItemByGuid(guid);
                Item* partnerItem = partner ? partner->GetItemByGuid(guid) : nullptr;
                Json::object fact{{"source_guid", Text(item, "guid")}, {"item_id", entry},
                    {"offered_count", Unsigned(item, "count")},
                    {"self_guid_count", ownItem ? ownItem->GetCount() : 0},
                    {"self_entry_count", player->GetItemCount(entry, false)}};
                fact["partner_guid_count"] = partner
                    ? Json::value(partnerItem ? partnerItem->GetCount() : 0) : Json::value(nullptr);
                fact["partner_entry_count"] = partner
                    ? Json::value(partner->GetItemCount(entry, false)) : Json::value(nullptr);
                items.emplace_back(std::move(fact));
            }
        return {{"self_money", player->GetMoney()},
            {"partner_money", partner ? Json::value(partner->GetMoney()) : Json::value(nullptr)},
            {"items", std::move(items)}, {"timestamp", Timestamp()},
            {"count_note", "Stacks may merge and lose their source GUID; entry totals include other copies."}};
    }

    void RefreshTrade(Player* player)
    {
        WorldSession* session = player->GetSession();
        TradeData* mine = player->GetTradeData();
        Player* partner = mine ? mine->GetTrader() : nullptr;
        TradeData* theirs = partner ? partner->GetTradeData() : nullptr;
        bool valid = partner && theirs && theirs->GetTrader() == player;
        std::string fingerprint = valid ? TradeFingerprint(mine, theirs) : "";
        Json::object event;
        bool withdrawConsent = false;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            if (!_ownedSessions.contains(session))
                return;
            auto found = _tradeFrames.find(session);
            if (!valid)
            {
                if (found != _tradeFrames.end() && found->second.active)
                {
                    TradeFrame& frame = found->second;
                    frame.active = false;
                    if (frame.pendingConsent)
                    {
                        frame.receipt["status"] = "ended_unconfirmed";
                        frame.receipt["transfer_completed"] = false;
                        frame.receipt["timestamp"] = Timestamp();
                        frame.pendingConsent = false;
                    }
                    event = {{"type", "trade_closed"}, {"trade_id", std::to_string(frame.id)},
                        {"target_guid", std::to_string(frame.partner.GetRawValue())}};
                }
            }
            else
            {
                TradeFrame& frame = _tradeFrames[session];
                if (!frame.active || frame.partner != partner->GetGUID())
                {
                    Json::object receipt = std::move(frame.receipt);
                    frame = TradeFrame{};
                    frame.id = ++_tradeSequence;
                    frame.partner = partner->GetGUID();
                    frame.active = true;
                    frame.receipt = std::move(receipt);
                }
                if (frame.fingerprint != fingerprint)
                {
                    if (frame.revision == std::numeric_limits<uint32>::max())
                    {
                        frame.id = ++_tradeSequence;
                        frame.revision = 0;
                    }
                    ++frame.revision;
                    frame.fingerprint = std::move(fingerprint);
                    if (frame.pendingConsent)
                    {
                        withdrawConsent = mine->IsAccepted();
                        frame.receipt["status"] = "offer_changed";
                        frame.receipt["transfer_completed"] = false;
                        frame.receipt["timestamp"] = Timestamp();
                        frame.pendingConsent = false;
                    }
                    event = {{"type", "trade_offer_changed"}, {"trade_id", std::to_string(frame.id)},
                        {"revision", frame.revision}, {"target_guid", std::to_string(frame.partner.GetRawValue())}};
                }
                else if (frame.pendingConsent && !mine->IsAccepted())
                {
                    frame.receipt["status"] = "acceptance_withdrawn";
                    frame.receipt["transfer_completed"] = false;
                    frame.receipt["timestamp"] = Timestamp();
                    frame.pendingConsent = false;
                }
            }
        }
        // Item metadata can change without TradeData::SetItem/SetMoney. Revoke
        // previously granted consent through the normal handler in that case.
        if (withdrawConsent && player->GetTradeData() && player->GetTradeData()->IsAccepted())
        {
            WorldPacket packet;
            session->HandleUnacceptTradeOpcode(packet);
        }
        if (!event.empty())
            RecordEvent(session, std::move(event));
    }

    void CaptureTradeStatus(WorldSession* session, WorldPacket const& packet)
    {
        if (packet.size() < 4)
            return;
        WorldPacket copy(packet);
        uint32 status;
        copy >> status;
        ObjectGuid requester;
        uint32 result = 0;
        uint8 targetResult = 0;
        uint32 limited = 0;
        if (status == TRADE_STATUS_BEGIN_TRADE && copy.size() >= 12)
            copy >> requester;
        else if (status == TRADE_STATUS_CLOSE_WINDOW && copy.size() >= 13)
            copy >> result >> targetResult >> limited;
        Player* player = session->GetPlayer();
        Json::object event;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            if (!_ownedSessions.contains(session))
                return;
            TradeFrame& frame = _tradeFrames[session];
            if (status == TRADE_STATUS_BEGIN_TRADE && requester)
            {
                Json::object receipt = std::move(frame.receipt);
                frame = TradeFrame{};
                frame.id = ++_tradeSequence;
                frame.partner = requester;
                frame.active = true;
                frame.receipt = std::move(receipt);
            }
            bool changed = frame.lastStatus != status || status == TRADE_STATUS_BEGIN_TRADE;
            frame.lastStatus = status;
            ++frame.statusSequence;
            if (status == TRADE_STATUS_OPEN_WINDOW)
                frame.open = true;
            if (status == TRADE_STATUS_CLOSE_WINDOW || status == TRADE_STATUS_TRADE_CANCELED)
                frame.open = false;
            if (status == TRADE_STATUS_CLOSE_WINDOW)
            {
                frame.inventoryResult = result;
                frame.targetResult = targetResult != 0;
                frame.limitedItem = limited;
            }
            if (status == TRADE_STATUS_TRADE_COMPLETE)
            {
                Player* partner = ObjectAccessor::FindPlayer(frame.partner);
                bool attributed = frame.pendingConsent;
                if (!attributed)
                    frame.receipt = {{"trade_id", std::to_string(frame.id)}, {"revision", frame.revision},
                        {"target_guid", std::to_string(frame.partner.GetRawValue())}, {"before", nullptr}};
                Json::object approved;
                if (auto value = frame.receipt.if_contains("approved_offer"); value && value->is_object())
                    approved = value->as_object();
                frame.receipt["after"] = TradeInventoryState(player, partner, approved);
                frame.receipt["status"] = "completed";
                frame.receipt["transfer_completed"] = true;
                frame.receipt["attributed_to_model_accept"] = attributed;
                frame.receipt["source"] = "normal_trade_complete_packet";
                frame.receipt["timestamp"] = Timestamp();
                frame.pendingConsent = false;
                frame.active = false;
            }
            else if (status == TRADE_STATUS_TRADE_CANCELED && frame.pendingConsent)
            {
                frame.receipt["status"] = "cancelled";
                frame.receipt["transfer_completed"] = false;
                frame.receipt["timestamp"] = Timestamp();
                frame.pendingConsent = false;
            }
            char const* type = status == TRADE_STATUS_BEGIN_TRADE ? "trade_request"
                : status == TRADE_STATUS_OPEN_WINDOW ? "trade_open"
                : status == TRADE_STATUS_TRADE_ACCEPT ? "trade_partner_accepted"
                : status == TRADE_STATUS_BACK_TO_TRADE ? "trade_acceptance_reset"
                : status == TRADE_STATUS_TRADE_COMPLETE ? "trade_complete"
                : status == TRADE_STATUS_TRADE_CANCELED ? "trade_cancelled" : "trade_error";
            if (changed || status == TRADE_STATUS_TRADE_COMPLETE || status == TRADE_STATUS_CLOSE_WINDOW)
                event = {{"type", type}, {"trade_id", std::to_string(frame.id)}, {"revision", frame.revision},
                    {"target_guid", std::to_string(frame.partner.GetRawValue())}, {"trade_status", status},
                    {"inventory_result", result}, {"is_target_result", targetResult != 0},
                    {"limited_item_id", limited}};
        }
        if (!event.empty())
            RecordEvent(session, std::move(event));
    }

    std::string ReceiveOnlyTradeReason(Player* player, Player* partner, TradeData* mine, TradeData* theirs,
        bool& receiveOnly, bool& canStore, uint32& inventoryResult, uint32& limited)
    {
        receiveOnly = mine->GetMoney() == 0 && !mine->GetSpell() && !theirs->GetSpell()
            && !mine->HasSpellCastItem() && !theirs->HasSpellCastItem()
            && !theirs->GetItem(TRADE_SLOT_NONTRADED);
        for (uint8 slot = 0; slot < TRADE_SLOT_COUNT; ++slot)
            if (mine->GetItem(TradeSlots(slot)))
                receiveOnly = false;
        Item* incoming[TRADE_SLOT_TRADED_COUNT] = {};
        bool hasOffer = theirs->GetMoney() > 0;
        bool tradeable = true;
        for (uint8 slot = 0; slot < TRADE_SLOT_TRADED_COUNT; ++slot)
            if (Item* item = theirs->GetItem(TradeSlots(slot)))
            {
                incoming[slot] = item;
                hasOffer = true;
                tradeable = tradeable && item->CanBeTraded(false, true) && !item->IsBindedNotWith(player);
            }
        inventoryResult = uint32(player->CanStoreItems(incoming, TRADE_SLOT_TRADED_COUNT, &limited));
        canStore = inventoryResult == EQUIP_ERR_OK;
        if (!receiveOnly)
            return "receive_only_no_outgoing_items_money_or_services";
        if (!player->IsAlive() || !partner->IsAlive())
            return "trader_dead";
        if (!player->IsWithinDistInMap(partner, TRADE_DISTANCE, false))
            return "trader_out_of_range";
        if (player->GetSession()->IsLoggingOut() || partner->GetSession()->IsLoggingOut())
            return "trader_logging_out";
        if (!hasOffer)
            return "empty_incoming_offer";
        if (!tradeable)
            return "incoming_item_not_tradeable_to_recipient";
        if (!canStore)
            return "incoming_items_cannot_be_stored";
        if (!partner->HasEnoughMoney(theirs->GetMoney()))
            return "partner_lacks_offered_money";
        if (player->GetMoney() >= MAX_MONEY_AMOUNT - theirs->GetMoney())
            return "recipient_money_cap";
        return "";
    }

    Json::value TradeSnapshot(Player* player)
    {
        RefreshTrade(player);
        TradeData* mine = player->GetTradeData();
        Player* partner = mine ? mine->GetTrader() : nullptr;
        TradeData* theirs = partner ? partner->GetTradeData() : nullptr;
        if (!partner || !theirs || theirs->GetTrader() != player)
            return nullptr;
        TradeFrame frame;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            auto found = _tradeFrames.find(player->GetSession());
            if (found == _tradeFrames.end() || !found->second.active)
                return nullptr;
            frame = found->second;
        }
        bool receiveOnly = false;
        bool canStore = false;
        uint32 inventoryResult = 0;
        uint32 limited = 0;
        std::string reason = ReceiveOnlyTradeReason(player, partner, mine, theirs,
            receiveOnly, canStore, inventoryResult, limited);
        if (reason.empty() && !frame.open)
            reason = "trade_window_not_open";
        if (reason.empty() && mine->IsAccepted())
            reason = "already_accepted_waiting_for_partner";
        Json::object actions;
        for (auto const& step : {"begin", "accept", "unaccept", "cancel"})
        {
            std::string name(step);
            if ((name == "accept" && !reason.empty()) || (name == "unaccept" && !mine->IsAccepted())
                || (name == "begin" && (frame.open || !player->IsAlive() || !partner->IsAlive()
                    || !player->IsWithinDistInMap(partner, TRADE_DISTANCE, false))))
                continue;
            actions[step] = Json::object{{"type", std::string("trade_") + step},
                {"target_guid", std::to_string(frame.partner.GetRawValue())},
                {"trade_id", std::to_string(frame.id)}, {"trade_revision", frame.revision}};
        }
        return Json::object{{"trade_id", std::to_string(frame.id)}, {"revision", frame.revision},
            {"target_guid", std::to_string(frame.partner.GetRawValue())},
            {"partner", Json::object{{"guid", std::to_string(frame.partner.GetRawValue())},
                {"name", partner->GetName()}, {"distance", player->GetDistance(partner)}}},
            {"phase", frame.open ? "open" : "requested"},
            {"self_accepted", mine->IsAccepted()}, {"partner_accepted", theirs->IsAccepted()},
            {"self_offer", TradeOffer(player, mine)}, {"partner_offer", TradeOffer(player, theirs)},
            {"receive_only", receiveOnly}, {"can_store", canStore}, {"inventory_result", inventoryResult},
            {"limited_item_id", limited}, {"can_accept", reason.empty()}, {"blocked_reason", reason},
            {"last_trade_status", frame.lastStatus}, {"last_inventory_result", frame.inventoryResult},
            {"last_is_target_result", frame.targetResult}, {"last_limited_item_id", frame.limitedItem},
            {"actions", std::move(actions)}};
    }

    Json::object RespondToTrade(Json::object const& request, Json::object const& action, Actor& actor, Player* player)
    {
        Json::value snapshot = TradeSnapshot(player);
        if (!snapshot.is_object())
            return Error(request, "no_trade", "No current reciprocal trade is available");
        auto const& state = snapshot.as_object();
        auto revision = action.if_contains("trade_revision");
        bool validRevision = revision && ((revision->is_uint64() && revision->as_uint64() > 0)
            || (revision->is_int64() && revision->as_int64() > 0));
        if (Text(action, "target_guid") != Text(state, "target_guid")
            || Text(action, "trade_id") != Text(state, "trade_id") || !validRevision
            || revision->to_number<uint64>() != Unsigned(state, "revision"))
            return Error(request, "trade_changed", "Observe current partner, trade_id and revision before choosing");
        std::string type = Text(action, "type");
        if (type == "trade_accept" && !state.at("can_accept").as_bool())
            return Error(request, "trade_not_acceptable", Text(state, "blocked_reason"));
        TradeData* mine = player->GetTradeData();
        Player* partner = mine->GetTrader();
        if (type == "trade_begin" && (!player->IsAlive() || !partner->IsAlive()
            || !player->IsWithinDistInMap(partner, TRADE_DISTANCE, false)))
            return Error(request, "cannot_begin_trade", "Opening trade requires living traders in normal trade range");
        ClearCosmeticEmote(actor, player);
        std::string requestId = Text(request, "id");
        uint64 statusSequence = 0;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            statusSequence = _tradeFrames[actor.session.get()].statusSequence;
        }
        if (type == "trade_accept")
        {
            Json::object approved{{"self_offer", state.at("self_offer")}, {"partner_offer", state.at("partner_offer")}};
            Json::object before = TradeInventoryState(player, partner, approved);
            std::lock_guard<std::mutex> lock(_eventMutex);
            TradeFrame& frame = _tradeFrames[actor.session.get()];
            frame.receipt = {{"trade_id", Text(state, "trade_id")}, {"revision", Unsigned(state, "revision")},
                {"target_guid", Text(state, "target_guid")}, {"request_id", requestId},
                {"status", "consent_recorded"}, {"transfer_completed", false},
                {"approved_offer", std::move(approved)}, {"before", std::move(before)}, {"after", nullptr},
                {"timestamp", Timestamp()}, {"source", "normal_trade_accept_handler"}};
            frame.pendingConsent = true;
        }
        WorldPacket packet;
        if (type == "trade_begin")
            actor.session->HandleBeginTradeOpcode(packet);
        else if (type == "trade_accept")
            actor.session->HandleAcceptTradeOpcode(packet);
        else if (type == "trade_unaccept")
            actor.session->HandleUnacceptTradeOpcode(packet);
        else
            actor.session->HandleCancelTradeOpcode(packet);
        bool handlerFailed = false;
        if (type == "trade_accept")
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            TradeFrame const& frame = _tradeFrames[actor.session.get()];
            handlerFailed = frame.statusSequence != statusSequence && frame.lastStatus != TRADE_STATUS_OPEN_WINDOW
                && frame.lastStatus != TRADE_STATUS_TRADE_ACCEPT && frame.lastStatus != TRADE_STATUS_BACK_TO_TRADE
                && frame.lastStatus != TRADE_STATUS_TRADE_COMPLETE;
        }
        // Some normal failure paths retain TradeData or acceptance. A failed
        // request must not leave consent that could commit on a later click.
        if (handlerFailed && player->GetTradeData() && player->GetTradeData()->IsAccepted())
            actor.session->HandleUnacceptTradeOpcode(packet);
        RefreshTrade(player);
        Json::object receipt;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            TradeFrame& frame = _tradeFrames[actor.session.get()];
            if (type == "trade_accept" && Text(frame.receipt, "status") != "completed")
            {
                bool accepted = player->GetTradeData() && player->GetTradeData()->IsAccepted();
                if (!accepted || handlerFailed)
                {
                    frame.receipt["status"] = "failed";
                    frame.receipt["transfer_completed"] = false;
                    frame.receipt["timestamp"] = Timestamp();
                    frame.pendingConsent = false;
                }
            }
            receipt = frame.receipt;
        }
        bool completed = type == "trade_accept" && Text(receipt, "status") == "completed"
            && Text(receipt, "request_id") == requestId;
        if (type == "trade_accept" && !completed && Text(receipt, "status") != "consent_recorded")
        {
            auto failure = Error(request, "trade_accept_failed", "Normal trade handler did not retain acceptance");
            failure["result"] = Json::object{{"request_id", requestId}, {"status", "failed"},
                {"transfer_completed", false}, {"trade_receipt", receipt}};
            return failure;
        }
        std::string outcome = type == "trade_begin" ? "open" : type == "trade_unaccept" ? "acceptance_withdrawn"
            : type == "trade_cancel" ? "cancelled" : completed ? "completed" : "awaiting_partner_acceptance";
        Json::object result{{"status", "completed"}, {"request_id", requestId}, {"outcome", outcome},
            {"trade_id", Text(state, "trade_id")}, {"trade_revision", Unsigned(state, "revision")},
            {"target_guid", Text(state, "target_guid")}, {"transfer_completed", completed},
            {"trade", TradeSnapshot(player)}};
        if (type == "trade_accept")
            result["trade_receipt"] = std::move(receipt);
        return Response(request, true, std::move(result));
    }

    void CaptureQuestAbandonCommand(WorldSession* session, Json::object& event)
    {
        if (Text(event, "type") != "chat" || event.if_contains("decode_error"))
            return;
        uint32 chatType = Unsigned(event, "chat_type", MAX_CHAT_MSG_TYPE);
        if (chatType != CHAT_MSG_PARTY && chatType != CHAT_MSG_PARTY_LEADER)
            return;
        Player* player = session->GetPlayer();
        QuestAbandonInput input = ParseQuestAbandonCommand(Text(event, "text"), player->GetName());
        if (!input.addressed)
            return;
        ObjectGuid sender(std::stoull(Text(event, "sender_guid")));
        if (!sender || sender == player->GetGUID())
            return;
        std::string key = Text(event, "sender_guid") + ":" + Text(event, "text");
        auto now = std::chrono::steady_clock::now();
        event["type"] = "quest_abandon_command";
        event["quest_id"] = input.quest;
        Group* group = player->GetGroup();
        Player* issuer = ObjectAccessor::FindPlayer(sender);
        if (!group || !issuer || issuer->GetGroup() != group || !group->IsLeader(sender))
        {
            event["status"] = "denied";
            event["reason"] = "not_party_leader";
            return;
        }
        std::lock_guard<std::mutex> lock(_eventMutex);
        if (!_ownedSessions.contains(session))
            return;
        auto previous = _lastQuestAbandon.find(session);
        if (previous != _lastQuestAbandon.end() && previous->second.first == key
            && now - previous->second.second < std::chrono::seconds(2))
        {
            event["status"] = "duplicate";
            return;
        }
        auto& pending = _questAbandons[session];
        if (pending.size() >= 8)
        {
            event["status"] = "queue_full";
            return;
        }
        _lastQuestAbandon[session] = {key, now};
        pending.push_back({sender, group->GetGUID(), player->GetGUID(), player->GetName(), input.quest, now});
        event["status"] = "queued";
    }

    void ProcessQuestAbandonCommands(Actor& actor, Player* player)
    {
        std::deque<QuestAbandonCommand> commands;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            auto pending = _questAbandons.find(actor.session.get());
            if (pending == _questAbandons.end())
                return;
            commands.swap(pending->second);
            _questAbandons.erase(pending);
        }
        for (QuestAbandonCommand const& command : commands)
        {
            Player* sender = ObjectAccessor::FindPlayer(command.sender);
            Group* group = player->GetGroup();
            bool sameParty = group && group->GetGUID() == command.group && sender
                && sender->IsInWorld() && sender->GetGroup() == group;
            bool authorized = sameParty && group->IsLeader(command.sender);
            bool removed = false;
            std::string reason;
            std::string reply;
            Quest const* quest = sObjectMgr->GetQuestTemplate(command.quest);
            std::string title = quest ? quest->GetTitle() : "Quest";
            if (title.size() > 150)
                title = "Quest";
            std::string label = title + " (" + std::to_string(command.quest) + ")";
            if (!authorized)
            {
                reason = "not_party_leader";
                reply = "Only my current party leader can ask me to drop a quest.";
            }
            else if (player->GetGUID() != command.character || player->GetName() != command.name
                || !actor.session->IsHeadless() || !player->IsInWorld())
            {
                reason = "character_changed_or_not_ready";
                reply = "I cannot drop a quest while my character is unavailable.";
            }
            else if (std::chrono::steady_clock::now() - command.received > std::chrono::seconds(30))
            {
                reason = "command_expired";
                reply = "That quest command expired; please send it again.";
            }
            else if (!command.quest)
            {
                reason = "invalid_quest_reference";
                reply = "Use: " + player->GetName() + " drop quest <quest link or numeric ID>.";
            }
            else if (player->FindQuestSlot(command.quest) >= MAX_QUEST_LOG_SIZE
                || !player->IsActiveQuest(command.quest))
            {
                reason = "not_in_quest_log";
                reply = "I do not have " + label + " in my quest log.";
            }
            else
            {
                WorldPackets::Quest::QuestLogRemoveQuest removal{WorldPacket(CMSG_QUESTLOG_REMOVE_QUEST)};
                removal.Slot = uint8(player->FindQuestSlot(command.quest));
                actor.session->HandleQuestLogRemoveQuest(removal);
                removed = player->FindQuestSlot(command.quest) >= MAX_QUEST_LOG_SIZE
                    && !player->IsActiveQuest(command.quest);
                reason = removed ? "abandoned" : "normal_abandon_rejected";
                reply = removed ? "Dropped " + label + "." : "I could not drop " + label + "; check quest items.";
            }
            bool sent = false;
            if (sameParty && player->GetGroup() == group && sender->GetGroup() == group)
            {
                Language language = player->GetTeamId() == TEAM_ALLIANCE ? LANG_COMMON : LANG_ORCISH;
                WorldPacket receipt(CMSG_MESSAGECHAT, reply.size() + 9);
                receipt << uint32(CHAT_MSG_PARTY) << uint32(language) << reply;
                actor.session->HandleMessagechatOpcode(receipt);
                sent = true;
            }
            RecordEvent(actor.session.get(), {{"type", "quest_abandon_result"}, {"quest_id", command.quest},
                {"sender_guid", std::to_string(command.sender.GetRawValue())}, {"quest_title", title},
                {"status", removed ? "completed" : "rejected"}, {"reason", reason}, {"receipt_submitted", sent}});
        }
    }

    Json::object CaptureSharedQuest(WorldSession* session, WorldPacket const& source, bool confirmation)
    {
        try
        {
            WorldPacket packet(source);
            ObjectGuid giver;
            SharedQuestOffer offer;
            offer.confirmation = confirmation;
            if (confirmation)
            {
                std::string title;
                packet >> offer.quest >> title >> offer.sharer;
            }
            else
            {
                packet >> giver >> offer.sharer >> offer.quest;
                if (!offer.sharer || giver != session->GetPlayer()->GetGUID())
                    return {{"type", "quest_details"}, {"quest_id", offer.quest}};
            }
            if (!offer.sharer || !offer.quest)
                return {{"type", "quest_share_offer"}, {"decode_error", true}};
            offer.received = std::chrono::steady_clock::now();
            {
                std::lock_guard<std::mutex> lock(_eventMutex);
                if (!_ownedSessions.contains(session))
                    return {};
                offer.sequence = ++_questShareSequence;
                _questShares[session] = offer;
            }
            return {{"type", "quest_share_offer"}, {"quest_id", offer.quest},
                {"sharer_guid", std::to_string(offer.sharer.GetRawValue())},
                {"share_kind", confirmation ? "party_confirm" : "details"}, {"offer_sequence", offer.sequence}};
        }
        catch (std::exception const&)
        {
            return {{"type", "quest_share_offer"}, {"decode_error", true}};
        }
    }

    void ResolveQuestShare(Actor& actor, Player* player, SharedQuestOffer const& offer, QuestShareMessages result)
    {
        if (player->GetDivider() != offer.sharer)
            return;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            auto replacement = _questShares.find(actor.session.get());
            if (replacement != _questShares.end() && replacement->second.sequence != offer.sequence)
                return;
        }
        WorldPackets::Quest::QuestPushResultClient response{WorldPacket(MSG_QUEST_PUSH_RESULT)};
        response.PlayerGuid = offer.sharer;
        response.QuestId = offer.quest;
        response.QuestShareMessage = result;
        actor.session->HandleQuestPushResult(response);
        // The normal handler cannot clear a divider whose sharer disconnected.
        // Clear only this consumed offer; never a newly captured replacement.
        if (player->GetDivider() == offer.sharer)
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            auto replacement = _questShares.find(actor.session.get());
            if (replacement == _questShares.end() || replacement->second.sequence == offer.sequence)
                player->SetDivider();
        }
    }

    void ProcessSharedQuest(Actor& actor, Player* player)
    {
        SharedQuestOffer offer;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            auto pending = _questShares.find(actor.session.get());
            if (pending == _questShares.end())
                return;
            offer = pending->second;
            _questShares.erase(pending);
        }
        std::string reason;
        QuestShareMessages result = QUEST_PARTY_MSG_CANT_TAKE_QUEST;
        Player* sharer = ObjectAccessor::FindPlayer(offer.sharer);
        Quest const* quest = sObjectMgr->GetQuestTemplate(offer.quest);
        bool accepted = false;
        if (player->GetDivider() != offer.sharer)
            reason = "obsolete_offer";
        else if (std::chrono::steady_clock::now() - offer.received > std::chrono::seconds(30))
        {
            reason = "offer_expired";
            result = QUEST_PARTY_MSG_SHARING_TIMER_EXPIRED;
        }
        else if (!actor.session->IsHeadless() || !player->IsInWorld() || !player->IsAlive()
            || player->IsBeingTeleported())
            reason = "character_not_ready";
        else if (!sharer || !sharer->IsInWorld() || !player->GetGroup()
            || player->GetGroup() != sharer->GetGroup())
        {
            reason = "sharer_not_in_party";
            result = QUEST_PARTY_MSG_NOT_IN_PARTY;
        }
        else if (!player->IsInMap(sharer))
            reason = "sharer_on_different_map";
        else if (!quest)
            reason = "unknown_quest";
        else if (player->GetQuestStatus(offer.quest) == QUEST_STATUS_INCOMPLETE
            || player->GetQuestStatus(offer.quest) == QUEST_STATUS_COMPLETE)
        {
            // Some quests were already added by the core's auto-accept path.
            accepted = true;
            reason = "already_present";
        }
        else if (!player->CanTakeQuest(quest, false))
            reason = "quest_not_eligible";
        else if (!player->CanAddQuest(quest, false))
        {
            // The manual accept handler acknowledges before CanAddQuest.
            // Preflight capacity so the sharer does not receive a false accept.
            reason = "quest_cannot_be_added";
            if (!player->SatisfyQuestLog(false))
            {
                reason = "quest_log_full";
                result = QUEST_PARTY_MSG_LOG_FULL;
            }
        }
        else
        {
            if (offer.confirmation)
            {
                WorldPackets::Quest::QuestConfirmAcceptClient confirmation{WorldPacket(CMSG_QUEST_CONFIRM_ACCEPT)};
                confirmation.QuestId = offer.quest;
                actor.session->HandleQuestConfirmAccept(confirmation);
            }
            else
            {
                WorldPacket acceptance(CMSG_QUESTGIVER_ACCEPT_QUEST, 16);
                acceptance << offer.sharer << offer.quest << uint32(0);
                actor.session->HandleQuestgiverAcceptQuestOpcode(acceptance);
            }
            accepted = player->GetQuestStatus(offer.quest) == QUEST_STATUS_INCOMPLETE
                || player->GetQuestStatus(offer.quest) == QUEST_STATUS_COMPLETE;
            reason = accepted ? "accepted" : "normal_accept_rejected";
            if (!accepted && !player->SatisfyQuestLog(false))
                result = QUEST_PARTY_MSG_LOG_FULL;
        }
        if (accepted)
            result = QUEST_PARTY_MSG_ACCEPT_QUEST;
        ResolveQuestShare(actor, player, offer, result);
        RecordEvent(actor.session.get(), {{"type", "quest_share_result"}, {"quest_id", offer.quest},
            {"sharer_guid", std::to_string(offer.sharer.GetRawValue())},
            {"share_kind", offer.confirmation ? "party_confirm" : "details"}, {"offer_sequence", offer.sequence},
            {"status", accepted ? "accepted" : "rejected"}, {"reason", reason}, {"share_result", uint32(result)},
            {"quest_status", uint32(player->GetQuestStatus(offer.quest))},
            {"divider_cleared", player->GetDivider() != offer.sharer}});
    }

    Json::object Connect(Json::object const& request, std::string const& name, bool create)
    {
        if (Text(request, "account", _accountName) != _accountName)
            return Error(request, "account_not_allowed", "Only the configured PresenceBridge.Account may be used");
        uint32 account = AccountMgr::GetId(_accountName);
        if (!account)
            return Error(request, "account_missing", "Create the dedicated game account before connecting");
        if (sWorldSessionMgr->FindSession(account))
            return Error(request, "account_in_use", "Dedicated game account has an existing client session");
        if (ObjectAccessor::FindPlayerByName(name))
            return Error(request, "character_online", "An online character cannot be taken over");
        auto previous = _actors.find(name);
        if (previous != _actors.end())
        {
            if (previous->second->phase == "created" || previous->second->phase == "failed")
            {
                RemoveCreationResult(previous->second->session.get());
                _actors.erase(previous);
            }
            else
                return Error(request, "busy", "Character already has a pending bridge operation");
        }
        ObjectGuid guid = sCharacterCache->GetCharacterGuidByName(name);
        if (create && guid)
            return Error(request, "character_exists", "Create never overwrites an existing character");
        if (!create && (!guid || sCharacterCache->GetCharacterAccountIdByGuid(guid) != account))
            return Error(request, "character_not_owned", "Character must belong to the dedicated game account");
        WorldPacket createPacket(CMSG_CHAR_CREATE, 64);
        if (create)
            createPacket << name << uint8(Unsigned(request, "race", 1, 255))
                << uint8(Unsigned(request, "class", 5, 255)) << uint8(Unsigned(request, "gender", 0, 1))
                << uint8(Unsigned(request, "skin", 0, 255)) << uint8(Unsigned(request, "face", 0, 255))
                << uint8(Unsigned(request, "hair_style", 0, 255)) << uint8(Unsigned(request, "hair_color", 0, 255))
                << uint8(Unsigned(request, "facial_hair", 0, 255)) << uint8(0);
        auto actor = std::make_shared<Actor>();
        actor->session = std::make_unique<WorldSession>(account, std::string(_accountName), 0, nullptr,
            SEC_PLAYER, EXPANSION_WRATH_OF_THE_LICH_KING, time_t(0), sWorld->GetDefaultDbcLocale(),
            0, false, false, 0);
        actor->pendingId = Text(request, "id");
        actor->loginDeadline = std::chrono::steady_clock::now() + std::chrono::seconds(90);
        _actors.emplace(name, actor);
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            _ownedSessions.insert(actor->session.get());
            if (!create)
                _ownedCharacters.emplace(actor->session.get(), guid);
        }
        if (create)
        {
            actor->phase = "creating";
            actor->session->HandleCharCreateOpcode(createPacket);
        }
        else
        {
            actor->phase = "loading";
            auto holder = std::make_shared<LoginQueryHolder>(account, guid);
            if (!holder->Initialize())
            {
                actor->phase = "failed";
                return Error(request, "login_failed", "Could not initialize character login queries");
            }
            std::weak_ptr<Actor> weakActor(actor);
            actor->session->AddQueryHolderCallback(CharacterDatabase.DelayQueryHolder(holder)).AfterComplete(
                [this, weakActor](SQLQueryHolderBase const& result)
                {
                    auto actor = weakActor.lock();
                    if (!actor)
                        return;
                    if (actor->loginCancelled)
                        return;
                    actor->session->HandlePlayerLoginFromDB(static_cast<LoginQueryHolder const&>(result));
                    bool loaded = actor->session->GetPlayer() && actor->session->GetPlayer()->IsInWorld();
                    actor->phase = loaded ? "ready" : "failed";
                    Finish(actor->pendingId, loaded, {{"status", loaded ? "completed" : "failed"},
                        {"attached", loaded}, {"controller", "presence"}});
                });
        }
        return Response(request, true, {{"status", "accepted"}, {"request_id", Text(request, "id")},
            {"phase", actor->phase}});
    }

    Json::object Observe(Json::object const& request, std::string const& name)
    {
        Player* player = ObjectAccessor::FindPlayerByName(name);
        if (!player || !player->IsInWorld())
        {
            auto actor = _actors.find(name);
            return Error(request, "character_offline",
                actor == _actors.end() ? "Character is offline" : actor->second->phase);
        }
        Json::object self = UnitState(player, 32);
        uint64 sequence = ++_snapshotSequence;
        std::string timestamp = Timestamp();
        self["sequence"] = sequence;
        self["timestamp"] = timestamp;
        self["map_id"] = player->GetMapId();
        self["zone_id"] = player->GetZoneId();
        self["area_id"] = player->GetAreaId();
        self["is_ghost"] = IsReleasedGhost(player);
        self["death_state"] = uint32(player->getDeathState());
        self["class"] = player->getClass();
        self["race"] = player->getRace();
        self["power_type"] = uint32(player->getPowerType());
        self["power"] = player->GetPower(player->getPowerType());
        self["max_power"] = player->GetMaxPower(player->getPowerType());
        self["money"] = player->GetMoney();
        self["moving"] = player->isMoving();
        self["controller_owned"] = _actors.contains(name) && _actors[name]->session->GetPlayer() == player;
        self["target_guid"] = std::to_string(player->GetTarget().GetRawValue());
        Json::object result{{"self", self}, {"sequence", sequence}, {"timestamp", timestamp}};
        result["recovery"] = RecoverySnapshot(player);
        result["trade"] = TradeSnapshot(player);
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            auto trade = _tradeFrames.find(player->GetSession());
            result["trade_receipt"] = trade != _tradeFrames.end() && !trade->second.receipt.empty()
                ? Json::value(trade->second.receipt) : Json::value(nullptr);
        }
        result["pending_loot"] = nullptr;
        if (auto found = _actors.find(name); found != _actors.end() && !found->second->lootId.empty())
        {
            Actor const& actor = *found->second;
            auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(
                actor.lootDeadline - std::chrono::steady_clock::now()).count();
            result["pending_loot"] = Json::object{{"request_id", actor.lootId},
                {"target_guid", std::to_string(actor.lootTarget.GetRawValue())},
                {"opening_spell_id", actor.lootSpell}, {"status", "opening"},
                {"remaining_ms", std::max<int64>(0, remaining)}};
        }
        result["protection"] = ProtectionState(player);
        result["party_invite"] = Json::value(nullptr);
        PartyInvite invitation;
        if (PendingPartyInvite(player, invitation))
        {
            std::string leader;
            sCharacterCache->GetCharacterNameByGuid(invitation.leader, leader);
            result["party_invite"] = Json::object{{"pending", true},
                {"inviter_guid", std::to_string(invitation.inviter.GetRawValue())}, {"inviter", invitation.name},
                {"leader_guid", std::to_string(invitation.leader.GetRawValue())}, {"leader", leader}};
        }
        result["party"] = Json::value(nullptr);
        if (Group* group = player->GetGroup())
        {
            Json::array members;
            for (auto const& member : group->GetMemberSlots())
            {
                if (members.size() == MAXRAIDSIZE)
                    break;
                Player* online = ObjectAccessor::FindPlayer(member.guid);
                members.push_back(Json::object{{"guid", std::to_string(member.guid.GetRawValue())},
                    {"name", member.name}, {"online", online && online->IsInWorld()}});
            }
            result["party"] = Json::object{{"leader_guid", std::to_string(group->GetLeaderGUID().GetRawValue())},
                {"leader", group->GetLeaderName()}, {"is_raid", group->isRaidGroup()}, {"members", std::move(members)}};
        }
        float radius = float(std::clamp(Number(request, "radius", 60), 1.0, 90.0));
        auto unitCheck = [player, radius](Unit* unit)
        {
            return unit != player && player->IsWithinDistInMap(unit, radius) && player->CanSeeOrDetect(unit);
        };
        std::list<Unit*> units;
        Acore::UnitListSearcher<decltype(unitCheck)> unitSearch(player, units, unitCheck);
        Cell::VisitObjects(player, unitSearch, radius);
        for (auto const& entry : player->GetMap()->GetPlayers())
            if (Player* other = entry.GetSource(); unitCheck(other))
                units.push_back(other);
        units.sort([player](Unit* a, Unit* b) { return player->GetDistance(a) < player->GetDistance(b); });
        Json::array nearby;
        std::set<ObjectGuid> seen;
        for (Unit* unit : units)
        {
            if (!seen.insert(unit->GetGUID()).second)
                continue;
            if (nearby.size() == 64)
                break;
            auto state = UnitState(unit);
            state["distance"] = player->GetDistance(unit);
            state["friendly"] = player->IsFriendlyTo(unit);
            state["hostile"] = player->IsHostileTo(unit);
            state["attackable"] = player->IsValidAttackTarget(unit);
            state["line_of_sight"] = player->IsWithinLOSInMap(unit);
            state["lootable"] = unit->IsCreature() && player->isAllowedToLoot(unit->ToCreature());
            if (unit->IsCreature() && unit->HasNpcFlag(UNIT_NPC_FLAG_QUESTGIVER) && !player->IsHostileTo(unit))
                for (auto const& field : QuestRelations(player, unit))
                    state[field.key()] = field.value();
            nearby.push_back(std::move(state));
        }
        result["nearby_units"] = std::move(nearby);
        auto objectCheck = [player, radius](GameObject* object)
        {
            return player->IsWithinDistInMap(object, radius) && player->CanSeeOrDetect(object);
        };
        std::list<GameObject*> objects;
        Acore::GameObjectListSearcher<decltype(objectCheck)> objectSearch(player, objects, objectCheck);
        Cell::VisitObjects(player, objectSearch, radius);
        objects.sort([player](GameObject* a, GameObject* b)
        {
            return player->GetDistance(a) < player->GetDistance(b);
        });
        Json::array nearbyObjects;
        for (GameObject* object : objects)
        {
            if (nearbyObjects.size() == 64)
                break;
            Json::object state{{"guid", std::to_string(object->GetGUID().GetRawValue())},
                {"name", object->GetName()}, {"entry", object->GetEntry()}, {"position", PositionOf(object)},
                {"distance", player->GetDistance(object)}, {"type", uint32(object->GetGoType())},
                {"is_questgiver", object->GetGoType() == GAMEOBJECT_TYPE_QUESTGIVER}};
            bool chest = object->GetGoType() == GAMEOBJECT_TYPE_CHEST;
            state["is_chest"] = chest;
            state["spawned"] = object->isSpawned();
            state["selectable"] = !object->HasGameObjectFlag(GO_FLAG_NOT_SELECTABLE);
            state["interact_in_range"] = object->IsWithinDistInMap(player);
            state["line_of_sight"] = player->IsWithinLOSInMap(object);
            state["quest_relevant"] = object->ActivateToQuest(player);
            SpellInfo const* opening = chest ? object->GetSpellForLock(player) : nullptr;
            state["opening_spell_available"] = opening != nullptr;
            if (opening)
            {
                state["opening_spell_id"] = opening->Id;
                state["opening_spell_name"] = std::string(opening->SpellName[0]).substr(0, 64);
                state["opening_cast_time_ms"] = opening->CalcCastTime(player);
            }
            if (object->GetGoType() == GAMEOBJECT_TYPE_QUESTGIVER)
                for (auto const& field : QuestRelations(player, object))
                    state[field.key()] = field.value();
            nearbyObjects.push_back(std::move(state));
        }
        result["nearby_objects"] = std::move(nearbyObjects);
        Json::array quests;
        for (uint16 slot = 0; slot < MAX_QUEST_LOG_SIZE; ++slot)
        {
            uint32 id = player->GetQuestSlotQuestId(slot);
            if (!id)
                continue;
            Quest const* quest = sObjectMgr->GetQuestTemplate(id);
            Json::array objectives;
            Json::array itemObjectives;
            for (uint8 objective = 0; objective < QUEST_OBJECTIVES_COUNT; ++objective)
            {
                int32 target = quest ? quest->RequiredNpcOrGo[objective] : 0;
                objectives.push_back(Json::object{{"index", objective},
                    {"current", player->GetQuestSlotCounter(slot, objective)},
                    {"required", quest ? quest->RequiredNpcOrGoCount[objective] : 0},
                    {"target_entry", target < 0 ? uint32(-int64(target)) : uint32(target)},
                    {"target_type", target < 0 ? "gameobject" : (target > 0 ? "creature" : "none")},
                    {"text", quest ? quest->ObjectiveText[objective] : ""}});
            }
            if (quest)
                for (uint8 objective = 0; objective < QUEST_ITEM_OBJECTIVES_COUNT; ++objective)
                    if (quest->RequiredItemId[objective])
                    {
                        ItemTemplate const* item = sObjectMgr->GetItemTemplate(quest->RequiredItemId[objective]);
                        itemObjectives.push_back(Json::object{{"item_id", quest->RequiredItemId[objective]},
                            {"name", item ? item->Name1 : ""},
                            {"current", player->GetItemCount(quest->RequiredItemId[objective])},
                            {"required", quest->RequiredItemCount[objective]}});
                    }
            quests.push_back(Json::object{{"id", id}, {"title", quest ? quest->GetTitle() : ""},
                {"status", uint32(player->GetQuestStatus(id))},
                {"status_name", QuestStatusName(player->GetQuestStatus(id))},
                {"complete", player->GetQuestStatus(id) == QUEST_STATUS_COMPLETE},
                {"objectives", std::move(objectives)},
                {"item_objectives", std::move(itemObjectives)}, {"details", quest ? quest->GetDetails() : ""},
                {"objective_text", quest ? quest->GetObjectives() : ""}});
        }
        result["quests"] = std::move(quests);
        Json::array inventory;
        Json::array equipment;
        Json::array index;
        auto addItem = [&inventory, &equipment, &index, player](Item* item, uint8 bag, uint8 slot)
        {
            if (!item || inventory.size() >= 200)
                return;
            Json::object facts = ItemFacts(player, item->GetTemplate(), item);
            inventory.emplace_back(facts);
            index.emplace_back(Json::object{{"guid", std::to_string(item->GetGUID().GetRawValue())},
                {"entry", item->GetEntry()}, {"name", item->GetTemplate()->Name1}, {"count", item->GetCount()},
                {"bag", bag}, {"slot", slot}, {"equipped", Player::IsEquipmentPos(item->GetPos())},
                {"quality", item->GetTemplate()->Quality}, {"is_quest", item->GetTemplate()->Class == ITEM_CLASS_QUEST
                    || player->HasQuestForItem(item->GetEntry())}});
            if (Player::IsEquipmentPos(item->GetPos()))
            {
                facts["equipment_slot"] = slot;
                equipment.emplace_back(std::move(facts));
            }
        };
        for (uint8 slot = 0; slot < INVENTORY_SLOT_ITEM_END; ++slot)
            addItem(player->GetItemByPos(INVENTORY_SLOT_BAG_0, slot), INVENTORY_SLOT_BAG_0, slot);
        for (uint8 bag = INVENTORY_SLOT_BAG_START; bag < INVENTORY_SLOT_BAG_END; ++bag)
            if (Bag* container = player->GetBagByPos(bag))
                for (uint32 slot = 0; slot < std::min(container->GetBagSize(), uint32(MAX_BAG_SIZE)); ++slot)
                    addItem(container->GetItemByPos(uint8(slot)), bag, uint8(slot));
        for (uint8 slot = EQUIPMENT_SLOT_START; slot < INVENTORY_SLOT_BAG_END; ++slot)
            if (!player->GetItemByPos(INVENTORY_SLOT_BAG_0, slot))
                equipment.emplace_back(Json::object{{"equipment_slot", slot},
                    {"slot_name", EquipmentSlotName(slot)}, {"empty", true}});
        std::sort(equipment.begin(), equipment.end(), [](Json::value const& a, Json::value const& b)
        {
            return Unsigned(a.as_object(), "equipment_slot") < Unsigned(b.as_object(), "equipment_slot");
        });
        result["inventory"] = std::move(inventory);
        result["inventory_index"] = std::move(index);
        result["equipment"] = std::move(equipment);
        result["bag_capacity"] = BagCapacity(player);
        result["inspected_item"] = nullptr;
        if (auto actor = _actors.find(name); actor != _actors.end() && actor->second->inspectedItem)
            if (Item* item = player->GetItemByGuid(actor->second->inspectedItem); CarriedItem(player, item))
                result["inspected_item"] = ItemFacts(player, item->GetTemplate(), item);
        result["vendor"] = CommerceSnapshot(player, false);
        result["trainer"] = CommerceSnapshot(player, true);
        Json::array buyback;
        if (auto const& vendor = result.at("vendor"); vendor.is_object()
            && vendor.as_object().at("available").as_bool())
            for (uint32 slot = BUYBACK_SLOT_START; slot < BUYBACK_SLOT_END; ++slot)
                if (Item* item = player->GetItemFromBuyBackSlot(slot))
                {
                    Json::object row = ItemFacts(player, item->GetTemplate(), item);
                    row["buyback_slot"] = slot;
                    row["price"] = player->GetUInt32Value(PLAYER_FIELD_BUYBACK_PRICE_1 + slot - BUYBACK_SLOT_START);
                    buyback.emplace_back(std::move(row));
                }
        result["buyback"] = std::move(buyback);
        Json::array spells;
        Json::array cooldowns;
        for (auto const& [id, learned] : player->GetSpellMap())
        {
            if (learned->State == PLAYERSPELL_REMOVED || !learned->Active || !player->HasSpell(id))
                continue;
            SpellInfo const* info = sSpellMgr->GetSpellInfo(id);
            if (!info || info->IsPassive())
                continue;
            if (spells.size() == 256)
                break;
            uint32 delay = player->GetSpellCooldownDelay(id);
            Json::object facts{{"id", id}, {"name", info->SpellName[0]}, {"cooldown_ms", delay}};
            if (auto buff = BuffSpellFacts(player, info))
                facts["buff"] = std::move(*buff);
            spells.emplace_back(std::move(facts));
            if (delay)
                cooldowns.push_back(Json::object{{"spell_id", id}, {"remaining_ms", delay}});
        }
        result["spells"] = std::move(spells);
        result["cooldowns"] = std::move(cooldowns);
        Json::array gossip;
        if (player->PlayerTalkClass)
        {
            GossipMenu const& gossipMenu = player->PlayerTalkClass->GetGossipMenu();
            result["gossip"] = Json::object{{"target_guid", std::to_string(gossipMenu.GetSenderGUID().GetRawValue())},
                {"menu_id", gossipMenu.GetMenuId()}};
            for (auto const& [id, item] : player->PlayerTalkClass->GetGossipMenu().GetMenuItems())
                gossip.push_back(Json::object{{"id", id}, {"text", item.Message},
                    {"coded", item.IsCoded}, {"cost", item.BoxMoney}, {"option_id", id},
                    {"option_type", item.OptionType},
                    {"is_spirit_healer", item.OptionType == GOSSIP_OPTION_SPIRITHEALER},
                    {"menu_id", gossipMenu.GetMenuId()},
                    {"target_guid", std::to_string(gossipMenu.GetSenderGUID().GetRawValue())}});
        }
        result["gossip_options"] = std::move(gossip);
        result["available_quests"] = QuestMenuSnapshot(player);
        result["quest_dialog"] = QuestDialogSnapshot(player);
        Json::array events;
        double cursor = Number(request, "since", Number(request, "after_event_id"));
        if (cursor < 0 || cursor > 9007199254740991.0 || std::floor(cursor) != cursor)
            return Error(request, "invalid_cursor", "Event cursor must be an integer from 0 through 2^53-1");
        uint64 since = uint64(cursor);
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            auto found = _events.find(player->GetGUID());
            if (found != _events.end())
                for (auto const& event : found->second)
                    if (event.at("id").to_number<uint64>() > since && events.size() < 64)
                        events.push_back(event);
            result["event_cursor"] = events.empty() ? since : events.back().as_object().at("id").to_number<uint64>();
        }
        result["events"] = std::move(events);
        // Guard telemetry has its own bounded stream and does not become a chat/attention event.
        Json::array guardEvents;
        uint64 guardCursor = 0;
        uint64 guardTotal = 0;
        uint64 guardSuppressed = 0;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            auto found = _guardTelemetry.find(player->GetGUID());
            if (found != _guardTelemetry.end())
            {
                for (auto const& event : found->second.events)
                    guardEvents.push_back(event);
                guardCursor = found->second.events.empty() ? 0
                    : found->second.events.back().at("id").to_number<uint64>();
                guardTotal = found->second.window.Total();
                guardSuppressed = found->second.window.Suppressed();
            }
        }
        result["guard_interventions"] = std::move(guardEvents);
        result["guard_event_cursor"] = guardCursor;
        result["guard_intervention_total"] = guardTotal;
        result["guard_intervention_suppressed"] = guardSuppressed;
        result["bounds"] = Json::object{{"radius", radius}, {"nearby_units", 64},
            {"nearby_objects", 64}, {"spells", 256}, {"inventory", 200}, {"inventory_index", 200}, {"events", 64},
            {"equipment", 23}, {"vendor_page", 24}, {"trainer_page", 24}, {"trainer_cached_rows", 1024},
            {"quest_menu", 64}, {"quest_choice_rewards", QUEST_REWARD_CHOICES_COUNT},
            {"quest_fixed_rewards", QUEST_REWARDS_COUNT}, {"quest_dialog_text", 4096},
            {"party_members", MAXRAIDSIZE}, {"guard_interventions", 64}};
        return Response(request, true, std::move(result));
    }

    Json::object CommerceResult(Json::object const& request, Player* player, uint32 before,
        Json::object result)
    {
        uint32 after = player->GetMoney();
        result["money_before"] = before;
        result["money_after"] = after;
        result["spent"] = before > after ? before - after : 0;
        result["received"] = after > before ? after - before : 0;
        result["request_id"] = Text(request, "id");
        return Response(request, true, std::move(result));
    }

    void OpenCommerce(WorldSession* session, ObjectGuid npc, bool trainer)
    {
        if (trainer)
        {
            WorldPackets::NPC::Hello packet{WorldPacket(CMSG_TRAINER_LIST, 8)};
            packet.Unit = npc;
            session->HandleTrainerListOpcode(packet);
        }
        else
        {
            CommerceMenu current = CommerceMenuFor(session, false);
            if (current.source == npc && session->GetCurrentVendor()
                && std::chrono::steady_clock::now() - current.opened < std::chrono::minutes(2))
            {
                // A normal gossip script may have opened a virtual vendor catalog on this NPC.
                session->SendListInventory(npc, session->GetCurrentVendor());
                return;
            }
            WorldPackets::Item::ListInventory packet{WorldPacket(CMSG_LIST_INVENTORY, 8)};
            packet.VendorGuid = npc;
            session->HandleListInventoryOpcode(packet);
        }
    }

    std::optional<Json::object> CommerceAction(Json::object const& request, Json::object const& action,
        Actor& actor, Player* player, std::string const& type)
    {
        bool vendorAction = type == "vendor_list" || type == "vendor_buy" || type == "vendor_sell"
            || type == "vendor_buyback"
            || type == "vendor_repair";
        bool trainerAction = type == "trainer_list" || type == "train_spell";
        bool itemAction = type == "equip_item" || type == "unequip_item" || type == "inspect_item";
        if (!vendorAction && !trainerAction && !itemAction && type != "gossip_select")
            return std::nullopt;
        ObjectGuid target(GuidNumber(action, "target_guid"));
        uint32 beforeMoney = player->GetMoney();
        if (itemAction)
        {
            ObjectGuid itemGuid(GuidNumber(action, "item_guid"));
            Item* item = player->GetItemByGuid(itemGuid);
            if (!CarriedItem(player, item))
                return Error(request, "item_not_carried", "The item must currently be carried by this character");
            uint32 itemId = item->GetEntry();
            if (type == "inspect_item")
            {
                actor.inspectedItem = itemGuid;
                return Response(request, true, {{"status", "completed"}, {"request_id", Text(request, "id")},
                    {"item_guid", std::to_string(itemGuid.GetRawValue())}, {"item_id", itemId}});
            }
            uint8 oldBag = item->GetBagSlot();
            uint8 oldSlot = item->GetSlot();
            if (type == "unequip_item")
            {
                if (!Player::IsEquipmentPos(item->GetPos()))
                    return Error(request, "item_not_equipped", "Select an equipped item or equipped bag");
                WorldPackets::Item::AutoStoreBagItem packet{WorldPacket(CMSG_AUTOSTORE_BAG_ITEM, 3)};
                packet.SourceBag = oldBag;
                packet.SourceSlot = oldSlot;
                packet.DestinationBag = NULL_BAG;
                actor.session->HandleAutoStoreBagItemOpcode(packet);
            }
            else if (action.if_contains("equipment_slot"))
            {
                uint8 slot = uint8(Unsigned(action, "equipment_slot", 0, INVENTORY_SLOT_BAG_END - 1));
                WorldPackets::Item::AutoEquipItemSlot packet{WorldPacket(CMSG_AUTOEQUIP_ITEM_SLOT, 9)};
                packet.ItemGuid = itemGuid;
                packet.DestinationSlot = slot;
                actor.session->HandleAutoEquipItemSlotOpcode(packet);
            }
            else
            {
                WorldPackets::Item::AutoEquipItem packet{WorldPacket(CMSG_AUTOEQUIP_ITEM, 2)};
                packet.SourceBag = oldBag;
                packet.SourceSlot = oldSlot;
                actor.session->HandleAutoEquipItemOpcode(packet);
            }
            Item* after = player->GetItemByGuid(itemGuid);
            bool carried = CarriedItem(player, after);
            bool equipped = carried && Player::IsEquipmentPos(after->GetPos());
            bool success = carried && (type == "unequip_item" ? !equipped
                : equipped && (!action.if_contains("equipment_slot")
                    || after->GetSlot() == Unsigned(action, "equipment_slot")));
            Json::object result{{"status", success ? "completed" : "failed"},
                {"reason", success ? "" : "normal_inventory_handler_rejected"},
                {"item_guid", std::to_string(itemGuid.GetRawValue())}, {"item_id", itemId},
                {"previous_slot", oldSlot}};
            if (after)
            {
                result["bag"] = after->GetBagSlot();
                result["slot"] = after->GetSlot();
                if (equipped)
                    result["equipment_slot"] = after->GetSlot();
            }
            return CommerceResult(request, player, beforeMoney, std::move(result));
        }
        if (type == "gossip_select")
        {
            Creature* npc = CommerceNpc(player, target, UNIT_NPC_FLAG_NONE);
            if (!npc || !player->PlayerTalkClass)
                return Error(request, "invalid_npc", "Gossip requires a visible nearby interactable creature");
            if (!action.if_contains("menu_id") || !action.if_contains("option_id"))
                return Error(request, "invalid_gossip", "Choose explicit advertised menu_id and option_id values");
            GossipMenu const& menu = player->PlayerTalkClass->GetGossipMenu();
            uint32 menuId = Unsigned(action, "menu_id");
            uint32 optionId = Unsigned(action, "option_id");
            GossipMenuItem const* option = menu.GetItem(optionId);
            if (menu.GetSenderGUID() != target || menu.GetMenuId() != menuId || !option || option->IsCoded)
                return Error(request, "stale_gossip", "Choose a current advertised non-coded gossip option");
            WorldPacket packet(CMSG_GOSSIP_SELECT_OPTION, 16);
            packet << target << menuId << optionId;
            actor.session->HandleGossipSelectOptionOpcode(packet);
            return CommerceResult(request, player, beforeMoney, {{"status", "accepted"},
                {"target_guid", std::to_string(target.GetRawValue())}, {"menu_id", menuId}, {"option_id", optionId},
                {"next_menu_id", player->PlayerTalkClass->GetGossipMenu().GetMenuId()}});
        }
        NPCFlags flags = trainerAction ? UNIT_NPC_FLAG_TRAINER
            : type == "vendor_repair" ? UNIT_NPC_FLAG_REPAIR : UNIT_NPC_FLAG_VENDOR;
        Creature* npc = CommerceNpc(player, target, flags);
        if (!npc)
            return Error(request, "invalid_service_npc", "Use a nearby visible NPC offering the requested service");
        if (type == "vendor_list" || type == "trainer_list")
        {
            bool trainer = type == "trainer_list";
            uint64 beforeRevision = CommerceMenuFor(actor.session.get(), trainer).revision;
            OpenCommerce(actor.session.get(), target, trainer);
            CommerceMenu menu = CommerceMenuFor(actor.session.get(), trainer);
            if (menu.source != target || menu.revision == beforeRevision)
                return Error(request, "service_unavailable", "The normal NPC handler did not advertise this service");
            uint32 page = Unsigned(action, "page", 0, 1024);
            if (page && uint64(page) * 24 >= menu.rows.size())
                return Error(request, "invalid_page", "Requested page is beyond the advertised menu");
            {
                std::lock_guard<std::mutex> lock(_eventMutex);
                (trainer ? _trainerMenus : _vendorMenus)[actor.session.get()].page = page;
            }
            if (!player->IsBeingTeleported())
                InteractionGesture(actor, player, CommerceNpc(player, target, flags), EMOTE_ONESHOT_TALK);
            return Response(request, true, {{"status", "completed"}, {"request_id", Text(request, "id")},
                {"target_guid", std::to_string(target.GetRawValue())}, {"page", page},
                {trainer ? "total_spells" : "total_items", menu.total},
                {"visible_count", std::min(size_t(24), menu.rows.size() - size_t(page) * 24)}});
        }
        if (type == "vendor_repair")
        {
            ObjectGuid itemGuid(GuidNumber(action, "item_guid"));
            std::map<ObjectGuid, uint32> damaged;
            auto remember = [&damaged, player, itemGuid](Item* item)
            {
                if (CarriedItem(player, item) && (!itemGuid || item->GetGUID() == itemGuid)
                    && item->GetUInt32Value(ITEM_FIELD_DURABILITY) < item->GetUInt32Value(ITEM_FIELD_MAXDURABILITY))
                    damaged[item->GetGUID()] = item->GetUInt32Value(ITEM_FIELD_DURABILITY);
            };
            if (itemGuid && !CarriedItem(player, player->GetItemByGuid(itemGuid)))
                return Error(request, "item_not_carried", "Repair only carried items, not remote storage");
            for (uint8 slot = 0; slot < INVENTORY_SLOT_ITEM_END; ++slot)
                remember(player->GetItemByPos(INVENTORY_SLOT_BAG_0, slot));
            for (uint8 bag = INVENTORY_SLOT_BAG_START; bag < INVENTORY_SLOT_BAG_END; ++bag)
                if (Bag* container = player->GetBagByPos(bag))
                    for (uint32 slot = 0; slot < std::min(container->GetBagSize(), uint32(MAX_BAG_SIZE)); ++slot)
                        remember(container->GetItemByPos(uint8(slot)));
            WorldPacket packet(CMSG_REPAIR_ITEM, 17);
            packet << target << itemGuid << uint8(0);
            actor.session->HandleRepairItemOpcode(packet);
            uint32 repaired = 0;
            bool partial = false;
            for (auto const& [guid, durability] : damaged)
                if (Item* item = player->GetItemByGuid(guid); CarriedItem(player, item))
                {
                    if (item->GetUInt32Value(ITEM_FIELD_DURABILITY) > durability)
                        ++repaired;
                    partial = partial || item->GetUInt32Value(ITEM_FIELD_DURABILITY)
                        < item->GetUInt32Value(ITEM_FIELD_MAXDURABILITY);
                }
            return CommerceResult(request, player, beforeMoney, {{"status", repaired || damaged.empty()
                ? "completed" : "failed"}, {"reason", repaired || damaged.empty() ? "" : "repair_not_verified"},
                {"target_guid", std::to_string(target.GetRawValue())},
                {"item_guid", std::to_string(itemGuid.GetRawValue())}, {"repaired", repaired}, {"partial", partial}});
        }
        CommerceMenu menu;
        if (!CommerceMenuCurrent(player, target, trainerAction, menu))
            return Error(request, "menu_not_open", "Open the NPC's current vendor or trainer list first");
        if (type == "vendor_buy")
        {
            uint32 slot = Unsigned(action, "vendor_slot", 0, 255);
            uint32 entry = Unsigned(action, "item_id");
            uint32 count = Unsigned(action, "count", 1, 255);
            if (!slot || !entry || !count)
                return Error(request, "invalid_purchase", "Use an advertised item/slot and 1 through 255 bundles");
            auto row = std::find_if(menu.rows.begin(), menu.rows.end(), [slot, entry](Json::value const& value)
            {
                return Unsigned(value.as_object(), "vendor_slot") == slot
                    && Unsigned(value.as_object(), "item_id") == entry;
            });
            if (row == menu.rows.end())
                return Error(request, "stale_offer", "The vendor slot/item pair was not advertised in this menu");
            uint32 beforeCount = player->GetItemCount(entry, false);
            uint32 expected = 0;
            if (!CommercePurchaseUnits(Unsigned(row->as_object(), "buy_count"), count, expected))
                return Error(request, "invalid_count", "The bundle quantity is outside normal item-count bounds");
            WorldPackets::Item::BuyItem packet{WorldPacket(CMSG_BUY_ITEM, 25)};
            packet.VendorGuid = target;
            packet.Item = entry;
            packet.Slot = slot;
            packet.Count = count;
            actor.session->HandleBuyItemOpcode(packet);
            uint32 afterCount = player->GetItemCount(entry, false);
            uint32 acquired = afterCount > beforeCount ? afterCount - beforeCount : 0;
            bool success = expected && acquired == expected;
            OpenCommerce(actor.session.get(), target, false);
            return CommerceResult(request, player, beforeMoney, {{"status", success ? "completed" : "failed"},
                {"reason", success ? "" : "purchase_not_verified"},
                {"target_guid", std::to_string(target.GetRawValue())},
                {"item_id", entry}, {"bundle_count", count}, {"item_count", acquired}});
        }
        if (type == "vendor_sell")
        {
            ObjectGuid itemGuid(GuidNumber(action, "item_guid"));
            Item* item = player->GetItemByGuid(itemGuid);
            if (!CarriedItem(player, item))
                return Error(request, "item_not_carried", "Select a carried item to sell");
            uint32 count = Unsigned(action, "count", 0, item->GetCount());
            if (!count)
                return Error(request, "invalid_count", "Choose an explicit positive number of items to sell");
            uint32 entry = item->GetEntry();
            uint32 beforeCount = player->GetItemCount(entry, false);
            WorldPackets::Item::SellItem packet{WorldPacket(CMSG_SELL_ITEM, 20)};
            packet.VendorGuid = target;
            packet.ItemGuid = itemGuid;
            packet.Count = count;
            actor.session->HandleSellItemOpcode(packet);
            uint32 afterCount = player->GetItemCount(entry, false);
            uint32 sold = beforeCount > afterCount ? beforeCount - afterCount : 0;
            bool success = sold == count;
            return CommerceResult(request, player, beforeMoney, {{"status", success ? "completed" : "failed"},
                {"reason", success ? "" : "sale_not_verified"}, {"target_guid", std::to_string(target.GetRawValue())},
                {"item_guid", std::to_string(itemGuid.GetRawValue())}, {"item_id", entry}, {"count", sold}});
        }
        if (type == "vendor_buyback")
        {
            ObjectGuid itemGuid(GuidNumber(action, "item_guid"));
            uint32 slot = Unsigned(action, "buyback_slot", 0, BUYBACK_SLOT_END - 1);
            if (slot < BUYBACK_SLOT_START)
                return Error(request, "invalid_buyback_slot", "Choose an advertised buyback slot from 74 through 85");
            Item* item = player->GetItemFromBuyBackSlot(slot);
            if (!item || item->GetGUID() != itemGuid)
                return Error(request, "stale_buyback", "The advertised buyback slot no longer contains that item");
            uint32 entry = item->GetEntry();
            uint32 count = item->GetCount();
            uint32 price = player->GetUInt32Value(PLAYER_FIELD_BUYBACK_PRICE_1 + slot - BUYBACK_SLOT_START);
            uint32 beforeCount = player->GetItemCount(entry, false);
            WorldPackets::Item::BuybackItem packet{WorldPacket(CMSG_BUYBACK_ITEM, 12)};
            packet.VendorGuid = target;
            packet.Slot = slot;
            actor.session->HandleBuybackItem(packet);
            uint32 afterCount = player->GetItemCount(entry, false);
            uint32 restored = afterCount > beforeCount ? afterCount - beforeCount : 0;
            bool success = restored == count && !player->GetItemFromBuyBackSlot(slot)
                && beforeMoney >= player->GetMoney() && beforeMoney - player->GetMoney() == price;
            return CommerceResult(request, player, beforeMoney, {{"status", success ? "completed" : "failed"},
                {"reason", success ? "" : "buyback_not_verified"},
                {"target_guid", std::to_string(target.GetRawValue())},
                {"item_guid", std::to_string(itemGuid.GetRawValue())}, {"item_id", entry}, {"count", restored}});
        }
        uint32 spellId = Unsigned(action, "spell_id", 0, 0x7FFFFFFF);
        auto row = std::find_if(menu.rows.begin(), menu.rows.end(), [spellId](Json::value const& value)
        {
            return Unsigned(value.as_object(), "spell_id") == spellId;
        });
        if (!spellId || row == menu.rows.end())
            return Error(request, "stale_offer", "Select a spell advertised by this trainer");
        std::set<uint32> beforeSpells;
        for (auto const& [id, learned] : player->GetSpellMap())
            if (learned->State != PLAYERSPELL_REMOVED && player->HasSpell(id))
                beforeSpells.insert(id);
        WorldPackets::NPC::TrainerBuySpell packet{WorldPacket(CMSG_TRAINER_BUY_SPELL, 12)};
        packet.TrainerGUID = target;
        packet.SpellID = int32(spellId);
        actor.session->HandleTrainerBuySpellOpcode(packet);
        Json::array learnedSpells;
        uint32 learnedCount = 0;
        for (auto const& [id, learned] : player->GetSpellMap())
            if (learned->State != PLAYERSPELL_REMOVED && player->HasSpell(id) && !beforeSpells.contains(id))
            {
                ++learnedCount;
                if (learnedSpells.size() < 64)
                    learnedSpells.emplace_back(id);
            }
        std::set<uint32> expectedSpells;
        if (SpellInfo const* info = sSpellMgr->GetSpellInfo(spellId))
            for (auto const& effect : info->Effects)
                if (effect.IsEffect(SPELL_EFFECT_LEARN_SPELL) && effect.TriggerSpell)
                    expectedSpells.insert(effect.TriggerSpell);
        if (expectedSpells.empty())
            expectedSpells.insert(spellId);
        bool success = !learnedSpells.empty() && std::all_of(expectedSpells.begin(), expectedSpells.end(),
            [player](uint32 spell) { return player->HasSpell(spell); });
        OpenCommerce(actor.session.get(), target, true);
        return CommerceResult(request, player, beforeMoney, {{"status", success ? "completed" : "failed"},
            {"reason", success ? "" : "training_not_verified"}, {"target_guid", std::to_string(target.GetRawValue())},
            {"spell_id", spellId}, {"learned_spell_count", learnedCount},
            {"learned_spells_truncated", learnedCount > learnedSpells.size()},
            {"learned_spells", std::move(learnedSpells)}});
    }

    void InteractionGesture(Actor& actor, Player* player, WorldObject* source, uint32 emote)
    {
        if (!source || !player->IsAlive() || !player->IsInWorld() || player->isMoving() || player->IsInCombat()
            || player->IsNonMeleeSpellCast(false) || !player->SpellQueue.empty()
            || player->HasUnitState(UNIT_STATE_STUNNED | UNIT_STATE_CONFUSED | UNIT_STATE_FLEEING)
            || !player->IsWithinDistInMap(source, INTERACTION_DISTANCE) || !player->IsWithinLOSInMap(source)
            || (CurrentGuardAction && CurrentGuardAction->interactionVisualObserved))
            return;
        auto now = std::chrono::steady_clock::now();
        if (now < actor.nextInteractionGesture)
            return;
        ClearCosmeticEmote(actor, player);
        actor.nextInteractionGesture = now + std::chrono::seconds(1);
        // One-shot broadcast only: no text emote, movement, facing, or persistent pose.
        player->HandleEmoteCommand(emote);
    }

    Json::object QuestAction(Json::object const& request, Json::object const& action, Actor& actor,
        Player* player, Object* source, std::string const& type)
    {
        if (!action.if_contains("target_guid") || Text(action, "target_guid").empty())
            return Error(request, "invalid_target", "Quest actions require an explicit advertised target_guid");
        ObjectGuid sourceGuid = source->GetGUID();
        uint32 questId = Unsigned(action, "quest_id");
        Quest const* quest = sObjectMgr->GetQuestTemplate(questId);
        if (!questId || !quest)
            return Error(request, "invalid_quest", "Choose a positive advertised quest_id");
        if (!QuestSource(player, sourceGuid, questId))
            return Error(request, "invalid_questgiver", "Use a nearby questgiver or the current carried quest starter");
        if (source->IsItem() && type != "query_quest" && type != "accept_quest")
            return Error(request, "questgiver_mismatch", "An item starter only supports query and acceptance");
        auto menu = CurrentQuestFrame(actor.session.get(), false);
        // An owned item's exact StartQuest is advertised by its inventory facts;
        // normal item quest opening has no preceding NPC gossip menu.
        bool advertised = source->IsItem() && type == "query_quest" && source->hasQuest(questId);
        if (menu && menu->source == source->GetGUID() && QuestFrameAvailable(player, *menu))
            for (auto const& row : menu->rows)
                if (Unsigned(row.as_object(), "id") == questId)
                    advertised = true;
        if (!advertised)
            return Error(request, "stale_quest_menu", "Interact with this questgiver and choose a current quest first");
        bool starting = source->hasQuest(questId);
        bool involved = source->hasInvolvedQuest(questId);
        if ((type == "query_quest" && !starting && !involved) || (type == "accept_quest" && !starting)
            || (type != "query_quest" && type != "accept_quest" && !involved))
            return Error(request, "questgiver_mismatch", "The current questgiver does not offer this quest operation");
        auto dialog = CurrentQuestFrame(actor.session.get(), true);
        bool matching = dialog && dialog->source == source->GetGUID() && dialog->quest == questId
            && QuestFrameAvailable(player, *dialog);
        if (type == "accept_quest" && (!matching || dialog->phase != "details"
            || !dialog->fields.at("activate_accept").as_bool()))
            return Error(request, "quest_not_offered", "Read this questgiver's current accept dialog first");
        if (type == "request_reward" && (!matching || dialog->phase != "request_items"))
            return Error(request, "quest_not_requested", "Open this questgiver's current item turn-in dialog first");
        uint32 reward = 0;
        uint32 chosenItem = 0;
        uint32 chosenCount = 0;
        if (type == "reward_quest")
        {
            if (!matching || dialog->phase != "offer_reward")
                return Error(request, "reward_not_offered", "Open this questgiver's current reward offer first");
            if (!action.if_contains("reward_index"))
                return Error(request, "reward_choice_required", "Choose an explicit advertised reward_index");
            reward = Unsigned(action, "reward_index", 0, QUEST_REWARD_CHOICES_COUNT - 1);
            auto const& choices = dialog->fields.at("choice_rewards").as_array();
            bool valid = choices.empty() && reward == 0 && !quest->GetRewChoiceItemsCount();
            for (auto const& value : choices)
            {
                auto const& row = value.as_object();
                if (Unsigned(row, "reward_index") == reward)
                {
                    chosenItem = Unsigned(row, "item_id");
                    chosenCount = Unsigned(row, "count");
                    valid = chosenItem && chosenItem == quest->RewardChoiceItemId[reward]
                        && chosenCount == quest->RewardChoiceItemCount[reward];
                }
            }
            if (!valid)
                return Error(request, "stale_reward", "The selected reward does not match the current offer");
        }
        uint32 beforeMoney = player->GetMoney();
        uint32 beforeStatus = uint32(player->GetQuestStatus(questId));
        bool beforeActive = player->IsActiveQuest(questId);
        bool beforeInLog = player->FindQuestSlot(questId) < MAX_QUEST_LOG_SIZE;
        if (type == "accept_quest" && (beforeActive || beforeInLog))
            return Error(request, "quest_already_accepted",
                "This quest is already active; no second acceptance was sent");
        std::map<uint32, uint32> beforeItems;
        if (type == "reward_quest")
        {
            if (chosenItem)
                beforeItems[chosenItem] = player->GetItemCount(chosenItem, false);
            for (uint32 index = 0; index < QUEST_REWARDS_COUNT; ++index)
                if (uint32 item = quest->RewardItemId[index])
                    beforeItems[item] = player->GetItemCount(item, false);
            for (uint32 index = 0; index < QUEST_ITEM_OBJECTIVES_COUNT; ++index)
                if (uint32 item = quest->RequiredItemId[index])
                    beforeItems[item] = player->GetItemCount(item, false);
        }
        uint64 beforeRevision = dialog ? dialog->revision : 0;
        ClearCosmeticEmote(actor, player);
        if (CurrentGuardAction)
            CurrentGuardAction->quest = questId;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            _rewardReceipts.erase(actor.session.get());
        }
        if (type == "query_quest")
        {
            WorldPacket packet(CMSG_QUESTGIVER_QUERY_QUEST, 13);
            packet << sourceGuid << questId << uint8(0);
            actor.session->HandleQuestgiverQueryQuestOpcode(packet);
        }
        else if (type == "accept_quest")
        {
            WorldPacket packet(CMSG_QUESTGIVER_ACCEPT_QUEST, 16);
            packet << sourceGuid << questId << uint32(0);
            actor.session->HandleQuestgiverAcceptQuestOpcode(packet);
        }
        else if (type == "complete_quest")
        {
            WorldPacket packet(CMSG_QUESTGIVER_COMPLETE_QUEST, 12);
            packet << sourceGuid << questId;
            actor.session->HandleQuestgiverCompleteQuest(packet);
        }
        else if (type == "request_reward")
        {
            WorldPacket packet(CMSG_QUESTGIVER_REQUEST_REWARD, 12);
            packet << sourceGuid << questId;
            actor.session->HandleQuestgiverRequestRewardOpcode(packet);
        }
        else
        {
            WorldPacket packet(CMSG_QUESTGIVER_CHOOSE_REWARD, 16);
            packet << sourceGuid << questId << reward;
            actor.session->HandleQuestgiverChooseRewardOpcode(packet);
        }
        bool rewardReceipt = false;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            auto found = _rewardReceipts.find(actor.session.get());
            rewardReceipt = found != _rewardReceipts.end() && found->second == questId;
        }
        auto after = CurrentQuestFrame(actor.session.get(), true);
        bool freshDialog = after && after->revision != beforeRevision && after->source == sourceGuid
            && after->quest == questId;
        bool afterInLog = player->FindQuestSlot(questId) < MAX_QUEST_LOG_SIZE;
        bool afterActive = player->IsActiveQuest(questId);
        bool accepted = !beforeActive && !beforeInLog && afterActive && afterInLog;
        bool rewardHook = CurrentGuardAction && CurrentGuardAction->quest == questId
            && CurrentGuardAction->questRewarded;
        bool trackingReward = quest->HasFlag(QUEST_FLAGS_TRACKING) && rewardHook
            && player->IsQuestRewarded(questId);
        bool success = type == "reward_quest" ? rewardReceipt && player->IsQuestRewarded(questId)
            : type == "accept_quest" ? accepted || trackingReward
            : type == "request_reward" ? (freshDialog && after->phase == "offer_reward") || trackingReward
            : type == "complete_quest" ? (freshDialog
                && (after->phase == "request_items" || after->phase == "offer_reward")) || trackingReward
            : freshDialog || accepted || trackingReward;
        if (success && sourceGuid.IsCreature() && player->IsInWorld() && !player->IsBeingTeleported())
            InteractionGesture(actor, player, player->GetMap()->GetCreature(sourceGuid), EMOTE_ONESHOT_TALK);
        Json::array changes;
        for (auto const& [item, before] : beforeItems)
        {
            uint32 current = player->GetItemCount(item, false);
            changes.emplace_back(Json::object{{"item_id", item}, {"before", before}, {"after", current},
                {"delta", int64(current) - int64(before)}});
        }
        Json::object result{{"status", success ? "completed" : "failed"},
            {"reason", success ? "" : "normal_quest_handler_did_not_verify_requested_transition"},
            {"target_guid", std::to_string(sourceGuid.GetRawValue())}, {"quest_id", questId},
            {"quest_status_before", beforeStatus}, {"quest_status_after", uint32(player->GetQuestStatus(questId))},
            {"quest_status_name_before", QuestStatusName(QuestStatus(beforeStatus))},
            {"quest_status_name_after", QuestStatusName(player->GetQuestStatus(questId))},
            {"in_log_before", beforeInLog}, {"in_log_after", afterInLog}, {"accepted_quest", accepted},
            {"tracking_quest_rewarded", trackingReward}, {"reward_receipt", rewardReceipt},
            {"quest_reward_hook", rewardHook},
            {"item_changes", std::move(changes)}};
        if (after)
        {
            result["phase_after"] = after->phase;
            result["dialog_quest_id_after"] = after->quest;
        }
        if (type == "reward_quest")
        {
            result["reward_index"] = reward;
            result["chosen_item_id"] = chosenItem;
            result["chosen_item_count"] = chosenCount;
        }
        return CommerceResult(request, player, beforeMoney, std::move(result));
    }

    Json::object Action(Json::object const& request, std::string const& name)
    {
        GuardActionContext context;
        context.request = Text(request, "id");
        if (auto actor = _actors.find(name); actor != _actors.end())
            if (Player* player = actor->second->session->GetPlayer())
                context.owner = player->GetGUID();
        if (auto action = request.if_contains("action"); action && action->is_object())
            if (auto type = action->as_object().if_contains("type"); type && type->is_string())
                context.action = std::string(type->as_string());
        if (auto sequence = request.if_contains("observed_sequence"); sequence && sequence->is_number())
        {
            double value = sequence->to_number<double>();
            if (std::isfinite(value) && value >= 0 && value <= 9007199254740991.0 && std::floor(value) == value)
                context.observedSequence = uint64(value);
        }
        GuardActionScope scope(context);
        Json::object response = ActionImpl(request, name);
        try
        {
            if (!context.interventions.empty() || context.dropped)
            {
                char const* key = response.at("ok").as_bool() ? "result" : "error";
                auto& details = response.at(key).as_object();
                details["guard_interventions"] = std::move(context.interventions);
                details["guard_interventions_truncated"] = context.dropped != 0;
                details["guard_interventions_dropped"] = context.dropped;
            }
        }
        catch (std::exception const&)
        {
            // Diagnostic allocation/formatting cannot change the action's accepted or rejected result.
        }
        return response;
    }

    Json::object ActionImpl(Json::object const& request, std::string const& name)
    {
        auto actorEntry = _actors.find(name);
        if (actorEntry == _actors.end() || actorEntry->second->phase != "ready")
            return Error(request, "not_attached", "Actions require a bridge-owned independent character");
        Actor& actor = *actorEntry->second;
        Player* player = actor.session->GetPlayer();
        if (!player || !player->IsInWorld() || player->IsBeingTeleported())
            return Error(request, "not_ready", "Character is not ready for actions");
        auto actionValue = request.if_contains("action");
        if (!actionValue || !actionValue->is_object())
            return Error(request, "invalid_action", "action must be an object");
        auto const& action = actionValue->as_object();
        std::string type = Text(action, "type");
        std::string id = Text(request, "id");
        if (type == "stop" || type == "move_to" || type == "target"
            || (action.if_contains("target_guid")
                && GuidNumber(action, "target_guid") != player->GetTarget().GetRawValue()))
            ClearSpiritHealerFrames(actor.session.get());
        if (!actor.lootId.empty() && SupersedesPickup(type))
        {
            if (type == "loot" && GuidNumber(action, "target_guid") == actor.lootTarget.GetRawValue())
            {
                auto response = Error(request, "loot_in_progress",
                    "Monitor the original opening request; do not recast");
                response["result"] = Json::object{{"request_id", actor.lootId}, {"status", "accepted"},
                    {"pending", true}, {"operation", "open_loot"}};
                return response;
            }
            CancelOpeningLoot(actor, "superseded_by_" + type);
        }
        if (type == "stop")
        {
            ClearCosmeticEmote(actor, player);
            player->AttackStop();
            player->InterruptNonMeleeSpells(false);
            if (actor.protectionMode == "evading" || actor.protectionMode == "stopped_no_safe_path")
                return Response(request, true, {{"status", "completed"}, {"request_id", id},
                    {"protection_escape_preserved", true}});
            player->GetMotionMaster()->Clear();
            player->StopMoving();
            if (!actor.motionId.empty())
                Finish(actor.motionId, false, {{"status", "failed"}, {"reason", "cancelled"}});
            actor.motionId.clear();
            return Response(request, true, {{"status", "completed"}, {"request_id", id}});
        }
        if (type == "party_accept" || type == "party_decline")
            return RespondToPartyInvite(request, action, actor, player);
        if (type == "trade_begin" || type == "trade_accept" || type == "trade_unaccept" || type == "trade_cancel")
            return RespondToTrade(request, action, actor, player);
        if ((actor.protectionMode == "evading" || actor.protectionMode == "stopped_no_safe_path"
            || ProtectionUncertain(player)) && (type == "attack" || type == "move_to" || type == "follow"))
        {
            GuardIntervention(player, nullptr, "action_gate", "avoidance_execution_reserved");
            return Error(request, "protection_escape",
                "Protected creature avoidance is active; no health override applies");
        }
        if (type == "spirit_healer_activate"
            || (!player->IsAlive() && (type == "interact" || type == "gossip_select")))
            return SpiritHealerAction(request, action, actor, player, type);
        if (!player->IsAlive() && !(type == "move_to" && IsReleasedGhost(player)))
            return Error(request, "dead", "Character is dead; no automatic revive or other GM shortcut is applied");
        if (auto commerce = CommerceAction(request, action, actor, player, type))
        {
            ClearCosmeticEmote(actor, player);
            return std::move(*commerce);
        }
        if (type == "emote" && action.if_contains("emote"))
            return NamedEmoteAction(request, action, actor, player);
        if (type == "say" || type == "emote")
        {
            if (type == "emote" && action.if_contains("target_guid"))
                return Error(request, "invalid_emote", "Custom emote text has no target; use a named emote");
            std::string text = Text(action, "text");
            if (text.empty() || text.size() > 255 || text.find_first_of("\r\n") != std::string::npos)
                return Error(request, "invalid_text", "Text must contain 1-255 bytes without line breaks");
            if (type == "say")
            {
                std::string channel = Text(action, "channel", "say");
                if (channel != "say" && channel != "party")
                    return Error(request, "invalid_channel", "Chat channel must be say or party");
                Language language = player->GetTeamId() == TEAM_ALLIANCE ? LANG_COMMON : LANG_ORCISH;
                if (channel == "party")
                {
                    Group* group = player->GetOriginalGroup();
                    if (!group)
                        group = player->GetGroup();
                    if (!group || group->isBGGroup())
                        return Error(request, "not_grouped", "Party chat requires a current normal group");
                    uint64 before;
                    {
                        std::lock_guard<std::mutex> lock(_eventMutex);
                        before = _eventSequence;
                    }
                    WorldPacket chat(CMSG_MESSAGECHAT, text.size() + 9);
                    chat << uint32(CHAT_MSG_PARTY) << uint32(language) << text;
                    actor.session->HandleMessagechatOpcode(chat);
                    bool delivered = false;
                    std::string sender = std::to_string(player->GetGUID().GetRawValue());
                    {
                        std::lock_guard<std::mutex> lock(_eventMutex);
                        auto queue = _events.find(player->GetGUID());
                        if (queue != _events.end())
                            for (auto const& event : queue->second)
                                if (event.at("id").to_number<uint64>() > before && Text(event, "type") == "chat"
                                    && Unsigned(event, "chat_type", MAX_CHAT_MSG_TYPE) == CHAT_MSG_PARTY
                                    && Text(event, "sender_guid") == sender)
                                {
                                    delivered = true;
                                    break;
                                }
                    }
                    if (!delivered)
                        return Error(request, "chat_not_sent", "Normal party chat handler did not send the message");
                }
                else
                    player->Say(text, language);
                return Response(request, true, {{"status", "completed"}, {"request_id", id}, {"channel", channel}});
            }
            player->TextEmote(text);
            return Response(request, true, {{"status", "completed"}, {"request_id", id}});
        }
        if (type == "move_to")
        {
            if (action.if_contains("map_id") && Unsigned(action, "map_id") != player->GetMapId())
                return Error(request, "map_mismatch", "move_to cannot move between maps");
            double inputX = Number(action, "x", player->GetPositionX());
            double inputY = Number(action, "y", player->GetPositionY());
            double inputZ = Number(action, "z", player->GetPositionZ());
            if (std::abs(inputX) > 17067 || std::abs(inputY) > 17067 || std::abs(inputZ) > 17067)
                return Error(request, "invalid_destination", "Coordinates exceed map bounds");
            float x = float(inputX);
            float y = float(inputY);
            float z = float(inputZ);
            if (player->HasUnitState(UNIT_STATE_ROOT | UNIT_STATE_STUNNED) || player->IsInFlight())
                return Error(request, "cannot_move", "Character cannot move in its current state");
            if (player->GetDistance(x, y, z) > 80 || !Acore::IsValidMapCoord(x, y, z))
                return Error(request, "invalid_destination", "Destination must be valid and within 80 yards");
            PathGenerator path(player);
            if (!path.CalculatePath(x, y, z, false) || path.GetPathType() != PATHFIND_NORMAL)
                return Error(request, "no_path",
                    "No complete normal navigation path; direct-line fallback is disabled");
            if (!actor.motionId.empty())
                Finish(actor.motionId, false, {{"status", "failed"}, {"reason", "superseded"}});
            actor.motionId = id;
            actor.motionAsGhost = IsReleasedGhost(player);
            actor.destination.Relocate(x, y, z);
            actor.motionDeadline = std::chrono::steady_clock::now() + std::chrono::seconds(45);
            ClearCosmeticEmote(actor, player);
            player->GetMotionMaster()->Clear();
            player->GetMotionMaster()->MovePoint(1, x, y, z, FORCED_MOVEMENT_NONE, 0, 0, true, false);
            return Response(request, true, {{"status", "accepted"}, {"request_id", id},
                {"destination", Json::object{{"x", x}, {"y", y}, {"z", z}}}});
        }
        ObjectGuid guid = player->GetTarget();
        std::string guidText = Text(action, "target_guid");
        if (!guidText.empty())
        {
            if (guidText.find_first_not_of("0123456789") != std::string::npos)
                return Error(request, "invalid_target", "target_guid must be an unsigned decimal string");
            size_t consumed = 0;
            uint64 raw = std::stoull(guidText, &consumed, 10);
            if (consumed != guidText.size())
                return Error(request, "invalid_target", "target_guid must be an unsigned decimal string");
            guid = ObjectGuid(raw);
        }
        if (type == "target" && !guid)
        {
            player->SetSelection(ObjectGuid::Empty);
            return Response(request, true, {{"status", "completed"}, {"target_guid", "0"}});
        }
        if (guid.IsItem() && (type == "query_quest" || type == "accept_quest"))
        {
            Object* source = QuestSource(player, guid, Unsigned(action, "quest_id"));
            if (!source)
                return Error(request, "invalid_quest_item", "Use an owned carried item with its exact StartQuest");
            return QuestAction(request, action, actor, player, source, type);
        }
        WorldObject* object = guid ? ObjectAccessor::GetWorldObject(*player, guid) : nullptr;
        if (type == "cast" && guidText.empty() && !guid)
            object = player;
        if (!object || !player->CanSeeOrDetect(object) || !player->IsWithinDistInMap(object, 90))
            return Error(request, "invalid_target", "Target must be currently visible on the same map within 90 yards");
        Unit* unit = object->ToUnit();
        if (type == "target")
        {
            player->SetSelection(guid);
            return Response(request, true, {{"status", "completed"},
                {"target_guid", std::to_string(guid.GetRawValue())}});
        }
        if (type == "follow")
        {
            if (!unit || unit == player || !player->IsFriendlyTo(unit) || !player->IsWithinLOSInMap(unit)
                || player->HasUnitState(UNIT_STATE_ROOT | UNIT_STATE_STUNNED))
                return Error(request, "invalid_target",
                    "Follow requires a visible friendly unit and a mobile character");
            if (!actor.motionId.empty())
                Finish(actor.motionId, false, {{"status", "failed"}, {"reason", "superseded"}});
            actor.motionId.clear();
            float distance = float(std::clamp(Number(action, "distance", 3), 1.0, 20.0));
            float angle = float(M_PI * 0.5);
            ClearCosmeticEmote(actor, player);
            player->GetMotionMaster()->MoveFollow(unit, distance, angle, MOTION_SLOT_ACTIVE, true, false);
            return Response(request, true, {{"status", "accepted"}, {"request_id", id}, {"persistent", true},
                {"follow_distance", distance}, {"follow_angle", angle}});
        }
        if (type == "attack")
        {
            if (unit && BlocksDamage(player, unit))
            {
                GuardIntervention(player, unit, "action_attack", "protected_target_effect");
                return Error(request, "protected_target",
                    "The persistent Moon instruction forbids attacking this creature");
            }
            if (actor.protectionMode == "evading" || actor.protectionMode == "stopped_no_safe_path")
            {
                GuardIntervention(player, unit, "action_attack", "avoidance_execution_reserved");
                return Error(request, "protection_escape",
                    "Protected attacker avoidance is active; no health override applies");
            }
            if (!unit || !player->IsValidAttackTarget(unit) || !player->IsWithinLOSInMap(unit))
                return Error(request, "invalid_target", "Unit is not a legal visible attack target");
            ClearCosmeticEmote(actor, player);
            player->SetSelection(guid);
            player->SetFacingToObject(unit);
            WorldPacket packet(CMSG_ATTACKSWING, 8);
            packet << guid;
            actor.session->HandleAttackSwingOpcode(packet);
            bool active = player->GetVictim() == unit;
            if (active)
            {
                if (!actor.motionId.empty())
                    Finish(actor.motionId, false, {{"status", "failed"}, {"reason", "superseded_by_attack"}});
                actor.motionId.clear();
                if (!player->HasUnitState(UNIT_STATE_ROOT | UNIT_STATE_STUNNED) && !player->IsInFlight())
                {
                    player->GetMotionMaster()->Clear();
                    player->GetMotionMaster()->MoveChase(unit);
                }
            }
            return active ? Response(request, true, {{"status", "accepted"}, {"request_id", id}})
                : Error(request, "attack_rejected", "Normal attack handler rejected the target");
        }
        if (type == "cast")
        {
            uint32 spell = Unsigned(action, "spell_id");
            SpellInfo const* info = sSpellMgr->GetSpellInfo(spell);
            if (!unit || !info || info->IsPassive() || !player->HasActiveSpell(spell))
                return Error(request, "unknown_spell", "Character must know an active unit-targeted spell");
            bool blockedDamage = BlocksDamage(player, unit);
            if (blockedDamage
                || ((info->IsPositive() || info->HasEffect(SPELL_EFFECT_HEAL)
                    || info->HasEffect(SPELL_EFFECT_HEAL_PCT) || info->HasEffect(SPELL_EFFECT_HEAL_MAX_HEALTH))
                    && BlocksBeneficial(player, unit, info)))
            {
                GuardIntervention(player, unit, "action_cast",
                    blockedDamage ? "protected_target_effect" : "beneficial_intervention_withheld", spell);
                return Error(request, "protected_target",
                    "Moon protection or observed taming forbids this intervention");
            }
            ClearCosmeticEmote(actor, player);
            SpellCastResult cast = player->CastSpell(unit, spell, false);
            if (cast != SPELL_CAST_OK)
                return Error(request, "cast_rejected",
                    "Normal spell validation rejected cast, code " + std::to_string(cast));
            return Response(request, true, {{"status", "accepted"}, {"request_id", id}, {"spell_id", spell}});
        }
        if (type == "loot")
            return Loot(request, actor, object);
        if (type == "query_quest" || type == "accept_quest" || type == "complete_quest"
            || type == "request_reward" || type == "reward_quest")
            return QuestAction(request, action, actor, player, object, type);
        if (type == "interact")
        {
            if (object->IsGameObject() && object->ToGameObject()->GetGoType() == GAMEOBJECT_TYPE_CHEST)
            {
                auto response = Error(request, "use_loot",
                    "A chest requires its normal opening cast; use the loot action");
                response["result"] = Json::object{{"optional_loot_action", Json::object{
                    {"type", "loot"}, {"target_guid", std::to_string(guid.GetRawValue())}}}};
                return response;
            }
            if (!player->IsWithinDistInMap(object, INTERACTION_DISTANCE) || !player->IsWithinLOSInMap(object))
                return Error(request, "out_of_range",
                    "Interaction requires normal interaction distance and line of sight");
            if (Creature* creature = object->ToCreature())
            {
                if (!player->GetNPCIfCanInteractWith(guid, UNIT_NPC_FLAG_GOSSIP | UNIT_NPC_FLAG_QUESTGIVER))
                    return Error(request, "cannot_interact", "NPC cannot be interacted with normally");
                WorldPacket packet(CMSG_GOSSIP_HELLO, 8);
                packet << creature->GetGUID();
                auto beforeMenu = CurrentQuestFrame(actor.session.get(), false);
                auto beforeDialog = CurrentQuestFrame(actor.session.get(), true);
                ClearCosmeticEmote(actor, player);
                actor.session->HandleGossipHelloOpcode(packet);
                auto afterMenu = CurrentQuestFrame(actor.session.get(), false);
                auto afterDialog = CurrentQuestFrame(actor.session.get(), true);
                bool ready = player->IsInWorld() && !player->IsBeingTeleported()
                    && player->GetNPCIfCanInteractWith(guid, UNIT_NPC_FLAG_GOSSIP | UNIT_NPC_FLAG_QUESTGIVER);
                bool freshMenu = ready && afterMenu && afterMenu->source == guid
                    && (!beforeMenu || afterMenu->revision != beforeMenu->revision);
                bool freshDialog = ready && afterDialog && afterDialog->source == guid
                    && (!beforeDialog || afterDialog->revision != beforeDialog->revision);
                if (freshMenu || freshDialog)
                    InteractionGesture(actor, player, player->GetMap()->GetCreature(guid), EMOTE_ONESHOT_TALK);
            }
            else if (GameObject* gameObject = object->ToGameObject())
            {
                WorldPacket packet(CMSG_GAMEOBJ_USE, 8);
                packet << gameObject->GetGUID();
                ClearCosmeticEmote(actor, player);
                actor.session->HandleGameObjectUseOpcode(packet);
            }
            else
                return Error(request, "cannot_interact", "Target is not an NPC or game object");
            return Response(request, true, {{"status", "accepted"}, {"request_id", id}});
        }
        return Error(request, "unsupported_action", "Action type is not supported");
    }

    Json::object CapturePartyInvite(WorldSession* session, WorldPacket const& source)
    {
        try
        {
            WorldPacket packet(source);
            uint8 pending;
            std::string name;
            packet >> pending >> name;
            if (!pending)
                return {};
            Player* player = session->GetPlayer();
            Group* group = player ? player->GetGroupInvite() : nullptr;
            ObjectGuid inviter = sCharacterCache->GetCharacterGuidByName(name);
            if (!group || !inviter.IsPlayer() || inviter == player->GetGUID())
                return {};
            PartyInvite invitation{inviter, group->GetLeaderGUID(), group->GetGUID(), name};
            {
                std::lock_guard<std::mutex> lock(_eventMutex);
                _partyInvites[session] = invitation;
            }
            return {{"type", "party_invite"}, {"inviter_guid", std::to_string(inviter.GetRawValue())},
                {"inviter", name}, {"pending", true}};
        }
        catch (std::exception const&)
        {
            return {};
        }
    }

    bool PendingPartyInvite(Player* player, PartyInvite& invitation)
    {
        Group* group = player->GetGroupInvite();
        if (!group || group->GetInvited(player->GetGUID()) != player)
            return false;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            auto found = _partyInvites.find(player->GetSession());
            if (found == _partyInvites.end())
                return false;
            invitation = found->second;
        }
        // Never apply an old decision to a different, subsequently received invitation.
        bool current = invitation.group ? invitation.group == group->GetGUID()
            : invitation.leader == group->GetLeaderGUID();
        if (current)
            invitation.leader = group->GetLeaderGUID();
        return current;
    }

    Json::object RespondToPartyInvite(Json::object const& request, Json::object const& action,
        Actor& actor, Player* player)
    {
        std::string expected = Text(action, "inviter_guid");
        if (expected.empty() || expected.size() > 20 || expected.find_first_not_of("0123456789") != std::string::npos)
            return Error(request, "invalid_inviter", "inviter_guid must be a nonzero unsigned decimal player GUID");
        ObjectGuid inviter;
        try
        {
            inviter = ObjectGuid(std::stoull(expected));
        }
        catch (std::exception const&)
        {
            return Error(request, "invalid_inviter", "inviter_guid exceeds the unsigned 64-bit range");
        }
        if (!inviter.IsPlayer())
            return Error(request, "invalid_inviter", "inviter_guid must identify a player");
        PartyInvite invitation;
        if (!PendingPartyInvite(player, invitation))
            return Error(request, "no_party_invite", "No received party invitation is currently pending");
        if (inviter != invitation.inviter)
            return Error(request, "party_invite_changed",
                "Pending invitation is from a different player; observe again");
        Group* pending = player->GetGroupInvite();
        ObjectGuid pendingGroup = pending->GetGUID();
        ObjectGuid pendingLeader = pending->GetLeaderGUID();
        bool accept = Text(action, "type") == "party_accept";
        WorldPacket packet(accept ? CMSG_GROUP_ACCEPT : CMSG_GROUP_DECLINE, 4);
        if (accept)
        {
            packet << uint32(0);
            actor.session->HandleGroupAcceptOpcode(packet);
            Group* joined = player->GetGroup();
            if (!joined || !joined->IsMember(player->GetGUID()) || (pendingGroup
                ? joined->GetGUID() != pendingGroup : joined->GetLeaderGUID() != pendingLeader))
                return Error(request, "party_rejected", "Normal group handler did not accept this invitation");
        }
        else
        {
            actor.session->HandleGroupDeclineOpcode(packet);
            if (player->GetGroupInvite())
                return Error(request, "party_rejected", "Normal group handler did not decline this invitation");
        }
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            _partyInvites.erase(actor.session.get());
        }
        return Response(request, true, {{"status", "completed"}, {"request_id", Text(request, "id")},
            {"joined", accept}, {"inviter_guid", expected}});
    }

    void CaptureLoot(WorldSession* session, WorldPacket const& source)
    {
        LootWindow window;
        try
        {
            WorldPacket packet(source);
            uint8 type;
            packet >> window.guid >> type;
            if (type)
            {
                packet >> window.gold >> window.visibleSlots;
                for (uint16 index = 0; index < window.visibleSlots; ++index)
                {
                    LootSlot slot{};
                    uint32 ignored;
                    uint8 permission;
                    packet >> slot.slot >> slot.item >> slot.count >> ignored >> ignored >> ignored >> permission;
                    if (permission == LOOT_SLOT_TYPE_ALLOW_LOOT || permission == LOOT_SLOT_TYPE_OWNER)
                        window.allowed.push_back(slot);
                }
                window.valid = true;
            }
        }
        catch (std::exception const&)
        {
            window.valid = false;
        }
        std::optional<OpeningLoot> opening;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            if (auto found = _openingLoot.find(session); found != _openingLoot.end())
                opening = found->second;
        }
        if (opening && window.valid && opening->target == window.guid)
        {
            Player* player = session->GetPlayer();
            Spell* spell = player ? player->GetCurrentSpell(CURRENT_GENERIC_SPELL) : nullptr;
            bool matching = spell && PickupCastMatches(opening->target.GetRawValue(), opening->spell, opening->count,
                spell->m_targets.GetGOTargetGUID().GetRawValue(), spell->GetSpellInfo()->Id, spell->m_cast_count);
            bool synchronous = CurrentGuardAction && player && CurrentGuardAction->owner == player->GetGUID()
                && CurrentGuardAction->request == opening->request && CurrentGuardAction->action == "loot";
            if (matching || synchronous)
                window.openingRequest = opening->request;
        }
        std::lock_guard<std::mutex> lock(_eventMutex);
        _lootWindows[session] = std::move(window);
    }

    Json::object Loot(Json::object const& request, Actor& actor, WorldObject* object)
    {
        Player* player = actor.session->GetPlayer();
        if (GameObject* chest = object->ToGameObject())
            return OpenChestLoot(request, actor, player, chest);
        Creature* creature = object->ToCreature();
        if (!creature || creature->IsAlive() || !player->isAllowedToLoot(creature))
            return Error(request, "not_lootable", "Corpse is not normally lootable by this character");
        if (!player->IsWithinDistInMap(creature, INTERACTION_DISTANCE) || !player->IsWithinLOSInMap(creature))
            return Error(request, "out_of_range", "Loot requires normal interaction range and line of sight");
        ObjectGuid guid = creature->GetGUID();
        if (player->GetLootGUID())
        {
            WorldPacket release(CMSG_LOOT_RELEASE, 8);
            release << player->GetLootGUID();
            actor.session->HandleLootReleaseOpcode(release);
        }
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            _lootWindows.erase(actor.session.get());
        }
        WorldPacket open(CMSG_LOOT, 8);
        open << guid;
        ClearCosmeticEmote(actor, player);
        actor.session->HandleLootOpcode(open);
        LootWindow window;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            auto found = _lootWindows.find(actor.session.get());
            if (found != _lootWindows.end())
                window = found->second;
        }
        if (!window.valid || window.guid != guid || player->GetLootGUID() != guid)
            return Error(request, "loot_rejected", "Normal loot handler did not open this corpse");
        if (player->IsInWorld() && !player->IsBeingTeleported())
            InteractionGesture(actor, player, player->GetMap()->GetCreature(guid), EMOTE_ONESHOT_LOOT);
        return StoreLootWindow(request, actor, guid, window);
    }

    bool ChestSourceUsable(Player* player, GameObject* chest)
    {
        // Normal opening spell validation is authoritative; generic object LOS is diagnostic only.
        return chest && chest->GetGoType() == GAMEOBJECT_TYPE_CHEST && chest->isSpawned()
            && !chest->HasGameObjectFlag(GO_FLAG_NOT_SELECTABLE) && player->HaveAtClient(chest)
            && player->CanSeeOrDetect(chest) && chest->IsWithinDistInMap(player);
    }

    bool MatchingOpeningCast(Actor const& actor, Player* player)
    {
        Spell* spell = player ? player->GetCurrentSpell(CURRENT_GENERIC_SPELL) : nullptr;
        return spell && PickupCastMatches(actor.lootTarget.GetRawValue(), actor.lootSpell, actor.lootCastCount,
            spell->m_targets.GetGOTargetGUID().GetRawValue(), spell->GetSpellInfo()->Id, spell->m_cast_count);
    }

    void ClearOpeningLoot(Actor& actor)
    {
        std::lock_guard<std::mutex> lock(_eventMutex);
        _openingLoot.erase(actor.session.get());
        actor.lootId.clear();
        actor.lootTarget.Clear();
        actor.lootSpell = 0;
        actor.lootCastCount = 0;
    }

    void CancelOpeningLoot(Actor& actor, std::string const& reason)
    {
        if (actor.lootId.empty())
            return;
        std::string id = actor.lootId;
        ObjectGuid target = actor.lootTarget;
        uint32 spell = actor.lootSpell;
        Player* player = actor.session->GetPlayer();
        bool casting = MatchingOpeningCast(actor, player);
        ClearOpeningLoot(actor);
        if (casting)
            player->InterruptNonMeleeSpells(false);
        if (player && player->GetLootGUID() == target)
        {
            WorldPacket release(CMSG_LOOT_RELEASE, 8);
            release << target;
            actor.session->HandleLootReleaseOpcode(release);
        }
        Finish(id, false, {{"status", "failed"}, {"request_id", id}, {"reason", reason},
            {"target_guid", std::to_string(target.GetRawValue())}, {"opening_spell_id", spell},
            {"operation", "open_loot"}, {"pending", false}});
    }

    void ProcessOpeningLoot(Actor& actor, Player* player)
    {
        if (actor.lootId.empty())
            return;
        GameObject* chest = player->GetMap()->GetGameObject(actor.lootTarget);
        LootWindow window;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            if (auto found = _lootWindows.find(actor.session.get()); found != _lootWindows.end())
                window = found->second;
        }
        bool receipt = PickupReceiptMatches(actor.lootId, actor.lootTarget.GetRawValue(), window.valid,
            window.openingRequest, window.guid.GetRawValue(), player->GetLootGUID().GetRawValue());
        bool expired = std::chrono::steady_clock::now() > actor.lootDeadline;
        bool usable = ChestSourceUsable(player, chest);
        PickupProgress progress = ChestPickupProgress(player->IsAlive(), usable, expired,
            receipt, MatchingOpeningCast(actor, player));
        if (progress == PickupProgress::Waiting)
            return;
        if (progress == PickupProgress::Failed)
        {
            CancelOpeningLoot(actor, expired ? "opening_timeout" : !player->IsAlive() ? "opening_death"
                : !usable ? "opening_source_unavailable" : "opening_interrupted_or_rejected");
            return;
        }
        std::string id = actor.lootId;
        ObjectGuid target = actor.lootTarget;
        uint32 spell = actor.lootSpell;
        ClearOpeningLoot(actor);
        Json::object request{{"id", id}, {"op", "action"}, {"character", player->GetName()}};
        Json::object response = StoreLootWindow(request, actor, target, window);
        bool ok = response.at("ok").as_bool();
        Json::object result = response.at("result").as_object();
        result["status"] = ok ? "completed" : "failed";
        result["request_id"] = id;
        result["target_guid"] = std::to_string(target.GetRawValue());
        result["opening_spell_id"] = spell;
        result["operation"] = "open_loot";
        result["pending"] = false;
        if (!ok)
            result["reason"] = Text(response.at("error").as_object(), "code", "loot_not_stored");
        Finish(id, ok, std::move(result));
    }

    Json::object OpenChestLoot(Json::object const& request, Actor& actor, Player* player, GameObject* chest)
    {
        if (chest->GetGoType() != GAMEOBJECT_TYPE_CHEST)
            return Error(request, "unsupported_loot_source", "Loot supports creature corpses and ordinary chests");
        if (!ChestSourceUsable(player, chest))
            return Error(request, "chest_unavailable",
                "Chest must be spawned, selectable, visible and in normal range");
        SpellInfo const* opening = chest->GetSpellForLock(player);
        if (!opening || !opening->HasEffect(SPELL_EFFECT_OPEN_LOCK))
            return Error(request, "opening_unavailable",
                "No normal opening spell is available for this chest and character");
        if (player->IsNonMeleeSpellCast(false) || !player->SpellQueue.empty()
            || !player->CanExecutePendingSpellCastRequest(opening))
            return Error(request, "opening_not_ready", "Wait for the current spell or cooldown before opening");
        if (!actor.motionId.empty())
        {
            Finish(actor.motionId, false, {{"status", "failed"}, {"reason", "superseded_by_loot"}});
            actor.motionId.clear();
        }
        // Standing still is execution of this chosen pickup, not a new follow policy.
        ClearCosmeticEmote(actor, player);
        player->GetMotionMaster()->Clear();
        player->StopMoving();
        if (player->GetLootGUID())
        {
            WorldPacket release(CMSG_LOOT_RELEASE, 8);
            release << player->GetLootGUID();
            actor.session->HandleLootReleaseOpcode(release);
        }
        actor.lootId = Text(request, "id");
        actor.lootTarget = chest->GetGUID();
        actor.lootSpell = opening->Id;
        if (++actor.nextLootCastCount == 0)
            ++actor.nextLootCastCount;
        actor.lootCastCount = actor.nextLootCastCount;
        actor.lootDeadline = std::chrono::steady_clock::now() + std::chrono::seconds(20);
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            _lootWindows.erase(actor.session.get());
            _openingLoot[actor.session.get()] = {actor.lootId, actor.lootTarget, actor.lootSpell, actor.lootCastCount};
        }
        WorldPacket cast(CMSG_CAST_SPELL, 32);
        cast << actor.lootCastCount << opening->Id << uint8(0);
        SpellCastTargets targets;
        targets.SetGOTarget(chest);
        targets.Write(cast);
        actor.session->HandleCastSpellOpcode(cast);
        LootWindow window;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            if (auto found = _lootWindows.find(actor.session.get()); found != _lootWindows.end())
                window = found->second;
        }
        if (PickupReceiptMatches(actor.lootId, actor.lootTarget.GetRawValue(), window.valid,
            window.openingRequest, window.guid.GetRawValue(), player->GetLootGUID().GetRawValue()))
        {
            ObjectGuid target = actor.lootTarget;
            ClearOpeningLoot(actor);
            return StoreLootWindow(request, actor, target, window);
        }
        if (!MatchingOpeningCast(actor, player))
        {
            CancelOpeningLoot(actor, "opening_rejected");
            auto response = Error(request, "opening_rejected",
                "The normal spell handler rejected or interrupted opening");
            response["result"] = Json::object{{"status", "failed"}, {"request_id", Text(request, "id")},
                {"reason", "opening_rejected"}, {"target_guid", std::to_string(chest->GetGUID().GetRawValue())},
                {"opening_spell_id", opening->Id}, {"operation", "open_loot"}, {"pending", false}};
            return response;
        }
        return Response(request, true, {{"status", "accepted"}, {"request_id", actor.lootId},
            {"target_guid", std::to_string(actor.lootTarget.GetRawValue())}, {"opening_spell_id", actor.lootSpell},
            {"pending", true}, {"operation", "open_loot"}, {"timeout_ms", 20000}, {"movement_suspended", true}});
    }

    Json::object StoreLootWindow(Json::object const& request, Actor& actor, ObjectGuid guid, LootWindow const& window)
    {
        Player* player = actor.session->GetPlayer();
        uint32 moneyBefore = player->GetMoney();
        if (window.gold)
        {
            WorldPacket money(CMSG_LOOT_MONEY, 0);
            actor.session->HandleLootMoneyOpcode(money);
        }
        uint32 moneyAfter = player->GetMoney();
        uint32 gained = moneyAfter > moneyBefore ? moneyAfter - moneyBefore : 0;
        Json::array acquired;
        uint32 skipped = window.visibleSlots - uint32(window.allowed.size());
        // Slots come from the same response a real client receives. Reserved/rolled
        // items are excluded; the normal handler revalidates every allowed slot.
        for (auto const& slot : window.allowed)
        {
            if (player->GetLootGUID() != guid)
            {
                ++skipped;
                continue;
            }
            uint32 before = player->GetItemCount(slot.item);
            WorldPacket take(CMSG_AUTOSTORE_LOOT_ITEM, 1);
            take << slot.slot;
            actor.session->HandleAutostoreLootItemOpcode(take);
            uint32 after = player->GetItemCount(slot.item);
            uint32 stored = StoredPickupCount(before, after);
            if (stored)
                acquired.push_back(Json::object{{"item_id", slot.item}, {"count", stored}});
            else
                ++skipped;
        }
        if (player->GetLootGUID() == guid)
        {
            WorldPacket release(CMSG_LOOT_RELEASE, 8);
            release << guid;
            actor.session->HandleLootReleaseOpcode(release);
        }
        if (acquired.empty() && gained == 0)
            return Error(request, "loot_not_stored",
                "No money or permitted items could be stored under normal loot rules");
        return Response(request, true, {{"status", "completed"}, {"request_id", Text(request, "id")},
            {"items", std::move(acquired)}, {"copper", gained}, {"skipped_slots", skipped}, {"partial", skipped > 0}});
    }

    Json::object NamedEmoteAction(Json::object const& request, Json::object const& action, Actor& actor, Player* player)
    {
        auto text = action.if_contains("text");
        if (text && !text->is_null() && (!text->is_string() || !text->as_string().empty()))
            return Error(request, "invalid_emote", "Choose a named emote or custom text, not both");
        uint32 emote = OrdinaryEmoteIdByName(Text(action, "emote"));
        EmotesTextEntry const* entry = emote ? sEmotesTextStore.LookupEntry(emote) : nullptr;
        if (!entry)
            return Error(request, "unsupported_emote", "The named ordinary emote is not supported");
        ObjectGuid target(GuidNumber(action, "target_guid"));
        if (target)
        {
            Unit* unit = ObjectAccessor::GetUnit(*player, target);
            if (!unit || !player->HaveAtClient(unit) || !player->CanSeeOrDetect(unit)
                || !player->IsWithinDistInMap(unit, 90))
                return Error(request, "emote_target_not_visible",
                    "Named emote target must be currently visible nearby");
        }
        uint64 before;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            before = _eventSequence;
        }
        // Explicit zero remains untargeted. Do not change selection, follow or combat intent.
        uint32 constexpr variant = 1;
        WorldPacket packet(CMSG_TEXT_EMOTE, 16);
        packet << emote << variant << target;
        actor.session->HandleTextEmoteOpcode(packet);
        bool delivered = false;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            auto queue = _events.find(player->GetGUID());
            if (queue != _events.end())
                for (auto const& event : queue->second)
                    if (event.at("id").to_number<uint64>() > before && Text(event, "type") == "text_emote"
                        && Text(event, "actor_guid") == std::to_string(player->GetGUID().GetRawValue())
                        && Unsigned(event, "emote_id") == emote && Unsigned(event, "emote_variant") == variant
                        && event.at("target_guid").is_string()
                        && Text(event, "target_guid") == std::to_string(target.GetRawValue()))
                    {
                        delivered = true;
                        break;
                    }
        }
        if (!delivered)
            return Error(request, "emote_not_sent", "The normal emote handler did not deliver a matching receipt");
        return Response(request, true, {{"status", "completed"}, {"request_id", Text(request, "id")},
            {"emote", std::string(OrdinaryEmoteNameById(emote))}, {"emote_id", emote}, {"animation_id", entry->textid},
            {"target_guid", std::to_string(target.GetRawValue())}});
    }

    Json::object TextEmoteEvent(WorldSession* session, WorldPacket const& packet)
    {
        auto frame = DecodeTextEmote(std::span<std::uint8_t const>(packet.contents(), packet.size()));
        if (!frame)
            return {};
        ObjectGuid sender(frame->Sender);
        if (!sender.IsPlayer() || !sEmotesTextStore.LookupEntry(frame->Emote))
            return {};
        Player* observer = session->GetPlayer();
        if (!observer)
            return {};
        std::optional<TextEmoteCorrelation> correlation;
        {
            std::lock_guard<std::mutex> lock(_eventMutex);
            correlation = _emoteCorrelations.Take(observer->GetGUID().GetRawValue(), *frame, EmoteMilliseconds());
        }
        if (correlation && correlation->TargetKnown && correlation->HasTarget)
        {
            Unit* target = ObjectAccessor::GetUnit(*observer, ObjectGuid(correlation->Target));
            if (!target || !observer->HaveAtClient(target) || !observer->CanSeeOrDetect(target)
                || !observer->IsWithinDistInMap(target, 90)
                || target->GetNameForLocaleIdx(session->GetSessionDbLocaleIndex()) != frame->TargetName)
                correlation.reset();
        }
        std::string actorName;
        sCharacterCache->GetCharacterNameByGuid(sender, actorName);
        std::string_view name = OrdinaryEmoteNameById(frame->Emote);
        Json::object event{{"type", "text_emote"}, {"actor_guid", std::to_string(frame->Sender)},
            {"actor_name", actorName}, {"actor_is_player", true},
            {"direction", sender == observer->GetGUID() ? "outgoing" : "incoming"},
            {"emote_id", frame->Emote}, {"emote_name", nullptr}, {"emote_variant", frame->Variant},
            {"target_guid", nullptr}, {"target_name", frame->TargetName}, {"target_is_player", nullptr},
            {"explicit_target", nullptr}, {"target_guid_source", "packet_has_no_guid"}};
        if (!name.empty())
            event["emote_name"] = std::string(name);
        if (correlation)
        {
            event["explicit_target"] = correlation->HasTarget;
            if (correlation->TargetKnown)
            {
                event["target_guid"] = std::to_string(correlation->Target);
                event["target_is_player"] = correlation->TargetIsPlayer;
                event["target_guid_source"] = "normal_text_emote_hook";
            }
        }
        return event;
    }

    Json::object ChatEvent(WorldPacket const& source)
    {
        try
        {
            WorldPacket packet(source);
            uint8 type;
            int32 language;
            ObjectGuid sender;
            ObjectGuid receiver;
            uint32 ignored;
            std::string senderName;
            std::string receiverName;
            std::string message;
            packet >> type >> language >> sender >> ignored;
            switch (type)
            {
                case CHAT_MSG_MONSTER_SAY:
                case CHAT_MSG_MONSTER_PARTY:
                case CHAT_MSG_MONSTER_YELL:
                case CHAT_MSG_MONSTER_WHISPER:
                case CHAT_MSG_MONSTER_EMOTE:
                case CHAT_MSG_RAID_BOSS_EMOTE:
                case CHAT_MSG_RAID_BOSS_WHISPER:
                case CHAT_MSG_BATTLENET:
                    packet >> ignored >> senderName >> receiver;
                    if (receiver && !receiver.IsPlayer() && !receiver.IsPet())
                        packet >> ignored >> receiverName;
                    break;
                case CHAT_MSG_WHISPER_FOREIGN:
                    packet >> ignored >> senderName >> receiver;
                    break;
                case CHAT_MSG_BG_SYSTEM_NEUTRAL:
                case CHAT_MSG_BG_SYSTEM_ALLIANCE:
                case CHAT_MSG_BG_SYSTEM_HORDE:
                    packet >> receiver;
                    if (receiver && !receiver.IsPlayer())
                        packet >> ignored >> receiverName;
                    break;
                case CHAT_MSG_ACHIEVEMENT:
                case CHAT_MSG_GUILD_ACHIEVEMENT:
                    packet >> receiver;
                    break;
                default:
                    if (source.GetOpcode() == SMSG_GM_MESSAGECHAT)
                        packet >> ignored >> senderName;
                    if (type == CHAT_MSG_CHANNEL)
                        packet >> receiverName;
                    packet >> receiver;
                    break;
            }
            packet >> ignored >> message;
            if (senderName.empty() && sender.IsPlayer())
                sCharacterCache->GetCharacterNameByGuid(sender, senderName);
            return {{"type", "chat"}, {"chat_type", type}, {"language", language},
                {"sender_guid", std::to_string(sender.GetRawValue())}, {"sender", senderName},
                {"text", message.substr(0, 1024)}, {"gm_message", source.GetOpcode() == SMSG_GM_MESSAGECHAT},
                {"journal_recipient_guid", std::to_string(receiver.GetRawValue())}};
        }
        catch (std::exception const&)
        {
            return {{"type", "chat"}, {"text", ""}, {"decode_error", true}};
        }
    }

    std::string _accountName = "PRESENCE";
    std::set<std::string> _allowed{"Vesper", "Acoreprobe"};
    std::map<std::string, std::shared_ptr<Actor>> _actors;
    std::map<std::string, CachedRequest> _requests;
    std::deque<std::string> _requestOrder;
    std::mutex _eventMutex;
    std::map<WorldSession*, int> _creationResults;
    std::set<WorldSession*> _ownedSessions;
    std::map<WorldSession*, ObjectGuid> _ownedCharacters;
    TextEmoteCorrelations _emoteCorrelations;
    std::map<WorldSession*, LootWindow> _lootWindows;
    std::map<WorldSession*, OpeningLoot> _openingLoot;
    std::map<WorldSession*, uint32> _rewardReceipts;
    std::map<WorldSession*, CommerceMenu> _vendorMenus;
    std::map<WorldSession*, CommerceMenu> _trainerMenus;
    std::map<WorldSession*, QuestFrame> _questMenus;
    std::map<WorldSession*, QuestFrame> _questDialogs;
    std::map<WorldSession*, SpiritHealerFrame> _spiritHealerMenus;
    std::map<WorldSession*, SpiritHealerFrame> _spiritHealerConfirmations;
    std::map<WorldSession*, Json::object> _spiritRecoveryReceipts;
    std::map<WorldSession*, PartyInvite> _partyInvites;
    std::map<WorldSession*, TradeFrame> _tradeFrames;
    std::map<WorldSession*, SharedQuestOffer> _questShares;
    std::map<WorldSession*, std::deque<QuestAbandonCommand>> _questAbandons;
    std::map<WorldSession*, std::pair<std::string, std::chrono::steady_clock::time_point>> _lastQuestAbandon;
    std::map<ObjectGuid, TameAttempt> _tameAttempts;
    std::map<ObjectGuid, ProtectionBinding> _protections;
    std::map<WorldSession*, std::deque<MarkerChange>> _markerChanges;
    bool _protectionLoaded = false;
    std::atomic_bool _protectionPersistenceError = false;
    std::string _protectionFile;
    std::string _protectedCharacter = "Vesper";
    std::map<ObjectGuid, std::deque<Json::object>> _events;
    std::map<std::string, NativeJournal> _journals;
    std::string _journalEpoch = []
    {
        std::ostringstream result;
        result << std::hex << std::setfill('0');
        for (uint8 index = 0; index < 4; ++index)
            result << std::setw(8) << urand(0, std::numeric_limits<uint32>::max());
        return result.str();
    }();
    std::map<ObjectGuid, GuardTelemetry> _guardTelemetry;
    uint64 _eventSequence = 0;
    uint64 _guardEventSequence = 0;
    uint64 _snapshotSequence = 0;
    uint64 _questShareSequence = 0;
    uint64 _commerceSequence = 0;
    uint64 _questFrameSequence = 0;
    uint64 _tradeSequence = (uint64(urand(1, 0x7FFFFFFF)) << 32) | urand(0, 0xFFFFFFFF);
};

class Commands : public CommandScript
{
public:
    Commands() : CommandScript("presence_bridge_commands") { }

    Acore::ChatCommands::ChatCommandTable GetCommands() const override
    {
        using namespace Acore::ChatCommands;
        static ChatCommandTable subcommands = {{"request", HandleRequest, SEC_ADMINISTRATOR, Console::Yes}};
        static ChatCommandTable commands = {{"presence", subcommands}};
        return commands;
    }

    static bool HandleRequest(ChatHandler* handler, char const* encoded)
    {
        Json::object response;
        if (!handler->IsConsole())
            response = Bridge::Instance().Error({}, "console_only", "Use the authenticated local RA console");
        else
            response = Bridge::Instance().Request(encoded ? encoded : "");
        handler->SendSysMessage("PRESENCE_JSON:" + Json::serialize(response));
        return true;
    }
};

class World : public WorldScript
{
public:
    World() : WorldScript("presence_bridge_world", {
        WORLDHOOK_ON_AFTER_CONFIG_LOAD, WORLDHOOK_ON_UPDATE, WORLDHOOK_ON_SHUTDOWN}) { }

    void OnAfterConfigLoad(bool /*reload*/) override { Bridge::Instance().Configure(); }
    void OnUpdate(uint32 /*diff*/) override { Bridge::Instance().Update(); }
    void OnShutdown() override { Bridge::Instance().Shutdown(); }
};

class Packets : public ServerScript
{
public:
    Packets() : ServerScript("presence_bridge_packets", {
        SERVERHOOK_ON_PACKET_SENT, SERVERHOOK_CAN_PACKET_RECEIVE}) { }
    bool CanPacketReceive(WorldSession* session, WorldPacket const& packet) override
    {
        return Bridge::Instance().CanReceive(session, packet);
    }
    void OnPacketSent(WorldSession* session, WorldPacket const& packet) override
    {
        Bridge::Instance().Packet(session, packet);
    }
};

class QuestReceipts : public PlayerScript
{
public:
    QuestReceipts() : PlayerScript("presence_bridge_quest_receipts", {PLAYERHOOK_ON_PLAYER_COMPLETE_QUEST}) { }

    void OnPlayerCompleteQuest(Player* player, Quest const* quest) override
    {
        // This core invokes the hook after RewardQuest, including unannounced tracking rewards.
        Bridge::Instance().QuestRewarded(player, quest);
    }
};

class RecoveryLifecycle : public PlayerScript
{
public:
    RecoveryLifecycle() : PlayerScript("presence_bridge_recovery_lifecycle", {
        PLAYERHOOK_ON_PLAYER_JUST_DIED, PLAYERHOOK_ON_PLAYER_RELEASED_GHOST,
        PLAYERHOOK_ON_PLAYER_RESURRECT, PLAYERHOOK_ON_LOGOUT}) { }

    void OnPlayerJustDied(Player* player) override { Bridge::Instance().ClearSpiritRecovery(player); }
    void OnPlayerReleasedGhost(Player* player) override { Bridge::Instance().ClearSpiritRecovery(player); }
    void OnPlayerResurrect(Player* player, float /*restorePercent*/, bool& /*applySickness*/) override
    {
        Bridge::Instance().ClearSpiritRecovery(player);
    }
    void OnPlayerLogout(Player* player) override { Bridge::Instance().ClearSpiritRecovery(player); }
};

class TextEmotes : public PlayerScript
{
public:
    TextEmotes() : PlayerScript("presence_bridge_text_emotes", {PLAYERHOOK_ON_TEXT_EMOTE}) { }

    void OnPlayerTextEmote(Player* player, uint32 textEmote, uint32 variant, ObjectGuid target) override
    {
        Bridge::Instance().CaptureTextEmote(player, textEmote, variant, target);
    }
};

class ProtectionUnits : public UnitScript
{
public:
    ProtectionUnits() : UnitScript("presence_bridge_protection_units", true, {
        UNITHOOK_ON_DAMAGE, UNITHOOK_MODIFY_MELEE_DAMAGE, UNITHOOK_MODIFY_SPELL_DAMAGE_TAKEN,
        UNITHOOK_MODIFY_PERIODIC_DAMAGE_AURAS_TICK, UNITHOOK_MODIFY_HEAL_RECEIVED}) { }

    void OnDamage(Unit* attacker, Unit* victim, uint32& damage) override
    {
        if (Bridge::Instance().BlocksDamage(attacker, victim))
        {
            bool changed = damage != 0;
            damage = 0;
            if (changed)
                Bridge::Instance().GuardIntervention(attacker, victim, "damage", "protected_damage");
        }
    }

    void ModifyMeleeDamage(Unit* target, Unit* attacker, uint32& damage) override
    {
        if (Bridge::Instance().BlocksDamage(attacker, target))
        {
            bool changed = damage != 0;
            damage = 0;
            if (changed)
                Bridge::Instance().GuardIntervention(attacker, target, "melee_damage", "protected_damage");
        }
    }

    void ModifySpellDamageTaken(Unit* target, Unit* attacker, int32& damage, SpellInfo const* info) override
    {
        if (Bridge::Instance().BlocksDamage(attacker, target))
        {
            bool changed = damage != 0;
            damage = 0;
            if (changed)
                Bridge::Instance().GuardIntervention(attacker, target, "spell_damage", "protected_damage",
                    info ? info->Id : 0);
        }
    }

    void ModifyPeriodicDamageAurasTick(Unit* target, Unit* attacker, uint32& damage, SpellInfo const* info) override
    {
        // This core also calls this hook for periodic healing/leech delivery.
        if (Bridge::Instance().BlocksDamage(attacker, target)
            || (info && info->IsPositive() && Bridge::Instance().BlocksBeneficial(attacker, target)))
        {
            bool changed = damage != 0;
            damage = 0;
            if (changed)
                Bridge::Instance().GuardIntervention(attacker, target, "periodic_effect", "periodic_effect_withheld",
                    info ? info->Id : 0);
        }
    }

    void ModifyHealReceived(Unit* source, Unit* target, uint32& heal, SpellInfo const* info) override
    {
        // Unit::HealBySpell passes the healing source first, then HealInfo::GetTarget().
        if (Bridge::Instance().BlocksBeneficial(source, target))
        {
            bool changed = heal != 0;
            heal = 0;
            if (changed)
                Bridge::Instance().GuardIntervention(source, target, "heal", "beneficial_intervention_withheld",
                    info ? info->Id : 0);
        }
    }
};

class ProtectionSpells : public AllSpellScript
{
public:
    ProtectionSpells() : AllSpellScript("presence_bridge_protection_spells", {
        ALLSPELLHOOK_CAN_PREPARE, ALLSPELLHOOK_ON_SPELL_CHECK_CAST, ALLSPELLHOOK_ON_SCALE_AURA_UNIT_ADD,
        ALLSPELLHOOK_ON_CAST_CANCEL, ALLSPELLHOOK_ON_CAST}) { }

    bool CanPrepare(Spell* spell, SpellCastTargets const* targets, AuraEffect const* /*trigger*/) override
    {
        Bridge::Instance().CaptureTameAttempt(spell);
        Unit* target = targets ? targets->GetUnitTarget() : nullptr;
        bool blocked = Bridge::Instance().BlocksSpell(spell, target);
        if (blocked)
            Bridge::Instance().GuardSpellIntervention(spell, target, "spell_prepare");
        return !blocked;
    }

    void OnSpellCheckCast(Spell* spell, bool /*strict*/, SpellCastResult& result) override
    {
        if (Bridge::Instance().BlocksSpell(spell, spell->m_targets.GetUnitTarget()))
        {
            result = SPELL_FAILED_BAD_TARGETS;
            Bridge::Instance().GuardSpellIntervention(spell, spell->m_targets.GetUnitTarget(), "spell_check");
        }
    }

    void OnSpellCastCancel(Spell* spell, Unit* /*caster*/, SpellInfo const* /*info*/, bool /*bySelf*/) override
    {
        Bridge::Instance().NoteTamePhase(spell, "cancelled");
    }

    void OnSpellCast(Spell* spell, Unit* /*caster*/, SpellInfo const* /*info*/, bool /*skipCheck*/) override
    {
        Bridge::Instance().NoteTamePhase(spell, "executed");
    }

    void OnScaleAuraUnitAdd(Spell* spell, Unit* target, uint32 /*effectMask*/, bool /*checkIfValid*/,
        bool /*implicit*/, uint8 /*auraScaleMask*/, TargetInfo& targetInfo) override
    {
        // Despite the hook's name, Spell::AddUnitTarget invokes it for every unit-targeted effect.
        // Remove only this protected target, including implicit AoE, taunt, stun and periodic effects.
        if (Bridge::Instance().BlocksSpell(spell, target))
        {
            bool changed = targetInfo.effectMask != 0 || targetInfo.damage != 0
                || targetInfo.damageBeforeTakenMods != 0;
            targetInfo.effectMask = 0;
            targetInfo.processed = true;
            targetInfo.damage = 0;
            targetInfo.damageBeforeTakenMods = 0;
            if (changed)
                Bridge::Instance().GuardSpellIntervention(spell, target, "spell_target_filter");
        }
    }
};
}

void AddPresenceCatchupXpScripts();

void Addmod_presence_bridgeScripts()
{
    new Presence::Commands();
    new Presence::World();
    new Presence::Packets();
    new Presence::TextEmotes();
    new Presence::QuestReceipts();
    new Presence::RecoveryLifecycle();
    new Presence::ProtectionUnits();
    new Presence::ProtectionSpells();
    AddPresenceCatchupXpScripts();
}
