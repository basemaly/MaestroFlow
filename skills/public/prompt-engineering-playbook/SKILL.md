---
name: prompt-engineering-playbook
description: Build stronger prompts and editing workflows for writing tasks. Use when the user wants help designing prompts, system messages, editing playbooks, or reusable refinement instructions.
license: Apache-2.0
---

# Prompt Engineering Playbook

Use this skill for prompt design, not just prose editing.

## Core Moves

- Clarify the role, goal, and audience
- State output structure explicitly
- Define evaluation criteria before asking for the final draft
- Break large writing tasks into stages when quality matters
- Add a self-critique or refinement pass when one-shot output is likely to be weak

## Workflow

1. Identify the real output the user wants.
2. Choose the lightest prompt structure that reliably gets that output.
3. Add constraints only when they materially improve results.
4. If the task is high stakes, include critique criteria and a revision step.
5. Return the final prompt or playbook in a format the user can reuse immediately.

## Deliverables

- A reusable prompt, system message, or short playbook
- A note explaining why this structure should work
- Optional variants when the user needs a fast version and a rigorous version
