FROM node:20-alpine

WORKDIR /app

COPY package.json tsconfig.json next-env.d.ts next.config.js /app/
COPY src /app/src

RUN npm install

EXPOSE 3001

CMD ["npm", "run", "dev"]

