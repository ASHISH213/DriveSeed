"""Unit tests for TaskStateMachine transitions and constraints."""

import uuid
from datetime import UTC, datetime

import pytest

from app.models.task import Task
from app.services.task_state import (
    InvalidStateTransitionError,
    TaskState,
    TaskStateMachine,
)


@pytest.fixture
def sample_task() -> Task:
    """Fixture providing a fresh Task in QUEUED state."""
    return Task(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        source_type="magnet",
        source_uri="magnet:?xt=urn:btih:dummy123",
        name="Sample Torrent",
        state=TaskState.QUEUED.value,
        progress=0.0,
        created_at=datetime.now(UTC),
    )


def test_allowed_lifecycle_transitions(sample_task: Task) -> None:
    """Verify happy path from queued to completed."""
    # queued -> fetching_metadata
    TaskStateMachine.transition(sample_task, TaskState.FETCHING_METADATA)
    assert sample_task.state == TaskState.FETCHING_METADATA.value

    # fetching_metadata -> awaiting_selection
    TaskStateMachine.transition(sample_task, TaskState.AWAITING_SELECTION)
    assert sample_task.state == TaskState.AWAITING_SELECTION.value

    # awaiting_selection -> downloading
    TaskStateMachine.transition(sample_task, TaskState.DOWNLOADING)
    assert sample_task.state == TaskState.DOWNLOADING.value

    # downloading -> paused -> downloading
    TaskStateMachine.transition(sample_task, TaskState.PAUSED)
    assert sample_task.state == TaskState.PAUSED.value
    TaskStateMachine.transition(sample_task, TaskState.DOWNLOADING)
    assert sample_task.state == TaskState.DOWNLOADING.value

    # downloading -> uploading
    TaskStateMachine.transition(sample_task, TaskState.UPLOADING)
    assert sample_task.state == TaskState.UPLOADING.value

    # uploading -> completed
    TaskStateMachine.transition(sample_task, TaskState.COMPLETED)
    assert sample_task.state == TaskState.COMPLETED.value
    assert sample_task.completed_at is not None
    assert sample_task.progress == 1.0


def test_cancel_allowed_from_any_active_state(sample_task: Task) -> None:
    """Verify cancelling from active states."""
    for active_state in [
        TaskState.QUEUED,
        TaskState.FETCHING_METADATA,
        TaskState.AWAITING_SELECTION,
        TaskState.DOWNLOADING,
        TaskState.PAUSED,
        TaskState.UPLOADING,
    ]:
        sample_task.state = active_state.value
        sample_task.completed_at = None
        TaskStateMachine.transition(sample_task, TaskState.CANCELLED)
        assert sample_task.state == TaskState.CANCELLED.value
        assert sample_task.completed_at is not None


def test_fail_allowed_from_any_active_state(sample_task: Task) -> None:
    """Verify failing from active states records error message."""
    sample_task.state = TaskState.DOWNLOADING.value
    TaskStateMachine.transition(sample_task, TaskState.FAILED, error_message="Network drop")
    assert sample_task.state == TaskState.FAILED.value
    assert sample_task.error == "Network drop"
    assert sample_task.completed_at is not None


def test_forbidden_transitions(sample_task: Task) -> None:
    """Verify illegal transitions raise InvalidStateTransitionError."""
    # Cannot jump queued -> completed
    with pytest.raises(InvalidStateTransitionError):
        TaskStateMachine.transition(sample_task, TaskState.COMPLETED)

    # Cannot jump queued -> paused
    with pytest.raises(InvalidStateTransitionError):
        TaskStateMachine.transition(sample_task, TaskState.PAUSED)

    # Terminal state completed cannot transition anywhere
    sample_task.state = TaskState.COMPLETED.value
    for target in TaskState:
        if target != TaskState.COMPLETED:
            with pytest.raises(InvalidStateTransitionError):
                TaskStateMachine.transition(sample_task, target)

    # Terminal state cancelled cannot transition anywhere
    sample_task.state = TaskState.CANCELLED.value
    for target in TaskState:
        if target != TaskState.CANCELLED:
            with pytest.raises(InvalidStateTransitionError):
                TaskStateMachine.transition(sample_task, target)

    # Failed state can only transition to QUEUED (retry), all others raise
    sample_task.state = TaskState.FAILED.value
    TaskStateMachine.transition(sample_task, TaskState.QUEUED)
    assert sample_task.state == TaskState.QUEUED.value

    sample_task.state = TaskState.FAILED.value
    for target in TaskState:
        if target not in (TaskState.FAILED, TaskState.QUEUED):
            with pytest.raises(InvalidStateTransitionError):
                TaskStateMachine.transition(sample_task, target)
