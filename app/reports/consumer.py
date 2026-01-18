import os
import json
import asyncio
import pika
import logging
from uuid import UUID
from datetime import datetime, date
from typing import Dict, Optional

from app.db.postgres import AsyncSessionLocal
from app.reports.repository import ReportsRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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

    def _patient_payload(self, event_data: Dict) -> Optional[Dict[str, object]]:
        patient_id = self._get_value(event_data, "patient_id", "patientId")
        if not patient_id:
            return None

        first_name = self._get_value(event_data, "first_name", "firstName")
        last_name = self._get_value(event_data, "last_name", "lastName")
        created_at = self._parse_datetime(self._get_value(event_data, "created_at", "createdAt")) or datetime.utcnow()
        updated_at = self._parse_datetime(self._get_value(event_data, "updated_at", "updatedAt")) or created_at
        is_active = self._get_value(event_data, "is_active", "isActive")
        if is_active is None:
            is_active = True

        return {
            "id": UUID(patient_id),
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
            "created_at": created_at,
            "updated_at": updated_at,
            "deleted_at": None,
        }

    def _user_payload(self, event_data: Dict) -> Optional[Dict[str, object]]:
        user_id = self._get_value(event_data, "user_id", "userId")
        if not user_id:
            return None

        role = self._get_value(event_data, "role")
        if role and str(role).upper() != "CAREGIVER":
            return None

        first_name = self._get_value(event_data, "first_name", "firstName")
        last_name = self._get_value(event_data, "last_name", "lastName")
        created_at = self._parse_datetime(self._get_value(event_data, "created_at", "createdAt")) or datetime.utcnow()
        updated_at = self._parse_datetime(self._get_value(event_data, "updated_at", "updatedAt")) or created_at
        is_active = self._get_value(event_data, "is_active", "isActive")
        if is_active is None:
            is_active = True

        return {
            "id": UUID(user_id),
            "first_name": first_name or "",
            "last_name": last_name or "",
            "email": self._get_value(event_data, "email"),
            "role": role,
            "is_active": is_active,
            "created_at": created_at,
            "updated_at": updated_at,
            "deleted_at": None,
        }

    async def _process_event(self, event_type: str, event_data: Dict):
        schema = self._schema_from_org(event_data)
        if not schema:
            logger.warning("Missing organization schema for event")
            return

        async with AsyncSessionLocal() as session:
            repository = ReportsRepository(session, schema)

            if event_type == "patient.created":
                payload = self._patient_payload(event_data)
                if not payload:
                    logger.warning("Missing patient_id in event")
                    return
                await repository.upsert_patient_cache(payload)
            elif event_type == "patient.deleted":
                patient_id = self._get_value(event_data, "patient_id", "patientId")
                if not patient_id:
                    logger.warning("Missing patient_id in delete event")
                    return
                deleted_at = self._parse_datetime(self._get_value(event_data, "deleted_at", "deletedAt")) or datetime.utcnow()
                await repository.mark_patient_deleted(UUID(patient_id), deleted_at)
            elif event_type == "patient.status_changed":
                patient_id = self._get_value(event_data, "patient_id", "patientId")
                if not patient_id:
                    logger.warning("Missing patient_id in status event")
                    return
                new_status = self._get_value(event_data, "new_status", "newStatus")
                changed_at = self._parse_datetime(self._get_value(event_data, "changed_at", "changedAt")) or datetime.utcnow()
                is_active = (str(new_status).lower() == "active")
                await repository.update_patient_status(UUID(patient_id), is_active, changed_at)
            elif event_type == "user.created":
                payload = self._user_payload(event_data)
                if not payload:
                    return
                await repository.upsert_user_cache(payload)
            elif event_type == "user.deleted":
                user_id = self._get_value(event_data, "user_id", "userId")
                if not user_id:
                    logger.warning("Missing user_id in delete event")
                    return
                role = self._get_value(event_data, "role")
                if role and str(role).upper() != "CAREGIVER":
                    return
                deleted_at = self._parse_datetime(self._get_value(event_data, "deleted_at", "deletedAt")) or datetime.utcnow()
                await repository.mark_user_deleted(UUID(user_id), deleted_at)
            elif event_type == "user.status_changed":
                user_id = self._get_value(event_data, "user_id", "userId")
                if not user_id:
                    logger.warning("Missing user_id in status event")
                    return
                role = self._get_value(event_data, "role")
                if role and str(role).upper() != "CAREGIVER":
                    return
                new_status = self._get_value(event_data, "new_status", "newStatus")
                changed_at = self._parse_datetime(self._get_value(event_data, "changed_at", "changedAt")) or datetime.utcnow()
                is_active = (str(new_status).lower() == "active")
                await repository.update_user_status(UUID(user_id), is_active, changed_at)
            elif event_type == "user.role_changed":
                user_id = self._get_value(event_data, "user_id", "userId")
                if not user_id:
                    logger.warning("Missing user_id in role event")
                    return
                new_role = self._get_value(event_data, "new_role", "newRole")
                old_role = self._get_value(event_data, "old_role", "oldRole")
                changed_at = self._parse_datetime(self._get_value(event_data, "changed_at", "changedAt")) or datetime.utcnow()

                if old_role and str(old_role).upper() == "CAREGIVER" and (not new_role or str(new_role).upper() != "CAREGIVER"):
                    await repository.update_user_role(UUID(user_id), new_role, False, changed_at)
                elif new_role and str(new_role).upper() == "CAREGIVER":
                    await repository.update_user_role(UUID(user_id), new_role, True, changed_at)
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
