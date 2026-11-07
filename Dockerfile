FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY index.html styles.css data.js robots.txt /srv/
COPY assets /srv/assets
