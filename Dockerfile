FROM quay.io/fedora/fedora:37

ENV NAME=betka-fedora \
    RELEASE=3 \
    ARCH=x86_64 \
    SUMMARY="Syncs changes from upstream repository to downstream" \
    DESCRIPTION="Syncs changes from upstream repository to downstream" \
    HOME="/home/betka" \
    SITE_PACKAGES=/usr/local/lib/python3.10/site-packages/betka

LABEL summary="$SUMMARY" \
      description="$DESCRIPTION" \
      io.k8s.description="$SUMMARY" \
      io.k8s.display-name="$NAME" \
      com.redhat.component="$NAME" \
      name="quay.io/rhscl/betka" \
      release="$RELEASE.$DISTTAG" \
      architecture="$ARCH" \
      usage="docker run -e REPO_URL=<url> quay.io/rhscl/betka" \
      maintainer="Petr Hracek <phracek@redhat.com>"


ENV LANG=en_US.UTF-8

RUN mkdir --mode=775 /var/log/bots

COPY requirements.sh requirements.txt /tmp/betka-bot/

RUN cd /tmp/betka-bot && bash requirements.sh

RUN cd /tmp/betka-bot && pip3 install -r requirements.txt

WORKDIR ${HOME}

COPY ./files/bin /bin
COPY ./files/home ${HOME}/
COPY ./config.json ${HOME}/

# Install betka
COPY ./ /tmp/betka-bot

RUN cd /tmp/betka-bot && pip3 install .

USER 1000

CMD ["/bin/run.sh"]
