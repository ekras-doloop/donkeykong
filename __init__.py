"""
🦍 DonkeyKong
Distributed Collection, Local Intelligence

The moment your data pipeline needs *judgment*, the economics change.
"""

__version__ = "0.1.0"

from .core.worker import DonkeyWorker, WorkerConfig, CollectionResult
from .core.monitor import DonkeyMonitor, MonitorConfig
from .kong.validator import (
    OllamaValidator, 
    SchemaValidator, 
    CompositeValidator,
    BaseValidator,
    create_validator
)
from .kong.adversarial import AdversarialValidator, OllamaAdversarialValidator
from .interfaces.python.api import Pipeline, PipelineConfig, collect, collect_urls

__all__ = [
    # Core
    'DonkeyWorker',
    'WorkerConfig', 
    'CollectionResult',
    'DonkeyMonitor',
    'MonitorConfig',
    
    # Kong (validators)
    'OllamaValidator',
    'SchemaValidator',
    'CompositeValidator',
    'BaseValidator',
    'create_validator',
    
    # Kong (adversarial)
    'AdversarialValidator',
    'OllamaAdversarialValidator',
    
    # High-level API
    'Pipeline',
    'PipelineConfig',
    'collect',
    'collect_urls',
]
