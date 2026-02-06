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
  name: "create_resource",
  version: "1.0.0",
});

server.tool(
  "create_resource",
  "Create resource via POST /{id_id}.",
{
  id_id: z.string(),
},
  async (args) => {
  const headers: Record<string, string> = {};
    const url = `${BASE_URL}/${args.id_id}`;
    const response = await client.request({
      method: "POST",
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
