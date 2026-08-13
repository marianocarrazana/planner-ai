from __future__ import annotations

import sys

from planner_ai.config import clear_credentials, get_config_path


def main() -> None:
    if "--reset-auth" in sys.argv:
        clear_credentials(
            [
                "claudeCodeOAuthToken",
                "cursorApiKey",
                "codexApiKey",
            ]
        )
        print(f"Cleared credentials in {get_config_path()}")
        return

    from planner_ai.app import PlannerApp

    PlannerApp().run()


if __name__ == "__main__":
    main()
