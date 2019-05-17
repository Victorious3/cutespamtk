
import Pyro4, signal
import argparse
import logging
import logging.handlers

from cutespam import db, log, log_formatter
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
            log.debug("Calling %s", name)
            return f(*args, db = self.db, **kwargs)
        return function
    setattr(DBService, name, wrapper(f, name))


def main():
    parser = argparse.ArgumentParser("Database service")
    parser.add_argument("-t", "--trace", action = "store_true")
    ARGS = parser.parse_args()

    # Write to service.log
    fh = logging.handlers.RotatingFileHandler(config.log_folder / "service.log", maxBytes = 10**7, backupCount = 20)
    fh.setFormatter(log_formatter)
    log.addHandler(fh)

    if ARGS.trace:
        config.trace_debug = True

    if config.trace_debug:
        log.info("trace_debug enabled")
        log.setLevel(logging.DEBUG)

    log.info("Starting service")
    db.init_db()
    db.start_listeners() 

    Pyro4.config.COMMTIMEOUT = 0.5
    Pyro4.config.REQUIRE_EXPOSE = False
    Pyro4.config.SERIALIZERS_ACCEPTED = set(["pickle"])

    deamon = Pyro4.Daemon(host = "localhost", port = config.service_port)
    uri = deamon.register(DBService, objectId = "cutespam-db")

    log.info("Listening on port %s", config.service_port)
    log.info("uri: %s", uri)

    deamon.requestLoop()

if __name__ == "__main__":
    main()