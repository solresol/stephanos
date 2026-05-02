#!/bin/bash
#
# Deploy the review CGI source to merah and rebuild review.cgi/save.cgi in place.
#

set -euo pipefail

REMOTE_HOST="${1:-stephanos@merah.cassia.ifost.org.au}"
REMOTE_BUILD_DIR="${2:-/home/stephanos/stephanos/review_cgi_build}"
REMOTE_CGI_DIR="${3:-/var/www/vhosts/stephanos.symmachus.org/cgi-bin}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

SOURCE_FILES=(
    "common.go"
    "guidance_common.go"
    "page.go"
    "review.go"
    "entities.go"
    "guidance.go"
    "guidance_status.go"
    "guidance_urgent_common.go"
    "guidance_urgent_worker.go"
    "save.go"
    "status.go"
    "templates.go"
    "shared_helpers.go"
    "go.mod"
    "go.sum"
)

echo "Preparing remote build directory on ${REMOTE_HOST}..."
ssh "$REMOTE_HOST" "mkdir -p '$REMOTE_BUILD_DIR'"

echo "Uploading review CGI sources..."
rsync -az \
    "${SOURCE_FILES[@]/#/${SCRIPT_DIR}/}" \
    "${REMOTE_HOST}:${REMOTE_BUILD_DIR}/"

echo "Building static review CGI binaries on ${REMOTE_HOST}..."
ssh "$REMOTE_HOST" "
    set -euo pipefail
    cd '$REMOTE_BUILD_DIR'
    export CGO_ENABLED=1
    export CC=/usr/bin/cc
    /usr/local/bin/go build -ldflags '-linkmode external -extldflags -static' -o review.cgi review.go common.go guidance_common.go page.go templates.go shared_helpers.go
    /usr/local/bin/go build -ldflags '-linkmode external -extldflags -static' -o entities.cgi entities.go common.go guidance_common.go page.go templates.go shared_helpers.go
    /usr/local/bin/go build -ldflags '-linkmode external -extldflags -static' -o guidance.cgi guidance.go common.go guidance_common.go guidance_urgent_common.go templates.go shared_helpers.go
    /usr/local/bin/go build -ldflags '-linkmode external -extldflags -static' -o guidance_status.cgi guidance_status.go common.go guidance_common.go guidance_urgent_common.go
    /usr/local/bin/go build -ldflags '-linkmode external -extldflags -static' -o guidance_urgent_worker guidance_urgent_worker.go common.go guidance_common.go guidance_urgent_common.go
    /usr/local/bin/go build -ldflags '-linkmode external -extldflags -static' -o save.cgi save.go common.go guidance_common.go guidance_urgent_common.go
    /usr/local/bin/go build -ldflags '-linkmode external -extldflags -static' -o status.cgi status.go common.go
    install -m 755 review.cgi '$REMOTE_CGI_DIR/review.cgi'
    install -m 755 entities.cgi '$REMOTE_CGI_DIR/entities.cgi'
    install -m 755 guidance.cgi '$REMOTE_CGI_DIR/guidance.cgi'
    install -m 755 guidance_status.cgi '$REMOTE_CGI_DIR/guidance_status.cgi'
    install -m 755 guidance_urgent_worker '$REMOTE_CGI_DIR/guidance_urgent_worker'
    install -m 755 save.cgi '$REMOTE_CGI_DIR/save.cgi'
    install -m 755 status.cgi '$REMOTE_CGI_DIR/status.cgi'
"

echo "Review CGI deployed to ${REMOTE_HOST}:${REMOTE_CGI_DIR}"
