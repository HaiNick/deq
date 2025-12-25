"""
DeQ - Task Scheduler
Background scheduler for running tasks at scheduled times.
"""

import threading
import time
from datetime import datetime
from typing import Optional

from config import get_config
from api.tasks import run_task, calculate_next_run


class TaskScheduler:
    """Background task scheduler that runs tasks at their scheduled times."""
    
    def __init__(self, check_interval: int = 60):
        """
        Initialize scheduler.
        
        Args:
            check_interval: How often to check for due tasks (seconds)
        """
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._check_interval = check_interval
    
    def start(self) -> None:
        """Start the scheduler thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[Scheduler] Started task scheduler")
    
    def stop(self) -> None:
        """Stop the scheduler thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        print("[Scheduler] Stopped task scheduler")
    
    def _run(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                self._check_tasks()
            except Exception as e:
                print(f"[Scheduler] Error checking tasks: {e}")
            
            # Sleep in small intervals to allow quick shutdown
            for _ in range(self._check_interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def _check_tasks(self) -> None:
        """Check for tasks that need to run."""
        config = get_config()
        now = datetime.now()
        
        for task in config.get('tasks', []):
            if not task.get('enabled', True):
                continue
            
            next_run = task.get('next_run')
            if not next_run:
                continue
            
            try:
                next_run_dt = datetime.fromisoformat(next_run)
                if now >= next_run_dt:
                    task_id = task.get('id')
                    task_name = task.get('name', 'unnamed')
                    print(f"[Scheduler] Running scheduled task: {task_name} ({task_id})")
                    
                    # Run the task
                    run_task(task_id)
                    
                    # Update next_run for the task
                    task['next_run'] = calculate_next_run(task)
                    
            except (ValueError, TypeError) as e:
                print(f"[Scheduler] Invalid next_run for task {task.get('id')}: {e}")


# Global scheduler instance
scheduler = TaskScheduler()
