from xmlrpc.server import SimpleXMLRPCServer

from cutespam import db
from cutespam.config import config
from cutespam.hashtree import HashTree

db.init_db()

server = SimpleXMLRPCServer(("localhost", config.service_port))
for f in db._functions:
    server.register_function(f)
server.serve_forever()