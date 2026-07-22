FROM node:20-slim

WORKDIR /app

# Copy the lockfile too, so the image installs the exact versions the repo
# pins rather than re-resolving semver ranges at build time.
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

CMD ["npm", "run", "dev"]
