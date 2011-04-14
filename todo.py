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

import sys, os
import optparse
import sqlite3
import datetime
import collections
import re

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
    optparser.add_option('-l', '--list', action='store_true', default=False,
        help='List the current items.')
    optparser.add_option('-s', '--search', action='append', metavar='REGEX',
        help='Search for an item based on a regex')
    optparser.add_option('--start-date', default=datetime.datetime.now(),
        nargs=1, help='Specify the starting date of the list.', metavar='DATE')
    optparser.add_option('--end-date', help='Specify the final listing date',
        nargs=1, default=datetime.datetime.now() + datetime.timedelta(days=5),
        metavar='DATE')
    optparser.add_option('--list-complete', default=False,
        action='store_true', help='List completed todo items')
    optparser.add_option('--hide-incomplete', default=False,
        action='store_true', help='Do not list incomplete todo items.')
    optparser.add_option('-c', '--complete', type='int', action='append',
        help='Mark an item as complete and exit.', metavar='ID')
    optparser.add_option('--list-id', default=False, action='store_true',
        help='Include the item ID in the output listing')
    optparser.add_option('--list-date', default=False, action='store_true',
        help='Include the due date in the output listing')
    optparser.add_option('-r', '--remove', type='int', action='append',
        help='Remove an item from the list and exit.', metavar='ID')
    optparser.add_option('-i', '--interactive', default=False,
        action='store_true', help='Add items interactively')
    optparser.add_option('-a', '--add', action='append',
        help='Add an item to the todo list.', metavar='NOTE')
    (options, arguments) = optparser.parse_args()

    with TodoManager(os.path.expanduser(options.database)) as todofile:
        if options.complete is not None:
            complete_items(todofile, options.complete)
        if options.remove is not None:
            remove_items(todofile, options.remove)
        if options.search is not None:
            options.list = True
        else:
            options.search = []
        #TODO make this cleaner
        if (options.list or options.list_complete or options.list_id or
            options.list_date):
            if type(options.start_date) is str:
                options.start_date = parse(options.start_date)
            if type(options.end_date) is str:
                options.end_date = parse(options.end_date)
            list_items(todofile, options, options.search)
        if options.add is not None:
            add_items(todofile, options.add)
        if options.interactive:
            interactive(todofile)

def find_items(todofile, items):
    """Return a list of items sharing itemid in items. """
    return [x for x in todofile.fetch_items() if x.itemid in items]

def remove_items(todofile, items):
    """Remove several items from the database altogether."""
    for item in find_items(todofile, items):
        todofile.remove_todo(item)

def complete_items(todofile, items):
    """Complete several items."""
    for item in find_items(todofile, items):
        todofile.finish_todo(item)

def list_items(todofile, opt, args):
    """List each todo item, one per each line."""
    def filt(item):
        """Filter function based on options."""
        result = (((item.done and opt.list_complete) or
            (not item.done and not opt.hide_incomplete)) and
            ((item.time is None) or
            (opt.start_date < item.time < opt.end_date)))
        for arg in args:
            result = result and (re.search(arg, item.text) != None)
        return result

    for item in [x for x in todofile.fetch_items() if filt(x)]:
        list_str = []
        list_str.append('X' if item.done else ' ')
        if(opt.list_id):
            list_str.append('{0:<3d}'.format(item.itemid))
        if(opt.list_date and item.time is not None):
            list_str.append(item.time.strftime('%c') + ' --')
        list_str.append(item.text)
        print ' '.join(list_str)

def add_items(todofile, items):
    """Parse user input from the todo file."""
    if(items is not None and len(items) > 0):
        for item in items:
            todofile.write_todo(parse_item(item))

def interactive(todo):
    print "Recording todo items. Format: <date> -- <todo>. ^D to quit."
    todotext = sys.stdin.readline()
    while (len(todotext) != 0):
        todofile.write_todo(parse_item(todotext))
        todotext = sys.stdin.readline()

def parse_item(todotext):
    """Parse an item from the following string: <date> -- <item>"""
    matchobj = re.match(r'^(.*)--(.*)$', todotext)
    if(matchobj != None):
        try:
            date = parse(matchobj.group(1).strip())
            text = matchobj.group(2).strip()
            return TodoItem(time=date, text=text, itemid=0, done=False)
        except:
            pass
    return TodoItem(time=None, text=todotext.strip(), itemid=0, done=False)

#Acts as the DAO for TodoManager's ORM
TodoItem = collections.namedtuple('TodoItem', 'itemid time text done')

class TodoManager:
    """ Sits atop the Todo DB and manages application interaction with it. """
    create_sql = '''
    CREATE TABLE IF NOT EXISTS TodoItems(
        itemid INTEGER PRIMARY KEY AUTOINCREMENT,
        time TIMESTAMP,
        text TEXT,
        done BOOLEAN);
     '''
    insert_sql = '''
        INSERT INTO TodoItems(time, text, done)
        VALUES (:time, :text, :done)
    '''
    update_sql = '''
        UPDATE TodoItems
        SET time = :time, text = :text, done = :done
        WHERE itemid = :itemid
    '''
    delete_sql = 'DELETE FROM TodoItems WHERE itemid = :itemid'
    select_sql = 'SELECT itemid, time, text, done FROM TodoItems'

    def __init__(self, dbpath):
        self.sqldb = sqlite3.connect(dbpath,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self.sqldb.execute(TodoManager.create_sql)
        self.sqldb.commit()
        self.items = None
        self.updated_items = []
        self.new_items = []
        self.deleted_items = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if traceback is None:
            self.__execsql(TodoManager.delete_sql, self.deleted_items)
            self.__execsql(TodoManager.update_sql, self.updated_items)
            self.__execsql(TodoManager.insert_sql, self.new_items)
            self.sqldb.commit()
        else:
            self.sqldb.rollback()

    def __execsql(self, sql, seq):
        """ Wrapper around executemany for line length. """
        return self.sqldb.executemany(sql, [x._asdict() for x in seq])

    def write_todo(self, todo):
        """ Insert a new todo item in the database. """
        self.new_items.append(todo)

    def finish_todo(self, todo):
        """ Mark an item as completed in the database. """
        self.updated_items.append(todo._replace(done=True))

    def remove_todo(self, todo):
        """ Remove a todo from the database. """
        self.deleted_items.append(todo)

    def fetch_items(self):
        """ Fetch the set of inserted items """
        if self.items is None:
            rows = self.sqldb.execute(TodoManager.select_sql).fetchall()
            self.items = [TodoItem._make(row) for row in rows]
        return self.items

if(__name__ == "__main__"):
    sys.exit(main())
