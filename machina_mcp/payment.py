"""
Machina x402 payment client.

Wraps the x402 Python SDK with a standard eth_account private key —
no CDP, no MetaMask, no browser. Just an Ethereum private key on Base.
"""

from __future__ import annotations

import os


MACHINA_NETWORK = os.environ.get("MACHINA_NETWORK", "eip155:8453")
MACHINA_WALLET_KEY = os.environ.get("MACHINA_WALLET_KEY", "")


def build_payment_client(wallet_key: str | None = None, network: str | None = None):
    """
    Create an x402 payment client from a raw private key.

    Args:
        wallet_key: Hex private key (0x-prefixed or bare). Falls back to
                    MACHINA_WALLET_KEY env var.
        network:    CAIP-2 network ID. Falls back to MACHINA_NETWORK env var,
                    which defaults to "eip155:8453" (Base mainnet).

    Returns:
        x402Client ready for use with x402HttpxClient.

    Raises:
        RuntimeError: If no wallet key is configured.
    """
    key = wallet_key or MACHINA_WALLET_KEY
    net = network or MACHINA_NETWORK

    if not key:
        raise RuntimeError(
            "No wallet key configured.\n"
            "Set the MACHINA_WALLET_KEY environment variable to your Base "
            "wallet private key (0x-prefixed):\n\n"
            "  export MACHINA_WALLET_KEY=0xYOUR_PRIVATE_KEY\n\n"
            "Your wallet needs a small USDC balance on Base (mainnet) to pay "
            "for API calls. Fund it at https://mach402.dev/docs/buyer-guide"
        )

    # Normalise key format
    if not key.startswith("0x"):
        key = f"0x{key}"

    from eth_account import Account
    from x402 import x402Client
    from x402.mechanisms.evm import EthAccountSigner
    from x402.mechanisms.evm.exact import ExactEvmScheme

    account = Account.from_key(key)
    signer = EthAccountSigner(account)
    client = x402Client()
    client.register(net, ExactEvmScheme(signer))
    return client
