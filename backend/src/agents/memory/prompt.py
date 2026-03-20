"""Prompt templates for memory update and injection."""

import re
from typing import Any

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

# Prompt template for updating memory based on conversation
MEMORY_UPDATE_PROMPT = """You are a memory management system. Your task is to analyze a conversation and update the user's memory profile.

<constraints>
High-Visibility Constraints:
- Only record durable information that will matter in future conversations.
- Do NOT infer facts that are not clearly supported by the conversation. If the user mentions a company or role, do NOT infer their tech stack or team unless explicitly stated.
- Do NOT record file upload events, temporary files, or other session-only artifacts.
- Remove facts directly contradicted by new information: add their IDs to factsToRemove. Common contradiction patterns: new job/company replaces old job, new primary language replaces old one, new location replaces old one.
- Return ONLY valid JSON. No markdown, commentary, or surrounding text.
</constraints>

Current Memory State:
<current_memory>
{current_memory}
</current_memory>

New Conversation to Process:
<conversation>
{conversation}
</conversation>

Memory Section Guidelines:

**User Context** (Current state - concise summaries):
- workContext: Professional role, company, key projects, main technologies (2-3 sentences)
  Example: Core contributor, project names with metrics (16k+ stars), technical stack
- personalContext: Languages, communication preferences, key interests (1-2 sentences)
  Example: Bilingual capabilities, specific interest areas, expertise domains
- topOfMind: Multiple ongoing focus areas and priorities (3-5 sentences, detailed paragraph)
  Example: Primary project work, parallel technical investigations, ongoing learning/tracking
  Include: Active implementation work, troubleshooting issues, market/research interests
  Note: This captures SEVERAL concurrent focus areas, not just one task
  Update: Integrate new themes while removing completed or abandoned ones; keep 3-5 active themes

**History** (Temporal context - rich paragraphs):
- recentMonths: Detailed summary of recent activities (4-6 sentences or 1-2 paragraphs)
  Timeline: Last 1-3 months of interactions
  Include: Technologies explored, projects worked on, problems solved, interests demonstrated
  Update: Integrate new information chronologically into the appropriate time period
- earlierContext: Important historical patterns (3-5 sentences or 1 paragraph)
  Timeline: 3-12 months ago
  Include: Past projects, learning journeys, established patterns
- longTermBackground: Persistent background and foundational context (2-4 sentences)
  Timeline: Overall/foundational information
  Include: Core expertise, longstanding interests, fundamental working style

**Facts Extraction**:
- Extract specific, quantifiable details (e.g., "16k+ GitHub stars", "200+ datasets")
- Include proper nouns (company names, project names, technology names)
- Preserve technical terminology and version numbers
- Categories:
  * preference: Tools, styles, approaches user prefers/dislikes
  * knowledge: Specific expertise, technologies mastered, domain knowledge
  * context: Background facts (job title, projects, locations, languages)
  * behavior: Working patterns, communication habits, problem-solving approaches
  * goal: Stated objectives, learning targets, project ambitions
- Confidence levels:
  * 0.9-1.0: Explicitly stated facts ("I work on X", "My role is Y")
  * 0.7-0.8: Strongly implied from actions/discussions
  * 0.5-0.6: Inferred patterns (use sparingly, only for clear patterns)

**Multilingual Content**:
- Preserve original language for proper nouns and company names
- Keep technical terms in their original form (DeepSeek, LangGraph, etc.)
- Note language capabilities in personalContext

Few-Shot Examples:
Example A — durable update:
Conversation snippet:
User: I lead the platform team at Acme and mostly work in Python and Postgres.
Assistant: Noted.
Expected shape:
{{
  "user": {{
    "workContext": {{ "summary": "Leads the platform team at Acme and primarily works with Python and Postgres.", "shouldUpdate": true }},
    "personalContext": {{ "summary": "", "shouldUpdate": false }},
    "topOfMind": {{ "summary": "", "shouldUpdate": false }}
  }},
  "history": {{
    "recentMonths": {{ "summary": "", "shouldUpdate": false }},
    "earlierContext": {{ "summary": "", "shouldUpdate": false }},
    "longTermBackground": {{ "summary": "", "shouldUpdate": false }}
  }},
  "newFacts": [
    {{ "content": "Leads the platform team at Acme.", "category": "context", "confidence": 0.95 }},
    {{ "content": "Primarily works with Python and Postgres.", "category": "knowledge", "confidence": 0.95 }}
  ],
  "factsToRemove": []
}}

Example B — ignore transient/session-only info:
Conversation snippet:
User: I uploaded three PDFs today and I'm exhausted right now.
Assistant: I can help with those PDFs.
Expected shape:
{{
  "user": {{
    "workContext": {{ "summary": "", "shouldUpdate": false }},
    "personalContext": {{ "summary": "", "shouldUpdate": false }},
    "topOfMind": {{ "summary": "", "shouldUpdate": false }}
  }},
  "history": {{
    "recentMonths": {{ "summary": "", "shouldUpdate": false }},
    "earlierContext": {{ "summary": "", "shouldUpdate": false }},
    "longTermBackground": {{ "summary": "", "shouldUpdate": false }}
  }},
  "newFacts": [],
  "factsToRemove": []
}}

Output Format (JSON):
{{
  "user": {{
    "workContext": {{ "summary": "...", "shouldUpdate": true/false }},
    "personalContext": {{ "summary": "...", "shouldUpdate": true/false }},
    "topOfMind": {{ "summary": "...", "shouldUpdate": true/false }}
  }},
  "history": {{
    "recentMonths": {{ "summary": "...", "shouldUpdate": true/false }},
    "earlierContext": {{ "summary": "...", "shouldUpdate": true/false }},
    "longTermBackground": {{ "summary": "...", "shouldUpdate": true/false }}
  }},
  "newFacts": [
    {{ "content": "...", "category": "preference|knowledge|context|behavior|goal", "confidence": 0.0-1.0 }}
  ],
  "factsToRemove": ["fact_id_1", "fact_id_2"]
}}

Return ONLY valid JSON, no explanation or markdown."""


# Prompt template for extracting facts from a single message
FACT_EXTRACTION_PROMPT = """NEVER infer facts not directly stated. NEVER record temporary states ("tired today", "just uploaded"). Return ONLY valid JSON.

Extract factual information about the user from this message.

Message:
{message}

Categories:
- preference: tools, styles, approaches the user likes or dislikes
- knowledge: expertise or knowledge domains the user has
- context: background facts — job, projects, location, languages
- behavior: working patterns, communication habits
- goal: stated objectives, learning targets, project ambitions

Confidence:
- 0.9+: explicitly stated ("I work at Acme", "I prefer Python")
- 0.6–0.8: strongly implied from actions or discussion
- below 0.6: do not record

Example A — durable, explicit fact:
Message: "I've been using Rust for systems work at my current job."
Output:
{{"facts": [
  {{"content": "Uses Rust for systems programming professionally.", "category": "knowledge", "confidence": 0.95}},
  {{"content": "Works in a systems engineering role.", "category": "context", "confidence": 0.75}}
]}}

Example B — transient, skip everything:
Message: "I'm exhausted and just uploaded three PDFs."
Output:
{{"facts": []}}

Example C — ambiguous, extract only what's explicit:
Message: "I've been looking into LangGraph lately."
Output:
{{"facts": [
  {{"content": "Currently exploring LangGraph.", "category": "knowledge", "confidence": 0.65}}
]}}

Output format:
{{"facts": [
  {{"content": "...", "category": "preference|knowledge|context|behavior|goal", "confidence": 0.0-1.0}}
]}}

Return ONLY valid JSON."""


def _count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count tokens in text using tiktoken.

    Args:
        text: The text to count tokens for.
        encoding_name: The encoding to use (default: cl100k_base for GPT-4/3.5).

    Returns:
        The number of tokens in the text.
    """
    if not TIKTOKEN_AVAILABLE:
        # Fallback to character-based estimation if tiktoken is not available
        return len(text) // 4

    try:
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except Exception:
        # Fallback to character-based estimation on error
        return len(text) // 4


def format_memory_for_injection(memory_data: dict[str, Any], max_tokens: int = 2000) -> str:
    """Format memory data for injection into system prompt.

    Args:
        memory_data: The memory data dictionary.
        max_tokens: Maximum tokens to use (counted via tiktoken for accuracy).

    Returns:
        Formatted memory string for system prompt injection.
    """
    if not memory_data:
        return ""

    sections = []

    # Format user context
    user_data = memory_data.get("user", {})
    if user_data:
        user_sections = []

        work_ctx = user_data.get("workContext", {})
        if work_ctx.get("summary"):
            user_sections.append(f"Work: {work_ctx['summary']}")

        personal_ctx = user_data.get("personalContext", {})
        if personal_ctx.get("summary"):
            user_sections.append(f"Personal: {personal_ctx['summary']}")

        top_of_mind = user_data.get("topOfMind", {})
        if top_of_mind.get("summary"):
            user_sections.append(f"Current Focus: {top_of_mind['summary']}")

        if user_sections:
            sections.append("User Context:\n" + "\n".join(f"- {s}" for s in user_sections))

    # Format history
    history_data = memory_data.get("history", {})
    if history_data:
        history_sections = []

        recent = history_data.get("recentMonths", {})
        if recent.get("summary"):
            history_sections.append(f"Recent: {recent['summary']}")

        earlier = history_data.get("earlierContext", {})
        if earlier.get("summary"):
            history_sections.append(f"Earlier: {earlier['summary']}")

        if history_sections:
            sections.append("History:\n" + "\n".join(f"- {s}" for s in history_sections))

    if not sections:
        return ""

    result = "\n\n".join(sections)

    # Use accurate token counting with tiktoken
    token_count = _count_tokens(result)
    if token_count > max_tokens:
        # Truncate to fit within token limit
        # Estimate characters to remove based on token ratio
        char_per_token = len(result) / token_count
        target_chars = int(max_tokens * char_per_token * 0.95)  # 95% to leave margin
        result = result[:target_chars] + "\n..."

    return result


def format_conversation_for_update(messages: list[Any]) -> str:
    """Format conversation messages for memory update prompt.

    Args:
        messages: List of conversation messages.

    Returns:
        Formatted conversation string.
    """
    lines = []
    for msg in messages:
        role = getattr(msg, "type", "unknown")
        content = getattr(msg, "content", str(msg))

        # Handle content that might be a list (multimodal)
        if isinstance(content, list):
            text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and "text" in p]
            content = " ".join(text_parts) if text_parts else str(content)

        # Strip uploaded_files tags from human messages to avoid persisting
        # ephemeral file path info into long-term memory.  Skip the turn entirely
        # when nothing remains after stripping (upload-only message).
        if role == "human":
            content = re.sub(r"<uploaded_files>[\s\S]*?</uploaded_files>\n*", "", str(content)).strip()
            if not content:
                continue

        # Truncate very long messages
        if len(str(content)) > 1000:
            content = str(content)[:1000] + "..."

        if role == "human":
            lines.append(f"User: {content}")
        elif role == "ai":
            lines.append(f"Assistant: {content}")

    return "\n\n".join(lines)
