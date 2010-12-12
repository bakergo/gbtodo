#!/usr/bin/python
# -*- coding: utf-8 -*-
#       Copyright 2010, Greg Baker.
#       All rights Reserved
#       Redistribution and use in source and binary forms, with or without
#       modification, are permitted provided that the following conditions are
#       met:
#       
#       * Redistributions of source code must retain the above copyright
#         notice, this list of conditions and the following disclaimer.
#       * Redistributions in binary form must reproduce the above
#         copyright notice, this list of conditions and the following disclaimer
#         in the documentation and/or other materials provided with the
#         distribution.
#       * Neither the name of the  nor the names of its
#         contributors may be used to endorse or promote products derived from
#         this software without specific prior written permission.
#       
#       THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#       "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#       LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#       A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#       OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#       SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#       LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#       DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#       THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#       (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#       OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""No bullshit way to add items to a todo list."""

#TODO: Integrate with unix util 'at', notifications
#TODO: Integrate with gcal

import sys, os
import optparse
import sqlite3
import datetime

try:
    from dateutil.parser import parse
except:
    print 'Error loading module dateutil.'
    print 'Dates can not be parsed until the module is loaded.'

def main():
    """Run through the arguments, then run through user input until we're out"""
    optparser = optparse.OptionParser(
        usage='%prog [Options]',
        version='%prog 0.0')
    optparser.add_option('-d', '--database', default='~/.todo.db', 
        type='string', help='Specify the database file used.')
    optparser.add_option('-l', '--list', default=False, action='store_true',
        help='List the current items.')
    optparser.add_option('--start_date', default=datetime.datetime.now(),
        nargs=1, help='Specify the starting date of the list.')
    optparser.add_option('--end_date', help='Specify the final listing date',
        nargs=1, default=datetime.datetime.now() + datetime.timedelta(days=1))
    optparser.add_option('--list_complete', default=False, 
        action='store_true', help='List completed todo items')
    optparser.add_option('--hide_incomplete', default=False, 
        action='store_true', help='Do not list incomplete todo items.')
    optparser.add_option('-c', '--complete', type='int', action='append', 
        help='Mark an item as complete and exit.')
    optparser.add_option('--list_id', default=False, action='store_true',
        help='Include the item ID in the output listing')
    optparser.add_option('--list_date', default=False, action='store_true',
        help='Include the due date in the output listing')
    optparser.add_option('-r', '--remove', type='int', action='append',
        help='Remove an item from the list and exit.')
    optparser.add_option('-a', '--add', default=False, action='store_true',
        help='Add an item to the todo list.')
    optparser.add_option('--notify', type='int', default=0,
        help='Display a notification that the item is due.')
    (options, arguments) = optparser.parse_args()
    
    with TodoSqlite(os.path.expanduser(options.database)) as todofile:
        if options.notify is not 0:
            notify_item(todofile, options.notify)
        if options.complete is not None:
            complete_items(todofile, options.complete)
        if options.remove is not None:
            remove_items(todofile, options.remove)
        if options.list:
            if type(options.start_date) is str:
                options.start_date = parse(options.start_date)
            if type(options.end_date) is str:
                options.end_date = parse(options.end_date)
            list_items(todofile, options)
        if options.add:
            add_items(todofile)
    
def remove_items(todofile, items):
    """Remove several items from the database altogether."""
    for item in items:
        todofile.remove_todo(item)
        
def complete_items(todofile, items):
    """complete several items."""
    for item in items:
        todofile.finish_todo(item)

def list_items(todofile, options):
    """List each todo item, one per each line."""
    items = todofile.list_items(options)
    if items is not None:
        for item in items:
            list_str = []
            donestr = 'X' if item.done else ' '
            item_id = '{0:<3d}'.format(item.item_id)
            datestr = '{0:^19s} --'.format(item.date)
            list_str.append(donestr)
            if(options.list_id): 
                list_str.append(item_id)
            if(options.list_date): 
                list_str.append(datestr)
            list_str.append(item.text)
            print ' '.join(list_str)
            
def add_items(todofile):
    """Parse user input from the todo file."""
    def parse_item(todotext):
        """Parse an item from the following string: <date> -- <item>"""
        splittext = todotext.split('--')
        if(len(splittext) > 1):
            try:
                date = parse(splittext[0])
                note = ' '.join(splittext[1:])
                return TodoItem(date, note.strip())
            except:
                pass
        return TodoItem(None, todotext.strip())
        
    print "Recording todo items. Format: <date> -- <todo>. ^D to quit."
    todo = sys.stdin.readline()
    while (len(todo) != 0):
        todofile.write_todo(parse_item(todo))
        todo = sys.stdin.readline()

def notify_item(todofile, itemid):
    """Pop up a notification using the python notification library."""
    try:
        import pynotify
        todo = todofile.get_todo(itemid)
        notification = pynotify.Notification("Todo Reminder", 
            todo.text, "help-hint")
        notification.show()
    except:
        print "Could not find itemid %d" % itemid

class TodoItem:
    """Contains the data used in constructing a Todo item."""
    def __init__(self, date, text):
        """Initialize the instance variables"""
        self.date = date
        self.text = text
        self.item_id = 0
        self.done = False
        
class TodoSqlite:
    """Abstraction of a sqlite database containing todo items"""
    create_sql = 'CREATE TABLE IF NOT EXISTS TodoItems(itemID INTEGER PRIMARY\
     KEY AUTOINCREMENT, time DATETIME, text TEXT, done INTEGER);'
    insert_sql = 'INSERT INTO TodoItems(time, text, done) VALUES (?,?,0)'
    select_sql = '''
SELECT TodoItems.itemID, TodoItems.time, TodoItems.text, TodoItems.done 
FROM TodoItems
WHERE
((TodoItems.time > ? AND TodoItems.time < ?) OR 
    TodoItems.time IS NULL) AND 
((TodoItems.done = 1 AND ? = 1) OR 
    (TodoItems.done = 0 AND ? = 0))
ORDER BY TodoItems.time, TodoItems.itemID
'''
    finish_sql = 'UPDATE TodoItems SET done = 1 WHERE itemID = ?'
    delete_sql = 'DELETE FROM TodoItems WHERE itemID = ?'
    get_sql = 'SELECT itemID, time, text, done FROM TodoItems WHERE itemID = ?'
    
    def __init__(self, path):
        """Open, create the required table Notes in the database.
        Initialize queries"""
        self.open_file = None
        sqldb = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
        sqldb.row_factory = sqlite3.Row
        sqldb.execute(TodoSqlite.create_sql)
        self.open_file = sqldb
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        if traceback is None:
            self.open_file.commit()
        else: 
            self.open_file.rollback()
        self.open_file.close()
        self.open_file = None
            
    def write_todo(self, todo):
        """Write a todo item to the database."""
        if self.open_file is not None:
            sqldb = self.open_file.cursor()
            #write the todo item
            sqldb.execute(TodoSqlite.insert_sql, [todo.date, todo.text])
            todo.itemid = sqldb.lastrowid
    
    def finish_todo(self, todoid):
        """Mark a todo item as complete."""
        if(self.open_file is not None):
            sqldb = self.open_file.cursor()
            sqldb.execute(TodoSqlite.finish_sql, [todoid])
            
    def remove_todo(self, todoid):
        """Remove a todo item from the database."""
        if(self.open_file is not None):
            sqldb = self.open_file.cursor()
            sqldb.execute(TodoSqlite.delete_sql, [todoid])
    
    def get_todo(self, todoid):
        """Select a single item from the database."""
        if(self.open_file is not None):
            sqldb = self.open_file.cursor()
            sqldb.execute(TodoSqlite.get_sql, [todoid])
            return self.__row_to_todo(sqldb.fetchone())
            
    def list_items(self, options):
        """Returns a list of all todo items"""
        if self.open_file is not None:
            sqldb = self.open_file.cursor()
            sqldb.execute(TodoSqlite.select_sql, 
                [options.start_date, options.end_date,
                options.list_complete, options.hide_incomplete])
            return [self.__row_to_todo(row) for row in sqldb.fetchall()]
        return None
    
    def __row_to_todo(self, row):
        """Converts a SQLite Row object into a TodoItem"""
        item = TodoItem(row['time'], row['text'])
        item.item_id = row['itemID']
        if(row['done'] == 1):
            item.done = True
        return item

if(__name__ == "__main__"):
    sys.exit(main())
