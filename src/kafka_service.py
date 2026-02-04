"""
Kafka Integration for Image Enhancement Pipeline
Handles job queuing, processing, and result publishing
"""
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, asdict
from enum import Enum

from confluent_kafka import Producer, Consumer, KafkaError, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic

from .config import get_config, KafkaConfig, ProcessingStatus

logger = logging.getLogger(__name__)


@dataclass
class ImageJob:
    """Represents an image enhancement job"""
    job_id: str
    image_id: str
    original_url: str
    enhancement_mode: str = "auto"
    priority: int = 5
    retry_count: int = 0
    max_retries: int = 3
    created_at: str = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImageJob":
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> "ImageJob":
        return cls.from_dict(json.loads(json_str))


@dataclass
class JobResult:
    """Result of processing an image job"""
    job_id: str
    image_id: str
    status: str
    original_url: str
    enhanced_url: Optional[str] = None
    enhanced_path: Optional[str] = None
    original_size_bytes: int = 0
    enhanced_size_bytes: int = 0
    quality_before: Optional[float] = None
    quality_after: Optional[float] = None
    quality_improvement: Optional[float] = None
    size_reduction: Optional[float] = None
    processing_time_ms: int = 0
    enhancements_applied: List[str] = None
    error: Optional[str] = None
    completed_at: str = None
    
    def __post_init__(self):
        if self.enhancements_applied is None:
            self.enhancements_applied = []
        if self.completed_at is None:
            self.completed_at = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class KafkaProducerService:
    """
    Kafka producer for publishing image enhancement jobs and results
    """
    
    def __init__(self, config: Optional[KafkaConfig] = None):
        self.config = config or get_config().kafka
        self._producer = None
    
    @property
    def producer(self) -> Producer:
        if self._producer is None:
            self._producer = Producer({
                'bootstrap.servers': self.config.bootstrap_servers,
                'acks': self.config.acks,
                'retries': self.config.retries,
                'linger.ms': 5,
                'batch.size': 16384,
            })
        return self._producer
    
    def _delivery_callback(self, err, msg):
        """Callback for message delivery confirmation"""
        if err:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}] @ {msg.offset()}")
    
    def publish_job(self, job: ImageJob, callback: Optional[Callable] = None) -> bool:
        """
        Publish an image enhancement job to Kafka
        
        Args:
            job: ImageJob to publish
            callback: Optional delivery callback
        
        Returns:
            True if queued successfully
        """
        try:
            self.producer.produce(
                topic=self.config.jobs_topic,
                key=job.image_id.encode('utf-8'),
                value=job.to_json().encode('utf-8'),
                callback=callback or self._delivery_callback
            )
            self.producer.poll(0)  # Trigger callbacks
            return True
        except Exception as e:
            logger.error(f"Failed to publish job: {e}")
            return False
    
    def publish_batch(self, jobs: List[ImageJob]) -> int:
        """
        Publish multiple jobs in batch
        
        Returns:
            Number of jobs successfully queued
        """
        success_count = 0
        for job in jobs:
            if self.publish_job(job):
                success_count += 1
        
        # Flush to ensure delivery
        remaining = self.producer.flush(timeout=10)
        if remaining > 0:
            logger.warning(f"{remaining} messages were not delivered")
        
        return success_count
    
    def publish_result(self, result: JobResult) -> bool:
        """Publish processing result"""
        try:
            self.producer.produce(
                topic=self.config.results_topic,
                key=result.image_id.encode('utf-8'),
                value=result.to_json().encode('utf-8'),
                callback=self._delivery_callback
            )
            self.producer.poll(0)
            return True
        except Exception as e:
            logger.error(f"Failed to publish result: {e}")
            return False
    
    def publish_to_dlq(self, job: ImageJob, error: str) -> bool:
        """Publish failed job to dead letter queue"""
        try:
            dlq_message = {
                **job.to_dict(),
                "error": error,
                "failed_at": datetime.utcnow().isoformat()
            }
            self.producer.produce(
                topic=self.config.dlq_topic,
                key=job.image_id.encode('utf-8'),
                value=json.dumps(dlq_message).encode('utf-8'),
                callback=self._delivery_callback
            )
            self.producer.poll(0)
            return True
        except Exception as e:
            logger.error(f"Failed to publish to DLQ: {e}")
            return False
    
    def flush(self, timeout: float = 10.0):
        """Flush pending messages"""
        self.producer.flush(timeout)
    
    def close(self):
        """Close producer"""
        if self._producer:
            self._producer.flush(timeout=10)
            self._producer = None


class KafkaConsumerService:
    """
    Kafka consumer for processing image enhancement jobs
    """
    
    def __init__(
        self,
        config: Optional[KafkaConfig] = None,
        group_id: Optional[str] = None
    ):
        self.config = config or get_config().kafka
        self.group_id = group_id or self.config.consumer_group
        self._consumer = None
        self._running = False
    
    @property
    def consumer(self) -> Consumer:
        if self._consumer is None:
            self._consumer = Consumer({
                'bootstrap.servers': self.config.bootstrap_servers,
                'group.id': self.group_id,
                'auto.offset.reset': self.config.auto_offset_reset,
                'enable.auto.commit': self.config.enable_auto_commit,
                'max.poll.interval.ms': 300000,
                'session.timeout.ms': self.config.session_timeout_ms,
                'heartbeat.interval.ms': self.config.heartbeat_interval_ms,
            })
        return self._consumer
    
    def subscribe(self, topics: Optional[List[str]] = None):
        """Subscribe to topics"""
        topics = topics or [self.config.jobs_topic]
        self.consumer.subscribe(topics)
        logger.info(f"Subscribed to topics: {topics}")
    
    def consume(
        self,
        handler: Callable[[ImageJob], JobResult],
        batch_size: int = 10,
        timeout: float = 1.0
    ):
        """
        Start consuming and processing jobs
        
        Args:
            handler: Function to process each job, returns JobResult
            batch_size: Number of messages to process before committing
            timeout: Poll timeout in seconds
        """
        self._running = True
        processed_count = 0
        producer = KafkaProducerService(self.config)
        
        try:
            while self._running:
                msg = self.consumer.poll(timeout)
                
                if msg is None:
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug(f"End of partition reached: {msg.topic()}[{msg.partition()}]")
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                    continue
                
                try:
                    # Parse job
                    job = ImageJob.from_json(msg.value().decode('utf-8'))
                    logger.info(f"Processing job: {job.job_id} for image: {job.image_id}")
                    
                    # Process job
                    result = handler(job)
                    
                    # Publish result
                    producer.publish_result(result)
                    
                    # Handle retries if failed
                    if result.status == ProcessingStatus.FAILED.value:
                        if job.retry_count < job.max_retries:
                            job.retry_count += 1
                            producer.publish_job(job)
                            logger.info(f"Requeued job {job.job_id} (retry {job.retry_count})")
                        else:
                            producer.publish_to_dlq(job, result.error or "Max retries exceeded")
                    
                    processed_count += 1
                    
                    # Commit after batch
                    if processed_count % batch_size == 0:
                        self.consumer.commit()
                        logger.debug(f"Committed offset after {processed_count} messages")
                        
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Don't commit on error, will retry
                    
        except KeyboardInterrupt:
            logger.info("Consumer interrupted")
        finally:
            self.consumer.commit()
            producer.close()
            self.close()
    
    def stop(self):
        """Stop consuming"""
        self._running = False
    
    def close(self):
        """Close consumer"""
        if self._consumer:
            self._consumer.close()
            self._consumer = None


class KafkaAdminService:
    """
    Kafka admin operations for topic management
    """
    
    def __init__(self, config: Optional[KafkaConfig] = None):
        self.config = config or get_config().kafka
        self._admin = None
    
    @property
    def admin(self) -> AdminClient:
        if self._admin is None:
            self._admin = AdminClient({
                'bootstrap.servers': self.config.bootstrap_servers
            })
        return self._admin
    
    def create_topics(self, num_partitions: int = 3, replication_factor: int = 1):
        """Create required topics if they don't exist"""
        topics = [
            NewTopic(self.config.jobs_topic, num_partitions, replication_factor),
            NewTopic(self.config.results_topic, num_partitions, replication_factor),
            NewTopic(self.config.dlq_topic, 1, replication_factor),
        ]
        
        # Check existing topics
        existing = self.admin.list_topics(timeout=10).topics.keys()
        topics_to_create = [t for t in topics if t.topic not in existing]
        
        if not topics_to_create:
            logger.info("All topics already exist")
            return
        
        # Create topics
        futures = self.admin.create_topics(topics_to_create)
        
        for topic, future in futures.items():
            try:
                future.result()
                logger.info(f"Created topic: {topic}")
            except Exception as e:
                logger.error(f"Failed to create topic {topic}: {e}")
    
    def list_topics(self) -> List[str]:
        """List all topics"""
        return list(self.admin.list_topics(timeout=10).topics.keys())
    
    def get_topic_info(self, topic: str) -> Dict[str, Any]:
        """Get topic metadata"""
        metadata = self.admin.list_topics(timeout=10)
        if topic in metadata.topics:
            topic_meta = metadata.topics[topic]
            return {
                "topic": topic,
                "partitions": len(topic_meta.partitions),
                "partition_ids": list(topic_meta.partitions.keys())
            }
        return {}


def create_image_jobs(image_urls: List[Dict[str, Any]], enhancement_mode: str = "auto") -> List[ImageJob]:
    """
    Helper to create ImageJob objects from a list of image data
    
    Args:
        image_urls: List of dicts with 'id', 'url', and optional 'metadata'
        enhancement_mode: Enhancement mode to use
    
    Returns:
        List of ImageJob objects
    """
    jobs = []
    for img_data in image_urls:
        job = ImageJob(
            job_id=str(uuid.uuid4()),
            image_id=img_data.get('id', str(uuid.uuid4())),
            original_url=img_data['url'],
            enhancement_mode=enhancement_mode,
            metadata=img_data.get('metadata', {})
        )
        jobs.append(job)
    return jobs


if __name__ == "__main__":
    # Test Kafka connection
    import sys
    
    config = get_config().kafka
    print(f"Testing Kafka connection to: {config.bootstrap_servers}")
    
    try:
        admin = KafkaAdminService()
        topics = admin.list_topics()
        print(f"Connected! Available topics: {topics}")
        
        if "--create-topics" in sys.argv:
            admin.create_topics()
            print("Topics created successfully")
            
    except Exception as e:
        print(f"Failed to connect to Kafka: {e}")
        print("Make sure Kafka is running and accessible")
