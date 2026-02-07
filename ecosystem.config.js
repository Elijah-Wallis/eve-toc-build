module.exports = {
  apps: [
    {
      name: "openclaw-runtime",
      script: "python3",
      args: "-m src.runtime.orchestrator_runtime",
      env: {
        NODE_ENV: "production",
        OPENCLAW_CONFIG_PATH: "./openclaw.json",
        PATH: "/opt/homebrew/opt/python@3.14/bin:/opt/homebrew/bin:/usr/bin:/bin"
      },
      autorestart: true,
      max_memory_restart: "512M"
    },
    {
      name: "openclaw-telegram",
      script: "python3",
      args: "-m src.runtime.telegram_listener",
      env: {
        NODE_ENV: "production",
        OPENCLAW_CONFIG_PATH: "./openclaw.json",
        PATH: "/opt/homebrew/opt/python@3.14/bin:/opt/homebrew/bin:/usr/bin:/bin"
      },
      autorestart: true,
      max_memory_restart: "256M"
    },
    {
      name: "openclaw",
      script: "openclaw",
      args: "gateway start",
      env: {
        NODE_ENV: "production",
        OPENCLAW_CONFIG_PATH: "./openclaw.json",
        PATH: "/opt/homebrew/opt/python@3.14/bin:/opt/homebrew/bin:/usr/bin:/bin"
      },
      autorestart: true,
      max_memory_restart: "1G"
    },
    {
      name: "retell-mcp",
      script: "python3",
      args: "-m mcp_servers.retell_mcp.server",
      env: {
        NODE_ENV: "production",
        OPENCLAW_CONFIG_PATH: "./openclaw.json",
        PATH: "/opt/homebrew/opt/python@3.14/bin:/opt/homebrew/bin:/usr/bin:/bin"
      },
      autorestart: true,
      max_memory_restart: "256M"
    },
    {
      name: "twilio-mcp",
      script: "python3",
      args: "-m mcp_servers.twilio_mcp.server",
      env: {
        NODE_ENV: "production",
        OPENCLAW_CONFIG_PATH: "./openclaw.json",
        PATH: "/opt/homebrew/opt/python@3.14/bin:/opt/homebrew/bin:/usr/bin:/bin"
      },
      autorestart: true,
      max_memory_restart: "256M"
    },
    {
      name: "intelligence-mcp",
      script: "python3",
      args: "-m mcp_servers.intelligence_mcp.server",
      env: {
        NODE_ENV: "production",
        OPENCLAW_CONFIG_PATH: "./openclaw.json",
        PATH: "/opt/homebrew/opt/python@3.14/bin:/opt/homebrew/bin:/usr/bin:/bin"
      },
      autorestart: true,
      max_memory_restart: "256M"
    }
  ]
};
