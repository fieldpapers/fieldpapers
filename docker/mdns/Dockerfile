FROM ubuntu:14.04

ENV DEBIAN_FRONTEND noninteractive

RUN \
  apt-get update && \
  apt-get upgrade -y && \
  apt-get clean

RUN \
  apt-get -y install avahi-daemon && \
  apt-get clean

RUN \
  sed -i -e 's/#enable-dbus=yes/enable-dbus=no/' /etc/avahi/avahi-daemon.conf && \
  sed -i -e 's/rlimit-nproc=3//' /etc/avahi/avahi-daemon.conf

CMD \
  sed -i -e 's/#?host-name=.*/host-name=${HOSTNAME}/' /etc/avahi/avahi-daemon.conf && \
  (/usr/sbin/avahi-daemon -k; /usr/sbin/avahi-daemon)
