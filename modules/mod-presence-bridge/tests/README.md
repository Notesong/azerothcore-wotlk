# Standalone regression checks

These four C++ source files preserve the isolated checks previously used for
commerce quantities, persistent Moon binding, bounded guard telemetry, and quest
command parsing. Test bodies are exact copies of the original checks; only the
header includes now use `../src/`.

`catchup-xp-policy-tests.cpp` additionally checks the current personal XP policy:
source/account isolation, lower/equal/higher levels, offline reference levels,
supported XP sources and unsafe arithmetic. It has its own `main` too.

`emote-policy-tests.cpp` checks named gesture mappings, packet parsing and bounded
sender/observer/target correlation. Its 141 isolated checks cover unknown target
identity, stale records, same-name different GUIDs, malformed packets and logout
cleanup and distinct bridge-owned observers without using Moon's character
filter. It also has its own `main`.

`pickup-policy-tests.cpp` checks source/cast/receipt identity, pending progress,
interruptions, overrides and actual stored-count deltas in 61 isolated checks.
It has its own `main` and does not connect to a running server.

Each file has its own `main` and must be compiled as a separate C++20 executable.
For example, from this directory with an available C++ compiler:

```sh
c++ -std=c++20 -Wall -Wextra -Werror commerce-policy-checks.cpp -o commerce-policy-checks
./commerce-policy-checks
```

The module build collects only `src/`, so these standalone checks are not linked
into the world server. No test executable, object, database, or live-stack test
is included. Preserving these sources does not claim that a fresh build was run
as part of the source-backup task.
