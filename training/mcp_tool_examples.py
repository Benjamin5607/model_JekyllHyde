"""Gold MCP sequential tool-calling examples for structured-output LoRA alignment."""

from __future__ import annotations


def mcp_tool_training_records(system: str) -> list[dict]:
    """JSON tool-call chains the model should reproduce reliably."""
    records: list[dict] = []

    def _rec(user: str, assistant: str, *, chain: str = "") -> dict:
        return {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ],
            "meta": {
                "type": "mcp_tool_chain",
                "format": "mcp_tool_call",
                "category": "mcp_tools",
                "quality_score": 0.95,
                "chain": chain,
            },
        }

    records.append(_rec(
        "Set community guidelines from this draft, then verify the spam section.",
        """```json
{
  "tool_calls": [
    {"name": "set_guidelines", "arguments": {"text": "# Spam policy\\nNo unsolicited bulk messages.", "title": "Community Guidelines"}},
    {"name": "verify_text", "arguments": {"text": "Spam section: no unsolicited bulk messages", "topic": "spam policy"}}
  ]
}
```""",
        chain="set_guidelines→verify_text",
    ))

    records.append(_rec(
        "Run a gray-zone duel on our harassment policy, 2 rounds.",
        """```json
{
  "tool_calls": [
    {"name": "run_duel_verification", "arguments": {"topic": "harassment policy gray zones", "rounds": 2}}
  ]
}
```""",
        chain="run_duel_verification",
    ))

    records.append(_rec(
        "Analyze Samsung vs SK Hynix and scan Korea market top movers.",
        """```json
{
  "tool_calls": [
    {"name": "analyze_stocks", "arguments": {"query": "Samsung vs SK Hynix investment memo with risks"}},
    {"name": "scan_market_region", "arguments": {"market": "Korea", "limit": 10}}
  ]
}
```""",
        chain="analyze_stocks→scan_market_region",
    ))

    records.append(_rec(
        "Check learning status and curate feedback without training yet.",
        """```json
{
  "tool_calls": [
    {"name": "learning_status", "arguments": {}},
    {"name": "run_continuous_learning", "arguments": {"train": false}}
  ]
}
```""",
        chain="learning_status→run_continuous_learning",
    ))

    records.append(_rec(
        "Get active guidelines, append a gray-zone note, then chat in Jekyll mode.",
        """```json
{
  "tool_calls": [
    {"name": "get_guidelines", "arguments": {}},
    {"name": "append_guidelines", "arguments": {"text": "## Gray zones\\nAmbiguous satire vs harassment → flag for review."}},
    {"name": "chat_with_model", "arguments": {"message": "Summarize the new gray-zone rule", "jekyll": true, "hyde": false}}
  ]
}
```""",
        chain="get_guidelines→append_guidelines→chat_with_model",
    ))

    records.append(_rec(
        "Run gray-zone duel reinforcement on privacy policy loopholes.",
        """```json
{
  "tool_calls": [
    {"name": "run_gray_zone_duel", "arguments": {"topic": "privacy policy loopholes and gray zones", "rounds": 3}}
  ]
}
```""",
        chain="run_gray_zone_duel",
    ))

    records.append(_rec(
        "Pull this quarter IT sector gray zone report — delegate to workers then manager approve.",
        """```json
{
  "tool_calls": [
    {"name": "delegate_workforce_brief", "arguments": {"brief": "IT sector gray zone report this quarter"}},
    {"name": "workforce_status", "arguments": {"job_id": "JOB_ID"}},
    {"name": "manager_approve_workforce", "arguments": {"job_id": "JOB_ID"}}
  ]
}
```""",
        chain="delegate_workforce_brief→workforce_status→manager_approve_workforce",
    ))

    return records
