"""User-facing exception types for ``buildc`` boundaries."""


class CliInputError(ValueError):
    """A user-supplied CLI input cannot be loaded or resolved."""
