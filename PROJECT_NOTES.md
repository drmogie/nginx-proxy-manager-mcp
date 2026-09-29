# Nginx Proxy Manager MCP - project notes

## 2026-09-28: first build (2026.09.28.01)

- Ask: Mogie wondered if an MCP was needed to configure Nginx Proxy Manager
  (NPM) at 172.16.90.75:81. The session shell could not reach the LAN
  ("Connection blocked by network allowlist"), so a local MCP that runs on
  Mogie's PC (same way as technitium-dns and home-assistant) is the fix.
- Copied the technitium-mcp design: Python, `mcp>=1.2,<2`, run through
  `uvx`, settings from environment only, read / change / destructive tiers.
- Auth: NPM has no long-lived API keys. The tool logs in with email and
  password (POST /api/tokens), caches the token, and logs in again on a 401.
  A user with two-step login on will not work.
- npm_hosts update: GET current, keep only the fields NPM accepts on write,
  overlay the change, PUT. NPM rejects read-only fields (id, owner,
  created_on, ...). The field lists come from the NPM schema; re-check them
  if a new NPM version rejects a write.
- Blocked on purpose: /api/tokens.
- Tested with a fake NPM server (tests/test_server.py, 44 checks) and a
  stdio start check. NOT tested against real NPM or on Windows.
- Reverse-proxy lesson from the shared GitHub doc: prefer a dedicated
  subdomain over a Custom Location on this NPM.
- GitHub repo: NOT created yet. Waiting on Mogie for the repo name
  (suggested: nginx-proxy-manager-mcp).
