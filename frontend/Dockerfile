# Stage 1: Build stage
FROM alpine:latest AS builder

WORKDIR /app

# Copy frontend assets
# In a typical setup, this stage might run `npm install` and `npm run build`
# Since this is a vanilla HTML/JS/CSS frontend, we prepare the static files here.
COPY . .

# Stage 2: Production Server stage
FROM nginx:alpine

# Remove default nginx website
RUN rm -rf /usr/share/nginx/html/*

# Copy frontend assets from builder stage
COPY --from=builder /app /usr/share/nginx/html

# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
