# Skill Metadata Spec

Each skill declares metadata for orchestration and risk controls.

```json
{
  "name": "n8n.trigger",
  "inputs": ["workflow", "data"],
  "outputs": ["response"],
  "risk_class": "B",
  "required_mcp": ["n8n-mcp"],
  "depends_on": []
}
```

## Fields
- `name`: unique skill name
- `inputs`: required input fields
- `outputs`: produced fields
- `risk_class`: C/B/A
- `required_mcp`: MCP servers needed
- `depends_on`: skill dependencies
