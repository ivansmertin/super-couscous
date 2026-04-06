from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AdminRelayMap, InboundMessage, User


@dataclass(slots=True)
class DialogSummary:
    total_messages: int
    last_message_at: datetime | None
    last_message_type: str | None


class Storage:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def upsert_user(self, telegram_id: int, full_name: str, username: str | None) -> None:
        with self._session_factory() as session:
            existing = session.get(User, telegram_id)
            if existing:
                existing.full_name = full_name
                existing.username = username
                existing.last_seen_at = datetime.now(timezone.utc)
            else:
                existing = User(
                    telegram_id=telegram_id,
                    full_name=full_name,
                    username=username,
                    first_seen_at=datetime.now(timezone.utc),
                    last_seen_at=datetime.now(timezone.utc),
                )
                session.add(existing)
            session.commit()

    def save_inbound_message(
        self,
        telegram_user_id: int,
        user_message_id: int,
        message_type: str,
    ) -> None:
        with self._session_factory() as session:
            item = InboundMessage(
                telegram_user_id=telegram_user_id,
                user_message_id=user_message_id,
                message_type=message_type,
            )
            session.add(item)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()

    def save_admin_relay_mapping(self, admin_message_id: int, target_user_id: int) -> None:
        with self._session_factory() as session:
            mapping = AdminRelayMap(
                admin_message_id=admin_message_id,
                target_user_id=target_user_id,
            )
            session.add(mapping)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()

    def resolve_user_id_by_admin_message_id(self, admin_message_id: int) -> int | None:
        with self._session_factory() as session:
            stmt = select(AdminRelayMap.target_user_id).where(
                AdminRelayMap.admin_message_id == admin_message_id
            )
            return session.execute(stmt).scalar_one_or_none()

    def should_send_confirmation(
        self,
        telegram_user_id: int,
        inactivity_minutes: int = 60,
    ) -> bool:
        with self._session_factory() as session:
            user = session.get(User, telegram_user_id)
            if not user:
                return True
            if user.last_confirmation_at is None:
                return True
            now = datetime.now(timezone.utc)
            threshold = now - timedelta(minutes=inactivity_minutes)
            return user.last_confirmation_at < threshold

    def mark_confirmation_sent(self, telegram_user_id: int) -> None:
        with self._session_factory() as session:
            user = session.get(User, telegram_user_id)
            if user:
                user.last_confirmation_at = datetime.now(timezone.utc)
                session.commit()

    def count_users(self) -> int:
        with self._session_factory() as session:
            return session.query(User).count()

    def list_user_ids(self) -> list[int]:
        with self._session_factory() as session:
            rows = session.scalars(select(User.telegram_id)).all()
            return list(rows)

    def count_dialogs(self) -> int:
        return self.count_users()

    def list_recent_dialogs(self, limit: int, offset: int = 0) -> list[User]:
        with self._session_factory() as session:
            stmt = (
                select(User)
                .order_by(User.last_seen_at.desc(), User.telegram_id.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(session.scalars(stmt).all())

    def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        with self._session_factory() as session:
            return session.get(User, telegram_id)

    def get_dialog_summary(self, telegram_user_id: int) -> DialogSummary:
        with self._session_factory() as session:
            summary_stmt = select(
                func.count(InboundMessage.id),
                func.max(InboundMessage.created_at),
            ).where(InboundMessage.telegram_user_id == telegram_user_id)
            total_messages, last_message_at = session.execute(summary_stmt).one()

            last_type_stmt = (
                select(InboundMessage.message_type)
                .where(InboundMessage.telegram_user_id == telegram_user_id)
                .order_by(InboundMessage.created_at.desc(), InboundMessage.id.desc())
                .limit(1)
            )
            last_message_type = session.execute(last_type_stmt).scalar_one_or_none()

            return DialogSummary(
                total_messages=int(total_messages or 0),
                last_message_at=last_message_at,
                last_message_type=last_message_type,
            )
