# Caddy Setup Guide for Sarthi

This guide explains how to set up Sarthi with Caddy as the reverse proxy, which provides automatic SSL/TLS certificates from Let's Encrypt.

## Why Caddy?

- **Automatic HTTPS**: Caddy automatically obtains and renews SSL certificates from Let's Encrypt
- **Simple Configuration**: Easier to configure than Nginx for SSL
- **Wildcard Support**: Supports wildcard domains with DNS challenge (requires DNS provider configuration)
- **Built-in Certificate Management**: No need for external tools like Certbot

## Prerequisites

1. A public Linux machine (Ubuntu 20+ LTS recommended) with root access
2. A wildcard domain pointing to your machine (e.g., `*.sarthi.yourcompany.io`)
3. Port 80 and 443 open on your firewall
4. A valid email address for Let's Encrypt notifications

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/tushar5526/sarthi.git
cd sarthi
```

### 2. Run the Caddy Setup Script

```bash
chmod +x setup-sarthi-caddy.sh
sudo ./setup-sarthi-caddy.sh
```

### 3. Follow the Prompts

The script will ask you for:

- **ENV**: Environment setting (default: local)
- **DOMAIN_NAME**: Your wildcard domain (e.g., sarthi.yourcompany.io)
- **CADDY_EMAIL**: Email for Let's Encrypt certificate notifications
- **SECRET_TEXT**: Authentication secret (will be auto-generated if not provided)

### 4. Access Your Services

After setup, your services will be available at:

- **Vault**: https://vault.sarthi.yourcompany.io
- **Portainer**: https://portainer.sarthi.yourcompany.io
- **Sarthi API**: https://api.sarthi.yourcompany.io
- **Grafana**: https://grafana.sarthi.yourcompany.io

All connections are automatically secured with SSL!

## Wildcard Domain Configuration

For wildcard SSL certificates (e.g., `*.sarthi.yourcompany.io`), you need to configure DNS validation.

### Using Cloudflare DNS

1. Add the Cloudflare DNS module to your Caddyfile:

```caddyfile
{
    acme_dns cloudflare {env.CLOUDFLARE_API_TOKEN}
}
```

2. Add your Cloudflare API token to the `.env` file:

```bash
CLOUDFLARE_API_TOKEN=your_token_here
```

3. Update the docker-compose-caddy.yml to pass the token to Caddy:

```yaml
environment:
  CLOUDFLARE_API_TOKEN: ${CLOUDFLARE_API_TOKEN}
```

### Other DNS Providers

Caddy supports many DNS providers through modules:
- AWS Route53
- Google Cloud DNS
- DigitalOcean
- And many more!

See [Caddy DNS Modules](https://caddyserver.com/docs/modules/) for the full list.

## Switching from Nginx to Caddy

If you have an existing Sarthi installation with Nginx and want to switch to Caddy:

### 1. Stop Existing Services

```bash
docker-compose down
```

### 2. Backup Configuration

```bash
cp .env .env.backup
```

### 3. Update Environment Variables

```bash
# Update .env file
PROXY_TYPE=caddy
CADDY_PROXY_CONF_LOCATION='$PWD/caddy-confs'
CADDY_EMAIL='your-email@example.com'
```

### 4. Start with Caddy

```bash
docker-compose -f docker-compose-caddy.yml up -d
```

## Configuration Files

### Caddyfile

The main Caddy configuration file is generated from `Caddyfile.template`:

```caddyfile
{
    email your-email@example.com
    auto_https on
}

vault.yourdomain.io {
    reverse_proxy vault:8200
}

# Import deployment configurations
import /etc/caddy/conf.d/*.caddy
```

### Deployment Configurations

Each deployment gets its own `.caddy` file in the `caddy-confs/` directory with automatic SSL:

```caddyfile
myapp-feature-branch-3000-abc123.yourdomain.io {
    reverse_proxy myapp:3000
}
```

## Troubleshooting

### Certificate Errors

If you see certificate-related errors:

1. Check your domain DNS is pointing correctly:
```bash
dig vault.sarthi.yourcompany.io
```

2. Check Caddy logs:
```bash
docker logs sarthi_caddy
```

3. Verify ports 80 and 443 are accessible:
```bash
nc -zv yourip 80
nc -zv yourip 443
```

### Using Let's Encrypt Staging

For testing, you can use Let's Encrypt's staging environment to avoid rate limits:

Edit your `Caddyfile` and uncomment:
```caddyfile
{
    acme_ca https://acme-staging-v02.api.letsencrypt.org/directory
}
```

### Manual Certificate Management

To manually obtain certificates:

```bash
docker exec sarthi_caddy caddy reload --config /etc/caddy/Caddyfile
```

## Architecture Differences

### Nginx Setup (Original)
- Manual SSL setup required (Certbot, etc.)
- HTTP only by default
- Configuration in `.conf` files
- Container name: `sarthi_nginx`

### Caddy Setup (New)
- Automatic SSL with Let's Encrypt
- HTTPS by default
- Configuration in `.caddy` files and `Caddyfile`
- Container name: `sarthi_caddy`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROXY_TYPE` | `nginx` | Set to `caddy` to use Caddy |
| `CADDY_PROXY_CONF_LOCATION` | `/etc/caddy/conf.d` | Directory for deployment configs |
| `CADDY_EMAIL` | `admin@example.com` | Email for Let's Encrypt |
| `DOMAIN_NAME` | `localhost` | Your domain name |

## Performance Considerations

- **Certificate Caching**: Caddy caches certificates in the `caddy_data` volume
- **Automatic Renewal**: Certificates are automatically renewed before expiration
- **Resource Usage**: Caddy is lightweight and efficient, similar to Nginx

## Security Best Practices

1. Always use a valid email for Let's Encrypt notifications
2. Keep Caddy updated: `docker pull caddy:2.7-alpine`
3. Use strong passwords for Vault and Portainer
4. Regularly review Caddy logs for suspicious activity
5. Consider using DNS validation for wildcard certificates

## Support

For issues specific to:
- **Caddy**: See [Caddy Documentation](https://caddyserver.com/docs/)
- **Sarthi**: Open an issue on [GitHub](https://github.com/tushar5526/sarthi/issues)
- **Let's Encrypt**: See [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
