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
    
    def pretty_print(self):
        """Format an item in an easy-to-read self-consistent manner."""
        donestr = 'X' if self.done else ' '
        datestr = 'whenever' if self.date is None else self.date
        return '{0:<3d}{1:<s} {2:^19s} -- {3}'.format(self.item_id, donestr, datestr, self.text)
        
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
        sqldb.row_factory = sqlite3.Row
        sqldb.execute(TodoSqlite.create_sql)
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
            todo.itemid = sqldb.lastrowid
    
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
            item.item_id = row['itemID']
            if(row['done'] == 1):
                item.done = True
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
        return TodoItem(None, splittext[0].strip())
    
    print "Recording todo items. Format: <date> -- <todo>. ^D to quit."
    
    todo = sys.stdin.readline() 
    while (len(todo) != 0):
        todofile.write_todo(parse_item(todo))
        todo = sys.stdin.readline()
    
    todofile.close()

if(__name__ == "__main__"):
    sys.exit(main())
