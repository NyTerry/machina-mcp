# machina-mcp

**Machina as an MCP server.** Use Machina's x402-powered agent services directly from Claude Desktop, Cursor, or any MCP-compatible AI host — no x402 integration required.

Payments happen automatically on every tool call. Configure once, pay per use.

## Tools

| Tool | What it does | Cost |
|---|---|---|
| `url_extract` | Fetch any URL → clean Markdown | $0.005 |
| `scan_python` | Scan Python code for security vulnerabilities | $0.020 |
| `validate_email` | Validate a single email (syntax, MX, SMTP) | $0.007 |
| `validate_email_bulk` | Validate up to 100 emails | $0.500 |
| `domain_intel` | DNS, WHOIS, SSL, tech stack for a domain | $0.050 |
| `pdf_inspect` | PDF page count + metadata | **FREE** |
| `pdf_extract` | PDF → Markdown (≤50 pages) | $0.050 |
| `pdf_extract_large` | PDF → Markdown (≤200 pages) | $0.180 |

Payments are in USDC on [Base](https://base.org) (Coinbase's L2). Gas fees are fractions of a cent.

---

## Quick Start

### 1. Install

```bash
pip install machina-mcp
```

### 2. Get a wallet + fund it

You need an Ethereum wallet with a small USDC balance on Base mainnet.

**Option A — New wallet (easiest):**
```bash
python -c "from eth_account import Account; a = Account.create(); print('Address:', a.address); print('Key:', a.key.hex())"
```
Copy the address and send it $1–5 USDC on Base via [Coinbase](https://coinbase.com) or [bridge.base.org](https://bridge.base.org).

**Option B — Existing wallet:**
Export your private key from MetaMask: Account Details → Export Private Key.

### 3. Set your key

```bash
export MACHINA_WALLET_KEY=0xYOUR_PRIVATE_KEY
```

### 4. Add to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "machina": {
      "command": "machina-mcp",
      "env": {
        "MACHINA_WALLET_KEY": "0xYOUR_PRIVATE_KEY"
      }
    }
  }
}
```

Restart Claude Desktop. The 8 Machina tools will appear automatically.

---

## Usage Examples

Once connected, ask Claude:

- *"Extract the content from https://example.com"* → uses `url_extract`
- *"Scan this Python code for security issues: [paste code]"* → uses `scan_python`
- *"Check if john@example.com is a real email"* → uses `validate_email`
- *"Get DNS and WHOIS info for openai.com"* → uses `domain_intel`
- *"How many pages is this PDF?"* → uses `pdf_inspect` (free)
- *"Extract text from report.pdf"* → uses `pdf_extract`

---

## Configuration

| Env var | Required | Default | Description |
|---|---|---|---|
| `MACHINA_WALLET_KEY` | ✅ | — | Ethereum private key (hex, 0x-prefixed) |
| `MACHINA_NETWORK` | ❌ | `eip155:8453` | CAIP-2 network ID (Base mainnet) |
| `MACHINA_BASE_URL` | ❌ | `https://mach402.dev` | Machina API base URL |

**Testnet mode** (free, mock payments):
```bash
export MACHINA_NETWORK=eip155:84532
export MACHINA_BASE_URL=https://mach402.dev  # testnet endpoints at same URL when TESTNET_MODE=true
```

---

## How payments work

1. Your agent calls a Machina MCP tool (e.g. `url_extract`)
2. The MCP server sends the request to `mach402.dev`
3. Machina responds with a 402 Payment Required + exact USDC amount
4. The MCP server signs and sends the x402 payment automatically using your wallet key
5. Machina verifies payment on-chain and returns the result
6. The result is passed back to your agent

The agent never sees any of this — it just calls a tool and gets a result.

---

## Running standalone (for testing)

```bash
# Test with MCP Inspector
npx @modelcontextprotocol/inspector machina-mcp

# Or run directly
export MACHINA_WALLET_KEY=0x...
machina-mcp
```

---

## Pricing

Machina charges per call in USDC on Base mainnet. Payments are settled on-chain via [Coinbase CDP](https://docs.cdp.coinbase.com/x402/). There are no subscriptions, no minimums, no monthly fees.

A $5 USDC balance covers ~1,000 URL extractions or ~250 Python code scans.

---

## Links

- **API docs:** https://mach402.dev/docs
- **Buyer guide:** https://mach402.dev/docs/buyer-guide
- **Source:** https://github.com/NyTerry/machina-mcp
- **Issues:** https://github.com/NyTerry/machina-mcp/issues

---

## License

MIT

<!-- mcp-name: io.github.NyTerry/machina-mcp -->
