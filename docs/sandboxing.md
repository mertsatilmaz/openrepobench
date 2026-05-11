# Sandboxing

OpenRepoBench supports two command executors.

## Local

Local execution runs task commands directly on the host. It is convenient for development and public seed tasks.

```yaml
environment:
  kind: local
  timeout_seconds: 60
  network: disabled
```

## Docker

Docker execution runs task commands in a pinned image with the scoring workspace mounted at `/workspace`.

```yaml
environment:
  kind: docker
  docker_image: python:3.11-slim
  timeout_seconds: 300
  network: disabled
  cpus: 1
  memory: 2g
```

For leaderboard tasks, prefer Docker. It makes setup, dependency behavior, network access, and resource limits easier to reproduce across evaluators.

Network is disabled by default for credible no-internet tracks. Internet-enabled tracks must be reported separately.
