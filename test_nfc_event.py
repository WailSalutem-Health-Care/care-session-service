#!/usr/bin/env python3
"""
Publish a test NFC event to RabbitMQ for testing care session creation.

This simulates the NFC service publishing an event when a tag is scanned.
"""

import os
import json
import pika
from datetime import datetime

# Configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
RABBITMQ_EXCHANGE = os.getenv("RABBITMQ_NFC_EXCHANGE", "nfc.events")


def publish_nfc_event(tag_id: str, patient_id: str):
    """Publish a test NFC event to RabbitMQ"""
    
    # Create event payload
    event = {
        "event": "nfc.resolved",
        "tag_id": tag_id,
        "patient_id": patient_id,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    print(f"📡 Publishing NFC event to RabbitMQ...")
    print(f"   Exchange: {RABBITMQ_EXCHANGE}")
    print(f"   Tag ID: {tag_id}")
    print(f"   Patient ID: {patient_id}")
    
    # Connect to RabbitMQ
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials
        )
    )
    channel = connection.channel()
    
    # Declare exchange (idempotent)
    channel.exchange_declare(
        exchange=RABBITMQ_EXCHANGE,
        exchange_type="topic",
        durable=True
    )
    
    # Publish event
    channel.basic_publish(
        exchange=RABBITMQ_EXCHANGE,
        routing_key="nfc.resolved",
        body=json.dumps(event),
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2  # Persistent
        )
    )
    
    connection.close()
    
    print(f"✅ NFC event published successfully!")
    print(f"\nYou can now create a care session with:")
    print(f'  curl -X POST http://localhost:8002/care-sessions/create \\')
    print(f'    -H "Authorization: Bearer YOUR_TOKEN" \\')
    print(f'    -H "Content-Type: application/json" \\')
    print(f'    -d \'{{"tag_id": "{tag_id}"}}\'')


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python test_nfc_event.py <tag_id> <patient_id>")
        print("\nExample:")
        print("  python test_nfc_event.py 04284962C36980 9558e722-15f5-4847-a78b-9bb369c37954")
        sys.exit(1)
    
    tag_id = sys.argv[1]
    patient_id = sys.argv[2]
    
    try:
        publish_nfc_event(tag_id, patient_id)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
