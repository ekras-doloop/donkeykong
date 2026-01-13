#!/usr/bin/env python3
"""
DonkeyKong MCP Server
Allows Claude to orchestrate distributed data collection through conversation.

"Start collecting these 1000 URLs and validate each page has pricing information"
"How's the collection going?"
"These 12 failed - retry them with a different strategy"
"""

import json
import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logging.warning("MCP SDK not installed. Install with: pip install mcp")

import redis

logger = logging.getLogger(__name__)


class DonkeyKongMCPServer:
    """
    MCP Server that exposes DonkeyKong functionality to Claude.
    
    This enables conversational orchestration of distributed data collection.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis = redis.from_url(redis_url)
        self.active_jobs: Dict[str, Dict] = {}
        
        if MCP_AVAILABLE:
            self.server = Server("donkeykong")
            self._register_tools()
    
    def _register_tools(self):
        """Register MCP tools"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                Tool(
                    name="donkeykong_start",
                    description="Start a new distributed collection job. Provide a list of entities to collect and optional validation criteria.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "entities": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of entity identifiers to collect (URLs, tickers, IDs, etc.)"
                            },
                            "workers": {
                                "type": "integer",
                                "default": 10,
                                "description": "Number of parallel workers"
                            },
                            "validation_prompt": {
                                "type": "string",
                                "description": "Custom prompt for Kong LLM validation"
                            },
                            "rate_limit": {
                                "type": "number",
                                "default": 2.0,
                                "description": "Seconds between requests per worker"
                            }
                        },
                        "required": ["entities"]
                    }
                ),
                Tool(
                    name="donkeykong_status",
                    description="Get current status of the collection job including progress, success rate, and worker status.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "job_id": {
                                "type": "string",
                                "description": "Job ID (optional, uses current job if not specified)"
                            }
                        }
                    }
                ),
                Tool(
                    name="donkeykong_failures",
                    description="Get list of failed entities with error details.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "default": 20,
                                "description": "Maximum number of failures to return"
                            }
                        }
                    }
                ),
                Tool(
                    name="donkeykong_retry",
                    description="Retry failed entities, optionally with a different strategy.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "entities": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Specific entities to retry (optional, retries all failures if not specified)"
                            },
                            "strategy": {
                                "type": "string",
                                "enum": ["default", "aggressive", "conservative"],
                                "default": "default",
                                "description": "Retry strategy - aggressive has shorter delays, conservative has longer"
                            },
                            "new_validation_prompt": {
                                "type": "string",
                                "description": "New validation prompt for Kong (optional)"
                            }
                        }
                    }
                ),
                Tool(
                    name="donkeykong_validate_sample",
                    description="Manually validate a sample of collected data to check quality.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "sample_size": {
                                "type": "integer",
                                "default": 5,
                                "description": "Number of random entities to validate"
                            },
                            "criteria": {
                                "type": "string",
                                "description": "What to check for in the validation"
                            }
                        }
                    }
                ),
                Tool(
                    name="donkeykong_stop",
                    description="Gracefully stop the current collection job.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "job_id": {
                                "type": "string",
                                "description": "Job ID to stop (optional)"
                            }
                        }
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            try:
                if name == "donkeykong_start":
                    result = await self._start_collection(arguments)
                elif name == "donkeykong_status":
                    result = await self._get_status(arguments)
                elif name == "donkeykong_failures":
                    result = await self._get_failures(arguments)
                elif name == "donkeykong_retry":
                    result = await self._retry_failures(arguments)
                elif name == "donkeykong_validate_sample":
                    result = await self._validate_sample(arguments)
                elif name == "donkeykong_stop":
                    result = await self._stop_collection(arguments)
                else:
                    result = {"error": f"Unknown tool: {name}"}
                
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, default=str)
                )]
                
            except Exception as e:
                logger.error(f"Tool {name} failed: {e}")
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": str(e)})
                )]
    
    async def _start_collection(self, args: Dict) -> Dict:
        """Start a new collection job"""
        entities = args.get('entities', [])
        workers = args.get('workers', 10)
        validation_prompt = args.get('validation_prompt')
        rate_limit = args.get('rate_limit', 2.0)
        
        if not entities:
            return {"error": "No entities provided"}
        
        job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Store job config
        job_config = {
            'job_id': job_id,
            'entities': entities,
            'workers': workers,
            'validation_prompt': validation_prompt,
            'rate_limit': rate_limit,
            'status': 'starting',
            'created_at': datetime.now().isoformat()
        }
        
        self.redis.hset(f'job:{job_id}', mapping={
            k: json.dumps(v) if isinstance(v, (list, dict)) else str(v) 
            for k, v in job_config.items()
        })
        
        # Reset progress counters
        self.redis.delete('collection:progress')
        self.redis.hset('collection:progress', mapping={
            'total_processed': 0,
            'total_successful': 0,
            'total_failed': 0
        })
        
        # Store entities for workers
        self.redis.delete('job:entities')
        for entity in entities:
            self.redis.rpush('job:entities', entity)
        
        self.active_jobs[job_id] = job_config
        
        # Calculate time estimate
        entities_per_worker = len(entities) / workers
        est_time_minutes = (entities_per_worker * rate_limit) / 60
        
        return {
            "job_id": job_id,
            "status": "started",
            "entities_count": len(entities),
            "workers": workers,
            "estimated_time_minutes": round(est_time_minutes, 1),
            "message": f"Started collection of {len(entities)} entities across {workers} workers. "
                       f"Estimated completion in ~{est_time_minutes:.0f} minutes. "
                       "Use donkeykong_status to monitor progress."
        }
    
    async def _get_status(self, args: Dict) -> Dict:
        """Get current job status"""
        progress = self.redis.hgetall('collection:progress')
        
        def decode(val):
            if isinstance(val, bytes):
                return val.decode()
            return val
        
        total_processed = int(decode(progress.get(b'total_processed', 0)) or 0)
        total_successful = int(decode(progress.get(b'total_successful', 0)) or 0)
        total_failed = int(decode(progress.get(b'total_failed', 0)) or 0)
        
        # Get worker stats
        worker_statuses = []
        for i in range(1, 11):  # Check up to 10 workers
            stats = self.redis.hgetall(f'worker:{i}:stats')
            if stats:
                worker_statuses.append({
                    'worker_id': i,
                    'status': decode(stats.get(b'status', b'unknown')),
                    'processed': decode(stats.get(b'entities_processed', b'0')),
                    'current': decode(stats.get(b'current_entity', b'-'))
                })
        
        success_rate = (total_successful / max(total_processed, 1)) * 100
        
        # Determine overall status
        active_workers = sum(1 for w in worker_statuses if w['status'] == 'running')
        
        if active_workers == 0 and total_processed > 0:
            overall_status = "completed"
        elif active_workers > 0:
            overall_status = "running"
        else:
            overall_status = "not_started"
        
        return {
            "status": overall_status,
            "progress": {
                "total_processed": total_processed,
                "total_successful": total_successful,
                "total_failed": total_failed,
                "success_rate": f"{success_rate:.1f}%"
            },
            "workers": {
                "active": active_workers,
                "details": worker_statuses
            },
            "health": "healthy" if success_rate >= 80 else "degraded" if success_rate >= 60 else "critical"
        }
    
    async def _get_failures(self, args: Dict) -> Dict:
        """Get failed entities"""
        limit = args.get('limit', 20)
        failures = []
        
        for key in self.redis.scan_iter('failures:*'):
            if len(failures) >= limit:
                break
                
            failure_data = self.redis.hgetall(key)
            entity = key.decode().split(':')[1] if isinstance(key, bytes) else key.split(':')[1]
            
            failures.append({
                'entity': entity,
                'error': failure_data.get(b'error', b'').decode() if b'error' in failure_data else '',
                'worker_id': failure_data.get(b'worker_id', b'').decode() if b'worker_id' in failure_data else '',
                'timestamp': failure_data.get(b'timestamp', b'').decode() if b'timestamp' in failure_data else ''
            })
        
        # Group by error type
        error_groups = {}
        for f in failures:
            error_type = f['error'][:50] if f['error'] else 'Unknown'
            if error_type not in error_groups:
                error_groups[error_type] = []
            error_groups[error_type].append(f['entity'])
        
        return {
            "total_failures": len(failures),
            "failures": failures,
            "error_summary": {k: len(v) for k, v in error_groups.items()},
            "retry_suggestion": f"Use donkeykong_retry to retry these {len(failures)} failed entities"
        }
    
    async def _retry_failures(self, args: Dict) -> Dict:
        """Retry failed entities"""
        specific_entities = args.get('entities', [])
        strategy = args.get('strategy', 'default')
        
        # Get failures to retry
        if specific_entities:
            to_retry = specific_entities
        else:
            to_retry = []
            for key in self.redis.scan_iter('failures:*'):
                entity = key.decode().split(':')[1] if isinstance(key, bytes) else key.split(':')[1]
                to_retry.append(entity)
        
        if not to_retry:
            return {"message": "No failures to retry"}
        
        # Clear failure records for entities being retried
        for entity in to_retry:
            self.redis.delete(f'failures:{entity}')
        
        # Queue for retry
        for entity in to_retry:
            self.redis.rpush('job:retry', entity)
        
        rate_limits = {
            'default': 2.0,
            'aggressive': 0.5,
            'conservative': 5.0
        }
        
        return {
            "status": "retry_queued",
            "entities_to_retry": len(to_retry),
            "strategy": strategy,
            "rate_limit": rate_limits.get(strategy, 2.0),
            "message": f"Queued {len(to_retry)} entities for retry with {strategy} strategy"
        }
    
    async def _validate_sample(self, args: Dict) -> Dict:
        """Validate a sample of collected data"""
        sample_size = args.get('sample_size', 5)
        criteria = args.get('criteria', 'completeness and accuracy')
        
        # This would integrate with Kong validator
        # For now, return a placeholder
        return {
            "sample_size": sample_size,
            "criteria": criteria,
            "message": "Sample validation requires Kong (local LLM) to be configured. "
                       "This feature validates random samples of collected data against your criteria."
        }
    
    async def _stop_collection(self, args: Dict) -> Dict:
        """Stop collection gracefully"""
        # Signal workers to stop
        self.redis.set('job:stop_signal', '1')
        
        return {
            "status": "stopping",
            "message": "Stop signal sent to all workers. They will finish current entity and exit."
        }
    
    async def run(self):
        """Run the MCP server"""
        if not MCP_AVAILABLE:
            raise RuntimeError("MCP SDK not installed. Install with: pip install mcp")
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


def main():
    """Entry point for MCP server"""
    import asyncio
    
    server = DonkeyKongMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
