# create_webhook

MCP tool generated from captured API traffic.

## Tool
- Name: `create_webhook`
- Description: Create webhook via POST /webhook/{webhook_id}.
- Source endpoint: `POST https://elijah-wallis.app.n8n.cloud/webhook/{webhook_id}`

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
