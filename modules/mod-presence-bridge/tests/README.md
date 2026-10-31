# Standalone regression checks

These four C++ source files preserve the isolated checks previously used for
commerce quantities, persistent Moon binding, bounded guard telemetry, and quest
command parsing. Test bodies are exact copies of the original checks; only the
header includes now use `../src/`.

`catchup-xp-policy-tests.cpp` additionally checks the current personal XP policy:
source/account isolation, lower/equal/higher levels, offline reference levels,
supported XP sources and unsafe arithmetic. It has its own `main` too.

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
