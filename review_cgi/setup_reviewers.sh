#!/bin/bash
# Setup HTTP Basic Auth users for review system
# Run this script on merah as root or with sudo

set -e

HTPASSWD_FILE="/var/www/vhosts/stephanos.symmachus.org/.htpasswd"
VHOST_DIR="/var/www/vhosts/stephanos.symmachus.org"

echo "=== Stephanos Review System - User Setup ==="
echo

# Check if running with sufficient privileges
if [ ! -w "$VHOST_DIR" ]; then
    echo "Error: Need write access to $VHOST_DIR"
    echo "Run with sudo or as root"
    exit 1
fi

# Check if htpasswd command exists
if ! command -v htpasswd &> /dev/null; then
    echo "Error: htpasswd command not found"
    echo "Install with: yum install httpd-tools"
    exit 1
fi

echo "Password file: $HTPASSWD_FILE"
echo

# If file exists, show current users
if [ -f "$HTPASSWD_FILE" ]; then
    echo "Current users:"
    cut -d: -f1 "$HTPASSWD_FILE" | while read user; do
        echo "  - $user"
    done
    echo
fi

# Menu
echo "Choose an action:"
echo "  1) Add new user"
echo "  2) Change password for existing user"
echo "  3) Delete user"
echo "  4) List all users"
echo "  5) Exit"
echo
read -p "Choice [1-5]: " choice

case $choice in
    1)
        read -p "Enter username: " username
        if [ -z "$username" ]; then
            echo "Error: Username cannot be empty"
            exit 1
        fi

        if [ -f "$HTPASSWD_FILE" ]; then
            # Append to existing file
            htpasswd "$HTPASSWD_FILE" "$username"
        else
            # Create new file
            htpasswd -c "$HTPASSWD_FILE" "$username"
            chmod 640 "$HTPASSWD_FILE"
            chown root:apache "$HTPASSWD_FILE"
        fi
        echo "User '$username' added successfully"
        ;;

    2)
        read -p "Enter username: " username
        if [ ! -f "$HTPASSWD_FILE" ]; then
            echo "Error: Password file does not exist"
            exit 1
        fi
        htpasswd "$HTPASSWD_FILE" "$username"
        echo "Password updated for '$username'"
        ;;

    3)
        read -p "Enter username to delete: " username
        if [ ! -f "$HTPASSWD_FILE" ]; then
            echo "Error: Password file does not exist"
            exit 1
        fi
        htpasswd -D "$HTPASSWD_FILE" "$username"
        echo "User '$username' deleted"
        ;;

    4)
        if [ ! -f "$HTPASSWD_FILE" ]; then
            echo "No users configured yet"
        else
            echo "Configured users:"
            cut -d: -f1 "$HTPASSWD_FILE" | while read user; do
                echo "  - $user"
            done
        fi
        ;;

    5)
        echo "Exiting"
        exit 0
        ;;

    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo
echo "Setup complete!"
echo
echo "To add more users, run this script again or use:"
echo "  htpasswd $HTPASSWD_FILE <username>"
