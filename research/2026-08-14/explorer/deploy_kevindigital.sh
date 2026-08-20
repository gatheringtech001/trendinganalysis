#!/usr/bin/env bash
set -eu

if [ "$#" -ne 2 ] && [ "$#" -ne 4 ]; then
  echo "usage: deploy_kevindigital.sh <archive-url-hex> <archive-sha256> [<env-url-hex> <env-sha256>]" >&2
  exit 2
fi

blob_url="$(python3 -c 'import sys; print(bytes.fromhex(sys.argv[1]).decode())' "$1")"
expected_sha256="$2"
base_dir="/home/regardsadmin/projects/fashion-scope"
runtime_dir="/var/lib/fashion-scope/detailed_visual_jobs"
report_runtime_dir="/var/lib/fashion-scope/reports"
release_id="$(date -u +%Y%m%dT%H%M%SZ)"
release_dir="$base_dir/releases/$release_id"
archive_path="/tmp/fashion-scope-$release_id.zip"
env_path="/tmp/fashion-scope-$release_id.env"
nginx_file="/etc/nginx/sites-enabled/career"
nginx_backup="$nginx_file.bak-fashion-scope-$release_id"

curl --fail --silent --show-error --location "$blob_url" --output "$archive_path"
actual_sha256="$(sha256sum "$archive_path" | awk '{print $1}')"
if [ "$actual_sha256" != "$expected_sha256" ]; then
  rm -f "$archive_path"
  echo "archive SHA-256 mismatch" >&2
  exit 1
fi
if [ "$#" -eq 4 ]; then
  env_blob_url="$(python3 -c 'import sys; print(bytes.fromhex(sys.argv[1]).decode())' "$3")"
  expected_env_sha256="$4"
  curl --fail --silent --show-error --location "$env_blob_url" --output "$env_path"
  actual_env_sha256="$(sha256sum "$env_path" | awk '{print $1}')"
  if [ "$actual_env_sha256" != "$expected_env_sha256" ]; then
    rm -f "$archive_path" "$env_path"
    echo "environment SHA-256 mismatch" >&2
    exit 1
  fi
  sudo install -o root -g root -m 0600 "$env_path" /etc/fashion-scope.env
  rm -f "$env_path"
fi
sudo install -d -o regardsadmin -g regardsadmin "$base_dir/releases" "$release_dir"
sudo -u regardsadmin python3 -m zipfile -e "$archive_path" "$release_dir"
rm -f "$archive_path"

test -f "$release_dir/server.py"
test -f "$release_dir/report_pdf.py"
test -f "$release_dir/explorer.db"
test -f "$release_dir/dist/index.html"
test -f "$release_dir/data/image_analysis_tops_cover_aloruh_shein.jsonl"
test -f "$release_dir/data/image_analysis_skirts_cover_aloruh_shein.jsonl"
test -f "$release_dir/analysis_scripts/analyze_dimension_selection.py"
test -f "$release_dir/requirements-production.txt"
sudo test -s /etc/fashion-scope.env
sudo -u regardsadmin python3 -m venv "$release_dir/.venv"
sudo -u regardsadmin "$release_dir/.venv/bin/pip" install \
  --disable-pip-version-check --no-cache-dir --only-binary=:all: \
  -r "$release_dir/requirements-production.txt"
sudo -u regardsadmin "$release_dir/.venv/bin/python" -c 'import PIL'
sudo install -d -o regardsadmin -g regardsadmin -m 0750 "$runtime_dir"
sudo install -d -o regardsadmin -g regardsadmin -m 0750 "$report_runtime_dir"
if [ -d "$release_dir/report_pdf" ] && [ ! -f "$report_runtime_dir/Aloruh纯视觉诊断-图片结论版.pdf" ]; then
  sudo -u regardsadmin cp -a "$release_dir/report_pdf/." "$report_runtime_dir/"
fi
ln -sfn "$release_dir" "$base_dir/current"

sudo install -m 0644 /dev/stdin /etc/systemd/system/fashion-scope.service <<'EOF'
[Unit]
Description=Fashion Scope research explorer
After=network.target

[Service]
Type=simple
User=regardsadmin
Group=regardsadmin
WorkingDirectory=/home/regardsadmin/projects/fashion-scope/current
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=FASHION_SCOPE_DATA_DIR=/home/regardsadmin/projects/fashion-scope/current/data
Environment=FASHION_SCOPE_ANALYSIS_SCRIPTS=/home/regardsadmin/projects/fashion-scope/current/analysis_scripts
Environment=FASHION_SCOPE_DETAILED_OUTPUT_DIR=/var/lib/fashion-scope/detailed_visual_jobs
Environment=FASHION_SCOPE_DETAILED_HISTORY_ROOT=/home/regardsadmin/projects/fashion-scope/current/detailed_history
Environment=FASHION_SCOPE_REPORT_PDF_DIR=/var/lib/fashion-scope/reports
EnvironmentFile=/etc/fashion-scope.env
ExecStart=/home/regardsadmin/projects/fashion-scope/current/.venv/bin/python server.py --host 127.0.0.1 --port 8603
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=/var/lib/fashion-scope/detailed_visual_jobs /var/lib/fashion-scope/reports

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable fashion-scope.service
sudo systemctl restart fashion-scope.service
for attempt in 1 2 3 4 5; do
  if curl --fail --silent http://127.0.0.1:8603/healthz >/dev/null; then
    break
  fi
  if [ "$attempt" -eq 5 ]; then
    sudo systemctl status fashion-scope.service --no-pager
    exit 1
  fi
  sleep 2
done

if ! sudo grep -q 'location /fashion-scope/' "$nginx_file"; then
  sudo cp "$nginx_file" "$nginx_backup"
  sudo sed -i '/^[[:space:]]*location \/cost\/ {/i\
    location = /fashion-scope {\
        return 301 /fashion-scope/;\
    }\
\
    location /fashion-scope/ {\
        proxy_pass http://127.0.0.1:8603/;\
        proxy_http_version 1.1;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_set_header X-Forwarded-Proto https;\
        proxy_set_header X-Forwarded-Prefix /fashion-scope;\
    }\
' "$nginx_file"
  if ! sudo nginx -t; then
    sudo cp "$nginx_backup" "$nginx_file"
    sudo nginx -t
    exit 1
  fi
  sudo systemctl reload nginx
fi

echo "release=$release_dir"
echo "service=$(sudo systemctl is-active fashion-scope.service)"
echo "health=$(curl --fail --silent http://127.0.0.1:8603/healthz)"
