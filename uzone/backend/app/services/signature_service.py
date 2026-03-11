"""Signature provider abstraction."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SignatureResult:
    provider: str
    external_id: str | None
    status: str


class SignatureProvider:
    name: str

    def sign(self, *, document_id: str, signer_name: str) -> SignatureResult:
        raise NotImplementedError


class InternalSignatureProvider(SignatureProvider):
    name = "internal"

    def sign(self, *, document_id: str, signer_name: str) -> SignatureResult:
        return SignatureResult(
            provider=self.name,
            external_id=f"internal_{document_id}",
            status="signed",
        )

