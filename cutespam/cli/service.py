
import Pyro4, signal

from cutespam import db
from cutespam.config import config
from cutespam.hashtree import HashTree

class DBService:
    def __init__(self):
        self.db = db.connect_db()

    def ping(self): return "pong"
           
for name, f in db._functions.items():
    def wrapper(f, name):
        def function(self, *args, **kwargs):
            kwargs.pop("db", None)
            print("Calling", name)
            return f(*args, db = self.db, **kwargs)
        return function
    setattr(DBService, name, wrapper(f, name))


def main():
    db.init_db()
    db.start_listeners() 

    Pyro4.config.COMMTIMEOUT = 0.5
    Pyro4.config.REQUIRE_EXPOSE = False
    Pyro4.config.SERIALIZERS_ACCEPTED = set(["pickle"])

    # Make sure we are running a single thread to share the database connection
    # TODO This should be changed in the future, multiple threads already use their own db.
    # Pass db as first parameter to every method?
    #Pyro4.config.SERVERTYPE = "multiplex" 

    deamon = Pyro4.Daemon(host = "localhost", port = config.service_port)
    uri = deamon.register(DBService, objectId = "cutespam-db")

    print("Listening on port", config.service_port)
    print("uri:", uri)

    deamon.requestLoop()

if __name__ == "__main__":
    main()