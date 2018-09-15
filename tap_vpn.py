# encoding: utf8

"""
ip tuntap add dev tap0 mode tap
ip tuntap del dev tap0
"""

import sys
import json
import socket
import select
import struct
import os
import fcntl

def log(fmt, *args):
    if args:
        print fmt % (args)
    else:
        print fmt

def main():
    mode = sys.argv[1]
    if mode == "vpn":
        run_vpn_node()
    else:
        run_control_center()

def run_control_center():
    server_ip, server_port = sys.argv[2:]
    server_port = int(server_port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((server_ip , server_port))

    clients = {}

    while True:
        binary, addr = sock.recvfrom(1024)
        data = json.loads(binary)
        udp_addr = data["udp"]
        udp_addr = tuple(udp_addr)
        clients[udp_addr] = addr
        packet = json.dumps([uaddr for uaddr in clients.iterkeys()])
        for _, remote_addr in clients.items():
            sock.sendto(packet, remote_addr)

def run_vpn_node():
    server_ip, server_port, local_ip, local_port, tap_name = sys.argv[2:]
    server_port = int(server_port)
    local_port = int(local_port)
    server_addr = (server_ip, server_port)
    local_addr = (local_ip, local_port)

    # 连接TAP
    IFF_NO_PI = 0x1000
    IFF_TUN = 0x0001
    IFF_TAP = 0x0002
    TUNSETIFF = 0x400454ca
    tap = open("/dev/net/tun", "r+b")
    mode = IFF_NO_PI | IFF_TAP
    fcntl.ioctl(tap.fileno(), TUNSETIFF, struct.pack("16sH", tap_name, mode))

    # 连接 CONTROL CENTER
    control_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    packet = json.dumps({"udp":[local_ip, local_port]})
    control_sock.sendto(packet, server_addr), server_addr
    
    # 监听本地UDP
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind((local_ip, local_port))

    peers = {}

    class Peer(object):

        def __init__(self, addr):
            self.mac = ""
            self.addr = addr

    # 主循环
    while True:
        readables, _, _ = select.select([control_sock, udp_sock, tap], [], [], 1)
        for readable in readables:
            if readable is control_sock:
                binary, _ = control_sock.recvfrom(1024)
                data = json.loads(binary)
                log("read from control_sock %s", data)
                for uaddr in data:
                    uaddr = tuple(uaddr)
                    peers[uaddr] = Peer(uaddr)

            elif readable is tap:
                # read from tap ethernet frame
                binary = os.read(tap.fileno(), 1024)
                dest, source = binary[:6], binary[6:12]
                log("read from tap %s %s %s", repr(dest), repr(source), repr(binary[12:]))

                # frame routing
                peer = None
                if dest != "\xff\xff\xff\xff\xff\xff":
                    for each in peers.itervalues():
                        if each.mac == dest:
                            log("frame routing to %s", each.addr)
                            peer = each
                            break

                # encode frame TODO
                frame_binary = binary

                # encrypt TODO

                # send frame
                if peer:
                    log("send frame to peer %s", peer.addr)
                    udp_sock.sendto(frame_binary, peer.addr)
                else:
                    for addr in peers:
                        if addr != local_addr:
                            log("send frame to each %s", addr)
                            udp_sock.sendto(frame_binary, addr)

            elif readable is udp_sock:
                # receive frame
                frame_binary, uaddr = udp_sock.recvfrom(1024)

                # decrypt TODO

                # decode frame TODO
                binary = frame_binary

                # mac learning
                dest, source = binary[:6], binary[6:12]
                log("read from udp %s %s %s", repr(dest), repr(source), repr(binary[12:]))

                peer = None
                for each in peers.itervalues():
                    if each.addr == uaddr:
                        peer = each
                        peer.mac = source
                        log("mac learning %s %s", uaddr, repr(source))
                        break

                # write to tap
                if peer is not None:
                    log("write to tap %s", repr(binary))
                    os.write(tap.fileno(), binary)


if __name__ == "__main__":
    main()

