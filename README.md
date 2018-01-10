# Dependencies

This software requires the following libraries: argparse\_actions, pyroute2,
portalocker, serf-python.

For installing argparse\_actions, pyroute2, portalocker executes:

```bash
pip install argparse\_actions, pyroute2, portalocker
```

For installing serf-python, executes:

```bash
git clone https://github.com/spikeekips/serf-python.git
git checkout 6feec505ce98e53c97b9edbabe2b7e3d99fbe4fc
cd serf-python
python setup.py install
```


# Usage examples

In all the examples that follow we assume we want to use "psngc" as the channels
tag name (specified with option -t) and that the RPC deamon responds at address
127.0.0.1 on port 7373 (specified with options -a and -p respectively).

# Add a new channel

Suppose you want to add a new channel named "Channel1" and whose source IP
address and port are 192.168.100.2 and 6000 respectively. Then you execute the
following command:

```
python psng-pyserf.py -t psngc -a 127.0.0.1 -p 7373 set 192.168.100.2 6000 "Channel1" "Reserved" http://192.168.100.2:8080/video.sdp
```

The last string "Reserved" can be used to specify any additional parameters that
can be useful for whoever will receive this channel.

NOTE: It is not possible to add two different channel that use the same address
and port. This contraint is verified only on the local node, this means that is
responsibility of the local node to use the correct source channel IP address.

NOTE: Adding a new channel propagates a member-update event on the Serf network.
If the channel already exist on the list of channels of the local node, then the
member-update event is not generated.


# Delete a channel

Channel deletion is based exclusively on the source IP address and port of a
channel. The channel name and the "Reserved" string are ignored. Suppose you
want to delete the channel that was added in the previous example (address
192.168.100.2 and port 6000). The you execute the following command:

```
python psng-pyserf.py -t psngc -a 127.0.0.1 -p 7373 del 192.168.100.2 6000
```

NOTE: Deleting a channel propagates a member-update event on the Serf network.
If the channel is not present in the list of channels that belong to the local
node, then the member-update event is not generated.


# Running the software in background

All the nodes that are interested in keepeing an updted list of channels
existing on the network should run the software in background mode with the
following command:

```
python psng-pyserf.py -t psngc -a 127.0.0.1 -p 7373 bg /tmp/channels.db
```

the path specified at the end of the command is the channels database file that
the software will use to list the existing channels. This file is written for
the first time when the software starts and is updated everytime a channel is
added or deleted (this is known by listening to the member-update events). The
software use an exclusive file system file lock every time the file is updated.
The file is formatted by an header line (starting with the character "#") and by
a list of zero or more channels. Here an examples of the channels database file
containing two channels:

\# channel\_name,source\_addr,source\_port,channel\_params
Channel1,192.168.100.2,6000,Reserved
Cool Channel,192.168.100.3,7000,720p h264

