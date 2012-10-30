#!/usr/bin/env python
import sqlite3
import time
import datetime
import sys
import getopt
import os
import gtk
import urlparse

class MySum:
    def __init__(self):
        self.count = 0

    def step(self, value):
        self.count += value

    def finalize(self):
        return self.count

class WhereStatement:
    columns = {}
    types = {}

    def __init__(self):
        self.columns = {}
        self.types = {}

    def push(self, column, value, types='='):
        self.columns[column] = value
        self.types[column] = types

    def build(self):
        query = ""
        count = 0

        for column in self.columns:
            count = count + 1

            if count > 1:
                query += "AND "

            if self.types[column] == '%':
                query += column+" like '%"+self.columns[column]+"%'"
            else:
                query += column+" = '"+self.columns[column]+"'"

        if query != "":
            return "WHERE "+query
        else:
            return ""

class Database:
    """ Internal database to store eg. keys, datas - uses SQLite3 """

    # SQLite stuff
    socket = None
    cursor = None
    sql = None
    Stage = 1

    def __init__(self, databaseDir):
        if not os.path.isfile(databaseDir):
            print("Database file does not exists")
            sys.exit(0)
            

        self.socket = sqlite3.connect(databaseDir, check_same_thread = False)

        # MySQL-like results
        self.socket.create_aggregate("mysum", 1, MySum)
        self.socket.row_factory = self.dict_factory

        self.socket.isolation_level = None
        self.cursor = self.socket.cursor()

    def dict_factory(self, cursor, row):
        """ Put results to dictionary """

        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d


class anaHttpView:
    filters = {'date': False, 'count': False}

    def usage(self):
        print("--help, -u    - displays usage")
        print("--date, -d    - specify date, format: 30.12.2089")

    def main(self):
        try:
            opts, args = getopt.getopt(sys.argv[1:], "ud:h", ['help', 'date=', 'hour='])
        except Exception as err:
            print("Error: "+str(err)+", Try --help for usage\n\n")
            self.usage()
            sys.exit(2)

        for o, a in opts:
            if o in ('-u', '--help'):
                self.usage()
                sys.exit(2)

            if o in ('-d', '--date'):
                self.filters['date'] = a

        currentDate = datetime.date.today()
        self.home = os.path.expanduser("~/.anahttp/")

        dbFile = self.home+"/"+str(currentDate.day)+"."+str(currentDate.month)+"."+str(currentDate.year)

        if not os.path.isfile(dbFile):
            k = os.listdir(self.home)

            if len(k) > 0:
                dbFile = self.home+"/"+k[0]

        self.DB = Database(dbFile)
        self.drawInterface()
        self.addFromDB()

        gtk.main()

    def addLink(self, date, method, url, cookies, parent=None):
        if method == 1:
            method = "GET"
        else:
            method = "POST"

        a = self.treestore.append(parent, [datetime.datetime.fromtimestamp(date).strftime('%Y-%m-%d %H:%M:%S'), method, url, cookies])
        self.window.show_all()

        return a

    def dialog(self, text):
        dialog = gtk.MessageDialog(self.window, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE, text)
        dialog.run()
        dialog.destroy()

    def showDialog(self, Object, Event):
        if str(Event.type.value_name) == "GDK_2BUTTON_PRESS":
            entry1,entry2 = self.treeview.get_selection().get_selected()

            text = "Method:\n"+entry1.get_value(entry2, 1)+"\n\nURL:\nhttp://"+entry1.get_value(entry2, 2)

            if entry1.get_value(entry2, 3) != "":
                text += "\n\nCookies:\n"+entry1.get_value(entry2, 3)

            self.dialog(text)

    def addFromDB(self, query='SELECT * FROM `history`'):
        print(query)

        obj = self.DB.cursor.execute(query)
        rows = obj.fetchall()

        lastDomain = False
        lastA = False
        
        for row in rows:
            url = urlparse.urlparse("http://"+row['url'])
            
            if lastDomain == url.netloc:
                a = self.addLink(row['date'], row['method'], row['url'], row['cookie'], parent=lastA)
            else:
                a = self.addLink(row['date'], row['method'], row['url'], row['cookie'], parent=None)
                lastA = a
                
            lastDomain = url.netloc


    def newSearch(self, a=''):
        self.DB = Database(self.home+"/"+self.searchDate.get_active_text())

        query = ""
        statement = WhereStatement()

        if self.searchMethod.get_active_text() != "All":
            if self.searchMethod.get_active_text() == "POST":
                method = "2"
            else:
                method = "1"

            statement.push("method", method)

        if self.searchURL.get_text() != "":
            statement.push("url", self.searchURL.get_text(), types='%')

        self.treestore.clear()
        self.addFromDB(query="SELECT * FROM `history` "+statement.build())

    def newQuerySearch(self, a=''):
        self.treestore.clear()
        self.addFromDB(self.queryText.get_text())

    def exitApplication(self, a='', b=''):
        sys.exit(0)

    def drawInterface(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_size_request(640, 480)
        self.window.set_title("anaHttp - przegladarka danych")

        self.window.connect("delete_event", self.exitApplication)

        self.treestore = gtk.TreeStore(str, str, str, str)

        self.treeview = gtk.TreeView(self.treestore)
        self.treeview.connect("button-press-event", self.showDialog)

        # date column
        tvcolumn = gtk.TreeViewColumn('Date')
        self.treeview.append_column(tvcolumn)

        cell = gtk.CellRendererText()
        tvcolumn.pack_start(cell, True)
        tvcolumn.add_attribute(cell, 'text', 0)
        tvcolumn.set_sort_column_id(0)

        # Method column
        methodColumn = gtk.TreeViewColumn('Method')
        self.treeview.append_column(methodColumn)

        methodCell = gtk.CellRendererText()
        methodColumn.pack_start(methodCell, True)
        methodColumn.add_attribute(methodCell, 'text', 1)
        methodColumn.set_sort_column_id(1)

        # URL column
        urlColumn = gtk.TreeViewColumn('URL')
        self.treeview.append_column(urlColumn)

        urlCell = gtk.CellRendererText()
        urlColumn.pack_start(urlCell, True)
        urlColumn.add_attribute(urlCell, 'text', 2)
        urlColumn.set_sort_column_id(2)

        # Cookie column
        cookieColumn = gtk.TreeViewColumn('Cookies')
        self.treeview.append_column(cookieColumn)

        cookieCell = gtk.CellRendererText()
        cookieColumn.pack_start(cookieCell, True)
        cookieColumn.add_attribute(cookieCell, 'text', 3)
        cookieColumn.set_sort_column_id(3)

        self.treeview.set_search_column(2)
        #self.treeview.set_reorderable(True)

        # Scrollbars
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        scrolled_window.set_border_width(0)
        #scrolled_window.set_size_request(600, 200)
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(self.treeview)

        # URL filtering
        searchLabel = gtk.Label("URL: ")
        self.searchURL = gtk.Entry()

        # date filtering
        dateLabel = gtk.Label("Date: ")
        self.searchDate = gtk.combo_box_new_text()

        files = os.listdir(self.home)

        for file in files:
            if os.path.isfile(self.home+"/"+file):
                self.searchDate.append_text(file)
        self.searchDate.set_active(0)

        # method filtering
        methodLabel = gtk.Label("Method: ")
        self.searchMethod = gtk.combo_box_new_text()
        self.searchMethod.append_text("All")
        self.searchMethod.append_text("POST")
        self.searchMethod.append_text("GET")
        self.searchMethod.set_active(0)

        searchButton = gtk.Button("Search")
        searchButton.connect("clicked", self.newSearch)

        # first row
        hbox = gtk.HBox()
        hbox.pack_start(searchLabel)
        hbox.pack_start(self.searchURL)
        hbox.pack_start(dateLabel)
        hbox.pack_start(self.searchDate)
        hbox.pack_start(methodLabel)
        hbox.pack_start(self.searchMethod)
        hbox.pack_end(searchButton)

        queryLabel = gtk.Label("DB Query: ")
        self.queryText = gtk.Entry()
        self.queryText.set_text("SELECT * FROM `history`")

        queryButton = gtk.Button("Search")
        queryButton.connect("clicked", self.newQuerySearch)

        tableLabel = gtk.Label("Columns: id, date, url, cookie, method")

        # second row
        hboxQuery = gtk.HBox()
        hboxQuery.pack_start(queryLabel)
        hboxQuery.pack_start(self.queryText)
        hboxQuery.pack_start(queryButton)


        Box = gtk.VBox()
        Box.pack_start(scrolled_window, True, True, 1)
        Box.pack_start(hbox, False, False, 1)
        Box.pack_end(hboxQuery, False, False, 1)
        Box.pack_start(tableLabel, False, False, 1)

        self.window.add(Box)
        self.window.show_all()

        
a = anaHttpView()
a.main()

    
