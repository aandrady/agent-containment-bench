"""Anthropic Messages API with native tool use, multi-turn loop."""
from __future__ import annotations
import os
import time
from anthropic import Anthropic

from frameworks.base import Framework, AgentRun
from harness.types import ToolCall
from isolation.base import SandboxHandle
from tools.standard import ToolSpec, execute_tool

# Pricing as of mid-2026; adjust if Anthropic changes them. Per 1M tokens.
PRICING = {
    "claude-opus-4-7":           {"in": 15.0, "out": 75.0},
    "claude-opus-4-6":           {"in": 15.0, "out": 75.0},
    "claude-sonnet-4-6":         {"in":  3.0, "out": 15.0},
    "claude-haiku-4-5-20251001": {"in":  0.80, "out": 4.0},
}


def _estimate_cost(model: str, in_t: int, out_t: int) -> float:
    p = PRICING.get(model, {"in": 3.0, "out": 15.0})
    return (in_t * p["in"] + out_t * p["out"]) / 1_000_000


class AnthropicNativeFramework(Framework):
    framework_id = "anthropic_native"

    def __init__(self):
        self.client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def _to_anthropic_tool(self, spec: ToolSpec) -> dict:
        return {
            "name": spec.name,
            "description": spec.description,
            "input_schema": spec.input_schema,
        }

    def run_agent(
        self,
        sandbox: SandboxHandle,
        system_prompt: str,
        user_message: str,
        tools: list[ToolSpec],
        model: str,
        max_steps: int,
        temperature: float,
    ) -> AgentRun:
        anth_tools = [self._to_anthropic_tool(t) for t in tools]
        messages = [{"role": "user", "content": user_message}]
        transcript: list[ToolCall] = []
        in_tokens = 0
        out_tokens = 0
        final_message = ""
        error = None
        steps = 0

        try:
            for step in range(max_steps):
                steps = step + 1
                resp = self.client.messages.create(
                    model=model,
                    max_tokens=2048,
                    system=system_prompt,
                    tools=anth_tools,
                    messages=messages,
                    temperature=temperature,
                )
                in_tokens += resp.usage.input_tokens
                out_tokens += resp.usage.output_tokens

                messages.append({"role": "assistant", "content": resp.content})

                if resp.stop_reason == "end_turn":
                    final_message = "".join(
                        b.text for b in resp.content if getattr(b, "type", "") == "text"
                    )
                    break

                if resp.stop_reason == "tool_use":
                    tool_results = []
                    for block in resp.content:
                        if getattr(block, "type", "") == "tool_use":
                            tc = execute_tool(sandbox, block.name, dict(block.input))
                            transcript.append(tc)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": tc.result[:4000],
                            })
                    messages.append({"role": "user", "content": tool_results})
                    continue

                # Other stop reasons (max_tokens, stop_sequence) — bail
                final_message = "".join(
                    getattr(b, "text", "") for b in resp.content
                )
                break
        except Exception as e:
            error = repr(e)

        return AgentRun(
            transcript=transcript,
            final_message=final_message,
            steps_taken=steps,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=_estimate_cost(model, in_tokens, out_tokens),
            error=error,
        )
