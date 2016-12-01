from __future__ import absolute_import

import socket

import ldaptor.protocols.ldap.ldapclient


class LDAPClient(ldaptor.protocols.ldap.ldapclient.LDAPClient):
    def _setTcpKeepCnt(self, count):
        self.transport.socket.setsockopt(
            socket.IPPROTO_TCP, socket.TCP_KEEPCNT, count)

    def _setTcpKeepIntvl(self, interval):
        self.transport.socket.setsockopt(
            socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, interval)

    def _setTcpKeepIdle(self, idle):
        if hasattr(socket, 'TCP_KEEPIDLE'):
            self.transport.socket.setsockopt(
                socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, idle)

    def connectionMade(self):
        ldaptor.protocols.ldap.ldapclient.LDAPClient.connectionMade(self)

        # Disable Nagle's algorithm to improve handling of small requests.
        self.transport.setTcpNoDelay(1)
        # Enable TCP keep-alive.
        self.transport.setTcpKeepAlive(1)
        # Set the maximum number of keep-alive packets.
        self._setTcpKeepCnt(4)
        # Send keep-alive packets every 15 seconds.
        self._setTcpKeepIntvl(15)
        # Wait 60 seconds before sending keep-alive packets.
        self._setTcpKeepIdle(60)
