import rpyc

from rpyc.utils.server import OneShotServer

from cutespam import db
from cutespam.config import config
from cutespam.hashtree import HashTree

class DBService(rpyc.Service):
    def __init__(self, functions):
        for name, f in functions.items():
            def wrapper(f, name):
                def function(*args, **kwargs):
                    print("Calling", name)
                    return f(*args, **kwargs)
                return function
            setattr(self, name, wrapper(f, name))

def main():
    db.init_db()

    server = OneShotServer(service = DBService(db._functions), hostname = "localhost", port = config.service_port, protocol_config = {
        "allow_public_attrs": True
    })

    print("Listening on port", config.service_port)

    while True:
        server.start()

if __name__ == "__main__":
    main()