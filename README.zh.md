# code-executor

## 场景

用于0xbot工作流执行引擎里面做Python代码执行,在docker里面安全的执行python代码,做为代码节点



## 启动
- 使用默认端口
```bash

docker build -t code-executor .
docker run -p 18080:18080 -p 18000:18000 code-executor
```

- 使用自定义端口
```bash

docker run \
  -e MAIN_PORT=18080 \
  -e METRICS_PORT=18000 \
  -p 9090:9090 \
  -p 9000:9000 \
  code-executor
```

## 测试
- 使用poetry
```bash
poetry shell
poetry install
python server.py
#打开新窗口
python client.py

```


