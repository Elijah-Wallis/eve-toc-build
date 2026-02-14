# Agent Codebase Bundle (for refactor/debug)

I created a reproducible archive of the current agent codebase (non-sensitive source files only) at:

- `/Users/elijah/Documents/New project/artifacts/eve_agent_codebase_full.tar.gz`

Manifest:

- SHA-256: `b20d360c2f60b8262d40d14943885e6a4ac611ec6b070c9659ca5bf79c41d25f`
- Included file list: `/Users/elijah/Documents/New project/artifacts/eve_agent_codebase_full_filelist.txt`

Excluded directories: `.git`, `.venv`, `.pytest_cache`, `__pycache__`, `.run`, `data`, `logs`, `node_modules`, and `dist`.

To extract:

```bash
mkdir -p /tmp/eve-agent-codebase
tar -xzf '/Users/elijah/Documents/New project/artifacts/eve_agent_codebase_full.tar.gz' -C /tmp/eve-agent-codebase
```

To rebuild the bundle in the future:

```bash
cd '/Users/elijah/Documents/New project'
find app src scripts tests docs tools dashboard apps -type d \
  \( -name .venv -o -name .git -o -name __pycache__ -o -name node_modules -o -name data -o -name logs -o -name .run -o -name .pytest_cache -o -name .idea -o -name .vscode \) -prune \
  -o -type f \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' -o -name '*.html' -o -name '*.css' -o -name '*.md' -o -name '*.toml' -o -name '*.yaml' -o -name '*.yml' -o -name '*.json' -o -name '*.cfg' -o -name '*.ini' -o -name '*.sh' \) -print > /tmp/eve_agent_code_files_full.txt
printf "README.md\npyproject.toml\nMakefile\n" >> /tmp/eve_agent_code_files_full.txt
tar -czf artifacts/eve_agent_codebase_full.tar.gz -T /tmp/eve_agent_code_files_full.txt
sha256sum artifacts/eve_agent_codebase_full.tar.gz > artifacts/eve_agent_codebase_full_manifest.txt
```

