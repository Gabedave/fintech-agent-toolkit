# Adopt the toolkit

The plugin supplies workflow guidance. An adopting repository supplies facts about its own product and safe proof path.

1. Write a concise root `AGENTS.md`: product boundary, source-of-truth documents, authorization rules, relevant environments, and how to discover related repositories.
2. Define a repository-owned `verify-<product>` skill or deterministic script. Map critical features to focused tests and runtime proof, including failure and recovery paths.
3. Add a risk map that connects changed paths to appropriate CI checks. Keep provider credentials and customer data out of fixtures.
4. Enable `fintech-mode` in Codex and try one read-only investigation, one small edit, and one high-risk change in a safe test repository.
5. Review routing and proof gaps before requiring the flow for a team.

The toolkit does not assume a specific host, issue tracker, branch name, deployment platform, payment provider, or repository layout. Repository instructions take precedence when they set a narrower authorization or safety boundary.
