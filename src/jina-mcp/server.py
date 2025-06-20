import asyncio
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List
from urllib.parse import urlparse

import httpx
import tiktoken
from pydantic import AnyUrl, BaseModel, Field

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
import mcp.types as types

server = Server("jina-markdown-wrapper")

@dataclass
class MarkdownResource:
    markdown: str
    token_count: int
    content_hash: str
    fetched_at: datetime

@dataclass
class MarkdownMeta:
    url: str
    uri: str
    token_count: int
    content_hash: str
    fetched_at: str
    has_changed: bool

class URLRequest(BaseModel):
    url: AnyUrl = Field(..., description="URL to fetch as Markdown from r.jina.ai")

resource_store: Dict[str, MarkdownResource] = {}

def normalize_uri(url: str) -> str:
    parsed = urlparse(url)
    safe_path = parsed.path.rstrip("/") or "_"
    safe_key = (parsed.netloc + safe_path).replace("/", "_").replace(".", "_")
    return f"jinamd://{safe_key}"

def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def estimate_tokens(text: str, model: str = "gpt-4") -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

async def fetch_jina_markdown(url: str) -> str:
    jina_url = f"https://r.jina.ai/{url}"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(jina_url, follow_redirects=True)
        response.raise_for_status()
        return response.text

async def fetch_and_store_url(url: str) -> List[types.TextContent]:
    markdown = await fetch_jina_markdown(url)
    content_hash = compute_hash(markdown)
    token_count = estimate_tokens(markdown)
    now = datetime.utcnow()
    uri = normalize_uri(url)

    old = resource_store.get(uri)
    has_changed = old.content_hash != content_hash if old else True

    resource_store[uri] = MarkdownResource(
        markdown=markdown,
        token_count=token_count,
        content_hash=content_hash,
        fetched_at=now
    )

    meta = MarkdownMeta(
        url=url,
        uri=uri,
        token_count=token_count,
        content_hash=content_hash,
        fetched_at=now.isoformat(),
        has_changed=has_changed
    )

    return [
        types.TextContent(
            type="text",
            text=markdown,
            _meta=asdict(meta)
        )
    ]

@server.list_tools()
async def list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="fetch_markdown",
            description="Fetch a single web page as Markdown.",
            inputSchema=URLRequest.model_json_schema(),
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict | None) -> List[types.TextContent]:
    if not arguments:
        raise ValueError("Missing arguments")
    if name != "fetch_markdown":
        raise ValueError(f"Unknown tool: {name}")
    args = URLRequest(**arguments)
    return await fetch_and_store_url(str(args.url))

@server.list_resources()
async def list_resources() -> List[types.Resource]:
    return [
        types.Resource(
            uri=types.AnyUrl(uri),
            name=f"Jina Markdown: {uri}",
            description=f"Fetched at {res.fetched_at.isoformat()} UTC, ~{res.token_count} tokens",
            mimeType="text/markdown",
        )
        for uri, res in resource_store.items()
    ]

@server.read_resource()
async def read_resource(uri: types.AnyUrl) -> str:
    if uri.scheme != "jinamd":
        raise ValueError(f"Unsupported URI scheme: {uri.scheme}")
    if str(uri) not in resource_store:
        raise ValueError(f"Resource not found: {uri}")

    res = resource_store[str(uri)]
    footer = (
        f"\n\n---\n"
        f"_Estimated tokens_: {res.token_count}\n"
        f"_Content hash_: `{res.content_hash[:12]}...`\n"
        f"_Fetched at_: {res.fetched_at.isoformat()} UTC"
    )
    return res.markdown + footer

async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="jina-markdown-wrapper",
                server_version="0.4.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
