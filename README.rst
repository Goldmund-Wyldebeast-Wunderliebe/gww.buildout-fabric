Buildout fabric tools
=====================

This module contains a Fabric script with several functions for releasing and
deploying to Plone buildouts.

Include this fabric config in an existing buildout
--------------------------------------------------

Note: this is already done in the recent buildout-templates.

Add this repository as a git submodule:

    cd {buildout-dir}
    git submodule add -f  git@git.gw20e.com:gww/fabric-buildout.git fabric_lib

Finally go to https://git.gw20e.com/tools/buildout-template/blob/master/fabfile.py
and download this file and place in in your buildout. 

Bootstrapping Fabric
--------------------

Fabric is included in the buildout:

    # ./bin/fab --version
    Fabric 1.8.3
    Paramiko 1.12.3

Modify the fabfile.py in the buildout and adjust the settings:

    # vim {buildout-dir}/fabfile.py

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
~~~~~~~~

Run test function on acceptance

    # fab test:env=acc

Copy database from master server on the production environment:

    # fab copy:env=prd,server=master

Deploy a new buildout for the slave server on the production environment:

    # fab deploy:env=prd,server=slave

Commands
~~~~~~~~

test
    Test the connection with acceptance environment

update
    Update acceptance environment using *pull_modules* and
    *restart_instances* tasks.

deploy
    This script handles the steps (1) which are executed on the production Appie's
    to deploy a new buildout. A fresh buildout is cloned and run. Switching can 
    be done in the next task.

switch
    The current buildout will be switched with the new one. Instances are restarted 
    and finally a switch is made between the old buildout and the  new one.

copy
    Copies the Data.fs and blobstorage to the local buildout. 


Fabric basic tasks
------------------
Preferably use the layered tasks. These are easier to use, you have to type less
to specify a specfic environment. The basic tasks are used under water by the 
layered ones.

Usage: fab <task name>

Examples
~~~~~~~~

Restart connection on nuffic-acc:
    # fab -H nuffic-acc -u app-nuffic-acc restart_instances

Prepare production release locally:
    # fab -H prepare_release:nuffic

Commands
~~~~~~~~

test_connection
    Runs a few harmless commands on the remote server to check the connection

pull_modules
    Used on acceptance to pull Git development modules.

restart_instances
    Restarts all instances in the remote buildout. After restarting an instance
    the script waits until the instance is up, it then continues restarting
    other instances.

prepare_release
    Adds production git tag to active Python modules, and configures prd-sources
    with same git tag.

    This is a local task, no remote host or user is needed!

deploy_buildout
    This script handles the steps (1) which are executed on the production Appie's
    to deploy a new buildout. A fresh buildout is cloned and run. Switching can 
    be done in the next task.

switch_buildout
    The current buildout will be switched with the new one. Instances are restarted 
    and finally a switch is made between the old buildout and the  new one.

1. https://intranet.gw20e.com/projects/nuffic/new-prd-release


Preparing Appie environments
------------------------------------

All Plone portals are contained in Appie environments. Appie users are
'locked' accounts by default. If a user is locked two exclamation marks can
be seen in /etc/shadow

This user is locked:

    # sudo cat /etc/shadow | grep app-nuffic-acc

    app-nuffic-acc:!!:15558:0:99999:7:::

Unlock the user:

    # sudo passwd -u app-nuffic-acc

Now we need to add your SSH public key to the authorized keys of the appie
user. If no .ssh directory of authorized_keys file is present create the ssh
dir structure by hand. Please keep in mind file permissions on ssh dir/files
must not be world/group readable and writeable.

    # appie become nuffic acc

    # vi .ssh/authorized_keys  # Add your public key

Now check if you connect via SSH:

    # ssh app-nuffic-acc@nuffic-acc

If the SSH connection is working, Fabric is also working. Use the following
command to double check:

    # fab -H nuffic-acc -u app-nuffic-acc test_connection

