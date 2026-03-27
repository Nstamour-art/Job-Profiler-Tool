# Agent-Driven Job Search — Design Spec
**Date:** 2026-03-27
**Status:** Approved

---

## Overview

A major revision of the Job Profiler Tool. The current tool requires the user to supply job URLs manually. This revision adds a proactive agent-driven mode: the user describes what they're looking for in a streaming chat session, a search sub-agent finds matching jobs via Tavily, and generation sub-agents produce tailored resumes and cover letters for the user's selected jobs. The existing `--url` pipeline is preserved unchanged.

---

## Goals

- Replace the Google Sheet as the primary entry point with a streaming agent chat loop
- Proactively discover matching jobs from the web using Tavily search
- Maintain cross-session memory of user preferences and previously seen jobs via Hindsight
- Use the Google Sheet as a structured output log (not an input queue)
- Allow the user to update their `resume.yaml` through natural language within the chat session
- Keep sub-agent context windows isolated to prevent context overflow on search and generation tasks

---

## Architecture

### Agent Topology

```
┌─────────────────────────────────────────────────────────────┐
│                    Hindsight Memory Layer                    │
│  (hindsight-all embedded, bank_id = resume basics.name)      │
│                                                              │
│  retain: user prefs, jobs seen, jobs generated               │
│  recall: past preferences, already-seen job URLs             │
└─────────────────────┬───────────────────────────────────────┘
                      │ inject recalled memories into system prompt
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Main Orchestrator Agent                         │
│  create_deep_agent(model, tools, system_prompt)              │
│                                                              │
│  Context holds only:                                         │
│  • Recalled Hindsight memories (preferences, seen jobs)      │
│  • Current session preferences (salary, location, roles)     │
│  • Compact job list (title, company, URL — no descriptions)  │
│  • User's selection and generation status                    │
│                                                              │
│  Tools:                                                      │
│  • search_jobs (spawns search sub-agent via task)            │
│  • generate_documents (spawns generation sub-agent via task) │
│  • read_resume_section / write_resume_section                │
│  • log_jobs_to_sheet                                         │
│  • retain_memory / recall_memory                             │
└──────┬──────────────────────────┬───────────────────────────┘
       │ task(search_prompt)      │ task(generate_prompt × N)
       ▼                          ▼
┌──────────────────┐   ┌──────────────────────────────────────┐
│ Search Sub-agent │   │ Generation Sub-agent (one per job)    │
│                  │   │                                        │
│ Tools:           │   │ Tools:                                 │
│ • tavily_search  │   │ • scrape_job                           │
│                  │   │ • parse_job_description                │
│ Returns:         │   │ • generate_resume                      │
│ compact JSON     │   │ • generate_cover_letter                │
│ list (max 10)    │   │ • build_docx                           │
│                  │   │ • update_sheet_row (status → Generated)│
└──────────────────┘   └──────────────────────────────────────┘
```

### Context Isolation Rationale

The main agent **never sees full job descriptions or the full resume YAML**. Both are large and would rapidly fill its context window. Instead:

- The search sub-agent handles Tavily results (many long strings) and returns only a compact job list (title, company, URL, one-line summary per job)
- Each generation sub-agent loads one job's description + the full resume YAML — its context is discarded after the task completes
- The main agent holds user preferences, the compact job list, and status updates only

---

## Conversation Flow

```
$ uv run python main.py run

Agent: "Hi! I'll help you find and apply to matching jobs. What roles are you targeting?"
User:  "AI Engineer or ML Platform Engineer"

Agent: "Got it. What's your preferred location or remote preference?"
User:  "Remote, or Montreal"

Agent: "What salary range are you looking for?"
User:  "Around $130k–$160k CAD"

Agent: [calls search_jobs tool → search sub-agent runs → returns compact list]
       "Found 10 matches. Here's what came up:

        1. Senior AI Engineer @ Acme Corp — Remote — ~$140k
        2. ML Platform Engineer @ Stripe — San Francisco — ~$150k
        3. AI Infrastructure Lead @ Shopify — Remote (Canada) — $135k–$160k
        ...

        Which would you like me to generate documents for?
        (Type numbers, e.g. 1, 3 — or 'all' for everything)"

User:  "1 and 3"

Agent: [calls generate_documents for jobs 1 and 3 sequentially]
       "Generating for Acme Corp... done ✓  (saved to output/)"
       "Generating for Shopify... done ✓  (saved to output/)"
       "Both jobs logged to your sheet. Anything else?"

User:  "I just got my AWS Solutions Architect cert, can you add it?"

Agent: [calls read_resume_section('certificates')]
       "Here's what I'd add to your certificates section:

        - name: AWS Certified Solutions Architect – Associate
          issuer: Amazon Web Services

        Does that look right? (yes/no)"

User:  "Yes"

Agent: [calls write_resume_section('certificates', updated_content)]
       "Done — resume.yaml updated."
```

The "present and select" step is handled naturally by the streaming chat loop — no special tool needed. The agent outputs the numbered list and waits for the user's next message.

---

## Memory Design

### Two-Tier Memory

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Semantic | Hindsight (embedded) | User preferences, search patterns, what jobs were seen |
| Structured | Google Sheet | Auditable log of all found and generated jobs |

### Hindsight Usage

- **Mode:** `hindsight-all` embedded (`HindsightServer` in-process — no Docker required)
- **Bank ID:** `resume["basics"]["name"]` (one bank per user)
- **LLM for memory processing:** `parser_model` from `config.yaml` (lightweight, same as job parsing)

Operations:

| When | Operation | Content |
|------|-----------|---------|
| Session start | `recall` | "What jobs have I already seen? What are my preferences?" |
| After preferences gathered | `retain` | Salary range, location, target roles |
| After search | `retain` | Job titles, companies, URLs found this session |
| After generation | `retain` | Which jobs became documents |

### Google Sheet

Sheet becomes **output-only**. The agent writes to it; users never manage it as a queue.

New column schema:

| Title | Company | URL | Status | Date Found | Priority | Reasoning |
|-------|---------|-----|--------|------------|----------|-----------|
| AI Engineer | Acme | ... | Generated | 2026-03-27 | 2 | Strong match |
| ML Platform | Stripe | ... | Seen | 2026-03-27 | — | — |

Status lifecycle: `Seen` → `Generated` → (user sets) `Applied`

---

## Resume Editing Tool

### Approach: Section-Targeted Read/Write

The agent can read and modify `resume.yaml` one section at a time. Supported sections:

- `basics` — name, contact info, location
- `work` — employment history
- `education` — degrees
- `skills` — skill categories and keywords
- `projects` — portfolio projects
- `certificates` — certifications

### Tools

**`read_resume_section(section: str) → dict`**
Returns the parsed content of the named section. Agent uses this to show the user current state before proposing changes.

**`write_resume_section(section: str, new_content: dict) → None`**
Merges the new content for the named section back into the full YAML and writes the file. The agent must always present the proposed change to the user in plain language and receive explicit confirmation ("yes") before calling this tool.

### Safety Invariant

The agent is instructed in its system prompt: *"Before calling `write_resume_section`, always show the user exactly what you are about to write and ask them to confirm. Never write without confirmation."*

---

## CLI Changes

### Commands

| Command | Behaviour |
|---------|-----------|
| `uv run python main.py run` | **NEW default** — launches streaming agent chat loop |
| `uv run python main.py run --url <url>` | **Existing** — direct URL pipeline, unchanged |
| `uv run python main.py list` | **Existing** — now shows all agent-found jobs from sheet |

### Flags Retired

`--row`, `--all`, `--force` — these were sheet-queue flags and are no longer needed.

### Flags Kept

`--provider`, `--config`, `--debug`, `--resume-only`, `--cover-only`

---

## New Files

```
src/
  agent.py              # create_deep_agent setup, streaming chat loop, Hindsight init
  memory.py             # Hindsight wrapper — typed retain/recall/reflect helpers
  tools/
    __init__.py
    search.py           # search_jobs tool — spawns Tavily search sub-agent via task
    generate.py         # generate_documents tool — spawns generation sub-agent via task
    resume_editor.py    # read_resume_section / write_resume_section tools
    sheet_log.py        # log_jobs_to_sheet / update_sheet_row tools
```

---

## Modified Files

```
src/sheets.py           # add upsert_job_row(job, status) for new schema
src/prompts.py          # add AGENT_SYSTEM_PROMPT, SEARCH_SUBAGENT_PROMPT,
                        #     GENERATION_SUBAGENT_PROMPT
main.py                 # route bare `run` to agent chat loop;
                        # retire --row, --all, --force flags
pyproject.toml          # add new dependencies
.env.example            # add TAVILY_API_KEY
config.yaml / example_config.yaml  # add agent: section
```

---

## New Dependencies

```toml
# pyproject.toml
deepagents
langchain-community     # TavilySearchResults tool
tavily-python
hindsight-all           # embedded Hindsight server
```

---

## Configuration

`config.yaml` additions:

```yaml
agent:
  max_jobs: 10            # max jobs surfaced per search session
  memory_bank: ""         # defaults to resume basics.name if empty
  memory_model: ""        # defaults to parser_model if empty
```

`.env` additions:

```env
TAVILY_API_KEY=your_key_here
```

---

## Out of Scope (Stage 2)

- **Resume YAML onboarding:** A dedicated interview agent that generates `resume.yaml` from scratch by asking the user questions section by section.
- **Parallel generation sub-agents:** Currently generation sub-agents run sequentially. Parallel dispatch via multiple `task` calls is a straightforward future upgrade.
- **Applied status tracking:** User-facing command or UI to mark sheet rows as Applied.
