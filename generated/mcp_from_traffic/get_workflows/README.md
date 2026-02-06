# get_workflows

MCP tool generated from captured API traffic.

## Tool
- Name: `get_workflows`
- Description: Get workflows via GET /api/v1/workflows.
- Source endpoint: `GET https://elijah-wallis.app.n8n.cloud/api/v1/workflows`

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
