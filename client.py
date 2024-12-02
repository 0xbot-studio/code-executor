from __future__ import annotations
import asyncio
import aiohttp
from typing import Any, Dict, TypeAlias
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_exponential

JsonDict: TypeAlias = Dict[str, Any]


@dataclass
class ExecutionResponse:
    """执行响应数据类"""
    status: str
    result: Any | None = None
    error: str | None = None
    traceback: str | None = None

    @classmethod
    def from_dict(cls, data: JsonDict) -> ExecutionResponse:
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__annotations__
        })


class CodeExecutionClient:
    """代码执行客户端"""

    def __init__(self, base_url: str = "http://localhost:18080") -> None:
        self.base_url = base_url

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def execute_code(
            self,
            code: str,
            params: JsonDict | None = None
    ) -> ExecutionResponse:
        """发送代码执行请求"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    f"{self.base_url}/execute",
                    json={
                        'code': code,
                        'params': params or {}
                    }
            ) as response:
                data = await response.json()
                return ExecutionResponse.from_dict(data)


async def main() -> None:
    # 测试代码
    test_code = """
def main(x: int, y: int) -> dict[str, int]:
    while True:
        print(".")
    return {'sum': x + y, 'product': x * y}
"""

    # test_code = """
    # def main(x: int, y: int) -> dict[str, int]:
    #     while True:
    #         print(".")
    #     return {'sum': x + y, 'product': x * y}
    # """

    client = CodeExecutionClient()
    result = await client.execute_code(
        code=test_code,
        params={'x': 10, 'y': 20}
    )
    print(result)

    match result:
        case ExecutionResponse(status='success', result=result):
            print(f"Success! Result: {result}")
        case ExecutionResponse(status='error', error=error):
            print(f"Error: {error}")
            if result.traceback:
                print(f"Traceback:\n{result.traceback}")
        case _:
            print(f"Unexpected response: {result}")


if __name__ == '__main__':
    asyncio.run(main())