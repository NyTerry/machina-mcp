"""
Machina MCP Server

Exposes Machina's x402 agent services as MCP tools. Each tool call
automatically handles the x402 payment flow — probe → pay → receive —
so the calling agent never touches crypto directly.

Environment variables:
  MACHINA_WALLET_KEY   Required. Ethereum private key (0x-prefixed or bare hex).
                       The wallet needs a USDC balance on Base mainnet.
  MACHINA_NETWORK      Optional. CAIP-2 network ID.
                       Default: eip155:8453 (Base mainnet)
                       Testnet: eip155:84532 (Base Sepolia)
  MACHINA_BASE_URL     Optional. Override Machina API base URL.
                       Default: https://mach402.dev
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Annotated, Optional

from mcp.server.mcpserver import MCPServer

from .payment import build_payment_client
from . import __version__

# ── Config ─────────────────────────────────────────────────────────────────────
MACHINA_BASE_URL = os.environ.get("MACHINA_BASE_URL", "https://mach402.dev").rstrip("/")
USER_AGENT = f"machina-mcp/{__version__}"

# ── Logging (stderr — stdout is reserved for MCP protocol) ────────────────────
_log_handler = logging.StreamHandler(sys.stderr)
_log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s — %(message)s"))
log = logging.getLogger("machina-mcp")
log.addHandler(_log_handler)
log.setLevel(logging.INFO)

# ── MCP Server ─────────────────────────────────────────────────────────────────
server = MCPServer(
    name="machina-mcp",
    title="Machina Agent Services",
    description=(
        "x402-powered AI agent services: URL extraction, Python security scanning, "
        "email validation, domain intelligence, and PDF processing. "
        "Payments are automatic — just configure your Base wallet key."
    ),
    version="0.1.0",
    website_url="https://mach402.dev",
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_pdf(pdf_path: Optional[str], pdf_base64: Optional[str]) -> bytes:
    """Return PDF bytes from either a local path or base64 string."""
    if pdf_path:
        path = Path(pdf_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")
        return path.read_bytes()
    elif pdf_base64:
        try:
            return base64.b64decode(pdf_base64)
        except Exception as exc:
            raise ValueError(f"Invalid base64 content: {exc}") from exc
    else:
        raise ValueError(
            "Provide either 'pdf_path' (local file path) "
            "or 'pdf_base64' (base64-encoded PDF)."
        )


def _fmt(result: dict) -> str:
    """Pretty-print a result dict as a JSON string for the MCP response."""
    return json.dumps(result, indent=2, ensure_ascii=False)


def _headers(content_type: str = "application/json") -> dict:
    """Default headers with User-Agent for all outbound requests."""
    return {"Content-Type": content_type, "User-Agent": USER_AGENT}


async def _paid_call(tool_name: str, endpoint: str, *,
                     json_body: dict | None = None,
                     raw_body: bytes | None = None,
                     content_type: str = "application/json",
                     timeout: float = 30.0) -> str:
    """Execute a paid Machina API call with x402 payment + logging."""
    log.info("tool=%s endpoint=%s", tool_name, endpoint)
    t0 = time.monotonic()
    try:
        pc = build_payment_client()
    except RuntimeError as exc:
        log.error("tool=%s config_error: %s", tool_name, exc)
        return f"Configuration error: {exc}"
    from x402.http.clients import x402HttpxClient
    try:
        async with x402HttpxClient(pc, headers={"User-Agent": USER_AGENT}) as http:
            kwargs = {
                "headers": {"Content-Type": content_type, "User-Agent": USER_AGENT},
                "timeout": timeout,
            }
            if raw_body is not None:
                kwargs["content"] = raw_body
            else:
                kwargs["json"] = json_body
            resp = await http.post(f"{MACHINA_BASE_URL}{endpoint}", **kwargs)
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        if resp.status_code == 200:
            log.info("tool=%s status=200 elapsed=%sms", tool_name, elapsed)
            return _fmt(resp.json())
        log.warning("tool=%s status=%s elapsed=%sms body=%s",
                    tool_name, resp.status_code, elapsed, resp.text[:200])
        return f"Error: HTTP {resp.status_code}: {resp.text[:300]}"
    except Exception as exc:
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        log.error("tool=%s error=%s elapsed=%sms: %s",
                  tool_name, type(exc).__name__, elapsed, exc)
        return f"Error: {type(exc).__name__}: {exc}"


# ── Tools ──────────────────────────────────────────────────────────────────────

@server.tool(
    description=(
        "Fetch a URL and return its full content as clean Markdown. "
        "Useful for reading web pages, articles, blog posts, and documentation. "
        "Returns title, word count, and the full text as Markdown. "
        "Cost: $0.005 per call."
    )
)
async def url_extract(url: str) -> str:
    """Fetch a URL and return its content as Markdown."""
    if not url.strip():
        return "Error: 'url' cannot be empty"
    return await _paid_call("url_extract", "/url/extract",
                            json_body={"url": url}, timeout=30.0)


@server.tool(
    description=(
        "Scan Python source code for security vulnerabilities. "
        "Detects: hardcoded secrets/API keys, eval/exec misuse, shell injection, "
        "insecure SSL/TLS, dangerous deserialization (pickle, yaml.load), "
        "path traversal, and CVE-affected dependency versions. "
        "Returns structured findings with severity (critical/high/medium/low) "
        "and line numbers. Handles up to 10,000 lines. "
        "Cost: $0.020 per call."
    )
)
async def scan_python(
    code: str,
    filename: str = "upload.py",
) -> str:
    """Scan Python code for security vulnerabilities."""
    if not code.strip():
        return "Error: 'code' cannot be empty"
    return await _paid_call("scan_python", "/scan/python",
                            json_body={"code": code, "filename": filename},
                            timeout=60.0)


@server.tool(
    description=(
        "Validate a single email address. "
        "Checks: syntax/format, MX record existence, disposable email "
        "provider detection, and role-address detection (noreply@, info@, etc.). "
        "With smtp_probe=True, attempts an SMTP connection to verify the mailbox "
        "exists (best-effort — some servers block probes). "
        "Returns a deliverability score and per-check results. "
        "Cost: $0.007 per call."
    )
)
async def validate_email(
    email: str,
    smtp_probe: bool = True,
) -> str:
    """Validate a single email address."""
    if not email.strip():
        return "Error: 'email' cannot be empty"
    return await _paid_call("validate_email", "/validate/email",
                            json_body={"email": email, "smtp_probe": smtp_probe},
                            timeout=20.0)


@server.tool(
    description=(
        "Validate up to 100 email addresses in a single call. "
        "Same checks as validate_email (syntax, MX, disposable, role-address) "
        "but optimised for batch processing. SMTP probing is off by default "
        "to keep latency low. Returns per-address results plus a summary. "
        "Cost: $0.500 per call (up to 100 emails, ~$0.005/email)."
    )
)
async def validate_email_bulk(
    emails: list[str],
    smtp_probe: bool = False,
) -> str:
    """Validate up to 100 email addresses in one call."""
    if not emails:
        return "Error: 'emails' list cannot be empty"
    if len(emails) > 100:
        return "Error: maximum 100 emails per bulk call"
    return await _paid_call("validate_email_bulk", "/validate/email/bulk",
                            json_body={"emails": emails, "smtp_probe": smtp_probe},
                            timeout=120.0)


@server.tool(
    description=(
        "Get comprehensive intelligence on a domain name. "
        "Returns: DNS records (A/MX/NS/TXT/SPF/DMARC), WHOIS registration "
        "data and domain age, SSL certificate details and expiry, HTTP response "
        "headers, tech stack detection (CMS, server, CDN, etc.), and email "
        "infrastructure analysis. "
        "Cost: $0.050 per call."
    )
)
async def domain_intel(domain: str) -> str:
    """Get DNS, WHOIS, SSL, and tech stack intelligence for a domain."""
    if not domain.strip():
        return "Error: 'domain' cannot be empty"
    return await _paid_call("domain_intel", "/domain/intel",
                            json_body={"domain": domain}, timeout=30.0)


@server.tool(
    description=(
        "FREE pre-check for a PDF file. Returns page count, file size, and "
        "metadata (title, author, creator, creation date) without extracting any text. "
        "Use this before pdf_extract or pdf_extract_large to check the page count "
        "and decide which extractor to use. No payment required. "
        "Cost: FREE."
    )
)
async def pdf_inspect(
    pdf_path: Optional[str] = None,
    pdf_base64: Optional[str] = None,
) -> str:
    """Check a PDF's page count and metadata for free."""
    log.info("tool=pdf_inspect endpoint=/pdf/inspect")
    t0 = time.monotonic()
    try:
        pdf_bytes = _load_pdf(pdf_path, pdf_base64)
    except (FileNotFoundError, ValueError) as exc:
        log.error("tool=pdf_inspect input_error: %s", exc)
        return f"Error: {exc}"
    import httpx
    try:
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as http:
            resp = await http.post(
                f"{MACHINA_BASE_URL}/pdf/inspect",
                content=pdf_bytes,
                headers=_headers("application/pdf"),
                timeout=30.0,
            )
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        if resp.status_code == 200:
            log.info("tool=pdf_inspect status=200 elapsed=%sms", elapsed)
            return _fmt(resp.json())
        log.warning("tool=pdf_inspect status=%s elapsed=%sms", resp.status_code, elapsed)
        return f"Error: HTTP {resp.status_code}: {resp.text[:300]}"
    except Exception as exc:
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        log.error("tool=pdf_inspect error=%s elapsed=%sms: %s",
                  type(exc).__name__, elapsed, exc)
        return f"Error: {type(exc).__name__}: {exc}"


@server.tool(
    description=(
        "Extract text from a PDF (up to 50 pages) and return it as Markdown. "
        "Preserves headings, tables, lists, and document structure. "
        "Call pdf_inspect first to verify page count — use pdf_extract_large "
        "for documents over 50 pages. "
        "Cost: $0.050 per call."
    )
)
async def pdf_extract(
    pdf_path: Optional[str] = None,
    pdf_base64: Optional[str] = None,
) -> str:
    """Extract text from a PDF (≤50 pages) as Markdown."""
    try:
        pdf_bytes = _load_pdf(pdf_path, pdf_base64)
    except (FileNotFoundError, ValueError) as exc:
        return f"Error: {exc}"
    return await _paid_call("pdf_extract", "/pdf/extract",
                            raw_body=pdf_bytes, content_type="application/pdf",
                            timeout=120.0)


@server.tool(
    description=(
        "Extract text from a large PDF (up to 200 pages) and return it as Markdown. "
        "For documents over 50 pages. Call pdf_inspect first to check the page count. "
        "For documents ≤50 pages, prefer pdf_extract (cheaper). "
        "Cost: $0.180 per call."
    )
)
async def pdf_extract_large(
    pdf_path: Optional[str] = None,
    pdf_base64: Optional[str] = None,
) -> str:
    """Extract text from a large PDF (≤200 pages) as Markdown."""
    try:
        pdf_bytes = _load_pdf(pdf_path, pdf_base64)
    except (FileNotFoundError, ValueError) as exc:
        return f"Error: {exc}"
    return await _paid_call("pdf_extract_large", "/pdf/extract/large",
                            raw_body=pdf_bytes, content_type="application/pdf",
                            timeout=120.0)


# ── Entry point ────────────────────────────────────────────────────────────────

async def _main() -> None:
    wallet_key = os.environ.get("MACHINA_WALLET_KEY", "")
    if not wallet_key:
        print(
            "⚠️  MACHINA_WALLET_KEY is not set.\n"
            "    Set your Base wallet private key before starting:\n\n"
            "      export MACHINA_WALLET_KEY=0xYOUR_PRIVATE_KEY\n\n"
            "    Your wallet needs USDC on Base mainnet to pay for API calls.\n"
            "    See: https://mach402.dev/docs/buyer-guide\n",
            file=sys.stderr,
        )
    await server.run_stdio_async()


def run() -> None:
    """Console-script entry point."""
    asyncio.run(_main())
