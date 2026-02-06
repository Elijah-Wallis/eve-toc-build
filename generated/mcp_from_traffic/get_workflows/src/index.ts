import axios from "axios";
import axiosRetry from "axios-retry";
import dotenv from "dotenv";
import FormData from "form-data";
import { z } from "zod";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

dotenv.config();
void FormData;

const BASE_URL = process.env.BASE_URL ?? "https://elijah-wallis.app.n8n.cloud";
const client = axios.create({ timeout: 30000, validateStatus: () => true });
axiosRetry(client, {
  retries: 3,
  retryDelay: axiosRetry.exponentialDelay,
  retryCondition: (error) => axiosRetry.isNetworkOrIdempotentRequestError(error) || (error.response?.status ?? 0) >= 500,
});

const server = new McpServer({
  name: "get_workflows",
  version: "1.0.0",
});

server.tool(
  "get_workflows",
  "Get workflows via GET /api/v1/workflows.",
{
},
  async (args) => {
  const headers: Record<string, string> = {};
  if (process.env.N8N_API_KEY) headers["X-N8N-API-KEY"] = process.env.N8N_API_KEY as string;
    const url = `${BASE_URL}/api/v1/workflows`;
    const response = await client.request({
      method: "GET",
      url,
      headers,
      params: undefined,
      data: undefined,
    });

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({ status: response.status, data: response.data, headers: response.headers }),
        },
      ],
    };
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
