#!/bin/sh
# Erzeugt eine Testkette nach dem Vorbild von letsencrypt.org (Stand 30.10.2026: 4 Zertifikate,
# 3576 Byte DER, Leaf ECDSA P-256). Nur für das Labor!
#
#   Lab Root X1 (RSA-4096, Vertrauensanker beim Client, wird nicht ausgeliefert)
#     -> Lab Root X2 (P-384) -> Lab Root YE (P-384) -> Lab YE2 (P-384) -> lab-server (P-256)
#
# Die Kettengröße bestimmt, wie viele Pakete der Server-Flight braucht, und damit die
# Angriffsfläche für Paketverlust. Die Dateien liegen im Repo, damit die Größen zwischen
# Wiederholungen exakt gleich bleiben.
#
# Aufruf: docker run --rm --network none -w /certs-rw -v "$PWD/lab/certs:/certs-rw" \
#           pqtls-lab/client sh gen_certs.sh
set -eu

# Unbekannte Extension als Platzhalter für die SCT-Liste echter Zertifikate (ca. 450 Byte, damit das Leaf die Größe des Vorbilds erreicht).
SCT_FILLER=$(head -c 450 /dev/zero | od -v -An -tx1 | tr -d ' \n')

ca_extensions() {
    cat <<EOF
basicConstraints=critical,CA:TRUE
keyUsage=critical,keyCertSign,cRLSign
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid
authorityInfoAccess=caIssuers;URI:http://$1.i.lab.example/
crlDistributionPoints=URI:http://$1.c.lab.example/
certificatePolicies=2.23.140.1.2.1
EOF
}

leaf_extensions() {
    cat <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=serverAuth
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid
authorityInfoAccess=caIssuers;URI:http://ye2.i.lab.example/
crlDistributionPoints=URI:http://ye2.c.lab.example/
certificatePolicies=2.23.140.1.2.1
subjectAltName=DNS:lab-server
1.3.6.1.4.1.55555.1=DER:$SCT_FILLER
EOF
}

# issue <name> <subject> <kurve> <aussteller> <extension-datei>
issue() {
    openssl ecparam -name "$3" -genkey -noout -out "$1.key"
    openssl req -new -key "$1.key" -subj "$2" -out "$1.csr"
    openssl x509 -req -in "$1.csr" -CA "$4.pem" -CAkey "$4.key" -CAcreateserial \
        -sha256 -days 3650 -out "$1.pem" -extfile "$5"
}

openssl req -x509 -newkey rsa:4096 -nodes -keyout root.key -sha256 -days 3650 \
    -subj "/C=AT/O=PQ-TLS Lab Internet Security Research/CN=Lab Root X1" -out root.pem

ca_extensions x1 > ext.tmp
issue x2 "/C=AT/O=PQ-TLS Lab Internet Security Research/CN=Lab Root X2" secp384r1 root ext.tmp
ca_extensions x2 > ext.tmp
issue ye "/C=AT/O=PQ-TLS Lab/CN=Lab Root YE" secp384r1 x2 ext.tmp
ca_extensions ye > ext.tmp
issue ye2 "/C=AT/O=PQ-TLS Lab/CN=Lab YE2" secp384r1 ye ext.tmp
leaf_extensions > ext.tmp
issue leaf "/CN=lab-server" prime256v1 ye2 ext.tmp

cat leaf.pem ye2.pem ye.pem x2.pem > chain.pem
rm -f ./*.csr ./*.srl ext.tmp root.key x2.key ye.key ye2.key x2.pem ye.pem ye2.pem
chmod 644 leaf.key
