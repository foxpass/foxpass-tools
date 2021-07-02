FROM python:2.7.18-alpine3.11
RUN mkdir -p /src/api
WORKDIR /src/api

# Install dependencies
RUN pip install requests

# Copy scripts
COPY api/* ./
COPY docker-images/api.sh ./

ENTRYPOINT ["./api.sh"]
