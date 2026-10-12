"""Tests for RSS subscriptions, XML parsing, regex filtering, preview, and deduplication."""

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import get_current_user
from app.core.config import Settings
from app.core.db import get_db_session
from app.main import create_app
from app.models.user import User
from app.services.rss import RssService
from tests.fakes.fake_db import FakeAsyncSession

SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Linux Distro Releases</title>
    <link>https://distro.example.org</link>
    <item>
      <title>Ubuntu 24.04.1 Desktop (amd64)</title>
      <link>magnet:?xt=urn:btih:ubuntu2404desktopamd64&amp;dn=ubuntu.iso</link>
      <guid>ubuntu-24-04-1-desktop-amd64</guid>
    </item>
    <item>
      <title>Ubuntu 24.04.1 Server (arm64)</title>
      <link>magnet:?xt=urn:btih:ubuntu2404serverarm64&amp;dn=ubuntu-arm.iso</link>
      <guid>ubuntu-24-04-1-server-arm64</guid>
    </item>
    <item>
      <title>Fedora 40 Workstation (x86_64)</title>
      <enclosure
        url="https://download.fedoraproject.org/fedora40.iso"
        length="2147483648"
        type="application/x-iso9660-image" />
      <guid>fedora-40-workstation</guid>
    </item>
  </channel>
</rss>
"""

SAMPLE_ATOM_XML = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Sample Atom Feed</title>
  <entry>
    <title>Arch Linux 2026.10 ISO</title>
    <id>arch-2026-10</id>
    <link rel="enclosure" href="https://archlinux.org/iso/arch.iso" />
  </entry>
</feed>
"""


@pytest.fixture
def fake_db() -> FakeAsyncSession:
    return FakeAsyncSession()


@pytest.fixture
def test_user(fake_db: FakeAsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        google_sub="sub-rss-test",
        email="rssuser@example.com",
        created_at=datetime.now(UTC),
    )
    fake_db.add(user)
    return user


def test_rss_and_atom_xml_parsing() -> None:
    """Test extracting items, magnet links, and enclosures from RSS 2.0 and Atom feeds."""
    service = RssService()

    # RSS 2.0
    feed_title, items = service.parse_feed_xml(SAMPLE_RSS_XML)
    assert feed_title == "Linux Distro Releases"
    assert len(items) == 3
    assert items[0]["title"] == "Ubuntu 24.04.1 Desktop (amd64)"
    assert items[0]["link"].startswith("magnet:?xt=urn:btih:ubuntu2404desktopamd64")
    assert items[0]["guid"] == "ubuntu-24-04-1-desktop-amd64"
    assert items[2]["link"] == "https://download.fedoraproject.org/fedora40.iso"

    # Atom
    atom_title, atom_items = service.parse_feed_xml(SAMPLE_ATOM_XML)
    assert atom_title == "Sample Atom Feed"
    assert len(atom_items) == 1
    assert atom_items[0]["title"] == "Arch Linux 2026.10 ISO"
    assert atom_items[0]["link"] == "https://archlinux.org/iso/arch.iso"


@pytest.mark.asyncio
async def test_rss_crud_api(fake_db: FakeAsyncSession, test_user: User) -> None:
    """Test POST, GET, and DELETE /api/rss endpoints."""
    app = create_app(Settings(DEBUG=True))
    app.dependency_overrides[get_db_session] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: test_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Create subscription
        create_resp = await client.post(
            "/api/rss",
            json={
                "name": "Ubuntu Desktop ISOs",
                "url": "https://distro.example.org/rss.xml",
                "filter_regex": r"(?i)ubuntu.*amd64",
            },
        )
        assert create_resp.status_code == 201
        data = create_resp.json()
        assert data["name"] == "Ubuntu Desktop ISOs"
        assert data["filter_regex"] == r"(?i)ubuntu.*amd64"
        sub_id = data["id"]

        # List subscriptions
        list_resp = await client.get("/api/rss")
        assert list_resp.status_code == 200
        subs = list_resp.json()
        assert len(subs) == 1
        assert subs[0]["id"] == sub_id

        # Delete subscription
        del_resp = await client.delete(f"/api/rss/{sub_id}")
        assert del_resp.status_code == 204

        # List again -> empty
        list_resp2 = await client.get("/api/rss")
        assert list_resp2.status_code == 200
        assert len(list_resp2.json()) == 0


@pytest.mark.asyncio
async def test_rss_preview_endpoint(test_user: User) -> None:
    """Test previewing feed and regex matches without persisting to DB."""
    app = create_app(Settings(DEBUG=True))
    app.dependency_overrides[get_current_user] = lambda: test_user

    service = RssService()

    def mock_fetch(url: str, **kwargs):
        return httpx.Response(200, text=SAMPLE_RSS_XML)

    transport = httpx.MockTransport(mock_fetch)
    mock_client = httpx.AsyncClient(transport=transport)

    feed_title, total, items = await service.preview_feed(
        url="https://test.org/rss",
        filter_regex=r"(?i)ubuntu.*amd64",
        allow_local=True,
        client=mock_client,
    )

    assert feed_title == "Linux Distro Releases"
    assert total == 3
    # First item matches amd64, second is arm64, third is fedora
    assert items[0]["is_match"] is True
    assert items[1]["is_match"] is False
    assert items[2]["is_match"] is False


@pytest.mark.asyncio
async def test_rss_sync_and_deduplication(fake_db: FakeAsyncSession, test_user: User) -> None:
    """Test syncing subscription auto-creates tasks and deduplicates on subsequent runs."""
    from app.services.task import TaskService

    rss_service = RssService()
    task_service = TaskService()

    sub = await rss_service.create_subscription(
        db=fake_db,
        user_id=test_user.id,
        name="Ubuntu Tracker",
        url="https://distro.example.org/rss.xml",
        filter_regex=r"(?i)ubuntu",
        allow_local=True,
    )

    def mock_fetch(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SAMPLE_RSS_XML)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_fetch))

    # First sync: 2 items match (?i)ubuntu
    total, created, task_ids = await rss_service.sync_subscription(
        db=fake_db,
        user=test_user,
        subscription_id=sub.id,
        task_service=task_service,
        allow_local=True,
        client=mock_client,
    )

    assert total == 3
    assert created == 2
    assert len(task_ids) == 2
    assert len(fake_db.tasks) == 2

    # Second sync: items are already in seen_guids -> 0 tasks created
    total2, created2, task_ids2 = await rss_service.sync_subscription(
        db=fake_db,
        user=test_user,
        subscription_id=sub.id,
        task_service=task_service,
        allow_local=True,
        client=mock_client,
    )

    assert total2 == 3
    assert created2 == 0
    assert len(task_ids2) == 0
    assert len(fake_db.tasks) == 2
