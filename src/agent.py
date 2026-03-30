"""
Main job search agent — orchestrator entry point.

Initialises Hindsight memory, builds the Deep Agents orchestrator with all
tools, and runs the interactive chat loop.
"""

from __future__ import annotations
import os
import uuid
from pathlib import Path

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model

from src.memory import MemoryManager
from src.onboarding import run_onboarding
from src.prompts import AGENT_SYSTEM_PROMPT_TEMPLATE
from src.providers import resolve_models, get_provider
from src.template_agent import run_template_wizard
from src.tools.search import create_search_tool
from src.tools.generate import create_generate_tool
from src.tools.resume_editor import create_resume_tools
from src.tools.sheet_log import create_sheet_log_tool
from src.tools.suggest_roles import create_suggest_roles_tool


def _create_change_template_tool(config: dict, provider_name: str):
    from langchain_core.tools import tool as lc_tool

    @lc_tool
    def change_template() -> str:
        """Let the user interactively choose a new resume template.
        Call this when the user says they want to change their template,
        switch themes, or update the look of their resume documents.
        """
        try:
            theme = run_template_wizard(config, provider_name)
            return f"Template updated to {theme.name.capitalize()}."
        except Exception as exc:
            return f"Template change failed: {exc}"

    return change_template


_LANGCHAIN_PREFIX: dict[str, str] = {
    "openai":    "openai",
    "anthropic": "anthropic",
    "gemini":    "google-genai",
    "local":     "ollama",
    "cloud":     "ollama",
}


def _langchain_model_string(provider_name: str, config: dict) -> tuple[str, str]:
    prefix = _LANGCHAIN_PREFIX.get(provider_name, "ollama")
    models, _ = resolve_models(provider_name, config["llm"])
    return prefix, models[0]


def build_agent(config: dict, resume: dict, provider_name: str, recalled_memories: str):
    """Construct and return the compiled Deep Agents orchestrator graph.

    Separated from run_agent_chat so it can be unit-tested without a chat loop.
    """
    prefix, model_name = _langchain_model_string(provider_name, config)
    agent_model = init_chat_model(model=model_name, model_provider=prefix)

    tavily_api_key = os.environ.get("TAVILY_API_KEY", "")
    max_jobs = config.get("agent", {}).get("max_jobs", 10)

    models, parser_models = resolve_models(provider_name, config["llm"])
    provider = get_provider(provider_name, config["llm"])

    search_tool = create_search_tool(agent_model, tavily_api_key, max_jobs)
    generate_tool = create_generate_tool(config, resume, provider, models, parser_models)
    read_resume, write_resume = create_resume_tools(config["paths"]["resume_yaml"])
    sheet_log_tool = create_sheet_log_tool(config)
    change_template_tool = _create_change_template_tool(config, provider_name)
    suggest_roles_tool = create_suggest_roles_tool(config, provider, parser_models)

    system_prompt = AGENT_SYSTEM_PROMPT_TEMPLATE.format(
        candidate_name=resume["basics"]["name"],
        candidate_location=resume["basics"].get("location", "Not specified"),
        recalled_memories=recalled_memories or "No previous sessions found.",
    )

    return create_deep_agent(
        model=agent_model,
        tools=[search_tool, generate_tool, read_resume, write_resume,
                sheet_log_tool, change_template_tool, suggest_roles_tool],
        system_prompt=system_prompt,
    )


def run_agent_chat(config: dict, provider_name: str) -> None:
    """Start the interactive chat loop with the job search agent.

    If resume.yaml does not exist, runs the onboarding interview first.
    """
    import yaml as _yaml

    resume_path = config["paths"]["resume_yaml"]
    if not Path(resume_path).exists():
        resume = run_onboarding(config, provider_name)
    else:
        with open(resume_path, encoding="utf-8") as f:
            resume = _yaml.safe_load(f)

    memory = MemoryManager(config=config, resume=resume, provider_name=provider_name)
    memory.start()

    recalled_prefs = memory.recall("What are this user's job search preferences?")
    recalled_jobs = memory.recall("What jobs has this user already been shown?")
    recalled_memories = "\n".join(filter(None, [recalled_prefs, recalled_jobs]))

    from langchain_core.runnables import RunnableConfig

    agent = build_agent(config, resume, provider_name, recalled_memories)
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
            try:
                result = agent.invoke({"messages": history}, config=RunnableConfig(configurable=thread_config))
                last_msg = result["messages"][-1]
                response_text = (
                    last_msg.content[0]["text"] if isinstance(last_msg.content, list) and len(last_msg.content) > 0 and "text" in last_msg.content[0]
                    else str(last_msg.content) if isinstance(last_msg.content, str)
                    else ""
                )
                history = result["messages"]
                memory.retain(
                    f"User said: {user_input}\nJob Agent responded: {response_text[:300]}",
                    context="conversation",
                )
            except Exception as exc:
                print(f"\n[Job Agent error: {exc}]")
    finally:
        memory.stop()
