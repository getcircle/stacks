FROM ubuntu:14.04

RUN apt-get update && apt-get install -y ca-certificates

COPY vault /usr/local/bin/vault
COPY config.hcl /opt/vault/config.hcl
EXPOSE 8200
ENTRYPOINT ["/usr/local/bin/vault", "server", "-config=/opt/vault/config.hcl"]
