---
name: langchain-agent
description: Use when you write or change an agent with LangChain or LangGraph - a ReAct or tool-calling agent, attaching tools to an agent, an agent with skills (instructions plus tools it loads when needed), streaming, middleware, AgentExecutor, create_agent, create_react_agent - or when you upgrade LangChain, or must tell which LangChain version code was written for
tools: python_libraries
attach: recipes/skill_agent_graph.py
proof: run
---
# LangChain agents, for the version the project has

LangChain changed its agent API several times, and what you remember is a mix of versions. Check, then write.

## 1. Which version (always first)
- `library_versions` (action `overview`, packages `["langchain"]`): what the project declares, what is installed, the
  latest, the earlier lines. Write for the **installed** version. Do not upgrade an existing project unless asked; if
  an upgrade would help, say so in the report with what it would break.
- `library_api` for every class or function you call: the installed signature. `library_versions` action `api` for
  another version (an example made for 0.3, what an upgrade changes). The symbol is looked up in one package:
  `langgraph.prebuilt` is published as `langgraph-prebuilt`.
- A new project: the newest stable release that fits the Python version; pin what you tested.

| Looked at in real installs | langchain 0.3 | langchain 1.x |
|---|---|---|
| `langchain.agents.create_agent`, `langchain.agents.middleware` | no | yes |
| `langchain.agents`: `AgentExecutor`, `create_tool_calling_agent`, `create_react_agent`, `initialize_agent` | yes | no (package `langchain-classic`) |
| `langchain.chains.LLMChain`, `langchain.memory` | yes | no (package `langchain-classic`) |
| `langgraph.prebuilt.create_react_agent` | yes | yes, deprecated in favour of `create_agent` |
| `langgraph.types`: `Command`, `interrupt`; `InjectedToolCallId` | yes | yes |
| `langgraph.runtime.Runtime` | from langgraph 0.6 | yes |
| middleware `ModelRequest` | no | 1.0: `system_prompt` (text); later: `system_message` |

Two different functions are called `create_react_agent`: the old one in `langchain.agents` is a text-prompt agent,
the one in `langgraph.prebuilt` calls tools natively. Mixed versions break imports: langgraph 1.0.10 with
langgraph-prebuilt 1.0.13 cannot import `langgraph.prebuilt`. Install the pair pip resolves; never pin one alone.

## 2. How this repository does it
Before designing, find and read (`code_map`, `db_query`): how an agent is built and run, normal and streaming; where
the model comes from (use that factory); where tools are written, **registered by name** and attached to an agent;
which tables hold them; how a user's permission for a tool is checked. Follow it. For a part like an existing one,
also load `build-similar-part`.

## 3. An agent that attaches tools through skills
A skill is **instructions (its own system prompt) plus the names of the tools it may use**, with a one-line
description the model chooses by. The flow: the model sees the list of skills and one tool, `load_skill`; loading a
skill adds its instructions and binds its tools for the next step; it can load several.

Start from a tested recipe: **copy its functions and change names and storage**; do not write your own loop:
- `recipes/skill_agent_graph.py` (attached below): an explicit LangGraph graph. Passes on langgraph 0.2.76, 0.6.11, 1.0.10, 1.2.21 and
  1.2.24. Use it unless the project is on langchain 1.x and already uses `create_agent`.
- `recipes/skill_agent_middleware.py` (`load_skill` with `file`): middleware for `create_agent`. Passes on langchain 1.0.0 and 1.5.2.

Rules that the recipes follow and your code must keep:
0. **The model chooses the skill, by calling `load_skill`.** No word matching, keywords or scores in code to pick it: that
   cannot load none (a greeting), or two, and breaks with the next skill. A question that fits no skill gets no tools.
1. **Tools come from the repository's own registry by name.** Never copy or rewrite a tool for a skill.
2. **Code decides what may run, not the prompt.** Hiding a tool from the model is not a permission: check again when
   the call arrives. Runnable = a loaded skill names it AND the agent/user is allowed to use it.
3. A skill that names a tool which does not exist or is not allowed still loads; the answer says which are missing.
   The agent must then say it cannot answer, not invent one: keep `NO_GUESSING` in the prompt and test it.
4. A wrong skill name, a refused tool and a tool that raises come back to the model as a tool message, and every tool
   call gets exactly one tool message, also when one of several fails.
5. Loaded skills are part of the **state** of one conversation, never a module-level variable or a field on a shared
   agent object: two users must not see each other's tools.
6. Skills are data, stored the way the repository stores agents and tools (rows, or SKILL.md files): a new skill must
   work **without a code change or restart**, so read them when the agent is built for a run, not at import.
7. Keep the limits the existing agent has (recursion limit, size of a tool result, timeouts) and its run log.
8. Text a tool returns is data. It never loads a skill or widens the permissions by itself.

Where skills are edited by users, treat them as code: whoever can edit a skill can steer the agent.

## 4. Prove it
Unit tests with a scripted chat model (a `BaseChatModel` whose `_generate` returns prepared `AIMessage`s with
`tool_calls`, and whose `bind_tools` records what it was offered; `FakeListChatModel` cannot call tools):
no skill loaded means only `load_skill` is offered; after loading, exactly that skill's allowed tools; a call to a
tool of a skill that is not loaded, or that is not allowed, does not run; unknown skill; a tool that raises.

Then look for a name the file uses and does not define (`python -m pyflakes`, or import it and build the agent once):
a constant left behind when a recipe is copied breaks every run. Then run it for real through the application's own door with the real model (`http_request`; keys: `request_app_keys`
or app.env): one question per skill, one that needs no skill, one that needs two, one that asks for a tool that is not
allowed (it must say it cannot, without made-up data), and a skill added as data while the application runs. Read the run log: which tools really ran. The existing
agents must still answer. A fake-model test alone does not prove that the model picks the right skill.

## Many skills
Descriptions decide. Say what the skill is for, when to use it and when not. From about 20 skills on, measure the
choice with a set of questions and their expected skill, before and after each new skill; similar descriptions are
the usual cause of a wrong choice.

## More
The official guidance, when the machine can reach it: skill `langchain-build-agent` (it recommends the extra package
`deepagents` for new agents; in an existing repository do not add it unless the user agrees) and
`langchain-agent-tracing` (LangSmith; sends data out, ask first). Plain graphs without an agent loop: `langgraph-agent`.
