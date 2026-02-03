module.exports = {
  apps: [
    {
      name: "n8n",
      script: "n8n",
      args: "start",
      env: {
        NODE_ENV: "production",
        N8N_PORT: "5678",
        N8N_MCP_ENABLED: "true"
      },
      autorestart: true,
      max_memory_restart: "1G"
    },
    {
      name: "openclaw",
      script: "openclaw",
      args: "gateway start",
      env: {
        NODE_ENV: "production",
        OPENCLAW_CONFIG_PATH: "./openclaw.json"
      },
      autorestart: true,
      max_memory_restart: "1G"
    }
  ]
};
