#!/usr/bin/env python3
"""USB-only proof-of-concept NBD file export. NOT FOR PRIVATE DATA.
Oldstyle NBD on a dedicated lab image; never export internal iPhone storage.
"""
import argparse
import os
import socket
import stat
import struct
from pathlib import Path

MAGIC = b"NBDMAGIC" + struct.pack("!Q", 0x00420281861253)
REQ = struct.Struct("!II8sQI")
REP = struct.Struct("!II8s")
MAX_IO = 1024 * 1024
SERVER_IP, CLIENT_IP, SERVER_PORT = "172.16.42.2", "172.16.42.1", 18890

def exact(sock, n):
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise EOFError("Client disconnected")
        data.extend(chunk)
    return bytes(data)

def serve_client(conn, fd, size, allow_write=False):
    flags = 1 | 4 | 8 | (0 if allow_write else 2)
    conn.sendall(MAGIC + struct.pack("!QI", size, flags) + bytes(124))
    while True:
        try:
            magic, command, handle, offset, length = REQ.unpack(exact(conn, REQ.size))
        except EOFError:
            return
        typ, fua = command & 0xffff, bool(command & (1 << 16))
        if magic != 0x25609513:
            raise ValueError("Invalid request magic")
        if typ == 2:
            return
        invalid = length > MAX_IO or offset > size or length > size - offset or offset % 512 != 0
        if typ == 0 and not invalid:
            payload = os.pread(fd, length, offset)
            if len(payload) != length:
                raise OSError("Short read")
            conn.sendall(REP.pack(0x67446698, 0, handle) + payload)
        elif typ == 1 and allow_write and not invalid:
            payload = exact(conn, length)
            if os.pwrite(fd, payload, offset) != length:
                raise OSError("Short write")
            if fua:
                os.fsync(fd)
            conn.sendall(REP.pack(0x67446698, 0, handle))
        elif typ == 3 and allow_write:
            os.fsync(fd)
            conn.sendall(REP.pack(0x67446698, 0, handle))
        else:
            conn.sendall(REP.pack(0x67446698, 22 if invalid else 30, handle))

def serve(image, allow_write=False):
    base = (Path.home() / ".local/share/cyberdeck/storage").resolve()
    real = image.resolve(strict=True)
    if real.parent != base or real.suffix != ".img":
        raise ValueError("Only dedicated images in private storage directory")
    st = real.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o077:
        raise ValueError("Image must be a private regular file, mode 0600")
    if not (32 * 1024 * 1024 <= st.st_size <= 1024 * 1024 * 1024):
        raise ValueError("Image must be 32 MiB through 1 GiB")
    fd = os.open(real, (os.O_RDWR if allow_write else os.O_RDONLY) | os.O_NOFOLLOW)
    try:
        with socket.socket() as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((SERVER_IP, SERVER_PORT))
            server.listen(1)
            print("N71_NBD_LISTEN USB_ONLY mode=" + ("rw" if allow_write else "ro"), flush=True)
            while True:
                conn, addr = server.accept()
                with conn:
                    if addr[0] != CLIENT_IP:
                        print("N71_NBD_REJECTED_NON_USB_CLIENT", flush=True)
                        continue
                    # Do not disconnect an idle mounted filesystem at an arbitrary timeout.
                    # This remains an attended, isolated USB-only lab service.
                    conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    conn.settimeout(None)
                    try:
                        serve_client(conn, fd, st.st_size, allow_write)
                    except (EOFError, OSError, ValueError):
                        print("N71_NBD_CLIENT_DISCONNECTED", flush=True)
                    break
    finally:
        os.close(fd)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, type=Path)
    ap.add_argument("--allow-write", action="store_true")
    args = ap.parse_args()
    serve(args.image, args.allow_write)
