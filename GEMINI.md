# Gemini Best Practices

- Use `search_file_content` and `glob` to understand the codebase before making changes.
- Use `read_file` and `read_many_files` to get context before writing code.
- Adhere to existing project conventions in your code.
- Mimic the style and structure of existing code.
- Add comments to explain *why* something is done, not *what* is done.
- Verify changes with tests and linters.
- Explain critical commands before executing them.
- Use absolute paths for file operations.
- Run independent tool calls in parallel.
- Use background processes for long-running commands.
- Avoid interactive shell commands.
- Use `save_memory` to remember user preferences.
- Respect user confirmation on tool calls.
- If a tool call is cancelled, do not retry it unless asked.
- Ask for clarification if a request is ambiguous.
- Do not revert changes unless asked.
- Commit changes with clear and concise messages.
- Do not push changes to a remote repository unless asked.
