# create_task_runs

MCP tool generated from captured API traffic.

## Tool
- Name: `create_task_runs`
- Description: Create task runs via POST /rest/v1/task_runs.
- Source endpoint: `POST https://gfazwukgloydihkejrhw.supabase.co/rest/v1/task_runs`

## Setup
```bash
npm install
npm run build
```

## Environment
Copy `.env.example` to `.env` and set values:
```bash
cp .env.example .env
```

## Run MCP Server
```bash
node dist/index.js
```

## Verify with Python Harness
```bash
python3 -m pip install mcp
python3 client.py
```
