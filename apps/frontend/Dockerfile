FROM node:22-alpine

WORKDIR /app

COPY apps/frontend/package*.json ./
RUN npm install

COPY apps/frontend .

EXPOSE 5173
