FROM python:3.8.12-alpine3.14
RUN mkdir -p /src/api
WORKDIR /src/api

# Install dependencies
RUN pip install requests

# Copy scripts
COPY api/* ./
COPY docker-images/api.sh ./

ENTRYPOINT ["./api.sh"]
