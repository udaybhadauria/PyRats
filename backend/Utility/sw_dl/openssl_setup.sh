#!/bin/bash
set -e

# Ensure non-interactive mode
export DEBIAN_FRONTEND=noninteractive

# Install required packages (no prompts)
sudo apt-get update -y
sudo apt install -y gnutls-bin
sudo apt-get install -y build-essential libp11-kit-dev libtasn1-6-dev nettle-dev
sudo apt-get install -y libssl-dev

# Define the file path
config_file="/etc/apache2/sites-available/default-ssl.conf"

# Update Apache SSL configuration
sudo sed -i 's|DocumentRoot /var/www/html|DocumentRoot /home/rats/RATS/Frontend|' "$config_file"
sudo sed -i 's|SSLCertificateFile      /etc/ssl/certs/ssl-cert-snakeoil.pem|SSLCertificateFile      /home/rats/RATS/ssl/newcert.pem|' "$config_file"
sudo sed -i 's|SSLCertificateKeyFile   /etc/ssl/private/ssl-cert-snakeoil.key|SSLCertificateKeyFile /home/rats/RATS/ssl/newkey.pem|' "$config_file"

# Enable SSL and site
sudo a2enmod ssl
sudo a2ensite default-ssl

# Restart Apache to apply the changes
sudo systemctl restart apache2

echo "SSLCertificateFile path updated and Apache restarted."
