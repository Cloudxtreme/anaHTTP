#!/usr/bin/env python
import sys
import sqlite3
import time
import datetime
import os
import re
from scapy.all import sniff,Ether,ARP,conf,TCP,Raw,IP,Dot11,Ether

conf.iface='wlan0'
conf.verb=0
conf.promisc=0
conf.use_pcap=True

class MySum:
    def __init__(self):
        self.count = 0

    def step(self, value):
        self.count += value

    def finalize(self):
        return self.count

class Database:
    """ Internal database to store eg. keys, datas - uses SQLite3 """

    # SQLite stuff
    socket = None
    cursor = None
    sql = None
    Stage = 1

    def dict_factory(self, cursor, row):
        """ Put results to dictionary """

        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def __init__(self, databaseDir=':memory:'):
        self.socket = sqlite3.connect(databaseDir, check_same_thread = False)

        # MySQL-like results
        self.socket.create_aggregate("mysum", 1, MySum)
        self.socket.row_factory = self.dict_factory

        self.socket.isolation_level = None
        self.cursor = self.socket.cursor()

        # new database must be built
        self.buildStructure()


    def buildStructure(self):
        """ Create tables """

        try:
            self.cursor.execute("CREATE TABLE `history` (id int(2) primary key, date double(64), url varchar(1024), cookie varchar(60), method int(1));")
            #self.cursor.execute("CREATE TABLE `ssl` (ip varchar(128) primary key, date double(64));")
        except sqlite3.OperationalError:
            pass

        return True

    def addLink(self, url, cookie, method, date):

        try:
            self.cursor.execute("INSERT INTO `history` (id, date, url, cookie, method) VALUES (NULL, '"+str(date)+"', '"+str(url)+"', '"+str(cookie)+"', '"+str(method)+"');")
        except sqlite3.OperationalError as e:
            print("Exception: "+str(e))
            pass

        return True

class anaHTTP:
    expr = 'tcp port http or tcp port 443'
    allpackets = dict()
    lastPacket = False
    whiteList = {'.css': True, '.js': True, '.exe': True}
    whiteListDomains = ('googleapis.com', 'hit.gemius.pl', 'ad.adview.pl', 'google-analytics.com', 's.photoblog.pl', 's.photoblog.pl/gazeta/ban.css', 'gstatic.com/', 'favicon.ico', 'ytimg.com/i/', 'safebrowsing-cache.google.com', 'adview.pl/ads/', 'openx.xenium.pl/www/', 'l.ghostery.com', 'safebrowsing.clients.google.com', 'chart.apis.google.com')

    sslCache = list()

    def dataParser(self, sid):
        header = self.allpackets[sid]['data']

        if "GET /" in header or "POST /" in header:
            url = re.findall('(GET|POST) (.*)\r\n', header)
            host = re.findall('Host: (.*)\r\n', header)

            method = url[0][0]

            completeUrl = host[0]+url[0][1].replace("HTTP/1.1", "").strip()

            if completeUrl[-5:] in self.whiteList:
                #print("Found whitelist item "+completeUrl)
                return None

            if completeUrl[-4:] in self.whiteList:
                #print("Found whitelist item "+completeUrl)
                return None


            # contains whitelisted domain (adserver etc.)
            for k in self.whiteListDomains:
                if k in completeUrl:
                    #print "Found: "+completeUrl
                    return None

            

            cookie = ""

            if "Cookie:" in header:
                try:
                    findCookies = re.findall('Cookie: (.*)\r\n', header)
                    cookie = findCookies[0]
                except IndexError: # if data is corrupted this can happen
                    pass

            #data = ""

            #if url[0][0] == "POST":
            #    print header

            #    findData = re.findall('\r\n\r\n(.*)', header)
            #    print findData

            if method == "POST":
                methodInt = 2
            else:
                methodInt = 1

            self.db.addLink(completeUrl, cookie, methodInt, time.time())

    def sslHost(self, ipsrc, ipdst):

        id = ipsrc+"_"+ipdst

        if not id in self.sslCache:
            self.db.addLink(ipsrc+" -> "+ipdst, "", 0, time.time())
            self.sslCache.append(id)


    def httpCallback(self, pkt):
        if pkt.haslayer(TCP):
            if pkt.getlayer(TCP).flags == 24 or pkt.getlayer(TCP).flags == 16:

                if pkt.haslayer(Raw):
                    tcpdata = pkt.getlayer(Raw).load

                    ipsrc = pkt.getlayer(IP).src
                    ipdst = pkt.getlayer(IP).dst
                    seq = pkt.getlayer(TCP).seq
                    ack = pkt.getlayer(TCP).ack
                    sport = pkt.sprintf("%IP.sport%")
                    dport = pkt.sprintf("%IP.dport%")

                    if str(sport) == "443":
                        self.sslHost(ipsrc, ipdst)
                        return None

                    TCP_SID = str(ack)+str(ipsrc)+str(ipdst) # UNIQUE KEY FOR EACH SESSION

                    if not TCP_SID in self.allpackets:
                        self.allpackets[TCP_SID] = dict()
                        self.allpackets[TCP_SID]['data'] = tcpdata
                        self.allpackets[TCP_SID]['packets'] = dict()
                        self.allpackets[TCP_SID]['packets'][seq] = pkt

                        #print("New session: "+TCP_SID)

                        if self.lastPacket != False:
                            self.dataParser(TCP_SID)

                        self.lastPacket = TCP_SID # mark last packet

                    elif TCP_SID in self.allpackets:
                        #self.allpackets[TCP_SID]['data'] = self.allpackets[TCP_SID]['data']+str(tcpdata)
                        #self.allpackets[TCP_SID]['packets'][seq] = pkt
                        return None

        return None

    def main(self):
        currentDate = datetime.date.today()
        home = os.path.expanduser("~/.anahttp/")

        if not os.path.isdir(home):
            os.mkdir(home)

        self.db = Database(home+"/"+str(currentDate.day)+"."+str(currentDate.month)+"."+str(currentDate.year))

        try:
            sniff(filter=self.expr, prn=self.httpCallback, store=0)
        except KeyboardInterrupt:
            sys.exit(0)

a = anaHTTP()
a.main()
