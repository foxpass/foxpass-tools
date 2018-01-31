# FoxPass Tools

## Docker images

We provide different docker images to run our utilities.

### API Docker Image

In order to create an image for the API, use the following command:

```sh
docker build -f './docker-images/api.Dockerfile' . -t 'foxpass-api'
```

Now you can run the docker image with:

```sh
docker run foxpass-api <action> [<options>]
```

Use the following command to obtain more help:

```sh
docker run foxpass-api

# Help example:
#  Usage:
#    docker run foxpass <action> [<options>]
#  Actions: list_groups list_users copy_group posix_user delete_group deactivate_user
#  Examples:
#    docker run foxpass copy_group [<options>]
#    docker run foxpass deactivate_user [<options>]
```
