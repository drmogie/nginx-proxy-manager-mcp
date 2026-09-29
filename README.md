# Nginx Proxy Manager MCP

![Version](https://img.shields.io/badge/version-2026.09.28.01-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A small tool that lets Claude read and change
[Nginx Proxy Manager](https://nginxproxymanager.com/) through its API.

It runs on your own computer. Your password stays on your computer.

## What Claude can do with it

- Check that NPM is up (npm_status).
- List, look at, add, change, turn on, turn off, and delete:
  proxy hosts, redirection hosts, 404 hosts, and streams (npm_hosts).
- List and delete certificates. List access lists (npm_hosts).
- See the newest changes made in NPM (npm_audit_log).
- Anything else in the NPM API, such as making or renewing a
  certificate, access lists, users, and settings (npm_call).

When Claude changes a host, the tool reads the current one first and merges
your change. Nothing else on that host is lost.

## Safety

Every call has a safety level.

- **read**: runs right away.
- **change**: adding, editing, turning on or off. It does not run until
  Claude asks you and sets `confirm`. Claude shows you what will be sent first.
- **destructive**: deleting anything, and any change to users or settings.
  It also needs an exact phrase typed back, like `delete proxy-hosts 5`.

Other protections:

- Login and token calls are blocked. The tool logs in by itself.
- The password and the login token are never printed.
  They are removed from error messages.
- Paths must start with `/api/`. The tool cannot be pointed at another site.

## Set up

### 1. Make a user for Claude

1. Open the NPM web page (port 81).
2. Go to Users, then Add User.
3. Use a separate user just for this, like `claude@example.com`.
   Then you can turn it off on its own later.
4. Turn OFF two-step login for this user. The tool cannot do the code step.
5. Give it Administrator, or pick the permissions you want it to have.

**Do not paste the password in a chat.** Put it only in the config file below.

### 2. Add the tool to Claude

Open the Claude desktop app settings and find the MCP servers config file.
Add the block from `claude_desktop_config.example.json`.
Change the address, email, and password.

- `NPM_URL`: your NPM admin address, like `http://172.16.90.75:81`
- `NPM_EMAIL`: the login email of the user you made
- `NPM_PASSWORD`: that user's password

That file now holds a secret. Do not share it. Do not put it on GitHub.

The example uses `uvx`. If you do not have it, use Python instead:

```
pip install D:\GitHub-Projects\nginx-proxy-manager-mcp
```

Then use `"command": "nginx-proxy-manager-mcp"` and no args.

Restart the Claude desktop app.

### 3. Try it

Ask Claude: "Show my Nginx Proxy Manager proxy hosts."

## Other settings

- `NPM_VERIFY_TLS=false`: for an https address with a self-signed certificate.

## Good to know

- For a new outside address, use its own subdomain as a proxy host.
  Custom Locations under an existing domain were unreliable on this NPM.
- The NPM API is not officially documented. This tool follows the
  schema in the NPM GitHub repo. If a new NPM version changes it, use
  `npm_call` and tell me what broke.
- Not tested against a real NPM when first built. It was tested against a
  fake server.
