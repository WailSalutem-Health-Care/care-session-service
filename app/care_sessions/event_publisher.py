"""Event publisher for care sessions"""
from app.messaging.rabbitmq import RabbitMQPublisher
from app.care_sessions.schemas import CareSessionResponse


class SessionEventPublisher:
    """Publishes care session events"""

    def __init__(self, tenant_schema: str):
        self.tenant_schema = tenant_schema
        self.publisher = RabbitMQPublisher()

    def publish_session_created(self, session):
        """Publish session created event"""
        session_response = CareSessionResponse.from_orm(session)
        message = {
            "event": "session.created",
            "tenant": self.tenant_schema,
            "data": session_response.dict()
        }
        self.publisher.publish("session.created", message)

    def publish_session_completed(self, session):
        """Publish session completed event"""
        session_response = CareSessionResponse.from_orm(session)
        message = {
            "event": "session.completed",
            "tenant": self.tenant_schema,
            "data": session_response.dict()
        }
        self.publisher.publish("session.completed", message)