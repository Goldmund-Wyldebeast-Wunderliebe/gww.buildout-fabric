Buildout fabric tools
=====================

This module contains a Fabric script with several functions for releasing and
deploying Plone buildouts.

Include this fabric config in an existing buildout
--------------------------------------------------

Note: this is already done in `gww.buildout`_

Add this repository as a git submodule:

    cd {buildout-dir}
    git submodule add -f  https://github.com/Goldmund-Wyldebeast-Wunderliebe/gww.buildout-fabric.git fabric_lib

Copy fabfile.py and deployment.py from `gww.buildout`_ to the existing
buildout.

.. _`gww.buildout`: https://github.com/Goldmund-Wyldebeast-Wunderliebe/gww.buildout

Bootstrapping Fabric
--------------------

Fabric is included in the buildout::

    ./bin/fab --version
    Fabric 1.8.3
    Paramiko 1.12.3

Modify the fabfile.py in the buildout and adjust the settings::

    vim {buildout-dir}/deployment.py

Add your SSH public key to the remote appie user, see paragraph 'Preparing
Appie environments'  below.


Fabric layered tasks
------------------------
Shortcuts for running one or more tasks on a specific buildout environment. 

Usage: fab  <task name>:<parameters>

The layered tasks will accept an *env* and *server* parameter to specify 
a specific envirnment. The *env* parameter accepts tst, acc and prd, *server* 
accepts master or slave.

Examples
^^^^^^^^

Test connection to the default environment::

    fab test

Copy database from master server on the production environment::

    # fab copy:env=prd,server=master

Deploy a new buildout for the slave server on the production environment::

    # fab deploy:env=prd,server=slave


Layered parameters
^^^^^^^^^^^^^^^^^^

layer
    This parameter defines which environment should be used for executing
    the task. Most used environment layers: ``acc``, ``tst`` and ``prd``.

server
    Used when a cluster setup is used, use this parameter to select a
    ``master`` or ``slave`` from the cluster. When this parameter is omitted
    all servers in cluster are used.



Tasks
^^^^^
The following tasks can be used:

check_cluster
    Check the servers in the clusters, shown information about DRBD and the
    current master and slave server.

copy
    Copy the ZODB database to loca buildout

deploy
    Create a new buildout or update an existing buildout. On tst and acc the
    switch command is automatically done, on prd a manual switch is required.

hatop
    Start and show hatop on the remote server

make_tag
    Git tag all modules in buildout

shell
    Start a shell to the remote server

switch
    Switch supervisor in current buildout dir to latest buildout

test
    Test the connection to the remote server, showing the output of hostname,
    whoami and pwd commands.


Preparing Appie environments
------------------------------------

All Plone portals are contained in Appie environments. Appie users are
'locked' accounts by default. If a user is locked two exclamation marks can
be seen in /etc/shadow

This user is locked:

    # sudo cat /etc/shadow | grep app-example-acc

    app-example-acc:!!:15558:0:99999:7:::

Unlock the user:

    # sudo passwd -u app-example-acc

Now we need to add your SSH public key to the authorized keys of the appie
user. If no .ssh directory of authorized_keys file is present create the ssh
dir structure by hand. Please keep in mind file permissions on ssh dir/files
must not be world/group readable and writeable.

    # appie become example acc

    # vi .ssh/authorized_keys  # Add your public key

Now check if you connect via SSH:

    # ssh app-example-acc@plone-acc

If the SSH connection is working, Fabric is also working. Use the following
command to double check:

    # fab -H example-acc -u app-example-acc test_connection

