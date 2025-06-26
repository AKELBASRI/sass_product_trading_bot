#!/bin/bash

# Exit on any error
set -e

# Colors for prettier output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Setting up React Trading Dashboard ===${NC}"

# Create frontend directory if it doesn't exist
if [ ! -d "frontend" ]; then
  echo -e "${GREEN}Creating frontend directory...${NC}"
  mkdir -p frontend
  mkdir -p frontend/src
  mkdir -p frontend/public
  mkdir -p frontend/src/components
  mkdir -p frontend/src/context
  mkdir -p nginx
fi

# Copy Nginx configuration
echo -e "${GREEN}Creating Nginx configuration directory...${NC}"
mkdir -p nginx

# Create frontend structure
echo -e "${GREEN}Setting up React project structure...${NC}"

# Initialize npm project if not already initialized
if [ ! -f "frontend/package.json" ]; then
  echo -e "${GREEN}Initializing npm project...${NC}"
  cd frontend
  npm init -y
  
  # Install dependencies
  echo -e "${GREEN}Installing dependencies...${NC}"
  npm install react react-dom react-scripts lightweight-charts axios
  npm install --save-dev @testing-library/jest-dom @testing-library/react @testing-library/user-event web-vitals
  
  # Add scripts to package.json
  echo -e "${GREEN}Updating package.json scripts...${NC}"
  sed -i 's/"test": "echo \\"Error: no test specified\\" && exit 1"/"start": "react-scripts start",\n    "build": "react-scripts build",\n    "test": "react-scripts test",\n    "eject": "react-scripts eject"/' package.json
  
  # Add browserlist to package.json
  echo -e "${GREEN}Adding browserlist to package.json...${NC}"
  cat > browserslist.tmp << EOF
  "browserslist": {
    "production": [
      ">0.2%",
      "not dead",
      "not op_mini all"
    ],
    "development": [
      "last 1 chrome version",
      "last 1 firefox version",
      "last 1 safari version"
    ]
  }
EOF
  
  # Insert browserslist before the last closing brace
  sed -i '/}$/i\,'"$(cat browserslist.tmp)" package.json
  
  # Clean up temp file
  rm browserslist.tmp
  
  cd ..
fi

# Create nginx configuration
echo -e "${GREEN}Creating Nginx configuration...${NC}"
cat > nginx/react-nginx.conf << 'EOF'
server {
    listen 80;
    
    # React app
    location / {
        root /usr/share/nginx/html;
        index index.html index.htm;
        try_files $uri $uri/ /index.html;
    }
    
    # API proxy - forward requests to Flask backend
    location /api/ {
        proxy_pass http://trading-backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Create Dockerfile
echo -e "${GREEN}Creating Dockerfile for React dashboard...${NC}"
cat > Dockerfile.react-dashboard << 'EOF'
# Build stage
FROM node:18-alpine AS build

WORKDIR /app

# Copy package files and install dependencies
COPY ./frontend/package*.json ./
RUN npm install

# Copy all files and build
COPY ./frontend ./
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files from build stage to nginx
COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx configuration
COPY ./nginx/react-nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
EOF

# Update docker-compose.yml
echo -e "${GREEN}Updating docker-compose.yml to include React dashboard...${NC}"
cat > docker-compose.react.yml << 'EOF'
services:
  # Direct connector (generates demo data)
  mt5-connector:
    build:
      context: .
      dockerfile: Dockerfile.direct
    container_name: mt5-connector
    depends_on:
      - redis
    restart: unless-stopped
    networks:
      - trading-network

  # Redis Service
  redis:
    image: redis:7-alpine
    container_name: trading-redis
    ports:
      - "6382:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - trading-network

  # Trading Backend Service
  trading-backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    container_name: trading-backend
    environment:
      - PYTHONUNBUFFERED=1
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    depends_on:
      - redis
      - mt5-connector
    volumes:
      - ./trading_system:/app/trading_system
      - ./logs:/app/logs
    ports:
      - "8009:8000"
    restart: unless-stopped
    networks:
      - trading-network

  # React Dashboard Service
  react-dashboard:
    build:
      context: .
      dockerfile: Dockerfile.react-dashboard
    container_name: react-dashboard
    ports:
      - "3000:80"
    depends_on:
      - trading-backend
    restart: unless-stopped
    networks:
      - trading-network

volumes:
  redis_data:

networks:
  trading-network:
    driver: bridge
EOF

echo -e "${YELLOW}Setup complete! Next steps:${NC}"
echo -e "${GREEN}1. Copy your React components to the frontend directory${NC}"
echo -e "${GREEN}2. Run docker-compose -f docker-compose.react.yml up -d${NC}"
echo -e "${GREEN}3. Access your new React dashboard at http://localhost:3000${NC}"
