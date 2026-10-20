"""Small, account-owned avatars stored with the application database."""
from sqlalchemy import ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class UserAvatar(Base):
    __tablename__ = "user_avatars"
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    image: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
