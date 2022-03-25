ARG VERSION
FROM ghcr.io/oca/oca-ci/py3.6-odoo${VERSION}:latest


COPY tools/requirement.txt /odoo/requirement.txt
RUN pip install -r /odoo/requirement.txt

COPY tools/bin/* /usr/local/bin/
COPY project_api /odoo/addons/project_api
COPY project_api_client /odoo/addons/project_api_client
COPY setup /odoo/addons/setup

ARG VERSION
ARG MODULE
RUN python /usr/local/bin/install-module
ENV MODULE=$MODULE
CMD ["odoo"]
