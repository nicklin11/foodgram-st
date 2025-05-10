# ../frontend/Dockerfile

# build env
FROM node:21.7.1-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . ./
RUN npm run build

# Copy the *contents* of /app/build into /app/result_build
CMD cp -r build/. result_build/