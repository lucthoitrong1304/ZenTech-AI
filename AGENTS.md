# AGENTS.md

## Project Context

This project is an AI Agent system built with Python, LangChain, and LangGraph.

The agent may use tools to inspect files, modify code, run commands, and reason about user requests. All code changes must be safe, minimal, and consistent with the existing project structure.

## Core Principles

* Always understand the user request before taking action.
* Do not guess existing code behavior.
* Inspect relevant files before editing them.
* Make the smallest possible change that solves the problem.
* Do not refactor unrelated code.
* Follow the existing architecture, naming conventions, and style.
* Prefer simple, readable, maintainable code.
* Explain assumptions when requirements are unclear.

## Tool Usage Rules

### Before Editing Code

The agent must:

1. Search for relevant files.
2. Read the files that are likely affected.
3. Understand the current implementation.
4. Identify the minimal change needed.
5. Only then apply edits.

The agent must not edit a file without reading it first.

### File Search

Use file search tools when:

* The user refers to existing code.
* The user asks to fix a bug.
* The user asks to modify a feature.
* The file path is unknown.
* The agent needs to understand project structure.

Do not invent file paths.

### File Reading

Use file reading tools when:

* The agent needs to verify current code.
* The agent needs to understand imports, function names, classes, or existing behavior.
* The agent needs context before editing.

### File Editing

When editing files:

* Keep changes focused.
* Avoid unrelated formatting changes.
* Preserve existing comments unless they are wrong or obsolete.
* Do not rename public functions, classes, routes, APIs, or schemas unless explicitly requested.
* Do not introduce new dependencies unless necessary.
* If an exact edit cannot be applied safely, stop and explain the issue.

### Running Commands

Use command execution only when useful.

Allowed examples:

* Run tests.
* Run lint/type checks.
* Inspect project files.
* Validate Python syntax.

Avoid destructive commands.

Do not run commands such as:

* `rm -rf`
* `git reset --hard`
* `git clean -fd`
* `drop database`
* `truncate table`
* Any deployment or production command

unless the user explicitly asks for it.

## Coding Rules

### Python Style

* Use clear function and variable names.
* Add type hints where practical.
* Keep functions small and focused.
* Prefer explicit error handling.
* Avoid overly clever logic.
* Avoid global mutable state unless required.
* Keep async code consistent with the existing project style.
* Use Pydantic models for structured input/output when appropriate.

### LangChain Rules

* Keep prompts separated from business logic when possible.
* Tool descriptions must clearly explain:

  * When to use the tool.
  * When not to use the tool.
  * Input format.
  * Output format.
  * Safety restrictions.
* Tool outputs should be structured and predictable.
* Do not let tools return vague success/failure strings only.
* Prefer structured results such as:

```text
{
    "success": true,
    "message": "File updated successfully",
    "data": {
        "path": "src/example.py",
        "changed": true
    },
    "error": null
}
```

### LangGraph Rules

* Keep graph nodes focused on one responsibility.
* Do not put all logic inside one large node.
* Prefer clear node separation, such as:

  * intent classification
  * planning
  * tool execution
  * verification
  * final response
* Keep state schema explicit.
* Avoid hidden state mutations.
* Route based on structured state fields, not vague text.

Example state fields:

```text
AgentState:
    user_request: str
    intent: str | None
    plan: list[str]
    tool_results: list[dict]
    final_answer: str | None
    error: str | None
```

## Agent Behavior Rules

### For Explanation Requests

If the user only asks for explanation:

* Do not modify files.
* Read files only if code context is required.
* Explain clearly and directly.
* Use examples when helpful.

### For Planning Requests

If the user asks for a plan:

* Do not modify files.
* Provide a step-by-step implementation plan.
* Mention affected files if they can be inferred.
* Mention risks or open questions.

### For Code Modification Requests

If the user asks to modify code:

1. Inspect relevant files.
2. Identify the root cause or required change.
3. Edit only the necessary files.
4. Run tests or checks if available.
5. Summarize the result.

Final response must include:

* What changed.
* Why it changed.
* Files changed.
* Tests/checks run.
* Any remaining risks.

### For Debugging Requests

When debugging:

* Identify the error type.
* Locate the likely source.
* Inspect relevant code.
* Fix the root cause, not only the symptom.
* Add defensive handling only when appropriate.
* Explain how to verify the fix.

## Safety Rules

The agent must never:

* Expose secrets, tokens, private keys, or `.env` values.
* Print full secret values.
* Delete files without explicit instruction.
* Run destructive commands without explicit instruction.
* Modify unrelated files.
* Make broad refactors without user approval.
* Claim a test passed if it was not actually run.
* Claim a file was changed if no edit was applied.

If sensitive values are found, mask them like:

```text
sk-****abcd
```

## Dependency Rules

Before adding a new dependency:

* Check whether the project already has an equivalent dependency.
* Prefer standard library solutions when reasonable.
* Explain why the dependency is needed.
* Update dependency files consistently.

Do not add dependencies just for small utility logic.

## Testing Rules

When possible, after code changes:

* Run existing tests.
* Run targeted tests first.
* Run lint/type checks if configured.
* If tests cannot be run, explain why.

Never say tests passed unless they were actually executed.

## Response Rules

The final response should be concise but complete.

For code changes, use this format:

```text
Done.

Changed:
- <file>: <summary>

Why:
- <reason>

Verification:
- <tests/checks run>

Notes:
- <risks or follow-up>
```

If no code was changed, say so clearly.

## Preferred Workflow

For most coding tasks, follow this workflow:

```text
Understand request
→ Search relevant files
→ Read files
→ Plan minimal change
→ Edit files
→ Verify
→ Summarize
```

## Important Rule

Read before edit.
Small change first.
Never guess existing code.
Never touch unrelated logic.
