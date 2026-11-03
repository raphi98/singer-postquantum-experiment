# Basis-Image per Digest und apt-Quellen per Snapshot fixiert: Der Build liefert auch
# später exakt dieselben Paketversionen. macOS und Windows bringen kein passendes OpenSSL mit.
FROM debian:13-slim@sha256:f6b08b09a05725f9431502d3b5714f5c4576e82c1a84fa1debe0c24a7e0c3ec4

ARG SNAPSHOT=20261029T000000Z

RUN rm -f /etc/apt/sources.list.d/* \
    && echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/${SNAPSHOT} trixie main" > /etc/apt/sources.list \
    && echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/${SNAPSHOT} trixie-security main" >> /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends openssl ca-certificates python3 bind9-dnsutils \
    && rm -rf /var/lib/apt/lists/*
