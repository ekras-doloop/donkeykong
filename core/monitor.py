#!/usr/bin/env python3
"""
DonkeyKong Progress Monitor
Real-time monitoring and reporting for distributed collection
"""

import os
import json
import redis
import time
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class MonitorConfig:
    """Configuration for the monitor"""
    redis_url: str = "redis://localhost:6379"
    report_dir: str = "/reports"
    report_interval: int = 100  # Report every N entities
    expected_workers: int = 10


class DonkeyMonitor:
    """Monitor progress of DonkeyKong collection jobs"""
    
    def __init__(self, config: Optional[MonitorConfig] = None):
        self.config = config or MonitorConfig(
            redis_url=os.environ.get('REDIS_URL', 'redis://localhost:6379'),
            report_dir=os.environ.get('REPORT_DIR', '/reports'),
            expected_workers=int(os.environ.get('EXPECTED_WORKERS', 10))
        )
        
        os.makedirs(self.config.report_dir, exist_ok=True)
        
        self.redis = redis.from_url(self.config.redis_url)
        self.start_time = datetime.now()
        self.last_report_count = 0
    
    def get_global_stats(self) -> Dict:
        """Get aggregated stats from all workers"""
        progress = self.redis.hgetall('collection:progress')
        
        # Handle bytes from Redis
        def decode(val):
            if isinstance(val, bytes):
                return val.decode()
            return val
        
        total_processed = int(decode(progress.get(b'total_processed', 0)) or 0)
        total_successful = int(decode(progress.get(b'total_successful', 0)) or 0)
        total_failed = int(decode(progress.get(b'total_failed', 0)) or 0)
        
        # Get individual worker stats
        worker_stats = {}
        for i in range(1, self.config.expected_workers + 1):
            worker_key = f'worker:{i}:stats'
            stats = self.redis.hgetall(worker_key)
            if stats:
                worker_stats[i] = {
                    decode(k): decode(v) for k, v in stats.items()
                }
        
        return {
            'total_processed': total_processed,
            'total_successful': total_successful,
            'total_failed': total_failed,
            'worker_stats': worker_stats
        }
    
    def get_failures(self, limit: int = 20) -> list:
        """Get recent failures"""
        failures = []
        
        for key in self.redis.scan_iter('failures:*'):
            failure_data = self.redis.hgetall(key)
            entity = key.decode().split(':')[1] if isinstance(key, bytes) else key.split(':')[1]
            
            failures.append({
                'entity': entity,
                'error': failure_data.get(b'error', b'').decode() if b'error' in failure_data else '',
                'worker_id': failure_data.get(b'worker_id', b'').decode() if b'worker_id' in failure_data else '',
                'timestamp': failure_data.get(b'timestamp', b'').decode() if b'timestamp' in failure_data else ''
            })
            
            if len(failures) >= limit:
                break
        
        return failures
    
    def create_progress_report(self, milestone: int) -> str:
        """Create detailed progress report"""
        stats = self.get_global_stats()
        elapsed_time = (datetime.now() - self.start_time).total_seconds()
        
        # Calculate metrics
        processed = max(stats['total_processed'], 1)
        success_rate = (stats['total_successful'] / processed) * 100
        avg_time = elapsed_time / processed
        
        # Count active workers
        active_workers = sum(
            1 for w in stats['worker_stats'].values() 
            if w.get('status') == 'running'
        )
        
        report = f"""
🦍 DONKEYKONG PROGRESS REPORT
{'='*50}
📅 Milestone: {milestone} Entities Processed
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

OVERALL STATISTICS:
-------------------
✅ Total Processed: {stats['total_processed']}
✅ Total Successful: {stats['total_successful']} ({success_rate:.1f}%)
❌ Total Failed: {stats['total_failed']}
⏱️ Elapsed Time: {elapsed_time/60:.1f} minutes
⏱️ Avg Time/Entity: {avg_time:.1f} seconds

WORKER STATUS:
--------------
🔧 Active Workers: {active_workers}/{self.config.expected_workers}
"""
        
        # Add worker details
        for worker_id, worker_data in sorted(stats['worker_stats'].items()):
            status = worker_data.get('status', 'unknown')
            processed = worker_data.get('entities_processed', 0)
            current = worker_data.get('current_entity', '-')
            
            status_icon = '🟢' if status == 'running' else '✅' if status == 'completed' else '🔴'
            report += f"\n  {status_icon} Worker {worker_id}: {processed} processed, Status: {status}"
            if status == 'running' and current != '-':
                report += f" (current: {current})"
        
        # System health
        health = '🟢 HEALTHY' if success_rate >= 80 and active_workers >= self.config.expected_workers * 0.8 else \
                 '🟡 DEGRADED' if success_rate >= 60 else '🔴 CRITICAL'
        
        report += f"""

SYSTEM HEALTH: {health}
{'='*50}
"""
        return report
    
    def save_report(self, report: str, milestone: int):
        """Save report to file"""
        report_file = os.path.join(
            self.config.report_dir, 
            f'progress_report_{milestone}_entities.txt'
        )
        with open(report_file, 'w') as f:
            f.write(report)
    
    def check_completion(self) -> bool:
        """Check if all workers have completed"""
        stats = self.get_global_stats()
        
        for worker_data in stats['worker_stats'].values():
            if worker_data.get('status') not in ['completed', 'failed']:
                return False
        
        return len(stats['worker_stats']) > 0
    
    def run(self, total_entities: Optional[int] = None):
        """Main monitoring loop"""
        print("🦍 DonkeyKong Progress Monitor Started")
        print(f"📊 Will report every {self.config.report_interval} entities processed")
        print("=" * 60)
        
        while True:
            try:
                stats = self.get_global_stats()
                total_processed = stats['total_processed']
                
                # Check if we need to report
                if total_processed > 0 and \
                   total_processed % self.config.report_interval == 0 and \
                   total_processed > self.last_report_count:
                    
                    report = self.create_progress_report(total_processed)
                    print(report)
                    self.save_report(report, total_processed)
                    self.last_report_count = total_processed
                
                # Quick status update every minute
                if int(time.time()) % 60 == 0:
                    processed = stats['total_processed']
                    success_rate = (stats['total_successful'] / max(processed, 1)) * 100
                    print(f"\r⏱️ {datetime.now().strftime('%H:%M:%S')} - "
                          f"Processed: {processed} ({success_rate:.1f}% success)", 
                          end='', flush=True)
                
                # Check completion
                if self.check_completion():
                    print("\n\n✅ ALL WORKERS COMPLETED!")
                    final_report = self.create_progress_report(total_processed)
                    print(final_report)
                    
                    # Save final report
                    final_file = os.path.join(self.config.report_dir, 'FINAL_REPORT.txt')
                    with open(final_file, 'w') as f:
                        f.write(final_report)
                    
                    break
                
                time.sleep(5)
                
            except KeyboardInterrupt:
                print("\n\n⚠️ Monitor stopped by user")
                break
            except Exception as e:
                print(f"\n❌ Monitor error: {e}")
                time.sleep(10)
    
    def get_status_json(self) -> Dict:
        """Get current status as JSON (for MCP/API)"""
        stats = self.get_global_stats()
        elapsed = (datetime.now() - self.start_time).total_seconds()
        processed = max(stats['total_processed'], 1)
        
        return {
            'total_processed': stats['total_processed'],
            'total_successful': stats['total_successful'],
            'total_failed': stats['total_failed'],
            'success_rate': (stats['total_successful'] / processed) * 100,
            'elapsed_seconds': elapsed,
            'avg_time_per_entity': elapsed / processed,
            'active_workers': sum(
                1 for w in stats['worker_stats'].values() 
                if w.get('status') == 'running'
            ),
            'total_workers': len(stats['worker_stats']),
            'is_complete': self.check_completion()
        }


if __name__ == "__main__":
    monitor = DonkeyMonitor()
    monitor.run()
