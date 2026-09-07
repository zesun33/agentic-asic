"""Robust stdio JSON-RPC 2.0 MCP Client for agentic-asic."""

import json
import os
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional


class MCPClientSession:
    """Manages an active stdio connection to a Model Context Protocol server."""

    def __init__(
        self,
        command: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 60.0,
    ):
        self.command = command
        self.cwd = cwd
        self.env = env or os.environ.copy()
        self.timeout = timeout
        self.proc: Optional[subprocess.Popen] = None
        self._msg_id = 0
        self._lock = threading.Lock()
        self.server_info: Dict[str, Any] = {}
        self._start()

    def _start(self) -> None:
        self.proc = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            env=self.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._initialize()

    def _initialize(self) -> None:
        init_req = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "agentic-asic",
                    "version": "0.2.0",
                },
            },
        }
        resp = self._send_request(init_req)
        self.server_info = resp.get("result", {}).get("serverInfo", {})

        # Send notifications/initialized per MCP specification
        notify_init = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        self._send_notification(notify_init)

    def _get_next_id(self) -> int:
        with self._lock:
            self._msg_id += 1
            return self._msg_id

    def _send_notification(self, payload: Dict[str, Any]) -> None:
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("MCP process not running")
        line = json.dumps(payload) + "\n"
        self.proc.stdin.write(line)
        self.proc.stdin.flush()

    def _send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.proc or not self.proc.stdin or not self.proc.stdout:
            raise RuntimeError("MCP process not running")

        target_id = payload.get("id")
        line = json.dumps(payload) + "\n"
        self.proc.stdin.write(line)
        self.proc.stdin.flush()

        while True:
            out_line = self.proc.stdout.readline()
            if not out_line:
                # Process exited or stdout closed
                stderr_output = ""
                if self.proc.stderr:
                    stderr_output = self.proc.stderr.read()
                raise RuntimeError(
                    f"MCP process terminated unexpectedly while awaiting response to id={target_id}. "
                    f"Stderr: {stderr_output.strip()}"
                )
            out_line = out_line.strip()
            if not out_line:
                continue
            try:
                msg = json.loads(out_line)
                if msg.get("id") == target_id:
                    if "error" in msg:
                        raise RuntimeError(f"MCP JSON-RPC Error: {msg['error']}")
                    return msg
            except json.JSONDecodeError:
                # Non-JSON debug output from server
                continue

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all tools registered by the MCP server."""
        req = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": "tools/list",
            "params": {},
        }
        resp = self._send_request(req)
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Call an MCP tool and return its payload."""
        req = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments or {},
            },
        }
        resp = self._send_request(req)
        content_list = resp.get("result", {}).get("content", [])
        if not content_list:
            return {}

        first_text = content_list[0].get("text", "")
        # Attempt to parse as JSON; fallback to raw text string
        try:
            return json.loads(first_text)
        except (json.JSONDecodeError, TypeError):
            return first_text

    def close(self) -> None:
        """Gracefully terminate the MCP session."""
        if self.proc:
            try:
                if self.proc.stdin:
                    self.proc.stdin.close()
                self.proc.terminate()
                self.proc.wait(timeout=2.0)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            finally:
                try:
                    if self.proc.stdout:
                        self.proc.stdout.close()
                    if self.proc.stderr:
                        self.proc.stderr.close()
                except Exception:
                    pass
                self.proc = None


class MCPServerLocator:
    """Discovers and resolves binary paths for the 8 EDA MCP servers."""

    SERVERS = {
        "review": "mcp-rtl-review",
        "verilog": "mcp-verilog",
        "cocotb": "mcp-cocotb",
        "yosys": "mcp-yosys",
        "openroad": "mcp-openroad",
        "gds": "mcp-gds",
        "formal": "mcp-formal",
        "fpga": "mcp-fpga",
    }

    @classmethod
    def resolve(cls, server_key: str) -> Optional[List[str]]:
        repo_name = cls.SERVERS.get(server_key, server_key)
        env_var = f"MCP_{server_key.upper()}_PATH"
        if env_var in os.environ:
            return ["node", os.environ[env_var]]

        # Check sibling directories relative to current repo or script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(script_dir, "..", "..", "..", repo_name, "dist", "index.js"),
            os.path.join(os.getcwd(), "..", repo_name, "dist", "index.js"),
            os.path.join("/data/mxm6982/projects/personal-projects", repo_name, "dist", "index.js"),
        ]
        for c in candidates:
            abs_c = os.path.abspath(c)
            if os.path.isfile(abs_c):
                return ["node", abs_c]

        return None
