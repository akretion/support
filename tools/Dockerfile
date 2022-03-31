ARG VERSION
ARG PYTHON_VERSION
FROM ghcr.io/oca/oca-ci/py${PYTHON_VERSION}-odoo${VERSION}:latest

ARG LOCAL_UID
RUN useradd --shell /bin/bash -u ${LOCAL_UID} -o -c "" -m odoo

COPY tools/requirement.txt /odoo/requirement.txt
RUN pip install -r /odoo/requirement.txt

COPY tools/bin/* /usr/local/bin/
COPY project_api /odoo/addons/project_api
COPY project_api_client /odoo/addons/project_api_client
COPY test-requirements.txt /odoo/addons/test-requirements.txt
COPY setup /odoo/addons/setup

ARG VERSION
ARG MODULE
RUN python /usr/local/bin/install-module
ENV MODULE=$MODULE
CMD ["odoo"]
