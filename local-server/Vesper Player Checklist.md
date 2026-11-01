# Vesper player checklist

Status checked: **November 1, 2026**. This is the development and playtest list for Vesper's
Presence-controlled Blood Elf Paladin.

**Expose grounded facts and exact legal actions; let Vesper's model choose.** The controller should execute chosen persistent intentions, notice meaningful changes, invalidate stale claims, and keep latency and token use reasonable. Available mechanics are not proof of good autonomous play. Preserve his agency while enforcing the standing Moon protection rule.

**How to read this:** `[x]` means an installed mechanical capability was verified in current code. `[ ]` means implementation or a concrete behavior playtest remains. Each section states whether the overall player loop is partial, not built, or awaiting playtest. A checked action does not mean the model consistently chooses it well.

For commands and operation, see [Vesper Commands.md](Vesper%20Commands.md). For ordinary Playerbots, custom alts, dungeon companions and the addon, see [Bot Guide.md](Bot%20Guide.md). Their commands and automation do not automatically apply to Vesper.

## Foundations already available

- [x] Structured character, surroundings, party, spell, inventory and quest observations; native actions use observed identities and normal game checks.
- [x] One native Full controller with separate body and social lanes. Party activity, danger, separation and useful results can attract planner attention without forcing a particular response.
- [x] Persistent follow, movement and melee execution between decisions; bounded action history and transient notes distinguish fresh facts from old proposals.
- [x] Expose the latest accepted controller movement intention with exact action, request ID and source sequence.
  `server_motion_verified: false` distinguishes accepted intention from proven ongoing server movement.
- [x] Omit unverified prior-proposal notes only from local body prompts; retain archives, social context and full MCP access.
- [x] Persistent Moon protection, protected-creature avoidance and attributable guard incident records. Low health does not authorize retaliation; see the command guide for release rules.
- [x] MCP inspection of full native observations, controller status and recorded model context, with exact complete request paging for newly captured calls.
- [x] MCP takeover, normal direct actions, action receipts and explicit hand-back to prior local controller intent; native Moon guard remains active.
- [x] Install and verify the remote lease correction: the exact secret token authorizes mutations and
  token-bearing status proves `owned_by_control_token`. SDK session churn does not own or revoke the lease;
  old generations stay fenced. Remote hand-back is explicit, with no automatic expiry. Local stdio remains
  session-bound with disconnect cleanup; local operator recovery can require the exact observed generation.
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
- [x] Ground carried quest starters in the exact owned item GUID, template StartQuest and normal eligibility.
  Use normal query/accept handlers, with fresh enabled details required for explicit acceptance; auto-accept behavior remains.
- [x] Verified Tainted Arcane Sliver (item 20483) query accepted quest 8338 at 07:05:42 UTC on November 1.
  The quest was complete in his log; the required sliver remained until Arcanist Helion's normal turn-in.
  The starter item is not the endgiver, and acceptance is not a reward receipt.
- [x] Focus safe current quest work on the actual bound menu/dialog phase without removing actions or choosing
  an item reward: menu → complete, request-items → request-reward, offer-reward → a chosen reward option.
  Explicit empty visible choice lists permit index 0; hidden, missing or truncated lists remain unknown.
- [x] At 07:39:51 UTC, Qwen chose quest 8338 reward index 0 at Helion. The normal receipt confirmed complete →
  rewarded, removal from the log, sliver count 1 → 0 and money 753 → 903 copper (+150).
  This verifies the item starter through NPC hand-in; this quest had no selectable item reward.
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
- [x] Local context links carried eligible items to exact observed destination slots and current equipment, without automatic rarity scoring. Verified autonomous equipping of the Green Chain Gauntlets, Vest and Boots, and Shoddy Chain Bracers.
- [x] Show signed base-template armor/stat deltas for known occupied-slot comparisons; eligibility is distinct
  from upgrade advice. Unknown or incomplete facts remain unknown; enchantment/random-property bonuses are excluded.
  No scoring, automatic equipping or action restriction is added.
- [x] November 1: Qwen autonomously equipped Shoddy Chain Pants (37 armor, +35 base armor), then Shoddy Chain Belt
  (24 armor, +5 base armor), with completed normal equipment receipts. Green Chain Boots remained equipped at 46 armor.
- [ ] Verify stable equipment choices without repeated boot downgrades or mechanics testing. One frozen Qwen 4B replay
  with negative armor deltas chose to wait; that single result does not establish that the live loop is fixed.
  Continue checking useful future upgrades against actual equipment receipts.
- [ ] Demonstrate sensible weapon, armor, shield/two-hand and quest-reward choices for his agreed role; verify the equipment result. Do not claim an unobserved specialization or computed stat total.

## 7. Vendors, repairs and buyback — mechanics installed; needs playtest

- [x] Inspect paged offers, buy, sell chosen carried items, repair and use the vendor's actual buyback list.
- [x] Recover an uncertain transaction through its original request identity and fresh state instead of automatically resending it.
- [x] Ground service approach/list actions and conservative miscellaneous-junk sale choices in current NPC/item facts.
  Preserve held quest requirements even when collected, plus gear, bags, supplies and uncertain items.
- [x] Verified four autonomous junk-stack sales through normal receipts, totaling 52 copper; money rose 905 → 957.
- [ ] Continue verifying affordable upkeep and preservation across other inventory; recover a mistaken sale while
  buyback is available. A successful sale is not proof of good judgment for every item.

## 8. Training and talents — training installed; talents not built

- [x] Inspect trainer offers/requirements and learn a chosen offered spell with normal costs and prerequisites.
- [x] Ground currently available, affordable trainer rows in exact `train_spell` actions. State 0 means available,
  1 unavailable and 2 known; opening the list does not purchase anything.
- [x] Verified autonomous training at Jesthenis Sunstriker: Devotion Aura (465, 9 copper), Judgement of Light
  (learned 20271 from offer 10321, 95 copper), and Blessing of Might (19740, 95 copper). Three normal completion
  receipts confirmed new known spells and 199 copper spent; money fell 957 → 758 copper (7 silver 58 copper).
- [x] Install nearby NPC titles and default-trainer type/requirement/class metadata in the native observation,
  retained in bounded body/social views and full MCP context. `class_matches_self` is advisory; default-provider
  metadata is distinct from current offers and does not force actions. No online-player list is required.
- [x] Verified the clean restart preserved 758 copper and known spells 465, 19740 and 20271.
- [ ] Verify reliable trainer discovery without repeated wrong-class attempts, and useful future lesson/budget choices.
- [ ] Observe the new native trainer class/title fields during the next real trainer encounter. No trainer NPC
  was in the post-restart observation; deployment alone is not a packet-level encounter verification.
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
- [ ] Ground direct-heal targets and urgent self-care in explicit spell roles and recipient health. The November 1
  bonfire incident included Holy Light aimed at a hostile, then full-health Aurenne while Vesper was critically hurt.

## 11. Buff maintenance and situational utility — support facts installed; self/party application observed

- [x] Known unit-targeted casting provides the mechanical basis for eligible self/party buffs and utility.
- [x] Expose bounded non-passive applied auras with caster, duration, rank family, stacks, positive state and effect mask.
  Coverage makes omitted/unknown observations explicit; an application with effect mask 0 is not an effective buff.
- [x] Known positive non-healing aura spells expose target/effect, power-cost, range, reagent and rank facts.
  Ground support candidates in observed recipients and distinguish present, suppressed, alternative-active, missing
  and unknown effects. Same-caster aura/seal alternatives do not become a default recast loop.
- [x] Useful support-state changes can attract out-of-combat attention; ordinary duration ticks do not repeatedly
  wake the planner. Loot/trade continuation and immediate combat/party needs retain priority.
- [x] Exclude temporary spells shorter than 60 seconds and Honorless Target effects (`aura_type: 159`) from
  routine upkeep candidates. Generic cast choices remain available for deliberate situational use.
- [x] Around 06:30 UTC, Qwen autonomously cast Devotion Aura (465), Blessing of Might (19740) and Seal of Righteousness
  (21084) on Vesper. Fresh aura rows had nonzero effect masks; subsequent body output waited with upkeep complete.
- [x] Verify Aurenne's own fresh aura rows: Devotion Aura (465, effect mask 1) and Blessing of Might
  (19740, effect mask 3), both from Vesper (caster GUID 102). A self blessing alone was not used as proof.
- [ ] Demonstrate continued useful upkeep, expiry recovery and party rejoining without unnecessary recasts
  or combat distraction. Repeated casts were still observed; successful party application does not solve that behavior.
- [x] Extend the native beneficial guard to positive persistent area-aura sources under Moon, uncertain protection
  or active/recent taming. Cancel only owned sources through normal aura removal; other casters' sources remain.
  Full cast choices and violation auditing remain available.
- [ ] Live-test the new Moon/tame area-source cancellation and foreign-caster preservation cases.
- [ ] Broaden grounded role facts for direct healing, damage and utility abilities beyond the current support subset.
- [ ] Demonstrate interrupt, cleanse, stun and emergency healing when actually available and appropriate. Respect protection/taming restrictions and verify the spell's real outcome.

## 12. Travel, hearth, taxis, inn binding and mounts — partial/not built

- [x] Short-range same-map pathfinding and persistent following provide local travel mechanics.
- [x] Distinguish accepted movement intention from selected-target inspection and unverified historical proposals.
  An accepted follow supersedes a prior NPC trip; any new detour remains a deliberate model choice based on fresh facts.
- [x] Ground a normal follow attempt in the exact current visible, friendly, alive configured lead and saved spacing.
  Keep the model field `follow_distance`, independent of an old selected NPC or a different bot party leader.
- [x] Keep latest recorded lead speech salient with its actual authorship/source facts; server sender GUIDs require
  matching event evidence. No follow keyword automatically executes movement or substitutes for the model's choice.
- [x] Track request-bound fresh movement progress and suppress wake loops from repeated verified already-there
  results. Meaningful chat/danger/state changes still wake; uncertain or genuinely progressing moves are distinct.
- [x] Aurenne confirmed the live walk-away test: he was following and staying with her. Fresh 07:41:28 UTC context
  confirmed persistent follow of GUID 103 at one yard while she moved; local waiting preserved movement.
- [ ] Verify long-term follow/old-NPC oscillation and recovery across interruptions. The identical frozen case
  also changed from trainer movement to follow, but one live success does not establish general reliability.
- [x] Failed moves retain exact destinations, source sequence and bounded recent failure counts for 60 seconds. Planner guidance distinguishes a rejected path from movement and repeated current-position moves from useful travel; ordinary navigation checks remain in force.
- [ ] Add deliberate hearthstone use, known taxi routes/selection and intentional inn binding, with observed availability, costs and resulting destination.
- [ ] Add reliable mount/dismount state and controls, travel/combat transitions and destination verification. Existing spell casting is not a complete travel subsystem.

## 13. World traversal — partial

- [x] Interact with eligible game objects, including objects that use the normal game-object handler.
- [ ] Playtest doors and zone transitions; add grounded handling for elevators, boats and portals, including boarding/waiting, transport state and arrival.
- [ ] Recognize a blocked route or changed map and recover without fabricated paths, direct-line fallback or teleport shortcuts.
- [ ] Ground a claimed travel goal in its actual destination and current quest state. On November 1, the planner
  copied Bonfire coordinates while claiming to travel to Falconwing Square for a quest whose required item was 0/1.
- [ ] Expose environmental hazard effects and scripted-behavior uncertainty. Bonfire 183444 uses `go_heat`, which
  is absent from current object facts; sampled health loss does not identify fire versus individual attackers.

## 14. Death and resurrection — ghost navigation verified; broader recovery incomplete

- [x] Install the native fix exposing `self.is_ghost` and numeric `self.death_state`, with ordinary
  `move_to` and `stop` for an already released ghost. Keep normal pathfinding, map/range/immobility checks
  and Moon protection. Cancel pending motion on living/ghost transitions or unreleased death before arrival.
- [x] Verify actual ghost navigation through a fresh accepted action, observed position change and original result.
  Generation 25 moved about 3.047 yards on map 530 while `is_ghost: true` and `alive: false`; the original
  receipt completed with `arrived: true`. Following, combat, casting and looting stay blocked dead.
- [ ] Expose actionable corpse/reclaim and resurrection-offer state.
- [ ] Add intentional release, corpse reclaim, acceptance of a real resurrection and appropriate recovery choices.
- [ ] Rejoin the party and restore the chosen goal after recovery; report when recovery is blocked. No automatic
  resurrection or GM shortcut is provided; ghost navigation alone does not complete the recovery loop.

## 15. Groups, readiness and dungeons — invitations partial; broader loop not built

- [x] Observe a received party invitation and choose accept/decline; observe party membership and activity.
- [ ] Add the remaining intentional group controls and readiness checks: waiting for members, confirming a plan, dungeon entry and appropriate reset handling.
- [ ] Demonstrate following the agreed group pace and recognizing who is missing or unready. Ordinary bot recruitment/role buttons remain separate; see the bot guide.

## 16. Lost or separated recovery — local following exists; broader recovery incomplete

- [x] Separation/distance changes can attract attention; reacquire a visible friendly unit and follow using normal movement.
- [ ] Build the full recovery ladder: reacquire → choose a grounded route → use appropriate transport/hearth if available → report the actual blocker when stuck.
- [ ] Preserve the intended reunion/goal across visibility loss and map changes without repeated failed actions or invented locations.

## 17. Intentional player trading — basic gift receipt verified; edge cases need playtest

- [x] Expose real trade participants, offered items/bags, money, acceptance, capacity and final before/after transfer receipts.
- [x] Add model-chosen begin/accept/unaccept/cancel for receiving gifts, bound to the current partner, trade generation and offer revision. Changed offers revoke consent; outgoing items/money and trade-slot services remain unavailable in this first version.
- [x] Distinguish opening the trade window from accepting its offer. An open empty trade or an accepted offer awaiting
  the partner can wait locally for up to 60 seconds; meaningful interrupts still wake the body planner.
- [x] Verified one real gift of three items plus 600 copper after both players accepted, using the completed-transfer
  receipt and before/after inventory and money facts. Consent alone is distinct from completed transfer.
- [ ] Playtest changed offers, full bags, cancellation and disconnection; verify that stale consent cannot complete
  a changed offer. Receipt of the gifted gear does not prove autonomous equipment selection.
- [ ] Add deliberate outgoing item/money offers and service-slot interactions with grounded choices and normal validation.

## 18. Bank and mail — not built

- [ ] Add observed bank access, storage contents/capacity and intentional deposit/withdrawal.
- [ ] Add observed mail, attachments/money, costs and deliberate send/claim actions with recipient and receipt checks.

## 19. Conversation and real emotes — mechanics installed; needs playtest

- [x] A separate social lane can choose conversation; native chat supports party while grouped and local speech while solo.
- [x] Route autonomous speech/emotes through the social lane and mechanical choices through the body lane; body
  output cannot echo the human's chat as Vesper's own line. Direct MCP speech/emote controls remain available.
- [x] Brief native interaction gestures accompany verified NPC/menu/quest progress and corpse-loot opening, without extra chat or persistent poses. Normal chest opening keeps its existing spell animation.
- [x] Send ordinary named/targeted WoW emotes through the real emote channel, including hug, point, kiss and slap. Named gestures and custom prose are distinct; completion requires an actual normal-handler delivery receipt.
- [x] Expose actor + emote + authoritative explicit target facts. Directed incoming player gestures can reach the social inbox once per event; unknown/untargeted gestures do not force a direct wake. Target identity is never guessed from a name.
- [x] Observed in play: Aurenne directed comfort at Vesper and he chose a targeted nod in response.
- [x] Clear the Presence-owned character's stored dance loop on mechanical intent or active movement/combat/casting,
  without changing posture, movement, spells or protection policy. Other bots are unaffected.
- [x] Normal-action QA verified dance state 10 → native `stop` → state 0 after deployment.
- [ ] Verify follow after dancing with Aurenne online; she was offline immediately after this restart.
- [ ] Playtest natural replies, greetings and downtime expression with cooldowns; avoid combat distraction, repeated lines and constant permission questions.

## 20. Continuity, intentions and asking for help — partial

- [x] Imported permitted Presence context, recent conversation, bounded session notes and optional observer images support continuity. Images require a bound renderer and describe that observer's view.
- [x] Focus safe local carried-item quest decisions before routine buff/service guidance while retaining complete
  dynamic observations and the allowed action schema. Matching fresh item details can advance; danger, travel,
  protected activity and other active dialogs keep the full guide.
- [ ] Maintain useful chosen goals through interruptions and discard stale/inconsistent claims using fresh observations and action receipts. Keep the payload small enough for timely decisions.
- [ ] Integrate durable adventure memory for this native Full controller; current session notes/scene ledger are not a complete persistent Chronicle, and starting a new run does not prove the previous goal was restored.
- [ ] Add an explicit, natural “ask Aurenne” fallback for meaningful ambiguity, missing information or consequential irreversible choices. Ask when it helps; carry out ordinary agreed actions without constant permission.

## Verification and next pass

**MCP ownership and ghost-navigation update — November 1:** the generation 23
orphaned lease was released locally and the prior Full controller was restored.
The ownership changes passed 218 harness tests, 86 subtests and 36 focused
TypeScript tests. The native change passed 181 source predicate/state checks
and its build; the gateway and native update are installed.

Live verification used separate connected MCP calls under generation 25.
Token-bearing status returned `control_mode: lease_token`,
`owned_by_control_token: true` and `owned_by_session: false`.
A normal map-530 ghost `move_to` advanced X 9407 → 9410; its original UUID
receipt completed with `arrived: true`. Fresh observation remained
`is_ghost: true`, `alive: false` at `(9410, -6847.6699, 15.468)`, about
3.047 yards from the starting position. Explicit hand-back released the lease
and restored Full running with Social stopped. This proves remote ownership,
normal ghost movement and hand-back; release/reclaim/resurrection remain open.

November 1: normal trade completion was verified for three incoming items and
600 copper, including actual inventory and money changes. Trade opening,
acceptance and completed transfer are separate states. The controller now waits
locally on an empty open trade or outstanding partner acceptance, while retaining
meaningful interrupts. Base equipment deltas and autonomous social-lane routing
are installed; the new core adds stored-dance recovery. Subsequent live Qwen
decisions equipped Shoddy Chain Pants (+35 base armor) and Shoddy Chain Belt
(+5 base armor), verified by normal completion receipts and equipped state.
Green Chain Boots remained equipped. Dance → native stop QA reset stored pose
10 → 0; following after dancing awaits a check with Aurenne online. Stable
future gear selection and reliable combat assistance remain behavior playtests.

Service grounding then produced four autonomous junk-stack sales for 52 copper
and three normal training receipts for Devotion Aura, Judgement of Light and
Blessing of Might, costing 199 copper. Funds changed 905 → 957 → 758 copper.
The correct trainer was eventually reached after wrong-class attempts; consistent
trainer discovery and buyback recovery remain open. Trainer metadata is now
installed in the core and body/social projections, with full MCP access when
NPCs are visible. The clean restart preserved 758 copper and the three learned
spells. No trainer was in the post-restart observation, so actual class/title
packet verification awaits the next encounter; current offers remain separate
from default-provider metadata.

The buff update is installed with 1,774 offline checks passed. Live self-aura
verification around 06:30 UTC showed Devotion Aura, Blessing of Might and Seal
of Righteousness active with nonzero effect masks after autonomous casts, then
an upkeep-complete wait. Aurenne's own aura rows subsequently confirmed Devotion
Aura (465, mask 1) and Blessing of Might (19740, mask 3), caster GUID 102. Routine
upkeep now excludes short temporary spells and Honorless Target effects, while
ordinary casting remains available. Unnecessary repeated buffs were still
observed; consistent future upkeep remains open. The new guarded area-source
cases still need live Moon/tame tests.

Normal carried-item quest support is installed. On November 1 at 07:05:42 UTC,
querying item 20483 accepted quest 8338 through normal auto-accept behavior.
The quest was complete in the log, with the sliver retained until Helion's turn-in.
At 07:39:51 UTC the updated Qwen controller chose the actual reward-page action,
`quest_reward` index 0. The normal receipt confirmed rewarded status, log removal,
sliver count 1 → 0 and 150 copper received (753 → 903). This quest's lack of an
item choice does not verify broader item-reward selection or the entire chosen
accept/objective/reward loop. The local quiet-item and current-phase guides and
accepted-controller-intent facts improve progress without reviving historical NPC trips.
Unverified proposal notes are omitted only from local body prompts; archives,
social context and full MCP access remain.

The installed follow/quest-phase controller package passed **2,065 offline
checks**, preserved settings and Full running state, and needed no game-server
restart. With all choices retained, frozen before/after cases changed a trainer
waypoint to follow Aurenne GUID 103 at one yard, and repeated quest-complete on
the reward page to quest-reward index 0. No game actions ran in those replays.
The live reward above succeeded. Aurenne then confirmed he was following and
staying with her; fresh 07:41:28 UTC context confirmed persistent follow of GUID
103 at one yard while she moved, with local waiting preserving motion. This
single walk-away test passed. Long-term follow/old-NPC oscillation, repeated
buffs and new Moon/tame guard cases remain open.

Earlier October 31 pickup verification used worldserver `e009657c1083`, with
emotes and catch-up XP retained. Pickup work passed 61 isolated native checks,
1,091 offline controller checks and 76 harness checks; the correction reran the
61 native checks and 1,091 existing controller cases. Normal opening requests
for Journal, Scroll and Orb each resolved to one stored item, with fresh
inventory and quest counters confirming 1/1. Scroll and Orb retained a false
generic LOS diagnostic while normal opening succeeded. Solanian's Belongings
was ready for turn-in at that check. These were operator validation pickups;
the full model-chosen quest loop remains a playtest item. Earlier emote checks
were followed by a real directed-emote reply in play. This document does not
claim a fresh successful live playtest for every installed option.

Prioritize one observable loop at a time: verify the facts and action contract, let Vesper choose, inspect the actual receipt, and record what still fails. Completion means both a working mechanic and a convincing player behavior test, with Moon protection intact.
