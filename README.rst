HOW TO TEST IT LOCALLY !
=========================

First install docker-compose

Then build docker image with

.. code-block:: bash

  tools/build


Then init server and client database

.. code-block:: bash

  tools/start-server init-db
  tools/start-client init-db


Start manually and hack it

.. code-block:: bash

  tools/start-client

