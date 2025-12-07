# Multi-stage build para Angular Frontend

# Stage 1: Build
FROM node:20-alpine AS build

WORKDIR /app

# Copiar package files
COPY package*.json ./

# Instalar dependencias
RUN npm ci

# Copiar código fuente
COPY . .

# Build de producción
RUN npm run build

# Stage 2: Serve con nginx
FROM nginx:alpine

# Copiar build de Angular
COPY --from=build /app/dist/tf-frontend/browser /usr/share/nginx/html

# Copiar configuración de nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Exponer puerto 8080 (Cloud Run requirement)
EXPOSE 8080

# Nginx correrá automáticamente
CMD ["nginx", "-g", "daemon off;"]
