# Security

GlassBox is a research tool that runs simulated paper trading. It holds no real money and places no real orders.

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Use GitHub's private reporting instead:
**Security tab → "Report a vulnerability"** on this repository. You'll get a reply as soon as the maintainer sees it.

Useful details: what you found, the steps to reproduce it, and what you think the impact is. Please don't test against
other users' accounts or run anything that could degrade the live site.

## How changes are protected

- `main` only accepts changes through a pull request that the maintainer has approved (code owners review).
- The `ci` checks (backend tests + dependency vulnerability scan, frontend type-check) must pass first.
- Force-pushes to `main` and deleting it are blocked.
- Deployment credentials are never stored in this repository: the deploy workflow uses short-lived keyless tokens
  and only runs for the maintainer's own pushes to `main`, never for pull requests or forks.
