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

def main():
    print sys.argv
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
        print addr
        data = json.loads(binary)
        udp_addr = data["udp"]
        print "----", data
        udp_addr = tuple(udp_addr)

        if udp_addr in clients:
            print "old", clients[udp_addr]
        clients[udp_addr] = addr

        packet = json.dumps([uaddr for uaddr in clients.iterkeys()])
        for _, remote_addr in clients.items():
            print "111", repr(packet), repr(remote_addr)
            sock.sendto(packet, remote_addr)

def run_vpn_node():
    server_ip, server_port, local_ip, local_port, tap_name = sys.argv[2:]
    server_port = int(server_port)
    local_port = int(local_port)
    server_addr = (server_ip, server_port)
    local_addr = (local_ip, local_port)

    # 连接TAP
    IFF_NO_PI = 0x1000
    # IFF_TUN = 0x0001
    IFF_TAP = 0x0002
    TUNSETIFF = 0x400454ca
    tap = open("/dev/net/tun", "r+b")
    mode = IFF_NO_PI | IFF_TAP
    print fcntl.ioctl(tap.fileno(), TUNSETIFF, struct.pack("16sH", tap_name, mode))

    # 连接 CONTROL CENTER
    control_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    packet = json.dumps({"udp":[local_ip, local_port]})
    control_sock.sendto(packet, server_addr)
    
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
        print "tick"
        readables, _, _ = select.select([control_sock, udp_sock, tap], [], [], 1)
        print "tick", readables
        for readable in readables:
            if readable is control_sock:
                print 1
                binary, _ = control_sock.recvfrom(1024)
                print "repr", repr(binary)
                data = json.loads(binary)
                print "control", data
                for uaddr in data:
                    uaddr = tuple(uaddr)
                    peers[uaddr] = Peer(uaddr)

            elif readable is tap:
                print 2
                # read from tap
                binary = os.read(tap.fileno(), 1024)
                # binary = tap.read(1024)
                print "read from tap", repr(binary), len(binary)
                # 读出来的binary是一个ethernet frame
                # char[6] + char[6] + short
                dest, source = binary[:6], binary[6:13]
                print "read from tap", repr(dest), repr(source)

                # frame routing
                peer = None
                for each in peers.itervalues():
                    if each.mac == dest:
                        peer = each
                        break

                # encode frame
                frame_binary = binary
                # encrypt 
                # send frame
                if peer:
                    print "sendto target", peer.addr
                    udp_sock.sendto(frame_binary, peer.addr)
                else:
                    print "bs"
                    for addr in peers:
                        if addr == local_addr:
                            print "skip ", local_addr
                            continue
                        print "---------" , addr
                        udp_sock.sendto(frame_binary, addr)

            elif readable is udp_sock:
                print 3
                # receive frame
                frame_binary, uaddr = udp_sock.recvfrom(1024)
                # decrypt
                # decode frame
                binary = frame_binary
                # mac learning
                dest, source = binary[:6], binary[6:13]
                print "read from udp", repr(binary)
                print "read from udp", _
                print "read from udp", repr(dest), repr(source)

                os.write(tap.fileno(), binary)
                continue
                continue
                peer = None
                for each in peers.itervalues():
                    if each.addr == uaddr:
                        peer = each
                        break
                if peer is None:
                    continue
                print "~~~~~~~~", peer.__dict__
                # write to tap

if __name__ == "__main__":
    main()

