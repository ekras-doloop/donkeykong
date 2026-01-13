#!/usr/bin/env python3
"""
DonkeyKong CLI
Command-line interface for distributed data collection.

Usage:
    dk collect entities.txt --workers 10
    dk status
    dk failures
    dk retry --strategy aggressive
    dk mcp-server
"""

import argparse
import json
import sys
import os
from pathlib import Path


def cmd_collect(args):
    """Start a collection job"""
    from ..core.worker import WorkerConfig
    from ..core.monitor import DonkeyMonitor, MonitorConfig
    
    # Load entities
    with open(args.entities_file, 'r') as f:
        entities = [line.strip() for line in f if line.strip()]
    
    print(f"🦍 DonkeyKong Collection")
    print(f"📊 Entities: {len(entities)}")
    print(f"👷 Workers: {args.workers}")
    print()
    
    if args.dry_run:
        print("🔍 Dry run - would collect:")
        for entity in entities[:10]:
            print(f"  - {entity}")
        if len(entities) > 10:
            print(f"  ... and {len(entities) - 10} more")
        return
    
    # Generate docker-compose
    compose = generate_docker_compose(
        workers=args.workers,
        entities_file=args.entities_file,
        rate_limit=args.rate_limit,
        validator=args.validator
    )
    
    compose_file = Path('docker-compose.donkeykong.yml')
    with open(compose_file, 'w') as f:
        f.write(compose)
    
    print(f"✅ Generated {compose_file}")
    print()
    print("To start collection:")
    print(f"  docker-compose -f {compose_file} up")
    print()
    print("To monitor:")
    print("  dk status")


def cmd_status(args):
    """Get current status"""
    import redis
    
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    
    try:
        r = redis.from_url(redis_url)
        progress = r.hgetall('collection:progress')
        
        def decode(val):
            if isinstance(val, bytes):
                return val.decode()
            return val
        
        total_processed = int(decode(progress.get(b'total_processed', 0)) or 0)
        total_successful = int(decode(progress.get(b'total_successful', 0)) or 0)
        total_failed = int(decode(progress.get(b'total_failed', 0)) or 0)
        
        success_rate = (total_successful / max(total_processed, 1)) * 100
        
        # Get worker stats
        workers = []
        for i in range(1, 11):
            stats = r.hgetall(f'worker:{i}:stats')
            if stats:
                workers.append({
                    'id': i,
                    'status': decode(stats.get(b'status', b'unknown')),
                    'processed': decode(stats.get(b'entities_processed', b'0'))
                })
        
        active = sum(1 for w in workers if w['status'] == 'running')
        
        print()
        print("🦍 DonkeyKong Status")
        print("=" * 40)
        print(f"📊 Processed: {total_processed}")
        print(f"✅ Successful: {total_successful} ({success_rate:.1f}%)")
        print(f"❌ Failed: {total_failed}")
        print()
        print(f"👷 Workers: {active} active / {len(workers)} total")
        
        for w in workers:
            icon = '🟢' if w['status'] == 'running' else '✅' if w['status'] == 'completed' else '⚪'
            print(f"   {icon} Worker {w['id']}: {w['processed']} processed")
        
        print()
        
    except redis.ConnectionError:
        print("❌ Cannot connect to Redis")
        print("   Make sure Redis is running: docker-compose up redis")
        sys.exit(1)


def cmd_failures(args):
    """List failures"""
    import redis
    
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    
    try:
        r = redis.from_url(redis_url)
        
        failures = []
        for key in r.scan_iter('failures:*'):
            if len(failures) >= args.limit:
                break
            
            data = r.hgetall(key)
            entity = key.decode().split(':')[1] if isinstance(key, bytes) else key.split(':')[1]
            
            failures.append({
                'entity': entity,
                'error': data.get(b'error', b'').decode() if b'error' in data else 'Unknown'
            })
        
        if not failures:
            print("✅ No failures!")
            return
        
        print()
        print(f"❌ Failures ({len(failures)})")
        print("=" * 40)
        
        for f in failures:
            print(f"  {f['entity']}: {f['error'][:60]}")
        
        print()
        print("To retry:")
        print("  dk retry")
        print()
        
    except redis.ConnectionError:
        print("❌ Cannot connect to Redis")
        sys.exit(1)


def cmd_retry(args):
    """Retry failures"""
    import redis
    
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    
    try:
        r = redis.from_url(redis_url)
        
        # Collect failures
        to_retry = []
        for key in r.scan_iter('failures:*'):
            entity = key.decode().split(':')[1] if isinstance(key, bytes) else key.split(':')[1]
            to_retry.append(entity)
            r.delete(key)
        
        if not to_retry:
            print("✅ No failures to retry")
            return
        
        # Queue for retry
        for entity in to_retry:
            r.rpush('job:retry', entity)
        
        print(f"🔄 Queued {len(to_retry)} entities for retry")
        print(f"   Strategy: {args.strategy}")
        
    except redis.ConnectionError:
        print("❌ Cannot connect to Redis")
        sys.exit(1)


def cmd_mcp_server(args):
    """Start MCP server"""
    from ..interfaces.mcp.server import main as mcp_main
    mcp_main()


def generate_docker_compose(
    workers: int,
    entities_file: str,
    rate_limit: float,
    validator: str
) -> str:
    """Generate docker-compose.yml for collection"""
    
    # Calculate ranges
    with open(entities_file, 'r') as f:
        total = sum(1 for line in f if line.strip())
    
    per_worker = total // workers
    
    services = ["  redis:\n    image: redis:7-alpine\n    ports:\n      - '6379:6379'\n"]
    
    for i in range(1, workers + 1):
        start = (i - 1) * per_worker
        end = start + per_worker if i < workers else total
        
        services.append(f"""
  worker-{i}:
    build: .
    environment:
      - WORKER_ID={i}
      - START_INDEX={start}
      - END_INDEX={end}
      - REDIS_URL=redis://redis:6379
      - RATE_LIMIT={rate_limit}
      - VALIDATOR={validator}
    volumes:
      - ./data:/data
      - ./logs:/logs
    depends_on:
      - redis
""")
    
    services.append("""
  monitor:
    build: .
    environment:
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./reports:/reports
    depends_on:
      - redis
    command: python -m donkeykong.core.monitor
""")
    
    return f"""version: '3.8'

services:
{''.join(services)}

volumes:
  redis_data:
"""


def main():
    parser = argparse.ArgumentParser(
        prog='dk',
        description='🦍 DonkeyKong - Distributed Collection, Local Intelligence'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # collect
    collect_parser = subparsers.add_parser('collect', help='Start collection')
    collect_parser.add_argument('entities_file', help='File with entities to collect')
    collect_parser.add_argument('--workers', type=int, default=10, help='Number of workers')
    collect_parser.add_argument('--rate-limit', type=float, default=2.0, help='Seconds between requests')
    collect_parser.add_argument('--validator', default='schema', help='Validator type: schema, ollama')
    collect_parser.add_argument('--dry-run', action='store_true', help='Show what would be collected')
    collect_parser.set_defaults(func=cmd_collect)
    
    # status
    status_parser = subparsers.add_parser('status', help='Get current status')
    status_parser.set_defaults(func=cmd_status)
    
    # failures
    failures_parser = subparsers.add_parser('failures', help='List failures')
    failures_parser.add_argument('--limit', type=int, default=20, help='Max failures to show')
    failures_parser.set_defaults(func=cmd_failures)
    
    # retry
    retry_parser = subparsers.add_parser('retry', help='Retry failures')
    retry_parser.add_argument('--strategy', choices=['default', 'aggressive', 'conservative'], 
                              default='default', help='Retry strategy')
    retry_parser.set_defaults(func=cmd_retry)
    
    # mcp-server
    mcp_parser = subparsers.add_parser('mcp-server', help='Start MCP server for Claude')
    mcp_parser.set_defaults(func=cmd_mcp_server)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == '__main__':
    main()
