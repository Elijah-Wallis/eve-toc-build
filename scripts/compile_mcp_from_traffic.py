#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlsplit


VAR_SEGMENT_PATTERNS = [
    re.compile(r"^\d+$"),
    re.compile(r"^[0-9a-fA-F]{8,}$"),
    re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F\-]{27,}$"),
    re.compile(r"^[A-Za-z]{2}[A-Za-z0-9]{16,}$"),
    re.compile(r"^[A-Za-z0-9_\-]{20,}$"),
]

RESERVED_ARG_NAMES = {"default", "function", "var", "const", "class", "new"}
SENSITIVE_HEADERS = {"authorization", "apikey", "x-api-key", "x-n8n-api-key"}
SENSITIVE_KEYS = {"token", "secret", "password", "apikey", "api_key", "authorization"}


@dataclass
class EndpointSpec:
    method: str
    base_url: str
    path_template: str
    path_params: List[Tuple[str, str]] = field(default_factory=list)
    query: Dict[str, Any] = field(default_factory=dict)
    body: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    sample_args: Dict[str, Any] = field(default_factory=dict)
    samples: int = 0


def snake_case(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return cleaned or "value"


def singularize(value: str) -> str:
    return value[:-1] if value.endswith("s") and len(value) > 1 else value


def is_variable_segment(segment: str) -> bool:
    if not segment:
        return False
    return any(p.match(segment) for p in VAR_SEGMENT_PATTERNS)


def safe_arg_name(name: str, existing: Iterable[str]) -> str:
    candidate = snake_case(name)
    if candidate in RESERVED_ARG_NAMES:
        candidate = f"{candidate}_arg"
    existing_set = set(existing)
    if candidate not in existing_set:
        return candidate
    i = 2
    while f"{candidate}_{i}" in existing_set:
        i += 1
    return f"{candidate}_{i}"


def make_arg_fields(keys: Iterable[str], used: Iterable[str]) -> List[Tuple[str, str]]:
    fields: List[Tuple[str, str]] = []
    seen = list(used)
    for key in keys:
        arg_name = safe_arg_name(str(key), seen)
        seen.append(arg_name)
        fields.append((arg_name, str(key)))
    return fields


def infer_path_template(path: str) -> Tuple[str, List[Tuple[str, str]]]:
    segments = [s for s in path.split("/") if s]
    template_parts: List[str] = []
    params: List[Tuple[str, str]] = []
    used: List[str] = []

    for idx, segment in enumerate(segments):
        if not is_variable_segment(segment):
            template_parts.append(segment)
            continue
        prev = segments[idx - 1] if idx > 0 else "id"
        base = f"{singularize(snake_case(prev))}_id"
        name = safe_arg_name(base, used)
        used.append(name)
        params.append((name, segment))
        template_parts.append(f"{{{name}}}")

    return "/" + "/".join(template_parts), params


def merge_dict(dest: Dict[str, Any], source: Dict[str, Any]) -> None:
    for key, value in source.items():
        if key not in dest:
            dest[key] = value


def infer_tool_name(method: str, path_template: str) -> str:
    parts = [p for p in path_template.split("/") if p and not (p.startswith("{") and p.endswith("}"))]
    if not parts:
        resource = "resource"
    else:
        resource = snake_case(parts[-1])
        if resource in {"search", "find", "lookup"} and len(parts) >= 2:
            resource = snake_case(parts[-2])
            return f"search_{resource}"
    verb_map = {
        "GET": "get",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }
    verb = verb_map.get(method.upper(), method.lower())
    return f"{verb}_{resource}"


def infer_description(method: str, path_template: str) -> str:
    tool_name = infer_tool_name(method, path_template).replace("_", " ")
    return f"{tool_name.capitalize()} via {method.upper()} {path_template}."


def zod_for_value(value: Any) -> str:
    if isinstance(value, bool):
        return "z.boolean()"
    if isinstance(value, int) or isinstance(value, float):
        return "z.number()"
    if isinstance(value, str):
        return "z.string()"
    if value is None:
        return "z.any().nullable()"
    if isinstance(value, list):
        if value:
            return f"z.array({zod_for_value(value[0])})"
        return "z.array(z.any())"
    if isinstance(value, dict):
        return "z.record(z.any())"
    return "z.any()"


def sanitize_value(value: Any, key: str = "") -> Any:
    key_l = key.lower()
    if key_l in SENSITIVE_KEYS:
        return "<redacted>"
    if isinstance(value, dict):
        return {k: sanitize_value(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_value(v, key) for v in value]
    return value


def env_name_for_header(host: str, header_name: str) -> str:
    header_l = header_name.lower()
    if host.endswith("supabase.co") and header_l in {"apikey", "authorization"}:
        return "SUPABASE_SERVICE_ROLE_KEY"
    if header_l == "x-n8n-api-key":
        return "N8N_API_KEY"
    if header_l == "authorization":
        return "API_AUTHORIZATION"
    return snake_case(header_name).upper()


def build_endpoint_specs(records: List[Dict[str, Any]]) -> List[EndpointSpec]:
    specs: Dict[Tuple[str, str, str], EndpointSpec] = {}
    for record in records:
        if record.get("event") != "http_traffic":
            continue
        method = str(record.get("method") or "").upper()
        url = str(record.get("url") or "")
        if not method or not url:
            continue
        parsed = urlsplit(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        raw_path = record.get("path") or parsed.path or "/"
        path_template, path_params = infer_path_template(raw_path)
        key = (method, base_url, path_template)
        request = record.get("request") or {}
        query = record.get("query") or {}
        body_json = request.get("json")
        body_data = request.get("data")
        body: Dict[str, Any] = {}
        if isinstance(body_json, dict):
            body = dict(body_json)
        elif isinstance(body_data, dict):
            body = dict(body_data)
        headers = request.get("headers") if isinstance(request.get("headers"), dict) else {}

        if key not in specs:
            spec = EndpointSpec(
                method=method,
                base_url=base_url,
                path_template=path_template,
                path_params=path_params,
                query={k: sanitize_value(v, k) for k, v in query.items()},
                body={k: sanitize_value(v, k) for k, v in body.items()},
                headers={k: str(v) for k, v in headers.items() if k.lower() in SENSITIVE_HEADERS},
            )
            for name, sample in path_params:
                spec.sample_args[name] = sample
            for k, v in spec.query.items():
                spec.sample_args[k] = v
            for k, v in spec.body.items():
                spec.sample_args[k] = v
            specs[key] = spec
        else:
            spec = specs[key]
            merge_dict(spec.query, {k: sanitize_value(v, k) for k, v in query.items()})
            merge_dict(spec.body, {k: sanitize_value(v, k) for k, v in body.items()})
            for header_k, header_v in headers.items():
                if header_k.lower() in SENSITIVE_HEADERS and header_k not in spec.headers:
                    spec.headers[header_k] = str(header_v)
            for name, sample in path_params:
                spec.sample_args.setdefault(name, sample)
            for k, v in query.items():
                spec.sample_args.setdefault(k, sanitize_value(v, k))
            for k, v in body.items():
                spec.sample_args.setdefault(k, sanitize_value(v, k))
        specs[key].samples += 1
    return sorted(specs.values(), key=lambda s: (s.base_url, s.path_template, s.method))


def ts_template_for_path(path_template: str) -> str:
    out = path_template
    for var in re.findall(r"{([A-Za-z0-9_]+)}", path_template):
        out = out.replace(f"{{{var}}}", f"${{args.{var}}}")
    return out


def render_tool_schema(
    spec: EndpointSpec,
    query_fields: List[Tuple[str, str]],
    body_fields: List[Tuple[str, str]],
) -> str:
    entries: List[str] = []
    for name, _sample in spec.path_params:
        entries.append(f'  {name}: z.string(),')
    for arg_name, key in query_fields:
        entries.append(f"  {arg_name}: {zod_for_value(spec.query.get(key))},")
    for arg_name, key in body_fields:
        entries.append(f"  {arg_name}: {zod_for_value(spec.body.get(key))},")
    return "{\n" + ("\n".join(entries) + "\n" if entries else "") + "}"


def render_headers_block(spec: EndpointSpec) -> Tuple[str, List[str]]:
    lines = ["const headers: Record<string, string> = {};"]
    env_keys: List[str] = ["BASE_URL"]
    for header_name in sorted(spec.headers.keys()):
        env_name = env_name_for_header(urlsplit(spec.base_url).netloc, header_name)
        env_keys.append(env_name)
        if header_name.lower() == "authorization" and env_name == "SUPABASE_SERVICE_ROLE_KEY":
            lines.append(f'if (process.env.{env_name}) headers["Authorization"] = `Bearer ${{process.env.{env_name}}}`;')
            continue
        lines.append(f'if (process.env.{env_name}) headers["{header_name}"] = process.env.{env_name} as string;')
    return "\n  ".join(lines), sorted(set(env_keys))


def render_query_object(query_fields: List[Tuple[str, str]]) -> str:
    if not query_fields:
        return "undefined"
    items = [f'"{key}": args.{arg_name}' for arg_name, key in query_fields]
    return "{ " + ", ".join(items) + " }"


def render_body_object(body_fields: List[Tuple[str, str]]) -> str:
    if not body_fields:
        return "undefined"
    items = [f'"{key}": args.{arg_name}' for arg_name, key in body_fields]
    return "{ " + ", ".join(items) + " }"


def write_package(spec: EndpointSpec, root: Path) -> Dict[str, Any]:
    tool_name = infer_tool_name(spec.method, spec.path_template)
    description = infer_description(spec.method, spec.path_template)
    package_dir = root / tool_name
    src_dir = package_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    headers_block, env_keys = render_headers_block(spec)
    path_ts = ts_template_for_path(spec.path_template)
    query_fields = make_arg_fields(spec.query.keys(), [name for name, _ in spec.path_params])
    body_fields = make_arg_fields(spec.body.keys(), [name for name, _ in spec.path_params] + [name for name, _ in query_fields])
    schema_block = render_tool_schema(spec, query_fields, body_fields)
    query_block = render_query_object(query_fields)
    body_block = render_body_object(body_fields)

    index_ts = f"""import axios from "axios";
import axiosRetry from "axios-retry";
import dotenv from "dotenv";
import FormData from "form-data";
import {{ z }} from "zod";
import {{ McpServer }} from "@modelcontextprotocol/sdk/server/mcp.js";
import {{ StdioServerTransport }} from "@modelcontextprotocol/sdk/server/stdio.js";

dotenv.config();
void FormData;

const BASE_URL = process.env.BASE_URL ?? "{spec.base_url}";
const client = axios.create({{ timeout: 30000, validateStatus: () => true }});
axiosRetry(client, {{
  retries: 3,
  retryDelay: axiosRetry.exponentialDelay,
  retryCondition: (error) => axiosRetry.isNetworkOrIdempotentRequestError(error) || (error.response?.status ?? 0) >= 500,
}});

const server = new McpServer({{
  name: "{tool_name}",
  version: "1.0.0",
}});

server.tool(
  "{tool_name}",
  "{description}",
{schema_block},
  async (args) => {{
  {headers_block}
    const url = `${{BASE_URL}}{path_ts}`;
    const response = await client.request({{
      method: "{spec.method}",
      url,
      headers,
      params: {query_block},
      data: {body_block},
    }});

    return {{
      content: [
        {{
          type: "text",
          text: JSON.stringify({{ status: response.status, data: response.data, headers: response.headers }}),
        }},
      ],
    }};
  }}
);

async function main() {{
  const transport = new StdioServerTransport();
  await server.connect(transport);
}}

main().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
    package_json = {
        "name": f"mcp-{tool_name}",
        "version": "1.0.0",
        "private": True,
        "type": "module",
        "scripts": {
            "build": "tsc",
            "start": "node dist/index.js",
        },
        "dependencies": {
            "@modelcontextprotocol/sdk": "^1.17.4",
            "axios": "^1.7.7",
            "axios-retry": "^4.5.0",
            "dotenv": "^16.4.5",
            "form-data": "^4.0.0",
            "zod": "^3.23.8",
        },
        "devDependencies": {
            "@types/node": "^22.10.0",
            "typescript": "^5.7.3",
        },
    }
    tsconfig = {
        "compilerOptions": {
            "target": "ES2022",
            "module": "NodeNext",
            "moduleResolution": "NodeNext",
            "strict": True,
            "esModuleInterop": True,
            "forceConsistentCasingInFileNames": True,
            "skipLibCheck": True,
            "outDir": "dist",
            "rootDir": "src",
        },
        "include": ["src/**/*.ts"],
    }
    sample_args = dict(spec.sample_args)
    for arg_name, key in query_fields:
        sample_args[arg_name] = spec.sample_args.get(key)
    for arg_name, key in body_fields:
        sample_args[arg_name] = spec.sample_args.get(key)

    client_py = f"""#!/usr/bin/env python3
import asyncio
import json
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TOOL_NAME = "{tool_name}"
TEST_ARGS = {json.dumps(sample_args, indent=2, ensure_ascii=True)}


async def main() -> None:
    server_dir = Path(__file__).resolve().parent
    params = StdioServerParameters(
        command="node",
        args=["dist/index.js"],
        cwd=str(server_dir),
        env=dict(os.environ),
    )
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                print("TOOLS")
                print(json.dumps(tools.model_dump(), indent=2, default=str))
                result = await session.call_tool(TOOL_NAME, arguments=TEST_ARGS)
                print("RESULT")
                print(json.dumps(result.model_dump(), indent=2, default=str))
    except Exception as exc:  # pylint: disable=broad-except
        print(f"ERROR: {{type(exc).__name__}}: {{exc}}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
"""
    env_example = "\n".join([f"{k}=" for k in env_keys]) + "\n"
    readme = f"""# {tool_name}

MCP tool generated from captured API traffic.

## Tool
- Name: `{tool_name}`
- Description: {description}
- Source endpoint: `{spec.method} {spec.base_url}{spec.path_template}`

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
"""
    (package_dir / "package.json").write_text(json.dumps(package_json, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    (package_dir / "tsconfig.json").write_text(json.dumps(tsconfig, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    (src_dir / "index.ts").write_text(index_ts, encoding="utf-8")
    (package_dir / "client.py").write_text(client_py, encoding="utf-8")
    (package_dir / ".env.example").write_text(env_example, encoding="utf-8")
    (package_dir / "README.md").write_text(readme, encoding="utf-8")

    return {
        "tool_name": tool_name,
        "description": description,
        "method": spec.method,
        "base_url": spec.base_url,
        "path_template": spec.path_template,
        "package_dir": str(package_dir),
        "sample_args": sample_args,
        "env_keys": env_keys,
        "samples": spec.samples,
    }


def render_skills_section(entries: List[Dict[str, Any]]) -> str:
    lines = [
        "## Auto-Generated MCP Skills (Traffic Compiler)",
        "",
        "Generated from `~/.openclaw-eve/runtime/api_traffic.jsonl`.",
        "",
    ]
    for entry in entries:
        lines.append(f"- `{entry['tool_name']}`: {entry['description']}")
        lines.append(f"  - Path: `{entry['package_dir']}`")
        lines.append(f"  - Build: `cd {entry['package_dir']} && npm run build`")
        lines.append(f"  - Verify: `cd {entry['package_dir']} && python3 client.py`")
    lines.append("")
    return "\n".join(lines)


def update_skills(skills_file: Path, entries: List[Dict[str, Any]]) -> None:
    marker = "## Auto-Generated MCP Skills (Traffic Compiler)"
    existing = skills_file.read_text(encoding="utf-8") if skills_file.exists() else ""
    section = render_skills_section(entries)
    if marker in existing:
        pre = existing.split(marker, 1)[0].rstrip() + "\n\n"
        skills_file.write_text(pre + section, encoding="utf-8")
        return
    prefix = existing.rstrip()
    new_content = (prefix + "\n\n" if prefix else "") + section
    skills_file.write_text(new_content, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile MCP tool packages from recorded HTTP traffic.")
    parser.add_argument("--traffic-file", default="~/.openclaw-eve/runtime/api_traffic.jsonl")
    parser.add_argument("--output-root", default="generated/mcp_from_traffic")
    parser.add_argument("--skills-file", default="SKILLS.md")
    parser.add_argument("--manifest-file", default="generated/mcp_from_traffic/manifest.json")
    parser.add_argument("--max-tools", type=int, default=0, help="Limit generated tools (0 = all).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    traffic_file = Path(args.traffic_file).expanduser()
    if not traffic_file.exists():
        raise SystemExit(f"traffic file missing: {traffic_file}")
    lines = [json.loads(line) for line in traffic_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    specs = build_endpoint_specs(lines)
    if args.max_tools > 0:
        specs = specs[: args.max_tools]
    output_root = Path(args.output_root)
    if output_root.exists():
        for child in output_root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    output_root.mkdir(parents=True, exist_ok=True)
    entries = [write_package(spec, output_root) for spec in specs]
    update_skills(Path(args.skills_file), entries)
    manifest = {
        "traffic_file": str(traffic_file),
        "generated_tools": entries,
    }
    manifest_path = Path(args.manifest_file)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"generated": len(entries), "manifest": str(manifest_path)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
