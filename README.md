# Jina AI MCP Server (Basic)

This is a lightweight MCP server that fetches and serves Markdown versions of web pages using [`r.jina.ai`](https://r.jina.ai). It enables LLMs to access clean, token-aware web content with minimal overhead.

Could also use the existing ```fetch``` mcp, but where's the fun in that!?

### Features

- Fetch any URL as Markdown
- Auto-hashes, tokenizes, and caches content
- Assigns stable URIs for resource lookup

### Usage

To test locally:

```bash
npx @modelcontextprotocol/inspector uv run src/jina-mcp/server.py
```

Integrate with an mcp client for LLM use. e.g. claude, cursor, custom.

### To Do

- Add support for batch fetching in parallel
- Deploy