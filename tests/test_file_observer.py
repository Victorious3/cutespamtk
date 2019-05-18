from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileDeletedEvent

def test_file_observer():

    class EventHandler(FileSystemEventHandler):
        def on_any_event(self, event):
            print("%s %r %r" % (type(event), getattr(event, "src_path", None), getattr(event, "dest_path", None)))


    file_observer = Observer()
    watch = file_observer.schedule(EventHandler(), str(Path("tests/data")))
    emitter = file_observer._emitter_for_watch.get(watch)
    file_observer.setDaemon(True)
    file_observer.start()

    emitter.queue_event(FileCreatedEvent("test.file"))

    