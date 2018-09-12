# encoding: utf8

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
    if mode == "ctrl_center":
        run_control_center()
    else:
        run_vpn_node()

def run_control_center():
    server_ip, server_port = sys.argv[2:]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((server_ip , server_port))

    clients = set()

    while True:
        binary, addr = sock.recvfrom(1024)
        data = json.loads(binary)
        udp_addr = data["udp"]

        if udp_addr not in clients:
            clients[addr] = udp_addr

        packet = json.dumps([uaddr for _, uaddr in clients.iteritems()])
        for remote_addr in clients.items():
            sock.sendto(packet, remote_addr)

def run_vpn_node():
    server_ip, server_port, local_ip, local_port, tap_name = sys.argv[2:]
    server_addr = (server_ip, server_port)

    # 连接TAP
    IFF_NO_PI = 0x1000
    # IFF_TUN = 0x0001
    IFF_TAP = 0x0002
    TUNSETIFF = 0x400454ca
    tap = open("/dev", "rw")
    mode = IFF_NO_PI | IFF_TAP
    fcntl.ioctl(tap.fileno(), TUNSETIFF, struct.pack("16sH", tap_name, mode))

    # 连接 CONTROL CENTER
    control_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    packet = json.dumps({"udp":[local_ip, local_port]})
    control_sock.sendto(packet, server_addr)
    
    # 监听本地UDP
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind((local_ip, local_port))

    peers = {}

    class Peer(object):
        pass

    # 主循环
    while True:
        readables, _, _ = select.select([control_sock, udp_sock, tap])
        for readable in readables:
            if readable is control_sock:
                binary, _ = control_sock.recvfrom(1024)
                data = json.loads(binary)
                for uaddr, in data:
                    peers[uaddr] = Peer()

            elif readable is tap:
                # read from tap
                binary = tap.read()
                # 读出来的binary是一个ethernet header
                # char[6] + char[6] + short
                dest, source, type_ = binary[:14]

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
                    udp_sock.sendto(frame_binary, peer.addr)
                else:
                    for each in peers:
                        udp_sock.sendto(frame_binary, each.addr)

            elif readable is udp_sock:
                # receive frame
                frame_binary, _ = udp_sock.recv(1024)
                # decrypt
                # decode frame
                binary = frame_binary
                # mac learning
                # write to tap
                dest, source, type_ = binary[:14]

if __name__ == "__main__":
    main()

