ARG VERSION
FROM quay.io/acsone/odoo-bedrock:${VERSION}-py36-latest as dist
ARG VERSION

RUN set -e \
  && apt update \
  && apt -y install wget unzip postgresql-client git

COPY .build/download-odoo /odoo/bin/download-odoo
RUN /odoo/bin/download-odoo
RUN pip install -r /odoo/src/requirements.txt -f https://wheelhouse.acsone.eu/manylinux2014
RUN pip install -e /odoo/src
COPY . /odoo/addons
COPY .build/requirement.txt /odoo/requirement.txt
RUN pip install -r /odoo/requirement.txt

ARG MODULE
COPY .build/install-module /odoo/bin/install-module
COPY .build/install-module-stable /odoo/bin/install-module-stable
RUN python /odoo/bin/install-module
COPY .build/start-entrypoint.d/* /odoo/start-entrypoint.d/
ENV MODULE=$MODULE
