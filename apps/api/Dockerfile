# ScrollWise API as a Lambda container image.
#
# Why a container (not a zip): the API has native deps (asyncpg, bcrypt,
# pydantic-core) that must be built for Amazon Linux. The AWS Lambda Python base
# image IS Amazon Linux, so pip pulls the right manylinux wheels and the result
# is guaranteed to match the Lambda runtime.
#
# Build + push (see infra/aws/api/README.md):
#   docker build --platform linux/amd64 -t scrollwise-api apps/api
#   docker tag / docker push to ECR, then point the Lambda at the image.
FROM public.ecr.aws/lambda/python:3.12

# Dependencies first, so the layer caches unless requirements change.
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Application code (the `app` package). Migrations/tests are not needed at runtime.
COPY app/ ${LAMBDA_TASK_ROOT}/app/

# Lambda calls this handler per request. Mangum bridges API Gateway <-> ASGI.
CMD [ "app.lambda_handler.handler" ]
