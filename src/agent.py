"""
Main job search agent — orchestrator entry point.

Initialises Hindsight memory, builds the Deep Agents orchestrator with all
tools, and runs the interactive chat loop.
"""

from __future__ import annotations
import os
import uuid
import yaml
from pathlib import Path
from typing import TYPE_CHECKING
from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool as lc_tool

if TYPE_CHECKING:
    from src.models import ProviderSuite

from src.memory import MemoryManager
from src.onboarding import run_onboarding
from src.prompts import AGENT_SYSTEM_PROMPT_TEMPLATE
from src.providers import resolve_models, get_provider, is_rate_error
from src.template_agent import run_template_wizard
from src.tools.search import create_search_tool
from src.tools.generate import create_generate_tool
from src.tools.resume_editor import create_resume_tools
from src.tools.sheet_log import create_sheet_log_tool
from src.tools.suggest_roles import create_suggest_roles_tool


def _create_change_template_tool(config: dict, provider_name: str):
    """Return a change_template tool."""
    @lc_tool
    def change_template() -> str:
        """Let the user interactively choose a new resume template.
        Call this when the user says they want to change their template,
        switch themes, or update the look of their resume documents.
        """
        try:
            theme = run_template_wizard(config, provider_name)
            return f"Template updated to {theme.name.capitalize()}."
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return f"Template change failed: {exc}"

    return change_template


_LANGCHAIN_PREFIX: dict[str, str] = {
    "openai":    "openai",
    "anthropic": "anthropic",
    "gemini":    "google-genai",
    "local":     "ollama",
    "cloud":     "ollama",
}


def _langchain_model_string(
    provider_name: str, config: dict, model_name: str | None = None
) -> tuple[str, str]:
    """Return the LangChain model provider prefix and model name."""
    prefix = _LANGCHAIN_PREFIX.get(provider_name, "ollama")
    if model_name is None:
        models, _ = resolve_models(provider_name, config["llm"])
        model_name = models[0]
    return prefix, model_name


def _init_tools(
    agent_model,
    config: dict,
    resume: dict,
    provider_name: str,
):
    """Initialize and return all tools for the agent."""
    tavily_api_key = os.environ.get("TAVILY_API_KEY", "")
    max_jobs = config.get("agent", {}).get("max_jobs", 10)

    models, parser_models = resolve_models(provider_name, config["llm"])
    provider = get_provider(provider_name, config["llm"])

    return [
        create_search_tool(agent_model, tavily_api_key, max_jobs),
        create_generate_tool(config, resume, provider, models, parser_models),
        *create_resume_tools(config["paths"]["resume_yaml"]),
        create_sheet_log_tool(config),
        _create_change_template_tool(config, provider_name),
        create_suggest_roles_tool(config, provider, parser_models)
    ]


def build_agent(
    config: dict,
    resume: dict,
    provider_name: str,
    recalled_memories: str,
    model_name: str | None = None,
):
    """Construct and return the compiled Deep Agents orchestrator graph."""
    prefix, model_name = _langchain_model_string(provider_name, config, model_name)
    agent_model = init_chat_model(model=model_name, model_provider=prefix)

    tools = _init_tools(agent_model, config, resume, provider_name)

    system_prompt = AGENT_SYSTEM_PROMPT_TEMPLATE.format(
        candidate_name=resume["basics"]["name"],
        candidate_location=resume["basics"].get("location", "Not specified"),
        recalled_memories=recalled_memories or "No previous sessions found.",
    )

    return create_deep_agent(
        model=agent_model,
        tools=tools,
        system_prompt=system_prompt,
    )


def _recall_memories(memory: MemoryManager) -> str:
    """Recall preferences and history from the MemoryManager."""
    recalled_prefs = memory.recall("What are this user's job search preferences?")
    recalled_jobs = memory.recall("What jobs has this user already been shown?")
    return "\n".join(filter(None, [recalled_prefs, recalled_jobs]))


def run_agent_chat(config: dict, provider_name: str) -> None:
    """Start the interactive chat loop with the job search agent."""
    resume_path = config["paths"]["resume_yaml"]
    if not Path(resume_path).exists():
        resume = run_onboarding(config, provider_name)
    else:
        with open(resume_path, encoding="utf-8") as f:
            resume = yaml.safe_load(f)

    memory = MemoryManager(config=config, resume=resume, provider_name=provider_name)
    memory.start()

    recalled = _recall_memories(memory)
    models, _ = resolve_models(provider_name, config["llm"])
    model_idx = 0
    agent = build_agent(config, resume, provider_name, recalled, models[0])
    thread_config = {"thread_id": str(uuid.uuid4())}

    print("\nJob Search Agent ready. Type 'exit' to quit.\n")
    history: list[dict] = []

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nJob Agent: Goodbye!")
                break

            if user_input.lower() in ("exit", "quit", "bye"):
                print("Job Agent: Goodbye! Good luck with your applications.")
                break

            if not user_input:
                continue

            history.append({"role": "user", "content": user_input})
            print("Job Agent: ", end="", flush=True)

            while model_idx < len(models):
                try:
                    result = agent.invoke(
                        {"messages": history},
                        config=RunnableConfig(configurable=thread_config)
                    )
                    last_msg = result["messages"][-1]
                    response_text = _extract_response(last_msg)
                    print(response_text)
                    history = result["messages"]
                    memory.retain(
                        f"User said: {user_input}\nJob Agent responded: {response_text[:300]}",
                        context="conversation",
                    )
                    break
                except Exception as e:  # pylint: disable=broad-exception-caught
                    if is_rate_error(e) and model_idx + 1 < len(models):
                        model_idx += 1
                        print(
                            f"\n  [{models[model_idx - 1]} overloaded]"
                            f" Switching to {models[model_idx]}..."
                        )
                        agent = build_agent(
                            config, resume, provider_name, recalled, models[model_idx]
                        )
                    else:
                        print(f"Error: {e}")
                        break
    finally:
        memory.stop()
        import asyncio  # pylint: disable=import-outside-toplevel
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                loop.run_until_complete(asyncio.sleep(0))
        except Exception:  # pylint: disable=broad-exception-caught
            pass


def _extract_response(message) -> str:
    """Extract text from a LangChain message, handling all provider content formats.

    Anthropic returns a list of typed blocks: [{"type": "text", "text": "..."}].
    Gemini/Ollama typically return a plain string. Both forms are handled here.
    """
    if isinstance(message.content, str):
        return message.content
    if isinstance(message.content, list):
        parts = []
        for block in message.content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
            elif not isinstance(block, dict) and hasattr(block, "text"):
                parts.append(getattr(block, "text"))
        return "\n".join(parts)
    return ""
