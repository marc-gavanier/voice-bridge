def must_delegate(tool: str, *, subagent: bool, allowed: frozenset[str]) -> bool:
    return not subagent and tool not in allowed
