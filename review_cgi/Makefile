.PHONY: all clean test

VERSION := $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)
BUILD_TIME := $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
STATUS_LDFLAGS := -X main.buildVersion=$(VERSION) -X main.buildTime=$(BUILD_TIME)

all: review.cgi save.cgi status.cgi

review.cgi: review.go common.go template.go
	go build -o review.cgi review.go common.go template.go

save.cgi: save.go common.go
	go build -o save.cgi save.go common.go

status.cgi: status.go common.go
	go build -ldflags "$(STATUS_LDFLAGS)" -o status.cgi status.go common.go

clean:
	rm -f review.cgi save.cgi status.cgi

test:
	go test -v

# For deployment on merah
deploy: all
	@echo "Built CGI programs. Ready to deploy to merah."
	@echo "Copy review.cgi, save.cgi, and status.cgi to /var/www/vhosts/stephanos.symmachus.org/cgi-bin/"
