# Python Smappee Connect

## Smappee Connect device

![Smappee Modbus TCP](doc/mceclip0.png)

The Smappee connect:

* IP network : to allow it to connect to the Smappee cloud
  * 1x RJ45 Ethernet
  * 1x Wifi
* Modbus RTU: for internel communicatin in between Smappee modules
  * 2x Modbus RTU (RS485)

## Enabling Modbus TCP

Send a mail to Smappee support and ask them to enable it. The Smappee Connect does not host the [expert portal](https://support.smappee.com/hc/en-gb/articles/360045277952-How-to-access-the-monitor-s-expert-portal) website.

## Find your Smappee device

The app or online dashboard does not expose the IP address of your device, you'll need to login

### Via your router its DHCP table

It's exposed as 'espressif' device

```
(192.168.0.253) at 1c:9d:c2:d8:e2:4b
```

### Via MAC address in the ARP table

Lookup the device via its MAC entry in the ARP table:

```
$ arp -a | grep "1e:"
? (192.168.0.158) at 1e:8c:79:b3:75:f4 [ether] on wlp0s20f3
```

Check if it has the modbus port open;

```
$ sudo nmap -p- -sS -T5 -n -Pn 192.168.0.253
Starting Nmap 7.94SVN ( https://nmap.org ) at 2026-05-14 00:04 CEST
Nmap scan report for 192.168.0.253
Host is up (0.0024s latency).
Not shown: 65534 closed tcp ports (reset)
PORT    STATE SERVICE
502/tcp open  mbap
MAC Address: 1C:9D:C2:D8:E2:4B (Espressif)

Nmap done: 1 IP address (1 host up) scanned in 29.26 seconds
```

## Usage

```
python smappee_connect.py <ip>
```

Example:

```
python smappee_connect.py 192.168.0.253
```

## Development

### Venv

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## References

* [Smappee Modbus registers Excel sheet](doc/Smappee-Infinity-Modbus-energy-meter-registers-2026.xlsx)