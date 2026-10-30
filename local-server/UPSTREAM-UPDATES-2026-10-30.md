# Original upstream update review — 2026-10-30

Checked the original repositories through the live GitHub API on October 30,
2026. This report compares the installed upstream baselines with the matching
stable branches. It does not compare against the user's backup forks or against
the projects' experimental `test-staging` branches.

**No updates were applied.** No local refs, source files, configuration, database,
running services or installed binaries were changed during this review. Saving
this report is the only filesystem change made by the research agent.

## Pinned versions

| Component and original repository | Stable branch | Installed upstream commit | Current upstream commit observed | Ahead / behind |
| --- | --- | --- | --- | --- |
| [Playerbot core](https://github.com/mod-playerbots/azerothcore-wotlk) | `Playerbot` | `3f2969ddb0da42b48b4fca050c02b19163ba1e20` | `93333d6a9eb00fdf0179adde30da3c17618207d6` | 37 / 0 |
| [Playerbots module](https://github.com/mod-playerbots/mod-playerbots) | `master` | `e88cc4099e69f35126b28942a412ca702d20453b` | `05a1f6fceb8a32aa879b13f5f48934c6e46a774c` | 25 / 0 |
| [AutoBalance](https://github.com/azerothcore/mod-autobalance) | `master` | `1d707cb61a0962ab01e4123681e2d3b66cc558a2` | `1d707cb61a0962ab01e4123681e2d3b66cc558a2` | 0 / 0 — identical |
| [AHBot](https://github.com/azerothcore/mod-ah-bot) | `master` | `c11d8318cbd8714a9980f9464f78e07d3d48a70a` | `c11d8318cbd8714a9980f9464f78e07d3d48a70a` | 0 / 0 — identical |

The core and module updates were merged on October 30 at approximately 17:25 UTC:
[core PR 268](https://github.com/mod-playerbots/azerothcore-wotlk/pull/268) and
[module PR 3011](https://github.com/mod-playerbots/mod-playerbots/pull/3011).
Ahead counts include merge commits and are not counts of separate fixes.

Pinned comparisons:

- [Core: installed baseline to observed head](https://github.com/mod-playerbots/azerothcore-wotlk/compare/3f2969ddb0da42b48b4fca050c02b19163ba1e20...93333d6a9eb00fdf0179adde30da3c17618207d6)
- [Playerbots: installed baseline to observed head](https://github.com/mod-playerbots/mod-playerbots/compare/e88cc4099e69f35126b28942a412ca702d20453b...05a1f6fceb8a32aa879b13f5f48934c6e46a774c)
- [AutoBalance observed head](https://github.com/azerothcore/mod-autobalance/commit/1d707cb61a0962ab01e4123681e2d3b66cc558a2)
- [AHBot observed head](https://github.com/azerothcore/mod-ah-bot/commit/c11d8318cbd8714a9980f9464f78e07d3d48a70a)

## Six useful changes

1. **Combat stability across the server.** Combat revalidation now collects
   invalid GUIDs and looks up each relationship again before ending combat.
   Combat-exit callbacks can alter the same relationship map; retaining an
   iterator across those callbacks could leave it invalid. This core fix can
   benefit normal characters and Vesper alike.
   [Core commit e8b5aadf3, PR 28208](https://github.com/mod-playerbots/azerothcore-wotlk/commit/e8b5aadf3b9f1485efbba1e6e92d44dcc18f573f)

2. **Party invitation cleanup.** Adding a character to a group removes the
   pending invitation from its owning group, rather than only clearing the
   character's invite pointer. The inviting group otherwise retained a raw
   player pointer that could become invalid after logout. This is a general
   core fix; it is not evidence that it caused the earlier Vesper invitation
   problems.
   [Core commit 39fd1165d, PR 28185](https://github.com/mod-playerbots/azerothcore-wotlk/commit/39fd1165d9cf7433171bb19739b92d96590d4e55)

3. **Population configuration crash safeguards.** Reversed minimum/maximum
   bot counts are swapped before random population selection. If both faction
   ratios are zero, they fall back to 50/50 instead of dividing by zero. These
   are safeguards for invalid settings, not an additional performance gain for
   the current valid population configuration.
   [Playerbots commit 0875218a7, PR 2957](https://github.com/mod-playerbots/mod-playerbots/commit/0875218a72da1eaeaf3d0e376b09dbb3b8a12112)

4. **More reliable ordinary-bot looting.** A closer eligible loot candidate can
   replace an old target; a progress watchdog backs off stalled approaches;
   interaction-distance checks follow the core's predicates. Related fixes
   preserve useful and quest loot with nearly full bags, respect hostile game
   objects and gathering requirements, and back off empty gameobject windows.
   These alter native PlayerbotAI loot behavior by default.
   [Approach/selection commit aa5b17a1f, PR 2915](https://github.com/mod-playerbots/mod-playerbots/commit/aa5b17a1ffbb6c6b99d630211dcd45ebc956243c),
   [eligibility commit e42362225, PR 2886](https://github.com/mod-playerbots/mod-playerbots/commit/e4236222586aa6f1b032124ed305e78ce9b5421f)

5. **Ordinary bots maintain themselves at vendors.** Bots running `new rpg`
   can sell surplus items, buy useful supplies/gear and repair when visiting
   appropriate vendors. The path retains quest requirements and needed class
   reagents, checks maintenance conditions and avoids expensive buy evaluation
   for bots without ten silver. This is an automatic behavior change for bots
   running that strategy. Its reagent-classification dependency, PR 2948, is
   included in the observed module head; do not cherry-pick the vendor feature
   alone without its dependencies.
   [Playerbots commit 3eb94de72, PR 2949](https://github.com/mod-playerbots/mod-playerbots/commit/3eb94de72a66bb0ed0877cbe10a1ce01f1fd01a1)

6. **Earlier self-defense for ordinary bots.** Native PlayerbotAI refreshes its
   cached attacker list when the bot enters combat, so existing assist logic
   can see the new attacker that tick instead of waiting for the one-second
   cache. This does not replace its existing target-selection policy and does
   not modify Vesper's Presence combat-intent policy.
   [Playerbots commit 1c6cf8f2c, PR 2918](https://github.com/mod-playerbots/mod-playerbots/commit/1c6cf8f2c1d8648aab5675610fc7647687540433)

## Scope and upgrade considerations

Vesper is a dedicated headless character controlled by Presence and
`mod-presence-bridge`, without native PlayerbotAI. The ordinary-bot vendor,
loot and reaction changes above therefore **do not automatically add or replace
Vesper's own decisions**. General core fixes can affect both Vesper and the
ordinary population. They also do not replace the installed AHBot economy.

The matching supported upstream pair remains the Playerbot core's `Playerbot`
branch and the Playerbots module's `master` branch. The standard AzerothCore
`master` branch is not a substitute for this Playerbot core fork.

An upgrade should be prepared on a backed-up branch and update the matching
core/module pair together. It requires a new build, including the Presence
bridge, and the normal database updater. The compared changes include core
world-database updates and Playerbots database updates; restoring old binaries
alone would not constitute a complete rollback after applying them.

The core bundle changes combat/death handling and reconnect/session lifetime.
It changes `DisconnectToleranceInterval` from a zero default to 60 seconds,
with a 20-second minimum, and extends `LFG.MailItemOnFullInventory` into a
bitmask. Preserve and reconcile local configuration deliberately. Check normal
login/logout, Vesper's headless attachment, party invitations, combat
observations and Moon protection before replacing the running server.

The module bundle also includes substantial battleground and raid work. Those
are less directly relevant to the current PvE leveling session. No claim that
the entire bundle makes a 1,000-bot server faster has been verified locally.

**No upstream updates, database migrations, rebuilds or runtime reloads were
performed by this review.** AutoBalance and AHBot have no newer commits on the
original stable branches observed here.

## Separate SPP fork

The GitHub repository [Notesong/spp-classics-cmangos](https://github.com/Notesong/spp-classics-cmangos)
is a fork of [celguar/spp-classics-cmangos](https://github.com/celguar/spp-classics-cmangos),
with `master` as its default branch. GitHub identifies the same repository as
its source parent. This is the older, separate SPP/CMaNGOS setup, not the active
AzerothCore stack. Its commit differences were not reviewed, and it was not
updated or modified.
