foxpass-setup
=========

A role that automatically install Foxpass, the logic is derived from `foxpass_setup.py`

Requirements
------------

There are no requirements

Role Variables
--------------

The following variables are what's needed to install vanilla Foxpass however one can modify default/main.yml for customization

You can modify these variables and rename `variables.example.yml` to `variables.yml` 

* base_dn: dc=test,dc=com
* bind_user: linux
* bind_pw: securedpassword
* api_key: securedapi

Dependencies
------------

There are no dependencies for this role

Example Playbook
----------------
Below is the example playbook locally, alternatively you can view the `playbook.yml`

- hosts: 127.0.0.1
  gather_facts: yes
  connection: local
  vars_files: 
    - variables.yml
  roles:
    - role: foxpass-setup

You can run the playbook locally using the following command, additional parameters can be appended especially for inventories

`ansible-playbook playbook.yml`

Running the playbook to a remote server, where hosts contains the inventory of the servers that the private key can access

`ansible-playbook -i hosts playbook-remote.yml --private-key <privatekeyfile>`

License
-------

BSD?
