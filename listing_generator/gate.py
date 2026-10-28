"""Password gate for the Streamlit app. The listing form stays hidden until it passes."""

from __future__ import annotations

import hmac
import os
from collections.abc import Mapping


class AppSecrets:
    """Reads one secret from Streamlit secrets, then from the environment."""

    @staticmethod
    def read(name: str) -> str:
        return AppSecrets.lookup(name, AppSecrets.mapping(), os.environ)

    @staticmethod
    def lookup(name: str, secrets: Mapping[str, object] | None, environ: Mapping[str, str]) -> str:
        if secrets is not None and name in secrets:
            value = AppSecrets.text(secrets.get(name))
            if value:
                return value
        return AppSecrets.text(environ.get(name) if environ is not None else "")

    @staticmethod
    def text(value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def mapping() -> Mapping[str, object]:
        try:
            import streamlit as st

            loaded = dict(st.secrets)
        except Exception:
            return {}
        if isinstance(loaded, dict):
            return loaded
        return {}


class AppGate:
    """Shared password. Nothing in the listing UI runs until this passes."""

    UNLOCKED = "app_unlocked"
    MISSING = "missing"
    OPEN = "open"
    PROMPT = "prompt"
    UNLOCK = "unlock"
    REJECT = "reject"

    @staticmethod
    def missing_message() -> str:
        return (
            "This app will not start until APP_PASSWORD is set. "
            "Add it to .streamlit/secrets.toml or the APP_PASSWORD environment variable, then restart."
        )

    @staticmethod
    def decide(expected: str, unlocked: bool, attempt: object, submitted: bool) -> str:
        expected = expected.strip() if isinstance(expected, str) else ""
        if not expected:
            return AppGate.MISSING
        if unlocked:
            return AppGate.OPEN
        if not submitted:
            return AppGate.PROMPT
        if AppGate.matches(attempt, expected):
            return AppGate.UNLOCK
        return AppGate.REJECT

    @staticmethod
    def matches(attempt: object, expected: str) -> bool:
        stored = expected.strip() if isinstance(expected, str) else ""
        if not stored:
            return False
        typed = attempt if isinstance(attempt, str) else ""
        try:
            return hmac.compare_digest(typed, stored)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def block_until_unlocked() -> None:
        import streamlit as st

        expected = AppSecrets.read("APP_PASSWORD")
        unlocked = st.session_state.get(AppGate.UNLOCKED) is True
        attempt = ""
        submitted = False
        if expected and not unlocked:
            st.markdown("**Listing Generator** is private. Enter the password to continue.")
            with st.form("app-password"):
                attempt = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Continue")
        decision = AppGate.decide(expected, unlocked, attempt, submitted)
        if decision == AppGate.OPEN:
            return
        if decision == AppGate.MISSING:
            st.error(AppGate.missing_message())
        elif decision == AppGate.UNLOCK:
            st.session_state[AppGate.UNLOCKED] = True
            st.rerun()
        elif decision == AppGate.REJECT:
            st.error("Wrong password.")
        st.stop()
