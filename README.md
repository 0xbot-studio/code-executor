# code-executor

## Scenario

Used for Python code execution in the 0xbot workflow execution engine, securely executing Python code in Docker as a code node.

## Startup
- Using default ports

```bash
docker build -t code-executor .
docker run -p 18080:18080 -p 18000:18000 code-executor
```

- Using custom ports

```bash
docker run \
  -e MAIN_PORT=18080 \
  -e METRICS_PORT=18000 \
  -p 9090:9090 \
  -p 9000:9000 \
  code-executor
```

## Test

- use poetry
```bash
poetry shell
poetry install
python server.py
#open new term
python client.py

```

