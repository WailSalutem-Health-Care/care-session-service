"""Event publishing for care sessions"""
from app.db.models import CareSession
from app.messaging.rabbitmq import publish_care_session_event


class SessionEventPublisher:
    """Publishes care session events to RabbitMQ"""
    
    def __init__(self, tenant_schema: str):
        self.tenant_schema = tenant_schema
    
    def publish_session_created(self, session: CareSession) -> None:
        """Publish session.created event"""
        self._publish_event('session.created', session)
    
    def publish_session_completed(self, session: CareSession) -> None:
        """Publish session.completed event"""
        self._publish_event('session.completed', session)
    
    def _publish_event(self, event_type: str, session: CareSession) -> None:
        """Publish care session event to RabbitMQ"""
        session_data = {
            'id': str(session.id),
            'patient_id': str(session.patient_id),
            'caregiver_id': str(session.caregiver_id),
            'check_in_time': session.check_in_time.isoformat() if session.check_in_time else None,
            'check_out_time': session.check_out_time.isoformat() if session.check_out_time else None,
            'status': session.status,
        }
        
        if session.caregiver_notes:
            session_data['caregiver_notes'] = session.caregiver_notes
        
        publish_care_session_event(
            event_type=event_type,
            session_data=session_data,
            tenant_schema=self.tenant_schema
        )
