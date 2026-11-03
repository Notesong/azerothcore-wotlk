# Vesper player checklist

Status checked: **November 2, 2026**. This is the development and playtest list for Vesper's
Presence-controlled Blood Elf Paladin.

**Expose grounded facts and exact legal actions; let Vesper's model choose.** The controller should execute chosen persistent intentions, notice meaningful changes, invalidate stale claims, and keep latency and token use reasonable. Available mechanics are not proof of good autonomous play. Preserve his agency while enforcing the standing Moon protection rule.

**How to read this:** `[x]` means an installed mechanical capability was verified in current code. `[ ]` means implementation or a concrete behavior playtest remains. Each section states whether the overall player loop is partial, not built, or awaiting playtest. A checked action does not mean the model consistently chooses it well.

For commands and operation, see [Vesper Commands.md](Vesper%20Commands.md). For ordinary Playerbots, custom alts, dungeon companions and the addon, see [Bot Guide.md](Bot%20Guide.md). Their commands and automation do not automatically apply to Vesper.

The body is back on local **Qwen3.5-4B** (`qwen3.5-4b-action`); the social lane uses
**GPT-6 Luna** (`gpt-6-luna`). Both use reasoning `none`, with Qwen thinking disabled.
This is the November 1 cost choice. Dated receipts and replays below describe the
models selected at those times; behavior still needs playtesting.

## Foundations already available

- [x] Structured character, surroundings, party, spell, inventory and quest observations; native actions use observed identities and normal game checks.
- [x] One native Full controller with separate body and social lanes. Party activity, danger, separation and useful results can attract planner attention without forcing a particular response.
- [x] Persistent follow, movement and melee execution between decisions; bounded action history and transient notes distinguish fresh facts from old proposals.
- [x] Expose the latest accepted controller movement intention with exact action, request ID and source sequence.
  `server_motion_verified: false` distinguishes accepted intention from proven ongoing server movement.
- [x] Apply the same compact grounded facts and focused native body guidance across local and API providers.
  Omit unverified prior-proposal notes from body prompts; retain archives, social context and full MCP access.
- [x] Require one complete native decision object; collapse equivalent complete repeated messages while
  rejecting conflicting decisions, duplicate keys and trailing fragments. Keep failure diagnostics bounded
  and free of provider text or reasoning.
- [x] Persistent Moon protection, protected-creature avoidance and attributable guard incident records. Low health does not authorize retaliation; see the command guide for release rules.
- [x] MCP inspection of full native observations, controller status and recorded model context, with exact complete request paging for newly captured calls.
- [x] Preserve the recorded `current_party_attention` cue in legacy request inspection through its existing
  recursive filters and capture limits. Retain source values without inferring a command;
  full wire capture is unchanged.
- [x] MCP takeover, normal direct actions, action receipts and explicit hand-back to prior local controller intent; native Moon guard remains active.
- [x] Install and verify the remote lease correction: the exact secret token authorizes mutations and
  token-bearing status proves `owned_by_control_token`. SDK session churn does not own or revoke the lease;
  old generations stay fenced. Remote hand-back is explicit, with no automatic expiry. Local stdio remains
  session-bound with disconnect cleanup; local operator recovery can require the exact observed generation.
- [x] Install the read-only Presence MCP ownership display, with Start/Resume blocked during takeover,
  active control, hand-back or invalid/unreadable lease status. Verified released status and the local
  controller running after installation; 71 backend and 33 frontend targeted checks plus lint passed.
- [x] Bounded MCP event waits with per-character cursors, server epoch/history-gap reporting and a fresh snapshot on wake. No API model calls are needed for MCP inspection or waiting.
- [ ] Playtest a complete MCP visit with Vesper: observe → take over → choose actions → wait on meaningful
  changes → inspect results → explicit `hand_back`. Verify ownership is released and the autonomous controller
  resumes if it was running before takeover. A conversation turn ending cannot itself signal hand-back.
  November 1 local operator recovery released stranded generation 38 after a completed visit; this does not
  verify the normal full-visit hand-back path.
- [x] Installed catch-up XP: Vesper receives 2× his normal award while below Aurenne's level, reverting to normal at equal/higher level. This is a local progression mechanic, not model quest competence.
- [ ] Continue playtesting attention, stale-note invalidation, persistent goals and response latency across real encounters; fix misleading facts or missing controls before prescribing choices.
- [ ] Expose bounded recent nonmovement failures with action/target/quest-phase identity, result code, age
  and attempt count. Reconsider them when relevant fresh facts change; annotate choices without automatic retry bans.

## 1. Quest acceptance, readiness, turn-in and rewards — mechanics installed; needs playtest

- [x] Expose native verified acceptance and post-reward lifecycle receipts with distinct transition IDs,
  title, actor and timestamp. Failed/full-log attempts, reopened menus and abandonment are not successes.
- [x] Queue fixed party acceptance/turn-in confirmations without a model call, preserving pending original
  speech IDs across controller restarts. Share bounded recent native facts with body and Social; full MCP
  retains the native receipt ring and coverage. Held quests are not backfilled as new acceptances.
- [ ] Playtest a new NPC/shared/item acceptance and an actual reward confirmation, including repeatable
  quest episodes and recovery of a queued notice. Offline checks do not establish live notice delivery.
  Installed November 2 as 13 files after **3,006 Presence checks**, **418 harness checks plus 89 subtests**,
  all **12 native pure suites** and the incremental worldserver build passed. Clean shutdown/startup,
  fresh native lifecycle/MCP preview, released control and resumed Full were verified; saved settings
  were preserved. The initial native ring was empty and explicitly did not backfill held quests.

- [x] Keep quiet current NPC acceptance/turn-in phases legible while a resolved Moon binding protects a
  different creature. This changes short-guide selection only; persistent identity, full Moon instructions,
  hard execution guard and buff/trade restrictions remain active. Normal NPC/dialog/action checks remain.
- [x] Pass 2,689 offline checks and select the correct current reward step in paired and real request-format
  replays without executing game actions. Direct MCP reward of quest 9254 and Qwen's prepatch acceptance of
  quest 8487 do not establish autonomous turn-in with the new guide.
- [ ] Playtest autonomous NPC acceptance and reward claiming under Moon without reopening an earlier dialog phase.

- [x] Query an observed offer, accept an eligible quest, recognize explicit quest status/readiness, and open the correct observed NPC's normal turn-in dialog.
- [x] November 1 direct MCP acceptance of Swift Discipline (9066) at Instructor Antheol:
  the normal receipt and fresh log confirmed acceptance; fresh inventory verified one
  Antheol's Disciplinary Rod (22473).
- [x] Install grounded NPC offer choices: current menu → `quest_query`, then fresh enabled details →
  `quest_accept`. The correction passes 2,350 offline game-player checks. An unheld quest's item-check
  page is not a turn-in opportunity.
- [ ] Playtest autonomous acceptance of a future offered NPC quest; direct MCP acceptance does not verify this choice.
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
- [x] November 1 direct MCP pickup opened crate 180600 through normal Opening (3365) and stored one crystal
  (20743). Fresh inventory changed 0 → 1 and quest 8463 advanced 0/6 → 1/6; the original request completed
  with no skipped slots and no pending opening.
- [x] After hand-back, Vesper autonomously chose two more crate pickups at 15:34:19 and 15:34:57 UTC.
  Each original request completed with one crystal (20743), no skipped slots and no partial result;
  captured follow-up views showed quest 8463 at 2/6 and then 3/6.
- [x] Later live observation and user confirmation showed the crystal objective at 6/6 after one direct pickup
  and five during autonomous play. This verifies the collected objective, not turn-in or reward; individual
  receipts were retained for the two examples above. Arcane Cores were 1/6 and the Head of Thaelis 0/1.
- [ ] Add generic carried-item use, including quest items with the required unit/object/location target and normal cooldown/consumption checks.
  Swift Discipline showed Ralen 1/1 and Meledor 0/1 on November 1; shared credit does not verify Vesper used the rod.
- [ ] Demonstrate quest-specific reasoning: choose a relevant object or spell, such as Arcane Torrent when a quest actually calls for it, using the observed learned spell and objective rather than an invented ability or target.
- [ ] Cover quest mechanics that need ground targeting, item targeting or other controls beyond the current unit-cast/object-interaction actions.

## 3. Quest discovery and navigation — partial

- [x] Expose held objectives, nearby units/objects, observed quest relevance, opening/range facts and nearby questgiver relations/status.
- [x] Provide body guidance across providers: object names/coordinates do not prove a route or destination,
  and already holding a required item is not a reason to revisit its source. Unknown routes stay unknown.
- [ ] Playtest departure from the old Soaked Tome and sustained navigation toward the agreed current objective.
- [ ] Connect objectives to relevant observed mobs, objects and NPCs; discover available quests and choose a useful next objective.
- [ ] Add grounded route/travel information and completion checks. Distinguish a known destination, a remembered lead and an unknown location; no magic GPS or fabricated coordinates.

## 4. Consumables and restocking — self-use first increment; needs playtest

- [x] Inspect vendor offers and buy available stock with normal money, quantity and bag-space checks.
- [x] Install and verify `use_item(item_guid)` for owned self-restoration potions and food/drink through
  the normal item-use handler. Expose supported effects, partial readiness, cooldown and exact current action;
  distinguish accepted, emitted, consumed and observed effects. Item spells are not learned `cast` abilities.
- [x] Verify bounded body choices and full MCP item-use access, with original-request receipt lookup and a
  persistent body-controller fence against repeating an uncertain use after a restart.
- [x] Pass 2,733 Presence checks, 314 harness checks plus 86 subtests, 87 Gateway source and 87 compiled
  checks, and 75 native item-use checks. Verify an actual Qwen request contains the owned potion's exact
  action, and MCP's live preview retains its use facts. These checks do not establish autonomous timing.
- [x] After the clean restart, live state offered the owned Minor Healing Potion (one) and Refreshing
  Spring Water (eight) with their exact self-use actions and cooldown facts. Stock drink-script support is
  restricted to its reviewed self-mana signature. Health/mana were full; neither item was consumed for testing.
- [ ] Playtest a useful self-chosen potion or food/drink use and verify inventory, cooldown and recovery.
  Do not consume the sole potion at full health just to demonstrate the action.
- [ ] Add generic consumable use and meaningful supply counts: food, water, potions, reagents and ammunition where the character's class actually needs them.
- [ ] Choose when to restock, how much to afford, and when to eat/drink/use a supply; verify the result without blindly repeating an uncertain purchase.

## 5. Bags and capacity — mechanics installed; needs playtest

- [x] Inspect backpack/bag occupancy, free general-purpose space, specialty restrictions and empty bag equipment slots.
- [x] Equip a carried eligible bag using `equip_item`, including a chosen bag slot; inspect and compare capacity before replacing a smaller bag.
- [x] Verified Vesper chose and equipped the Sunstrider Book Satchel in a free bag slot during safe downtime.
- [x] Retain up to four current equipped-bag identities in Social context, matched by GUID and bag slot;
  missing/conflicting facts remain unknown. At the November 1 check, Small Brown Pouch (4496) was equipped
  in slot 20 with six slots and total capacity 26. Its normal equip receipts had succeeded.
- [x] Attribute Social failure claims to the matching requested action and item/target, using current equipment
  facts for equipment status; an unrelated quest failure is not an equip failure.
- [ ] Playtest accurate Social bag reporting after a new equipment change.
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

**VesperLoot read-only hints:** the server update and client package are installed,
and the native build and server restart are complete. The font-wrapping compatibility
correction is installed and passes with that API absent; 46 offline Lua 5.1 checks
pass in total. Basic live client display and server replies are now user-confirmed;
detailed row-state changes and group/range/expiry edges remain awaiting playtests.

- [x] After a full client restart, Vesper Loot Hints appeared in the AddOns list.
  With Vesper in the party, the user confirmed a fresh Arcane Patroller's tooltip
  and inspected-corpse panel showed loot information on November 1.
- [ ] Verify the current party leader receives Vesper's current item need and
  availability while Aurenne's own completed quota and pickup eligibility remain unchanged.
- [ ] Verify actual generated per-player loot distinguishes available, not currently
  needed, collected from this corpse, unavailable, partial and unknown states.
- [ ] Verify a real Vesper pickup changes the hint and his inventory/objective count;
  incomplete replies, target changes, group loss and expiry must not retain stale availability.

These hints add no native loot slots or pickup actions and make no model calls.
Missing generation/per-player facts remain unknown; a loot-template possibility
is not proof that an item exists on this corpse.

- [x] Loot eligible creature corpses and ordinary chest objects under normal ownership, lock, quest, range and bag rules. Pending openings retain their original request identity; failed/unfinished pickups do not become collected-item working notes.
- [x] Local body view binds currently observed lootable corpses/chests to exact `loot(target_guid)` candidates, preserves full corpse facts and skips the pending target; contents remain unpredicted until actual receipts.
- [x] Correct candidate ordering: ready corpse pickups precede distant crates, with a bounded mix of source
  kinds that does not displace ready pickups. The installed controller update passed 2,182 offline checks.
- [x] Demonstrate autonomous named-corpse pickup after the candidate correction. At 16:07:36 UTC, Qwen chose
  loot on a new Thaelis corpse; the original completed receipt stored one Head (21781), with no skipped
  slots or partial result. Fresh state showed Vesper alive, inventory count 1 and quest 8468 at 1/1;
  the user confirmed the pickup. This preceded the approach freshness correction; sustained reliability remains open.
  Earlier, at 15:38:59 UTC, dead, lootable Thaelis
  was 0.24 yards away but omitted behind four crates 5–48 yards away. No retained loot attempt targeted
  that corpse; Head progress remained 0/1, and the corpse's actual contents were not established.
- [ ] Add a bounded new-loot availability wake event for untracked deaths, preserving combat, movement and pending-opening priorities. Current untracked loot can wait for the normal review deadline.
- [x] Add observed Need/Greed/Pass rolls and model-chosen responses, including equipment usefulness and group expectations.
  The installed action uses an opaque round identity and exact currently legal choices, preserves
  ongoing movement/combat, and distinguishes a recorded vote from winning or receiving loot.
  Verified November 2: native build and 462 isolated checks; 2,850 controller tests including 48 roll cases;
  364 harness tests plus 89 subtests; 96 Gateway checks against source and compiled output.
  After the clean restart, Vesper was online, Full was running, control was released and saved settings were preserved.
- [ ] Playtest Need, Greed and Pass on real party loot, including an expired round and normal inventory delivery.
  The first observed Malachite roll expired without a submitted vote: the body woke four times with
  legal choices but pursued quests and ordinary corpse loot. A compact, deadline-aware priority decision
  is installed. The user subsequently observed an immediate real Pass on November 2; that checks one
  timely vote, while Need, Greed and normal item delivery still need playtesting. The six-file update passed 2,876
  regression checks and 176 independent focused checks. A model-only historical Malachite replay
  returned deliberate Pass in 1.406 seconds with 861 input tokens, without sending a game action.
- [ ] Handle bind-on-pickup/other confirmations, unique limits, quest loot, full bags and partial/error results explicitly; avoid loops or assumptions that every item was received.

## 10. Combat and party awareness — core mechanics installed; needs playtest

- [x] Observe party/lead activity, targets, health/resources, learned spells, cooldowns and nearby threats; target, attack/chase, stop and cast legal known spells.
- [x] Configured lead-specific combat healing preference: routine topping-off at 50% or above should not delay fighting/following; below 50% healing remains a choice. Local lead health is explicit; tame/Moon protection retains priority.
- [x] Recognize a current living hostile victim matched to the accepted attack as an ongoing chosen pursuit
  before melee contact sets `in_combat`; idle lead/spacing facts alone do not make the body idle.
- [ ] Playtest continuing a permitted chosen fight while the lead is idle or starts another action, with
  withdrawal, newer directions and protection still available to the planner.
- [ ] Demonstrate timely awareness of Aurenne's actual outgoing attacks/casts, meaningful assistance, range/path recovery and sensible resource use. A selected target alone is not proof she attacked.
- [ ] Evaluate combat choices in real fights without replacing his choices with a fixed rotation or automatic attack rule. A dedicated tank/healer role remains separate development.
- [ ] Ground ordinary offensive/healing spell choices in current target applicability, range, resources,
  cooldown and protection facts; unknown checks remain unknown. Include recipient health and urgent self-care:
  the November 1 bonfire incident included Holy Light aimed at a hostile, then full-health Aurenne while
  Vesper was critically hurt.
- [x] Install additive native spell facts and a bounded body combat card linking current targets to matching
  cast attempts, with partial target checks, normal melee range, cooldown/GCD and base costs.
  Effective cost, exact spell range and full castability stay unknown; ordinary execution validation is final.
  Self-area/other target modes retain their full catalog/actions but are outside this compact first version.
  Full MCP access and hard Moon/taming guards remain. Native build, clean restart and Presence deployment
  completed; 2,404 offline checks passed, with the full 27 body actions retained.
  Live Holy Light (635/639) checks accepted self/ally; Judgement (20271) rejected them. Native melee facts
  and all 29 exposed active spells reached the actual Qwen body request. No hostile was present; the card correctly
  remained absent during healthy, quiet observation.
- [x] Observe the combat card in live body requests with active lead engagement, the exact hostile and matching
  attack/cast choices before follow decisions. This verifies input availability, not a successful cast or useful assistance.
- [ ] Verify useful combat choices and response latency across real encounters; supplied context alone does not
  establish reliable behavior.
- [x] Install guidance to review current lead life/combat/outgoing-action facts before following.
  `follow` tracks the lead without assisting; `attack` selects, chases and starts ordinary autoattack.
  This is an interpretation/focus correction: combat context already existed before problematic follow choices.
  Informed assistance, another useful action, following/retreating and restraint during taming remain choices.
  The Python-only update passed 2,427 offline checks and is installed, with saved settings preserved and
  the Full controller resumed; no game-server restart, automatic assist or dispatch veto was added.
  Qwen's actual 20:04:54 UTC request (sequence 466) included Aurenne alive, out of combat and at 202/202 health.
  This verifies delivery of the new facts; corrected follow/assist decisions in a fresh fight remain unverified.

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
- [x] Separate observed active buffs from missing-effect work in both model lanes. Show readable actual
  aura time alongside raw milliseconds, and compute the support summary before candidate display limits.
  Quiet buff-upkeep focus requires a fresh missing effect with observed mechanical readiness; an all-present
  quiet scene instead permits companion continuity, the agreed goal, waiting, following, speech or initiative.
  Unknown/suppressed/alternative effects remain distinct. Normal casting and near-expiry decisions stay available.
- [ ] Playtest the first companion-framing adjustment against the repeated healthy-Might loop. This changes
  presentation and guidance, not the executor, a timed refresh rule or the ability to cast deliberately.
  Installed November 2 as seven Presence files with **3,054 checks passed**, saved settings preserved,
  Full resumed and the world server kept online. Paired local replays used identical historical world
  facts/goals and dispatched no actions: both quiet-scene versions waited; the moving-party choice
  changed from Aurenne's nine-minute Might to Edgalin's 81-second Might. This is one grounded choice,
  not proof that repeated buffs or all future companion decisions are solved.
- [x] Extend the native beneficial guard to positive persistent area-aura sources under Moon, uncertain protection
  or active/recent taming. Cancel only owned sources through normal aura removal; other casters' sources remain.
  Full cast choices and violation auditing remain available.
- [ ] Live-test the new Moon/tame area-source cancellation and foreign-caster preservation cases.
- [ ] Broaden grounded role facts for direct healing, damage and utility abilities beyond the current support subset.
- [ ] Demonstrate interrupt, cleanse, stun and emergency healing when actually available and appropriate. Respect protection/taming restrictions and verify the spell's real outcome.

## 12. Travel, hearth, taxis, inn binding and mounts — partial

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
- [x] Expose friendly flight masters and normal local-node discovery, followed by a fresh route menu.
  Offer only Vesper's learned reachable network, with route identity and normal reputation fares.
- [x] Install paid `taxi_start` choices for body, already active Full social turns and direct MCP.
  Bind the fresh menu/NPC/destination and preserve original-request uncertainty fences across restarts;
  a missing reply does not authorize a second purchase. Native flight owns motion until landing.
- [x] Expose actual flight state, normal headless spline/worldport continuation, original-request results
  and bounded MCP taxi-change/arrival events. Routine follow/stuck replans wait locally in transit;
  chat, eligible loot rolls and meaningful safety/ownership changes retain attention.
- [x] Verify one ordinary chosen paid flight during play: on November 2, Qwen selected Tranquillien →
  Silvermoon City. Original request `1ead039871a648cd80364400aac78834` recorded the native flight and
  later completed with `arrived: true`, landing coordinates and an initial fare of 99 copper.
- [ ] Playtest new local-node discovery and an ordinary route crossing maps. The single same-map paid
  ride does not establish those branches or reliable future travel choices.
- [ ] Add deliberate hearthstone use and intentional inn binding, with observed availability and resulting destination.
- [ ] Add reliable mount/dismount state and controls, travel/combat transitions and destination verification. Existing spell casting is not a complete travel subsystem.

November 2 flightpaths installation passed **2,922 Presence checks**, all **11 native pure suites**,
**415 harness checks plus 89 subtests**, and **100 Gateway source / 100 compiled checks**.
The incremental worldserver build passed. Clean shutdown, startup, fresh native/MCP taxi state,
released control and resumed Qwen were verified; all saved settings were preserved. No paid flight
was dispatched for installation verification. Subsequent normal play confirmed the same-map ride
above; new-point discovery and cross-map continuation remain unchecked.

## 13. World traversal — partial

- [x] Interact with eligible game objects, including objects that use the normal game-object handler.
- [ ] Playtest doors and zone transitions; add grounded handling for elevators, boats and portals, including boarding/waiting, transport state and arrival.
- [ ] Recognize a blocked route or changed map and recover without fabricated paths, direct-line fallback or teleport shortcuts.
- [ ] Ground a claimed travel goal in its actual destination and current quest state. On November 1, the planner
  copied Bonfire coordinates while claiming to travel to Falconwing Square for a quest whose required item was 0/1.
- [ ] Correct the later fabricated Bonfire repair mechanic and blocked-follow loop. At 15:40:19 UTC, Qwen
  chose the exact fire center to "rest and recover gear durability" despite full health. A subsequent live
  check found him alive there with 135 health. The object advertised no repair service;
  sustained behavior still needs testing.
- [x] Install conditional body guidance across providers for visible fires/spell-focus objects: names, flags and
  object coordinates establish no rest/repair service or useful waypoint. Durability repair requires an
  observed repair NPC and normal `vendor_repair`; no movement ban or blanket type-8 hazard claim is added.
- [x] Generate approach choices two yards to the actor's side of loot, quest, service and blocked-lead targets,
  retaining observed height and separate source coordinates. These are unverified pathfinding choices;
  fresh range/LOS checks remain authoritative, with no safe-zone or reachability promise.
- [x] Report explicit lead LOS blockage without advertising an unchanged follow link, and offer a bounded
  normal approach choice when grounded in fresh same-map positions.
- [x] Pass fresh observations into approach generation. The installed two-file follow-up passed 2,190 offline
  checks; the actual Qwen 4B request at 16:12:26 UTC showed two noncenter loot approach choices, each two
  horizontal yards to the actor's side with source height preserved. This verifies model-visible representation.
- [ ] Verify executed approach movement, route safety and sustained recovery. The earlier successful Head
  pickup does not establish that generated approach points were used.
- [ ] Expose environmental hazard effects and scripted-behavior uncertainty. Bonfire 183444 uses `go_heat`, which
  is absent from current object facts; sampled health loss does not identify fire versus individual attackers.

## 14. Death and resurrection — normal recovery mechanics verified; broader loop incomplete

- [x] Install the native fix exposing `self.is_ghost` and numeric `self.death_state`, with ordinary
  `move_to` and `stop` for an already released ghost. Keep normal pathfinding, map/range/immobility checks
  and Moon protection. Cancel pending motion on living/ghost transitions or unreleased death before arrival.
- [x] Verify actual ghost navigation through a fresh accepted action, observed position change and original result.
  Generation 25 moved about 3.047 yards on map 530 while `is_ghost: true` and `alive: false`; the original
  receipt completed with `arrived: true`. Following, combat, casting and looting stay blocked dead.
- [x] Expose observed Spirit Healers and their normal recovery option. Selecting it opens a server confirmation;
  a separate chosen `spirit_healer_activate` requires that exact current, single-use healer confirmation.
  Ordinary interaction range, visibility and line of sight apply; Moon protection remains active.
- [x] Verify direct MCP recovery through normal healer menu 83, option 0, then explicit confirmation in generation 30.
  The actual receipt showed alive false → true, ghost true → false, health 1 → 79 of 158, 14 durability changes
  at the configured 25% rate and no resurrection sickness at level 6. Later health regenerated to 158.
  Explicit hand-back restored Full running with Social stopped.
- [x] Preserve actual recovery receipts, distinguish them from current consent, expire confirmations after 30 seconds,
  clear them on scene/life changes, and resolve uncertain activation through its original request without repeating it.
- [x] Expose current own-corpse GUID, map/instance, position, normal range/delay and grounded reclaim eligibility.
  Unresolved identity, range or delay stays unknown and cannot advertise a reclaim action.
- [x] Choose `reclaim_corpse(target_guid)` against the exact currently observed own corpse, using the normal handler.
  Released-ghost, same-map/instance, elapsed-delay, 39-yard range and arena rules apply. The choice is not automatic,
  and adds no GM shortcut or Spirit Healer resurrection sickness/durability penalty.
- [x] Verify a chosen live normal reclaim at about 31.684 yards: alive false → true, ghost true → false,
  health 1 → 101 of 202 and no remaining resurrectable corpse. The receipt verifies this mechanical action.
- [ ] Add intentional release and exposed acceptance of a real resurrection offer, with appropriate recovery choices.
- [ ] Demonstrate autonomous recovery choice, rejoin the party and restore the chosen goal; report when recovery is
  blocked. No automatic resurrection or GM shortcut is provided; the direct Spirit Healer and corpse tests are
  mechanical checks rather than proof of autonomous recovery judgment.

## 15. Groups, readiness and dungeons — invitations partial; broader loop not built

- [x] Observe a received party invitation and choose accept/decline; observe party membership and activity.
- [ ] Add the remaining intentional group controls and readiness checks: waiting for members, confirming a plan, dungeon entry and appropriate reset handling.
- [ ] Demonstrate following the agreed group pace and recognizing who is missing or unready. Ordinary bot recruitment/role buttons remain separate; see the bot guide.

## 16. Lost or separated recovery — local following exists; broader recovery incomplete

- [x] Separation/distance changes can attract attention; reacquire a visible friendly unit and follow using normal movement.
- [x] Add bounded pickup surroundings from current raw observations before display caps: distinguish hostile,
  other attackable and unknown-relation living creatures; expose source/advertised-approach proximity and levels.
  Coverage marks omissions and missing geometry. The 15-yard sample radius establishes neither aggro range nor
  a safe path; the model retains every gameplay choice and Moon protection remains unchanged.
- [x] Highlight current lead visibility/motion and pickup detour distances; preserve unknown lead coordinates.
  Explain that a fixed `move_to` to snapshot coordinates replaces tracking, while `wait` preserves ordinary motion.
  An accepted follow is past execution evidence, not a standing human order or proof of current server movement.
- [x] Keep the newest recorded human words salient with authorship/time/source facts. Older conversation and
  model proposals remain historical, without automatic keyword commands or inferred instructions.
- [x] Ground one model-written party separation alert in prior observed follow contact plus three seconds/newer
  state, or repeated measured follow failures bound to the exact lead and distinct request identities. Startup
  roster entries alone do not establish lost contact. Cached polls preserve state without authorizing speech.
  The brief alert can accompany movement/combat, yields to pending human replies, and suppresses repeats only
  after confirmed delivery. Failed sends remain eligible; uncertain delivery resolves its original request.
- [x] For an offered current separation episode, require its exact status tag and a factual opening from a small
  set, with the remainder written by the model. This is an output contract, not evidence of learned situational
  judgment. Gameplay choices and other contexts retain their existing action schemas.
- [x] Install the exact nine-file controller update without a world restart, preserve settings and restore Full
  running/unpaused with MCP control released. Fresh verification found Vesper alive. The full offline suite
  passed 2,633 checks before the final factual-opening/parse guard; 13 targeted checks passed after those changes.
- [x] Keep validated native separation alerts from waiting on the routine speech cooldown, while retaining
  execution policy, human-reply priority and confirmed-once episode tracking. The installed two-file
  priority follow-up passed 125 focused offline checks; ordinary speech cooldowns remain unchanged.
- [ ] Verify a real lost-contact party alert, its source chip, deferred/failed delivery and reunion suppression.
- [ ] Playtest dangerous pickups while following, including the mob-filled Weapon Container area; verify grounded
  choices instead of replaying old destinations or narratives. Offline fixtures do not establish live reliability.
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
- [x] Route main conversation and autonomous emotes through the social lane; Full's shared controller executes gameplay choices.
  Body output cannot echo the human's chat as Vesper's own line. Direct MCP speech/emote controls remain available.
  Ordinary optional body speech and typed factual reports are installed below; model behavior still needs a playtest.
- [x] Install and verify native Full social gameplay: reserve one primary action slot for an already eligible
  social call, refresh and validate relevant facts after generation, and use the same policies, normal native
  actions, MCP interlock, Moon guard and original-request uncertainty handling as the body.
- [x] Preserve accepted continuing social intentions across routine body reviews, while keeping danger,
  new human input, protection changes, completion and failure meaningful interrupts. Social wait keeps the body intention.
- [x] Retain the actual social request/capture, model identity, validation facts and execution result, with
  lane-specific Moon audits. A proposed or accepted interaction is not proof of a completed teleport.
- [x] Expose a bounded `needs_reasoning_help` cue from repeated verified body failures to the next existing
  social call, preserving exact request/action/error context without extra API polling or forced retries.
- [ ] Playtest a social-chosen mechanical action and its actual effect; verify Qwen resumes useful work afterward.
  Installed November 2 with 2,800 controller checks, 100 independently repeated feature/audit checks,
  321 harness tests plus 86 subtests, and 91 Gateway checks against both source and compiled output.
  Readiness checks confirmed Full running, control released and saved settings preserved; the world server stayed online.
- [x] Brief native interaction gestures accompany verified NPC/menu/quest progress and corpse-loot opening, without extra chat or persistent poses. Normal chest opening keeps its existing spell animation.
- [x] Send ordinary named/targeted WoW emotes through the real emote channel, including hug, point, kiss and slap. Named gestures and custom prose are distinct; completion requires an actual normal-handler delivery receipt.
- [x] Expose actor + emote + authoritative explicit target facts. Directed incoming player gestures can reach the social inbox once per event; unknown/untargeted gestures do not force a direct wake. Target identity is never guessed from a name.
- [x] Observed in play: Aurenne directed comfort at Vesper and he chose a targeted nod in response.
- [x] Clear the Presence-owned character's stored dance loop on mechanical intent or active movement/combat/casting,
  without changing posture, movement, spells or protection policy. Other bots are unaffected.
- [x] Normal-action QA verified dance state 10 → native `stop` → state 0 after deployment.
- [ ] Verify follow after dancing with Aurenne online; she was offline immediately after this restart.
- [ ] Playtest natural replies, greetings and downtime expression with cooldowns; avoid combat distraction, repeated lines and constant permission questions.
- [x] Install the optional body reports and VesperVoice addon files in the matching 17-file update.
  Keep normal speech intact; attach runtime lane/provider/requested-model metadata outside the utterance.
- [x] Permit ordinary optional Qwen speech in existing gameplay calls without requiring an evidence tag.
  Explain intent, ask questions or comment with 20-second body spacing and 30-second queued expiry;
  keep human-reply priority, normal delivery checks, deduplication and original-request uncertainty handling.
  Shared transcript entries carry source and time without turning model claims into verified world facts.
- [x] Ground trainer pages in normal Available/Unavailable/Known states, per-page eligibility and exact
  next-page actions for both lanes. An unchanged first-page query is not learning, and later pages remain unknown.
- [x] Verify ordinary Qwen speech in live play: five later party lines had successful delivery receipts
  and Body/local `qwen3.5-4b-action` provenance after installation.
- [x] The user's November 2 screenshot confirmed the Qwen source chip beside ordinary party speech.
- [ ] Playtest chip hover details, timely trainer progress and Luna's use of the shared updates.
  Optional speech does not guarantee that the model chooses to say something.
  Installed November 2 as ten Presence files with **2,971 offline checks passed**, saved settings
  preserved and Full resumed without a world restart. A frozen local Qwen replay chose trainer page 1
  and a natural spoken line; no game action was dispatched by that replay.
- [x] Verify the clean world restart and game/administration readiness, preserve saved settings, resume Full,
  and release MCP control. Vesper was online and alive with Full running unpaused and no reported error.
  The separate Social-only controller stays stopped because Full supplies both model lanes.
- [x] Repair Presence's bundled `tools.presence_acore.Client` parity with the canonical harness:
  the Full runner's old `execute` signature rejected speech metadata before server dispatch.
  Default-client and serialization checks passed; the user then confirmed a genuine Social reply and **[Luna]** chip.
- [x] Install addon 0.1.1's missing LFG notice template fallback. The actual client channel-notice branch
  reproduced `format(nil)` without that template; existing localized strings remain intact.
- [ ] Reload the client and check the LFG notice fallback. The current error's notice token was not recorded;
  reproducing this known missing-template path does not identify every possible channel-notice error.
- [ ] Playtest a verified completion report, a current blocker and human-reply priority, with no new model calls
  or repeated routine narration. Verify Qwen and MCP chips and hover details; only the Luna chip is confirmed in play.
- [x] Install learned-ability names and whole-link handling from verified completed training receipts. Match exact
  learned IDs to observed catalog/direct trainer names; keep unknown names unknown and never substitute wrapper labels.
  Earlier native receipts verified Hammer of Justice (853), Purify (1152) and Parry (3127).
- [x] Share character-bound recent learning facts between Body and Social: at most four receipts/eight abilities
  for 30 minutes in memory, covering receipts observed by the running controller without historical backfill.
  Reports remain optional model choices in existing calls; quiet-state checks, cooldowns and human replies take priority.
  The three-file update preserved settings and resumed Full without a world restart. MCP control was released.
- [x] Pass the final 2,498 offline checks and 26 independent feature checks for the learned-ability update.
- [ ] Playtest a new training report, its complete clickable link and Social's use of the shared learning history.
  Earlier training receipts do not prove these new behaviors; this is not a full spellbook or automatic announcement.

## 20. Continuity, intentions and asking for help — partial

- [x] Imported permitted Presence context, recent conversation, bounded session notes and optional observer images support continuity. Images require a bound renderer and describe that observer's view.
- [x] Focus safe local carried-item quest decisions before routine buff/service guidance while retaining complete
  dynamic observations and the allowed action schema. Matching fresh item details can advance; danger, travel,
  protected activity and other active dialogs keep the full guide.
- [ ] Maintain useful chosen goals through interruptions and discard stale/inconsistent claims using fresh observations and action receipts. Keep the payload small enough for timely decisions.
- [ ] Integrate durable adventure memory for this native Full controller; current session notes/scene ledger are not a complete persistent Chronicle, and starting a new run does not prove the previous goal was restored.
- [ ] Add an explicit, natural “ask Aurenne” fallback for meaningful ambiguity, missing information or consequential irreversible choices. Ask when it helps; carry out ordinary agreed actions without constant permission.

## Verification and next pass

**Body grounding and bag-reporting update — November 1:** installed manifest
`c9506d3e1769` passed **2,279 offline checks**, preserved settings and resumed the
Full controller after explicit hand-back without a game-server restart. Body
facts/focused guidance now apply across providers; transport, Full profile,
Social/full MCP detail and permissions, and Moon's hard guard retain their scope.
The body is back on Qwen3.5-4B and Social remains GPT-6 Luna, both reasoning off.
These are installed representation/parser changes, not proof that wandering,
early abandonment of fights or incorrect bag claims are solved in play.

The reviewed GPT-6 Luna run contained 44 rejected outputs among 126 retained
decisions: 36 invalid JSON and 8 incomplete outputs. The exact cause remains
unproven. Equivalent complete repeated JSON messages are now handled despite
whitespace/key-order differences; strict whole-response validation and bounded
content-free diagnostics support the next check without claiming that this
parser edge caused the earlier failures.

**Spirit Healer and crystal pickup — November 1:** direct MCP generation 30
completed the normal healer dialog and separate activation. Its measured receipt
confirmed living state, health 1 → 79 of 158, 14 durability losses at the configured
25% rate and no sickness at level 6. A subsequent normal crate opening stored
one crystal (20743); fresh inventory and quest 8463 both changed from zero to
one, leaving the quest at 1/6. The original loot request completed with no pending
opening. Explicit hand-back restored Full running with Social stopped. These
operator checks establish the direct mechanics. After hand-back, Vesper chose
two more crate pickups at 15:34:19 and 15:34:57 UTC. Follow-up captures at
15:34:20 and 15:34:59 UTC retained completed original receipts, each with one
crystal (20743), no skipped slots and no partial result, alongside quest counts
2/6 and 3/6. A later live observation, confirmed by the user, showed crystals
6/6, Arcane Cores 1/6 and the Head of Thaelis 0/1. The crystal objective was
collected after one direct pickup and five during autonomous play; turn-in and
reward remain unverified.

The missing Head diagnosis found no retained loot attempt on the nearby dead,
lootable Thaelis corpse: the four displayed pickup choices were farther crates.
This establishes a candidate omission, not a failed Head-loot receipt or proof
of the corpse's contents. The later Bonfire visit was another observed failure:
Qwen invented resting there to restore durability and moved to its exact center.
The seven-file correction is now installed and passed 2,182 offline checks:
ready corpses precede distant crates, bounded kind mixing preserves ready
pickups, and conditional fire guidance rejects inferred rest/repair services.
Generated approach choices use two-yard actor-side horizontal offsets with
observed height and separate source coordinates. Explicitly blocked follow
reports its LOS problem and can offer an approach choice. Normal pathfinding
and fresh interaction checks remain authoritative; these points are not proven
safe zones. At 16:07:36 UTC, Qwen chose loot on a new Thaelis corpse; its original
completed receipt stored one Head (21781), with no skipped slots or partial
result. Fresh state confirmed inventory count 1 and quest 8468 at 1/1 while
Vesper was alive, also confirmed by the user. This success preceded the approach
freshness correction. The two-file freshness follow-up is now installed and
passed 2,190 offline checks. An actual Qwen 4B request at 16:12:26 UTC showed two
loot approach choices, each two horizontal yards to the actor's side, preserving
source height and avoiding the source center. This verifies representation in
the model request, not executed approach movement or safety. Sustained
pickup/navigation behavior, native hazard metadata, autonomous resurrection
and the full corpse/rejoin loop remain open.

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
normal ghost movement and hand-back. The later Spirit Healer check above adds
normal recovery; release, corpse reclaim and real resurrection offers remain open.

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
