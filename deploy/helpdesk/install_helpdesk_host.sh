#!/usr/bin/env bash
# Bootstrap the dedicated Helpdesk host resources. Run as root only.
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
env_file="/etc/helpdesk/helpdesk.env"

if [[ ! -f "${env_file}" ]]; then
  echo "Missing ${env_file}. Install the reviewed root-only environment first." >&2
  exit 1
fi

if ! getent group helpdesk >/dev/null; then
  groupadd --system helpdesk
fi
if ! id -u helpdesk >/dev/null 2>&1; then
  useradd --system --gid helpdesk --home-dir /var/lib/helpdesk --shell /usr/sbin/nologin helpdesk
fi

install -d -o root -g root -m 0755 /opt/helpdesk /opt/helpdesk/releases /etc/helpdesk
install -d -o helpdesk -g helpdesk -m 0750 /var/lib/helpdesk
chown root:root "${env_file}"
chmod 0600 "${env_file}"

install -o root -g root -m 0644 "${script_dir}/helpdesk-server.service" /etc/systemd/system/helpdesk-server.service
install -o root -g root -m 0644 "${script_dir}/helpdesk-control.service" /etc/systemd/system/helpdesk-control.service
install -o root -g root -m 0644 "${script_dir}/helpdesk-migrate.service" /etc/systemd/system/helpdesk-migrate.service

install -d -o root -g root -m 0755 /etc/nginx/sites-available /etc/nginx/sites-enabled
install -o root -g root -m 0644 "${script_dir}/helpdesk.nginx.conf" /etc/nginx/sites-available/helpdesk
ln -sfn /etc/nginx/sites-available/helpdesk /etc/nginx/sites-enabled/helpdesk

systemctl daemon-reload
systemctl enable helpdesk-server.service helpdesk-control.service
nginx -t
systemctl reload nginx

echo "Helpdesk host resources are installed. Deploy a committed release with scripts/deploy_helpdesk_release.py."
