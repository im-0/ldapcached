from __future__ import absolute_import

import functools
import logging

import twisted.internet
from twisted.internet import reactor

import ldaptor.protocols.ldap.ldapconnector

import ldapcached.cache
import ldapcached.client
import ldapcached.proxy


# Logger.
_log = logging.getLogger(__name__)


def _build_protocol(client_connector, conf, cache):
    proto = ldapcached.proxy.LDAPProxy(cache)
    proto.clientConnector = client_connector
    proto.use_tls = conf.get('upstream_use_tls', False)
    return proto


def run(conf):
    factory = twisted.internet.protocol.ServerFactory()
    client_connector = functools.partial(
        ldaptor.protocols.ldap.ldapconnector.connectToLDAPEndpoint,
        reactor,
        conf['upstream'],
        ldapcached.client.LDAPClient)

    cache = ldapcached.cache.LDAPSearchCache(conf.get('cache_conf', {}))

    factory.protocol = functools.partial(
        _build_protocol, client_connector, conf, cache)
    listen_port = conf.get('listen_port', 389)
    reactor.listenTCP(listen_port, factory)
    _log.info('Server started on port %u', listen_port)
    reactor.run()
