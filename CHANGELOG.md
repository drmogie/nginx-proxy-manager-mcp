# Changelog

## 2026.09.28.01

- First release.
- Tools: npm_status, npm_hosts, npm_call, npm_audit_log.
- npm_hosts handles proxy hosts, redirection hosts, 404 hosts and streams
  (list, get, create, update, delete, enable, disable), and lists
  certificates and access lists.
- Update reads the current item and merges, and strips fields NPM rejects.
- Safety levels: read runs at once. Changes need confirm. Deleting, users
  and settings also need an exact phrase typed back.
- Logs in by itself and logs in again when the token runs out.
- Password and token are removed from anything returned.
- Tested against a fake NPM server. Not yet tested on a real one.
