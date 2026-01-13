#!/usr/bin/env python3
"""
DonkeyKong Core Worker
Base class for distributed data collection with local LLM validation
"""

import os
import json
import time
import redis
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class WorkerConfig:
    """Configuration for a DonkeyKong worker"""
    worker_id: int = 1
    start_index: int = 0
    end_index: int = 100
    redis_url: str = "redis://localhost:6379"
    data_dir: str = "/data"
    backup_dir: str = "/backups"
    log_dir: str = "/logs"
    rate_limit: float = 2.0  # seconds between entities
    checkpoint_interval: int = 10
    retry_attempts: int = 3
    

@dataclass 
class CollectionResult:
    """Result of collecting a single entity"""
    entity_id: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    quality_score: float = 0.0
    error: Optional[str] = None
    validation_result: Optional[Dict] = None
    collection_time: float = 0.0
    

class DonkeyWorker(ABC):
    """
    Base class for DonkeyKong workers.
    
    Subclass this and implement:
    - collect(entity) -> raw data
    - validate(entity, data) -> validation result (optional, uses Kong if not implemented)
    """
    
    def __init__(self, config: Optional[WorkerConfig] = None):
        self.config = config or WorkerConfig(
            worker_id=int(os.environ.get('WORKER_ID', 1)),
            start_index=int(os.environ.get('START_INDEX', 0)),
            end_index=int(os.environ.get('END_INDEX', 100)),
            redis_url=os.environ.get('REDIS_URL', 'redis://localhost:6379'),
            data_dir=os.environ.get('DATA_DIR', '/data'),
            rate_limit=float(os.environ.get('RATE_LIMIT', 2.0)),
        )
        
        # Create directories
        os.makedirs(self.config.data_dir, exist_ok=True)
        os.makedirs(self.config.backup_dir, exist_ok=True)
        os.makedirs(self.config.log_dir, exist_ok=True)
        
        # Initialize Redis
        self.redis = redis.from_url(self.config.redis_url)
        
        # Kong validator (set by Pipeline or manually)
        self.kong = None
        
        # Worker stats
        self.stats = {
            'worker_id': self.config.worker_id,
            'start_time': None,
            'entities_processed': 0,
            'entities_successful': 0,
            'entities_failed': 0,
            'current_entity': None,
            'status': 'initialized'
        }
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup worker-specific logging"""
        log_file = os.path.join(
            self.config.log_dir, 
            f'worker_{self.config.worker_id}.log'
        )
        
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter(
            f'[%(asctime)s] Worker {self.config.worker_id}: %(message)s'
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    def log(self, message: str):
        """Log message to file and console"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] Worker {self.config.worker_id}: {message}"
        print(log_entry)
        logger.info(message)
    
    @abstractmethod
    def collect(self, entity: str) -> Dict[str, Any]:
        """
        Collect data for a single entity.
        
        Override this method with your collection logic.
        
        Args:
            entity: The entity identifier to collect
            
        Returns:
            Dictionary containing collected data
        """
        pass
    
    def validate(self, entity: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate collected data.
        
        Override this method for custom validation, or let Kong handle it.
        
        Args:
            entity: The entity identifier
            data: The collected data to validate
            
        Returns:
            Dictionary with 'valid' bool and optional 'issues' list
        """
        if self.kong:
            return self.kong.validate(entity, data)
        
        # Default: simple schema validation
        return {
            'valid': bool(data) and not data.get('error'),
            'issues': [],
            'quality_score': 100.0 if data else 0.0
        }
    
    def process_entity(self, entity: str) -> CollectionResult:
        """Process a single entity: collect and validate"""
        start_time = time.time()
        
        self.log(f"Processing {entity}")
        self.stats['current_entity'] = entity
        self._update_redis_stats()
        
        try:
            # Collect data
            data = self.collect(entity)
            
            # Validate with Kong or custom validator
            validation = self.validate(entity, data)
            
            collection_time = time.time() - start_time
            
            result = CollectionResult(
                entity_id=entity,
                success=validation.get('valid', False),
                data=data,
                quality_score=validation.get('quality_score', 0.0),
                validation_result=validation,
                collection_time=collection_time
            )
            
            # Save result
            self._save_result(entity, result)
            
            if result.success:
                self.stats['entities_successful'] += 1
                self.log(f"✅ {entity}: Success (Quality: {result.quality_score:.1f}%)")
                self.redis.hincrby('collection:progress', 'total_successful', 1)
            else:
                self.stats['entities_failed'] += 1
                issues = validation.get('issues', ['Unknown issue'])
                self.log(f"⚠️ {entity}: Failed validation - {issues}")
                self.redis.hincrby('collection:progress', 'total_failed', 1)
                self._record_failure(entity, str(issues))
            
            return result
            
        except Exception as e:
            self.stats['entities_failed'] += 1
            self.log(f"❌ {entity}: Error - {e}")
            self.redis.hincrby('collection:progress', 'total_failed', 1)
            self._record_failure(entity, str(e))
            
            return CollectionResult(
                entity_id=entity,
                success=False,
                error=str(e),
                collection_time=time.time() - start_time
            )
    
    def _save_result(self, entity: str, result: CollectionResult):
        """Save collection result to file"""
        filename = os.path.join(self.config.data_dir, f"{entity}_data.json")
        
        output = {
            'entity_id': result.entity_id,
            'success': result.success,
            'data': result.data,
            'quality_score': result.quality_score,
            'validation_result': result.validation_result,
            'collection_time': result.collection_time,
            'worker_id': self.config.worker_id,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2, default=str)
    
    def _record_failure(self, entity: str, error: str):
        """Record failure details in Redis"""
        failure_key = f'failures:{entity}'
        self.redis.hset(failure_key, mapping={
            'worker_id': str(self.config.worker_id),
            'error': error,
            'timestamp': datetime.now().isoformat()
        })
    
    def _update_redis_stats(self):
        """Update worker stats in Redis"""
        try:
            worker_key = f'worker:{self.config.worker_id}:stats'
            self.redis.hset(worker_key, mapping={
                k: str(v) for k, v in self.stats.items()
            })
            
            # Publish progress event for monitor
            if self.stats['entities_processed'] % 10 == 0:
                self.redis.publish('progress', json.dumps({
                    'worker_id': self.config.worker_id,
                    'entities_processed': self.stats['entities_processed'],
                    'success_rate': self._success_rate()
                }))
                
        except Exception as e:
            self.log(f"Redis update error: {e}")
    
    def _success_rate(self) -> float:
        """Calculate current success rate"""
        processed = self.stats['entities_processed']
        if processed == 0:
            return 0.0
        return (self.stats['entities_successful'] / processed) * 100
    
    def _create_checkpoint(self):
        """Create checkpoint for resuming"""
        checkpoint = {
            'worker_id': self.config.worker_id,
            'stats': self.stats,
            'timestamp': datetime.now().isoformat()
        }
        
        checkpoint_file = os.path.join(
            self.config.backup_dir, 
            f'worker_{self.config.worker_id}_checkpoint.json'
        )
        
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
    
    def run(self, entities: List[str]):
        """
        Main worker loop.
        
        Args:
            entities: List of entity identifiers to process
        """
        self.log(f"Starting worker {self.config.worker_id}")
        self.log(f"Processing {len(entities)} entities")
        
        self.stats['start_time'] = datetime.now().isoformat()
        self.stats['status'] = 'running'
        self._update_redis_stats()
        
        for entity in entities:
            self.process_entity(entity)
            self.stats['entities_processed'] += 1
            
            # Update global progress
            self.redis.hincrby('collection:progress', 'total_processed', 1)
            
            # Rate limiting
            time.sleep(self.config.rate_limit)
            
            # Checkpoint
            if self.stats['entities_processed'] % self.config.checkpoint_interval == 0:
                self._create_checkpoint()
                self._update_redis_stats()
                
                self.log(
                    f"Progress: {self.stats['entities_processed']}/{len(entities)}, "
                    f"Success rate: {self._success_rate():.1f}%"
                )
        
        # Final stats
        self.stats['status'] = 'completed'
        self.stats['end_time'] = datetime.now().isoformat()
        self._update_redis_stats()
        
        self.log(f"""
Worker {self.config.worker_id} Complete!
========================
Processed: {self.stats['entities_processed']}
Successful: {self.stats['entities_successful']}
Failed: {self.stats['entities_failed']}
Success Rate: {self._success_rate():.1f}%
""")


# Convenience function for simple cases
def run_worker(worker_class, entities_file: str):
    """Run a worker with entities from a file"""
    with open(entities_file, 'r') as f:
        all_entities = [line.strip() for line in f if line.strip()]
    
    config = WorkerConfig()
    worker = worker_class(config)
    
    # Get assigned range
    assigned = all_entities[config.start_index:config.end_index]
    worker.run(assigned)
