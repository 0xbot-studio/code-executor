from functools import wraps

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    start_http_server as prometheus_start_http_server
)
import logging
from typing import Optional
import threading
import time


logger = logging.getLogger(__name__)


class MetricsServer:

    _instance: Optional['MetricsServer'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self):
        # 只初始化一次
        if hasattr(self, '_initialized'):
            return

        # 请求相关指标
        self.requests_total = Counter(
            'code_execution_requests_total',
            'Total number of code execution requests',
            ['status', 'endpoint']
        )

        self.requests_in_progress = Gauge(
            'code_execution_requests_in_progress',
            'Number of code execution requests in progress'
        )

        self.execution_time = Histogram(
            'code_execution_duration_seconds',
            'Time spent executing code',
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        )

        # 系统资源指标
        self.memory_usage = Gauge(
            'code_execution_memory_bytes',
            'Current memory usage in bytes'
        )

        self.cpu_usage = Gauge(
            'code_execution_cpu_percent',
            'Current CPU usage percentage'
        )

        # 错误指标
        self.error_total = Counter(
            'code_execution_errors_total',
            'Total number of execution errors',
            ['error_type']
        )

        self._server = None
        self._initialized = True

    def start_server(self, port: int, addr: str = '0.0.0.0') -> None:
        try:
            prometheus_start_http_server(port, addr)
            logger.info(f"Metrics server started on {addr or '0.0.0.0'}:{port}")
            self._server = True
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")
            raise

    def track_request(self, endpoint: str = '/execute'):

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                self.requests_in_progress.inc()

                try:
                    result = await func(*args, **kwargs)
                    status = result.status if hasattr(result, 'status') else 'success'
                    self.requests_total.labels(
                        status=status,
                        endpoint=endpoint
                    ).inc()
                    return result

                except Exception as e:
                    self.error_total.labels(
                        error_type=type(e).__name__
                    ).inc()
                    raise

                finally:
                    self.execution_time.observe(time.time() - start_time)
                    self.requests_in_progress.dec()

            return wrapper

        return decorator

    def update_system_metrics(self):
        try:
            import psutil
            process = psutil.Process()

            memory_info = process.memory_info()
            self.memory_usage.set(memory_info.rss)

            self.cpu_usage.set(process.cpu_percent())

        except ImportError:
            logger.warning("psutil not installed, system metrics unavailable")
        except Exception as e:
            logger.error(f"Failed to update system metrics: {e}")


