"""Custom errors for serial verification workflow."""


class SerialVerificationError(RuntimeError):
    """Base error for operational failures in the verification flow."""


class ADBCommandError(SerialVerificationError):
    """Raised when an ADB command fails or times out."""
