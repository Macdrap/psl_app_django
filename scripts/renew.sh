#!/bin/bash
certbot renew --webroot -w /opt/psl-app/certbot/www
cp -rL /etc/letsencrypt /opt/psl-app/certbot/conf/
docker-compose --env-file /opt/psl-app/.env -f /opt/psl-app/docker/docker-compose.prod.yml restart nginx