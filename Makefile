
.PHONY: local-dev
local-dev:
	cp .env.sample .env
	echo "\nDEPLOYMENTS_MOUNT_DIR='$(PWD)/deployments' # DO NOT EDIT THIS - FIX FOR RESOURCE SHARING BUG" >> .env
	echo "\nNGINX_PROXY_CONF_LOCATION='$(PWD)/nginx-confs' # DO NOT EDIT THIS - FIX FOR RESOURCE SHARING BUG" >> .env
	echo "\nDEPLOYMENT_HOST='localhost' # DO NOT EDIT THIS" >> .env
	bash setup-vault.sh docker-compose-local.yml
	echo "\nVAULT_BASE_URL='http://localhost:8200'" >> .env
	mkdir -p deployments nginx-confs
	docker-compose -f docker-compose-local.yml up -d nginx

.PHONY: sarthi
sarthi:
	python app.py

.PHONY: test
test:
	python -m pytest -vvv tests

.PHONY: reset
reset:
	rm -f .env keys.txt parsed-key.txt ansi-keys.txt
	docker compose -f docker-compose-local.yml down -v
	rm -rf deployments nginx-confs
