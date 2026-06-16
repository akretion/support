.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=========================
Project Customer Access
=========================

Project menu and views for customers accessing your own ERP.
Module based on :
- `cross_connect_server <https://github.com/OCA/server-auth/pull/734>`_ to make the connection between the two ERP
- `base_group_backend <https://github.com/OCA/server-backend/tree/16.0/base_group_backend>`_ to give restricted backend access to the customer.


Configuration
=============

The customer's user needs to be part of one of the security groups "Project Access Customer" to access its Tasks with restricted access.

As these groups are based on "User types / Backend UI user", the only way to add the user to these groups through the UI will be through the group's form view itself, changing the "Users" tab.


Usage
=====

#. Create a user with the security group "Project Access Customer / User" or "Manager"
#. Relate the user and the projects he needs to access to the same "Cross Connect Client"
#. Connect as the customer's and go to its "Project" menu


Contributors
------------

* Clément Mombereau <clement.mombereau@akretion.com>
