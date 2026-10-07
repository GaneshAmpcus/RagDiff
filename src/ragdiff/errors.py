class RagDiffError(Exception):
    """Base exception for errors raised by RagDiff."""


class ConfigError(RagDiffError):
    """The evaluation configuration is invalid or cannot be loaded."""


class AppLoadError(RagDiffError):
    """The configured application entrypoint cannot be loaded."""


class IntegrationError(RagDiffError):
    """An optional integration is unavailable or failed."""


class StorageError(RagDiffError):
    """A storage operation failed."""
