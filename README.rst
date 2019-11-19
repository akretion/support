Support Project
================

These modules are used and developped by Akretion to support our customers.

Basically we have 2 modules:

* project_api that exposes an API in our ERP and adds some extra features
* project_api_client that is installed in our customer ERP's and interact with our ERP through the API

TODO
======

Move to OCA


Simplify test:

Test are a little complexe. For now you have to

- run the test in "learning" mode for project_api_client then project_api this will generate json file base on automatic mocked call
- then you can run the test normally

This is not really easy to debug, but it's the simpliets solution found for now

If we have a better idea it will be great to propose it.
