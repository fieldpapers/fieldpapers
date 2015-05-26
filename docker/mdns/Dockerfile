FROM ubuntu:14.04

ENV DEBIAN_FRONTEND noninteractive

RUN \
  apt-get update && \
  apt-get upgrade -y && \
  apt-get clean

RUN \
  apt-get -y install avahi-daemon && \
  apt-get clean

ADD avahi-daemon.conf /etc/avahi/avahi-daemon.conf

CMD /usr/sbin/avahi-daemon
