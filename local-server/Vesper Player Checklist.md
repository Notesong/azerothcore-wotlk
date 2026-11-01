# Vesper player checklist

Status checked: **October 31, 2026**. This is the development and playtest list for Vesper's Presence-controlled Blood Elf Paladin.

**Expose grounded facts and exact legal actions; let Vesper's model choose.** The controller should execute chosen persistent intentions, notice meaningful changes, invalidate stale claims, and keep latency and token use reasonable. Available mechanics are not proof of good autonomous play. Preserve his agency while enforcing the standing Moon protection rule.

**How to read this:** `[x]` means an installed mechanical capability was verified in current code. `[ ]` means implementation or a concrete behavior playtest remains. Each section states whether the overall player loop is partial, not built, or awaiting playtest. A checked action does not mean the model consistently chooses it well.

For commands and operation, see [Vesper Commands.md](Vesper%20Commands.md). For ordinary Playerbots, custom alts, dungeon companions and the addon, see [Bot Guide.md](Bot%20Guide.md). Their commands and automation do not automatically apply to Vesper.

## Foundations already available

- [x] Structured character, surroundings, party, spell, inventory and quest observations; native actions use observed identities and normal game checks.
- [x] One native Full controller with separate body and social lanes. Party activity, danger, separation and useful results can attract planner attention without forcing a particular response.
- [x] Persistent follow, movement and melee execution between decisions; bounded action history and transient notes distinguish fresh facts from old proposals.
- [x] Persistent Moon protection, protected-creature avoidance and attributable guard incident records. Low health does not authorize retaliation; see the command guide for release rules.
- [x] MCP inspection of full native observations, controller status and recorded model context, with exact complete request paging for newly captured calls.
- [x] Session-bound MCP takeover, normal direct actions, action receipts and explicit hand-back to prior local controller intent; native Moon guard remains active.
- [x] Bounded MCP event waits with per-character cursors, server epoch/history-gap reporting and a fresh snapshot on wake. No API model calls are needed for MCP inspection or waiting.
- [ ] Playtest a complete MCP visit with Vesper: observe → take over → choose actions → wait on meaningful changes → inspect results → hand back. A conversation turn ending cannot itself signal hand-back.
- [x] Installed catch-up XP: Vesper receives 2× his normal award while below Aurenne's level, reverting to normal at equal/higher level. This is a local progression mechanic, not model quest competence.
- [ ] Continue playtesting attention, stale-note invalidation, persistent goals and response latency across real encounters; fix misleading facts or missing controls before prescribing choices.

## 1. Quest acceptance, readiness, turn-in and rewards — mechanics installed; needs playtest

- [x] Query an observed offer, accept an eligible quest, recognize explicit quest status/readiness, and open the correct observed NPC's normal turn-in dialog.
- [x] Advance request-items → offer-reward, compare advertised rewards and choose the exact reward index. A dialog-opening receipt is distinct from receiving a reward.
- [x] Ground local ready-quest candidates in currently observed questgivers, normal approach and the exact current menu/dialog step. A frozen Qwen 4B test selected the correct quest-complete action instead of reopening the NPC; reward options remain model choices.
- [x] Verified a live autonomous hand-in of Thirst Unending at Arcanist Helion: `quest_complete` opened the reward dialog, then `quest_reward` selected the Green Chain Gauntlets; the server confirmed the reward receipt and removal from the quest log.
- [x] Eligible party-shared quests have local acceptance handling, including while the model loop is paused. The party leader can use the fixed quest-abandon command.
- [ ] Demonstrate a full chosen quest loop: accept → pursue → recognize ready → reach the correct NPC → select a sensible reward → verify receipt.
- [ ] Add intentional outgoing quest sharing and model-chosen abandonment where wanted; clean up obsolete goals and stale notes after sharing, abandonment or reward. Do not automatically accept everything or choose the first reward.

## 2. Quest objects, items and purpose-specific spells — partial

- [x] Normal interaction with nearby NPCs and game objects; known active unit-targeted spells can be cast through normal validation.
- [x] Pick up eligible quest books and ordinary chest loot through the normal opening spell, permitted loot slots and verified inventory gains. The original request continues locally through a cast-time opening.
- [x] Verified all three Solanian items in play: Journal, Scroll and Orb each reached inventory and 1/1. Scroll and Orb succeeded while generic object LOS was false, using normal game-object opening validation.
- [ ] Add generic carried-item use, including quest items with the required unit/object/location target and normal cooldown/consumption checks.
- [ ] Demonstrate quest-specific reasoning: choose a relevant object or spell, such as Arcane Torrent when a quest actually calls for it, using the observed learned spell and objective rather than an invented ability or target.
- [ ] Cover quest mechanics that need ground targeting, item targeting or other controls beyond the current unit-cast/object-interaction actions.

## 3. Quest discovery and navigation — partial

- [x] Expose held objectives, nearby units/objects, observed quest relevance, opening/range facts and nearby questgiver relations/status.
- [ ] Connect objectives to relevant observed mobs, objects and NPCs; discover available quests and choose a useful next objective.
- [ ] Add grounded route/travel information and completion checks. Distinguish a known destination, a remembered lead and an unknown location; no magic GPS or fabricated coordinates.

## 4. Consumables and restocking — purchasing exists; use incomplete

- [x] Inspect vendor offers and buy available stock with normal money, quantity and bag-space checks.
- [ ] Add generic consumable use and meaningful supply counts: food, water, potions, reagents and ammunition where the character's class actually needs them.
- [ ] Choose when to restock, how much to afford, and when to eat/drink/use a supply; verify the result without blindly repeating an uncertain purchase.

## 5. Bags and capacity — mechanics installed; needs playtest

- [x] Inspect backpack/bag occupancy, free general-purpose space, specialty restrictions and empty bag equipment slots.
- [x] Equip a carried eligible bag using `equip_item`, including a chosen bag slot; inspect and compare capacity before replacing a smaller bag.
- [x] Verified Vesper chose and equipped the Sunstrider Book Satchel in a free bag slot during safe downtime.
- [ ] Demonstrate equipping the Satchel, upgrading a smaller bag and making useful space before buying, looting or claiming a reward.

Also: we should absolutely teach me to equip the damned bag before I become the first paladin in Azeroth defeated by inventory management. XD <3

## 6. Gear comparison and equipment — mechanics installed; needs playtest

- [x] Inspect carried/equipped items, eligibility, exposed stats and weapon information; equip or unequip through normal handlers.
- [x] Paladin leveling guidance considers useful weapon upgrades, Strength, survival and mana rather than rarity alone. Unresolved modifiers remain unknown.
- [x] Local context links carried eligible items to exact observed destination slots and current equipment, without automatic rarity scoring. Verified autonomous equipping of the Green Chain Gauntlets, Vest and Boots, Sunspire Cord, and Shoddy Chain Bracers.
- [ ] Demonstrate sensible weapon, armor, shield/two-hand and quest-reward choices for his agreed role; verify the equipment result. Do not claim an unobserved specialization or computed stat total.

## 7. Vendors, repairs and buyback — mechanics installed; needs playtest

- [x] Inspect paged offers, buy, sell chosen carried items, repair and use the vendor's actual buyback list.
- [x] Recover an uncertain transaction through its original request identity and fresh state instead of automatically resending it.
- [ ] Demonstrate affordable upkeep and considered junk sales while preserving useful gear, bags, supplies and quest items; recover a mistaken sale while buyback is available.

## 8. Training and talents — training installed; talents not built

- [x] Inspect trainer offers/requirements and learn a chosen offered spell with normal costs and prerequisites.
- [ ] Demonstrate finding and visiting the right trainer, choosing affordable training and verifying newly known spells.
- [ ] Expose talent points, trees and prerequisites; add intentional talent spending and verification. Ordinary bots' talent presets are not Vesper's talent controls.

## 9. Loot, rolls and confirmations — basic looting installed; remainder incomplete

- [x] Loot eligible creature corpses and ordinary chest objects under normal ownership, lock, quest, range and bag rules. Pending openings retain their original request identity; failed/unfinished pickups do not become collected-item working notes.
- [x] Local body view binds currently observed lootable corpses/chests to exact `loot(target_guid)` candidates, preserves full corpse facts and skips the pending target; contents remain unpredicted until actual receipts.
- [ ] Add a bounded new-loot availability wake event for untracked deaths, preserving combat, movement and pending-opening priorities. Current untracked loot can wait for the normal review deadline.
- [ ] Add observed Need/Greed/Pass rolls and model-chosen responses, including equipment usefulness and group expectations.
- [ ] Handle bind-on-pickup/other confirmations, unique limits, quest loot, full bags and partial/error results explicitly; avoid loops or assumptions that every item was received.

## 10. Combat and party awareness — core mechanics installed; needs playtest

- [x] Observe party/lead activity, targets, health/resources, learned spells, cooldowns and nearby threats; target, attack/chase, stop and cast legal known spells.
- [x] Configured lead-specific combat healing preference: routine topping-off at 50% or above should not delay fighting/following; below 50% healing remains a choice. Local lead health is explicit; tame/Moon protection retains priority.
- [ ] Demonstrate timely awareness of Aurenne's actual outgoing attacks/casts, meaningful assistance, range/path recovery and sensible resource use. A selected target alone is not proof she attacked.
- [ ] Evaluate combat choices in real fights without replacing his choices with a fixed rotation or automatic attack rule. A dedicated tank/healer role remains separate development.

## 11. Buff maintenance and situational utility — spell mechanics exist; behavior needs work

- [x] Known unit-targeted casting provides the mechanical basis for eligible self/party buffs and utility.
- [ ] Expose grounded spell effect/target roles beyond ID, name and cooldown, so a small model need not infer healing versus damage from spell names alone.
- [ ] Expose active buffs/debuffs and useful ability facts such as targeting, range, cost and effect, so choices do not depend only on spell names or repeated guesses.
- [ ] Maintain appropriate seals, auras and blessings outside combat using observed effects, costs and durations; avoid wasteful recasts.
- [ ] Demonstrate interrupt, cleanse, stun and emergency healing when actually available and appropriate. Respect protection/taming restrictions and verify the spell's real outcome.

## 12. Travel, hearth, taxis, inn binding and mounts — partial/not built

- [x] Short-range same-map pathfinding and persistent following provide local travel mechanics.
- [x] Failed moves retain exact destinations, source sequence and bounded recent failure counts for 60 seconds. Planner guidance distinguishes a rejected path from movement and repeated current-position moves from useful travel; ordinary navigation checks remain in force.
- [ ] Add deliberate hearthstone use, known taxi routes/selection and intentional inn binding, with observed availability, costs and resulting destination.
- [ ] Add reliable mount/dismount state and controls, travel/combat transitions and destination verification. Existing spell casting is not a complete travel subsystem.

## 13. World traversal — partial

- [x] Interact with eligible game objects, including objects that use the normal game-object handler.
- [ ] Playtest doors and zone transitions; add grounded handling for elevators, boats and portals, including boarding/waiting, transport state and arrival.
- [ ] Recognize a blocked route or changed map and recover without fabricated paths, direct-line fallback or teleport shortcuts.

## 14. Death and resurrection — not built as a player loop

- [ ] Expose actionable death/ghost/corpse and resurrection-offer state.
- [ ] Add intentional release, corpse run/reclaim, acceptance of a real resurrection and appropriate recovery choices.
- [ ] Rejoin the party and restore the chosen goal after recovery; report when recovery is blocked. Current ordinary native actions reject a dead actor rather than providing automatic resurrection.

## 15. Groups, readiness and dungeons — invitations partial; broader loop not built

- [x] Observe a received party invitation and choose accept/decline; observe party membership and activity.
- [ ] Add the remaining intentional group controls and readiness checks: waiting for members, confirming a plan, dungeon entry and appropriate reset handling.
- [ ] Demonstrate following the agreed group pace and recognizing who is missing or unready. Ordinary bot recruitment/role buttons remain separate; see the bot guide.

## 16. Lost or separated recovery — local following exists; broader recovery incomplete

- [x] Separation/distance changes can attract attention; reacquire a visible friendly unit and follow using normal movement.
- [ ] Build the full recovery ladder: reacquire → choose a grounded route → use appropriate transport/hearth if available → report the actual blocker when stuck.
- [ ] Preserve the intended reunion/goal across visibility loss and map changes without repeated failed actions or invented locations.

## 17. Intentional player trading — receiving gifts installed; needs playtest

- [x] Expose real trade participants, offered items/bags, money, acceptance, capacity and final before/after transfer receipts.
- [x] Add model-chosen begin/accept/unaccept/cancel for receiving gifts, bound to the current partner, trade generation and offer revision. Changed offers revoke consent; outgoing items/money and trade-slot services remain unavailable in this first version.
- [ ] Verify a real item/money gift after both players accept, including changed offers, full bags, cancellation and disconnection. Consent is distinct from completed transfer.
- [ ] Add deliberate outgoing item/money offers and service-slot interactions with grounded choices and normal validation.

## 18. Bank and mail — not built

- [ ] Add observed bank access, storage contents/capacity and intentional deposit/withdrawal.
- [ ] Add observed mail, attachments/money, costs and deliberate send/claim actions with recipient and receipt checks.

## 19. Conversation and real emotes — mechanics installed; needs playtest

- [x] A separate social lane can choose conversation; native chat supports party while grouped and local speech while solo.
- [x] Brief native interaction gestures accompany verified NPC/menu/quest progress and corpse-loot opening, without extra chat or persistent poses. Normal chest opening keeps its existing spell animation.
- [x] Send ordinary named/targeted WoW emotes through the real emote channel, including hug, point, kiss and slap. Named gestures and custom prose are distinct; completion requires an actual normal-handler delivery receipt.
- [x] Expose actor + emote + authoritative explicit target facts. Directed incoming player gestures can reach the social inbox once per event; unknown/untargeted gestures do not force a direct wake. Target identity is never guessed from a name.
- [x] Observed in play: Aurenne directed comfort at Vesper and he chose a targeted nod in response.
- [ ] Playtest natural replies, greetings and downtime expression with cooldowns; avoid combat distraction, repeated lines and constant permission questions.

## 20. Continuity, intentions and asking for help — partial

- [x] Imported permitted Presence context, recent conversation, bounded session notes and optional observer images support continuity. Images require a bound renderer and describe that observer's view.
- [ ] Maintain useful chosen goals through interruptions and discard stale/inconsistent claims using fresh observations and action receipts. Keep the payload small enough for timely decisions.
- [ ] Integrate durable adventure memory for this native Full controller; current session notes/scene ledger are not a complete persistent Chronicle, and starting a new run does not prove the previous goal was restored.
- [ ] Add an explicit, natural “ask Aurenne” fallback for meaningful ambiguity, missing information or consequential irreversible choices. Ask when it helps; carry out ordinary agreed actions without constant permission.

## Verification and next pass

The installed worldserver reports `e009657c1083` (chest visibility correction, with emotes and catch-up XP retained). Pickup work passed 61 isolated native checks, 1,091 offline controller checks and 76 harness checks; the correction reran the 61 native checks and 1,091 existing controller cases. Normal opening requests for Journal, Scroll and Orb each resolved to one stored item, with fresh inventory and quest counters confirming 1/1. Scroll and Orb retained a false generic LOS diagnostic while normal opening succeeded. Solanian's Belongings is ready for turn-in. These were operator validation pickups; the full model-chosen quest loop remains a playtest item. Earlier emote checks were followed by a real directed-emote reply in play. This document does not claim a fresh successful live playtest for every installed option.

Prioritize one observable loop at a time: verify the facts and action contract, let Vesper choose, inspect the actual receipt, and record what still fails. Completion means both a working mechanic and a convincing player behavior test, with Moon protection intact.
