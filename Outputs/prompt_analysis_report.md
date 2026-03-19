# MaestroFlow LLM Prompts and Tool Instructions Report

After a comprehensive review of the MaestroFlow codebase (both backend and frontend), here is the analysis of internal LLM prompts, system messages, and tool descriptions.

## 1. System Prompts & Templates

### 1.1 Lead Agent System Prompt
- **Location**: `backend/src/agents/lead_agent/prompt.py` (`SYSTEM_PROMPT_TEMPLATE`)
- **Confidence Score**: **85%**
- **Evaluation**: This prompt is extremely well-structured, utilizing XML-like tags (`<role>`, `<thinking_style>`, `<clarification_system>`, `<working_directory>`, `<critical_reminders>`) to separate concerns. It handles edge cases like when to ask for clarification comprehensively. However, its sheer length and intermixing of behavioral instructions with hardcoded environment paths might dilute the LLM's attention on critical cognitive tasks.
- **Suggestions for Improvement**:
  - **Refactor Lists**: Break the clarification types into a more concise bulleted list; the detailed explanations could be shortened to preserve context window if using advanced reasoning models.
  - **Dynamic Environment**: Extract the hardcoded `/mnt/user-data/...` paths into a dynamically injected variable, ensuring the core prompt remains purely behavioral.
  - **Citation Guardrails**: The `<citations>` section could include a strict negative constraint (e.g., "NEVER invent URLs; only cite URLs explicitly found in web search results").

### 1.2 Subagent Mode / Orchestrator Prompt
- **Location**: `backend/src/agents/lead_agent/prompt.py` (`_build_subagent_section`)
- **Confidence Score**: **90%**
- **Evaluation**: Excellent guidelines on concurrency (`MAXIMUM {n} task CALLS`). Using concrete examples for single-batch vs. multi-batch execution helps the LLM understand complex orchestration and parallelization seamlessly.
- **Suggestions for Improvement**:
  - **Negative Examples**: While phrases like "THIS IS NOT OPTIONAL" are strong, providing a code snippet of an *incorrect* execution (e.g., launching 10 tasks sequentially without batching) would reinforce the concurrency limits.

### 1.3 Memory Update Prompt
- **Location**: `backend/src/agents/memory/prompt.py` (`MEMORY_UPDATE_PROMPT`)
- **Confidence Score**: **80%**
- **Evaluation**: The prompt provides detailed instructions for JSON extraction based on the current memory state and new conversations. The specific length guidelines and "Confidence levels" thresholds are fantastic touches for maintaining clean memory states.
- **Suggestions for Improvement**:
  - **Few-Shot Prompting**: Provide a few-shot example of a conversation snippet mapped to the expected output JSON. Few-shot prompting drastically improves JSON formatting reliability and adherence to constraints like `shouldUpdate`.
  - **Visibility of Negative Constraints**: The "IMPORTANT: Do NOT record file upload events..." rule is tucked at the very end. Move this closer to the top or inside a high-visibility `<constraints>` XML block.

### 1.4 Fact Extraction Prompt
- **Location**: `backend/src/agents/memory/prompt.py` (`FACT_EXTRACTION_PROMPT`)
- **Confidence Score**: **75%**
- **Evaluation**: Very brief and to the point, making it token-efficient, but it lacks guardrails against hallucination or over-inference.
- **Suggestions for Improvement**:
  - Add explicit negative instructions: "Do NOT infer facts that are not present in the message."
  - Provide a short example demonstrating how to handle vague or temporary information (e.g., "I'm tired today" should be ignored, while "I prefer Python" should be logged).

### 1.5 Thread Title Generation Prompt
- **Location**: `backend/src/config/title_config.py` (`prompt_template`)
- **Confidence Score**: **70%**
- **Evaluation**: Straightforward and effective for lightweight models, but highly susceptible to instruction-tuning drift (where models insist on prepending "Title: " or using quotes).
- **Suggestions for Improvement**:
  - Provide an explicit format example: `Example output: Setting up the Docker Environment`.
  - Add a strict constraint: "Do not use markdown formatting, quotes, or prefixes like 'Title:'."

---

## 2. Tool Descriptions & Instructions

### 2.1 Task Tool (Subagent Delegation)
- **Location**: `backend/src/tools/builtins/task_tool.py`
- **Confidence Score**: **95%**
- **Evaluation**: Outstanding docstring. It clearly delineates "When to use" and "When NOT to use" the tool, and defines the available subagent types perfectly. The parameter descriptions use imperative, clear ordering ("ALWAYS PROVIDE THIS PARAMETER FIRST").
- **Suggestions for Improvement**:
  - The `subagent_model` description could specify that if left blank, it defaults safely to the system routing preference, which reduces the LLM's cognitive load and prevents it from guessing models unnecessarily.

### 2.2 Ask Clarification Tool
- **Location**: `backend/src/tools/builtins/clarification_tool.py`
- **Confidence Score**: **90%**
- **Evaluation**: Very detailed use-cases mapped exactly to the `clarification_type` literals. The "Best practices" section ensures the LLM doesn't bombard the user with multiple questions at once.
- **Suggestions for Improvement**:
  - State explicitly that the `options` parameter should be omitted if the clarification type doesn't naturally present choices (like `missing_info`), to prevent the LLM from passing empty arrays or hallucinating options.

### 2.3 Present Files Tool
- **Location**: `backend/src/tools/builtins/present_file_tool.py`
- **Confidence Score**: **85%**
- **Evaluation**: Clear guardrails ("Only files in /mnt/user-data/outputs can be presented") and good negative constraints.
- **Suggestions for Improvement**:
  - Add a sequencing reminder: "Ensure you have successfully written the file to the outputs directory BEFORE calling this tool." LLMs often try to present files before the write operation has fully resolved.

### 2.4 Calibre Integration Tools
- **Location**: `backend/src/tools/builtins/calibre_search_tool.py`, `calibre_ingest_tool.py`, `calibre_preview_tool.py`
- **Confidence Score**: **80%**
- **Evaluation**: Good descriptions differentiating natural language queries from exact metadata filters.
- **Suggestions for Improvement**:
  - Clarify the sequencing relationship between `preview` and `ingest`. In the preview tool, add: "Always use this tool to show the user what will be ingested before calling ingest_calibre_books_to_search_space."

### 2.5 Executive Orchestration Tools
- **Location**: `backend/src/executive/tools.py`
- **Confidence Score**: **82%**
- **Evaluation**: Tools like `executive_analyze_prompt`, `executive_create_project`, and `executive_run_agent` have well-defined parameter schemas and descriptive use-cases.
- **Suggestions for Improvement**:
  - **Schema Examples**: For `executive_create_project`, the `stages_json` parameter requires a complex nested JSON structure. Without a concrete JSON snippet example in the docstring, the LLM is likely to hallucinate the structure. Add a minimal JSON string example of a valid stage array.
  - **Standardization**: Standardize the "When to use" and "When NOT to use" format across all executive tools to match the high quality seen in `task_tool`.

### 2.6 View Image Tool
- **Location**: `backend/src/tools/builtins/view_image_tool.py`
- **Confidence Score**: **85%**
- **Evaluation**: Simple and clear, with good constraints on absolute paths and allowed extensions.
- **Suggestions for Improvement**:
  - Explicitly state that the LLM will receive the image content conceptually in a subsequent turn/state, so it shouldn't expect raw pixels or base64 data to be returned directly in the text response of the tool call.

### 2.7 Setup Agent Tool
- **Location**: `backend/src/tools/builtins/setup_agent_tool.py`
- **Confidence Score**: **75%**
- **Evaluation**: Brief and functional but lacks detailed formatting instructions for the `soul` parameter.
- **Suggestions for Improvement**:
  - Specify what a high-quality `SOUL.md` should look like. (e.g., "The soul parameter must be formatted in Markdown and contain specific structural sections like Role, Tone, and Core Directives").

*(Note: The `frontend` directory primarily contains UI components that parse and render these tool calls (e.g., `task`, `ask_clarification`), and does not contain primary system prompts beyond some user-facing UI "quick prompts" in `executive-drawer.tsx`.)*