# OpenBSD httpd Configuration for Review System

## Current Configuration Issues

The existing stephanos.symmachus.org configuration (lines 430-442 in /etc/httpd.conf) has a bug:

```
location "/cgi-bin/*" {
    fastcgi
    root "/vhosts/www.symmachus.org"   # <-- WRONG PATH!
}
```

This points to the wrong vhost directory.

## Required Changes

Edit `/etc/httpd.conf` on merah and update the stephanos.symmachus.org server block:

### Replace Lines 430-442 With:

```
server "stephanos.symmachus.org" {
	log style combined
        directory { auto index }
        listen on $listen_addr port 80
        root "/vhosts/stephanos.symmachus.org/htdocs"

        # Protected images - already configured correctly
        location "/protected/*" {
           authenticate "Private Area" with "/vhosts/stephanos.symmachus.org/etc/htpasswd"
        }

        # Review system CGI programs - FIXED PATH + ADD AUTH
        location "/cgi-bin/*.cgi" {
            fastcgi
            root "/vhosts/stephanos.symmachus.org"
            authenticate "Stephanos Review System" with "/vhosts/stephanos.symmachus.org/etc/htpasswd"
        }

        # Block access to database directory
        location "/db/*" {
            block
        }
}
```

### Key Changes:

1. **Fixed cgi-bin root path**: Changed from `/vhosts/www.symmachus.org` to `/vhosts/stephanos.symmachus.org`
2. **Added authentication to CGI**: Review system now requires same auth as /protected
3. **Added /db block**: Prevents web access to SQLite database
4. **Specific *.cgi pattern**: Only CGI files, not all /cgi-bin content

## Deployment Steps

### 1. Deploy CGI Programs

```bash
# On merah
cd /var/www/vhosts/stephanos.symmachus.org
mkdir -p cgi-bin db

# Copy binaries from raksasa
scp stephanos@raksasa:~/stephanos/review_cgi/review.cgi cgi-bin/
scp stephanos@raksasa:~/stephanos/review_cgi/save.cgi cgi-bin/

# Set permissions
chmod 755 cgi-bin/*.cgi
chown www:www cgi-bin/*.cgi

# Create database directory
chmod 755 db
chown www:www db
```

### 2. Initialize SQLite Database

```bash
# On merah
cd /var/www/vhosts/stephanos.symmachus.org/cgi-bin

# Copy schema
scp stephanos@raksasa:~/stephanos/review_cgi/init_schema.sql /tmp/

# Initialize database
sqlite3 ../db/reviews.db < /tmp/init_schema.sql

# Set permissions
chmod 664 ../db/reviews.db
chown www:www ../db/reviews.db
```

### 3. Deploy Review Data JSON

```bash
# On raksasa, export data
cd ~/stephanos
uv run export_for_review.py

# Copy to merah
scp review_data.json stephanos@merah:/var/www/vhosts/stephanos.symmachus.org/db/

# On merah, set permissions
chmod 644 /var/www/vhosts/stephanos.symmachus.org/db/review_data.json
chown www:www /var/www/vhosts/stephanos.symmachus.org/db/review_data.json
```

### 4. Setup HTTP Basic Auth Users

The htpasswd file already exists at `/vhosts/stephanos.symmachus.org/etc/htpasswd` (used by /protected).

To add review users:

```bash
# On merah
cd /var/www/vhosts/stephanos.symmachus.org/etc

# Add a new user
htpasswd htpasswd reviewer1

# Or use the setup script (copy from raksasa)
# scp stephanos@raksasa:~/stephanos/review_cgi/setup_reviewers.sh /tmp/
# Edit paths in script to match /vhosts/stephanos.symmachus.org/etc/htpasswd
# sh /tmp/setup_reviewers.sh
```

### 5. Update httpd.conf

```bash
# On merah
# Edit /etc/httpd.conf using the changes shown above
vi /etc/httpd.conf

# Test configuration
httpd -n

# If OK, restart httpd
rcctl restart httpd
```

### 6. Verify Deployment

```bash
# Check CGI programs exist
ls -l /var/www/vhosts/stephanos.symmachus.org/cgi-bin/

# Check database exists
ls -l /var/www/vhosts/stephanos.symmachus.org/db/

# Check data file exists
ls -lh /var/www/vhosts/stephanos.symmachus.org/db/review_data.json

# Test CGI access (should prompt for authentication)
curl -I http://stephanos.symmachus.org/cgi-bin/review.cgi

# Test with authentication (replace user:pass)
curl -u reviewer1:password http://stephanos.symmachus.org/cgi-bin/review.cgi | head -50
```

## File Locations Reference

| File | Location on merah |
|------|-------------------|
| CGI binaries | `/var/www/vhosts/stephanos.symmachus.org/cgi-bin/*.cgi` |
| SQLite database | `/var/www/vhosts/stephanos.symmachus.org/db/reviews.db` |
| Review data JSON | `/var/www/vhosts/stephanos.symmachus.org/db/review_data.json` |
| htpasswd file | `/var/www/vhosts/stephanos.symmachus.org/etc/htpasswd` |
| Page images | `/var/www/vhosts/stephanos.symmachus.org/htdocs/protected/*.jpg` |
| httpd config | `/etc/httpd.conf` |

## Path Mapping (Important!)

OpenBSD httpd runs in a chroot at `/var/www`. Paths in configuration are relative to this:

| In httpd.conf | Actual filesystem path |
|---------------|------------------------|
| `/htdocs` | `/var/www/htdocs` (default server) |
| `/vhosts/stephanos.symmachus.org/htdocs` | `/var/www/vhosts/stephanos.symmachus.org/htdocs` |
| `/vhosts/stephanos.symmachus.org/etc/htpasswd` | `/var/www/vhosts/stephanos.symmachus.org/etc/htpasswd` |

When CGI programs run, they also operate within the chroot, so:
- Config paths in Go code should use `/var/www/vhosts/...` (full path)
- OR we need to update common.go to use chroot-relative paths

## Troubleshooting

### CGI not executing
```bash
# Check slowcgi is running
rcctl check slowcgi
rcctl start slowcgi

# Check CGI permissions
ls -l /var/www/vhosts/stephanos.symmachus.org/cgi-bin/

# Check httpd logs
tail -f /var/log/httpd/error.log
tail -f /var/log/httpd/access.log
```

### Authentication not working
```bash
# Verify htpasswd file exists
ls -l /var/www/vhosts/stephanos.symmachus.org/etc/htpasswd

# Test user
htpasswd -v /var/www/vhosts/stephanos.symmachus.org/etc/htpasswd username
```

### Database not found
```bash
# Check paths in common.go match actual filesystem
# Remember: CGI runs in chroot at /var/www/
```

## Next Steps After Deployment

1. Test review interface in browser: `http://stephanos.symmachus.org/cgi-bin/review.cgi`
2. Verify images load correctly from /protected/
3. Test saving a review
4. Check that review data is written to SQLite
5. Set up daily cron job to sync data back to raksasa (Phase 5)
