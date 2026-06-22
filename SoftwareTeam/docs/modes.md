<!--
Author: Ahmed Ellamie
Email: ahmed.ellamiee@gmail.com
-->

# Modes

## INIT MODE
- Analyze project and generate memory + docs
- Use `/init` in chat

## ARCHITECT MODE
- Understand system only
- **Never edit code**
- Use `/architect` in chat

## CODER MODE
- Edit **only** specified files
- **No global search**
- After every edit, record change via `record_change_tool`
- Use `/coder` in chat

## REVIEWER MODE
- Check bugs only
- **No edits**
- Use `/reviewer` in chat

## TESTER MODE (optional enhancement)
- Run tests via `run_tests` MCP tool
- Use `/test` in chat
