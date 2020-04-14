FROM docker.io/usercont/frambo

ENV NAME=betka \
    RELEASE=1 \
    ARCH=x86_64 \
    SUMMARY="Syncs changes from upstream repository to downstream" \
    DESCRIPTION="Syncs changes from upstream repository to downstream" \
    HOME="/home/betka" \
    SITE_PACKAGES=/usr/local/lib/python3.7/site-packages/frambo

LABEL summary="$SUMMARY" \
      description="$DESCRIPTION" \
      io.k8s.description="$SUMMARY" \
      io.k8s.display-name="$NAME" \
      com.redhat.component="$NAME" \
      name="$FGC/$NAME" \
      release="$RELEASE.$DISTTAG" \
      architecture="$ARCH" \
      usage="docker run -e REPO_URL=<url> $FGC/$NAME" \
      maintainer="Petr Hracek <phracek@redhat.com>"

RUN dnf install -y --setopt=tsflags=nodocs distgen nss_wrapper krb5-devel krb5-workstation origin-clients openssh-clients \
    && mkdir --mode=775 /tmp/betka-generator \
    && mkdir -p ${HOME}/config \
    && useradd -u 1000 -r -g 0 -d ${HOME} -s /bin/bash -c "Default Application User" ${NAME} \
    && chown -R 1000:0 ${HOME} \
    && chmod -R g+rwx ${HOME} \
    && dnf clean all

COPY ./requirements.txt /tmp/betka-bot/
RUN cd /tmp/betka-bot && pip3 install -r requirements.txt

WORKDIR ${HOME}

COPY ./files/bin /bin
COPY ./files/home ${HOME}/
COPY ./pagure.conf /etc/rpkg/fedpkg.conf

# Install betka
COPY ./ /tmp/betka-bot

RUN rm -f ${SITE_PACKAGES}/data/conf.d/config.yml
COPY ./files/data/conf.d/config.yml ${SITE_PACKAGES}/data/conf.d/config.yml

RUN cd /tmp/betka-bot && pip3 install .

USER 1000

CMD ["/bin/run.sh"]
