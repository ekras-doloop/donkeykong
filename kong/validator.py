#!/usr/bin/env python3
"""
Kong - Local LLM Validator for DonkeyKong
Intelligent data validation using Ollama (Llama, Mistral, Phi, etc.)
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of Kong validation"""
    valid: bool
    quality_score: float
    issues: List[str]
    should_retry: bool
    reasoning: Optional[str] = None
    

class BaseValidator(ABC):
    """Base class for validators"""
    
    @abstractmethod
    def validate(self, entity: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate collected data"""
        pass


class OllamaValidator(BaseValidator):
    """
    Kong validator using Ollama for local LLM inference.
    
    This is the 'Kong' in DonkeyKong - the intelligent overseer
    that validates what the donkeys (workers) have collected.
    """
    
    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        validation_prompt: Optional[str] = None,
        temperature: float = 0.1,
        timeout: int = 30
    ):
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.timeout = timeout
        
        self.validation_prompt = validation_prompt or self._default_prompt()
        
        # Lazy import - only when actually used
        self._client = None
    
    def _default_prompt(self) -> str:
        return """You are a data quality validator. Evaluate the following collected data for completeness and accuracy.

Entity: {entity}
Data: {data}

Respond with ONLY valid JSON in this exact format:
{{
    "valid": true or false,
    "quality_score": 0-100,
    "issues": ["list", "of", "issues"] or [],
    "should_retry": true or false,
    "reasoning": "brief explanation"
}}

Be strict but fair. Data is valid if it contains meaningful content for the entity.
"""
    
    @property
    def client(self):
        """Lazy-load the Ollama client"""
        if self._client is None:
            try:
                import ollama
                self._client = ollama.Client(host=self.base_url)
            except ImportError:
                raise ImportError(
                    "Ollama package not installed. "
                    "Install with: pip install ollama"
                )
        return self._client
    
    def validate(self, entity: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate collected data using local LLM.
        
        Args:
            entity: The entity identifier
            data: The collected data to validate
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Format the prompt
            prompt = self.validation_prompt.format(
                entity=entity,
                data=json.dumps(data, indent=2, default=str)[:2000]  # Truncate large data
            )
            
            # Call Ollama
            response = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": self.temperature}
            )
            
            # Parse response
            content = response['message']['content']
            
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            result = json.loads(content.strip())
            
            return {
                'valid': result.get('valid', False),
                'quality_score': float(result.get('quality_score', 0)),
                'issues': result.get('issues', []),
                'should_retry': result.get('should_retry', False),
                'reasoning': result.get('reasoning', ''),
                'model': self.model
            }
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            # Fallback to simple validation
            return self._fallback_validation(entity, data)
            
        except Exception as e:
            logger.error(f"Kong validation error: {e}")
            return self._fallback_validation(entity, data)
    
    def _fallback_validation(self, entity: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback validation when LLM fails"""
        is_valid = bool(data) and not data.get('error')
        
        return {
            'valid': is_valid,
            'quality_score': 80.0 if is_valid else 0.0,
            'issues': [] if is_valid else ['LLM validation unavailable, using fallback'],
            'should_retry': not is_valid,
            'reasoning': 'Fallback validation (LLM unavailable)',
            'model': 'fallback'
        }
    
    def batch_validate(
        self, 
        items: List[tuple], 
        concurrency: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Validate multiple items.
        
        Args:
            items: List of (entity, data) tuples
            concurrency: Number of concurrent validations (future use)
            
        Returns:
            List of validation results
        """
        results = []
        for entity, data in items:
            result = self.validate(entity, data)
            results.append(result)
        return results
    
    def test_connection(self) -> bool:
        """Test if Ollama is available"""
        try:
            models = self.client.list()
            available = [m['name'] for m in models.get('models', [])]
            
            if self.model not in available and f"{self.model}:latest" not in available:
                logger.warning(
                    f"Model {self.model} not found. "
                    f"Available: {available}. "
                    f"Pull with: ollama pull {self.model}"
                )
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Ollama connection failed: {e}")
            return False


class SchemaValidator(BaseValidator):
    """
    Simple schema-based validator.
    Use this when you don't need LLM intelligence.
    """
    
    def __init__(self, required_fields: List[str] = None, min_data_size: int = 10):
        self.required_fields = required_fields or []
        self.min_data_size = min_data_size
    
    def validate(self, entity: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate based on schema rules"""
        issues = []
        
        # Check for error
        if data.get('error'):
            return {
                'valid': False,
                'quality_score': 0.0,
                'issues': [f"Collection error: {data['error']}"],
                'should_retry': True
            }
        
        # Check required fields
        for field in self.required_fields:
            if field not in data or not data[field]:
                issues.append(f"Missing required field: {field}")
        
        # Check data size
        data_str = json.dumps(data)
        if len(data_str) < self.min_data_size:
            issues.append(f"Data too small: {len(data_str)} bytes")
        
        # Calculate score
        if not issues:
            quality_score = 100.0
        else:
            quality_score = max(0, 100 - len(issues) * 25)
        
        return {
            'valid': len(issues) == 0,
            'quality_score': quality_score,
            'issues': issues,
            'should_retry': len(issues) > 0 and 'Collection error' in str(issues)
        }


class CompositeValidator(BaseValidator):
    """
    Combine multiple validators.
    Useful for schema check + LLM validation.
    """
    
    def __init__(self, validators: List[BaseValidator]):
        self.validators = validators
    
    def validate(self, entity: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Run all validators and combine results"""
        all_issues = []
        min_score = 100.0
        any_retry = False
        
        for validator in self.validators:
            result = validator.validate(entity, data)
            all_issues.extend(result.get('issues', []))
            min_score = min(min_score, result.get('quality_score', 0))
            any_retry = any_retry or result.get('should_retry', False)
        
        return {
            'valid': len(all_issues) == 0,
            'quality_score': min_score,
            'issues': all_issues,
            'should_retry': any_retry
        }


# Convenience function
def create_validator(
    validator_type: str = "ollama",
    **kwargs
) -> BaseValidator:
    """
    Factory function to create validators.
    
    Args:
        validator_type: "ollama", "schema", or "composite"
        **kwargs: Arguments passed to validator constructor
        
    Returns:
        BaseValidator instance
    """
    validators = {
        "ollama": OllamaValidator,
        "schema": SchemaValidator,
        "composite": CompositeValidator
    }
    
    if validator_type not in validators:
        raise ValueError(f"Unknown validator type: {validator_type}")
    
    return validators[validator_type](**kwargs)
