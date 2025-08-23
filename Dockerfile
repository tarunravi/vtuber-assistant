FROM nikolaik/python-nodejs:python3.11-nodejs20

WORKDIR /app

# Copy the entire project into the image (no bind mounts at runtime)
COPY . /app

# Ensure startup script is executable
RUN chmod +x start.sh

# Expose only the frontend port for Vite dev server
EXPOSE 5173

CMD ["./start.sh"]


