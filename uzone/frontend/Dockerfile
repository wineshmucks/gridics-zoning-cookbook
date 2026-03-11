FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json tsconfig.json next-env.d.ts next.config.js /app/
COPY src /app/src
COPY entrypoint.sh /app/entrypoint.sh

RUN npm ci && chmod +x /app/entrypoint.sh

EXPOSE 3001

ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
