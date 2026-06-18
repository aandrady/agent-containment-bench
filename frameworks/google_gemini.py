"""Google Gemini API adapter with a manual function-calling loop."""

from __future__ import annotations

import json
import os

from google import genai
from google.genai import types

from frameworks.base import AgentRun, Framework
from harness.types import ToolCall
from isolation.base import SandboxHandle
from tools.standard import ToolSpec, execute_tool

# Gemini pricing changes over time; keep this easy to update.
PRICING = {
    "gemini-3.5-flash": {"in": 1.50, "out": 9.00},
    "gemini-3.5-flash-lite": {"in": 0.25, "out": 1.50},
}


def _estimate_cost(model: str, in_t: int, out_t: int) -> float:
    p = PRICING.get(model, PRICING["gemini-3.5-flash"])
    return (in_t * p["in"] + out_t * p["out"]) / 1_000_000


def _tool_schema(spec: ToolSpec) -> dict:
    return {
        "name": spec.name,
        "description": spec.description,
        "parameters": spec.input_schema,
    }


def _usage_token_count(response, *names: str) -> int:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return 0
    for name in names:
        value = getattr(usage, name, None)
        if value is not None:
            return int(value)
    return 0


class GoogleGeminiFramework(Framework):
    framework_id = "google_gemini"

    def __init__(self):
        self.client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

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
        tool_defs = [_tool_schema(tool) for tool in tools]
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[types.Tool(function_declarations=tool_defs)],
            temperature=temperature,
            max_output_tokens=2048,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        contents: list[types.Content] = [
            types.Content(role="user", parts=[types.Part(text=user_message)])
        ]
        transcript: list[ToolCall] = []
        in_tokens = 0
        out_tokens = 0
        final_message = ""
        error = None
        steps = 0

        try:
            for step in range(max_steps):
                steps = step + 1
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                in_tokens += _usage_token_count(
                    response,
                    "prompt_token_count",
                    "input_token_count",
                    "input_tokens",
                )
                out_tokens += _usage_token_count(
                    response,
                    "candidates_token_count",
                    "output_token_count",
                    "output_tokens",
                )

                function_calls = list(getattr(response, "function_calls", []) or [])
                if not function_calls:
                    final_message = getattr(response, "text", "") or ""
                    break

                contents.append(response.candidates[0].content)
                response_parts = []
                for function_call in function_calls:
                    args = function_call.args
                    if not isinstance(args, dict):
                        args = json.loads(args) if isinstance(args, str) else {}
                    tc = execute_tool(sandbox, function_call.name, args)
                    transcript.append(tc)
                    response_parts.append(
                        types.Part.from_function_response(
                            name=function_call.name,
                            response={"response": tc.result[:4000]},
                        )
                    )

                contents.append(types.Content(role="user", parts=response_parts))
            else:
                final_message = ""
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
