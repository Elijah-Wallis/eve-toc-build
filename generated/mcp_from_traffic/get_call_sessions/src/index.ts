import axios from "axios";
import axiosRetry from "axios-retry";
import dotenv from "dotenv";
import FormData from "form-data";
import { z } from "zod";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

dotenv.config();
void FormData;

const BASE_URL = process.env.BASE_URL ?? "https://gfazwukgloydihkejrhw.supabase.co";
const client = axios.create({ timeout: 30000, validateStatus: () => true });
axiosRetry(client, {
  retries: 3,
  retryDelay: axiosRetry.exponentialDelay,
  retryCondition: (error) => axiosRetry.isNetworkOrIdempotentRequestError(error) || (error.response?.status ?? 0) >= 500,
});

const server = new McpServer({
  name: "get_call_sessions",
  version: "1.0.0",
});

server.tool(
  "get_call_sessions",
  "Get call sessions via GET /rest/v1/call_sessions.",
{
  select: z.string(),
  created_at: z.string(),
},
  async (args) => {
  const headers: Record<string, string> = {};
  if (process.env.SUPABASE_SERVICE_ROLE_KEY) headers["Authorization"] = `Bearer ${process.env.SUPABASE_SERVICE_ROLE_KEY}`;
  if (process.env.SUPABASE_SERVICE_ROLE_KEY) headers["apikey"] = process.env.SUPABASE_SERVICE_ROLE_KEY as string;
    const url = `${BASE_URL}/rest/v1/call_sessions`;
    const response = await client.request({
      method: "GET",
      url,
      headers,
      params: { "select": args.select, "created_at": args.created_at },
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
