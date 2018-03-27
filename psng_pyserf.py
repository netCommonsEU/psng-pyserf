#!/usr/bin/env python

# BSD 3-Clause License
#
# Copyright (c) 2017, netCommons H2020 project
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its contributors
# may be used to endorse or promote products derived from this software without
# specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import argparse
import argparse_actions
import serf
import sys
import portalocker


class Channel(object):
    def __init__(self, name, ipaddr, port, quality, sdpuri):
        self.ipaddr = ipaddr
        self.port = port
        self.name = name
        self.quality = quality
        self.sdpuri = sdpuri

    def __str__(self):
        return self.name + "," + self.ipaddr + "," + str(self.port) + "," + \
            self.quality + "," + self.sdpuri

    def to_tuple(self):
        return (self.ipaddr, self.port, self.name, self.quality, self.sdpuri)

    def __hash__(self):
        return hash(self.ipaddr + self.port + self.name)

    def __eq__(self, src):
        return self.ipaddr == src.ipaddr and \
            self.port == src.port and \
            self.name == src.name

    def __ne__(self, src):
        return not self.__eq__(src)

    @classmethod
    def channel_from_file(cls, filedb):
        res = set()
        try:
            db_file = open(filedb, 'r')
            portalocker.lock(db_file, portalocker.LOCK_EX)
            for line in db_file:
                line = line.strip()
                if len(line) > 0 and line[0] != "#":
                    tokens = line.split(',')
                    res.add(Channel(tokens[0], tokens[1], tokens[2], tokens[3],
                                    tokens[4]))
            db_file.close()
        except IOError:
            sys.stderr.write("Local source database not found...\n")

        return res


class PSngSerfClient(object):
    def __init__(self, rpc_addr, rpc_port):
        self.serf_client = serf.Client(rpc_addr + ":" + str(rpc_port))
        self.serf_client.handshake().request()
        self._psng_event = "PSng-channel"

    def broadcast_channel(self, addr, port, name, txt, sdp):
        c = Channel(name, addr, port, txt, sdp)
        self.serf_client.event(Name=self._psng_event, Payload=str(c)).request()

    def list_channels(self):
        channel_bucket = set([])

        def channel_callback(res):
            if res.is_success:
                line = res.body["Payload"]
                line = line.strip()
                tokens = line.split(',')
                channel_bucket.add(Channel(tokens[0], tokens[1], tokens[2],
                                           tokens[3], tokens[4]))
        self.serf_client.stream(Type="user:"+str(self._psng_event))
        self.serf_client.add_callback(channel_callback).request()
        return channel_bucket

    def channel_synch(self, dbfile, source_dbfile):
        while True:
            source_chs = Channel.channel_from_file(source_dbfile)
            for ch in source_chs:
                print("Adding local: " + str(ch))
                self.broadcast_channel(*ch.to_tuple())

            chs = self.list_channels()
            db_file = open(dbfile, 'w')
            portalocker.lock(db_file, portalocker.LOCK_EX)
            for ch in chs.difference(source_chs):
                print("Adding remote: " + str(ch))
                db_file.write(str(ch) + "\n")
            db_file.close()


def psng_serf_client_init():
    parser = argparse.ArgumentParser()

    parser.add_argument("-a", "--rpcaddress", type=str, default="127.0.0.1",
                        help="IP address of the Serf RPC server",
                        dest="rpcaddress",
                        action=argparse_actions.ProperIpFormatAction)
    parser.add_argument("-p", "--rpcport", type=int, default=7373,
                        help="TCP port of the Serf RPC server",
                        dest="rpcport", choices=range(0, 65536),
                        metavar="[0-65535]")

    subparsers = parser.add_subparsers(dest="command")
    # Set PeerStreamer Next-Generation source tag
    parser_set = subparsers.add_parser("set", help="Set and propagate the "
                                       "PeerStreamer-ng channel")
    parser_set.add_argument("caddr", type=str,
                            help="Source channel IP address",
                            action=argparse_actions.ProperIpFormatAction)
    parser_set.add_argument("cport", type=int, choices=range(0, 65536),
                            help="Source channel port",
                            metavar="[0-65535]")
    parser_set.add_argument("cname", type=str,
                            help="Source channel name")
    parser_set.add_argument("ctxt", type=str,
                            help="Source channel additional parameters")
    parser_set.add_argument("csdpuri", type=str,
                            help="SDP URI of the channel")

    parser_list = subparsers.add_parser("list", help="List channels")
    parser_list.add_argument("caddr", type=str,
                             help="Source channel IP address",
                             action=argparse_actions.ProperIpFormatAction)
    parser_list.add_argument("cport", type=int, choices=range(0, 65536),
                             help="Source channel port",
                             metavar="[0-65535]")
    parser_db = subparsers.add_parser("bg",
                                      help="Run in background and keep the "
                                      "database file updated by listening to "
                                      "Serf events.")
    parser_db.add_argument("dbfile", type=str,
                           help="Channels database file")
    parser_db.add_argument("src_dbfile", type=str,
                           help="Local source database file")

    try:
        args = parser.parse_args()

        rpc_address = args.rpcaddress
        rpc_port = args.rpcport

        client = PSngSerfClient(rpc_address, rpc_port)
        print(client)

        command = args.command
        if command == "bg":
            ch_dbfile = args.dbfile
            source_dbfile = args.src_dbfile
            client.channel_synch(ch_dbfile, source_dbfile)
        elif command == "set":
            ch_addr = args.caddr
            ch_port = args.cport
            ch_name = args.cname
            ch_txt = args.ctxt
            ch_sdpuri = args.csdpuri
            client.broadcast_channel(ch_addr, ch_port, ch_name, ch_txt,
                                     ch_sdpuri)
        elif command == "list":
            chs = client.list_channels()
            print(chs)
        else:
            print "Unknown mode"
            return -1

    except argparse_actions.InvalidIp as e:
        print "IP address is invalid: {0}".format(e.ip)


if __name__ == "__main__":
    psng_serf_client_init()
