"""Task state machine enforcing valid transitions according to ARCHITECTURE.md."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import ClassVar

from app.models.task import Task


class TaskState(StrEnum):
    """Lifecycle states of a download task."""

    QUEUED = "queued"
    FETCHING_METADATA = "fetching_metadata"
    AWAITING_SELECTION = "awaiting_selection"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InvalidStateTransitionError(Exception):
    """Exception raised when an illegal task state transition is attempted."""

    def __init__(self, current_state: str, target_state: str) -> None:
        self.current_state = current_state
        self.target_state = target_state
        super().__init__(f"Cannot transition task from '{current_state}' to '{target_state}'.")


class TaskStateMachine:
    """State machine governing task lifecycle transitions."""

    # Explicit transition mapping derived from ARCHITECTURE.md Section 4
    ALLOWED_TRANSITIONS: ClassVar[dict[TaskState, set[TaskState]]] = {
        TaskState.QUEUED: {
            TaskState.FETCHING_METADATA,
            TaskState.DOWNLOADING,  # direct downloads bypassing metadata phase
            TaskState.CANCELLED,
            TaskState.FAILED,
        },
        TaskState.FETCHING_METADATA: {
            TaskState.AWAITING_SELECTION,
            TaskState.DOWNLOADING,
            TaskState.CANCELLED,
            TaskState.FAILED,
        },
        TaskState.AWAITING_SELECTION: {
            TaskState.DOWNLOADING,
            TaskState.CANCELLED,
            TaskState.FAILED,
        },
        TaskState.DOWNLOADING: {
            TaskState.PAUSED,
            TaskState.UPLOADING,
            TaskState.COMPLETED,
            TaskState.CANCELLED,
            TaskState.FAILED,
        },
        TaskState.PAUSED: {
            TaskState.DOWNLOADING,
            TaskState.CANCELLED,
            TaskState.FAILED,
        },
        TaskState.UPLOADING: {
            TaskState.COMPLETED,
            TaskState.CANCELLED,
            TaskState.FAILED,
        },
        # Terminal / final states
        TaskState.COMPLETED: set(),
        TaskState.FAILED: {TaskState.QUEUED},  # retry transitions back to queued
        TaskState.CANCELLED: set(),
    }

    @classmethod
    def can_transition(cls, current: TaskState | str, target: TaskState | str) -> bool:
        """Return True if transition from current to target is allowed."""
        try:
            current_state = TaskState(current)
            target_state = TaskState(target)
        except ValueError:
            return False

        allowed = cls.ALLOWED_TRANSITIONS.get(current_state, set())
        return target_state in allowed

    @classmethod
    def transition(
        cls,
        task: Task,
        target: TaskState | str,
        error_message: str | None = None,
    ) -> Task:
        """Validate and apply state transition to a Task entity."""
        target_state = TaskState(target)
        current_state = TaskState(task.state)

        if not cls.can_transition(current_state, target_state):
            raise InvalidStateTransitionError(current_state.value, target_state.value)

        task.state = target_state.value

        # Handle terminal completion timestamps and error payloads
        if target_state in (TaskState.COMPLETED, TaskState.CANCELLED, TaskState.FAILED):
            task.completed_at = datetime.now(UTC)

        if target_state == TaskState.FAILED:
            task.error = error_message
        elif target_state == TaskState.COMPLETED:
            task.progress = 1.0

        return task
