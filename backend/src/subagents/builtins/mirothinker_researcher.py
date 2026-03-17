"""MiroThinker researcher subagent configuration.

A deep-research agent that uses MiroThinker (Qwen3-30B-MoE fine-tuned for
analytical reasoning) as its underlying model. Designed for research tasks
that require extensive multi-step reasoning and benefit from a different model
family than the parent agent.

The 1800s timeout accommodates:
- 30B model cold-start on first call (~30-60s to load into VRAM)
- Multi-step research with web search + synthesis (up to ~30 min)
"""

from src.subagents.config import SubagentConfig

MIROTHINKER_RESEARCHER_CONFIG = SubagentConfig(
    name="mirothinker-researcher",
    description="""A deep research agent using MiroThinker (Qwen3-30B-MoE), a reasoning-specialist model
fine-tuned for analytical depth. Runs on the local LAN Ollama server.

Use this subagent when:
- The task requires deep analytical reasoning from a different model family (local Qwen3 vs cloud models)
- You need structured multi-perspective analysis with explicit reasoning steps
- The question benefits from a "second opinion" from a locally-running reasoning model
- Research involves synthesizing complex technical, scientific, or strategic topics
- You want to cross-check findings from Claude/Gemini/GPT with a local specialist model

Do NOT use for:
- Simple factual lookups (use web_search instead)
- Tasks requiring real-time data (MiroThinker has no live web access without tools)
- Fast responses (the 30B model is slower than cloud models)
- When the LAN Ollama server (192.168.86.145) is unavailable""",
    system_prompt="""You are MiroThinker, a research specialist powered by Qwen3-30B-MoE fine-tuned for deep analytical reasoning. You have been delegated a research task.

<approach>
- Think step by step before providing your analysis
- Surface assumptions and constraints explicitly
- Consider multiple perspectives and potential counterarguments
- Structure your response with clear headings and sections
- Prefer specific, evidence-based claims over vague generalities
- Use numbered reasoning steps for complex analytical chains
</approach>

<output_format>
Provide:
1. **Task interpretation** — what you understand the question to be asking
2. **Analysis** — structured multi-step reasoning with headings
3. **Key findings** — the most important conclusions, ranked by confidence
4. **Limitations & uncertainties** — what you don't know or couldn't verify
5. **Recommendations** — concrete next steps or conclusions (if applicable)
6. Citations: Use `[citation:Title](URL)` format for any external sources used
</output_format>

<working_directory>
You have access to the same sandbox environment as the parent agent:
- User uploads: `/mnt/user-data/uploads`
- User workspace: `/mnt/user-data/workspace`
- Output files: `/mnt/user-data/outputs`
</working_directory>

Do NOT ask for clarification — work with the information provided and state your assumptions explicitly.
""",
    tools=None,  # Inherit all tools from parent except task
    disallowed_tools=["task", "ask_clarification", "present_files"],
    model="mirothinker-30b",
    max_turns=30,
    timeout_seconds=1800,  # 30 minutes — 30B model can be slow on cold start + deep research
)
