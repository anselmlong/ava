"""User repository for database operations."""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User, AccessRequest, UserStatus, AccessRequestStatus


class UserRepository:
    """Repository for User-related database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by database ID."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: Optional[str] = None,
        status: str = UserStatus.PENDING.value,
    ) -> User:
        """Create a new user."""
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
            status=status,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_or_create(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: Optional[str] = None,
        auto_approve: bool = False,
    ) -> tuple[User, bool]:
        """Get existing user or create a new one.

        Returns:
            Tuple of (user, created) where created is True if user was newly created
        """
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            # Update user info if changed
            updated = False
            if username and user.username != username:
                user.username = username
                updated = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                updated = True
            if language_code and user.language_code != language_code:
                user.language_code = language_code
                updated = True
            if updated:
                user.updated_at = datetime.now(timezone.utc)
            return user, False

        # Create new user
        status = UserStatus.APPROVED.value if auto_approve else UserStatus.PENDING.value
        user = await self.create(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
            status=status,
        )
        return user, True

    async def approve(
        self,
        user_id: int,
        approved_by: Optional[int] = None,
    ) -> Optional[User]:
        """Approve a user."""
        user = await self.get_by_id(user_id)
        if not user:
            return None

        user.status = UserStatus.APPROVED.value
        user.approved_by = approved_by
        user.approved_at = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)
        return user

    async def approve_by_telegram_id(
        self,
        telegram_id: int,
        approved_by: Optional[int] = None,
    ) -> Optional[User]:
        """Approve a user by Telegram ID."""
        user = await self.get_by_telegram_id(telegram_id)
        if not user:
            return None

        user.status = UserStatus.APPROVED.value
        user.approved_by = approved_by
        user.approved_at = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)
        return user

    async def suspend(self, user_id: int) -> Optional[User]:
        """Suspend a user."""
        user = await self.get_by_id(user_id)
        if not user:
            return None

        user.status = UserStatus.SUSPENDED.value
        user.updated_at = datetime.now(timezone.utc)
        return user

    async def ban(self, user_id: int) -> Optional[User]:
        """Ban a user."""
        user = await self.get_by_id(user_id)
        if not user:
            return None

        user.status = UserStatus.BANNED.value
        user.updated_at = datetime.now(timezone.utc)
        return user

    async def update_activity(self, user_id: int) -> None:
        """Update user's last activity timestamp and increment message count."""
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                last_active=datetime.now(timezone.utc),
                last_message_at=datetime.now(timezone.utc),
                message_count=User.message_count + 1,
            )
        )

    async def get_pending_users(self) -> List[User]:
        """Get all users with pending status."""
        result = await self.session.execute(
            select(User)
            .where(User.status == UserStatus.PENDING.value)
            .order_by(User.created_at.desc())
        )
        return list(result.scalars().all())

    async def count_by_status(self, status: str) -> int:
        """Count users by status."""
        result = await self.session.execute(
            select(func.count(User.id)).where(User.status == status)
        )
        return result.scalar_one()

    # Access Request operations
    async def create_access_request(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> AccessRequest:
        """Create an access request."""
        request = AccessRequest(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            reason=reason,
        )
        self.session.add(request)
        await self.session.flush()
        return request

    async def get_pending_access_requests(self) -> List[AccessRequest]:
        """Get all pending access requests."""
        result = await self.session.execute(
            select(AccessRequest)
            .where(AccessRequest.status == AccessRequestStatus.PENDING.value)
            .order_by(AccessRequest.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_access_request_by_telegram_id(
        self,
        telegram_id: int,
    ) -> Optional[AccessRequest]:
        """Get the latest access request for a Telegram ID."""
        result = await self.session.execute(
            select(AccessRequest)
            .where(AccessRequest.telegram_id == telegram_id)
            .order_by(AccessRequest.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def approve_access_request(
        self,
        request_id: int,
        reviewed_by: Optional[int] = None,
    ) -> Optional[AccessRequest]:
        """Approve an access request."""
        result = await self.session.execute(
            select(AccessRequest).where(AccessRequest.id == request_id)
        )
        request = result.scalar_one_or_none()
        if not request:
            return None

        request.status = AccessRequestStatus.APPROVED.value
        request.reviewed_by = reviewed_by
        request.reviewed_at = datetime.now(timezone.utc)
        return request

    async def reject_access_request(
        self,
        request_id: int,
        reviewed_by: Optional[int] = None,
        rejection_reason: Optional[str] = None,
    ) -> Optional[AccessRequest]:
        """Reject an access request."""
        result = await self.session.execute(
            select(AccessRequest).where(AccessRequest.id == request_id)
        )
        request = result.scalar_one_or_none()
        if not request:
            return None

        request.status = AccessRequestStatus.REJECTED.value
        request.reviewed_by = reviewed_by
        request.reviewed_at = datetime.now(timezone.utc)
        request.rejection_reason = rejection_reason
        return request
