Support Project
================

These modules are used and developped by Akretion to support our customers.

Basically we have 2 modules:

* project_api that exposes an API in our ERP and adds some extra features
* project_api_client that is installed in our customer ERP's and interact with our ERP through the API

TODO
======

Move to OCA


HOW TO TEST AND DEVELOP
======================

* clone the repository and choose your branch
* In tools directory create a .env file with the following : 
  COMPOSE_FILE=docker-compose.yml:dev.docker-compose.yml
  SERVER_VERSION=branch version (ex : 14.0)
  CLIENT_VERSION=branch version (ex : 14.0)
* run the script build
* run the script start_server and the script start_client
* Lauch both odoo server and odoo client and start to develop and test


If you want to test a server and client from 2 different version, you can clone the repository twice.
Do the same steps as described before and launch only the script start_server or start_client depending of the version you want.
