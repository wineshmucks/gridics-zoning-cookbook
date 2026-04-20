from typing import Any
from types import SimpleNamespace

def _first_nonempty_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
    return None

def _get_run_context(target: Any = None, **kwargs: Any) -> Any:
    run_context = kwargs.get("run_context")
    if run_context is not None:
        return run_context
    existing = getattr(target, "run_context", None)
    if existing is not None:
        return existing
    if any(key in kwargs for key in ("metadata", "dependencies", "session_state")):
        return SimpleNamespace(
            metadata=kwargs.get("metadata") or {},
            dependencies=kwargs.get("dependencies") or {},
            session_state=kwargs.get("session_state") or {},
        )
    return None

def _get_client_id(run_context: Any, **kwargs: Any) -> str | None:
    dependencies = kwargs.get("dependencies")
    if not isinstance(dependencies, dict):
        dependencies = getattr(run_context, "dependencies", None)
    if not isinstance(dependencies, dict):
        return None
    client_id = dependencies.get("client_id")
    return client_id.strip() if isinstance(client_id, str) and client_id.strip() else None

def _get_conversation_id(run_context: Any, run_output: Any = None, **kwargs: Any) -> str | None:
    metadata = kwargs.get("metadata")
    if not isinstance(metadata, dict):
        metadata = getattr(run_context, "metadata", None)

    metadata_conversation_id = None
    metadata_session_id = None
    metadata_thread_id = None
    metadata_message_id = None
    metadata_run_id = None
    if isinstance(metadata, dict):
        metadata_conversation_id = metadata.get("conversation_id")
        metadata_session_id = metadata.get("session_id")
        metadata_thread_id = metadata.get("thread_id")
        metadata_message_id = metadata.get("message_id")
        metadata_run_id = metadata.get("run_id")

    return _first_nonempty_string(
        metadata_conversation_id,
        metadata_session_id,
        metadata_thread_id,
        getattr(run_context, "conversation_id", None),
        getattr(run_context, "session_id", None),
        getattr(run_context, "thread_id", None),
        getattr(run_output, "conversation_id", None),
        getattr(run_output, "session_id", None),
    )