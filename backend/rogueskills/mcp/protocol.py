from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, TextIO

from pydantic import BaseModel, ValidationError

from .api_client import RogueSkillsApiError

MCP_PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_MCP_PROTOCOL_VERSIONS = frozenset(
    {"2024-11-05", "2025-03-26", MCP_PROTOCOL_VERSION}
)

JsonObject = dict[str, Any]
ToolHandler = Callable[[JsonObject], Awaitable[object]]


@dataclass(frozen=True)
class McpTool:
    name: str
    description: str
    input_schema: JsonObject
    handler: ToolHandler
    output_schema: JsonObject | None = None
    annotations: JsonObject | None = None

    def definition(self) -> JsonObject:
        result: JsonObject = {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }
        if self.output_schema is not None:
            result["outputSchema"] = self.output_schema
        if self.annotations is not None:
            result["annotations"] = self.annotations
        return result


class McpProtocolError(ValueError):
    def __init__(self, code: int, message: str, data: object | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _tool_result(value: object, *, is_error: bool = False) -> JsonObject:
    json_value = _jsonable(value)
    text = json.dumps(json_value, ensure_ascii=False, separators=(",", ":"))
    result: JsonObject = {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }
    if isinstance(json_value, dict):
        result["structuredContent"] = json_value
    return result


class StdioMcpServer:
    def __init__(
        self,
        *,
        name: str,
        version: str,
        instructions: str,
        tools: list[McpTool],
    ) -> None:
        self.name = name
        self.version = version
        self.instructions = instructions
        self._tools = {tool.name: tool for tool in tools}
        if len(self._tools) != len(tools):
            raise ValueError("MCP tool names must be unique")

    def _success(self, message_id: object, result: object) -> JsonObject:
        return {"jsonrpc": "2.0", "id": message_id, "result": result}

    def _error(self, message_id: object, error: McpProtocolError) -> JsonObject:
        body: JsonObject = {"code": error.code, "message": error.message}
        if error.data is not None:
            body["data"] = error.data
        return {"jsonrpc": "2.0", "id": message_id, "error": body}

    async def handle_message(self, message: object) -> JsonObject | None:
        if not isinstance(message, Mapping):
            return self._error(None, McpProtocolError(-32600, "Invalid Request"))
        message_id = message.get("id")
        try:
            if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
                raise McpProtocolError(-32600, "Invalid Request")
            method = str(message["method"])
            params = message.get("params", {})
            if not isinstance(params, Mapping):
                raise McpProtocolError(-32602, "Invalid params")

            if message_id is None:
                return None
            if method == "initialize":
                requested = str(params.get("protocolVersion") or MCP_PROTOCOL_VERSION)
                negotiated = (
                    requested
                    if requested in SUPPORTED_MCP_PROTOCOL_VERSIONS
                    else MCP_PROTOCOL_VERSION
                )
                return self._success(
                    message_id,
                    {
                        "protocolVersion": negotiated,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": self.name, "version": self.version},
                        "instructions": self.instructions,
                    },
                )
            if method == "ping":
                return self._success(message_id, {})
            if method == "tools/list":
                return self._success(
                    message_id,
                    {"tools": [tool.definition() for tool in self._tools.values()]},
                )
            if method == "tools/call":
                return self._success(message_id, await self._call_tool(params))
            raise McpProtocolError(-32601, "Method not found", {"method": method})
        except McpProtocolError as error:
            return self._error(message_id, error)

    async def _call_tool(self, params: Mapping[str, Any]) -> JsonObject:
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or name not in self._tools:
            raise McpProtocolError(-32602, "Unknown tool", {"name": name})
        if not isinstance(arguments, dict):
            raise McpProtocolError(-32602, "Tool arguments must be an object")
        try:
            return _tool_result(await self._tools[name].handler(arguments))
        except ValidationError as error:
            return _tool_result(
                {
                    "code": "INVALID_TOOL_ARGUMENTS",
                    "message": "Tool arguments do not match the declared input schema.",
                    "retryable": False,
                    "details": {"errors": error.errors(include_url=False)},
                },
                is_error=True,
            )
        except RogueSkillsApiError as error:
            return _tool_result(error.error, is_error=True)
        except Exception as error:
            return _tool_result(
                {
                    "code": "INTERNAL_TOOL_ERROR",
                    "message": "The MCP tool failed before producing a valid result.",
                    "retryable": False,
                    "details": {"errorType": type(error).__name__},
                },
                is_error=True,
            )


async def serve_stdio(server: StdioMcpServer, *, reader: TextIO, writer: TextIO) -> None:
    while True:
        line = await asyncio.to_thread(reader.readline)
        if not line:
            return
        try:
            message = json.loads(line)
        except json.JSONDecodeError as error:
            response: JsonObject | None = server._error(
                None,
                McpProtocolError(
                    -32700,
                    "Parse error",
                    {"line": error.lineno, "column": error.colno},
                ),
            )
        else:
            response = await server.handle_message(message)
        if response is not None:
            writer.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            writer.flush()


async def run_stdio(server: StdioMcpServer) -> None:
    await serve_stdio(server, reader=sys.stdin, writer=sys.stdout)
