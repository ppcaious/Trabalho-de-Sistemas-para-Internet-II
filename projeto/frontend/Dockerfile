FROM nginx:1.27-alpine

# Página estática (HTML/CSS/JS puro) + proxy reverso de /api para o backend
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY public/ /usr/share/nginx/html/

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
