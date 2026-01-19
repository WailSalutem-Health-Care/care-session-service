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
                host=self.host, port=self.port, credentials=credentials,
                heartbeat=600, blocked_connection_timeout=300
            )
        )
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange=self.exchange, exchange_type='topic', durable=True)
        self.channel.queue_declare(queue=self.queue, durable=True)
        self.channel.queue_bind(exchange=self.exchange, queue=self.queue, routing_key='nfc.resolved')
        self.channel.queue_bind(exchange=self.exchange, queue=self.queue, routing_key='nfc.assigned')
    
    def _on_message(self, ch, method, properties, body):
        try:
            message = json.loads(body)
            tag_id = message.get('tag_id')
            patient_id = message.get('patient_id')
            tenant_schema = message.get('tenant_schema') or message.get('organization_id')
            
            if tag_id and patient_id and tenant_schema:
                self.cache.store(tag_id, str(patient_id), tenant_schema)
                logger.info(f"Cached: {tag_id} → {patient_id}")
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Error: {e}")
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
