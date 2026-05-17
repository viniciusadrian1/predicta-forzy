FROM node:22-alpine

WORKDIR /app

# Evita o download dos navegadores do Playwright na imagem de runtime.
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
