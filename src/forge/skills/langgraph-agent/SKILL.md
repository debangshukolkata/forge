---
name: langgraph-agent
description: Build or extend a LangGraph graph (typed state, nodes, conditional edges, LLM client from the app's factory, tests with fake LLMs).
---
# LangGraph graphs

1. Mirror the app's existing graph module: state definition (`TypedDict` or pydantic), builder function
   signature (usually takes the LLM as a parameter), where prompts live, how the graph is compiled.
2. State: add only the keys the new nodes need; keep them typed.
3. Nodes are small functions `state -> partial state`. Put prompt text in the app's prompts location.
4. Routing: `add_conditional_edges(source, router_fn, {label: node})`; make the router pure and unit-test it.
5. Never create LLM clients inside nodes: take them from the builder argument / the app's LLM factory.
6. Tests: build the graph with a fake chat model (`FakeListChatModel(responses=[...])` or the repo's
   existing fake), invoke it, assert the final state and the path taken. No real LLM calls in tests.
7. Check wiring with `langgraph_check` (setup code that builds the graph with a fake LLM, `expect_nodes`).
