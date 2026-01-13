#!/usr/bin/env python3
"""
DonkeyKong Python API
High-level interface for distributed data collection with local LLM validation.

Usage:
    from donkeykong import Pipeline, OllamaValidator
    
    class MyCollector(Pipeline):
        def collect(self, entity):
            return fetch_data(entity)
    
    pipeline = MyCollector(
        entities=my_list,
        workers=10,
        kong=OllamaValidator(model="llama3.2")
    )
    pipeline.run()
"""

import os
import json
import subprocess
import tempfile
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from pathlib import Path

from ..core.worker import DonkeyWorker, WorkerConfig, CollectionResult
from ..core.monitor import DonkeyMonitor, MonitorConfig
from ..kong.validator import OllamaValidator, SchemaValidator, BaseValidator


@dataclass
class PipelineConfig:
    """Configuration for a DonkeyKong pipeline"""
    workers: int = 10
    rate_limit: float = 2.0
    checkpoint_interval: int = 100
    data_dir: str = "./data"
    redis_url: str = "redis://localhost:6379"
    use_docker: bool = True


class Pipeline:
    """
    High-level pipeline for distributed data collection.
    
    Subclass this and implement the `collect` method.
    Optionally implement `validate` for custom validation,
    or provide a Kong validator for LLM-based validation.
    """
    
    def __init__(
        self,
        entities: List[str],
        config: Optional[PipelineConfig] = None,
        kong: Optional[BaseValidator] = None,
        collector_func: Optional[Callable] = None
    ):
        self.entities = entities
        self.config = config or PipelineConfig()
        self.kong = kong
        self._collector_func = collector_func
        
        # Ensure data directory exists
        Path(self.config.data_dir).mkdir(parents=True, exist_ok=True)
    
    def collect(self, entity: str) -> Dict[str, Any]:
        """
        Collect data for a single entity.
        
        Override this method OR provide collector_func in constructor.
        
        Args:
            entity: The entity identifier
            
        Returns:
            Dictionary containing collected data
        """
        if self._collector_func:
            return self._collector_func(entity)
        
        raise NotImplementedError(
            "Implement collect() method or provide collector_func"
        )
    
    def validate(self, entity: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate collected data.
        
        Override for custom validation, or let Kong handle it.
        """
        if self.kong:
            return self.kong.validate(entity, data)
        
        # Default validation
        return {
            'valid': bool(data) and not data.get('error'),
            'quality_score': 100.0 if data else 0.0,
            'issues': []
        }
    
    def run(self, blocking: bool = True) -> Dict[str, Any]:
        """
        Run the pipeline.
        
        Args:
            blocking: If True, wait for completion. If False, return immediately.
            
        Returns:
            Dictionary with results summary
        """
        if self.config.use_docker:
            return self._run_docker(blocking)
        else:
            return self._run_local()
    
    def _run_local(self) -> Dict[str, Any]:
        """Run collection locally (single process)"""
        results = []
        
        for entity in self.entities:
            try:
                data = self.collect(entity)
                validation = self.validate(entity, data)
                
                result = CollectionResult(
                    entity_id=entity,
                    success=validation.get('valid', False),
                    data=data,
                    quality_score=validation.get('quality_score', 0),
                    validation_result=validation
                )
                results.append(result)
                
                # Save to file
                filename = Path(self.config.data_dir) / f"{entity}_data.json"
                with open(filename, 'w') as f:
                    json.dump({
                        'entity': entity,
                        'data': data,
                        'validation': validation
                    }, f, indent=2, default=str)
                    
            except Exception as e:
                results.append(CollectionResult(
                    entity_id=entity,
                    success=False,
                    error=str(e)
                ))
        
        successful = sum(1 for r in results if r.success)
        
        return {
            'total': len(results),
            'successful': successful,
            'failed': len(results) - successful,
            'success_rate': (successful / len(results)) * 100 if results else 0
        }
    
    def _run_docker(self, blocking: bool) -> Dict[str, Any]:
        """Run collection with Docker workers"""
        # Write entities to temp file
        entities_file = Path(self.config.data_dir) / 'entities.txt'
        with open(entities_file, 'w') as f:
            for entity in self.entities:
                f.write(f"{entity}\n")
        
        # Generate docker-compose
        compose = self._generate_compose()
        compose_file = Path(self.config.data_dir) / 'docker-compose.yml'
        with open(compose_file, 'w') as f:
            f.write(compose)
        
        # Start Docker
        cmd = ['docker-compose', '-f', str(compose_file), 'up']
        if not blocking:
            cmd.append('-d')
        
        subprocess.run(cmd, cwd=self.config.data_dir)
        
        return {
            'status': 'started' if not blocking else 'completed',
            'entities': len(self.entities),
            'workers': self.config.workers,
            'compose_file': str(compose_file)
        }
    
    def _generate_compose(self) -> str:
        """Generate docker-compose.yml"""
        per_worker = len(self.entities) // self.config.workers
        
        services = []
        
        # Redis
        services.append("""
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
""")
        
        # Workers
        for i in range(1, self.config.workers + 1):
            start = (i - 1) * per_worker
            end = start + per_worker if i < self.config.workers else len(self.entities)
            
            services.append(f"""
  worker-{i}:
    build: .
    environment:
      - WORKER_ID={i}
      - START_INDEX={start}
      - END_INDEX={end}
      - REDIS_URL=redis://redis:6379
      - RATE_LIMIT={self.config.rate_limit}
    volumes:
      - ./:/data
    depends_on:
      - redis
""")
        
        return f"""version: '3.8'

services:
{''.join(services)}
"""
    
    def get_results(self) -> List[Dict]:
        """Get collected results from data directory"""
        results = []
        
        for file in Path(self.config.data_dir).glob('*_data.json'):
            with open(file, 'r') as f:
                results.append(json.load(f))
        
        return results
    
    def get_failures(self) -> List[str]:
        """Get list of failed entities"""
        results = self.get_results()
        return [
            r['entity'] for r in results 
            if not r.get('validation', {}).get('valid', False)
        ]


# Convenience functions

def collect(
    entities: List[str],
    collector: Callable[[str], Dict],
    validator: Optional[BaseValidator] = None,
    workers: int = 10,
    **kwargs
) -> Dict[str, Any]:
    """
    Quick collection without subclassing.
    
    Args:
        entities: List of entity identifiers
        collector: Function that takes entity and returns data dict
        validator: Optional Kong validator
        workers: Number of parallel workers
        
    Returns:
        Results summary
    """
    pipeline = Pipeline(
        entities=entities,
        kong=validator,
        collector_func=collector,
        config=PipelineConfig(workers=workers, **kwargs)
    )
    return pipeline.run()


def collect_urls(
    urls: List[str],
    validator: Optional[BaseValidator] = None,
    workers: int = 10
) -> Dict[str, Any]:
    """
    Convenience function for URL collection.
    
    Args:
        urls: List of URLs to fetch
        validator: Optional Kong validator for content validation
        workers: Number of parallel workers
    """
    import requests
    
    def fetch_url(url: str) -> Dict:
        try:
            response = requests.get(url, timeout=30)
            return {
                'url': url,
                'status_code': response.status_code,
                'content_length': len(response.text),
                'content': response.text[:1000]  # First 1000 chars
            }
        except Exception as e:
            return {'url': url, 'error': str(e)}
    
    return collect(urls, fetch_url, validator, workers)
