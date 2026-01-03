import os
import json
import pika
import logging
from typing import Dict

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


if __name__ == "__main__":
    start_consumer()
