#!/usr/bin/python
# -*- coding: utf-8 -*-
"""No bullshit way to add items to a todo list.
"""

#TODO: Integrate with unix util 'at', notifications
#TODO: Integrate with gcal

import sys, os
import optparse
import sqlite3
from dateutil.parser import parse

class TodoItem:
    """Contains the data used in constructing a Todo item."""
    def __init__(self, date, text):
        """Initialize the instance variables"""
        self.date = date
        self.text = text
        self.item_id = 0
        self.done = False
        
    def set_item_id(self, item_id):
        """Set an item id for interaction with todo items"""
        self.item_id = item_id
        
    def set_done(self, done):
        """Decide if an item is 'done'"""
        self.done = done
    
    def pretty_print(self):
        """Format an item in an easy-to-read self-consistent manner."""
        
        prepstr = str(self.item_id).rjust(3)
        if(self.done):
            prepstr += 'X'
        else:
            prepstr += ' '
        
        datestr = self.date
        if(datestr is None):
            datestr = 'whenever'
        
        return '%s %s -- %s' % (prepstr, datestr, self.text)
        
class TodoSqlite:
    """Abstraction of a sqlite database containing todo items"""
    create_sql = 'CREATE TABLE IF NOT EXISTS TodoItems(itemID INTEGER PRIMARY KEY AUTOINCREMENT, time DATETIME, text TEXT, done INTEGER);'
    insert_sql = 'INSERT INTO TodoItems(time, text, done) VALUES (?,?,0)'
    select_sql = 'SELECT itemID, time, text, done FROM TodoItems'
    finish_sql = 'UPDATE TodoItems SET done = 1 WHERE itemID = ?'
    
    def __init__(self, path):
        """Open, create the required table Notes in the database. Initialize queries"""
        self.open_file = None
        sqldb = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
        sqldb.execute(TodoSqlite.create_sql)
        sqldb.row_factory = sqlite3.Row
        self.open_file = sqldb
        
    def close(self):
        """Close & commit data"""
        if(self.open_file is not None):
            self.open_file.commit()
            self.open_file.close()
            self.open_file = None
            
    def write_todo(self, todo):
        """Write a todo item to the database."""
        if self.open_file is not None:
            sqldb = self.open_file.cursor()
            #write the todo item
            sqldb.execute(TodoSqlite.insert_sql, [todo.date, todo.text])
            itemid = sqldb.lastrowid
            todo.set_item_id(itemid)
    
    def finish_todo(self, todoid):
        """Mark a todo item as complete."""
        if(self.open_file is not None):
            sqldb = self.open_file.cursor()
            sqldb.execute(TodoSqlite.finish_sql, [todoid])
    
    def list_items(self):
        """Returns a list of all todo items"""
        def r2td(row):
            """Converts a SQLite Row object into a TodoItem"""
            item = TodoItem(row['time'], row['text'])
            item.set_item_id(row['itemID'])
            if(row['done'] == 1):
                item.set_done(True)
            return item
            
        if self.open_file is not None:
            sqldb = self.open_file.cursor()
            sqldb.execute(TodoSqlite.select_sql)
            return map(r2td, sqldb.fetchall())
        return None
             
def main():
    """Run through the arguments, then loop through user input until we're out"""
    parser = optparse.OptionParser(
        usage='Take todo items and store them in a database')
    parser.add_option('-d', '--database', default='~/.todo.db', 
        type="string", help='Specify the database file used.')
    parser.add_option('-l', '--list', default=False,
        action='store_true', help='List the current TODO items')
    parser.add_option('-f', '--finish', default=0,
        type='int',  help='Mark an item as complete, then exit')
    parser.add_option('-q', '--quit', default=False,
        action='store_true', help='Quit on startup. Useful for -l and -f')
    
    (options, arguments) = parser.parse_args()
    
    todofile = TodoSqlite(os.path.expanduser(options.database))
    
    if(options.finish > 0):
        todofile.finish_todo(options.finish)
    
    if (options.list):
        items = todofile.list_items()
        if(items is not None):
            for item in items:
                print item.pretty_print()
    
    if(options.quit):
        todofile.close()
        return
        
    def parse_item(todotext):
        """Parse an item from the following string: <date> -- <item>"""
        splittext = todotext.split('--')
        if(len(splittext) > 1):
            date = parse(splittext[0])
            note = ' '.join(splittext[1:])
            return TodoItem(date, note.strip())
        return TodoItem(None, splittext[0])
    
    print "Recording todo items. Format: <date> -- <todo>. ^D to quit."
    
    todo = sys.stdin.readline() 
    while (len(todo) != 0):
        todofile.write_todo(parse_item(todo))
        todo = sys.stdin.readline()
    
    todofile.close();

if(__name__ == "__main__"):
    sys.exit(main())
