"""Service managing RSS subscriptions, XML parsing, regex filtering, and automated downloads."""

import logging
import re
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ssrf import SSRFError, validate_url
from app.models.rss import RssFeedItem, RssSubscription
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreateRequest
from app.services.task import TaskService

logger = logging.getLogger(__name__)


class RssService:
    """Manages RSS feed polling, XML parsing, regex filtering, and task creation."""

    @staticmethod
    def _strip_tag(tag: str) -> str:
        """Strip XML namespace prefix from element tag."""
        return tag.split("}")[-1] if "}" in tag else tag

    @classmethod
    def parse_feed_xml(cls, xml_text: str) -> tuple[str | None, list[dict[str, Any]]]:
        """Parse RSS 2.0 or Atom feed XML into structured item dictionaries."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as err:
            raise ValueError(f"Malformed XML feed: {err}") from err

        root_tag = cls._strip_tag(root.tag).lower()
        items: list[dict[str, Any]] = []
        feed_title: str | None = None

        if root_tag == "rss":
            # RSS 2.0 standard
            channel = next(
                (child for child in root if cls._strip_tag(child.tag).lower() == "channel"), None
            )
            if channel is not None:
                for child in channel:
                    tag_name = cls._strip_tag(child.tag).lower()
                    if tag_name == "title" and feed_title is None:
                        feed_title = (child.text or "").strip()
                    elif tag_name == "item":
                        item_dict = cls._parse_rss_item(child)
                        if item_dict.get("link"):
                            items.append(item_dict)
        elif root_tag == "feed":
            # Atom standard
            for child in root:
                tag_name = cls._strip_tag(child.tag).lower()
                if tag_name == "title" and feed_title is None:
                    feed_title = (child.text or "").strip()
                elif tag_name == "entry":
                    item_dict = cls._parse_atom_entry(child)
                    if item_dict.get("link"):
                        items.append(item_dict)
        else:
            # Fallback scan for any <item> or <entry> tags
            for elem in root.iter():
                tag_name = cls._strip_tag(elem.tag).lower()
                if tag_name == "item":
                    item_dict = cls._parse_rss_item(elem)
                    if item_dict.get("link"):
                        items.append(item_dict)
                elif tag_name == "entry":
                    item_dict = cls._parse_atom_entry(elem)
                    if item_dict.get("link"):
                        items.append(item_dict)

        return feed_title, items

    @classmethod
    def _parse_rss_item(cls, item_elem: ET.Element) -> dict[str, Any]:
        """Extract title, link, and guid from RSS <item>."""
        title = ""
        link = ""
        guid = ""

        for child in item_elem:
            tag = cls._strip_tag(child.tag).lower()
            if tag == "title":
                title = (child.text or "").strip()
            elif tag == "link" and not link:
                text_link = (child.text or "").strip()
                if text_link:
                    link = text_link
            elif tag == "enclosure":
                enc_url = child.attrib.get("url")
                if enc_url:
                    link = enc_url.strip()
            elif "magneturi" in tag:
                magnet_text = (child.text or "").strip()
                if magnet_text:
                    link = magnet_text
            elif tag == "guid":
                guid = (child.text or "").strip()

        if not guid:
            guid = link or title

        return {"title": title, "link": link, "guid": guid}

    @classmethod
    def _parse_atom_entry(cls, entry_elem: ET.Element) -> dict[str, Any]:
        """Extract title, link, and id from Atom <entry>."""
        title = ""
        link = ""
        entry_id = ""

        for child in entry_elem:
            tag = cls._strip_tag(child.tag).lower()
            if tag == "title":
                title = (child.text or "").strip()
            elif tag == "id":
                entry_id = (child.text or "").strip()
            elif tag == "link":
                rel = child.attrib.get("rel", "alternate")
                href = child.attrib.get("href", "")
                if rel in ("enclosure", "alternate") and href and not link:
                    link = href.strip()

        if not entry_id:
            entry_id = link or title

        return {"title": title, "link": link, "guid": entry_id}

    async def fetch_feed(
        self,
        url: str,
        allow_local: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Fetch XML content from URL with SSRF checks and parse it."""
        try:
            await validate_url(url, allow_local=allow_local)
        except SSRFError as err:
            raise ValueError(f"Invalid feed URL: {err}") from err

        should_close = False
        http_client = client
        if http_client is None:
            http_client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
            should_close = True

        try:
            resp = await http_client.get(
                url,
                headers={
                    "User-Agent": "DriveSeed-RSS/1.0",
                    "Accept": (
                        "application/rss+xml, application/atom+xml, application/xml, text/xml"
                    ),
                },
            )
            if not resp.is_success:
                raise ValueError(f"Failed to fetch feed: HTTP {resp.status_code}")
            return self.parse_feed_xml(resp.text)
        finally:
            if should_close and http_client:
                await http_client.aclose()

    async def create_subscription(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        name: str,
        url: str,
        filter_regex: str | None = None,
        allow_local: bool = False,
    ) -> RssSubscription:
        """Register a new RSS subscription."""
        try:
            await validate_url(url, allow_local=allow_local)
        except SSRFError as err:
            raise ValueError(f"Invalid feed URL: {err}") from err

        clean_regex = filter_regex.strip() if filter_regex and filter_regex.strip() else None
        if clean_regex:
            try:
                re.compile(clean_regex)
            except re.error as err:
                raise ValueError(f"Invalid regular expression: {err}") from err

        subscription = RssSubscription(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name.strip(),
            url=url.strip(),
            filter_regex=clean_regex,
            is_active=True,
            last_checked_at=None,
            last_item_title=None,
            created_at=datetime.now(UTC),
        )

        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)
        return subscription

    async def list_subscriptions(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> Sequence[RssSubscription]:
        """List all subscriptions configured by user."""
        stmt = (
            select(RssSubscription)
            .where(RssSubscription.user_id == user_id)
            .order_by(RssSubscription.created_at.desc())
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    async def delete_subscription(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        subscription_id: uuid.UUID,
    ) -> bool:
        """Delete an RSS subscription and cascade delete its processed item records."""
        stmt = select(RssSubscription).where(
            RssSubscription.id == subscription_id,
            RssSubscription.user_id == user_id,
        )
        res = await db.execute(stmt)
        sub = res.scalar_one_or_none()

        if sub is None:
            return False

        await db.delete(sub)
        await db.commit()
        return True

    async def preview_feed(
        self,
        url: str,
        filter_regex: str | None = None,
        allow_local: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> tuple[str | None, int, list[dict[str, Any]]]:
        """Fetch feed and evaluate regex filter against items without saving."""
        feed_title, items = await self.fetch_feed(url, allow_local=allow_local, client=client)

        pattern = None
        if filter_regex and filter_regex.strip():
            try:
                pattern = re.compile(filter_regex.strip())
            except re.error as err:
                raise ValueError(f"Invalid regular expression: {err}") from err

        previews: list[dict[str, Any]] = []
        for itm in items:
            title = itm["title"]
            is_match = bool(pattern.search(title)) if pattern else True
            previews.append(
                {
                    "title": title,
                    "link": itm["link"],
                    "is_match": is_match,
                }
            )

        return feed_title, len(items), previews

    async def sync_subscription(
        self,
        db: AsyncSession,
        user: User,
        subscription_id: uuid.UUID,
        task_service: TaskService,
        allow_local: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> tuple[int, int, list[uuid.UUID]]:
        """Poll feed, find new matching items, and automatically create download tasks."""
        stmt = select(RssSubscription).where(
            RssSubscription.id == subscription_id,
            RssSubscription.user_id == user.id,
        )
        res = await db.execute(stmt)
        sub = res.scalar_one_or_none()

        if sub is None or not sub.is_active:
            return 0, 0, []

        feed_title, items = await self.fetch_feed(sub.url, allow_local=allow_local, client=client)

        pattern = None
        if sub.filter_regex:
            pattern = re.compile(sub.filter_regex)

        # Query seen items for deduplication
        seen_stmt = select(RssFeedItem).where(RssFeedItem.subscription_id == sub.id)
        seen_res = await db.execute(seen_stmt)
        seen_guids = {item.guid for item in seen_res.scalars().all()}

        # Also query user tasks to deduplicate by source_uri
        user_tasks_stmt = select(Task).where(Task.user_id == user.id)
        user_tasks_res = await db.execute(user_tasks_stmt)
        existing_uris = {t.source_uri for t in user_tasks_res.scalars().all()}

        created_task_ids: list[uuid.UUID] = []
        latest_matched_title: str | None = None

        for itm in items:
            title = itm["title"]
            link = itm["link"]
            guid = itm["guid"]

            is_match = bool(pattern.search(title)) if pattern else True
            if not is_match:
                continue

            if latest_matched_title is None:
                latest_matched_title = title

            # Deduplication check
            if guid in seen_guids or link in existing_uris:
                continue

            # Create download task
            try:
                task = await task_service.create_task(
                    db=db,
                    user=user,
                    request=TaskCreateRequest(source_uri=link, name=title),
                )
                created_task_ids.append(task.id)
                seen_guids.add(guid)
                existing_uris.add(link)

                # Record seen item
                seen_record = RssFeedItem(
                    id=uuid.uuid4(),
                    subscription_id=sub.id,
                    guid=guid,
                    title=title,
                    created_at=datetime.now(UTC),
                )
                db.add(seen_record)
            except Exception as err:
                logger.error("Failed to auto-create task for RSS item '%s': %s", title, err)

        # Update subscription status
        sub.last_checked_at = datetime.now(UTC)
        if latest_matched_title:
            sub.last_item_title = latest_matched_title
        await db.commit()

        return len(items), len(created_task_ids), created_task_ids
