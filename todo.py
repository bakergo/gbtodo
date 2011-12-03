#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2011, Greg Baker.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""No bullshit way to add items to a todo list."""

import sys, os
import optparse
import sqlite3
import datetime
import collections
import re
import tempfile
import subprocess

try:
    from dateutil.parser import parse
except ImportError:
    print "Can't load python-dateutil (do you have it installed?)"
    print "Dates must be of format MM/DD/YY"
    def parse(date):
        return datetime.datetime.strptime(date, "%m/%d/%y")

def main():
    """Run through the arguments, then run through user input until we're out"""
    optparser = optparse.OptionParser(
        usage='%prog [Options]',
        version='%prog 0.2')
    optparser.add_option('-d', '--database', default='~/.todo.db',
        type='string', help='Specify the database file used')
    optparser.add_option('-a', '--add', action='append',
        help='Add a task to the todo list', metavar='TASK')
    optparser.add_option('-i', '--interactive', default=False,
        action='store_true', help='Add tasks interactively')
    optparser.add_option('-r', '--remove', type='int', action='append',
        help='Remove a task from the list', metavar='ID')
    optparser.add_option('-c', '--complete', type='int', action='append',
        help='Mark a task as complete', metavar='ID')
    optparser.add_option('-l', '--list', action='store_true', default=False,
        help='List the current tasks')
    optparser.add_option('-s', '--search', action='append', metavar='REGEX',
        help='Show only tasks matching a given regular expression')
    optparser.add_option('--list-id', default=False, action='store_true',
        help='Include the task ID in the output listing')
    optparser.add_option('--list-date', default=False, action='store_true',
        help='Include the due date in the output listing')
    optparser.add_option('--list-complete', default=False,
        action='store_true', help='List completed todo tasks')
    optparser.add_option('--hide-incomplete', default=False,
        action='store_true', help='Do not list incomplete tasks')
    optparser.add_option('--start-date', default=datetime.datetime.now(),
        nargs=1, help='Specify the starting date of the list', metavar='DATE')
    optparser.add_option('--end-date', help='Specify the final listing date',
        nargs=1, default=datetime.datetime.now() + datetime.timedelta(days=5),
        metavar='DATE')
    if(len(sys.argv) == 1):
        optparser.print_help()
        return 0
    (options, arguments) = optparser.parse_args()
    # Implied options
    options.list = (options.list or options.list_id or options.list_date or
            options.list_complete or (options.search is not None))

    with TodoManager(os.path.expanduser(options.database)) as todofile:
        if options.complete is not None:
            complete_items(todofile, options.complete)
        if options.remove is not None:
            remove_items(todofile, options.remove)
        if options.search is None:
            options.search = []
        if options.list:
            if type(options.start_date) is str:
                options.start_date = parse(options.start_date)
            if type(options.end_date) is str:
                options.end_date = parse(options.end_date)
            list_items(todofile, options, options.search)
        if options.add is not None:
            add_items(todofile, options.add)
        if options.interactive:
            interactive(todofile)

def remove_items(todofile, items):
    """Remove several items from the database altogether."""
    for item in filter(lambda x: x.itemid in items, todofile.fetch_items()):
        todofile.remove_todo(item)

def complete_items(todofile, items):
    """Complete several items."""
    for item in filter(lambda x: x.itemid in items, todofile.fetch_items()):
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

    for item in filter(filt, todofile.fetch_items()):
        list_str = ['']
        if (item.done):
            list_str.append('X')
        elif (item.time is not None and item.time < datetime.datetime.now()):
            list_str.append('!')
        else:
            list_str.append('*')
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

def interactive(todofile):
    """ Opens an interactive text editor to edit multiple items """
    tmpfile = tempfile.NamedTemporaryFile(suffix='.txt', prefix='todo-',
            delete=False)
    print >> tmpfile
    print >> tmpfile , '# Todo items should be formed as <date> -- <todo>'
    print >> tmpfile , '# The date field is optional.'
    print >> tmpfile , '# Lines starting with # are ignored.'
    tmpfile.close()
    subprocess.call(['editor', tmpfile.name])
    with open(tmpfile.name) as writtenfile:
        add_items(todofile, writtenfile.readlines())
    os.remove(tmpfile.name)

def parse_item(todotext):
    """Parse an item from the following string: <date> -- <item>"""
    matchobj = re.match(r'^(.*)--(.*)$', todotext)
    ignore = re.search(r'^((#(.*))|(\s+))$', todotext)
    if ignore != None:
        return None
    if(matchobj != None):
        try:
            date = parse(matchobj.group(1).strip())
            text = matchobj.group(2).strip()
            return TodoItem(time=date, text=text, itemid=0, done=False)
        except ValueError:
            # Can't parse the date. Ignore it.
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
        if todo != None:
            print 'added "%s"' % todo.text
            self.new_items.append(todo)

    def finish_todo(self, todo):
        """ Mark an item as completed in the database. """
        self.updated_items.append(todo._replace(done=True))
        print 'completed "%s"' % todo.text

    def remove_todo(self, todo):
        """ Remove a todo from the database. """
        self.deleted_items.append(todo)
        print 'removed "%s"' % todo.text

    def fetch_items(self):
        """ Fetch the set of inserted items """
        if self.items is None:
            rows = self.sqldb.execute(TodoManager.select_sql).fetchall()
            self.items = [TodoItem._make(row) for row in rows]
        return self.items

if(__name__ == "__main__"):
    sys.exit(main())
