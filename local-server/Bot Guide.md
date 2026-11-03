# Playerbot companion guide

For this AzerothCore installation. Verified against the installed source and settings on October 30, 2026.

These commands control ordinary Playerbots: your offline alts and recruited companions.
They do not use model tokens. Vesper uses Presence instead; his commands are in
[Vesper Commands.md](Vesper%20Commands.md).

## The easiest way: the addon

Type `/bot` to open the updated MaNGOSBot window. `/mangosbot` also works.

1. Click **Refresh**, then select a bot. Your offline account alts appear in the roster too.
2. Use **Login** for an offline alt, or **Recruit** to get a companion by class.
3. If needed, use **Tank**, **Healer**, or **Damage**. Wait for the server's confirmation.
4. **Match gear** generates upgrades for the selected role within the current gear limits.
5. Use the movement buttons for that companion. **Party follow/stay/flee** sends orders only
   to roster-confirmed ordinary bots in your group, excluding Vesper.

**Inspect** asks for character details, talents and current combat strategies.
**Available specs** lists the server's talent presets. The addon does not automatically
change roles, generate gear or recruit companions when you open it.

More addon details: [addons/Mangosbot/README.md](addons/Mangosbot/README.md).

## How to type commands

There are two command forms:

| Form | Example | Purpose |
| --- | --- | --- |
| Server command, beginning with a dot | `.playerbots bot list` | Roster, login, logout and recruitment. |
| A normal whisper to the bot | `/w BotName follow` | Movement, talents, equipment and other bot actions. |

Replace `BotName`, `AltName` and `ActualBotName` with the character's actual name.
Do not add quotes. Send one command at a time and allow the bot to reply.

Use individual whispers when Vesper is with you. Native bots also accept party commands,
but `/p follow` can reach several bots and appear as conversation to Vesper.
Typing `/follow BotName` makes **your character** follow that bot.

These ordinary player commands do not require GM mode. Inviting or controlling a bot
can still fail if it belongs to the other faction, already has a controller, or is unavailable.

## Make your own persistent companions

Use your own alts when you want a particular named companion with ongoing progression.

1. Create a **Horde** character on your normal player account.
2. Log that character out, then log Aurenne in.
3. Add the offline character:

```text
.playerbots bot add AltName
```

It normally joins your party when it finishes loading. If it is online already,
`add` cannot create a second session. Keep Vesper on his separate Presence account;
do not use these login controls for him.

| Command | Result |
| --- | --- |
| `.playerbots bot list` | Lists available account alts and controlled/grouped bots. |
| `.playerbots bot add AltName` | Logs an eligible offline alt in as a bot. |
| `.playerbots bot remove AltName` | Saves and logs your controlled bot out. |
| `/w AltName leave` | Makes the online bot leave the group; does not log it out. |
| `/uninvite AltName` | Normal party removal, also useful for an offline party entry. |

Your alts are not automatically logged in when you log Aurenne in. Add them when wanted.
Logging a bot out can leave its offline name in the party; `/uninvite AltName` frees that slot.

## Recruit a companion by class

```text
.playerbots bot addclass priest
```

This selects an available Horde character from the existing class pool. It does not
create a new custom character. Read its name from the party/roster before issuing whispers.

Accepted class names:

```text
warrior  paladin  hunter  rogue  priest  shaman  mage  warlock  druid  dk
```

Death knights have a starting-level restriction; they are not level-2 companions.
You can also send `/invite BotName` to an available online Horde bot.

**Does recruitment match my level?** If a pooled bot differs from you by more than
three levels, login normally rebuilds it at your level with generated gear. Within
three levels, it can keep its previous level and gear. For an exact level match,
after it joins and while out of combat:

```text
.playerbots bot init=auto ActualBotName
```

This is a **full setup/rebuild**, including talents and equipment, with a gear budget
based on your equipment. Use it before choosing the role. It is restricted to pooled
`addclass` bots; it is not a progression command for your own custom alts or Vesper.
Use the specific name rather than `*`, which targets grouped characters broadly.

## Build a dungeon party

A normal dungeon group has **five character slots**. Aurenne and Vesper occupy two,
so you can add three ordinary companions. Your hunter pet does not use a party slot.
Adding beyond five through the bot manager can convert the group to a raid.

A practical starting arrangement is Aurenne + Vesper + tank + healer + damage bot.
For now, count Vesper as damage/support; his dedicated tank or healer behavior has
not been established. During early leveling, your pet may cover the tanking you need.

Class alone does not guarantee a role. A priest may have a damage spec, and a warrior
may lack a shield or tank setup. The addon role buttons are the easiest way to apply
a matching talent preset and combat strategies, then inspect what the server reports.
Below level 10, talent points and role abilities are limited.

### Inspect talents and strategies

```text
/w BotName who
/w BotName talents
/w BotName talents spec list
/w BotName co ?
```

`talents spec list` is the current list for that class. Preset names must match it exactly.
`co ?` reports combat strategies; `nc ?` reports noncombat strategies.
This version uses **`co`**, not the older MaNGOS `cc` command.

The addon currently uses these configured PvE presets:

| Class | Tank | Healer | Damage |
| --- | --- | --- | --- |
| Warrior | `prot pve` | — | `arms pve` |
| Paladin | `prot pve` | `holy pve` | `ret pve` |
| Priest | — | `holy pve` | `shadow pve` |
| Druid | `bear pve` | `resto pve` | `balance pve` |
| Shaman | — | `resto pve` | `ele pve` |
| Death knight | `blood pve` | — | `frost pve` |
| Hunter | — | — | `bm pve` |
| Rogue | — | — | `combat pve` |
| Mage | — | — | `frost pve` |
| Warlock | — | — | `affli pve` |

These are the addon's choices, not the complete list of available builds.

### Manual warrior tank setup

For a newly recruited warrior, initialize first if needed. Then, replacing the name:

```text
/w BotName talents spec prot pve
/w BotName co -arms,-fury,+prot,-dps assist,+tank assist
/w BotName autogear match
/w BotName talents
/w BotName co ?
```

Wait for the talent-selection reply before the strategy and gear commands. Check that
the tank has usable equipment, including an appropriate one-handed weapon and shield.

### Manual priest healer setup

```text
/w BotName talents spec holy pve
/w BotName co -disc,-holy dps,-shadow,+holy heal,-tank assist,+dps assist
/w BotName autogear match
/w BotName co ?
```

For priests, `holy heal` is a healing strategy; `holy dps` is a damage strategy.
The generic `dps assist` flag here does not turn off the priest's healing role.

## Movement and combat reference

| Whisper | What it asks the ordinary bot to do |
| --- | --- |
| `/w BotName follow` | Follow you; clears the stay/passive shortcut state. |
| `/w BotName stay` | Stay at its position. |
| `/w BotName flee` | Follow you passively rather than continuing the fight. Use `follow` to resume normal following. |
| `/w BotName summon` | Teleport to you, subject to location/session restrictions. |
| `/w BotName attack` | Attack your selected target, subject to normal action checks. |
| `/w BotName do attack my target` | Explicitly request the same attack action. |
| `/w BotName pull` | Request a pull on your selected target. |
| `/w BotName attackers` | Report attackers. |
| `/w BotName target` | Report its target. |
| `/w BotName rebuff` | Request rebuffing. |
| `/w BotName leave` | Leave the party. |

**Moon protection belongs to Vesper's bridge. Ordinary Playerbots do not inherit his
persistent protected-creature rule.** Keep other companions out of a rare tame attempt;
a Moon marker does not give them Vesper's guarantee of restraint.

## Equipment, bags and upkeep

| Whisper | What it does |
| --- | --- |
| `/w BotName stats` | Report money, free bag space, repair/durability information and XP progress. |
| `/w BotName inv` | Query inventory items. |
| `/w BotName autogear match` | Generate current-spec upgrades scaled to your average worn item level. |
| `/w BotName repair` | Seek a repair NPC and repair using the bot's money. |
| `/w BotName maintenance` | Run the server's broad provisioning/maintenance routine. See below. |

**Gear matching is optional generated setup.** The current autogear quality cap is
blue, and existing items may remain if replacements are not considered upgrades.
Pick the spec first, match gear afterward, and inspect the result. It does not simply
prefer purple over blue over green regardless of useful stats.

Avoid the `autogear reset` variant on equipment you care about: it destroys equipped
gear before generating replacements. Avoid repeating `init=auto` after choosing
talents or collecting gear you want to keep.

**Maintenance is much broader than repair.** Current settings can provision supplies
and bags, learn skills/spells, change talents and pet setup, add enchants and more,
and repair for free. It is a convenience/setup command that can affect progression.
Use `repair` for an ordinary paid repair visit.

### Loot and trading

| Whisper | What it does |
| --- | --- |
| `/w BotName ll ?` | Show the current loot policy and always-loot list. |
| `/w BotName ll normal` | Use the normal useful-item loot policy. |
| `/w BotName ll gray` | Include gray items as well as items considered useful. |
| `/w BotName ll all` | Allow all items; bags can fill quickly. |
| `/w BotName nc +loot` | Enable the noncombat looting strategy. |
| `/w BotName nc -loot` | Disable that looting strategy. |
| `/w BotName add all loot` | Scan nearby loot and attempt looting it. |
| `/w BotName t` | Open a normal trade with you when no trade is open. |
| `/w BotName t ITEM_LINK` | Once trading, place the specified carried item in the trade window. |

Replace `ITEM_LINK` by shift-clicking the item into chat. Trade items to the bot
through the ordinary trade window. Loot policy and the looting strategy are separate
settings; changing one does not necessarily enable the other. There is no `ll none`
policy in this version. Loot ownership, group loot rules and bag capacity still apply.

## Quests

Share your quests with ordinary companions through your quest log's **Share Quest**
button. Eligibility, prerequisites and quest-log space still matter.

| Whisper | What it does |
| --- | --- |
| `/w BotName quests all` | List its quests. |
| `/w BotName quests completed` | List completed objectives awaiting turn-in. |
| `/w BotName quests incompleted` | List unfinished quests; `incompleted` is the installed spelling. |
| `/w BotName q QUEST_LINK` | Report progress on that quest. |
| `/w BotName share QUEST_LINK` | Ask the bot to share its quest with the party. |
| `/w BotName drop QUEST_LINK` | Abandon that active quest on the ordinary bot. |

Replace `QUEST_LINK` with the clickable quest link, inserted by shift-clicking the
quest. Prefer the link to a typed title, so the intended quest is unambiguous.
Use `drop` only for an active quest shown in that bot's own `quests all` list;
this native command can also change completion records if given a turned-in quest.
For Vesper, the separate fixed command is `/p Vesper drop quest QUEST_LINK`.

## Death and recovery

To ask a living priest companion to resurrect Vesper, whisper the caster:

```text
/w Edgalin cast Resurrection on Vesper
```

Replace `Edgalin` with your priest's name. Alternatively, select Vesper and whisper
`/w Edgalin cast Resurrection`. A real spell link can replace the spell name;
literal `[target]` is not a required keyword. The priest must know the spell and
meet its normal casting requirements. Vesper then chooses whether to accept the
real offer. This was verified during ordinary play on November 3.

The commands below instead control the named bot's own recovery:

| Whisper | What it does |
| --- | --- |
| `/w BotName release` | Release the spirit if dead. If alive, this command can set stay instead. |
| `/w BotName revive` | Request spirit-healer recovery; it is not an instant resurrection anywhere. |
| `/w BotName summon` | Bring it to you, repair it, and conditionally revive it. |

Summoning can revive a dead bot when you are alive and out of combat, under the current settings.
Recovery still has location/state restrictions. If a recovered companion remains
behind, try `follow`. If it is actually offline, use the roster/login controls instead.

## Help and troubleshooting

```text
.playerbots bot help
/w BotName help
/w BotName who
/w BotName co ?
/w BotName nc ?
/w BotName talents spec list
```

- **No reply:** Check the name, online state, faction and who controls it. Refresh `/bot`.
- **Still standing after fleeing:** Send `follow` to restore normal following.
- **Wrong role:** Inspect talents and `co ?`; apply the role, wait for confirmation, then inspect gear.
- **Wrong level after recruitment:** Use named `init=auto` on that pooled bot before selecting its role.
- **Party full after logout:** `/uninvite BotName` removes the remaining offline entry.
- **Cannot recruit another bot for a dungeon:** Count characters; keep the party at five or fewer.
- **Vesper ignores a native command:** Use Presence and [Vesper Commands.md](Vesper%20Commands.md).

## Installed settings and verification

The current server targets 1,000 wandering bots, with bot battleground participation
disabled. The companion manager permits up to 40 added bots; that is a server limit,
not a five-player dungeon party size. Custom-alt autologin is off.

This reference was checked against `mod-playerbots` revision
`05a1f6fceb8a32aa879b13f5f48934c6e46a774c` and
`server/configs/modules/playerbots.conf`. Commands can change after an upstream update.
The implementation is by the mod-playerbots contributors; this guide describes the
local installation rather than the command set of another MaNGOS/SPP version.

Main verification sources in `source/modules/mod-playerbots/src/`:

- `Bot/PlayerbotMgr.cpp`: roster, add/remove/addclass and initialization.
- `Ai/Base/Strategy/ChatCommandHandlerStrategy.cpp`: chat command routing.
- `Ai/Base/Actions/ChangeTalentsAction.cpp`: talent presets.
- `Ai/Base/Actions/TrainerAction.cpp`: maintenance and autogear.
- `Ai/Base/Actions/LootStrategyAction.cpp`: loot policies and always-loot items.
- `Ai/Base/Actions/DropQuestAction.cpp`: ordinary-bot quest abandonment.
- `Ai/Base/Actions/ChatShortcutActions.cpp`: follow/stay/flee.
- `Ai/Base/Actions/UseMeetingStoneAction.cpp`: summon behavior.
- `Ai/Base/Actions/ReviveFromCorpseAction.cpp`: spirit-healer recovery.
