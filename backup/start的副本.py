#!/usr/bin/env python

import datetime
import math
import optparse #处理参数
import os
import re
import sys
import threading
import time
import webbrowser
from collections import namedtuple, OrderedDict 
from functools import wraps
import urllib

# Py3k compat.
if sys.version_info[0] == 3:
    binary_types = (bytes, bytearray)
    decode_handler = 'backslashreplace'
    numeric = (int, float)
    unicode_type = str
    from io import StringIO
else:
    binary_types = (buffer, bytes, bytearray)
    decode_handler = 'replace'
    numeric = (int, long, float)
    unicode_type = unicode
    from StringIO import StringIO

try:
    from flask import (
        Flask, abort, escape, flash, jsonify, make_response, Markup, redirect,
        render_template, request, session, url_for)
except ImportError:
    raise RuntimeError('Unable to import flask module. Install by running '
                       'pip install flask')

try:
    from pygments import formatters, highlight, lexers
except ImportError:
    import warnings
    warnings.warn('pygments library not found.', ImportWarning)
    syntax_highlight = lambda data: '<a>%s</a>' % data
else:
    def syntax_highlight(data):
        if not data:
            return ''
        lexer = lexers.get_lexer_by_name('xml')
        formatter = formatters.HtmlFormatter(linenos=False)
        return highlight(data, lexer, formatter)

try:
    from peewee import __version__
    peewee_version = tuple([int(p) for p in __version__.split('.')])
except ImportError:
    raise RuntimeError('Unable to import peewee module. Install by running '
                       'pip install peewee')
else:
    if peewee_version <= (2, 4, 2):
        raise RuntimeError('Peewee >= 2.4.3 is required. Found version %s. '
                           'Please update by running pip install --update '
                           'peewee' % __version__)

from peewee import *
from peewee import IndexMetadata
'''
class IndexMetadata(name, sql, columns, unique, table)

name:The name of the index.
sql:The SQL query used to generate the index.
columns:A list of columns that are covered by the index.
unique:A boolean value indicating whether the index has a unique constraint.
table:The name of the table containing this index.
'''
from playhouse.dataset import DataSet
from playhouse.migrate import migrate

CUR_DIR = os.path.realpath(os.path.dirname(__file__))
DEBUG = True
MAX_RESULT_SIZE = 1000
# ROWS_PER_PAGE = 50
ROWS_PER_PAGE = 50
SECRET_KEY = 'sqlite-database-browser-0.1.0'
special_characters=[['u̯', 'i̯', 'm̄', 'ḟ', '·'], 
                    ['ȩ', '⁊', 'ɫ', 'Ȩ', 'ṡ'], 
                    ['ā', 'ē', 'ī', 'ō', 'ū'], 
                    ['ä', 'ë', 'ï', 'ö', 'ü'], 
                    ['ă', 'ĕ', 'ĭ', 'ŏ', 'ŭ'], 
                    ['æ', 'Æ', 'ʒ', 'đ', 'ɔ̄'], 
                    ['φ', 'þ', 'β', '˜', 'χ'], 
                    ['γ', '∅', 'ə', 'ɛ', 'ƀ'], 
                    ['θ', 'ð', 'ɣ', 'ɸ', 'β']]


app = Flask(
    __name__,
    static_folder=os.path.join(CUR_DIR, 'static'),
    template_folder=os.path.join(CUR_DIR, 'templates'))
app.config.from_object(__name__)
dataset = None
migrator = None

#
# Database metadata objects.
#

TriggerMetadata = namedtuple('TriggerMetadata', ('name', 'sql'))

ViewMetadata = namedtuple('ViewMetadata', ('name', 'sql'))
def format_str(origin_str):
    return origin_str.replace("'","''").replace('/','//').replace('%','/%').replace('_','/_').replace('^','/^').replace('-','_').replace('·','_')
def escape_single_quote(origin_str):
    return origin_str.replace("'","''")

# def replace_dash(origin_str):
#     return origin_str.replace("-","/_").replace(".","/_").replace("•","/_")
#
# Database helpers.
#

class SqliteDataSet(DataSet):
    @property
    def filename(self):
        return os.path.realpath(dataset._database.database)

    @property
    def base_name(self):
        return os.path.basename(self.filename)

    @property
    def created(self):
        stat = os.stat(self.filename)
        return datetime.datetime.fromtimestamp(stat.st_ctime)

    @property
    def modified(self):
        stat = os.stat(self.filename)
        return datetime.datetime.fromtimestamp(stat.st_mtime)

    @property
    def size_on_disk(self):
        stat = os.stat(self.filename)
        return stat.st_size

    def get_indexes(self, table):
        return dataset._database.get_indexes(table)

    def get_all_indexes(self):
        cursor = self.query(
            'SELECT name, sql FROM sqlite_master '
            'WHERE type = ? ORDER BY name',
            ('index',))
        '''
        return [
                IndexMetadata('TABLE_name', 'sql_sentence',none,none,none),
                IndexMetadata('TABLE_name', 'sql_sentence',none,none,none),
                ...
                IndexMetadata('TABLE_name', 'sql_sentence',none,none,none)
                ]
        '''
        return [IndexMetadata(row[0], row[1], None, None, None)
                for row in cursor.fetchall()]

    def get_columns(self, table):
        return dataset._database.get_columns(table)

    def get_foreign_keys(self, table):
        return dataset._database.get_foreign_keys(table)

    def get_triggers(self, table):
        cursor = self.query(
            'SELECT name, sql FROM sqlite_master '
            'WHERE type = ? AND tbl_name = ?',
            ('trigger', table))
        return [TriggerMetadata(*row) for row in cursor.fetchall()]

    def get_all_triggers(self):
        cursor = self.query(
            'SELECT name, sql FROM sqlite_master '
            'WHERE type = ? ORDER BY name',
            ('trigger',))
        return [TriggerMetadata(*row) for row in cursor.fetchall()]

    def get_all_views(self):
        cursor = self.query(
            'SELECT name, sql FROM sqlite_master '
            'WHERE type = ? ORDER BY name',
            ('view',))
        return [ViewMetadata(*row) for row in cursor.fetchall()]

    def get_virtual_tables(self):
        cursor = self.query(
            'SELECT name FROM sqlite_master '
            'WHERE type = ? AND sql LIKE ? '
            'ORDER BY name',
            ('table', 'CREATE VIRTUAL TABLE%'))
        return set([row[0] for row in cursor.fetchall()])

    def get_corollary_virtual_tables(self):
        virtual_tables = self.get_virtual_tables()
        suffixes = ['content', 'docsize', 'segdir', 'segments', 'stat']
        return set(
            '%s_%s' % (virtual_table, suffix) for suffix in suffixes
            for virtual_table in virtual_tables)

#
# Flask views.
#
@app.template_filter('url_encoder')
def url_encoder(strs):
    return urllib.parse.quote(strs)

@app.template_filter('error_newline')
def error_newline(strs):
    return strs.replace('#$#','<br>')


@app.route('/')
def index():
    return render_template('index.html')



@app.errorhandler(404)
def page404(e):
    error_mes='You have been redirected to homepage because an error occurs, please see the detail:#$# %s'%(e)
    print(error_mes)
    flash(error_mes)
    return redirect(url_for('index'))

@app.errorhandler(500)
def page500(e):
    error_mes='You have been redirected to homepage because an error occurs, please see the detail:#$# %s'%(e)
    print(error_mes)
    flash(error_mes)
    return redirect(url_for('index'))


def require_table(fn):
    @wraps(fn)
    def inner(table, *args, **kwargs):
        if table not in dataset.tables:
            flash('No table named %s, you have been redirected to homepage'%(table))
            return redirect(url_for('index'))
        return fn(table, *args, **kwargs)
    return inner


@app.route('/<table>/content/')
@require_table
def table_content(table):
    global special_characters
    page_number = request.args.get('page') or ''
    page_number = int(page_number) if page_number.isdigit() else 1

    ds_table = dataset[table]
    total_rows = ds_table.all().count()
    rows_per_page = app.config['ROWS_PER_PAGE']
    total_pages = int(math.ceil(total_rows / float(rows_per_page)))
    # Restrict bounds.
    page_number = min(page_number, total_pages)
    page_number = max(page_number, 1)

    previous_page = page_number - 1 if page_number > 1 else None
    next_page = page_number + 1 if page_number < total_pages else None
    

    return render_template(
        'table_content.html',
        columns=columns,
        ds_table=ds_table,
        field_names=field_names,
        next_page=next_page,
        ordering=ordering,
        page=page_number,
        previous_page=previous_page,
        query=query,
        table=table,
        total_pages=total_pages,
        total_rows=total_rows,
        special_characters=special_characters)

@app.route('/<table>/content/filtered/', methods=['GET','POST'])
@require_table
def filter_content(table):
    global special_characters
    ds_table = dataset[table]
    field_names = ds_table.columns
    model_meta = ds_table.model_class._meta
    rows_per_page = app.config['ROWS_PER_PAGE']
    try:
        fields = model_meta.sorted_fields
    except AttributeError:
        fields = model_meta.get_fields()
    if peewee_version >= (3, 0, 0):
        columns = [field.column_name for field in fields]
    else:
        columns = [field.db_column for field in fields]

    if request.method=="GET":
        print(str(request.path))
        page_number=request.args.get('page',None)
        if not page_number:
            return redirect(url_for('table_content', table=table))
        print(page_number)
        arg_values=request.args
        sql_query='SELECT * FROM %s WHERE '%(table)
        
        cols_and_values={}
        for k in arg_values:
            if k != 'page':
                sql_query=sql_query+"(\"%s\" LIKE '%%%s%%' ESCAPE '/') AND "%(k,format_str(arg_values[k]))
                cols_and_values[k]=arg_values[k]
        sql_query=sql_query.strip(' AND ')
        print(sql_query)
        filtered_values=dataset.query(sql_query).fetchall()
        total_rows=len(filtered_values)
        
        total_pages = int(math.ceil(total_rows / float(rows_per_page)))
        page_number=int(page_number)
        next_page=None if total_pages<=page_number else page_number+1
        previous_page=page_number-1 if page_number>1 else None

        start_index=(page_number-1)*rows_per_page
        end_index=min(start_index+rows_per_page,len(filtered_values))
        filtered_values_in_range=filtered_values[start_index:end_index]    
        return render_template(
            'table_content_filtered.html',
            # filtered_values=filtered_values,
            filtered_values_in_range=filtered_values_in_range,
            columns=columns,
            next_page=next_page,
            page=page_number,
            previous_page=previous_page,
            table=table,
            cols_and_values=cols_and_values,
            total_pages=total_pages,
            total_rows=total_rows,
            form_values=cols_and_values,
            special_characters=special_characters)


        
    

    else:
        form_values=request.form
        print("POST Form values: ",form_values)
        cols=[]
        values=[]
        for c in columns:
            if form_values[c] != '':
                cols.append(c)
                values.append(form_values[c])

        
        if cols and values:
            cols_and_values=dict(zip(cols,values))
            temp1=['"%s"'%(c) for c in cols]
            temp2=["'%%%s%%'"%(format_str(v)) for v in values]
            temp=['('+temp1[t]+" LIKE "+temp2[t]+"ESCAPE '/' )" for t in range(len(temp1))]
            temp_str=" AND ".join(temp)
            sql_query="SELECT * FROM %s WHERE %s "%(table, temp_str)
            print(sql_query)
            filtered_values=dataset.query(sql_query).fetchall()
            total_rows=len(filtered_values)
            page_number=1
            total_pages = int(math.ceil(total_rows / float(rows_per_page)))
            if total_pages<=1:
                next_page=None
            else:
                next_page=page_number+1
            start_index=(page_number-1)*rows_per_page
            end_index=min(start_index+rows_per_page,len(filtered_values))
            filtered_values_in_range=filtered_values[start_index:end_index]
            return render_template(
                'table_content_filtered.html',
                # filtered_values=filtered_values,
                filtered_values_in_range=filtered_values_in_range,
                columns=columns,
                next_page=next_page,
                page=page_number,
                previous_page=None,
                table=table,
                cols_and_values=cols_and_values,
                total_pages=total_pages,
                total_rows=total_rows,
                form_values=form_values,
                special_characters=special_characters)


        else:
            return redirect(url_for('table_content', table=table))

    
    return redirect(url_for('table_content', table=table))


@app.route('/<table>/content/filtered/<row_index>/', methods=['GET', 'POST'])
@app.route('/<table>/content/<row_index>/', methods=['GET', 'POST'])
@require_table
def row_detail(table,row_index):
    global special_characters
    ds_table = dataset[table]
    path=str(request.path)
    page=request.args.get('page',1)
    ordering=request.args.get('ordering',None)
    if '/content/filtered/' in path:
        return redirect(url_for('row_detail', table=table,row_index=row_index)) 

    try:
        idx=int(row_index)
        error_message="No such row index"
    except:
        return redirect(url_for('table_content', table=table)) 
    sql_select_by_index='SELECT * FROM %s WHERE %s >= %s'%(table,"ID_unique_number",idx)
    # columns=ds_table.columns
    field_names = ds_table.columns
    model_meta = ds_table.model_class._meta
    try:
        fields = model_meta.sorted_fields
    except AttributeError:
        fields = model_meta.get_fields()
    if peewee_version >= (3, 0, 0):
        columns = [field.column_name for field in fields]
    else:
        columns = [field.db_column for field in fields]
    try:
        current_row=dataset.query(sql_select_by_index).fetchone()
    except:
        return redirect(url_for('table_content', table=table))
    if not current_row:
        return redirect(url_for('table_content', table=table))
    current_row_data=dict(zip(columns,current_row))
    # print(current_row_data)
    if request.method == 'POST':
        print("POST")
        return redirect(url_for('table_content', table=table))

    # current_row=
    return render_template('table_row_detail.html',
        ds_table=ds_table,
        columns=columns,
        idx=idx,
        table=table,
        current_row_data=current_row_data,
        current_row=current_row,
        page=page,
        ordering=ordering,
        special_characters=special_characters)

@app.route('/<table>/content/<row_index>/UPDATE/', methods=['POST'])
@require_table
def update_row(table,row_index):
    ds_table = dataset[table]
    field_names = ds_table.columns
    model_meta = ds_table.model_class._meta
    try:
        fields = model_meta.sorted_fields
    except AttributeError:
        fields = model_meta.get_fields()
    if peewee_version >= (3, 0, 0):
        columns = [field.column_name for field in fields]
    else:
        columns = [field.db_column for field in fields]

    try:
        idx=int(row_index)
    except:
        return redirect(url_for('table_content', table=table))

    form_values=request.form
    col_names=[c for c in columns if c != "ID_unique_number"]
    values=["'"+escape_single_quote(form_values[c])+"'" for c in col_names]
    col_names=["'"+c+"'" for c in col_names]
    col_and_value=dict(zip(col_names,values))
    temp_list=[v+' = '+col_and_value[v] for v in col_and_value]
    sql_update_by_index='UPDATE %s SET %s WHERE ID_unique_number = %s'%(table, ','.join(temp_list), idx)
    dataset.query(sql_update_by_index)
    page=request.form.get('hidden_page',1)
    ordering= request.form.get('hidden_ordering',None)
    if (ordering is not None) and str(ordering).upper()!='NONE':
        return redirect(url_for('table_content', table=table, page=page,ordering=ordering))
    return redirect(url_for('table_content', table=table, page=page))





@app.route('/<table>/content/<row_index>/DELETE/', methods=['POST'])
@require_table
def del_row(table,row_index):
    ds_table = dataset[table]

    try:
        idx=int(row_index)
    except:
        print("delete2")
        return redirect(url_for('table_content', table=table))
    sql_delete_by_index='DELETE FROM %s WHERE ID_unique_number = %s'%(table,idx)
    dataset.query(sql_delete_by_index)
    print('Delete')
    page=request.form.get('hidden_page',1)
    ordering= request.form.get('hidden_ordering',None)
    if (ordering is not None) and str(ordering).upper()!='NONE':
        return redirect(url_for('table_content', table=table, page=page,ordering=ordering))
    return redirect(url_for('table_content', table=table,page=page))

# @app.route('/<table>/INSERT/', methods=['GET','POST'])
@app.route('/<table>/content/INSERT/', methods=['GET','POST'])
@require_table
def insert_row(table):
    global special_characters
    ds_table = dataset[table]
    field_names = ds_table.columns
    model_meta = ds_table.model_class._meta
    page=request.args.get('page',1)
    totalpage=request.args.get('totalpage',None)
    ordering=request.args.get('ordering',None)
    if str(ordering)=="None":
        ordering=None
    try:
        fields = model_meta.sorted_fields
    except AttributeError:
        fields = model_meta.get_fields()
    if peewee_version >= (3, 0, 0):
        columns = [field.column_name for field in fields]
    else:
        columns = [field.db_column for field in fields]
    if request.method=="POST":
        
        except_list=["ID_unique_number",'hidden_page','hidden_totalpage']
        cols=[c for c in columns if c not in except_list]
        form_values=request.form
        values=["'"+escape_single_quote(form_values[c])+"'" for c in cols]
        cols=["'"+c+"'" for c in cols]
        sql_insert_row='INSERT INTO %s (%s) VALUES (%s)'%(table,','.join(cols),','.join(values))
        dataset.query(sql_insert_row)
        print('INSERT(POST) finished, redirect to last page')
        return redirect(url_for('table_content', table=table, page=form_values['hidden_totalpage']))
    else:
        print(str(request.path))
        return render_template('table_insert.html',
            table=table,
            columns=columns,
            page=page,
            totalpage=totalpage,
            ordering=ordering,
            special_characters=special_characters)



















#
# Flask application helpers.
#

@app.context_processor
def _general():
    return {'dataset': dataset}

@app.context_processor
def _now():
    return {'now': datetime.datetime.now()}

@app.before_request
def _connect_db():
    dataset.connect()

@app.teardown_request
def _close_db(exc):
    if not dataset._database.is_closed():
        dataset.close()

#
# Script options.
#

def get_option_parser():
    parser = optparse.OptionParser()
    parser.add_option(
        '-p',
        '--port',
        default=8010,
        help='Port for web interface, default=8080',
        type='int')
    parser.add_option(
        '-H',
        '--host',
        default='127.0.0.1',
        help='Host for web interface, default=127.0.0.1')
    parser.add_option(
        '-d',
        '--debug',
        action='store_true',
        help='Run server in debug mode')
    parser.add_option(
        '-x',
        '--no-browser',
        action='store_false',
        default=True,
        dest='browser',
        help='Do not automatically open browser page.')
    return parser

def die(msg, exit_code=1):
    sys.stderr.write('%s\n' % msg)
    sys.stderr.flush()
    sys.exit(exit_code)

def open_browser_tab(host, port):

    url = 'http://%s:%s/' % (host, port)

    def _open_tab(url):
        time.sleep(1)
        webbrowser.open_new_tab(url)

    thread = threading.Thread(target=_open_tab, args=(url,))
    thread.daemon = True
    thread.start()

def main():
    # This function exists to act as a console script entry-point.
    parser = get_option_parser()
    options, args = parser.parse_args()
    # if not args:
    #     die('Error: missing required path to database file.')

    db_file = 'test.sqlite3'
    global dataset
    global migrator
    if peewee_version >= (3, 0, 0):
        dataset_kwargs = {'bare_fields': True}
    else:
        dataset_kwargs = {}
    dataset = SqliteDataSet('sqlite:///%s' % db_file, **dataset_kwargs)
    migrator = dataset._migrator
    dataset.close()
    if options.browser:
        import socket
        myname = socket.getfqdn(socket.gethostname())
        myaddr = socket.gethostbyname(myname)
        open_browser_tab(myaddr, 8010)
    app.run(host='0.0.0.0', port=8010, debug=options.debug)


if __name__ == '__main__':
    main()
