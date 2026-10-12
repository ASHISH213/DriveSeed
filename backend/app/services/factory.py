"""Service factory module for profile-aware component creation."""

from app.core.config import Settings, get_settings
from app.interfaces.queue import TaskQueue
from app.interfaces.storage import StorageBackend

_inprocess_queue_singleton: TaskQueue | None = None


def get_storage_backend(settings: Settings | None = None) -> StorageBackend:
    """Return appropriate StorageBackend based on runtime PROFILE."""
    current_settings = settings or get_settings()
    if current_settings.PROFILE == "colab":
        from app.services.mounted_drive import MountedDriveStorage

        return MountedDriveStorage(settings=current_settings)

    from app.services.drive import DriveApiStorage

    return DriveApiStorage(settings=current_settings)


def get_task_queue(settings: Settings | None = None) -> TaskQueue:
    """Return appropriate TaskQueue based on runtime PROFILE."""
    global _inprocess_queue_singleton
    current_settings = settings or get_settings()
    if current_settings.PROFILE == "colab":
        if _inprocess_queue_singleton is None:
            from app.services.inprocess_queue import InProcessQueue

            _inprocess_queue_singleton = InProcessQueue()
        return _inprocess_queue_singleton

    from app.services.queue import ArqTaskQueue

    return ArqTaskQueue(settings=current_settings)
