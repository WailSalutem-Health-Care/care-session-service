"""
RabbitMQ Consumer for NFC Events

Consumes events from the NFC microservice and caches tag-to-patient mappings.

Expected Event Payload from NFC Service:
{
    "event": "nfc.resolved" | "nfc.assigned",
    "tag_id": "string",              # Required: NFC tag identifier (globally unique)
    "patient_id": "uuid-string",     # Required: Patient UUID
    "timestamp": "iso-datetime"      # Auto-added by publisher
}

Note: Tag IDs must be globally unique across all organizations.
If the same physical tag ID can exist in multiple orgs, use tenant-namespaced approach instead.
"""

import os
import json
import pika
import logging
from app.messaging.nfc_cache import get_nfc_cache

logger = logging.getLogger(__name__)


class NFCEventConsumer:
    def __init__(self):
        self.host = os.getenv("RABBITMQ_HOST")
        self.port = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.user = os.getenv("RABBITMQ_USER")
        self.password = os.getenv("RABBITMQ_PASSWORD")
        self.exchange = os.getenv("RABBITMQ_NFC_EXCHANGE", "nfc.events")
        self.queue = "care_session_nfc_events"
        self.connection = None
        self.channel = None
        self.cache = get_nfc_cache()

    def connect(self):
        credentials = pika.PlainCredentials(self.user, self.password)
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=self.host, port=self.port, credentials=credentials, heartbeat=600, blocked_connection_timeout=300
            )
        )
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange=self.exchange, exchange_type="topic", durable=True)
        self.channel.queue_declare(queue=self.queue, durable=True)
        self.channel.queue_bind(exchange=self.exchange, queue=self.queue, routing_key="nfc.resolved")
        self.channel.queue_bind(exchange=self.exchange, queue=self.queue, routing_key="nfc.assigned")

    def _on_message(self, ch, method, properties, body):
        try:
            message = json.loads(body)
            tag_id = message.get("tag_id")
            patient_id = message.get("patient_id")

            if not tag_id:
                logger.error(f"Missing tag_id in event: {message}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

            if not patient_id:
                logger.error(f"Missing patient_id in event: {message}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

            # Store in global cache (no tenant namespace required)
            self.cache.store(tag_id, str(patient_id))
            logger.info(f"✅ Cached NFC mapping: {tag_id} → {patient_id}")

            ch.basic_ack(delivery_tag=method.delivery_tag)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def start_consuming(self):
        try:
            self.connect()
            logger.info(f"NFC Consumer connected ({self.host}:{self.port})")
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(queue=self.queue, on_message_callback=self._on_message)
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            logger.error(f"Consumer error: {e}")
            self.stop()
            raise

    def stop(self):
        if self.channel and not self.channel.is_closed:
            self.channel.stop_consuming()
            self.channel.close()
        if self.connection and not self.connection.is_closed:
            self.connection.close()


def start_consumer():
    logging.basicConfig(level=logging.INFO)
    NFCEventConsumer().start_consuming()


if __name__ == "__main__":
    start_consumer()
