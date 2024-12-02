from __future__ import annotations
import asyncio
import logging
import os

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, TypeAlias, TypeVar, cast, NamedTuple, Set
from aiohttp import web
import traceback

import resource


from metrics import MetricsServer

JsonDict: TypeAlias = Dict[str, Any]
T = TypeVar('T')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@dataclass
class ExecutionResult:
    status: str
    result: Any | None = None
    error: str | None = None
    traceback: str | None = None

    def to_dict(self) -> JsonDict:
        return {k: v for k, v in self.__dict__.items() if v is not None}





SAFE_BUILTINS: Set[str] = {
    'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes',
    'chr', 'complex', 'dict', 'divmod', 'enumerate', 'filter', 'float',
    'format', 'frozenset', 'hash', 'hex', 'int', 'isinstance', 'issubclass',
    'iter', 'len', 'list', 'map', 'max', 'min', 'next', 'oct', 'ord',
    'pow', 'print', 'range', 'repr', 'reversed', 'round', 'set', 'slice',
    'sorted', 'str', 'sum', 'tuple', 'type', 'zip'
}

FORBIDDEN_MODULES: Set[str] = {
    'os', 'sys', 'subprocess', 'socket', 'requests', 'urllib',
    'pathlib', 'pickle', 'shutil', 'importlib', 'builtins'
}

RESOURCE_LIMITS = {
    'CPU_TIME': 1,  # 秒
    'MEMORY': 100 * 1024 * 1024,  # 30MB
    'FILE_SIZE': 1024 * 1024,  # 1MB
    'PROCESSES': 1,
    'OPEN_FILES': 10
}


def set_resource_limits() -> None:
    """resource limit"""
    try:
        resource.setrlimit(resource.RLIMIT_CPU,
                           (RESOURCE_LIMITS['CPU_TIME'], RESOURCE_LIMITS['CPU_TIME']))

        resource.setrlimit(resource.RLIMIT_AS,
                           (RESOURCE_LIMITS['MEMORY'], RESOURCE_LIMITS['MEMORY']))

        resource.setrlimit(resource.RLIMIT_FSIZE,
                           (RESOURCE_LIMITS['FILE_SIZE'], RESOURCE_LIMITS['FILE_SIZE']))

        resource.setrlimit(resource.RLIMIT_NPROC,
                           (RESOURCE_LIMITS['PROCESSES'], RESOURCE_LIMITS['PROCESSES']))

        resource.setrlimit(resource.RLIMIT_NOFILE,
                           (RESOURCE_LIMITS['OPEN_FILES'], RESOURCE_LIMITS['OPEN_FILES']))

    except Exception as e:
        logger.error(f"Failed to set resource limits: {e}")
        raise


def create_safe_globals() -> Dict[str, Any]:
    safe_globals = {
        '__builtins__': {
            name: getattr(__builtins__, name)
            for name in SAFE_BUILTINS
        },
        'print': lambda *args, **kwargs: None  # 禁用打印功能
    }
    return safe_globals


def validate_code(code: str) -> None:

    for module in FORBIDDEN_MODULES:
        if f"import {module}" in code or f"from {module}" in code:
            raise SecurityError(f"Importing module '{module}' is not allowed")

    if 'eval(' in code or 'exec(' in code:
        raise SecurityError("Using eval() or exec() is not allowed")

    if 'open(' in code or 'file(' in code:
        raise SecurityError("File operations are not allowed")


class SecurityError(Exception):
    pass







class CodeExecutor:

    @staticmethod
    async def execute_code_in_process(code: str, params: JsonDict) -> ExecutionResult:
        loop = asyncio.get_event_loop()
        with ProcessPoolExecutor(max_workers=1) as executor:
            try:
                future = loop.run_in_executor(
                    executor,
                    CodeExecutor._execute_code_safely,
                    code,
                    params
                )
                result = await asyncio.wait_for(future, timeout=RESOURCE_LIMITS['CPU_TIME'])
                return result
            except asyncio.TimeoutError:
                return ExecutionResult(
                    status='error',
                    error='Execution timeout'
                )
            except Exception as e:
                return ExecutionResult(
                    status='error',
                    error=str(e),
                    traceback=traceback.format_exc()
                )

    @staticmethod
    def _execute_code_safely(code: str, params: JsonDict) -> ExecutionResult:
        try:
            set_resource_limits()

            validate_code(code)

            globals_dict = create_safe_globals()
            globals_dict.update(params)

            compiled_code = compile(code, '<string>', 'exec')

            exec(compiled_code, globals_dict)

            if 'main' not in globals_dict:
                return ExecutionResult(
                    status='error',
                    error="No main function defined"
                )

            result = globals_dict['main'](**params)
            return ExecutionResult(
                status='success',
                result=result
            )

        except SecurityError as e:
            return ExecutionResult(
                status='error',
                error=f"Security violation: {str(e)}"
            )
        except Exception as e:
            return ExecutionResult(
                status='error',
                error=str(e),
                traceback=traceback.format_exc()
            )



class ServerConfig(NamedTuple):
    main_port: int = int(os.getenv('MAIN_PORT', '18080'))
    metrics_port: int = int(os.getenv('METRICS_PORT', '18000'))
    host: str = os.getenv('SERVER_HOST', '0.0.0.0')
    log_level: str = os.getenv('LOG_LEVEL', 'INFO')
    max_workers: int = int(os.getenv('MAX_WORKERS', '1'))
    timeout: int = int(os.getenv('TIMEOUT', '30'))


class CodeExecutionServer:

    def __init__(self, config: ServerConfig | None = None) -> None:
        self.app = web.Application()
        self.config = config or ServerConfig()
        self.metrics = MetricsServer()
        self.setup_routes()

    def setup_routes(self) -> None:
        self.app.router.add_post('/execute', self.handle_execute)

    @MetricsServer().track_request('/execute')
    async def handle_execute(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()

            match data:
                case {'code': code, 'params': params}:
                    result = await CodeExecutor.execute_code_in_process(code, params)
                case {'code': code}:
                    result = await CodeExecutor.execute_code_in_process(code, {})
                case _:
                    result = ExecutionResult(
                        status='error',
                        error='Invalid request format'
                    )

            return web.json_response(result.to_dict())

        except Exception as e:
            logger.error(f"Request handling error: {str(e)}\n{traceback.format_exc()}")
            result = ExecutionResult(
                status='error',
                error=str(e),
                traceback=traceback.format_exc()
            )
            return web.json_response(result.to_dict())

    async def start_background_tasks(self, app: web.Application):

        async def update_metrics():
            while True:
                self.metrics.update_system_metrics()
                await asyncio.sleep(15)  # 每15秒更新一次

        app['metrics_updater'] = asyncio.create_task(update_metrics())

    async def cleanup_background_tasks(self, app: web.Application):
        app['metrics_updater'].cancel()
        await app['metrics_updater']

    def run(self) -> None:
        self.metrics.start_server(self.config.metrics_port)

        self.app.on_startup.append(self.start_background_tasks)
        self.app.on_cleanup.append(self.cleanup_background_tasks)

        web.run_app(
            self.app,
            host=self.config.host,
            port=self.config.main_port
        )

if __name__ == '__main__':
    server = CodeExecutionServer()
    server.run()