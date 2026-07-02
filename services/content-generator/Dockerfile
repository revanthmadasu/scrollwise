# ScrollWise content-generator as a Fargate task image.
#
# Unlike apps/api (a Lambda container that uses the AWS Lambda base image + the
# Runtime Interface), this runs as a plain container on ECS/Fargate: the task is
# started (EventBridge Scheduler -> RunTask, or later SQS-driven), drains the
# `user_prompts` queue via `scripts/drain_prompts.py --once`, and exits. No
# 15-min cap, so big topics / per-asset LLM generation are safe.
#
# arm64 (Graviton) — ~20% cheaper on Fargate. Build native on an M-series Mac.
#
# Build + push (see infra/aws/generator/README.md):
#   docker build --platform linux/arm64 -t scrollwise-generator services/content-generator
#   docker tag / docker push to ECR scrollwise-generator, then point the ECS task def at it.
FROM --platform=linux/arm64 python:3.12-slim

WORKDIR /app

# Dependencies first, so the layer caches unless requirements change.
# psycopg2-binary, Pillow and numpy all ship manylinux arm64 wheels, so no
# build toolchain is needed.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code. Tests and dev-only scripts are excluded via .dockerignore.
COPY generators/ ./generators/
COPY storage/ ./storage/
COPY scripts/ ./scripts/
COPY prompts/ ./prompts/
COPY data/ ./data/

# One drain pass, then exit (scale-to-zero scheduled task). Args can be tuned in
# the task def, e.g. add --batch-size 3 / --modules 2.
CMD ["python", "-m", "scripts.drain_prompts", "--once"]
