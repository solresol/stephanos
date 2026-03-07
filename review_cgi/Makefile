.PHONY: all clean test

all: review.cgi save.cgi status.cgi

review.cgi: review.go common.go template.go
	go build -o review.cgi review.go common.go template.go

save.cgi: save.go common.go
	go build -o save.cgi save.go common.go

status.cgi: status.go common.go
	@version="${VERSION}"; \
	if [ -z "$$version" ]; then version=$$(git rev-parse --short HEAD 2>/dev/null || echo dev); fi; \
	build_time="${BUILD_TIME}"; \
	if [ -z "$$build_time" ]; then build_time=$$(date -u +%Y-%m-%dT%H:%M:%SZ); fi; \
	go build -ldflags "-X main.buildVersion=$$version -X main.buildTime=$$build_time" -o status.cgi status.go common.go

clean:
	rm -f review.cgi save.cgi status.cgi

test:
	go test -v

# For deployment on merah
deploy: all
	@echo "Built CGI programs. Ready to deploy to merah."
	@echo "Copy review.cgi, save.cgi, and status.cgi to /var/www/vhosts/stephanos.symmachus.org/cgi-bin/"
