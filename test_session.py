"""
Minimal session-leak diagnostic.

Run with:
    uv run python test_session.py

Three isolated sub-tests printed in sequence:
  TEST A - deepagents + dummy tool (no Tavily)
  TEST B - TavilySearch tool invoked directly (no deepagents)
  TEST C - deepagents + TavilySearch together (mirrors real agent)

Watch for "Unclosed client session" after each block.
"""
import os
import warnings
from dotenv import load_dotenv

load_dotenv()

# Show ALL ResourceWarnings so we can see exactly which test triggers it.
warnings.simplefilter("always", ResourceWarning)


import yaml
from pathlib import Path

def _load_model():
    """Load the model string from config.yaml using the same logic as the real app."""
    from langchain.chat_models import init_chat_model
    from src.providers import resolve_models

    config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    provider = config.get("provider", "gemini")
    models, _ = resolve_models(provider, config["llm"])
    prefix_map = {
        "openai": "openai", "anthropic": "anthropic",
        "gemini": "google-genai", "local": "ollama", "cloud": "ollama",
    }
    prefix = prefix_map.get(provider, "ollama")
    print(f"  [using {provider} / {prefix}/{models[0]}]")
    return init_chat_model(model=models[0], model_provider=prefix)


# ---------------------------------------------------------------------------
# TEST A: deepagents with a pure-Python tool — no aiohttp involved at all
# ---------------------------------------------------------------------------
def run_test_a():
    print("\n=== TEST A: deepagents + dummy tool (no Tavily) ===")
    from deepagents import create_deep_agent
    from langchain_core.tools import tool as lc_tool

    @lc_tool
    def echo(message: str) -> str:
        """Echo back the message."""
        return f"echo: {message}"

    model = _load_model()
    agent = create_deep_agent(model=model, tools=[echo], system_prompt="You are a test agent.")
    result = agent.invoke({"messages": [{"role": "user", "content": "Say hello"}]})
    print("A result:", result["messages"][-1].content[:80])
    print("=== END TEST A ===")


# ---------------------------------------------------------------------------
# TEST B: TavilySearch invoked directly — no deepagents
# ---------------------------------------------------------------------------
def run_test_b():
    print("\n=== TEST B: TavilySearch direct (no deepagents) ===")
    from langchain_tavily import TavilySearch

    tavily_api_key = os.environ.get("TAVILY_API_KEY", "")
    search = TavilySearch(max_results=1, tavily_api_key=tavily_api_key)
    result = search.invoke("python job openings Toronto")
    print("B result type:", type(result))
    print("=== END TEST B ===")


# ---------------------------------------------------------------------------
# TEST C: deepagents + TavilySearch together (mirrors the real agent)
# ---------------------------------------------------------------------------
def run_test_c():
    print("\n=== TEST C: deepagents + TavilySearch together ===")
    from deepagents import create_deep_agent
    from langchain_tavily import TavilySearch

    tavily_api_key = os.environ.get("TAVILY_API_KEY", "")
    search_tool = TavilySearch(max_results=1, tavily_api_key=tavily_api_key)

    model = _load_model()
    agent = create_deep_agent(
        model=model,
        tools=[search_tool],
        system_prompt="You are a test agent. Use the search tool to answer.",
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "Search for python jobs in Toronto"}]}
    )
    print("C result:", result["messages"][-1].content[:80])
    print("=== END TEST C ===")


if __name__ == "__main__":
    run_test_a()
    run_test_b()
    run_test_c()
    print("\nAll tests done. Any 'Unclosed client session' above tells us which test owns the leak.")
