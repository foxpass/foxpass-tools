# Usage:
#   - Build image:
#     docker build -f api.Dockerfile .. -t foxpass-api
#
#   - Run:
#     docker run foxpass-api <action> <options>
#
#     Action = Name of the script without "foxpass_" prefix and without ".py" suffix
#     Example:
#       docker run foxpass-api copy_group <options>
#       docker run foxpass-api deactivate_user <optio]ns>
#       docker run foxpass-api delete_group <options>

FROM python:3.6.4-alpine3.7
RUN mkdir -p /src/api
WORKDIR /src/api

# Install dependencies
RUN pip install requests

# Copy scripts
COPY api/* ./
COPY docker-images/api.sh ./

ENTRYPOINT ["./api.sh"]
