"""No-device protocol tests for the bounded N71 USB NBD laboratory export."""
import importlib.util
from pathlib import Path
import socket
import struct
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("nbd_export", ROOT / "experimental/storage/nbd_export.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

def recv_exact(sock, size):
    out = bytearray()
    while len(out) != size:
        out += sock.recv(size - len(out))
    return bytes(out)

class NBDProtocol(unittest.TestCase):
    def test_reject_write_in_read_only_mode(self):
        self.trial(False)

    def test_read_write_fsync_and_bounds(self):
        self.trial(True)

    def trial(self, writable):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "lab.img"
            image.write_bytes(bytes(8192))
            fd = image.open("r+b", buffering=0)
            client, server = socket.socketpair()
            errors = []
            def serve():
                try:
                    module.serve_client(server, fd.fileno(), 8192, writable)
                except Exception as exc:
                    errors.append(exc)
                finally:
                    server.close()
            thread = threading.Thread(target=serve)
            thread.start()
            try:
                hs = recv_exact(client, 152)
                self.assertTrue(hs.startswith(b"NBDMAGIC"))
                self.assertEqual(struct.unpack("!Q", hs[16:24])[0], 8192)
                self.assertEqual(bool(struct.unpack("!I", hs[24:28])[0] & 2), not writable)
                def request(typ, offset=0, data=b"", length=0):
                    tag = b"TESTABCD"
                    client.sendall(struct.pack("!II8sQI", 0x25609513, typ, tag, offset, length))
                    if typ == 1 and writable and length <= module.MAX_IO:
                        client.sendall(data)
                    return recv_exact(client, 16)
                write = request(1, 0, b"ABCD" * 128, 512)
                self.assertEqual(struct.unpack("!I", write[4:8])[0], 0 if writable else 30)
                response = request(0, 0, b"", 512)
                self.assertEqual(struct.unpack("!I", response[4:8])[0], 0)
                data = recv_exact(client, 512)
                self.assertEqual(data, b"ABCD" * 128 if writable else bytes(512))
                self.assertEqual(struct.unpack("!I", request(0, 8192, b"", 512)[4:8])[0], 22)
                if writable:
                    self.assertEqual(struct.unpack("!I", request(3)[4:8])[0], 0)
                client.sendall(struct.pack("!II8sQI", 0x25609513, 2, b"TESTABCD", 0, 0))
            finally:
                client.close()
                thread.join(3)
                fd.close()
                self.assertFalse(thread.is_alive())
                self.assertFalse(errors, errors)

if __name__ == "__main__":
    unittest.main()
