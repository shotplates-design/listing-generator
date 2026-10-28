"""Errors from a vision call. These never become guessed listing facts."""


class VisionError(RuntimeError):
    """The photos could not be read. The form should stay unchanged."""
