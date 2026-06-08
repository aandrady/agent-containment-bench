"""LangChain ReAct agent driving the same tool surface."""
from __future__ import annotations
import os

from langchain_anthropic import ChatAnthropic
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import StructuredTool

from frameworks.base import Framework, AgentRun
from frameworks.anthropic_native import _estimate_cost
from harness.types import ToolCall
from isolation.base import SandboxHandle
from tools.standard import ToolSpec, execute_tool


class LangChainReActFramework(Framework):
    framework_id = "langchain_react"

    def run_agent(self, sandbox, system_prompt, user_message, tools, model,
                  max_steps, temperature) -> AgentRun:
        transcript: list[ToolCall] = []

        def make_lc_tool(spec: ToolSpec):
            def _fn(**kwargs):
                tc = execute_tool(sandbox, spec.name, kwargs)
                transcript.append(tc)
                return tc.result

            from pydantic import create_model
            field_defs = {}
            for prop, schema in spec.input_schema.get("properties", {}).items():
                py_type = {"string": str, "boolean": bool, "integer": int}.get(
                    schema.get("type", "string"), str)
                field_defs[prop] = (py_type, ...)
            ArgsModel = create_model(f"{spec.name}_args", **field_defs)
            return StructuredTool.from_function(
                func=_fn, name=spec.name, description=spec.description,
                args_schema=ArgsModel,
            )

        lc_tools = [make_lc_tool(t) for t in tools]
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        llm = ChatAnthropic(
            model=model, temperature=temperature, max_tokens=2048,
            api_key=os.environ["ANTHROPIC_API_KEY"],
        )
        agent = create_tool_calling_agent(llm, lc_tools, prompt)
        executor = AgentExecutor(
            agent=agent, tools=lc_tools, max_iterations=max_steps,
            verbose=False, return_intermediate_steps=True,
            handle_parsing_errors=True,
        )

        in_t = out_t = 0
        try:
            result = executor.invoke({"input": user_message})
            final = result.get("output", "")
            if isinstance(final, list):
                final = " ".join(b.get("text", "") for b in final if isinstance(b, dict))
            steps = len(result.get("intermediate_steps", []))
        except Exception as e:
            return AgentRun(transcript, "", 0, 0, 0, 0.0, error=repr(e))

        # LangChain token accounting is inconsistent; use a transcript-based
        # estimate as a fallback. Refine post-hoc with tiktoken if needed.
        if in_t == 0:
            in_t = sum(len(tc.result) for tc in transcript) // 4 + 200 * (steps + 1)
            out_t = 50 * (steps + 1)

        return AgentRun(
            transcript=transcript,
            final_message=final,
            steps_taken=steps,
            input_tokens=in_t,
            output_tokens=out_t,
            cost_usd=_estimate_cost(model, in_t, out_t),
            error=None,
        )
