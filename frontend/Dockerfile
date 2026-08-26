FROM node:22-alpine

WORKDIR /app

# Evita o download dos navegadores do Playwright na imagem de runtime.
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# Build determinista: usa o lockfile (npm ci) em vez de npm install.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
