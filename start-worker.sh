#!/bin/bash
# Worker entrypoint. PYTHONPATH is already set in the Dockerfile (ENV PYTHONPATH=/app),
# so this script must NOT redefine it. Kept as a single-token command so Railway's
# exec-form start command cannot mis-parse an env-var prefix as the executable.

echo "=== TG Parser worker startup ==="
echo "Python: $(python --version)"

exec python -m app.worker
