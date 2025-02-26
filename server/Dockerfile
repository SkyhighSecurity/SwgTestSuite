# Use the official Nginx image
FROM nginx:latest

# Copy website files
COPY server_content /usr/share/nginx/html

# Copy SSL certificate and key
COPY cert.pem /etc/nginx/ssl/cert.pem
COPY key.pem /etc/nginx/ssl/key.pem

# Copy the Nginx configuration file
COPY nginx.conf /etc/nginx/nginx.conf

# Expose ports
EXPOSE 80
EXPOSE 443