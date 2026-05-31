.PHONY: all clean test

COMMON_REVIEW_SRCS = common.go guidance_common.go page.go templates.go shared_helpers.go site_nav.go
GUIDANCE_SRCS = common.go guidance_common.go guidance_urgent_common.go

all: review.cgi entities.cgi guidance.cgi guidance_impacts.cgi final_review.cgi guidance_status.cgi guidance_urgent_worker save.cgi status.cgi canonical_translation.cgi

review.cgi: review.go $(COMMON_REVIEW_SRCS)
	go build -o review.cgi review.go $(COMMON_REVIEW_SRCS)

entities.cgi: entities.go $(COMMON_REVIEW_SRCS)
	go build -o entities.cgi entities.go $(COMMON_REVIEW_SRCS)

guidance.cgi: guidance.go $(GUIDANCE_SRCS) templates.go shared_helpers.go site_nav.go
	go build -o guidance.cgi guidance.go $(GUIDANCE_SRCS) templates.go shared_helpers.go site_nav.go

guidance_impacts.cgi: guidance_impacts.go common.go guidance_common.go shared_helpers.go site_nav.go
	go build -o guidance_impacts.cgi guidance_impacts.go common.go guidance_common.go shared_helpers.go site_nav.go

final_review.cgi: final_review.go common.go guidance_common.go shared_helpers.go site_nav.go
	go build -o final_review.cgi final_review.go common.go guidance_common.go shared_helpers.go site_nav.go

guidance_status.cgi: guidance_status.go $(GUIDANCE_SRCS)
	go build -o guidance_status.cgi guidance_status.go $(GUIDANCE_SRCS)

guidance_urgent_worker: guidance_urgent_worker.go $(GUIDANCE_SRCS)
	go build -o guidance_urgent_worker guidance_urgent_worker.go $(GUIDANCE_SRCS)

save.cgi: save.go $(GUIDANCE_SRCS)
	go build -o save.cgi save.go $(GUIDANCE_SRCS)

status.cgi: status.go common.go guidance_common.go
	@version="${VERSION}"; \
	if [ -z "$$version" ]; then version=$$(git rev-parse --short HEAD 2>/dev/null || echo dev); fi; \
	build_time="${BUILD_TIME}"; \
	if [ -z "$$build_time" ]; then build_time=$$(date -u +%Y-%m-%dT%H:%M:%SZ); fi; \
	go build -ldflags "-X main.buildVersion=$$version -X main.buildTime=$$build_time" -o status.cgi status.go common.go guidance_common.go

canonical_translation.cgi: canonical_translation.go common.go guidance_common.go
	go build -o canonical_translation.cgi canonical_translation.go common.go guidance_common.go

clean:
	rm -f review.cgi entities.cgi guidance.cgi guidance_impacts.cgi final_review.cgi guidance_status.cgi guidance_urgent_worker save.cgi status.cgi canonical_translation.cgi

test:
	cd .. && uv run python -m unittest test_place_cluster_extraction.py test_review_template_split.py

# For deployment on merah
deploy: all
	@echo "Built CGI programs. Ready to deploy to merah."
	@echo "Copy review.cgi, entities.cgi, guidance.cgi, guidance_impacts.cgi, final_review.cgi, guidance_status.cgi, guidance_urgent_worker, save.cgi, status.cgi, and canonical_translation.cgi to /var/www/vhosts/stephanos.symmachus.org/cgi-bin/"
