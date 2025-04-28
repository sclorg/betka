.PHONY: prepare build build_generator build_test run run_generator test test_in_container clean send_master_sync send_pr_sync image_push deploy

IMAGE_NAME = quay.io/rhscl/betka
TEST_IMAGE_NAME = betka-test
DEPLOY_NAME = quay.io/rhscl/betka-deployment
UNAME=$(shell uname)
ifeq ($(UNAME),Darwin)
	PODMAN := /opt/podman/bin/podman #docker
else
	PODMAN := /usr/bin/podman
endif

# https://blog.153.io/2016/04/18/source-a-shell-script-in-make
-include secrets.mk
secrets.mk: secrets.env
	sed 's/"//g ; s/=/:=/' < $< > $@

prepare:
	mkdir -m 777 -p logs
	mkdir -m 777 -p betka-generator/results

build:
	$(PODMAN) build --tag ${IMAGE_NAME} -f Dockerfile .

build_generator:
	docker-compose build generator

build_test: build
	$(PODMAN) build --tag ${TEST_IMAGE_NAME} -f Dockerfile.tests .

run: prepare build
	docker-compose --verbose up betka redis

run_betka: prepare build
	./run-podman.sh

run_generator: prepare build_generator
	docker-compose up generator

test:
	cd tests && PYTHONPATH=$(CURDIR) pytest --color=yes --verbose --showlocals

test_in_container: build_test
	$(PODMAN) run --rm --net=host -e DEPLOYMENT=test ${TEST_IMAGE_NAME}

image_push: build
	$(PODMAN) push ${IMAGE_NAME}

send_master_sync:
	podman exec betka python3 /tmp/betka-bot/upstream_master_sync.py
	#docker-compose exec betka python3 /tmp/betka-bot/upstream_master_sync.py

clean:
	find . -name '*.pyc' -delete

stop:
	docker-compose down

stop_podman:
	podman stop redis && podman rm redis
	podman stop betka && podman rm betka

image_deploy:
	$(PODMAN) build --tag=${DEPLOY_NAME} -f Dockerfile.deployment .

deploy: image_deploy
	./openshift/run-deployment-in-container.sh
