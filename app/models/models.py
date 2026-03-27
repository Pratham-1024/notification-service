from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from app.core.database import Base



class User(Base):
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    notifications = relationship("Notification", back_populates="user")



class Template(Base):
    __tablename__ = 'templates'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    channel = Column(String, nullable=False)
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


    notifications = relationship("Notification", back_populates="template")


class Notification(Base):
    __tablename__ = 'notifications'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel = Column(String, nullable=False)
    recipient = Column(String)
    variables = Column(JSON,nullable=True)
    sent_at = Column(DateTime, nullable=True)
    idempotency_key = Column(String, unique=True, nullable=False)
    scheduled_at = Column(DateTime, nullable=True)
    status= Column(String,default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=False)


    user = relationship("User", back_populates="notifications")

    template = relationship("Template", back_populates="notifications")

    delivery_logs = relationship("DeliveryLog", back_populates="notification")


class DeliveryLog(Base):
    __tablename__ = 'delivery_logs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_number = Column(Integer)
    status = Column(String)
    error_message = Column(Text, nullable=True)
    attempted_at = Column(DateTime, default=datetime.utcnow)

    notification_id = Column(UUID(as_uuid=True), ForeignKey("notifications.id"), nullable=False)


    notification = relationship("Notification", back_populates="delivery_logs")


