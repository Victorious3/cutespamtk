import sys, struct, json, threading
import logging, traceback
import api
import dataclasses

from queue import Queue
from time import sleep

def read_input(queue: Queue):
    while True:
        # Read the message length (first 4 bytes).
        text_length_bytes = sys.stdin.read(4)
        if len(text_length_bytes) == 0: # Prepare exit
            queue.put(None)
            sys.exit(0)

        # Unpack message length as 4 byte integer.
        text_length = struct.unpack('i', text_length_bytes)[0]
        # Read the text (JSON object) of the message.
        message = json.loads(sys.stdin.read(text_length).decode("utf-8"))
        queue.put(message)

def process_input(queue: Queue):
    while True:
        while not queue.empty():
            message = queue.get_nowait()
            if message == None:
                return
            on_message(message)
        sleep(0.01)

def on_message(message):
    try:
        action = message["action"].replace("-", "_")
        try:
            apif = getattr(api, action)
        except AttributeError:
            send_message({"error": "Invalid action " + message["action"]})
        else:
            del message["action"]
            reply = apif(**message)
            message = reply.__dict__
            send_message(message)

    except Exception as e:
        tb = ''.join(traceback.format_exception(etype = type(e), value = e, tb = e.__traceback__))
        send_message({"error": str(e), "trace": tb})

def send_message(message):
    text = json.dumps(message)
    # Write message size.
    sys.stdout.write(struct.pack('I', len(text)))
    # Write the message itself.
    sys.stdout.write(text.encode("utf-8"))
    sys.stdout.flush()

if __name__ == "__main__":
    # On Windows, the default I/O mode is O_TEXT. Set this to O_BINARY
    # to avoid unwanted modifications of the input/output streams.
    if sys.platform == "win32":
        import os, msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

    sys.stdout = sys.stdout.buffer
    sys.stdin = sys.stdin.buffer

    queue = Queue()

    thread = threading.Thread(target=read_input, args=(queue,))
    thread.daemon = True
    thread.start()

    process_input(queue)
   