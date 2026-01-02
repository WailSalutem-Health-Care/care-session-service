"""
RabbitMQ Consumer Entry Point
Starts the event consumer for NFC events
"""
from app.messaging.consumer import start_consumer

if __name__ == "__main__":
    start_consumer()
