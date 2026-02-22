# Structured Skills

Structured Skills for Agents - launch MCP servers from skill directories.

## MCP Usage

You can launch skills in the `mcp.json` format. For example if our skills directory contains the [internal-comms](https://github.com/anthropics/skills/tree/main/skills/internal-comms) skill, it might look like this:

```json
{
  "mcpServers": {
    "skills": {
      "command": "uvx",
      "args": [
        "structured_skills",
        "run",
        "/path/to/root"
      ]
    }
  }
}
```

This can then be integrated to any LLM via a toolcall. For example, using LM Studio's `api/v1/chat` endpoint, a sample session may look like this:

```sh
curl http://localhost:1234/api/v1/chat \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-30b-a3b-instruct-2507",
    "system_prompt": "You are a helpful assistant.",
    "input": "Write an internal comms guide",
    "integrations": ["mcp/skills"]
}'

{
  "model_instance_id": "qwen3-30b-a3b-instruct-2507",
  "output": [
    {
      "type": "tool_call",
      "tool": "list_skills",
      "arguments": {},
      "output": "[{\"type\":\"text\",\"text\":\"{\\n  \\\"internal-comms\\\": \\\"A set of resources to help me...",
      "provider_info": {
        "plugin_id": "mcp/skills",
        "type": "plugin"
      }
    },
    {
      "type": "tool_call",
      "tool": "load_skill",
      "arguments": {
        "skill_name": "internal-comms"
      },
      "output": "[{\"type\":\"text\",\"text\":\"## When to use this skill\\nTo write internal communications, ...",
      "provider_info": {
        "plugin_id": "mcp/skills",
        "type": "plugin"
      }
    },
    {
      "type": "tool_call",
      "tool": "read_skill_resource",
      "arguments": {
        "skill_name": "internal-comms",
        "resource_name": "examples/general-comms.md"
      },
      "output": "[{\"type\":\"text\",\"text\":\"## Instructions\\n  You are being asked to write internal ...",
      "provider_info": {
        "plugin_id": "mcp/skills",
        "type": "plugin"
      }
    },
    {
      "type": "message",
      "content": "To help you write an effective internal communications guide, I need a few details:..."
    }
  ],
  "stats": {
    "input_tokens": 515,
    "total_output_tokens": 211,
    "reasoning_output_tokens": 0,
    "tokens_per_second": 38.38782308952077,
    "time_to_first_token_seconds": 1.639
  },
  "response_id": "resp_4184f10e02ff80d1a09519ff925142042ccf168105a53863"
}
```
