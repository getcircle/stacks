SHELL=/bin/bash

docker-machine-init:
	eval "$(docker-machine env default)"

heka-build: docker-machine-init
	./containers/heka/setup
	docker build -t lunohq/heka containers/heka

heka-push: heka-build
	docker push lunohq/heka

vault-build: docker-machine-init
	./containers/vault/setup
	docker build -t lunohq/vault containers/vault

vault-push: vault-build
	docker push lunohq/vault

build-prod:
	stacker build -r us-east-1 conf/lunohq/production.env conf/lunohq/config.yml --tail

outputs-prod:
	stacker info -r us-east-1 conf/lunohq/production.env conf/lunohq/config.yml

build-staging:
	stacker build -r us-east-1 conf/lunohq/staging.env conf/lunohq/config.yml --tail

outputs-staging:
	stacker info -r us-east-1 conf/lunohq/staging.env conf/lunohq/config.yml

build:
	stacker build -r us-west-2 conf/lunohq/dev.env conf/lunohq/config.yml --tail

outputs:
	stacker info -r us-west-2 conf/lunohq/dev.env conf/lunohq/config.yml

seal:
	tar cvf ssl.tar.gz ssl
	keybase encrypt mhahn ssl.tar.gz
	rm -rf ssl
	rm ssl.tar.gz

unseal:
	keybase decrypt ssl.tar.gz.asc -o ssl.tar.gz
	tar xzvf ssl.tar.gz
