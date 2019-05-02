from xmlrpc.server import SimpleXMLRPCServer

from cutespam import config
from cutespam.hashtree import HashTree

__last_updated = 0

server = SimpleXMLRPCServer(("localhost", config.SERVICE_PORT))