.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=========================
Project API client
=========================

This module adds a new menu entry "support" to allow you to interact with your integrator


Configuration
=============

- According settings done in project_api in the other instance, add your account in Configuration > Technical > Parameters > Support Accounts
- Apply to choosen users the Support group : `Support User` or `Support Manager`
  

Usage
=====

Refresh web page and click on Support menu


Testing Tips
=============

For running the test as the module project_api and project_api_client
interact together. A mock have been design based on request-mock and
a json file

If you run the test in "learning mode"

LEARN=True odoo -u project_api_client,project_api --test-enable --stop-after-init

Odoo will update the data.json file automatically

Then you can run it in real testing mode by removing the LEARN=True var

Contributors
------------

* Sébastien BEAU <sebastien.beau@akretion.com>
* Benoit Guillot <benoit.guillot@akretion.com>
