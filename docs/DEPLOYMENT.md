# Deployment Guide

This guide covers deploying 3-GAL to various platforms.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Heroku Deployment](#heroku-deployment)
- [PythonAnywhere Deployment](#pythonanywhere-deployment)
- [AWS Deployment](#aws-deployment)
- [DigitalOcean Deployment](#digitalocean-deployment)
- [Docker Deployment](#docker-deployment)
- [Nginx + Gunicorn (VPS)](#nginx--gunicorn-vps)

## Prerequisites

Before deploying, ensure you have:

- Git installed
- Python 3.8+ (for local testing)
- A GitHub account (for some platforms)
- Account on your target platform

## Heroku Deployment

### Step 1: Create Required Files

**Procfile** (create in root directory):
```
web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2
```

**runtime.txt**:
```
python-3.10.12
```

### Step 2: Deploy

```bash
# Install Heroku CLI
curl https://cli-assets.heroku.com/install.sh | sh

# Login
heroku login

# Create app
heroku create your-3gal-app

# Add buildpack
heroku buildpacks:set heroku/python

# Deploy
git push heroku main

# Open app
heroku open
```

### Step 3: Configure Environment

```bash
heroku config:set FLASK_DEBUG=False
```

## PythonAnywhere Deployment

### Step 1: Sign Up

1. Go to https://www.pythonanywhere.com
2. Create a free account (or paid for custom domain)

### Step 2: Clone Repository

1. Open a **Bash console** from the Dashboard
2. Run:
   ```bash
   git clone https://github.com/anacondy/3-GAL.git
   cd 3-GAL
   ```

### Step 3: Create Virtual Environment

```bash
mkvirtualenv --python=/usr/bin/python3.10 3gal-env
pip install -r requirements.txt
```

### Step 4: Configure Web App

1. Go to **Web** tab
2. Click **Add a new web app**
3. Choose **Manual configuration** → **Python 3.10**
4. Set:
   - Source code: `/home/yourusername/3-GAL`
   - Working directory: `/home/yourusername/3-GAL`
   - Virtualenv: `/home/yourusername/.virtualenvs/3gal-env`

### Step 5: Edit WSGI File

In the WSGI configuration file:

```python
import sys
import os

# Add your project directory to the sys.path
project_home = '/home/yourusername/3-GAL'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set working directory
os.chdir(project_home)

# Import Flask app
from app import app as application
```

### Step 6: Reload

Click **Reload** button on the Web tab.

## AWS Deployment

### Option 1: Elastic Beanstalk

1. Install EB CLI:
   ```bash
   pip install awsebcli
   ```

2. Initialize:
   ```bash
   eb init -p python-3.10 3-gal-app
   ```

3. Create environment:
   ```bash
   eb create 3-gal-env
   ```

4. Deploy:
   ```bash
   eb deploy
   ```

### Option 2: EC2 Instance

1. Launch EC2 instance (Ubuntu 22.04 recommended)
2. SSH into instance
3. Install dependencies:
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-venv nginx
   ```
4. Clone and setup (see Nginx + Gunicorn section)

## DigitalOcean Deployment

### App Platform (Recommended)

1. Go to DigitalOcean App Platform
2. Connect GitHub repository
3. Configure:
   - Run Command: `gunicorn app:app --bind 0.0.0.0:$PORT`
   - HTTP Port: 8080

### Droplet (Manual)

1. Create Ubuntu droplet
2. SSH into droplet
3. Follow Nginx + Gunicorn section below

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 5007

# Set environment variables
ENV FLASK_DEBUG=False
ENV PYTHONUNBUFFERED=1

# Run with gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5007", "--workers", "2", "--threads", "2"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5007:5007"
    volumes:
      - ./data:/app/data
    environment:
      - FLASK_DEBUG=False
    restart: unless-stopped
```

### Build and Run

```bash
# Build image
docker build -t 3-gal .

# Run container
docker run -d -p 5007:5007 --name 3gal-app 3-gal

# Or with docker-compose
docker-compose up -d
```

## Nginx + Gunicorn (VPS)

For any Linux VPS (AWS EC2, DigitalOcean Droplet, Linode, etc.)

### Step 1: Install Dependencies

```bash
sudo apt update
sudo apt install python3-pip python3-venv nginx
```

### Step 2: Clone and Setup

```bash
cd /var/www
sudo git clone https://github.com/anacondy/3-GAL.git
cd 3-GAL

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

### Step 3: Create Systemd Service

Create `/etc/systemd/system/3gal.service`:

```ini
[Unit]
Description=3-GAL Gunicorn Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/3-GAL
Environment="PATH=/var/www/3-GAL/venv/bin"
ExecStart=/var/www/3-GAL/venv/bin/gunicorn --workers 3 --bind unix:3gal.sock -m 007 app:app

[Install]
WantedBy=multi-user.target
```

### Step 4: Configure Nginx

Create `/etc/nginx/sites-available/3gal`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/3-GAL/3gal.sock;
    }

    location /static {
        alias /var/www/3-GAL/static;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/3gal /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

### Step 5: Start Service

```bash
sudo systemctl start 3gal
sudo systemctl enable 3gal
```

### Step 6: SSL (Optional but Recommended)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   lsof -i :5007
   kill -9 <PID>
   ```

2. **Permission denied**
   ```bash
   sudo chown -R www-data:www-data /var/www/3-GAL
   ```

3. **Module not found**
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Database locked**
   - Restart the service
   - Check for zombie processes

### Logs

- Heroku: `heroku logs --tail`
- Systemd: `journalctl -u 3gal -f`
- Nginx: `tail -f /var/log/nginx/error.log`
