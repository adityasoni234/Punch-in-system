#!/usr/bin/env bash
#
# Generates a self-signed certificate for local HTTPS development.
#
# Why this exists: browsers only expose navigator.geolocation on a secure
# context. http://localhost counts as secure, but http://192.168.x.x -- the
# address a phone on the same Wi-Fi has to use -- does not. Without HTTPS the
# phone can never punch, no matter what its Location Services say.
#
# The certificate covers localhost and this machine's current LAN address.
# Re-run it if your LAN IP changes.
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p certs

LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
if [ -z "${LAN_IP}" ]; then
  LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
fi
if [ -z "${LAN_IP}" ]; then
  echo "Could not determine this machine's LAN IP address." >&2
  echo "Pass it explicitly:  LAN_IP=192.168.1.23 $0" >&2
  exit 1
fi

echo "Issuing a development certificate for localhost and ${LAN_IP}"

cat > certs/openssl.cnf <<CONF
[req]
distinguished_name = dn
x509_extensions    = ext
prompt             = no

[dn]
CN = Punch In development

[ext]
subjectAltName   = DNS:localhost, IP:127.0.0.1, IP:${LAN_IP}
basicConstraints = critical, CA:TRUE
keyUsage         = digitalSignature, keyEncipherment, keyCertSign
extendedKeyUsage = serverAuth
CONF

openssl req -x509 -nodes -newkey rsa:2048 -sha256 -days 825 \
  -keyout certs/dev-key.pem \
  -out certs/dev-cert.pem \
  -config certs/openssl.cnf >/dev/null 2>&1

chmod 600 certs/dev-key.pem
rm -f certs/openssl.cnf

cat <<MSG

Certificate written to frontend/certs/
  dev-cert.pem   (public — this is the one to install on the phone)
  dev-key.pem    (private — never commit or share)

Next:
  1. npm run dev:https
  2. On the phone open  https://${LAN_IP}:5173

iPhone: Safari will warn that the certificate is not trusted. To clear the
warning permanently, AirDrop or email dev-cert.pem to the phone, then:
  Settings -> General -> VPN & Device Management -> install the profile
  Settings -> General -> About -> Certificate Trust Settings -> switch it on

Android/Chrome: tap "Advanced" -> "Proceed", or install the certificate under
Settings -> Security -> Encryption & credentials -> Install a certificate.
MSG
