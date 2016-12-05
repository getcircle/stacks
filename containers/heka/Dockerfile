FROM debian:jessie

COPY heka.deb /tmp/heka.deb
RUN dpkg -i /tmp/heka.deb && rm /tmp/heka.deb

EXPOSE 4352
ENTRYPOINT ["hekad"]
