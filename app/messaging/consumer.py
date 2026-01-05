import os
import json
import asyncio
import pika
import logging
from uuid import UUID
from datetime import datetime, date
from typing import Dict, Optional
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from app.db.postgres import AsyncSessionLocal
from app.db.models import Patient, User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NFCEventConsumer:
    
    def __init__(self):
        self.host = os.getenv("RABBITMQ_HOST")
        self.port = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.user = os.getenv("RABBITMQ_USER")
        self.password = os.getenv("RABBITMQ_PASSWORD")
        self.nfc_exchange = os.getenv("RABBITMQ_NFC_EXCHANGE", "nfc.events")
        self.connection = None
        self.channel = None
        
    def connect(self):
        credentials = pika.PlainCredentials(self.user, self.password)
        parameters = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
        
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        
        self.channel.exchange_declare(
            exchange=self.nfc_exchange,
            exchange_type='topic',
            durable=True
        )
        
        queue_name = 'care_session_nfc_events'
        self.channel.queue_declare(queue=queue_name, durable=True)
        
        self.channel.queue_bind(
            exchange=self.nfc_exchange,
            queue=queue_name,
            routing_key='nfc.resolved'
        )
        
        self.channel.queue_bind(
            exchange=self.nfc_exchange,
            queue=queue_name,
            routing_key='nfc.assigned'
        )
        
        return queue_name
    
    def process_nfc_resolved(self, event_data: Dict):
        """Process NFC tag scan events for auditing purposes."""
        try:
            tag_id = event_data.get('tag_id')
            patient_id = event_data.get('patient_id')
            org_id = event_data.get('organization_id')
            
            logger.info(f"NFC tag scanned - Tag: {tag_id}, Patient: {patient_id}, Org: {org_id}")
            
        except Exception as e:
            logger.error(f"Error processing nfc.resolved event: {e}")
    
    def process_nfc_assigned(self, event_data: Dict):
        """Process NFC tag assignment events."""
        try:
            tag_id = event_data.get('tag_id')
            patient_id = event_data.get('patient_id')
            
            logger.info(f"NFC tag assigned - Tag: {tag_id}, Patient: {patient_id}")
            
        except Exception as e:
            logger.error(f"Error processing nfc.assigned event: {e}")
    
    def callback(self, ch, method, properties, body):
        """Process incoming messages from the queue."""
        try:
            message = json.loads(body)
            event_type = message.get('event')
            
            if event_type == 'nfc.resolved':
                self.process_nfc_resolved(message)
            elif event_type == 'nfc.assigned':
                self.process_nfc_assigned(message)
            else:
                logger.warning(f"Unknown event type: {event_type}")
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def start_consuming(self):
        """Start consuming messages from RabbitMQ."""
        try:
            queue_name = self.connect()
            
            logger.info("="*60)
            logger.info("Care Session Service - NFC Event Consumer")
            logger.info(f"Connected to RabbitMQ: {self.host}:{self.port}")
            logger.info(f"Listening to queue: {queue_name}")
            logger.info(f"Routing keys: nfc.resolved, nfc.assigned")
            logger.info("="*60)
            
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=self.callback
            )
            
            self.channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("Stopping consumer...")
            self.stop()
        except Exception as e:
            logger.error(f"Consumer error: {e}")
            self.stop()
            raise
    
    def stop(self):
        """Stop consuming and close connections."""
        if self.channel and not self.channel.is_closed:
            self.channel.stop_consuming()
            self.channel.close()
        if self.connection and not self.connection.is_closed:
            self.connection.close()
        logger.info("Consumer stopped")


def start_consumer():
    """Entry point for starting the NFC event consumer."""
    consumer = NFCEventConsumer()
    consumer.start_consuming()




class OrganizationEventConsumer:
    
    def __init__(self):
        self.host = os.getenv("RABBITMQ_HOST")
        self.port = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.user = os.getenv("RABBITMQ_USER")
        self.password = os.getenv("RABBITMQ_PASSWORD")
        self.org_exchange = os.getenv("RABBITMQ_ORG_EXCHANGE", "wailsalutem.events")
        self.connection = None
        self.channel = None
        self.routing_keys = [
            "patient.created",
            "patient.deleted",
            "patient.status_changed",
            "user.created",
            "user.deleted",
            "user.status_changed",
            "user.role_changed",
        ]
    
    def connect(self):
        credentials = pika.PlainCredentials(self.user, self.password)
        parameters = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
        
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        
        self.channel.exchange_declare(
            exchange=self.org_exchange,
            exchange_type='topic',
            durable=True
        )
        
        queue_name = 'care_session_org_events'
        self.channel.queue_declare(queue=queue_name, durable=True)
        
        for routing_key in self.routing_keys:
            self.channel.queue_bind(
                exchange=self.org_exchange,
                queue=queue_name,
                routing_key=routing_key
            )
        
        return queue_name
    
    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    
    def _parse_date(self, value: Optional[str]) -> Optional[date]:
        if not value:
            return None
        return date.fromisoformat(value)
    
    def _get_value(self, data: Dict, *keys: str):
        for key in keys:
            if key in data and data[key] is not None:
                return data[key]
        return None
    
    def _schema_from_org(self, event_data: Dict) -> Optional[str]:
        schema_name = self._get_value(event_data, "schema_name", "orgSchemaName")
        if schema_name:
            return schema_name
        org_id = self._get_value(event_data, "organization_id", "organisation_id", "organizationId")
        if not org_id:
            return None
        return f"org_{org_id.replace('-', '_')}"
    
    async def _upsert_patient(self, event_data: Dict):
        schema = self._schema_from_org(event_data)
        if not schema:
            logger.warning("Missing organization for patient event")
            return
        
        patient_id = self._get_value(event_data, "patient_id", "patientId")
        if not patient_id:
            logger.warning("Missing patient_id in event")
            return
        
        first_name = self._get_value(event_data, "first_name", "firstName")
        last_name = self._get_value(event_data, "last_name", "lastName")
        
        created_at = self._parse_datetime(self._get_value(event_data, "created_at", "createdAt")) or datetime.utcnow()
        updated_at = self._parse_datetime(self._get_value(event_data, "updated_at", "updatedAt")) or created_at
        is_active = self._get_value(event_data, "is_active", "isActive")
        if is_active is None:
            is_active = True
        
        stmt = insert(Patient).values(
            id=UUID(patient_id),
            first_name=first_name or "",
            last_name=last_name or "",
            email=self._get_value(event_data, "email"),
            phone_number=self._get_value(event_data, "phone_number", "phoneNumber"),
            date_of_birth=self._parse_date(self._get_value(event_data, "date_of_birth", "dateOfBirth")),
            address=self._get_value(event_data, "address"),
            medical_notes=self._get_value(event_data, "medical_notes", "medicalNotes"),
            careplan_type=self._get_value(event_data, "careplan_type", "careplanType"),
            careplan_frequency=self._get_value(event_data, "careplan_frequency", "careplanFrequency"),
            is_active=is_active,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        ).on_conflict_do_update(
            index_elements=[Patient.id],
            set_={
                "first_name": first_name or "",
                "last_name": last_name or "",
                "email": self._get_value(event_data, "email"),
                "phone_number": self._get_value(event_data, "phone_number", "phoneNumber"),
                "date_of_birth": self._parse_date(self._get_value(event_data, "date_of_birth", "dateOfBirth")),
                "address": self._get_value(event_data, "address"),
                "medical_notes": self._get_value(event_data, "medical_notes", "medicalNotes"),
                "careplan_type": self._get_value(event_data, "careplan_type", "careplanType"),
                "careplan_frequency": self._get_value(event_data, "careplan_frequency", "careplanFrequency"),
                "is_active": is_active,
                "updated_at": updated_at,
                "deleted_at": None,
            }
        )
        
        async with AsyncSessionLocal() as session:
            await session.execute(text(f'SET search_path TO "{schema}"'))
            await session.execute(stmt)
            await session.commit()
    
    async def _mark_patient_deleted(self, event_data: Dict):
        schema = self._schema_from_org(event_data)
        if not schema:
            logger.warning("Missing organization for patient delete event")
            return
        
        patient_id = self._get_value(event_data, "patient_id", "patientId")
        if not patient_id:
            logger.warning("Missing patient_id in delete event")
            return
        
        deleted_at = self._parse_datetime(self._get_value(event_data, "deleted_at", "deletedAt")) or datetime.utcnow()
        
        async with AsyncSessionLocal() as session:
            await session.execute(text(f'SET search_path TO "{schema}"'))
            await session.execute(
                Patient.__table__.update()
                .where(Patient.id == UUID(patient_id))
                .values(deleted_at=deleted_at, is_active=False, updated_at=deleted_at)
            )
            await session.commit()
    
    async def _update_patient_status(self, event_data: Dict):
        schema = self._schema_from_org(event_data)
        if not schema:
            logger.warning("Missing organization for patient status event")
            return
        
        patient_id = self._get_value(event_data, "patient_id", "patientId")
        if not patient_id:
            logger.warning("Missing patient_id in status event")
            return
        
        new_status = self._get_value(event_data, "new_status", "newStatus")
        changed_at = self._parse_datetime(self._get_value(event_data, "changed_at", "changedAt")) or datetime.utcnow()
        is_active = (str(new_status).lower() == "active")
        
        async with AsyncSessionLocal() as session:
            await session.execute(text(f'SET search_path TO "{schema}"'))
            await session.execute(
                Patient.__table__.update()
                .where(Patient.id == UUID(patient_id))
                .values(is_active=is_active, updated_at=changed_at)
            )
            await session.commit()
    
    async def _upsert_caregiver(self, event_data: Dict):
        schema = self._schema_from_org(event_data)
        if not schema:
            logger.warning("Missing organization for user event")
            return
        
        user_id = self._get_value(event_data, "user_id", "userId")
        if not user_id:
            logger.warning("Missing user_id in event")
            return
        
        role = self._get_value(event_data, "role")
        if role and role.upper() != "CAREGIVER":
            return
        
        first_name = self._get_value(event_data, "first_name", "firstName")
        last_name = self._get_value(event_data, "last_name", "lastName")
        
        created_at = self._parse_datetime(self._get_value(event_data, "created_at", "createdAt")) or datetime.utcnow()
        updated_at = self._parse_datetime(self._get_value(event_data, "updated_at", "updatedAt")) or created_at
        is_active = self._get_value(event_data, "is_active", "isActive")
        if is_active is None:
            is_active = True
        
        stmt = insert(User).values(
            id=UUID(user_id),
            first_name=first_name or "",
            last_name=last_name or "",
            email=self._get_value(event_data, "email"),
            role=role,
            is_active=is_active,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        ).on_conflict_do_update(
            index_elements=[User.id],
            set_={
                "first_name": first_name or "",
                "last_name": last_name or "",
                "email": self._get_value(event_data, "email"),
                "role": role,
                "is_active": is_active,
                "updated_at": updated_at,
                "deleted_at": None,
            }
        )
        
        async with AsyncSessionLocal() as session:
            await session.execute(text(f'SET search_path TO "{schema}"'))
            await session.execute(stmt)
            await session.commit()
    
    async def _mark_caregiver_deleted(self, event_data: Dict):
        schema = self._schema_from_org(event_data)
        if not schema:
            logger.warning("Missing organization for user delete event")
            return
        
        user_id = self._get_value(event_data, "user_id", "userId")
        if not user_id:
            logger.warning("Missing user_id in delete event")
            return
        
        role = self._get_value(event_data, "role")
        if role and role.upper() != "CAREGIVER":
            return
        
        deleted_at = self._parse_datetime(self._get_value(event_data, "deleted_at", "deletedAt")) or datetime.utcnow()
        
        async with AsyncSessionLocal() as session:
            await session.execute(text(f'SET search_path TO "{schema}"'))
            await session.execute(
                User.__table__.update()
                .where(User.id == UUID(user_id))
                .values(deleted_at=deleted_at, is_active=False, updated_at=deleted_at)
            )
            await session.commit()
    
    async def _update_caregiver_status(self, event_data: Dict):
        schema = self._schema_from_org(event_data)
        if not schema:
            logger.warning("Missing organization for user status event")
            return
        
        user_id = self._get_value(event_data, "user_id", "userId")
        if not user_id:
            logger.warning("Missing user_id in status event")
            return
        
        role = self._get_value(event_data, "role")
        if role and role.upper() != "CAREGIVER":
            return
        
        new_status = self._get_value(event_data, "new_status", "newStatus")
        changed_at = self._parse_datetime(self._get_value(event_data, "changed_at", "changedAt")) or datetime.utcnow()
        is_active = (str(new_status).lower() == "active")
        
        async with AsyncSessionLocal() as session:
            await session.execute(text(f'SET search_path TO "{schema}"'))
            await session.execute(
                User.__table__.update()
                .where(User.id == UUID(user_id))
                .values(is_active=is_active, updated_at=changed_at)
            )
            await session.commit()
    
    async def _update_caregiver_role(self, event_data: Dict):
        schema = self._schema_from_org(event_data)
        if not schema:
            logger.warning("Missing organization for user role event")
            return
        
        user_id = self._get_value(event_data, "user_id", "userId")
        if not user_id:
            logger.warning("Missing user_id in role event")
            return
        
        new_role = self._get_value(event_data, "new_role", "newRole")
        old_role = self._get_value(event_data, "old_role", "oldRole")
        changed_at = self._parse_datetime(self._get_value(event_data, "changed_at", "changedAt")) or datetime.utcnow()
        
        if old_role and old_role.upper() == "CAREGIVER" and (not new_role or new_role.upper() != "CAREGIVER"):
            async with AsyncSessionLocal() as session:
                await session.execute(text(f'SET search_path TO "{schema}"'))
                await session.execute(
                    User.__table__.update()
                    .where(User.id == UUID(user_id))
                    .values(role=new_role, is_active=False, updated_at=changed_at)
                )
                await session.commit()
            return
        
        if new_role and new_role.upper() == "CAREGIVER":
            async with AsyncSessionLocal() as session:
                await session.execute(text(f'SET search_path TO "{schema}"'))
                await session.execute(
                    User.__table__.update()
                    .where(User.id == UUID(user_id))
                    .values(role=new_role, is_active=True, updated_at=changed_at)
                )
                await session.commit()
    
    async def _process_event(self, event_type: str, event_data: Dict):
        if event_type == "patient.created":
            await self._upsert_patient(event_data)
        elif event_type == "patient.deleted":
            await self._mark_patient_deleted(event_data)
        elif event_type == "patient.status_changed":
            await self._update_patient_status(event_data)
        elif event_type == "user.created":
            await self._upsert_caregiver(event_data)
        elif event_type == "user.deleted":
            await self._mark_caregiver_deleted(event_data)
        elif event_type == "user.status_changed":
            await self._update_caregiver_status(event_data)
        elif event_type == "user.role_changed":
            await self._update_caregiver_role(event_data)
        else:
            logger.warning(f"Unknown event type: {event_type}")
    
    def callback(self, ch, method, properties, body):
        """Process incoming messages from the queue."""
        try:
            message = json.loads(body)
            event_type = method.routing_key or message.get("event_type") or message.get("event")
            event_data = message.get("data", {})
            
            asyncio.run(self._process_event(event_type, event_data))
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def start_consuming(self):
        """Start consuming messages from RabbitMQ."""
        try:
            queue_name = self.connect()
            
            logger.info("="*60)
            logger.info("Care Session Service - Organization Event Consumer")
            logger.info(f"Connected to RabbitMQ: {self.host}:{self.port}")
            logger.info(f"Listening to queue: {queue_name}")
            logger.info(f"Routing keys: {', '.join(self.routing_keys)}")
            logger.info("="*60)
            
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=self.callback
            )
            
            self.channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("Stopping consumer...")
            self.stop()
        except Exception as e:
            logger.error(f"Consumer error: {e}")
            self.stop()
            raise
    
    def stop(self):
        """Stop consuming and close connections."""
        if self.channel and not self.channel.is_closed:
            self.channel.stop_consuming()
            self.channel.close()
        if self.connection and not self.connection.is_closed:
            self.connection.close()
        logger.info("Consumer stopped")


def start_org_consumer():
    """Entry point for starting the organization event consumer."""
    consumer = OrganizationEventConsumer()
    consumer.start_consuming()


if __name__ == "__main__":
    start_consumer()
