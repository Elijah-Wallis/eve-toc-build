# get_segments

MCP tool generated from captured API traffic.

## Tool
- Name: `get_segments`
- Description: Get segments via GET /rest/v1/segments.
- Source endpoint: `GET https://gfazwukgloydihkejrhw.supabase.co/rest/v1/segments`

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
