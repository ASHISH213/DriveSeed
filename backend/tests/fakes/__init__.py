"""Test fakes implementing application protocols."""

from tests.fakes.fake_download import FakeDownloadEngine
from tests.fakes.fake_queue import FakeTaskQueue
from tests.fakes.fake_redis import FakePubSub, FakeRedis
from tests.fakes.fake_storage import FakeStorageBackend
from tests.fakes.fake_streamer import FakeStreamer

__all__ = [
    "FakeDownloadEngine",
    "FakePubSub",
    "FakeRedis",
    "FakeStorageBackend",
    "FakeStreamer",
    "FakeTaskQueue",
]
