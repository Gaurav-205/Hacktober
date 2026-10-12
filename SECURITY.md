# Security policy

Munim handles photographs of business papers on the user's own computer. See `docs/SECURITY_PRIVACY.md` for the threat model.

## Supported versions
Only the latest release on `main`. This is a hackathon-born project maintained on a best-effort basis.

## Reporting a vulnerability
Please report privately:
1. Use GitHub's "Report a vulnerability" (Security Advisories) on this repository, or
2. Email the maintainer at the address on the maintainer's GitHub profile **[fill at submission]**.

Include: affected version or commit, steps to reproduce, impact. Do not include real personal or business documents; use synthetic ones.

Expect an acknowledgement within a few days and a fix or mitigation plan as time allows. We will credit reporters who want credit.

## Scope
In scope: the web app, upload handling, CSRF/host checks, data deletion, logging of content, the optional hosted provider key handling.
Out of scope: attacks requiring full control of the user's computer account; weaknesses in Ollama, Gemma weights, or Google's APIs themselves (report those upstream).

## Known limits (not vulnerabilities)
No login in v1; raw photos are not pixel-redacted; model misreads can pass checks (measured and published).
