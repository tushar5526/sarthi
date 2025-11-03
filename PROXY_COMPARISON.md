# Nginx vs Caddy: Choosing the Right Proxy for Sarthi

This document helps you decide which reverse proxy to use for your Sarthi deployment.

## Quick Comparison

| Feature | Nginx | Caddy |
|---------|-------|-------|
| **SSL/TLS** | Manual setup required | Automatic with Let's Encrypt |
| **Configuration Syntax** | Complex | Simple |
| **Certificate Renewal** | Manual (Certbot) | Automatic |
| **Wildcard Domains** | Requires DNS challenge setup | Built-in DNS challenge support |
| **Performance** | Excellent | Excellent |
| **Maturity** | Very mature | Mature |
| **Default Protocol** | HTTP | HTTPS |
| **Learning Curve** | Steeper | Gentler |

## When to Use Nginx

Choose Nginx if:

✅ You already have Nginx expertise  
✅ You need maximum control over configuration  
✅ You're running in an environment without internet access for Let's Encrypt  
✅ You have existing Nginx infrastructure  
✅ You prefer manual SSL certificate management  
✅ You're using localhost or don't need SSL  

### Nginx Setup Command
```bash
sudo ./setup-sarthi.sh
```

### Nginx Pros
- Battle-tested and extremely reliable
- More configuration options and modules
- Well-documented across the internet
- Default choice, more stable

### Nginx Cons
- Requires manual SSL setup with Certbot
- More complex configuration syntax
- Certificate renewal needs separate tooling
- More maintenance overhead for SSL

## When to Use Caddy

Choose Caddy if:

✅ You want automatic SSL/TLS certificates  
✅ You have a public domain with DNS access  
✅ You prefer simpler configuration  
✅ You want automatic certificate renewal  
✅ You're new to reverse proxies  
✅ You need wildcard SSL certificates  

### Caddy Setup Command
```bash
sudo ./setup-sarthi-caddy.sh
```

### Caddy Pros
- Automatic HTTPS with zero configuration
- Simple, readable Caddyfile syntax
- Automatic certificate renewal
- Built-in DNS challenge for wildcards
- Less maintenance overhead

### Caddy Cons
- Requires internet access for Let's Encrypt
- Less mature than Nginx (but still production-ready)
- Fewer third-party modules
- May require DNS provider API tokens for wildcards

## Configuration Examples

### Nginx Configuration (manual)
```nginx
server {
    listen 80;
    server_name myapp.sarthi.example.com;
    
    location / {
        proxy_pass http://myapp:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# SSL requires separate Certbot setup
```

### Caddy Configuration (automatic SSL)
```caddyfile
myapp.sarthi.example.com {
    reverse_proxy myapp:3000
}

# SSL certificates automatically obtained and renewed!
```

## Environment Variables

### Common Variables (Both)
```bash
DEPLOYMENTS_MOUNT_DIR='/path/to/deployments'
ENV='prod'
DOMAIN_NAME='sarthi.yourcompany.io'
SECRET_TEXT='your-secret-token'
VAULT_TOKEN='your-vault-token'
```

### Nginx-Specific
```bash
PROXY_TYPE='nginx'  # or omit, as nginx is default
NGINX_PROXY_CONF_LOCATION='/path/to/nginx-confs'
```

### Caddy-Specific
```bash
PROXY_TYPE='caddy'
CADDY_PROXY_CONF_LOCATION='/path/to/caddy-confs'
CADDY_EMAIL='admin@yourcompany.io'
```

## Migration Between Proxies

### Nginx to Caddy

1. Stop Nginx services:
```bash
docker-compose down
```

2. Update `.env` file:
```bash
PROXY_TYPE='caddy'
CADDY_PROXY_CONF_LOCATION='$PWD/caddy-confs'
CADDY_EMAIL='your-email@example.com'
```

3. Start with Caddy:
```bash
docker-compose -f docker-compose-caddy.yml up -d
```

### Caddy to Nginx

1. Stop Caddy services:
```bash
docker-compose -f docker-compose-caddy.yml down
```

2. Update `.env` file:
```bash
PROXY_TYPE='nginx'
NGINX_PROXY_CONF_LOCATION='$PWD/nginx-confs'
# Remove CADDY_EMAIL
```

3. Start with Nginx:
```bash
docker-compose up -d
```

## Performance Considerations

Both Nginx and Caddy have excellent performance characteristics:

- **Nginx**: Slightly lower memory footprint in some scenarios
- **Caddy**: Comparable performance with Go's efficient runtime
- **SSL Overhead**: Minimal difference for both

For typical Sarthi deployments, performance difference is negligible.

## Security Considerations

### Nginx Security
- Manual SSL means you control the entire certificate lifecycle
- More granular security controls available
- Requires discipline for certificate renewal

### Caddy Security
- Automatic certificate renewal reduces human error
- Always uses the latest TLS protocols
- Built-in security best practices
- Requires trust in automatic certificate management

## Wildcard Domain Support

### Nginx with Certbot
```bash
# Requires DNS challenge setup
certbot certonly --dns-cloudflare \
  --dns-cloudflare-credentials ~/.secrets/cloudflare.ini \
  -d '*.sarthi.example.com'
```

### Caddy with DNS Challenge
```caddyfile
{
    acme_dns cloudflare {env.CLOUDFLARE_API_TOKEN}
}

*.sarthi.example.com {
    reverse_proxy host.docker.internal:8080
}
```

## Recommendation

**For Production with Public Domain**: Choose **Caddy**
- Automatic SSL reduces operational overhead
- More secure due to automatic renewals
- Simpler configuration reduces errors

**For Development or Internal Networks**: Choose **Nginx**
- No SSL complexity needed
- More familiar to most teams
- Doesn't require internet access

**Already Have Nginx Experience**: Stick with **Nginx**
- Your existing knowledge is valuable
- Migration might not provide enough benefit

## Getting Help

- **Nginx Issues**: Check Nginx documentation or Sarthi GitHub issues
- **Caddy Issues**: See [CADDY_SETUP.md](CADDY_SETUP.md) or Caddy forums
- **General Sarthi Issues**: Open an issue on [GitHub](https://github.com/tushar5526/sarthi/issues)

## Conclusion

Both options are production-ready. Choose based on your needs:

- **Simplicity + Automatic SSL** → Caddy
- **Maximum Control + Familiarity** → Nginx

You can always switch later if needed!
