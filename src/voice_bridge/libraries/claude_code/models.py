type ModelSettings = dict[str, str | dict[str, str]]


def model_settings(*, model: str | None, subagent_model: str | None) -> ModelSettings:
    main: ModelSettings = {} if model is None else {"model": model}
    subagents: ModelSettings = {} if subagent_model is None else {"env": {"CLAUDE_CODE_SUBAGENT_MODEL": subagent_model}}
    return {**main, **subagents}
