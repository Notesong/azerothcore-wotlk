from __future__ import annotations

import argparse
import json
import sys

from .client import BridgeError, Client


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect and control a local Presence agent character.")
    parser.add_argument("operation", choices=["observe", "capabilities", "attach", "detach", "action", "create", "action_result"])
    parser.add_argument("character", nargs="?", default="")
    parser.add_argument("--action", help="JSON game action, for example {\"type\":\"stop\"}")
    parser.add_argument("--arguments", help="Additional JSON arguments for operator operations")
    args = parser.parse_args()
    try:
        arguments = json.loads(args.arguments) if args.arguments else {}
        if args.operation == "action":
            arguments["action"] = json.loads(args.action or "{}")
        if not isinstance(arguments, dict):
            raise ValueError("Additional arguments must be a JSON object.")
        result = Client().request(args.operation, args.character, request_fields=arguments)
    except (BridgeError, ValueError) as exc:
        print(json.dumps({"ok": False, "code": getattr(exc, "code", "invalid_json"), "error": str(exc)}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
