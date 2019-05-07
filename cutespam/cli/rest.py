import sys, struct, json, threading, os
import logging, traceback
import dataclasses

from queue import Queue
from time import sleep

from cutespam import api, JSONEncoder

stdin = None
stdout = None

def read_input(queue: Queue):
    while True:
        # Read the message length (first 4 bytes).
        text_length_bytes = stdin.read(4)
        if len(text_length_bytes) == 0: # Prepare exit
            queue.put(None)
            sys.exit(0)

        # Unpack message length as 4 byte integer.
        text_length = struct.unpack('i', text_length_bytes)[0]
        # Read the text (JSON object) of the message.
        message = json.loads(stdin.read(text_length).decode("utf-8"))
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
        apif = api.get_apifun(action)

        del message["action"]
        reply = apif(**message)
        if isinstance(reply, dict):
            message = reply
        else:
            try:
                message = getattr(reply, "__dict__")
            except:
                message = reply

        if message is None:
            send_message("OK")
        else:
            send_message(message)

    except Exception as e:
        tb = ''.join(traceback.format_exception(etype = type(e), value = e, tb = e.__traceback__))
        send_message({"error": str(e), "trace": tb})

def send_message(message):
    text = json.dumps(message, cls = JSONEncoder)
    # Write message size.
    stdout.write(struct.pack('I', len(text)))
    # Write the message itself.
    stdout.write(text.encode("utf-8"))
    stdout.flush()

def main():
    # On Windows, the default I/O mode is O_TEXT. Set this to O_BINARY
    # to avoid unwanted modifications of the input/output streams.
    if sys.platform == "win32":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

    global stdout, stdin
    stdout = sys.stdout.buffer
    stdin = sys.stdin.buffer

    sys.stdout = open(os.devnull, "w") # Make sure nothing upsets comms
    sys.stdin = open(os.devnull, "r")

    queue = Queue()

    thread = threading.Thread(target=read_input, args=(queue,))
    thread.daemon = True
    thread.start()

    process_input(queue)

if __name__ == "__main__":
    main()
   