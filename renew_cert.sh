#!/bin/bash
docker run --rm \
  -v "/srv/vidmore/nginx/certbot/conf:/etc/letsencrypt" \
  -v "/srv/vidmore/nginx/certbot/www:/var/www/certbot" \
  certbot/certbot renew
docker-compose exec nginx nginx -s reload
