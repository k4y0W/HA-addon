ARG BUILD_FROM
FROM $BUILD_FROM

# Instalujemy pakiety BEZ numerów wersji - system sam dobierze pasujące
RUN apk add --no-cache \
    python3 \
    nano \
    coreutils \
    wget

# Kopiujemy Twój skrypt
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]