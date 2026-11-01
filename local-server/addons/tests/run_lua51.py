"""Offline Lua 5.1 tests; no game, API or network calls."""
import argparse
import os
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-path", type=Path, default=os.environ.get("VESPERVOICE_LUA51_PATH"),
        help="Optional directory containing an isolated lupa package (or set VESPERVOICE_LUA51_PATH).")
    args = parser.parse_args(argv)
    if args.runtime_path is not None:
        sys.path.insert(0, str(args.runtime_path.resolve()))
    from lupa.lua51 import LuaRuntime

    lua = LuaRuntime(unpack_returned_tuples=True)
    assert lua.eval("_VERSION") == "Lua 5.1"
    addon = Path(__file__).resolve().parent.parent / "VesperVoice"
    lua.globals().arg = lua.table_from({1: str(addon)})
    lua.execute(Path(__file__).with_name("test_vesper_voice.lua").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
