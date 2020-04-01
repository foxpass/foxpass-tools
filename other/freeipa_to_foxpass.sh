#!/bin/bash
if [[ $(id -u) -ne 0 ]]; then
echo "Must run as 'root'"
exit 1
fi
set -eou pipefail

apt-get remove sssd libpam-sss freeipa-common sssd-ipa libipa-hbac0 -y
apt-get autoremove -y
apt-get clean -y
rm -rf /var/lib/ipa-client

rm -rf /etc/sssd/*

sed -i 's/KerberosAuthentication.\+//g' /etc/ssh/sshd_config
sed -i 's/PubkeyAuthentication.\+//g' /etc/ssh/sshd_config
sed -i 's/AuthorizedKeysCommand.\+//g' /etc/ssh/sshd_config
sed -i 's/GSSAPIAuthentication.\+//g' /etc/ssh/sshd_config
sed -i 's/ChallengeResponseAuthentication.\+//g' /etc/ssh/sshd_config

echo "###############################"
echo "Setup FoxPass"
echo "###############################"
curl -o /tmp/foxpass_setup.py https://raw.githubusercontent.com/foxpass/foxpass-setup/master/linux/ubuntu/18.04/foxpass_setup.py
python3 /tmp/foxpass_setup.py --base-dn dc=example,dc=com --bind-user [bind_user] --bind-pw XXXXXXXX --api-key XXXXXXXX

export SUDO_FORCE_REMOVE=yes

rm -f /etc/sudoers.d/95-foxpass-sudo
apt-get install sudo-ldap libpam-ldapd -y

cat > /etc/sudo-ldap.conf <<-EOF
#
# LDAP Defaults
#

# See ldap.conf(5) for details
# This file should be world readable but not world writable.

URI ldaps://ldap.foxpass.com
BINDDN cn=[bind_user],dc=example,dc=com
BINDPW XXXXXXXX

# The amount of time, in seconds, to wait while trying to connect to
# an LDAP server.
bind_timelimit 30
#
# The amount of time, in seconds, to wait while performing an LDAP query.
timelimit 30
#
# Must be set or sudo will ignore LDAP; may be specified multiple times.
sudoers_base ou=SUDOers,dc=example,dc=com
#
# verbose sudoers matching from ldap
sudoers_debug 0
#
# Enable support for time-based entries in sudoers.
sudoers_timed yes

#SIZELIMIT 12
#TIMELIMIT 15
#DEREF never

# TLS certificates (needed for GnuTLS)
TLS_CACERT /etc/ssl/certs/ca-certificates.crt
EOF

sed -i 's/sudoers:.\+/sudoers:\tldap files/g' /etc/nsswitch.conf

service sshd restart
