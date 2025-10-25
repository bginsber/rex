"""Signer port interface for cryptographic signing (future use)."""

from typing import Protocol


class SignerPort(Protocol):
    """Port interface for cryptographic signing operations.

    Future use for digital signatures on audit entries and manifests.

    Side effects: None (pure computation).
    """

    def sign(self, data: bytes) -> bytes:
        """Sign data.

        Args:
            data: Data to sign

        Returns:
            Signature bytes
        """
        ...

    def verify(self, data: bytes, signature: bytes) -> bool:
        """Verify signature.

        Args:
            data: Original data
            signature: Signature to verify

        Returns:
            True if signature is valid
        """
        ...
