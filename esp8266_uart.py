"""MicroPython module to connect ESP8266 to Raspberry Pi Pico"""

from machine import UART
from utime import sleep_ms
from binascii import b2a_base64 as base64enc

class ESP8266:

    def __init__(self, uartPort: int, baudrate: int=115200, debug: bool=False) -> None:
        """
        Parameters:
            uartPort (int): The UART port number of the Pico's UART BUS
            baudrate (int): UART baud rate for communicating between Pico & ESP8266 [Default 115200]
            debug (bool):   Default debug level for all methods if not explicitly set
        """
        self.uart = UartTimeOut(uartPort, baudrate=baudrate, txbuf=1024, rxbuf=2048)
        self.debug = debug

    #
    # BASIC COMMANDS
    # ESP8266 AT Instruction Set https://ieee-sensors.org/wp-content/uploads/2018/05/4a-esp8266_at_instruction_set_en.pdf
    #
    def test(self, debug=None):
        """Test the AT command interface"""
        response, ok = self._exec('AT', b'OK', debug=debug)
        return ok

    def echoOff(self, debug=None):
        """AT commands echoing set to OFF"""
        response, ok = self._exec('ATE0', b'OK', debug=debug)
        return ok

    def echoOn(self, debug=None):
        """AT commands echoing set to ON"""
        response, ok = self._exec('ATE1', b'OK', debug=debug)
        return ok

    def restart(self, debug=None):
        """Restarts the module """
        response, ok = self._exec('AT+RST', b'ready', timeout=10000, debug=debug)
        return ok

    def factoryReset(self, debug=None):
        """Restores the factory default settings"""
        response, ok = self._exec('AT+RESTORE', b'ready', timeout=10000, debug=debug)
        return ok

    def version(self, debug=None):
        """Checks ESP8266 version information
        Returns dictionary with 'AT version', 'SDK version' and 'compile time'
        """
        response, ok = self._exec('AT+GMR', b'OK', debug=debug)
        if (not ok):
            return None

        if (type(response) is not list):
            return None

        ret = {}
        for line in response:
            line = line.decode('utf-8').replace('\r', '').replace('\n', '')
            if (line.find('AT version:') == 0):
                ret["AT version"] = line.split(":", 1)[1]
            if (line.find('SDK version:') == 0):
                ret['SDK version'] = line.split(":", 1)[1]
            if (line.find('compile time:') == 0):
                ret['compile time'] = line.split(":", 1)[1]

        return ret

    def getSleepMode(self, debug=None):
        """Checks the sleep mode:
            0: sleep mode disabled
            1: Light-sleep mode
            2: Modem-sleep mode
        """
        response, ok = self._exec('AT+SLEEP?', b'OK', debug=debug)
        for line in response:
            line = line.decode('utf-8').replace('\r', '').replace('\n', '')
            if (line.find('+SLEEP:') == 0):
                return int(line.split(':')[1])

    def setSleepMode(self, mode, debug=None):
        """Configures the Sleep Modes. This command can only be used in Station mode. Modem-sleep (2) is the default sleep mode.
            0: disables sleep mode
            1: Light-sleep mode
            2: Modem-sleep mode
        """
        response, ok = self._exec('AT+SLEEP=' + str(mode), b'OK', debug=debug)
        return ok

    #
    # WI-FI AT COMMANDS
    #
    def getMode(self, debug=None):
        """Gets the Wi-Fi mode (Station/SoftAP/Station+SoftAP)"""
        response, ok = self._exec('AT+CWMODE_CUR?', b'OK', debug=debug)
        return self._parseMode(ok, response, '+CWMODE_CUR:', debug=debug)

    def getDefaultMode(self, debug=None):
        """Gets the Wi-Fi Mode (Station/SoftAP/Station+SoftAP)"""
        response, ok = self._exec('AT+CWMODE_DEF?', b'OK', debug=debug)
        return self._parseMode(ok, response, '+CWMODE_DEF:', debug=debug)

    def _parseMode(self, ok, response, q, debug=None):
        if (not ok):
            return None
        if (type(response) is list):
            for line in response:
                line = line.decode('utf-8')
                if (line.find(q) == 0):
                    return int(line.split(':')[1])

    def setMode(self, mode, debug=None):
        """Sets the Wi-Fi Mode (Station/SoftAP/Station+SoftAP)"""
        response, ok = self._exec('AT+CWMODE_CUR='+str(mode), b'OK', debug=debug)
        return ok

    def setDefaultMode(self, mode, debug=None):
        """Sets the Wi-Fi Mode (Station/SoftAP/Station+SoftAP)"""
        response, ok = self._exec('AT+CWMODE_DEF='+str(mode), b'OK', debug=debug)
        return ok

    def connect(self, ssid, password, bssid=None, timeout=10000, debug=None):
        """Tries to connect to an AP"""
        response, ok = self._exec('AT+CWJAP_CUR=' + self._joinArgs(ssid, password, bssid), b'OK', timeout=timeout, debug=debug)
        return ok

    def connectDefault(self, ssid, password, bssid=None, timeout=10000, debug=None):
        """Tries to connect to an AP and saves configuration in the flash"""
        response, ok = self._exec('AT+CWJAP_DEF=' + self._joinArgs(ssid, password, bssid), b'OK', timeout=timeout, debug=debug)
        return ok

    def disconnect(self, debug=None):
        response, ok = self._exec('AT+CWQAP', b'WIFI DISCONNECT', timeout=1000, debug=debug)
        return ok

    def getConnection(self, debug=None):
        """Query current connection to an AP"""
        response, ok = self._exec('AT+CWJAP_CUR?', b'OK', debug=debug)
        return self._parseConnection(ok, response, '+CWJAP_CUR:', debug=debug)

    def getDefaultConnection(self, debug=None):
        """Query default connection to an AP"""
        response, ok = self._exec('AT+CWJAP_DEF?', b'OK', debug=debug)
        return self._parseConnection(ok, response, '+CWJAP_DEF:', debug=debug)

    def _parseConnection(self, ok, response, q, debug=None):
        if (not ok):
            return False
        if (type(response) is list):
            for line in response:
                line = line.decode('utf-8')
                if (line.find('No AP') > -1):
                    return False
                if (line.find(q) == 0):
                    conn = line.replace('\r', '').replace('\n', '').split(":", 1)[1]
                    details = conn.split(",")
                    return {
                        "ssid": details[0],
                        "bssid": details[1],
                        "channel": int(details[2]),
                        "rssi": int(details[3])
                    }

    def scan(self, timeout=15000, debug=None):
        """Lists Available APs"""
        if (debug is None):
            debug = self.debug
        # set sort option (not working on my esp-01)
        # response, ok = self._exec('T+CWLAPOPT=0,15')
        response, ok = self._exec('AT+CWLAP', b'OK', timeout=timeout, debug=debug)
        aps = self._parseApList(response)
        if debug:
            print(aps)
        if aps:
            aps.sort(key=lambda item: item.get("rssi"), reverse=True)

        return aps

    def _parseApList(self, apList):
        # Authentication modes reported from scan in field 'ecn'
        ECNs = {0: "open", 1: "WEP", 2: "WPA-PSK", 3: "WPA2-PSK", 4: "WPA/WPA2-PSK"}

        if (apList is None):
            return None

        aps = []
        # [b'+CWLAP:(4,"one",-82,"22:11:33:44:55:66",1,-27,0)\r\n', b'+CWLAP:(4,"another",-33,"00:aa:bb:cc:dd:ee",1,-27,0)\r\n']
        for ap in apList:
            try:
                ap = ap.decode('utf-8')
                ap = ap.rstrip().split('+CWLAP:')[1]
                # '(4,"one",-84,"22:11:33:44:55:66",1,-27,0)'
                decoded = {}
                # eval is evil!
                ap = eval(ap)
                # (4, 'one', -84, '22:11:33:44:55:66', 1, -27, 0)
                if (len(ap) >= 3):
                    ecn = int(ap[0])
                    decoded = {
                        'ecn': ecn,
                        'auth_mode': ECNs[ecn], # UX friendly
                        'ssid': ap[1],
                        'rssi': int(ap[2])
                    }
                if (len(ap) >= 4):
                    decoded['mac'] = ap[3]
                if (len(ap) >= 5):
                    decoded['channel'] = ap[4]

                aps.append(decoded)
            except Exception: # IndexError:
                # The AP line in scan is malformatted
                continue

        return aps

    def getApMac(self, debug=None):
        """Query the MAC address of the ESP8266 SoftAP"""
        response, ok = self._exec('AT+CIPAPMAC_CUR?', b'OK', debug=debug)
        if (not ok):
            return None

        if (type(response) is list):
            for line in response:
                line = line.decode('utf-8').replace('\r', '').replace('\n', '')
                if (line.find('+CIPAPMAC_CUR:') == 0):
                    return line.split(':', 1)[1]


    def getStationMac(self, debug=None):
        """Query the MAC address of the ESP8266 station"""
        response, ok = self._exec('AT+CIPSTAMAC_CUR?', b'OK', debug=debug)
        if (not ok):
            return None

        if (type(response) is list):
            for line in response:
                line = line.decode('utf-8').replace('\r', '').replace('\n', '')
                if (line.find('+CIPSTAMAC_CUR:') == 0):
                    return line.split(':', 1)[1]

    def getApIp(self, debug=None):
        """Query the IP address of the ESP8266 SoftAP"""
        response, ok = self._exec('AT+CIPAP_CUR?', b'OK', debug=debug)
        if (not ok):
            return None
        # print(response) # [b'+CIPAP_CUR:ip:"192.168.4.1"\r\n', b'+CIPAP_CUR:gateway:"192.168.4.1"\r\n', b'+CIPAP_CUR:netmask:"255.255.255.0"\r\n', b'\r\n']
        ip = None
        gateway = None
        netmask = None

        if (type(response) is list):
            for line in response:
                line = line.decode('utf-8').replace('"', '').replace('\r', '').replace('\n', '')
                if (line.find('+CIPAP_CUR:ip:') == 0):
                    ip = line.split(":", 2)[2]
                if (line.find('+CIPAP_CUR:gateway:') == 0):
                    gateway = line.split(":", 2)[2]
                if (line.find('+CIPAP_CUR:netmask:') == 0):
                    netmask = line.split(":", 2)[2]

        if (ip is None):
            return None

        return {
            "ip": ip,
            "gateway": gateway,
            "netmask": netmask
        }


    def getStationIp(self, debug=None):
        """Query the IP address of the ESP8266 station"""
        result, ok = self._exec('AT+CIPSTA_CUR?', b'OK', debug=debug)
        if (not ok):
            return None

        # print(result) #[b'+CIPSTA_CUR:ip:"192.168.31.195"\r\n', b'+CIPSTA_CUR:gateway:"192.168.31.1"\r\n', b'+CIPSTA_CUR:netmask:"255.255.255.0"\r\n', b'\r\n']
        ip = None
        gateway = None
        netmask = None
        if (type(result) is list):
            for line in result:
                line = line.decode('utf-8').replace('"', '').replace('\r', '').replace('\n', '')
                if (line.find('+CIPSTA_CUR:ip:') == 0):
                    ip = line.split(":", 2)[2]
                if (line.find('+CIPSTA_CUR:gateway:') == 0):
                    gateway = line.split(":", 2)[2]
                if (line.find('+CIPSTA_CUR:netmask:') == 0):
                    netmask = line.split(":", 2)[2]

        if (ip is None):
            return None

        return {
            "ip": ip,
            "gateway": gateway,
            "netmask": netmask
        }

    def getApConfig(self, debug=None):
        """Gets configuration for the ESP8266 SoftAP"""
        response, ok = self._exec('AT+CWSAP_CUR?', b'OK', debug=debug)
        # +CWSAP_CUR:<ssid>,<pwd>,<chl>,<ecn>,<max conn>,<ssid hidden>
        if (not ok):
            return None
        if (type(response) is list):
            for line in response:
                line = line.decode('utf-8')
                if (line.find("+CWSAP_CUR:") == 0):
                    config = line.replace('\r', '').replace('\n', '').split(":", 1)[1]
                    details = config.split(",")
                    return {
                        "ssid": details[0],
                        "password": details[1],
                        "channel": int(details[2]),
                        "ecn": int(details[3]),
                        "max_conn": int(details[4]),
                        "hidden": bool(details[5])
                    }

    def getDefaultApConfig(self, debug=None):
        """Gets configuration for the ESP8266 SoftAP"""
        response, ok = self._exec('AT+CWSAP_DEF?', b'OK', debug=debug)
        # +CWSAP_DEF:<ssid>,<pwd>,<chl>,<ecn>,<max conn>,<ssid hidden>
        if (not ok):
            return None
        if (type(response) is list):
            for line in response:
                line = line.decode('utf-8')
                if (line.find("+CWSAP_DEF:") == 0):
                    config = line.replace('\r', '').replace('\n', '').split(":", 1)[1]
                    details = config.split(",")
                    return {
                        "ssid": details[0],
                        "password": details[1],
                        "channel": int(details[2]),
                        "ecn": int(details[3]),
                        "max_conn": int(details[4]),
                        "hidden": not bool(details[5])
                    }

    def setApConfig(self, ssid, password, channel, ecn=4, max_conn=4, hidden=0, debug=None):
        """Configures the ESP8266 SoftAP; Configuration Not Saved in the Flash"""
        response, ok = self._exec('AT+CWSAP_CUR='+self._joinArgs(ssid, password, channel, ecn, max_conn, hidden), debug=debug)
        return ok

    def setDefaultApConfig(self, ssid, password, channel, ecn=4, max_conn=4, hidden=0, debug=None):
        """Configures the ESP8266 SoftAP;"""
        response, ok = self._exec('AT+CWSAP_DEF='+self._joinArgs(ssid, password, channel, ecn, max_conn, hidden), debug=debug)
        return ok

    def startServer(self, port=80, maxAllowedConnections=1, tcpTimeout=30, debug=None):
        if (1 > maxAllowedConnections > 5):
            raise Exception('Max Allowed TCP Connection must be between 1 and 5')
        if (0 > tcpTimeout > 7200):
            raise Exception('Max TCP Timeout must be between 0 and 7200 seconds')
        # A TCP server can only be created when multiple connections are activated (AT+CIPMUX=1)
        self._exec('AT+CIPMUX=1', b'OK', debug=debug)
        # Set the Maximum Connections Allowed by Server - in this case we want 1
        self._exec('AT+CIPSERVERMAXCONN='+str(maxAllowedConnections), b'OK', debug=debug)
        # Start the server on requested port
        response, ok = self._exec('AT+CIPSERVER=1,'+str(port), b'OK', debug=debug)
        # Sets the TCP Server Timeout - in this case we need 30 s
        self._exec('AT+CIPSTO='+str(tcpTimeout), b'OK', debug=debug)
        return ok

    def stopServer(self, debug=None):
        response, ok = self._exec('AT+CIPSERVER=0', b'OK', debug=debug)
        return ok

    #
    # TCP/IP-Related Commands
    #
    def ping(self, destination, debug=None):
        """Ping the destination address or hostname"""
        """Returns the response time or None if the ping is unsuccessful"""
        result, ok = self._exec('AT+PING='+self._joinArgs(destination), b'OK', debug=debug)
        if (debug):
            print(result)

        if (type(result) is list):
            for line in result:
                line = line.decode('utf-8').replace('\r', '').replace('\n', '')
                if (line.find('ERR') > -1):
                    return None
                if (line.find('+timeout') > -1):
                    return None
                if (line.find('+') == 0):
                    # the response time of ping
                    return int(line.replace('+', ''))

    def httpRequest(self, method, url, data=None, headers=[], user_agent="ESP-01 (on RPi Pico)", timeout=10000, debug=None):
        if method not in ["HEAD", "GET", "POST", "PUT", "DELETE"]:
            raise Exception('Unknown HTTP method ' + method)

        try:
            proto, nothing, host, path = url.split("/", 3)
        except ValueError:
            proto, nothing, host = url.split("/", 2)
            path = ""
        path = "/" + path
        if proto == "http:":
            transportType = "TCP"
            port = 80
        elif proto == "https:":
            transportType = "SSL"
            port = 443
        else:
            raise Exception("Unsupported protocol: " + proto)

        if "@" in host:
            auth, host = host.split("@", 1)
        else:
            auth = None
        if ":" in host:
            host, port = host.split(":", 1)
            port = int(port)

        if (not self.startConnection(transportType, host, port)):
            if (debug):
                print('startConnection failed')
            return None

        header = method + " " + path + " HTTP/1.1\r\n" + "Host: " + host + "\r\n" + "User-Agent: " + user_agent + "\r\n" + "Connection: close\r\n"
        if auth:
            auth = str(base64enc(auth)).replace("b'", "").replace("\\n'", "")
            header += f"Authorization: Basic {auth}\r\n"
        header += "\r\n"
        if (debug):
        #    print('Connection to', host, 'ESTABLISHED')
            print('Requesting:')
            print(header)
        result, ok = self._exec("AT+CIPSEND="+str(len(header)), b'OK')
        result, ok = self._exec(header, b'SEND OK', timeout=timeout)
        if (debug):
            print(result)

        _, data = self.receiveData(debug=debug)
        #self.closeConnection(debug=debug)

        return data

    def _parseHttpResponse(self, response):
        if (response is None):
            return 0, None

        data = ""
        headers = []
        code = 0

        if data:
            data = data.split("\r\n\r\n")
            headers = data[0].split('\r\n')
            data = data[1]

        return code, headers, data

    def startConnection(self, transportType, link, port=80, debug=None):
        """Establishes TCP/SSL Connection"""
        if (transportType not in ['TCP', 'UDP', 'SSL']):
            raise Exception('Invalid Transport Type')

        # self._exec("AT+CIPMUX=0")
        args = self._joinArgs(transportType, link, port)
        # print('AT+CIPSTART=' + args)
        result, ok = self._exec('AT+CIPSTART=' + args, b'OK', timeout=5000, debug=debug)

        # if ok == False does not mean that there is no connection
        # check for ERROR and CONNECT (ALREADY CONNECTED)
        if (type(result) is list):
            for line in result:
                line = line.decode('utf-8').replace('\r', '').replace('\n', '')
                if (line.find('ERR') > -1):
                    return False
                if (line.find('CONN') > -1):
                    return True
                if (line.find('OK') > -1):
                    return True

        return ok

    def closeConnection(self, debug=None):
        """Closes Connection"""
        result, ok = self._exec('AT+CIPCLOSE', b'OK', debug=debug)

        return True

    def receiveData(self, debug=None):
        if (debug is None):
            debug = self.debug

        data = self.uart.read()
        if (data != None):
            data = data.decode()
            if debug:
                print(data)
            if (data.find('+IPD') >= 0):
                n1 = data.find('+IPD,')
                n2 = data.find(':',n1+5)
                ID = int(data[n1+5:n2])
                n3 = data.find(':')
                data = data[n3+1:]
                if data.endswith('CLOSED'):
                    data = data[:-6]
                return ID, data
        return None, None

    def sendResponse(self, connId, data, statusCode=200, debug=None):
        if (debug is None):
            debug = self.debug

        cnt = len(data)
        data = "HTTP/1.1 {} OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n".format(statusCode) + data
        result, ok = self._exec('AT+CIPSEND='+str(connId)+','+str(cnt), b'OK')
        self.uart.write(data)
        if (debug):
            print(data)
        self.closeConnection(debug=debug)

    def _exec(self, cmd, acc=None, timeout=2000, debug=None):
        DELTA_WAIT = 100 # the time in milliseconds before checking the result
        if (debug is None):
            debug = self.debug

        result = []
        ok = False
        if (debug):
            print ('<', cmd)
        cmd += '\r\n' # AT commands must end with a new line (CR LF)
        self.uart.write(cmd)

        # wait no more then a maximum timeout given (in milliseconds) for a command reaction
        ticks = int(timeout / DELTA_WAIT)
        if (ticks < 1):
            ticks = 1
        while ticks > 0:
            if self.uart.any():
                line = self.uart.readline()
                if not line:
                    continue
                if (debug):
                    print('>',line)
                if line.rstrip() == b'OK':
                    ok = True
                if (acc and (line.rstrip() == acc)):
                    return result, ok
                else:
                    result.append(line)
            else:
                sleep_ms(DELTA_WAIT)
            ticks -= 1

        return result, ok

    def _joinArgs(self, *args):
        result = []
        for arg in args:
            if type(arg) is str:
                # TODO: escape backslash with backslash \ -> \\
                # TODO: escape double quote with backslash " -> \"
                result.append('"' + arg + '"')
            elif type(arg) is bytes:
                result.append(arg.decode())
            elif type(arg) is bool:
                result.append(str(int(arg)))
            elif arg is not None:
                result.append(str(arg))
        return ','.join(result)

from utime import ticks_ms

class UartTimeOut(UART):
    """
    The MicroPython port for RPi Pico has no timeout for readline() at this moment.
    We use this hack to make sure it won't get stuck forever.

    Thanks to Roger
    https://github.com/myvobot/pi_pico_wifi_driver/blob/main/uart_timeout_any.py
    """
    def readline(self, timeOut=100):
       if timeOut is None:
           return super().readline()
       else:
           now = ticks_ms()
           data = b''
           while True:
               if ticks_ms()-now > timeOut:
                   break
               else:
                   if super().any():
                       _d = super().read(1)
                       data += _d
                       if "\n" in _d:
                           break
           return data
