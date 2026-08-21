from __future__ import annotations

import sys

from planner_ai.config import clear_credentials, get_config_path


def main() -> None:
    if "--reset-auth" in sys.argv:
        from planner_ai.providers.codex_auth import logout_codex_sync

        logout_error: Exception | None = None
        try:
            logout_codex_sync()
        except Exception as err:
            logout_error = err
        clear_credentials(
            [
                "claudeCodeOAuthToken",
                "cursorApiKey",
                "codexApiKey",
            ]
        )
        print(f"Cleared credentials in {get_config_path()}")
        if logout_error is not None:
            print(
                f"Warning: unable to clear the shared Codex session: {logout_error}",
                file=sys.stderr,
            )
        return

    from planner_ai.app import PlannerApp

    PlannerApp().run()


if __name__ == "__main__":
    main()
